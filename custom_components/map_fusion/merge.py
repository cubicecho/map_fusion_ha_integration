"""Build the fused map from source maps, area links and stored origins.

Pure Python, no Home Assistant imports: the manager gathers the inputs.

Frames: one per HA floor, or one per vacuum map when its areas have no
floor. Each frame has one anchor map; other maps whose areas match the
anchor's (2+ shared areas, see align.py) are lined up with it and join the
frame. Maps that can't be lined up get their own frame.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from . import placements as pl
from .align import Fit, area_centres, fit, moved
from .const import SCHEMA_VERSION
from .geometry import iou, overlap
from .model import (
    FusedArea,
    FusedFrame,
    FusedMap,
    Geometry,
    Point,
    Rect,
    Ring,
    SourceMap,
    SourceRoom,
    Transform,
)
from .placements import Placements

MIN_OVERLAP_M2 = 0.01


@dataclass(slots=True)
class AreaInfo:
    area_id: str
    name: str
    floor_id: str | None


@dataclass(slots=True)
class SourceInput:
    map: SourceMap
    # The user's links: area_id → segment ids (core vacuum area_mapping).
    area_mapping: dict[str, list[str]]


@dataclass(slots=True)
class FrameOrigin:
    """Where a frame's (0, 0) sits in its anchor source's frame."""

    anchor: str  # SourceMap.key
    origin: Point


@dataclass(slots=True)
class _Group:
    """One frame being built: its anchor map and the maps lined up with it."""

    frame_id: str
    floor_id: str | None
    anchor: SourceInput
    aligned: list[tuple[SourceInput, Fit]] = field(default_factory=list)


@dataclass(slots=True)
class BuildResult:
    fused: FusedMap
    # Origins to store: existing ones plus any new frames.
    origins: dict[str, FrameOrigin] = field(default_factory=dict)
    # Placements to store (moved along when a frame id changed).
    placements: Placements = field(default_factory=dict)


def build(
    sources: list[SourceInput],
    areas: dict[str, AreaInfo],
    floor_names: dict[str, str],
    origins: dict[str, FrameOrigin],
    generated_at: str,
    placements: Placements | None = None,
    floor_choices: dict[str, str | None] | None = None,
) -> BuildResult:
    """Build the fused map.

    `placements` are the user's shapes by frame. `floor_choices` pins a
    source map (by `SourceMap.key`) to a floor, or to no floor (None);
    maps not listed pick their floor by majority vote.

    When a map moves to another frame id (its areas got a floor, or a floor
    choice changed), its stored origin and placements move with it. The
    result carries the updated origins and placements for the caller to store.
    """
    new_origins = dict(origins)
    new_placements: Placements = {f: dict(a) for f, a in (placements or {}).items()}
    choices = floor_choices or {}

    # 1. Which frame each source map goes in. Maps that anchored a frame
    # before go first, so anchors (and stored origins) stay put.
    stored_anchors = {o.anchor for o in origins.values()}
    ordered = sorted(
        sources, key=lambda s: (s.map.key not in stored_anchors, -len(_linked(s)), s.map.key)
    )
    groups: list[_Group] = []
    notes: dict[str, list[str]] = {}
    used_frame_ids: set[str] = set()
    for src in ordered:
        key = src.map.key
        chosen = choices.get(key, "")
        if key in choices and (chosen is None or chosen in floor_names):
            floor_id = chosen
        else:  # no choice, or the chosen floor was deleted
            floor_id = _floor_for(src, areas)
        if _join_group(src, floor_id, groups, notes):
            continue
        frame_id = floor_id if floor_id and floor_id not in used_frame_ids else key
        used_frame_ids.add(frame_id)
        groups.append(_Group(frame_id=frame_id, floor_id=floor_id, anchor=src))

    # 2. Origins and placements follow their anchor to its frame id.
    for group in groups:
        _migrate(group.anchor.map.key, group.frame_id, used_frame_ids, new_origins, new_placements)

    # 3. Frames.
    frames: list[FusedFrame] = []
    placed: set[str] = set()
    for group in groups:
        smap = group.anchor.map
        floor_id, frame_id = group.floor_id, group.frame_id
        name = (
            floor_names.get(floor_id, floor_id)
            if floor_id and frame_id == floor_id
            else smap.map_name or smap.key
        )
        stored = new_origins.get(frame_id)
        if stored is None or stored.anchor != smap.key:
            stored = FrameOrigin(anchor=smap.key, origin=_default_origin(smap))
            new_origins[frame_id] = stored
        ox, oy = stored.origin
        frame = _build_frame(group, areas, name, -ox, -oy, new_placements.get(frame_id, {}), notes)
        placed.update(a.area_id for a in frame.areas)
        frames.append(frame)
    frames.sort(key=lambda f: [g.frame_id for g in groups].index(f.frame_id))

    # Floors with placements but no vacuum: a frame of placements only.
    for frame_id in sorted(set(new_placements) - used_frame_ids):
        if frame_id not in floor_names:
            continue  # its vacuum is missing right now; keep the placements
        frame = _manual_frame(frame_id, floor_names[frame_id], areas, new_placements[frame_id])
        if frame.areas:
            placed.update(a.area_id for a in frame.areas)
            frames.append(frame)

    unplaced = [
        {"area_id": a.area_id, "name": a.name, "floor_id": a.floor_id}
        for a in sorted(areas.values(), key=lambda a: a.name.lower())
        if a.area_id not in placed
    ]
    fused = FusedMap(
        version=SCHEMA_VERSION, generated_at=generated_at, frames=frames, unplaced_areas=unplaced
    )
    return BuildResult(fused=fused, origins=new_origins, placements=new_placements)


def _linked(src: SourceInput) -> set[str]:
    """Areas this map has at least one room for."""
    return {a for a, segs in src.area_mapping.items() if any(s in src.map.rooms for s in segs)}


def _join_group(
    src: SourceInput, floor_id: str | None, groups: list[_Group], notes: dict[str, list[str]]
) -> bool:
    """Line `src` up with an existing frame on the same floor, if possible."""
    centres = area_centres(src.map, src.area_mapping)
    for group in groups:
        if group.floor_id != floor_id:
            continue
        anchor = group.anchor
        result = fit(area_centres(anchor.map, anchor.area_mapping), centres)
        if isinstance(result, Fit):
            group.aligned.append((SourceInput(moved(src.map, result.transform), src.area_mapping), result))
            return True
        notes.setdefault(src.map.key, []).append(f"Not lined up with {anchor.map.key}: {result.reason}")
    return False


def _migrate(
    key: str,
    frame_id: str,
    used_frame_ids: set[str],
    origins: dict[str, FrameOrigin],
    placements: Placements,
) -> None:
    """Move a source's stored frame (origin + placements) to its new id."""
    for old_id, origin in list(origins.items()):
        if old_id == frame_id or origin.anchor != key or old_id in used_frame_ids:
            continue
        current = origins.get(frame_id)
        if current is None or current.anchor != key:
            origins[frame_id] = origin
        del origins[old_id]
        moved = placements.pop(old_id, None)
        if moved:
            # Placements already under the new id win.
            placements[frame_id] = {**moved, **placements.get(frame_id, {})}


