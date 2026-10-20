"""Draw a frame as SVG for the image entity. Pure Python.

SVG keeps this dependency-free (no Pillow) and every browser shows it in
an <img>, so picture cards work. The image's pixels map to frame metres by
`to_image`; `calibration_points` ties pixels to the anchor vacuum's own
coordinates, in the format Xiaomi Vacuum Map Card uses.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

from .model import FusedFeature, FusedFrame, Point, Rect, Ring, Transform

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


# Doors and windows: (colour when closed, line width px). Open ones are drawn red.
FEATURE_STYLE = {"door": ("#6d4c41", 6), "window": ("#0288d1", 5)}
OPEN_COLOUR = "#e53935"


def _feature_svg(
    feature: FusedFeature, to_image: Transform, state: str = "unknown", scale: float = 1.0
) -> str:
    """A door or window as a thick line across the wall, coloured by open/closed."""
    colour, width = FEATURE_STYLE.get(feature.kind, ("#616161", 5))
    if state == "open":
        colour = OPEN_COLOUR
    (x0, y0), (x1, y1) = (to_image.apply(p) for p in (feature.points[0], feature.points[-1]))
    w = width * scale
    dash = ' stroke-dasharray="4 3"' if state == "unknown" and feature.entity_id else ""
    title = escape(feature.name or feature.kind.title())
    line = (
        f'<line class="feature feature-{feature.kind} {state}" x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" '
        f'stroke="{colour}" stroke-width="{w:g}" stroke-linecap="butt"{dash}><title>{title}</title></line>'
    )
    if feature.kind == "window":
        # A thin pale line down the middle reads as glass.
        line += (
            f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="#e1f5fe" '
            f'stroke-width="{max(1.0, w / 3):g}"/>'
        )
    return line


def render(
    frame: FusedFrame, *, filled: bool = False, states: dict[str, str] | None = None
) -> RenderedFrame:
    """The frame as SVG. `states` maps feature ids to "open" / "closed" / "unknown"."""
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
        key = "filled_polygons" if filled else "polygons"
        rings = [[(p[0], p[1]) for p in ring] for ring in room.get(key) or room["polygons"]]
        parts.append(f'<path class="unlinked" d="{_path(rings, to_image)}"/>')
    for i, area in enumerate(frame.areas):
        cls = "room manual" if area.origin == "manual" else "room"
        fill = FILLS[i % len(FILLS)]
        shape = (area.filled_polygons or area.polygons) if filled else area.polygons
        parts.append(
            f'<path class="{cls}" fill="{fill}" d="{_path(shape, to_image)}">'
            f"<title>{escape(area.name)}</title></path>"
        )
    for feature in frame.features:
        parts.append(_feature_svg(feature, to_image, (states or {}).get(feature.feature_id, "unknown")))
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


# Editing preview -------------------------------------------------------------------

PREVIEW_PX_PER_M = 40
PREVIEW_MARGIN_M = 1.0


def render_preview(
    frame: FusedFrame | None,
    *,
    editing: str | None = None,
    proposal: list[Ring] | None = None,
    title: str = "",
) -> bytes:
    """The map for placing an area by hand, as SVG.

    - A metre grid with coordinate labels, so x/y/width/height can be read off.
    - Other areas faint and labelled, unlinked vacuum rooms dashed.
    - The area being edited (`editing`) dashed in its current shape.
    - The `proposal` (the shape about to be saved) in a strong colour, with
      its rectangle written out.
    """
    areas = [a for a in (frame.areas if frame else []) if a.area_id != editing]
    current = next((a for a in (frame.areas if frame else []) if a.area_id == editing), None)
    rooms = frame.unmapped_rooms if frame else []
    pts: list[Point] = [p for a in (frame.areas if frame else []) for r in a.polygons for p in r]
    pts += [(p[0], p[1]) for room in rooms for r in room["polygons"] for p in r]
    pts += [p for r in proposal or [] for p in r]
    box = Rect.from_points(pts) if pts else Rect(0, 0, 4, 4)
    # Whole metres around everything, plus a margin to place things beside the map.
    x0 = math.floor(box.x - PREVIEW_MARGIN_M)
    y0 = math.floor(box.y - PREVIEW_MARGIN_M)
    x1 = math.ceil(box.x + box.width + PREVIEW_MARGIN_M)
    y1 = math.ceil(box.y + box.height + PREVIEW_MARGIN_M)
    gutter = 28  # px for axis labels
    scale = PREVIEW_PX_PER_M
    to_image = Transform(a=scale, d=scale, tx=gutter - x0 * scale, ty=gutter - y0 * scale)
    width = gutter + (x1 - x0) * scale + 8
    height = gutter + (y1 - y0) * scale + 8
    step = 1 if max(x1 - x0, y1 - y0) <= 20 else 2

    style = (
        ".bg{fill:#fff}.grid{stroke:#e0e0e0;stroke-width:1}.axis{stroke:#9e9e9e;stroke-width:1.5}"
        ".tick{font:11px sans-serif;fill:#616161}"
        ".room{stroke:#9e9e9e;stroke-width:1;fill:#eceff1}"
        ".unlinked{fill:none;stroke:#bdbdbd;stroke-dasharray:4 3}"
        ".current{fill:none;stroke:#1565c0;stroke-width:2;stroke-dasharray:6 4}"
        ".proposal{fill:#ff9800;fill-opacity:.45;stroke:#e65100;stroke-width:2.5}"
        ".label{font:12px sans-serif;fill:#424242;text-anchor:middle;dominant-baseline:middle;"
        "paint-order:stroke;stroke:#fff;stroke-width:3px}"
        ".plabel{font:bold 13px sans-serif;fill:#bf360c;text-anchor:middle;dominant-baseline:middle;"
        "paint-order:stroke;stroke:#fff;stroke-width:3px}"
    )
    svg_open = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )
    out = [
        svg_open,
        f"<title>{escape(title)}</title>",
        f"<style>{style}</style>",
        f'<rect class="bg" width="{width}" height="{height}"/>',
    ]
    for gx in range(x0, x1 + 1):
        px, _ = to_image.apply((gx, 0))
        cls = "axis" if gx == 0 else "grid"
        out.append(f'<line class="{cls}" x1="{px:.1f}" y1="{gutter}" x2="{px:.1f}" y2="{height - 8}"/>')
        if (gx - x0) % step == 0:
            out.append(f'<text class="tick" x="{px:.1f}" y="{gutter - 8}" text-anchor="middle">{gx}</text>')
    for gy in range(y0, y1 + 1):
        _, py = to_image.apply((0, gy))
        cls = "axis" if gy == 0 else "grid"
        out.append(f'<line class="{cls}" x1="{gutter}" y1="{py:.1f}" x2="{width - 8}" y2="{py:.1f}"/>')
        if (gy - y0) % step == 0:
            out.append(f'<text class="tick" x="{gutter - 4}" y="{py + 4:.1f}" text-anchor="end">{gy}</text>')
    out.append('<text class="tick" x="4" y="11">m</text>')

    for room in rooms:
        rings = [[(p[0], p[1]) for p in ring] for ring in room["polygons"]]
        out.append(f'<path class="unlinked" d="{_path(rings, to_image)}"/>')
    for area in areas:
        out.append(f'<path class="room" d="{_path(area.polygons, to_image)}"/>')
    for area in areas:
        x, y = to_image.apply(area.label_point)
        out.append(f'<text class="label" x="{x:.1f}" y="{y:.1f}">{escape(area.name)}</text>')
    for feature in frame.features if frame else []:
        out.append(_feature_svg(feature, to_image, scale=0.8))
    if current is not None:
        out.append(f'<path class="current" d="{_path(current.polygons, to_image)}"/>')
    if proposal:
        out.append(f'<path class="proposal" d="{_path(proposal, to_image)}"/>')
        r = Rect.from_points([p for ring in proposal for p in ring])
        cx, cy = to_image.apply((r.x + r.width / 2, r.y + r.height / 2))
        text = f"{r.width:g} × {r.height:g} m at ({r.x:g}, {r.y:g})"
        out.append(f'<text class="plabel" x="{cx:.1f}" y="{cy:.1f}">{escape(title)}</text>')
        out.append(f'<text class="plabel" x="{cx:.1f}" y="{cy + 16:.1f}">{escape(text)}</text>')
    out.append("</svg>")
    return "".join(out).encode()


def default_spot(frame: FusedFrame | None, width: float = 3.0, height: float = 3.0) -> Rect:
    """Where a new area starts: just right of the map, top-aligned, easy to spot."""
    if frame is None or frame.bounds is None:
        return Rect(0.0, 0.0, width, height)
    b = frame.bounds
    return Rect(round(b.x + b.width + 0.5, 1), round(b.y, 1), width, height)
