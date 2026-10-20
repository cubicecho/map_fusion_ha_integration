"""Data model for Map Fusion. Pure Python, no Home Assistant imports.

Coordinates are metres with y pointing down the screen unless a name says
otherwise. A "source frame" is one vacuum map's own metric frame. A "frame"
(see `FusedFrame`) is what cards draw: a source frame shifted by a stored
origin, shared by everything on one HA floor or one floor-less vacuum map.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Point = tuple[float, float]
Ring = list[Point]

Geometry = Literal["pixels", "bbox", "manual"]


@dataclass(frozen=True, slots=True)
class Rect:
    """Axis-aligned rectangle. Same fields as presence-map-card's AreaConfig."""

    x: float
    y: float
    width: float
    height: float

    @classmethod
    def from_points(cls, points: list[Point]) -> Rect:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return cls(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    @classmethod
    def union(cls, rects: list[Rect]) -> Rect:
        x0 = min(r.x for r in rects)
        y0 = min(r.y for r in rects)
        x1 = max(r.x + r.width for r in rects)
        y1 = max(r.y + r.height for r in rects)
        return cls(x0, y0, x1 - x0, y1 - y0)

    def shifted(self, dx: float, dy: float) -> Rect:
        return Rect(self.x + dx, self.y + dy, self.width, self.height)

    def intersection(self, other: Rect) -> Rect | None:
        x0 = max(self.x, other.x)
        y0 = max(self.y, other.y)
        x1 = min(self.x + self.width, other.x + other.width)
        y1 = min(self.y + self.height, other.y + other.height)
        if x1 <= x0 or y1 <= y0:
            return None
        return Rect(x0, y0, x1 - x0, y1 - y0)

    def as_dict(self) -> dict[str, float]:
        return {
            "x": _r(self.x),
            "y": _r(self.y),
            "width": _r(self.width),
            "height": _r(self.height),
        }


@dataclass(frozen=True, slots=True)
class Transform:
    """2D affine map: x' = a*x + b*y + tx, y' = c*x + d*y + ty."""

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    tx: float = 0.0
    ty: float = 0.0

    def apply(self, p: Point) -> Point:
        x, y = p
        return (self.a * x + self.b * y + self.tx, self.c * x + self.d * y + self.ty)

    def then(self, other: Transform) -> Transform:
        """Return the transform that applies self first, then other."""
        return Transform(
            a=other.a * self.a + other.b * self.c,
            b=other.a * self.b + other.b * self.d,
            c=other.c * self.a + other.d * self.c,
            d=other.c * self.b + other.d * self.d,
            tx=other.a * self.tx + other.b * self.ty + other.tx,
            ty=other.c * self.tx + other.d * self.ty + other.ty,
        )

    def inverse(self) -> Transform:
        det = self.a * self.d - self.b * self.c
        if det == 0:
            raise ValueError("transform is not invertible")
        a, b, c, d = self.d / det, -self.b / det, -self.c / det, self.a / det
        return Transform(a, b, c, d, -(a * self.tx + b * self.ty), -(c * self.tx + d * self.ty))

    def as_list(self) -> list[float]:
        return [self.a, self.b, self.c, self.d, _r(self.tx, 4), _r(self.ty, 4)]


@dataclass(slots=True)
class SourceRoom:
    """One vacuum room (segment), in its source frame."""

    segment_id: str  # the id core's Segment uses, e.g. Dreame "1_3"
    name: str | None
    polygons: list[Ring]  # largest piece first
    rect: Rect
    label_point: Point
    area_m2: float
    geometry: Geometry


@dataclass(slots=True)
class SourceMap:
    """One vacuum map, normalised by a source adapter."""

    source_id: str  # vacuum entity id
    kind: str  # "dreame", later "valetudo", ...
    map_id: str
    map_name: str | None
    rooms: dict[str, SourceRoom]  # by segment_id
    # Source frame (metres, y down) → the vacuum's native coordinates.
    to_native: Transform
    # How well to_native was fitted (metres RMS), None when not fitted.
    native_residual_m: float | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.source_id}:{self.map_id}"


@dataclass(slots=True)
class FusedArea:
    area_id: str
    name: str
    polygons: list[Ring]
    rect: Rect
    label_point: Point
    area_m2: float
    origin: Literal["vacuum", "manual"]
    geometry: Geometry
    sources: list[dict[str, str]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "area_id": self.area_id,
            "name": self.name,
            "polygons": [_ring(r) for r in self.polygons],
            "rect": self.rect.as_dict(),
            "label_point": [_r(self.label_point[0]), _r(self.label_point[1])],
            "area_m2": _r(self.area_m2, 2),
            "origin": self.origin,
            "geometry": self.geometry,
            "sources": self.sources,
        }


@dataclass(slots=True)
class FusedFrame:
    frame_id: str
    floor_id: str | None
    name: str
    bounds: Rect | None
    areas: list[FusedArea]
    unmapped_rooms: list[dict[str, Any]]
    overlaps: list[dict[str, Any]]
    sources: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "floor_id": self.floor_id,
            "name": self.name,
            "bounds": self.bounds.as_dict() if self.bounds else None,
            "areas": [a.as_dict() for a in self.areas],
            "unmapped_rooms": self.unmapped_rooms,
            "overlaps": self.overlaps,
            "sources": self.sources,
        }


@dataclass(slots=True)
class FusedMap:
    version: int
    generated_at: str
    frames: list[FusedFrame]
    unplaced_areas: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "frames": [f.as_dict() for f in self.frames],
            "unplaced_areas": self.unplaced_areas,
        }

    def frame(self, frame_id: str) -> FusedFrame | None:
        return next((f for f in self.frames if f.frame_id == frame_id), None)


def _r(v: float, nd: int = 3) -> float:
    return round(v, nd) + 0.0  # + 0.0 turns -0.0 into 0.0


def _ring(ring: Ring) -> list[list[float]]:
    return [[_r(x), _r(y)] for x, y in ring]
