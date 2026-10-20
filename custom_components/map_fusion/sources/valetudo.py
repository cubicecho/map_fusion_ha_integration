"""Valetudo map source (Valetudo's own MQTT autodiscovery).

Entities used, found by unique id on the robot's MQTT device
(`<id>` is Valetudo's identifier, e.g. its system id):

- vacuum `<id>_vacuum`: segments (when the robot supports segment
  cleaning) + the user's area mapping, like any core vacuum.
- camera `<id>_camera_MapData` ("Map data"): a PNG wrapper with the
  ValetudoMap JSON in a zTXt chunk. Same parser as Dreame.
- sensor `<id>_sensor_MapSegments` (optional): segment id → name in its
  attributes. Used to notice room edits.

Coordinates: Valetudo's own frame is cm with y down, the same grid as the
map pixels (cells × pixelSize). The source frame is that in metres, so
`to_native` is just ×100.

The Map data camera's image changes with every map update, but Home
Assistant sees no state change for it, so the map is also re-read every
`POLL_INTERVAL`.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.camera import async_get_image
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from ..model import SourceMap, Transform
from . import valetudo_map
from .base import SourceDevice

_LOGGER = logging.getLogger(__name__)

PLATFORM = "mqtt"
KIND = "valetudo"
POLL_INTERVAL = timedelta(minutes=10)
MAP_ID = "map"  # Valetudo keeps one map

# Source frame (m, y down) → Valetudo native (cm, y down).
TO_NATIVE = Transform(a=100.0, d=100.0)

VACUUM_SUFFIX = "_vacuum"
MAP_DATA_SUFFIX = "_camera_MapData"
SEGMENTS_SUFFIX = "_sensor_MapSegments"


def discover(hass: HomeAssistant) -> list[SourceDevice]:
    """Find Valetudo robots: an MQTT vacuum with a Map data camera on its device."""
    registry = er.async_get(hass)
    by_device: dict[str, list[er.RegistryEntry]] = {}
    for entry in registry.entities.values():
        if entry.platform == PLATFORM and entry.device_id:
            by_device.setdefault(entry.device_id, []).append(entry)

    found: list[SourceDevice] = []
    for entries in by_device.values():
        vacuum = _find(entries, "vacuum", VACUUM_SUFFIX)
        camera = _find(entries, "camera", MAP_DATA_SUFFIX)
        if vacuum is None or camera is None or vacuum.disabled_by or camera.disabled_by:
            continue
        segments = _find(entries, "sensor", SEGMENTS_SUFFIX)
        segments_id = segments.entity_id if segments and not segments.disabled_by else None
        found.append(
            SourceDevice(
                kind=KIND,
                vacuum=vacuum.entity_id,
                tracked=[e for e in (vacuum.entity_id, segments_id) if e],
                extra={"camera": camera.entity_id, "segments": segments_id},
            )
        )
    return sorted(found, key=lambda d: d.vacuum)


def _find(entries: list[er.RegistryEntry], domain: str, suffix: str) -> er.RegistryEntry | None:
    return next((e for e in entries if e.domain == domain and e.unique_id.endswith(suffix)), None)


def map_signature(hass: HomeAssistant, device: SourceDevice) -> tuple[Any, ...] | None:
    """Changes when rooms are added, removed or renamed."""
    camera = hass.states.get(device.extra["camera"])
    if camera is None or camera.state == STATE_UNAVAILABLE:
        return None
    segments_id = device.extra["segments"]
    segments = hass.states.get(segments_id) if segments_id else None
    if segments is None or segments.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return ("no-segments-sensor",)
    attrs = {k: v for k, v in segments.attributes.items() if k not in ("friendly_name", "icon")}
    return (segments.state, tuple(sorted((str(k), str(v)) for k, v in attrs.items())))


async def async_read(
    hass: HomeAssistant, device: SourceDevice, *, fill_max_m: float = valetudo_map.DEFAULT_FILL_MAX_M
) -> SourceMap | None:
    """Read the map from the Map data camera. None when it has no map yet."""
    camera = device.extra["camera"]
    try:
        image = await async_get_image(hass, camera)
        vmap = valetudo_map.parse(valetudo_map.extract_from_png(image.content))
    except (HomeAssistantError, valetudo_map.ValetudoMapError) as err:
        _LOGGER.debug("%s: no readable map yet: %s", camera, err)
        return None
    rooms = valetudo_map.rooms(vmap, fill_max_m=fill_max_m)
    if not rooms:
        return None
    vacuum = hass.states.get(device.vacuum)
    name = vacuum.attributes.get("friendly_name") if vacuum else None
    return SourceMap(
        source_id=device.vacuum,
        kind=KIND,
        map_id=MAP_ID,
        map_name=str(name) if name else None,
        rooms=rooms,
        to_native=TO_NATIVE,
    )
