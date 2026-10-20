"""User-placed area shapes: checking and tidying them. Pure Python.

A placement is one or more rings in a frame's coordinates (metres, y down).
A rectangle is stored as one 4-point ring.
"""
from __future__ import annotations

import math
from typing import Any

from .geometry import point_in_ring, signed_area
from .model import Point, Rect, Ring

# frame_id → area_id → rings
Placements = dict[str, dict[str, list[Ring]]]

MAX_RINGS = 20
MAX_POINTS = 1000
MAX_COORD_M = 10_000.0
MIN_AREA_M2 = 0.0001  # 1 cm²


class InvalidPlacement(ValueError):
    """The shape can't be used. The message says why, for the user."""


def rect_ring(x: float, y: float, width: float, height: float) -> Ring:
    """A rectangle as a clockwise-on-screen ring."""
    if not (width > 0 and height > 0):
        raise InvalidPlacement("width and height must be greater than 0")
    return normalise([[(x, y), (x + width, y), (x + width, y + height), (x, y + height)]])[0]


def normalise(polygons: Any) -> list[Ring]:
    """Check user rings and return them tidied: clockwise, largest first.

    Accepts `[[[x, y], ...], ...]`. Drops a repeated closing point and
    repeated neighbours. Rejects rings with fewer than 3 points, no area,
    or edges that cross.
    """
    if not isinstance(polygons, list | tuple) or not polygons:
        raise InvalidPlacement("polygons must be a non-empty list of rings")
    if len(polygons) > MAX_RINGS:
        raise InvalidPlacement(f"at most {MAX_RINGS} rings are allowed")
    rings: list[Ring] = []
    total = 0
    for index, raw in enumerate(polygons, start=1):
        ring = _ring(raw, index)
        total += len(ring)
        if total > MAX_POINTS:
            raise InvalidPlacement(f"at most {MAX_POINTS} points are allowed")
        if _self_intersects(ring):
            raise InvalidPlacement(f"ring {index} crosses itself")
        area = signed_area(ring)
        if abs(area) < MIN_AREA_M2:
            raise InvalidPlacement(f"ring {index} has no area")
        rings.append(ring if area > 0 else ring[::-1])
    rings.sort(key=signed_area, reverse=True)
    return rings


def area_m2(rings: list[Ring]) -> float:
    return sum(abs(signed_area(r)) for r in rings)


def bounds(rings: list[Ring]) -> Rect:
    return Rect.from_points([p for r in rings for p in r])


def label_point(rings: list[Ring]) -> Point:
    """A point inside the largest ring, near its middle."""
    ring = rings[0]
    cx, cy = _centroid(ring)
    if point_in_ring((cx, cy), ring):
        return (cx, cy)
    # Widest stretch of the horizontal line through the centroid.
    xs = sorted(_crossings(ring, cy))
    spans = list(zip(xs[::2], xs[1::2], strict=False))
    if spans:
        a, b = max(spans, key=lambda s: s[1] - s[0])
        return ((a + b) / 2, cy)
    return ring[0]


def as_lists(rings: list[Ring]) -> list[list[list[float]]]:
    """Rings as JSON-ready nested lists (for storage)."""
    return [[[x, y] for x, y in ring] for ring in rings]


def _ring(raw: Any, index: int) -> Ring:
    if not isinstance(raw, list | tuple):
        raise InvalidPlacement(f"ring {index} must be a list of [x, y] points")
    points: Ring = []
    for p in raw:
        if not isinstance(p, list | tuple) or len(p) != 2:
            raise InvalidPlacement(f"ring {index}: each point must be [x, y]")
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError):
            raise InvalidPlacement(f"ring {index}: coordinates must be numbers") from None
        if not (math.isfinite(x) and math.isfinite(y)) or max(abs(x), abs(y)) > MAX_COORD_M:
            raise InvalidPlacement(f"ring {index}: coordinates must be finite and within {MAX_COORD_M:g} m")
        point = (round(x, 3) + 0.0, round(y, 3) + 0.0)
        if not points or points[-1] != point:
            points.append(point)
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(points) < 3:
        raise InvalidPlacement(f"ring {index} needs at least 3 different points")
    return points


def _centroid(ring: Ring) -> Point:
    a = signed_area(ring)
    cx = cy = 0.0
    for i in range(len(ring)):
        x0, y0 = ring[i - 1]
        x1, y1 = ring[i]
        cross = x0 * y1 - x1 * y0
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    return (cx / (6 * a), cy / (6 * a))


def _crossings(ring: Ring, y: float) -> list[float]:
    out = []
    for i in range(len(ring)):
        (x0, y0), (x1, y1) = ring[i - 1], ring[i]
        if (y0 > y) != (y1 > y):
            out.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    return out


def _self_intersects(ring: Ring) -> bool:
    """True if any two non-neighbouring edges touch or cross."""
    n = len(ring)
    edges = [(ring[i], ring[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                if _overlapping_neighbours(edges[i], edges[j]):
                    return True
                continue
            if _segments_touch(*edges[i], *edges[j]):
                return True
    return False


def _overlapping_neighbours(e1: tuple[Point, Point], e2: tuple[Point, Point]) -> bool:
    """Neighbouring edges that fold back over each other (a spike)."""
    (a, b), (c, d) = e1, e2
    shared = b if b in (c, d) else a
    p = a if shared == b else b
    q = d if shared == c else c
    if _orient(shared, p, q) != 0:
        return False
    # Collinear: a spike if both go the same way from the shared point.
    return (p[0] - shared[0]) * (q[0] - shared[0]) + (p[1] - shared[1]) * (q[1] - shared[1]) > 0


def _orient(a: Point, b: Point, c: Point) -> int:
    v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)


def _on_segment(a: Point, b: Point, p: Point) -> bool:
    return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])


def _segments_touch(a: Point, b: Point, c: Point, d: Point) -> bool:
    o1, o2, o3, o4 = _orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    return (
        (o1 == 0 and _on_segment(a, b, c))
        or (o2 == 0 and _on_segment(a, b, d))
        or (o3 == 0 and _on_segment(c, d, a))
        or (o4 == 0 and _on_segment(c, d, b))
    )
