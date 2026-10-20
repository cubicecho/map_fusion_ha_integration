"""Line up a second vacuum's map with the anchor map on the same floor.

Pure Python. Both maps are already metric with y down (source adapters do
that), so the fit is rigid: a rotation plus a shift, no scaling. The
matching points are the centres of areas that both vacuums have linked to
the same HA area.

- 2 shared areas give an exact rotation and shift (residual ~0).
- 3 or more give a least-squares fit and a meaningful `residual_m`. A
  mirrored fit is also tried then, in case an adapter got an axis backwards;
  it only wins when clearly better.
- Fewer than 2, or a residual over `MAX_RESIDUAL_M`, means no alignment.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import centroid
from .model import Point, Rect, SourceMap, SourceRoom, Transform

MIN_SHARED = 2
MAX_RESIDUAL_M = 0.75
# A mirrored fit must beat the straight one by this factor to be used.
MIRROR_MARGIN = 0.5


@dataclass(slots=True)
class Fit:
    # Other map's source frame → anchor map's source frame.
    transform: Transform
    residual_m: float
    shared: list[str]  # area ids used
    mirrored: bool


@dataclass(slots=True)
class NoFit:
    reason: str


def area_centres(smap: SourceMap, area_mapping: dict[str, list[str]]) -> dict[str, Point]:
    """Centre of each linked area's rooms, in the map's source frame."""
    out: dict[str, Point] = {}
    for area_id, segment_ids in area_mapping.items():
        rings = [ring for s in segment_ids if s in smap.rooms for ring in smap.rooms[s].polygons]
        if rings:
            out[area_id] = centroid(rings)
    return out


def fit(
    anchor: dict[str, Point], other: dict[str, Point], *, max_residual_m: float = MAX_RESIDUAL_M
) -> Fit | NoFit:
    """Rigid transform taking `other` centres onto `anchor` centres."""
    shared = sorted(set(anchor) & set(other))
    if len(shared) < MIN_SHARED:
        return NoFit(f"{len(shared)} shared area(s), need {MIN_SHARED}")
    src = [other[a] for a in shared]
    dst = [anchor[a] for a in shared]
    best = _rigid(src, dst, mirrored=False)
    if len(shared) >= 3:
        flipped = _rigid(src, dst, mirrored=True)
        if flipped[1] < best[1] * MIRROR_MARGIN:
            best = flipped
    transform, residual, mirrored = best
    if residual > max_residual_m:
        return NoFit(f"shared areas don't line up (off by {residual:.2f} m)")
    return Fit(transform=transform, residual_m=residual, shared=shared, mirrored=mirrored)


def _rigid(src: list[Point], dst: list[Point], *, mirrored: bool) -> tuple[Transform, float, bool]:
    """Least-squares rotation + shift (2D Kabsch), optionally after mirroring x."""
    pts = [(-x, y) for x, y in src] if mirrored else src
    n = len(pts)
    sx = sum(p[0] for p in pts) / n
    sy = sum(p[1] for p in pts) / n
    dx = sum(p[0] for p in dst) / n
    dy = sum(p[1] for p in dst) / n
    dot = cross = 0.0
    for (px, py), (qx, qy) in zip(pts, dst, strict=True):
        ax, ay, bx, by = px - sx, py - sy, qx - dx, qy - dy
        dot += ax * bx + ay * by
        cross += ax * by - ay * bx
    theta = math.atan2(cross, dot)
    c, s = math.cos(theta), math.sin(theta)
    rot = Transform(a=c, b=-s, c=s, d=c, tx=dx - (c * sx - s * sy), ty=dy - (s * sx + c * sy))
    transform = Transform(a=-1.0).then(rot) if mirrored else rot
    errs = [_dist2(transform.apply(p), q) for p, q in zip(src, dst, strict=True)]
    return transform, math.sqrt(sum(errs) / n), mirrored


def moved(smap: SourceMap, t: Transform) -> SourceMap:
    """The map with its rooms carried into another frame by `t`.

    `to_native` is adjusted so native coordinates still come out right.
    """
    rooms = {sid: _moved_room(room, t) for sid, room in smap.rooms.items()}
    return SourceMap(
        source_id=smap.source_id,
        kind=smap.kind,
        map_id=smap.map_id,
        map_name=smap.map_name,
        rooms=rooms,
        to_native=t.inverse().then(smap.to_native),
        native_residual_m=smap.native_residual_m,
        warnings=list(smap.warnings),
    )


def _moved_room(room: SourceRoom, t: Transform) -> SourceRoom:
    polygons = [[t.apply(p) for p in ring] for ring in room.polygons]
    return SourceRoom(
        segment_id=room.segment_id,
        name=room.name,
        polygons=polygons,
        rect=Rect.from_points([p for ring in polygons for p in ring]),
        label_point=t.apply(room.label_point),
        area_m2=room.area_m2,
        geometry=room.geometry,
    )


def _dist2(a: Point, b: Point) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