def _build_frame(
    group: _Group,
    areas: dict[str, AreaInfo],
    name: str,
    dx: float,
    dy: float,
    manual: dict[str, list[Ring]],
    notes: dict[str, list[str]],
) -> FusedFrame:
    members: list[tuple[SourceInput, Fit | None]] = [(group.anchor, None), *group.aligned]
    by_area: dict[str, FusedArea] = {}
    unmapped: list[dict[str, Any]] = []
    rects: list[Rect] = []
    frame_sources: list[dict[str, Any]] = []
    for src, fitted in members:
        smap = src.map
        linked: set[str] = set()
        for area_id, segment_ids in src.area_mapping.items():
            info = areas.get(area_id)
            rooms = [smap.rooms[s] for s in segment_ids if s in smap.rooms]
            if info is None or not rooms:
                continue
            linked.update(r.segment_id for r in rooms)
            area = _area(info, rooms, smap, dx, dy)
            existing = by_area.get(area_id)
            if existing is None:
                by_area[area_id] = area
                continue
            # Seen by an earlier map (the anchor wins the shape): record agreement.
            existing.sources.extend(area.sources)
            agreement = iou(existing.polygons, area.polygons)
            existing.confidence = (
                agreement if existing.confidence is None else min(existing.confidence, agreement)
            )
        for room in sorted(smap.rooms.values(), key=lambda r: r.segment_id):
            if room.segment_id in linked:
                continue
            unmapped.append(
                {
                    "source_id": smap.source_id,
                    "segment_id": room.segment_id,
                    "name": room.name,
                    "polygons": [_ring_dict(_shift(r, dx, dy)) for r in room.polygons],
                    "filled_polygons": [
                        _ring_dict(_shift(r, dx, dy)) for r in (room.filled or room.polygons)
                    ],
                    "rect": room.rect.shifted(dx, dy).as_dict(),
                }
            )
            rects.append(room.rect.shifted(dx, dy))
        frame_sources.append(_source_entry(smap, fitted, dx, dy, notes.get(smap.key, [])))

    # A user placement replaces the vacuums' shape for that area.
    by_area.update(_manual_areas(areas, manual))
    fused_areas = [by_area[k] for k in sorted(by_area)]
    rects += [a.rect for a in fused_areas]
    return FusedFrame(
        frame_id=group.frame_id,
        floor_id=group.floor_id,
        name=name,
        bounds=Rect.union(rects) if rects else None,
        areas=fused_areas,
        unmapped_rooms=unmapped,
        overlaps=_overlaps(fused_areas),
        sources=frame_sources,
    )


