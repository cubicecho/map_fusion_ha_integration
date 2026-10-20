"""End to end inside Home Assistant: fake Dreame entities → websocket API."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.camera import Image
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.map_fusion.const import DOMAIN

from . import synthetic
from .ha_env import (
    DATA_CAMERA,
    FRAME_ID,
    MAP_CAMERA,
    PATCH_IMAGE,
    VACUUM,
    add_dreame,
    link_areas,
    map_camera_attrs,
    setup_map_fusion,
)


async def test_fused_map_over_websocket(
    hass: HomeAssistant, hass_ws_client, areas: dict[str, str], image_mock: AsyncMock
) -> None:
    await add_dreame(hass)
    await link_areas(hass, {areas["Kitchen"]: ["1_1"], areas["Office"]: ["1_2", "1_3"]})
    with patch(PATCH_IMAGE, image_mock):
        await setup_map_fusion(hass)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/get"})
    msg = await client.receive_json()
    assert msg["success"], msg
    doc = msg["result"]

    (frame,) = doc["frames"]
    assert frame["frame_id"] == FRAME_ID
    assert frame["floor_id"] is None
    assert [a["name"] for a in frame["areas"]] == ["Kitchen", "Office"]
    kitchen = frame["areas"][0]
    assert kitchen["geometry"] == "pixels"
    assert kitchen["rect"]["x"] == 0 and kitchen["rect"]["y"] == 0
    assert frame["sources"][0]["residual_m"] == pytest.approx(0, abs=1e-3)
    assert [a["name"] for a in doc["unplaced_areas"]] == ["Garage"]
    image_mock.assert_awaited_once_with(hass, DATA_CAMERA)

    # Filter by frame
    await client.send_json_auto_id({"type": f"{DOMAIN}/get", "frame_id": "nope"})
    msg = await client.receive_json()
    assert msg["result"]["frames"] == []


async def test_subscribe_pushes_updates_when_links_change(
    hass: HomeAssistant, hass_ws_client, areas: dict[str, str], image_mock: AsyncMock
) -> None:
    await add_dreame(hass)
    await link_areas(hass, {areas["Kitchen"]: ["1_1"]})
    with patch(PATCH_IMAGE, image_mock):
        entry = await setup_map_fusion(hass)

        client = await hass_ws_client(hass)
        await client.send_json_auto_id({"type": f"{DOMAIN}/subscribe"})
        assert (await client.receive_json())["success"]
        first = (await client.receive_json())["event"]
        assert [a["name"] for a in first["frames"][0]["areas"]] == ["Kitchen"]

        await link_areas(hass, {areas["Kitchen"]: ["1_1"], areas["Office"]: ["1_2"]})
        await entry.runtime_data.async_refresh_now()
        second = (await client.receive_json())["event"]
        assert [a["name"] for a in second["frames"][0]["areas"]] == ["Kitchen", "Office"]

    # Link changes don't re-read the map image, only layout changes do.
    assert image_mock.await_count == 1


async def test_robot_moves_dont_reread_but_layout_changes_do(
    hass: HomeAssistant, areas: dict[str, str], image_mock: AsyncMock
) -> None:
    await add_dreame(hass)
    await link_areas(hass, {areas["Kitchen"]: ["1_1"]})
    with patch(PATCH_IMAGE, image_mock):
        entry = await setup_map_fusion(hass)
        manager = entry.runtime_data

        hass.states.async_set(MAP_CAMERA, "2026-10-20 01:30:00", map_camera_attrs(frame_id=999))
        await manager.async_refresh_now()
        assert image_mock.await_count == 1

        rooms = synthetic.attr_rooms()
        rooms["1"]["x1"] += 500
        hass.states.async_set(MAP_CAMERA, "2026-10-20 01:31:00", map_camera_attrs(rooms=rooms))
        await manager.async_refresh_now()
        assert image_mock.await_count == 2


async def test_disabled_map_data_falls_back_to_boxes_and_raises_issue(
    hass: HomeAssistant, hass_ws_client, areas: dict[str, str]
) -> None:
    await add_dreame(hass, data_camera_enabled=False)
    await link_areas(hass, {areas["Kitchen"]: ["1_1"]})
    with patch(PATCH_IMAGE) as image:
        await setup_map_fusion(hass)
        image.assert_not_called()

    assert ir.async_get(hass).async_get_issue(DOMAIN, f"map_data_disabled_{VACUUM}")

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/get"})
    frame = (await client.receive_json())["result"]["frames"][0]
    assert frame["areas"][0]["geometry"] == "bbox"
    assert frame["sources"][0]["warnings"]


async def test_unreadable_map_data_falls_back_to_boxes(
    hass: HomeAssistant, hass_ws_client, areas: dict[str, str]
) -> None:
    await add_dreame(hass)
    await link_areas(hass, {areas["Kitchen"]: ["1_1"]})
    bad = AsyncMock(return_value=Image("image/png", synthetic.png_with(None)))
    with patch(PATCH_IMAGE, bad):
        await setup_map_fusion(hass)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/get"})
    frame = (await client.receive_json())["result"]["frames"][0]
    assert frame["areas"][0]["geometry"] == "bbox"
    assert "unreadable" in frame["sources"][0]["warnings"][0]


async def test_frame_origin_survives_restart(
    hass: HomeAssistant, areas: dict[str, str], image_mock: AsyncMock, hass_storage: dict[str, Any]
) -> None:
    await add_dreame(hass)
    await link_areas(hass, {areas["Kitchen"]: ["1_1"]})
    hass_storage[DOMAIN] = {
        "version": 1,
        "key": DOMAIN,
        "data": {"frames": {FRAME_ID: {"anchor": FRAME_ID, "origin": [-40.0, -40.0]}}},
    }
    with patch(PATCH_IMAGE, image_mock):
        entry = await setup_map_fusion(hass)
    kitchen = entry.runtime_data.fused.frames[0].areas[0]
    assert kitchen.rect.x > 0  # shifted by the stored origin, not reset to 0


async def test_no_vacuums_still_lists_areas(
    hass: HomeAssistant, hass_ws_client, areas: dict[str, str]
) -> None:
    await setup_map_fusion(hass)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/get"})
    doc = (await client.receive_json())["result"]
    assert doc["frames"] == []
    assert len(doc["unplaced_areas"]) == 3


async def test_unload(hass: HomeAssistant, areas: dict[str, str]) -> None:
    entry = await setup_map_fusion(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
