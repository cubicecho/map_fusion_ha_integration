"""A small made-up Dreame map for tests, so CI never needs a real floor plan.

Layout in 5 cm cells, offset by BASE like a real Dreame map:

- segment 1 "L room": an L shape (40×20 cells plus 20×20 below its left half)
- segment 2 "Holey room": 40×40 cells with a 10×10 hole in the middle
- segment 3 "Specky room": 40×20 cells plus a 3×3 speck far away (dropped)

Rooms are one cell apart (the "walls").
"""
from __future__ import annotations

import json
import struct
import zlib
from typing import Any

PIXEL_SIZE = 5  # cm
BASE = (400, 600)
SIZE = 6554
# Constant shift from ValetudoMap metres to the Dreame source frame, as in
# the real D10 Plus data (Dreame's formula plus a small rounding offset).
DX = -32.768 - 0.018
DY = 32.768 - SIZE / 100 + 0.078


def _rect(x0: int, y0: int, w: int, h: int) -> set[tuple[int, int]]:
    return {(BASE[0] + x, BASE[1] + y) for x in range(x0, x0 + w) for y in range(y0, y0 + h)}


SEGMENTS: dict[int, tuple[str, set[tuple[int, int]]]] = {
    1: ("L room", _rect(0, 0, 40, 20) | _rect(0, 21, 20, 20)),
    2: ("Holey room", _rect(41, 0, 40, 40) - _rect(56, 15, 10, 10)),
    3: ("Specky room", _rect(21, 41, 60, 20) | _rect(120, 120, 3, 3)),
}


def runs(cells: set[tuple[int, int]]) -> list[int]:
    out: list[int] = []
    for y in sorted({c[1] for c in cells}):
        xs = sorted(c[0] for c in cells if c[1] == y)
        start = prev = xs[0]
        for x in xs[1:]:
            if x != prev + 1:
                out += [start, y, prev - start + 1]
                start = x
            prev = x
        out += [start, y, prev - start + 1]
    return out


def valetudo_doc() -> dict[str, Any]:
    return {
        "__class": "ValetudoMap",
        "size": {"x": SIZE, "y": SIZE},
        "pixelSize": PIXEL_SIZE,
        "layers": [
            {
                "type": "segment",
                "compressedPixels": runs(cells),
                "metaData": {"segmentId": sid, "name": name, "active": False},
            }
            for sid, (name, cells) in SEGMENTS.items()
        ],
        "entities": [],
        "metaData": {"version": 2, "rotation": 0},
    }


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def png_with(doc: dict[str, Any] | None, *, kind: bytes = b"zTXt") -> bytes:
    """A 1×1 PNG carrying `doc` as a ValetudoMap text chunk."""
    out = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    if doc is not None:
        text = json.dumps(doc).encode()
        if kind == b"zTXt":
            out += _chunk(b"zTXt", b"ValetudoMap\0\0" + zlib.compress(text))
        elif kind == b"tEXt":
            out += _chunk(b"tEXt", b"ValetudoMap\0" + text)
        else:
            out += _chunk(b"iTXt", b"ValetudoMap\0\x01\0\0\0" + zlib.compress(text))
    out += _chunk(b"IDAT", zlib.compress(b"\0\0\0\0\0")) + _chunk(b"IEND", b"")
    return out


def attr_rooms() -> dict[str, dict[str, Any]]:
    """The `rooms` attribute Dreame's map camera would show (vacuum mm, y up)."""
    rooms: dict[str, dict[str, Any]] = {}
    scale = PIXEL_SIZE / 100
    for sid, (name, cells) in SEGMENTS.items():
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        x, y = min(xs) * scale + DX, min(ys) * scale + DY
        w, h = (max(xs) + 1 - min(xs)) * scale, (max(ys) + 1 - min(ys)) * scale
        rooms[str(sid)] = {
            "x0": round(1000 * x),
            "y0": round(-1000 * (y + h)),
            "x1": round(1000 * (x + w)),
            "y1": round(-1000 * y),
            "room_id": sid,
            "name": name,
            "visibility": "Visible",
        }
    return rooms
