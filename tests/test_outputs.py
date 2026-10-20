"""Read services and the image entity, inside Home Assistant."""
from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import floor_registry as fr

from custom_components.map_fusion.const import DOMAIN

from .ha_env import FRAME_ID, VACUUM

IMAGE = "image.map_fusion_map_1"


async def _call(hass: HomeAssistant, service: str, **data: Any) -> dict[str, Any]:
    return await hass.services.async_call(DOMAIN, service, data, blocking=True, return_response=True)


async def test_get_map(hass: HomeAssistant, ready: Any) -> None:
    doc = await _call(hass, "get_map")
    assert doc["version"] == 1
    assert [f["frame_id"] for f in doc["frames"]] == [FRAME_ID]
    assert (await _call(hass, "get_map", frame_id=FRAME_ID))["frames"][0]["name"] == "Map 1"
    with pytest.raises(ServiceValidationError, match="does not exist"):
        await _call(hass, "get_map", frame_id="nope")


async def test_transform_point_both_ways(hass: HomeAssistant, ready: Any) -> None:
    native = await _call(hass, "transform_point", x=1, y=2)
    assert native["source_id"] == VACUUM and native["frame_id"] == FRAME_ID
    back = await _call(hass, "transform_point", x=native["x"], y=native["y"], to="frame", source_id=VACUUM)
    assert (back["x"], back["y"]) == pytest.approx((1, 2))
    with pytest.raises(ServiceValidationError, match="No frame uses"):
        await _call(hass, "transform_point", x=0, y=0, source_id="vacuum.other")


async def test_locate_point(hass: HomeAssistant, areas: dict[str, str], ready: Any) -> None:
    kitchen = ready.runtime_data.fused.frames[0].areas[0]
    lx, ly = kitchen.label_point
    found = await _call(hass, "locate_point", x=lx, y=ly)
    assert found["area_id"] == areas["Kitchen"] and found["inside"] is True

    # The same spot in the vacuum's own coordinates (e.g. the robot's position).
    native = await _call(hass, "transform_point", x=lx, y=ly)
    by_vacuum = await _call(hass, "locate_point", x=native["x"], y=native["y"], source_id=VACUUM)
    assert by_vacuum["area_id"] == areas["Kitchen"]
    assert (by_vacuum["x"], by_vacuum["y"]) == pytest.approx((lx, ly), abs=1e-3)

    assert (await _call(hass, "locate_point", x=500, y=500))["area_id"] is None


async def test_image_entity(hass: HomeAssistant, hass_client, ready: Any) -> None:
    state = hass.states.get(IMAGE)
    assert state is not None, hass.states.async_entity_ids("image")
    assert state.attributes["frame_id"] == FRAME_ID
    assert state.attributes["area_count"] == 1
    assert len(state.attributes["calibration_points"]) == 3

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{IMAGE}")
    assert resp.status == 200
    assert resp.headers["Content-Type"].startswith("image/svg+xml")
    body = await resp.text()
    assert body.startswith("<svg") and "Kitchen" in body


async def test_image_updates_with_the_map(hass: HomeAssistant, areas: dict[str, str], ready: Any) -> None:
    before = hass.states.get(IMAGE).state
    await hass.services.async_call(
        DOMAIN, "set_area", {"area_id": areas["Garage"], "x": 20, "y": 0, "width": 3, "height": 3}, blocking=True
    )
    await hass.async_block_till_done()
    after = hass.states.get(IMAGE)
    assert after.state != before
    assert after.attributes["area_count"] == 2


async def test_moved_frame_gets_a_new_image(hass: HomeAssistant, ready: Any) -> None:
    floor = fr.async_get(hass).async_create("Ground")
    await ready.runtime_data.async_set_floor_choice(FRAME_ID, floor.floor_id, auto=False)
    await hass.async_block_till_done()
    assert hass.states.get(IMAGE).state == STATE_UNAVAILABLE
    assert hass.states.get("image.map_fusion_ground") is not None


# Filled shapes ---------------------------------------------------------------------


async def test_filled_variant_everywhere(hass: HomeAssistant, hass_ws_client, ready: Any) -> None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/get", "variant": "filled"})
    doc = (await client.receive_json())["result"]
    assert doc["variant"] == "filled"
    area = doc["frames"][0]["areas"][0]
    assert area["polygons"] == area["filled_polygons"]

    await client.send_json_auto_id({"type": f"{DOMAIN}/get", "variant": "nope"})
    assert not (await client.receive_json())["success"]

    svc = await _call(hass, "get_map", variant="filled")
    assert svc["variant"] == "filled"

    filled_image = hass.states.get("image.map_fusion_map_1_filled")
    assert filled_image is not None
    assert filled_image.attributes["variant"] == "filled"
    assert hass.states.get(IMAGE).attributes["variant"] == "traced"


async def test_fill_setting_rereads_and_is_stored(
    hass: HomeAssistant, ready: Any, image_mock: Any, hass_storage: dict[str, Any]
) -> None:
    manager = ready.runtime_data
    reads = image_mock.await_count
    result = await hass.config_entries.options.async_init(ready.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "filled_shapes"})
    assert result["step_id"] == "filled_shapes"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"fill_max_m": 0})
    assert manager.fill_max_m == 0
    assert image_mock.await_count == reads + 1
    kitchen = manager.fused.frames[0].areas[0]
    assert kitchen.filled_polygons == kitchen.polygons  # filling off: same as traced
    assert hass_storage[DOMAIN]["data"]["settings"] == {"fill_max_m": 0}


# Sidebar page -----------------------------------------------------------------------


async def test_panel_is_registered_when_the_frontend_is_loaded(
    hass: HomeAssistant, hass_client, areas: dict[str, str], image_mock: Any
) -> None:
    from unittest.mock import AsyncMock, patch

    from homeassistant.setup import async_setup_component

    from custom_components.map_fusion import panel

    assert await async_setup_component(hass, "http", {})
    client = await hass_client()
    hass.config.components.add("frontend")
    with (
        patch("custom_components.map_fusion.panel.panel_custom.async_register_panel", new=AsyncMock()) as register,
        patch("custom_components.map_fusion.panel.frontend.async_remove_panel") as remove,
    ):
        await panel.async_register(hass)
        await panel.async_register(hass)  # a reload: static path isn't registered twice
        kwargs = register.await_args.kwargs
        assert kwargs["frontend_url_path"] == "map-fusion"
        assert kwargs["webcomponent_name"] == "map-fusion-panel"
        assert kwargs["require_admin"] is True
        assert kwargs["module_url"].startswith("/map_fusion_static/map-fusion-panel.js?v=")
        panel.async_unregister(hass)
        remove.assert_called_once()

    # The bundle is served from the integration folder.
    resp = await client.get("/map_fusion_static/map-fusion-panel.js")
    assert resp.status == 200
    assert (await resp.text()).startswith("/*! map-fusion-panel v")
