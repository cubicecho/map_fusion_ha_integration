"""Websocket API: `map_fusion/get` and `map_fusion/subscribe`."""
from __future__ import annotations

from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import MapFusionManager
from .model import FusedMap

try:  # HA 2026.10+ validates websocket messages with probatio
    import probatio as vol
except ImportError:  # older HA
    import voluptuous as vol  # type: ignore[no-redef]


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get)
    websocket_api.async_register_command(hass, ws_subscribe)


def _manager(hass: HomeAssistant) -> MapFusionManager | None:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


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
    manager = _manager(hass)
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
    manager = _manager(hass)
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
