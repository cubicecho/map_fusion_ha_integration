"""Build the fused map from source maps, area links and stored origins.

Pure Python, no Home Assistant imports: the manager gathers the inputs.

Frames: one per HA floor, or one per vacuum map when its areas have no
floor. Phase 1 has no alignment between vacuums, so a second vacuum map on
a floor that already has one gets its own frame for now.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from . import placements as pl
from .const import SCHEMA_VERSION
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

    # 1. Which frame each source map goes in.
    assigned: list[tuple[SourceInput, str, str | None]] = []
    used_frame_ids: set[str] = set()
    for src in sorted(sources, key=lambda s: s.map.key):
        key = src.map.key
        chosen = choices.get(key, "")
        if key in choices and (chosen is None or chosen in floor_names):
            floor_id = chosen
        else:  # no choice, or the chosen floor was deleted
            floor_id = _floor_for(src, areas)
        frame_id = floor_id if floor_id and floor_id not in used_frame_ids else key
        used_frame_ids.add(frame_id)
        assigned.append((src, frame_id, floor_id))

    # 2. Origins and placements follow their source to its frame id.
    for src, frame_id, _floor in assigned:
        _migrate(src.map.key, frame_id, used_frame_ids, new_origins, new_placements)

    # 3. Frames.
    frames: list[FusedFrame] = []
    placed: set[str] = set()
    for src, frame_id, floor_id in assigned:
        smap = src.map
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
        frame = _build_frame(
            src, areas, frame_id, floor_id, name, -ox, -oy, new_placements.get(frame_id, {})
        )
        placed.update(a.area_id for a in frame.areas)
        frames.append(frame)

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
    src: SourceInput,
    areas: dict[str, AreaInfo],
    frame_id: str,
    floor_id: str | None,
    name: str,
    dx: float,
    dy: float,
    manual: dict[str, list[Ring]],
) -> FusedFrame:
    smap = src.map
    by_area: dict[str, FusedArea] = {}
    linked: set[str] = set()
    for area_id, segment_ids in src.area_mapping.items():
        info = areas.get(area_id)
        rooms = [smap.rooms[s] for s in segment_ids if s in smap.rooms]
        if info is None or not rooms:
            continue
        linked.update(r.segment_id for r in rooms)
        by_area[area_id] = _area(info, rooms, smap, dx, dy)
    # A user placement replaces the vacuum's shape for that area.
    by_area.update(_manual_areas(areas, manual))
    fused_areas = [by_area[k] for k in sorted(by_area)]

    unmapped = [
        {
            "source_id": smap.source_id,
            "segment_id": room.segment_id,
            "name": room.name,
            "polygons": [_ring_dict(_shift(r, dx, dy)) for r in room.polygons],
            "rect": room.rect.shifted(dx, dy).as_dict(),
        }
        for room in sorted(smap.rooms.values(), key=lambda r: r.segment_id)
        if room.segment_id not in linked
    ]

    rects = [a.rect for a in fused_areas] + [
        r.rect.shifted(dx, dy) for r in smap.rooms.values() if r.segment_id not in linked
    ]
    # native → frame: undo to_native, then shift.
    native_to_frame = smap.to_native.inverse().then(Transform(tx=dx, ty=dy))
    return FusedFrame(
        frame_id=frame_id,
        floor_id=floor_id,
        name=name,
        bounds=Rect.union(rects) if rects else None,
        areas=fused_areas,
        unmapped_rooms=unmapped,
        overlaps=_overlaps(fused_areas),
        sources=[
            {
                "source_id": smap.source_id,
                "kind": smap.kind,
                "map_id": smap.map_id,
                "map_name": smap.map_name,
                "role": "anchor",
                "transform": native_to_frame.as_list(),
                "residual_m": None if smap.native_residual_m is None else round(smap.native_residual_m, 4),
                "warnings": smap.warnings,
            }
        ],
    )


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
    """Box overlaps between areas when at least one is only a box.

    Traced outlines don't overlap, so pairs of `pixels` areas are skipped.
    """
    out: list[dict[str, Any]] = []
    for i, a in enumerate(areas):
        for b in areas[i + 1 :]:
            if a.geometry == "pixels" and b.geometry == "pixels":
                continue
            inter = a.rect.intersection(b.rect)
            if inter and inter.width * inter.height >= MIN_OVERLAP_M2:
                out.append(
                    {
                        "a": a.area_id,
                        "b": b.area_id,
                        "rect": inter.as_dict(),
                        "m2": round(inter.width * inter.height, 2),
                    }
                )
    return out


def _shift(ring: list[Point], dx: float, dy: float) -> list[Point]:
    return [(x + dx, y + dy) for x, y in ring]


def _ring_dict(ring: list[Point]) -> list[list[float]]:
    return [[round(x, 3) + 0.0, round(y, 3) + 0.0] for x, y in ring]
