"""Websocket API.

Read: `map_fusion/get`, `map_fusion/subscribe`.
Write (admin): `map_fusion/area/set`, `map_fusion/area/clear`.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from . import placements as pl
from .const import DOMAIN
from .coordinator import PlacementError, get_manager
from .model import FusedMap

try:  # HA 2026.10+ validates websocket messages with probatio
    import probatio as vol
except ImportError:  # older HA
    import voluptuous as vol  # type: ignore[no-redef]


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get)
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_area_set)
    websocket_api.async_register_command(hass, ws_area_clear)


def _document(fused: FusedMap | None, frame_id: str | None) -> dict[str, Any] | None:
    if fused is None:
        return None
    doc = fused.as_dict()
    if frame_id is not None:
        doc["frames"] = [f for f in doc["frames"] if f["frame_id"] == frame_id]
    return doc


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/get", vol.Optional("frame_id"): str}
)
@callback
def ws_get(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the fused map (null until the first build)."""
    manager = get_manager(hass)
    if manager is None:
        connection.send_error(msg["id"], "not_loaded", "Map Fusion is not set up")
        return
    connection.send_result(msg["id"], _document(manager.fused, msg.get("frame_id")))


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/subscribe", vol.Optional("frame_id"): str}
)
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send the fused map now (if built) and again on every change."""
    manager = get_manager(hass)
    if manager is None:
        connection.send_error(msg["id"], "not_loaded", "Map Fusion is not set up")
        return
    frame_id = msg.get("frame_id")

    @callback
    def forward(fused: FusedMap) -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], _document(fused, frame_id))
        )

    connection.subscriptions[msg["id"]] = manager.async_subscribe(forward)
    connection.send_result(msg["id"])
    if manager.fused is not None:
        forward(manager.fused)


RECT_SCHEMA = vol.Schema(
    {
        vol.Required("x"): vol.Coerce(float),
        vol.Required("y"): vol.Coerce(float),
        vol.Required("width"): vol.Coerce(float),
        vol.Required("height"): vol.Coerce(float),
    }
)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/area/set",
        vol.Required("area_id"): str,
        vol.Optional("frame_id"): str,
        vol.Exclusive("rect", "shape"): RECT_SCHEMA,
        vol.Exclusive("polygons", "shape"): list,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_area_set(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Place an area by hand (a rect or polygons, in frame metres). Returns the area."""
    manager = get_manager(hass)
    if manager is None:
        connection.send_error(msg["id"], "not_loaded", "Map Fusion is not set up")
        return
    try:
        if "rect" in msg:
            r = msg["rect"]
            rings = [pl.rect_ring(r["x"], r["y"], r["width"], r["height"])]
        elif "polygons" in msg:
            rings = pl.normalise(msg["polygons"])
        else:
            raise pl.InvalidPlacement("give either rect or polygons")
        area = await manager.async_set_area(msg["area_id"], rings, msg.get("frame_id"))
    except pl.InvalidPlacement as err:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))
        return
    except PlacementError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    connection.send_result(msg["id"], area.as_dict())


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/area/clear",
        vol.Required("area_id"): str,
        vol.Optional("frame_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_area_clear(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Remove an area's hand placement. Returns the frame it was in."""
    manager = get_manager(hass)
    if manager is None:
        connection.send_error(msg["id"], "not_loaded", "Map Fusion is not set up")
        return
    try:
        frame_id = await manager.async_clear_area(msg["area_id"], msg.get("frame_id"))
    except PlacementError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    connection.send_result(msg["id"], {"frame_id": frame_id})
