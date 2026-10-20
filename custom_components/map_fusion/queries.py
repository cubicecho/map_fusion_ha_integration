"""Questions about the fused map: which frame, which area, which coordinates.

Pure Python. The services call these so every consumer gets the same
answers (one point-in-area rule, one transform).
"""
from __future__ import annotations

from typing import Any

from .geometry import distance_to_ring, point_in_ring
from .model import FusedArea, FusedFrame, FusedMap, Point, Ring, Transform

# Vacuum outlines stop a few cm short of walls and doorways.
NEAR_M = 0.1

# Shape variants: what the vacuum traced, or with furniture gaps filled.
TRACED = "traced"
FILLED = "filled"
VARIANTS = (TRACED, FILLED)


class QueryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def find_frame(fused: FusedMap | None, frame_id: str | None, source_id: str | None = None) -> FusedFrame:
    """The frame asked for, or the only one that fits."""
    frames = fused.frames if fused else []
    if frame_id is not None:
        frame = next((f for f in frames if f.frame_id == frame_id), None)
        if frame is None:
            raise QueryError("not_found", f"Frame {frame_id} does not exist")
        return frame
    if source_id is not None:
        frames = [f for f in frames if any(s["source_id"] == source_id for s in f.sources)]
        if not frames:
            raise QueryError("not_found", f"No frame uses {source_id}")
    if len(frames) == 1:
        return frames[0]
    if not frames:
        raise QueryError("not_found", "There is no map yet")
    raise QueryError("frame_required", "There is more than one map frame; give a frame_id")


def source_transform(frame: FusedFrame, source_id: str | None) -> tuple[str, Transform]:
    """(source_id, native → frame transform) for a source in this frame."""
    if not frame.sources:
        raise QueryError("not_found", f"Frame {frame.frame_id} has no vacuum map")
    src: dict[str, Any] | None
    if source_id is None:
        if len(frame.sources) > 1:
            raise QueryError("source_required", "This frame has several vacuum maps; give a source_id")
        src = frame.sources[0]
    else:
        src = next((s for s in frame.sources if s["source_id"] == source_id), None)
        if src is None:
            raise QueryError("not_found", f"{source_id} is not in frame {frame.frame_id}")
    return src["source_id"], Transform(*src["transform"])


def to_frame(frame: FusedFrame, source_id: str | None, point: Point) -> tuple[str, Point]:
    sid, native_to_frame = source_transform(frame, source_id)
    return sid, native_to_frame.apply(point)


def to_source(frame: FusedFrame, source_id: str | None, point: Point) -> tuple[str, Point]:
    sid, native_to_frame = source_transform(frame, source_id)
    return sid, native_to_frame.inverse().apply(point)


def locate(
    frame: FusedFrame, point: Point, near_m: float = NEAR_M, variant: str = TRACED
) -> dict[str, Any]:
    """The area a frame point is in.

    Inside an outline wins; where shapes overlap (boxes, manual shapes) the
    smallest area wins, as the most specific. Otherwise the nearest area
    within `near_m` counts. `area_id` is None when nothing is close.
    """
    def shape(a: FusedArea) -> list[Ring]:
        return (a.filled_polygons or a.polygons) if variant == FILLED else a.polygons

    inside = [a for a in frame.areas if any(point_in_ring(point, r) for r in shape(a))]
    if inside:
        best = min(inside, key=lambda a: a.area_m2)
        return {"area_id": best.area_id, "name": best.name, "inside": True, "distance_m": 0.0}
    nearest = None
    nearest_d = near_m
    for area in frame.areas:
        d = min((distance_to_ring(point, r) for r in shape(area)), default=float("inf"))
        if d <= nearest_d:
            nearest, nearest_d = area, d
    if nearest is None:
        return {"area_id": None, "name": None, "inside": False, "distance_m": None}
    return {"area_id": nearest.area_id, "name": nearest.name, "inside": False, "distance_m": round(nearest_d, 3)}


def document(
    fused: FusedMap | None, frame_id: str | None = None, variant: str = TRACED
) -> dict[str, Any] | None:
    """The fused map as JSON, optionally only one frame.

    With `variant="filled"`, `polygons` (and `area_m2`) are the filled
    shapes, so consumers that only read `polygons` get them unchanged.
    `rect` is the same in both variants.
    """
    if fused is None:
        return None
    doc = fused.as_dict()
    doc["variant"] = variant
    if frame_id is not None:
        doc["frames"] = [f for f in doc["frames"] if f["frame_id"] == frame_id]
    if variant == FILLED:
        for frame in doc["frames"]:
            for area in frame["areas"]:
                area["polygons"], area["area_m2"] = area["filled_polygons"], area["filled_m2"]
            for room in frame["unmapped_rooms"]:
                room["polygons"] = room["filled_polygons"]
    return doc
