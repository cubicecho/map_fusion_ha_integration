"""Grid-cell masks to simplified polygons, plus small polygon helpers.

Pure Python, no Home Assistant imports. A mask is a set of integer (x, y)
cells; cell (x, y) covers [x, x+1] × [y, y+1]. y points down the screen.

Rings are lists of points, not closed (the first point isn't repeated).
Outer rings run clockwise on screen, which gives them a positive
`signed_area`; holes run the other way.
"""
from __future__ import annotations

import math
from collections.abc import Iterable

from .model import Point, Rect, Ring

Cell = tuple[int, int]

# Directions with y down. Turning right means clockwise on screen.
_RIGHT = {(1, 0): (0, 1), (0, 1): (-1, 0), (-1, 0): (0, -1), (0, -1): (1, 0)}
_LEFT = {v: k for k, v in _RIGHT.items()}


def cells_from_runs(runs: list[int]) -> set[Cell]:
    """Decode run-length triples [x_start, y, count, ...] into cells."""
    if len(runs) % 3:
        raise ValueError("run list length must be a multiple of 3")
    cells: set[Cell] = set()
    for i in range(0, len(runs), 3):
        x, y, count = runs[i], runs[i + 1], runs[i + 2]
        cells.update((x + k, y) for k in range(count))
    return cells


def cells_from_pairs(pairs: list[int]) -> set[Cell]:
    """Decode a flat [x0, y0, x1, y1, ...] list into cells."""
    if len(pairs) % 2:
        raise ValueError("pixel list length must be even")
    return {(pairs[i], pairs[i + 1]) for i in range(0, len(pairs), 2)}


def close_mask(cells: set[Cell], radius: int) -> set[Cell]:
    """Morphological close (dilate then erode) with a square of `radius`.

    Fills gaps and notches narrower than about 2 * radius + 1 cells, such as
    the specks furniture legs leave. The result always contains `cells`.
    """
    if radius <= 0 or not cells:
        return set(cells)
    offsets = [(dx, dy) for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1)]
    dilated = {(x + dx, y + dy) for x, y in cells for dx, dy in offsets}
    return {c for c in dilated if all((c[0] + dx, c[1] + dy) in dilated for dx, dy in offsets)}


def trace_rings(cells: set[Cell]) -> list[Ring]:
    """Trace the boundary of a mask into rings, in cell units.

    Interior is always on the right of the walking direction, so outer rings
    come out clockwise on screen and holes anticlockwise. Where two cells
    touch only at a corner, the walk turns right, keeping the two pieces
    as separate rings.
    """
    # Outgoing boundary edges per vertex, as unit directions.
    out: dict[Cell, list[Cell]] = {}

    def add(start: Cell, direction: Cell) -> None:
        out.setdefault(start, []).append(direction)

    for x, y in cells:
        if (x, y - 1) not in cells:
            add((x, y), (1, 0))  # top edge, walking right
        if (x + 1, y) not in cells:
            add((x + 1, y), (0, 1))  # right edge, walking down
        if (x, y + 1) not in cells:
            add((x + 1, y + 1), (-1, 0))  # bottom edge, walking left
        if (x - 1, y) not in cells:
            add((x, y + 1), (0, -1))  # left edge, walking up

    rings: list[Ring] = []
    while out:
        start = min(out)  # deterministic order
        direction = out[start][0]
        ring: list[Cell] = []
        vertex = start
        while True:
            dirs = out[vertex]
            dirs.remove(direction)
            if not dirs:
                del out[vertex]
            ring.append(vertex)
            vertex = (vertex[0] + direction[0], vertex[1] + direction[1])
            if vertex == start:
                break
            choices = out.get(vertex)
            if not choices:
                break  # malformed mask; keep what we have
            if len(choices) == 1:
                direction = choices[0]
            else:
                # Pinch vertex: prefer right turn, then straight, then left.
                for candidate in (_RIGHT[direction], direction, _LEFT[direction]):
                    if candidate in choices:
                        direction = candidate
                        break
        rings.append(_drop_collinear([(float(x), float(y)) for x, y in ring]))
    return rings


def signed_area(ring: Ring) -> float:
    """Shoelace area. Positive for clockwise-on-screen rings (y down)."""
    total = 0.0
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i - 1]
        x1, y1 = ring[i]
        total += x0 * y1 - x1 * y0
    return total / 2


def simplify_ring(ring: Ring, tolerance: float) -> Ring:
    """Douglas–Peucker on a closed ring. Never returns fewer than 3 points."""
    if len(ring) <= 4 or tolerance <= 0:
        return list(ring)
    # Split at the point farthest from the first, simplify both halves.
    far = max(range(len(ring)), key=lambda k: _dist2(ring[k], ring[0]))
    first = _dp(ring[: far + 1], tolerance)
    second = _dp(ring[far:] + [ring[0]], tolerance)
    result = _drop_collinear(first[:-1] + second[:-1])
    return result if len(result) >= 3 else list(ring)


