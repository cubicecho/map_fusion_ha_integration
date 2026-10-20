"""Config flow tests."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import floor_registry as fr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.map_fusion.const import DOMAIN

from .ha_env import FRAME_ID


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Map Fusion"


# Options flow -----------------------------------------------------------------

async def _menu(hass: HomeAssistant, entry: Any, choice: str) -> dict[str, Any]:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": choice})


async def test_options_place_and_clear_an_area(
    hass: HomeAssistant, areas: dict[str, str], ready: Any
) -> None:
    manager = ready.runtime_data
    result = await _menu(hass, ready, "place_area")
    assert result["step_id"] == "place_area"
    assert "frame_id" not in result["data_schema"].schema  # only one frame

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"area_id": areas["Garage"]}
    )
    assert result["step_id"] == "place_rect"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"x": 1, "y": 2, "width": 3, "height": 4}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert manager.placements[FRAME_ID][areas["Garage"]] == [[(1, 2), (4, 2), (4, 6), (1, 6)]]

    # Placing it again starts from the current rectangle.
    result = await _menu(hass, ready, "place_area")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"area_id": areas["Garage"]}
    )
    defaults = {str(k): k.default() for k in result["data_schema"].schema}
    assert defaults == {"x": 1, "y": 2, "width": 3, "height": 4}
    hass.config_entries.options.async_abort(result["flow_id"])

    result = await _menu(hass, ready, "clear_area")
    assert result["step_id"] == "clear_area"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"placement": f"{FRAME_ID}|{areas['Garage']}"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert manager.placements == {}

    result = await _menu(hass, ready, "clear_area")
    assert result["reason"] == "no_placements"


async def test_options_map_floor(hass: HomeAssistant, areas: dict[str, str], ready: Any) -> None:
    manager = ready.runtime_data
    floor = fr.async_get(hass).async_create("Ground")
    await hass.async_block_till_done()
    source_key = FRAME_ID  # a floor-less frame is named after its source map

    result = await _menu(hass, ready, "map_floor")
    assert result["step_id"] == "map_floor"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"map": source_key, "floor": floor.floor_id}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert manager.floor_choices == {source_key: floor.floor_id}
    assert [f.frame_id for f in manager.fused.frames] == [floor.floor_id]

    result = await _menu(hass, ready, "map_floor")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"map": source_key, "floor": "auto"}
    )
    assert manager.floor_choices == {}
    assert [f.frame_id for f in manager.fused.frames] == [FRAME_ID]


async def test_options_need_a_loaded_entry(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["reason"] == "not_loaded"
