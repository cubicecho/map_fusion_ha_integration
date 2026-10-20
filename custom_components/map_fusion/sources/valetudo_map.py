"""ValetudoMap JSON → room polygons.

ValetudoMap is Valetudo's map format. Tasshack/dreame-vacuum emits it too,
from its "Map data" camera, embedded in a PNG text chunk.

- `pixelSize`: cm per cell.
- `layers[]`: `type` floor | wall | segment, cells as `compressedPixels`
  (run-length `[x_start, y, count, ...]`, v2) or `pixels` (flat pairs, v1).
  Segment layers have `metaData.segmentId` (int or str) and `name`.
- Layer coordinates are cells, entity coordinates are cm. y points down.

Pure Python, no Home Assistant imports.
"""
from __future__ import annotations

import json
import struct
import zlib
from dataclasses import dataclass, field
from typing import Any

from .. import geometry
from ..model import Rect, SourceRoom

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
TEXT_KEY = b"ValetudoMap"


class ValetudoMapError(ValueError):
    """The data is not a usable ValetudoMap."""


@dataclass(slots=True)
class MapSegment:
    segment_id: str
    name: str | None
    cells: set[geometry.Cell]


@dataclass(slots=True)
class ValetudoMap:
    pixel_size_cm: float
    size: tuple[int, int]  # in cm
    rotation: int
    segments: dict[str, MapSegment]
    entities: list[dict[str, Any]] = field(default_factory=list)

    @property
    def metres_per_cell(self) -> float:
        return self.pixel_size_cm / 100


def extract_from_png(data: bytes) -> dict[str, Any]:
    """Return the ValetudoMap JSON embedded in a PNG's text chunks."""
    if not data.startswith(PNG_SIGNATURE):
        raise ValetudoMapError("not a PNG")
    pos = len(PNG_SIGNATURE)
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind not in (b"tEXt", b"zTXt", b"iTXt"):
            if kind == b"IEND":
                break
            continue
        key, _, rest = body.partition(b"\0")
        if key != TEXT_KEY:
            continue
        try:
            if kind == b"tEXt":
                text = rest
            elif kind == b"zTXt":
                text = zlib.decompress(rest[1:])  # rest[0] is the compression method
            else:
                compressed = rest[0] == 1
                _, _, rest = rest[2:].partition(b"\0")  # language tag
                _, _, rest = rest.partition(b"\0")  # translated keyword
                text = zlib.decompress(rest) if compressed else rest
            return json.loads(text)
        except (zlib.error, ValueError) as err:
            raise ValetudoMapError(f"bad ValetudoMap chunk: {err}") from err
    raise ValetudoMapError("PNG has no ValetudoMap data (is this the Map data camera?)")


def parse(doc: dict[str, Any]) -> ValetudoMap:
    """Parse ValetudoMap JSON (v1 or v2 pixels)."""
    if doc.get("__class") != "ValetudoMap":
        raise ValetudoMapError("not a ValetudoMap document")
    try:
        pixel_size = float(doc["pixelSize"])
        size = (int(doc["size"]["x"]), int(doc["size"]["y"]))
    except (KeyError, TypeError, ValueError) as err:
        raise ValetudoMapError(f"missing map size: {err}") from err
    if pixel_size <= 0:
        raise ValetudoMapError("pixelSize must be above 0")

    segments: dict[str, MapSegment] = {}
    for layer in doc.get("layers") or []:
        if layer.get("type") != "segment":
            continue
        meta = layer.get("metaData") or {}
        if meta.get("segmentId") is None:
            continue
        segment_id = str(meta["segmentId"])
        if layer.get("compressedPixels"):
            cells = geometry.cells_from_runs(layer["compressedPixels"])
        else:
            cells = geometry.cells_from_pairs(layer.get("pixels") or [])
        if not cells:
            continue
        if segment_id in segments:  # same id twice: merge
            segments[segment_id].cells |= cells
        else:
            segments[segment_id] = MapSegment(segment_id, meta.get("name"), cells)

    meta = doc.get("metaData") or {}
    return ValetudoMap(
        pixel_size_cm=pixel_size,
        size=size,
        rotation=int(meta.get("rotation") or 0),
        segments=segments,
        entities=list(doc.get("entities") or []),
    )


def rooms(
    vmap: ValetudoMap,
    *,
    close_cells: int = 1,
    min_piece_m2: float = 0.25,
    tolerance_m: float = 0.075,
) -> dict[str, SourceRoom]:
    """Polygons per segment, in metres (cells × pixelSize), y down.

    Each room is closed (small gaps filled) without growing into another
    room's cells, so rooms never overlap. Pieces under `min_piece_m2` are
    dropped, except a room's largest piece, which is always kept.
    """
    scale = vmap.metres_per_cell
    claimed: dict[geometry.Cell, str] = {}
    for seg in vmap.segments.values():
        for cell in seg.cells:
            claimed[cell] = seg.segment_id

    result: dict[str, SourceRoom] = {}
    for seg in vmap.segments.values():
        closed = {
            c
            for c in geometry.close_mask(seg.cells, close_cells)
            if claimed.get(c, seg.segment_id) == seg.segment_id
        }
        min_cells = min_piece_m2 / (scale * scale)
        rings = geometry.mask_to_polygons(
            closed, min_piece_cells=0, tolerance_cells=tolerance_m / scale
        )
        kept = [r for i, r in enumerate(rings) if i == 0 or geometry.signed_area(r) >= min_cells]
        polygons = [[(x * scale, y * scale) for x, y in ring] for ring in kept]
        lx, ly = geometry.label_point(seg.cells)
        result[seg.segment_id] = SourceRoom(
            segment_id=seg.segment_id,
            name=seg.name,
            polygons=polygons,
            rect=Rect.union([Rect.from_points(p) for p in polygons]),
            label_point=(lx * scale, ly * scale),
            area_m2=len(seg.cells) * scale * scale,
            geometry="pixels",
        )
    return result


def cell_bounds(vmap: ValetudoMap, segment_id: str) -> Rect:
    """A segment's raw cell bounding box, in metres (for fitting transforms)."""
    cells = vmap.segments[segment_id].cells
    scale = vmap.metres_per_cell
    x0 = min(c[0] for c in cells)
    y0 = min(c[1] for c in cells)
    x1 = max(c[0] for c in cells) + 1
    y1 = max(c[1] for c in cells) + 1
    return Rect(x0 * scale, y0 * scale, (x1 - x0) * scale, (y1 - y0) * scale)