def _source_entry(
    smap: SourceMap, fitted: Fit | None, dx: float, dy: float, notes: list[str]
) -> dict[str, Any]:
    # native → frame: undo to_native, then shift.
    native_to_frame = smap.to_native.inverse().then(Transform(tx=dx, ty=dy))
    entry: dict[str, Any] = {
        "source_id": smap.source_id,
        "kind": smap.kind,
        "map_id": smap.map_id,
        "map_name": smap.map_name,
        "role": "anchor" if fitted is None else "aligned",
        "transform": native_to_frame.as_list(),
        "residual_m": None if smap.native_residual_m is None else round(smap.native_residual_m, 4),
        "warnings": [*smap.warnings, *notes],
    }
    if fitted is not None:
        # For aligned maps the residual is how well they line up with the anchor.
        entry["residual_m"] = round(fitted.residual_m, 4)
        entry["shared_areas"] = fitted.shared
        if fitted.mirrored:
            entry["warnings"].append("Map was mirrored to line up; check the vacuum's axes")
    return entry


def _manual_frame(
    frame_id: str, name: str, areas: dict[str, AreaInfo], manual: dict[str, list[Ring]]
) -> FusedFrame:
    """A floor with no vacuum: only the user's placements, origin (0, 0)."""
    by_area = _manual_areas(areas, manual)
    fused_areas = [by_area[k] for k in sorted(by_area)]
    return FusedFrame(
        frame_id=frame_id,
        floor_id=frame_id,
        name=name,
        bounds=Rect.union([a.rect for a in fused_areas]) if fused_areas else None,
        areas=fused_areas,
        unmapped_rooms=[],
        overlaps=_overlaps(fused_areas),
        sources=[],
    )


