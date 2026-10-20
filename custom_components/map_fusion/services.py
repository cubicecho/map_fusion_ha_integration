"""Services: `map_fusion.set_area` and `map_fusion.clear_area`."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from . import placements as pl
from .const import DOMAIN
from .coordinator import MapFusionManager, get_manager
from .model import Ring

try:  # HA 2026.10+ validates with probatio
    import probatio as vol
except ImportError:  # older HA
    import voluptuous as vol  # type: ignore[no-redef]

SERVICE_SET_AREA = "set_area"
SERVICE_CLEAR_AREA = "clear_area"

RECT_FIELDS = ("x", "y", "width", "height")

SET_AREA_SCHEMA = vol.Schema(
    {
        vol.Required("area_id"): cv.string,
        vol.Optional("frame_id"): cv.string,
        **{vol.Inclusive(k, "rect"): vol.Coerce(float) for k in RECT_FIELDS},
        vol.Optional("polygons"): list,
    }
)
CLEAR_AREA_SCHEMA = vol.Schema(
    {vol.Required("area_id"): cv.string, vol.Optional("frame_id"): cv.string}
)


@callback
def async_register(hass: HomeAssistant) -> None:
    hass.services.async_register(DOMAIN, SERVICE_SET_AREA, _set_area, schema=SET_AREA_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_AREA, _clear_area, schema=CLEAR_AREA_SCHEMA)


def _manager(hass: HomeAssistant) -> MapFusionManager:
    manager = get_manager(hass)
    if manager is None:
        raise ServiceValidationError("Map Fusion is not set up")
    return manager


def _rings(data: dict[str, Any]) -> list[Ring]:
    has_rect = "x" in data
    has_polygons = "polygons" in data
    if has_rect == has_polygons:
        raise ServiceValidationError("Give either x, y, width and height, or polygons")
    try:
        if has_rect:
            return [pl.rect_ring(*(data[k] for k in RECT_FIELDS))]
        return pl.normalise(data["polygons"])
    except pl.InvalidPlacement as err:
        raise ServiceValidationError(f"Invalid shape: {err}") from err


async def _set_area(call: ServiceCall) -> None:
    manager = _manager(call.hass)
    await manager.async_set_area(call.data["area_id"], _rings(dict(call.data)), call.data.get("frame_id"))


async def _clear_area(call: ServiceCall) -> None:
    manager = _manager(call.hass)
    await manager.async_clear_area(call.data["area_id"], call.data.get("frame_id"))
