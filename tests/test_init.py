"""End to end inside Home Assistant: fake Dreame entities → websocket API."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.camera import Image
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
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


@pytest.fixture
def image_mock() -> AsyncMock:
    return AsyncMock(return_value=Image("image/png", synthetic.png_with(synthetic.valetudo_doc())))


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


@pytest.fixture
async def areas(hass: HomeAssistant) -> dict[str, str]:
    reg = ar.async_get(hass)
    return {
        name: reg.async_create(name).id for name in ("Kitchen", "Office", "Garage")
    }


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
