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

from .const import SCHEMA_VERSION
from .model import (
    FusedArea,
    FusedFrame,
    FusedMap,
    Geometry,
    Point,
    Rect,
    SourceMap,
    SourceRoom,
    Transform,
)

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


def build(
    sources: list[SourceInput],
    areas: dict[str, AreaInfo],
    floor_names: dict[str, str],
    origins: dict[str, FrameOrigin],
    generated_at: str,
) -> BuildResult:
    new_origins = dict(origins)
    frames: list[FusedFrame] = []
    used_frame_ids: set[str] = set()
    placed: set[str] = set()

    for src in sorted(sources, key=lambda s: s.map.key):
        smap = src.map
        floor_id = _floor_for(src, areas)
        frame_id = floor_id if floor_id and floor_id not in used_frame_ids else smap.key
        used_frame_ids.add(frame_id)
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

        frame = _build_frame(src, areas, frame_id, floor_id, name, -ox, -oy)
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
    return BuildResult(fused=fused, origins=new_origins)


def _build_frame(
    src: SourceInput,
    areas: dict[str, AreaInfo],
    frame_id: str,
    floor_id: str | None,
    name: str,
    dx: float,
    dy: float,
) -> FusedFrame:
    smap = src.map
    fused_areas: list[FusedArea] = []
    linked: set[str] = set()
    for area_id, segment_ids in sorted(src.area_mapping.items()):
        info = areas.get(area_id)
        rooms = [smap.rooms[s] for s in segment_ids if s in smap.rooms]
        if info is None or not rooms:
            continue
        linked.update(r.segment_id for r in rooms)
        fused_areas.append(_area(info, rooms, smap, dx, dy))

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
