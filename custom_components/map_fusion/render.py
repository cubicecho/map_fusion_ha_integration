"""Draw a frame as SVG for the image entity. Pure Python.

SVG keeps this dependency-free (no Pillow) and every browser shows it in
an <img>, so picture cards work. The image's pixels map to frame metres by
`to_image`; `calibration_points` ties pixels to the anchor vacuum's own
coordinates, in the format Xiaomi Vacuum Map Card uses.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

from .model import FusedFrame, Point, Rect, Ring, Transform

PX_PER_M = 50
PAD_M = 0.3
FILLS = ["#90caf9", "#ffcc80", "#a5d6a7", "#f48fb1", "#ce93d8", "#80cbc4", "#fff59d", "#bcaaa4"]


@dataclass(slots=True)
class RenderedFrame:
    svg: bytes
    width: int
    height: int
    # Frame metres → image pixels.
    to_image: Transform
    calibration_points: list[dict[str, dict[str, float]]] | None


def render(frame: FusedFrame) -> RenderedFrame:
    bounds = frame.bounds or Rect(0, 0, 1, 1)
    to_image = Transform(
        a=PX_PER_M,
        d=PX_PER_M,
        tx=(PAD_M - bounds.x) * PX_PER_M,
        ty=(PAD_M - bounds.y) * PX_PER_M,
    )
    width = round((bounds.width + 2 * PAD_M) * PX_PER_M)
    height = round((bounds.height + 2 * PAD_M) * PX_PER_M)
    font = max(10, min(18, round(min(width, height) / 25)))

    style = (
        ".room{stroke:#616161;stroke-width:1.5;stroke-linejoin:round;fill-opacity:.55}"
        ".manual{stroke-dasharray:6 3}"
        ".unlinked{fill:none;stroke:#9e9e9e;stroke-width:1;stroke-dasharray:4 3}"
        f".label{{font:{font}px sans-serif;fill:#212121;text-anchor:middle;dominant-baseline:middle;"
        "paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round}"
    )
    svg_open = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )
    parts = [svg_open, f"<title>{escape(frame.name)}</title>", f"<style>{style}</style>"]
    for room in frame.unmapped_rooms:
        rings = [[(p[0], p[1]) for p in ring] for ring in room["polygons"]]
        parts.append(f'<path class="unlinked" d="{_path(rings, to_image)}"/>')
    for i, area in enumerate(frame.areas):
        cls = "room manual" if area.origin == "manual" else "room"
        fill = FILLS[i % len(FILLS)]
        parts.append(
            f'<path class="{cls}" fill="{fill}" d="{_path(area.polygons, to_image)}">'
            f"<title>{escape(area.name)}</title></path>"
        )
    for area in frame.areas:
        x, y = to_image.apply(area.label_point)
        parts.append(f'<text class="label" x="{x:.1f}" y="{y:.1f}">{escape(area.name)}</text>')
    parts.append("</svg>")

    return RenderedFrame(
        svg="".join(parts).encode(),
        width=width,
        height=height,
        to_image=to_image,
        calibration_points=_calibration(frame, bounds, to_image),
    )


def _path(rings: list[Ring], to_image: Transform) -> str:
    out = []
    for ring in rings:
        pts = [to_image.apply(p) for p in ring]
        out.append("M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z")
    return " ".join(out)


def _calibration(
    frame: FusedFrame, bounds: Rect, to_image: Transform
) -> list[dict[str, dict[str, float]]] | None:
    """Three vacuum ↔ image point pairs for the anchor source, if any."""
    anchor = next((s for s in frame.sources if s.get("role") == "anchor"), None)
    if anchor is None:
        return None
    frame_to_native = Transform(*anchor["transform"]).inverse()
    corners: list[Point] = [
        (bounds.x, bounds.y),
        (bounds.x + bounds.width, bounds.y),
        (bounds.x, bounds.y + bounds.height),
    ]
    points = []
    for corner in corners:
        vx, vy = frame_to_native.apply(corner)
        ix, iy = to_image.apply(corner)
        points.append({"vacuum": {"x": round(vx, 1), "y": round(vy, 1)}, "map": {"x": round(ix, 1), "y": round(iy, 1)}})
    return points


def attributes(frame: FusedFrame, rendered: RenderedFrame, version: int) -> dict[str, Any]:
    """Small state attributes for the image entity (never geometry)."""
    return {
        "frame_id": frame.frame_id,
        "floor_id": frame.floor_id,
        "area_count": len(frame.areas),
        "schema_version": version,
        "width": rendered.width,
        "height": rendered.height,
        "map_to_image": rendered.to_image.as_list(),
        "calibration_points": rendered.calibration_points,
    }
