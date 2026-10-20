"""Fake Dreame entities and Map Fusion setup for tests that run inside HA."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.map_fusion.const import DOMAIN

from . import synthetic

MAC = "aa:bb:cc:dd:ee:ff"
VACUUM = "vacuum.d10_plus"
MAP_CAMERA = "camera.d10_plus_map"
DATA_CAMERA = "camera.d10_plus_map_data"
FRAME_ID = f"{VACUUM}:46"
PATCH_IMAGE = "custom_components.map_fusion.sources.dreame.async_get_image"


def map_camera_attrs(**extra: Any) -> dict[str, Any]:
    return {"map_index": 1, "saved_map_id": 46, "rooms": synthetic.attr_rooms(), **extra}


async def add_dreame(hass: HomeAssistant, *, data_camera_enabled: bool = True) -> str:
    """Register a Dreame-like device with a vacuum and two map cameras."""
    dreame_entry = MockConfigEntry(domain="dreame_vacuum")
    dreame_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=dreame_entry.entry_id, identifiers={("dreame_vacuum", MAC)}
    )
    reg = er.async_get(hass)
    for domain, unique_id, object_id, disabled in (
        ("vacuum", f"{MAC}_dreame_vacuum", "d10_plus", False),
        ("camera", f"{MAC}_map_map", "d10_plus_map", False),
        ("camera", f"{MAC}_map_map_data", "d10_plus_map_data", not data_camera_enabled),
    ):
        reg.async_get_or_create(
            domain,
            "dreame_vacuum",
            unique_id,
            suggested_object_id=object_id,
            config_entry=dreame_entry,
            device_id=device.id,
            disabled_by=er.RegistryEntryDisabler.USER if disabled else None,
        )
    hass.states.async_set(VACUUM, "docked", {"selected_map": "Map 1", "selected_map_index": 1})
    hass.states.async_set(MAP_CAMERA, "2026-10-20 01:24:56", map_camera_attrs())
    if data_camera_enabled:
        hass.states.async_set(DATA_CAMERA, "idle", {})
    return device.id


async def link_areas(hass: HomeAssistant, mapping: dict[str, list[str]]) -> None:
    er.async_get(hass).async_update_entity_options(VACUUM, "vacuum", {"area_mapping": mapping})


async def setup_map_fusion(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Map Fusion")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


# Valetudo -----------------------------------------------------------------------

VALETUDO_ID = "ShinyPracticalRobot"
VALETUDO_VACUUM = "vacuum.valetudo_robot"
VALETUDO_CAMERA = "camera.valetudo_robot_map_data"
VALETUDO_SEGMENTS = "sensor.valetudo_robot_map_segments"
PATCH_VALETUDO_IMAGE = "custom_components.map_fusion.sources.valetudo.async_get_image"


async def add_valetudo(hass: HomeAssistant) -> None:
    """Register a Valetudo robot the way its MQTT autodiscovery does."""
    mqtt_entry = MockConfigEntry(domain="mqtt")
    mqtt_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=mqtt_entry.entry_id, identifiers={("mqtt", VALETUDO_ID)}
    )
    reg = er.async_get(hass)
    for domain, suffix, object_id in (
        ("vacuum", "_vacuum", "valetudo_robot"),
        ("camera", "_camera_MapData", "valetudo_robot_map_data"),
        ("sensor", "_sensor_MapSegments", "valetudo_robot_map_segments"),
    ):
        reg.async_get_or_create(
            domain,
            "mqtt",
            f"{VALETUDO_ID}{suffix}",
            suggested_object_id=object_id,
            config_entry=mqtt_entry,
            device_id=device.id,
        )
    hass.states.async_set(VALETUDO_VACUUM, "docked", {"friendly_name": "Valetudo robot"})
    hass.states.async_set(VALETUDO_CAMERA, "idle", {})
    hass.states.async_set(VALETUDO_SEGMENTS, "3", {"1": "Kitchen", "2": "Office", "3": "Nook"})


async def link_valetudo_areas(hass: HomeAssistant, mapping: dict[str, list[str]]) -> None:
    er.async_get(hass).async_update_entity_options(VALETUDO_VACUUM, "vacuum", {"area_mapping": mapping})
