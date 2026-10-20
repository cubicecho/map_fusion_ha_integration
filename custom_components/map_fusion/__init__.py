"""Map Fusion: one area-aware map built from robot vacuum maps.

See .agents/plan.md for the design.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import websocket
from .const import DOMAIN
from .coordinator import MapFusionManager

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MapFusionConfigEntry = ConfigEntry[MapFusionManager]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the websocket API once."""
    websocket.async_register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MapFusionConfigEntry) -> bool:
    """Set up Map Fusion from a config entry."""
    manager = MapFusionManager(hass)
    entry.runtime_data = manager
    await manager.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MapFusionConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.async_stop()
    return True
