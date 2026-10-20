"""Dreame (Tasshack/dreame-vacuum) map source.

Entities used, found by unique id on the vacuum's device:

- vacuum `<mac>_dreame_vacuum`: segments + the user's area mapping.
- camera `<mac>_map_map` ("Current map"): `rooms` attribute with bounding
  boxes in vacuum mm (y up), `map_index`, `saved_map_id`.
- camera `<mac>_map_map_data` ("Map data", disabled by default): PNG with
  ValetudoMap JSON → real room outlines.

Source frame (shared by both modes, so switching between them doesn't move
anything): vacuum mm / 1000, y flipped. So `to_native` is always
x_mm = 1000 x, y_mm = -1000 y.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.camera import async_get_image
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from ..model import Rect, SourceMap, SourceRoom, Transform
from . import valetudo_map

_LOGGER = logging.getLogger(__name__)

PLATFORM = "dreame_vacuum"
KIND = "dreame"

# Source frame (m, y down) → vacuum native (mm, y up).
TO_NATIVE = Transform(a=1000.0, d=-1000.0)

# Dreame's ValetudoMap conversion: cm = (mm + 32768) / 10, y flipped against size.y.
_DREAME_INT16_HALF = 32768


@dataclass(slots=True)
class DreameEntities:
    vacuum: str
    map_camera: str | None
    map_data_camera: str | None  # None when missing or disabled
    map_data_disabled: bool


def discover(hass: HomeAssistant) -> list[DreameEntities]:
    """Find Dreame vacuums and their map cameras."""
    registry = er.async_get(hass)
    by_device: dict[str, list[er.RegistryEntry]] = {}
    for entry in registry.entities.values():
        if entry.platform == PLATFORM and entry.device_id:
            by_device.setdefault(entry.device_id, []).append(entry)

    found: list[DreameEntities] = []
    for entries in by_device.values():
        vacuum = next((e for e in entries if e.domain == "vacuum"), None)
        if vacuum is None or vacuum.disabled_by is not None:
            continue
        map_camera = next(
            (e for e in entries if e.domain == "camera" and e.unique_id.endswith("_map_map")), None
        )
        data_camera = next(
            (e for e in entries if e.domain == "camera" and e.unique_id.endswith("_map_map_data")),
            None,
        )
        data_disabled = data_camera is not None and data_camera.disabled_by is not None
        found.append(
            DreameEntities(
                vacuum=vacuum.entity_id,
                map_camera=map_camera.entity_id if map_camera and not map_camera.disabled_by else None,
                map_data_camera=None if data_camera is None or data_disabled else data_camera.entity_id,
                map_data_disabled=data_camera is None or data_disabled,
            )
        )
    return sorted(found, key=lambda d: d.vacuum)


def map_signature(hass: HomeAssistant, ents: DreameEntities) -> tuple[Any, ...] | None:
    """Changes when the room layout changes, not when the robot moves."""
    state = hass.states.get(ents.map_camera) if ents.map_camera else None
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    attrs = state.attributes
    rooms = attrs.get("rooms") or {}
    return (
        attrs.get("saved_map_id"),
        attrs.get("map_index"),
        tuple(
            sorted(
                (str(k), v.get("x0"), v.get("y0"), v.get("x1"), v.get("y1"))
                for k, v in rooms.items()
                if isinstance(v, dict)
            )
        ),
    )


async def async_read(hass: HomeAssistant, ents: DreameEntities) -> SourceMap | None:
    """Read the current map. None when the map camera has nothing yet."""
    state = hass.states.get(ents.map_camera) if ents.map_camera else None
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    attrs = state.attributes
    vacuum_state = hass.states.get(ents.vacuum)
    vacuum_attrs = vacuum_state.attributes if vacuum_state else {}

    map_index = attrs.get("map_index") or vacuum_attrs.get("selected_map_index")
    map_id = attrs.get("saved_map_id") or vacuum_attrs.get("selected_map_id") or attrs.get("map_id")
    if map_index is None or map_id is None:
        _LOGGER.debug("%s: no map index/id yet", ents.map_camera)
        return None
    attr_rooms = _attr_rooms(attrs.get("rooms"))
    warnings: list[str] = []

    rooms: dict[str, SourceRoom] | None = None
    residual: float | None = None
    if ents.map_data_camera:
        try:
            image = await async_get_image(hass, ents.map_data_camera)
            vmap = valetudo_map.parse(valetudo_map.extract_from_png(image.content))
            rooms, residual = pixel_rooms(vmap, attr_rooms)
        except (HomeAssistantError, valetudo_map.ValetudoMapError) as err:
            warnings.append(f"map data unreadable, using room boxes: {err}")
            _LOGGER.warning("%s: %s", ents.map_data_camera, warnings[-1])
    if rooms is None:
        rooms = bbox_rooms(attr_rooms)
        if not ents.map_data_camera:
            warnings.append("Map data camera is disabled, using room boxes")

    return SourceMap(
        source_id=ents.vacuum,
        kind=KIND,
        map_id=str(map_id),
        map_name=vacuum_attrs.get("selected_map"),
        rooms={f"{map_index}_{sid}": _renamed(room, f"{map_index}_{sid}") for sid, room in rooms.items()},
        to_native=TO_NATIVE,
        native_residual_m=residual,
        warnings=warnings,
    )


def pixel_rooms(
    vmap: valetudo_map.ValetudoMap, attr_rooms: dict[str, Rect]
) -> tuple[dict[str, SourceRoom], float | None]:
    """Room outlines, moved into the shared source frame.

    The shift from ValetudoMap metres to the source frame is fitted from the
    rooms' cell boxes against their attribute boxes (same sizes, constant
    offset). Without attribute boxes, Dreame's formula is used.
    """
    rooms = valetudo_map.rooms(vmap)
    pairs = [
        (valetudo_map.cell_bounds(vmap, sid), attr_rooms[sid])
        for sid in rooms
        if sid in attr_rooms
    ]
    residual: float | None = None
    if pairs:
        dx = sum(b.x - a.x for a, b in pairs) / len(pairs)
        dy = sum(b.y - a.y for a, b in pairs) / len(pairs)
        errs = [
            e * e
            for a, b in pairs
            for e in (
                a.x + dx - b.x,
                a.y + dy - b.y,
                a.x + a.width + dx - (b.x + b.width),
                a.y + a.height + dy - (b.y + b.height),
            )
        ]
        residual = (sum(errs) / len(errs)) ** 0.5
    else:
        # x_mm = x_cm * 10 - 32768 ; y_mm = (size_y - y_cm) * 10 - 32768
        dx = -_DREAME_INT16_HALF / 1000
        dy = _DREAME_INT16_HALF / 1000 - vmap.size[1] / 100
    return {sid: _shifted(room, dx, dy) for sid, room in rooms.items()}, residual


def bbox_rooms(attr_rooms: dict[str, Rect]) -> dict[str, SourceRoom]:
    """Fallback: each room is its bounding box."""
    result: dict[str, SourceRoom] = {}
    for sid, rect in attr_rooms.items():
        ring = [
            (rect.x, rect.y),
            (rect.x + rect.width, rect.y),
            (rect.x + rect.width, rect.y + rect.height),
            (rect.x, rect.y + rect.height),
        ]
        result[sid] = SourceRoom(
            segment_id=sid,
            name=None,
            polygons=[ring],
            rect=rect,
            label_point=(rect.x + rect.width / 2, rect.y + rect.height / 2),
            area_m2=rect.width * rect.height,
            geometry="bbox",
        )
    return result


def _attr_rooms(raw: Any) -> dict[str, Rect]:
    """The `rooms` attribute as rects in the source frame (m, y down)."""
    rooms: dict[str, Rect] = {}
    if not isinstance(raw, dict):
        return rooms
    for sid, room in raw.items():
        if not isinstance(room, dict) or room.get("visibility") in ("Hidden", False):
            continue
        try:
            x0, y0, x1, y1 = (float(room[k]) for k in ("x0", "y0", "x1", "y1"))
        except (KeyError, TypeError, ValueError):
            continue
        rooms[str(sid)] = Rect(
            min(x0, x1) / 1000, -max(y0, y1) / 1000, abs(x1 - x0) / 1000, abs(y1 - y0) / 1000
        )
    return rooms


def _shifted(room: SourceRoom, dx: float, dy: float) -> SourceRoom:
    return SourceRoom(
        segment_id=room.segment_id,
        name=room.name,
        polygons=[[(x + dx, y + dy) for x, y in ring] for ring in room.polygons],
        rect=room.rect.shifted(dx, dy),
        label_point=(room.label_point[0] + dx, room.label_point[1] + dy),
        area_m2=room.area_m2,
        geometry=room.geometry,
    )


def _renamed(room: SourceRoom, segment_id: str) -> SourceRoom:
    room.segment_id = segment_id
    return room
