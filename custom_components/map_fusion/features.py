"""Map features: things placed on the map that aren't areas. Pure Python.

Today: doors and windows (openings in a wall). Each kind is one entry in
`KINDS`, which says what it's called, its icon, its geometry and which
entities can be linked to it. A new kind (vent, radiator, stairs, …) is a
new entry; storage, APIs and the panel read the table.

A feature is stored per frame (like placements):

    {"kind": "door", "points": [[x, y], [x, y]], "name": str | None,
     "entity_id": str | None, "areas": [area_id, ...] | None}

`areas` None means "work it out": the areas on each side of the line.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from .geometry import distance_to_ring, point_in_ring
from .model import Point, Ring

FeatureGeometry = Literal["segment"]

# frame_id → feature_id → stored feature
Features = dict[str, dict[str, dict[str, Any]]]

MIN_LENGTH_M = 0.05
MAX_LENGTH_M = 20.0
# How far either side of the line to look for the rooms it joins.
SIDE_PROBES_M = (0.15, 0.3, 0.5)
NEAR_M = 0.1


@dataclass(frozen=True, slots=True)
class FeatureKind:
    key: str
    name: str
    icon: str
    geometry: FeatureGeometry
    # Entity domain → device classes that fit (None: any device class).
    entity_domains: dict[str, frozenset[str] | None]
    # Most areas it can join (a door between two rooms, a window between a room and outside).
    max_areas: int = 2

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "icon": self.icon,
            "geometry": self.geometry,
            "entity_domains": {
                d: (sorted(c) if c is not None else None) for d, c in self.entity_domains.items()
            },
            "max_areas": self.max_areas,
        }


KINDS: dict[str, FeatureKind] = {
    "door": FeatureKind(
        key="door",
        name="Door",
        icon="mdi:door",
        geometry="segment",
        entity_domains={
            "binary_sensor": frozenset({"door", "garage_door", "opening"}),
            "cover": frozenset({"door", "garage", "gate"}),
        },
    ),
    "window": FeatureKind(
        key="window",
        name="Window",
        icon="mdi:window-closed-variant",
        geometry="segment",
        entity_domains={
            "binary_sensor": frozenset({"window", "opening"}),
            "cover": frozenset({"window", "awning", "blind", "curtain", "shade", "shutter"}),
        },
    ),
}


class InvalidFeature(ValueError):
    """The feature can't be used. The message says why, for the user."""


def kinds_doc() -> dict[str, Any]:
    return {key: kind.as_dict() for key, kind in KINDS.items()}


def entity_fits(kind: FeatureKind, entity_id: str) -> bool:
    """Whether an entity's domain can be linked to this kind (device class is a hint only)."""
    return entity_id.split(".", 1)[0] in kind.entity_domains


def normalise(data: dict[str, Any]) -> dict[str, Any]:
    """Check a feature from the user and return what's stored."""
    kind = KINDS.get(str(data.get("kind")))
    if kind is None:
        raise InvalidFeature(f"kind must be one of: {', '.join(KINDS)}")
    points = _segment(data.get("points"))
    name = data.get("name")
    entity_id = data.get("entity_id")
    if entity_id is not None:
        entity_id = str(entity_id)
        if not entity_fits(kind, entity_id):
            raise InvalidFeature(
                f"a {kind.name.lower()} can be linked to {', '.join(kind.entity_domains)} entities"
            )
    areas = data.get("areas")
    if areas is not None:
        if not isinstance(areas, list | tuple) or len(areas) > kind.max_areas:
            raise InvalidFeature(f"areas must be a list of at most {kind.max_areas} area ids")
        areas = [str(a) for a in dict.fromkeys(areas)]
    return {
        "kind": kind.key,
        "points": [[x, y] for x, y in points],
        "name": (str(name).strip() or None) if name is not None else None,
        "entity_id": entity_id or None,
        "areas": areas,
    }


def _segment(raw: Any) -> list[Point]:
    if not isinstance(raw, list | tuple) or len(raw) != 2:
        raise InvalidFeature("points must be two [x, y] points (the ends of the opening)")
    pts: list[Point] = []
    for p in raw:
        if not isinstance(p, list | tuple) or len(p) != 2:
            raise InvalidFeature("each point must be [x, y]")
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError):
            raise InvalidFeature("coordinates must be numbers") from None
        if not (math.isfinite(x) and math.isfinite(y)):
            raise InvalidFeature("coordinates must be finite")
        pts.append((round(x, 3) + 0.0, round(y, 3) + 0.0))
    length = math.dist(pts[0], pts[1])
    if length < MIN_LENGTH_M:
        raise InvalidFeature(f"the opening must be at least {MIN_LENGTH_M * 100:g} cm long")
    if length > MAX_LENGTH_M:
        raise InvalidFeature(f"the opening can be at most {MAX_LENGTH_M:g} m long")
    return pts


def sides(areas: list[tuple[str, list[Ring]]], a: Point, b: Point, max_areas: int = 2) -> list[str]:
    """The areas on either side of the line a–b (left side first).

    Probes a little way out from the middle of the line on each side; a
    point counts as in an area when inside its outline or within 10 cm.
    """
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    length = math.dist(a, b) or 1.0
    nx, ny = -(b[1] - a[1]) / length, (b[0] - a[0]) / length
    found: list[str] = []
    for sign in (1, -1):
        for d in SIDE_PROBES_M:
            hit = _area_at((mx + sign * nx * d, my + sign * ny * d), areas)
            if hit is not None:
                if hit not in found:
                    found.append(hit)
                break
    return found[:max_areas]


def _area_at(p: Point, areas: list[tuple[str, list[Ring]]]) -> str | None:
    for area_id, rings in areas:
        if any(point_in_ring(p, r) for r in rings):
            return area_id
    best, best_d = None, NEAR_M
    for area_id, rings in areas:
        d = min((distance_to_ring(p, r) for r in rings), default=math.inf)
        if d <= best_d:
            best, best_d = area_id, d
    return best


OpenState = Literal["open", "closed", "unknown"]


def open_state(entity_id: str | None, state: str | None) -> OpenState:
    """Is the linked door/window open? From a binary_sensor or cover state."""
    if not entity_id or state is None:
        return "unknown"
    domain = entity_id.split(".", 1)[0]
    if domain == "binary_sensor":
        return "open" if state == "on" else "closed" if state == "off" else "unknown"
    if domain == "cover":
        if state in ("open", "opening", "closing"):
            return "open"
        return "closed" if state == "closed" else "unknown"
    return "unknown"