def mask_to_polygons(
    cells: set[Cell],
    *,
    min_piece_cells: int,
    tolerance_cells: float,
) -> list[Ring]:
    """Outer rings of a mask, largest first, pieces under the size dropped.

    Holes are dropped (v1). Coordinates stay in cell units.
    """
    rings = trace_rings(cells)
    outers = [r for r in rings if signed_area(r) > 0 and signed_area(r) >= min_piece_cells]
    outers.sort(key=signed_area, reverse=True)
    return [simplify_ring(r, tolerance_cells) for r in outers]


def label_point(cells: set[Cell]) -> Point:
    """A point inside the mask near its centre of mass, in cell units."""
    mx = sum(c[0] for c in cells) / len(cells) + 0.5
    my = sum(c[1] for c in cells) / len(cells) + 0.5
    if (math.floor(mx), math.floor(my)) in cells:
        return (mx, my)
    best = min(cells, key=lambda c: (c[0] + 0.5 - mx) ** 2 + (c[1] + 0.5 - my) ** 2)
    return (best[0] + 0.5, best[1] + 0.5)


def point_in_ring(p: Point, ring: Ring) -> bool:
    """Even-odd ray cast."""
    x, y = p
    inside = False
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i - 1]
        x1, y1 = ring[i]
        if (y0 > y) != (y1 > y):
            cross_x = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < cross_x:
                inside = not inside
    return inside


def distance_to_ring(p: Point, ring: Ring) -> float:
    """Distance from p to the ring's edges."""
    return min(_dist_to_segment(p, ring[i - 1], ring[i]) for i in range(len(ring)))


def bounds(points: Iterable[Point]) -> Rect:
    return Rect.from_points(list(points))


def _dp(points: list[Point], tolerance: float) -> list[Point]:
    """Douglas–Peucker on an open polyline (iterative)."""
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i0, i1 = stack.pop()
        best, best_d = -1, tolerance
        for k in range(i0 + 1, i1):
            d = _dist_to_segment(points[k], points[i0], points[i1])
            if d > best_d:
                best, best_d = k, d
        if best >= 0:
            keep[best] = True
            stack.append((i0, best))
            stack.append((best, i1))
    return [p for p, k in zip(points, keep) if k]


def _drop_collinear(ring: Ring) -> Ring:
    """Remove points that lie on a straight line between their neighbours."""
    changed = True
    pts = list(ring)
    while changed and len(pts) > 3:
        changed = False
        out: Ring = []
        n = len(pts)
        for i in range(n):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
            if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < 1e-9:
                changed = True
                continue
            out.append(b)
        if len(out) < 3:
            break
        pts = out
    return pts


def _dist2(a: Point, b: Point) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _dist_to_segment(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return _dist2(p, a) ** 0.5
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return _dist2(p, (a[0] + t * dx, a[1] + t * dy)) ** 0.5


def centroid(rings: list[Ring]) -> Point:
    """Area-weighted centre of several rings."""
    total = cx = cy = 0.0
    for ring in rings:
        a = signed_area(ring)
        if a == 0:
            continue
        rx = ry = 0.0
        for i in range(len(ring)):
            x0, y0 = ring[i - 1]
            x1, y1 = ring[i]
            cross = x0 * y1 - x1 * y0
            rx += (x0 + x1) * cross
            ry += (y0 + y1) * cross
        cx += rx / 6
        cy += ry / 6
        total += a
    if total == 0:
        pts = [p for r in rings for p in r]
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    return (cx / total, cy / total)


def raster(rings: list[Ring], cell: float, x0: float, y0: float, nx: int, ny: int) -> set[Cell]:
    """Grid cells whose centres are inside any ring (scanline fill)."""
    out: set[Cell] = set()
    for j in range(ny):
        y = y0 + (j + 0.5) * cell
        for ring in rings:
            xs: list[float] = []
            for i in range(len(ring)):
                (ax, ay), (bx, by) = ring[i - 1], ring[i]
                if (ay > y) != (by > y):
                    xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2], strict=False):
                first = max(0, math.ceil((a - x0) / cell - 0.5))
                last = min(nx - 1, math.floor((b - x0) / cell - 0.5))
                for i in range(first, last + 1):
                    out.add((i, j))
    return out


def overlap(
    a: list[Ring], b: list[Ring], cell: float = 0.05, box: Rect | None = None
) -> tuple[float, float, float]:
    """(area of a, area of b, area of both) in m², measured on a grid.

    With `box`, only that part of the plane is measured (cheaper when only
    the shared part matters).
    """
    if box is None:
        pts = [p for r in a + b for p in r]
        if not pts:
            return (0.0, 0.0, 0.0)
        box = bounds(pts)
    nx = max(1, math.ceil(box.width / cell))
    ny = max(1, math.ceil(box.height / cell))
    ca = raster(a, cell, box.x, box.y, nx, ny)
    cb = raster(b, cell, box.x, box.y, nx, ny)
    m2 = cell * cell
    return (len(ca) * m2, len(cb) * m2, len(ca & cb) * m2)


def iou(a: list[Ring], b: list[Ring], cell: float = 0.05) -> float:
    """Intersection over union of two shapes: 1 = identical, 0 = apart."""
    area_a, area_b, both = overlap(a, b, cell)
    union = area_a + area_b - both
    return both / union if union else 0.0