def _manual_areas(areas: dict[str, AreaInfo], manual: dict[str, list[Ring]]) -> dict[str, FusedArea]:
    out: dict[str, FusedArea] = {}
    for area_id, rings in manual.items():
        info = areas.get(area_id)
        if info is None or not rings:
            continue  # area deleted; the manager prunes these
        out[area_id] = FusedArea(
            area_id=area_id,
            name=info.name,
            polygons=rings,
            rect=pl.bounds(rings),
            label_point=pl.label_point(rings),
            area_m2=pl.area_m2(rings),
            origin="manual",
            geometry="manual",
            sources=[],
        )
    return out


def _area(info: AreaInfo, rooms: list[SourceRoom], smap: SourceMap, dx: float, dy: float) -> FusedArea:
    rooms = sorted(rooms, key=lambda r: r.area_m2, reverse=True)
    polygons = [_shift(ring, dx, dy) for room in rooms for ring in room.polygons]
    biggest = rooms[0]
    geometry: Geometry = "pixels" if all(r.geometry == "pixels" for r in rooms) else "bbox"
    return FusedArea(
        area_id=info.area_id,
        name=info.name,
        polygons=polygons,
        rect=Rect.union([r.rect.shifted(dx, dy) for r in rooms]),
        label_point=(biggest.label_point[0] + dx, biggest.label_point[1] + dy),
        area_m2=sum(r.area_m2 for r in rooms),
        origin="vacuum",
        geometry=geometry,
        sources=[
            {"source_id": smap.source_id, "map_id": smap.map_id, "segment_id": r.segment_id}
            for r in rooms
        ],
        filled_polygons=[_shift(ring, dx, dy) for room in rooms for ring in (room.filled or room.polygons)],
        filled_m2=sum(r.area_m2 if r.filled_m2 is None else r.filled_m2 for r in rooms),
    )


def _floor_for(src: SourceInput, areas: dict[str, AreaInfo]) -> str | None:
    """Majority floor of the areas linked to rooms on this map."""
    counts: Counter[str] = Counter()
    for area_id, segment_ids in src.area_mapping.items():
        info = areas.get(area_id)
        if info and info.floor_id and any(s in src.map.rooms for s in segment_ids):
            counts[info.floor_id] += 1
    if not counts:
        return None
    (best, n), *rest = counts.most_common()
    if rest and rest[0][1] == n:
        return None  # tie: let the user choose (phase 2)
    return best


def _default_origin(smap: SourceMap) -> Point:
    """Top-left of all rooms, so a new frame starts at (0, 0)."""
    if not smap.rooms:
        return (0.0, 0.0)
    r = Rect.union([room.rect for room in smap.rooms.values()])
    return (r.x, r.y)


def _overlaps(areas: list[FusedArea]) -> list[dict[str, Any]]:
    """Areas whose shapes overlap (measured on a 5 cm grid).

    Outlines traced from one vacuum never overlap, so those pairs are
    skipped. Boxes, manual shapes and shapes from different vacuums can.
    """
    out: list[dict[str, Any]] = []
    for i, a in enumerate(areas):
        for b in areas[i + 1 :]:
            if a.geometry == "pixels" and b.geometry == "pixels" and _source_of(a) == _source_of(b):
                continue
            inter = a.rect.intersection(b.rect)
            if inter is None or inter.width * inter.height < MIN_OVERLAP_M2:
                continue
            _, _, both = overlap(a.polygons, b.polygons, box=inter)
            if both >= MIN_OVERLAP_M2:
                out.append({"a": a.area_id, "b": b.area_id, "rect": inter.as_dict(), "m2": round(both, 2)})
    return out


def _source_of(area: FusedArea) -> str | None:
    return area.sources[0]["source_id"] if area.sources else None


def _shift(ring: list[Point], dx: float, dy: float) -> list[Point]:
    return [(x + dx, y + dy) for x, y in ring]


def _ring_dict(ring: list[Point]) -> list[list[float]]:
    return [[round(x, 3) + 0.0, round(y, 3) + 0.0] for x, y in ring]
