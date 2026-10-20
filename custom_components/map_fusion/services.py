"""Services.

Write: `set_area`, `clear_area`. Read (return a response):
`get_map`, `transform_point`, `locate_point`.
"""
from __future__ import annotations

from typing import Any

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from . import placements as pl
from .const import DOMAIN
from .coordinator import MapFusionManager, get_manager
from .model import FusedFrame, Ring
from .queries import QueryError, document, find_frame, locate, to_frame, to_source

try:  # HA 2026.10+ validates with probatio
    import probatio as vol
except ImportError:  # older HA
    import voluptuous as vol  # type: ignore[no-redef]

SERVICE_SET_AREA = "set_area"
SERVICE_CLEAR_AREA = "clear_area"
SERVICE_GET_MAP = "get_map"
SERVICE_TRANSFORM_POINT = "transform_point"
SERVICE_LOCATE_POINT = "locate_point"

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
GET_MAP_SCHEMA = vol.Schema({vol.Optional("frame_id"): cv.string})
POINT_FIELDS = {
    vol.Optional("frame_id"): cv.string,
    vol.Optional("source_id"): cv.entity_id,
    vol.Required("x"): vol.Coerce(float),
    vol.Required("y"): vol.Coerce(float),
}
TRANSFORM_POINT_SCHEMA = vol.Schema(
    {**POINT_FIELDS, vol.Optional("to", default="source"): vol.In(["source", "frame"])}
)
LOCATE_POINT_SCHEMA = vol.Schema(POINT_FIELDS)


@callback
def async_register(hass: HomeAssistant) -> None:
    hass.services.async_register(DOMAIN, SERVICE_SET_AREA, _set_area, schema=SET_AREA_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_AREA, _clear_area, schema=CLEAR_AREA_SCHEMA)
    for name, handler, schema in (
        (SERVICE_GET_MAP, _get_map, GET_MAP_SCHEMA),
        (SERVICE_TRANSFORM_POINT, _transform_point, TRANSFORM_POINT_SCHEMA),
        (SERVICE_LOCATE_POINT, _locate_point, LOCATE_POINT_SCHEMA),
    ):
        hass.services.async_register(
            DOMAIN, name, handler, schema=schema, supports_response=SupportsResponse.ONLY
        )


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


def _frame(call: ServiceCall) -> FusedFrame:
    manager = _manager(call.hass)
    try:
        return find_frame(manager.fused, call.data.get("frame_id"), call.data.get("source_id"))
    except QueryError as err:
        raise ServiceValidationError(str(err)) from err


async def _get_map(call: ServiceCall) -> ServiceResponse:
    manager = _manager(call.hass)
    frame_id = call.data.get("frame_id")
    if frame_id is not None:
        _frame(call)  # error out on unknown frames
    return document(manager.fused, frame_id) or {"version": None, "frames": [], "unplaced_areas": []}


async def _transform_point(call: ServiceCall) -> ServiceResponse:
    """Frame metres → vacuum native coordinates (to: source), or back (to: frame)."""
    frame = _frame(call)
    point = (call.data["x"], call.data["y"])
    convert = to_source if call.data["to"] == "source" else to_frame
    try:
        source_id, (x, y) = convert(frame, call.data.get("source_id"), point)
    except QueryError as err:
        raise ServiceValidationError(str(err)) from err
    return {"frame_id": frame.frame_id, "source_id": source_id, "x": round(x, 4), "y": round(y, 4)}


async def _locate_point(call: ServiceCall) -> ServiceResponse:
    """Which area a point is in. With source_id, the point is in that vacuum's coordinates."""
    frame = _frame(call)
    point = (call.data["x"], call.data["y"])
    if "source_id" in call.data:
        try:
            _sid, point = to_frame(frame, call.data["source_id"], point)
        except QueryError as err:
            raise ServiceValidationError(str(err)) from err
    return {
        "frame_id": frame.frame_id,
        "x": round(point[0], 4),
        "y": round(point[1], 4),
        **locate(frame, point),
    }
