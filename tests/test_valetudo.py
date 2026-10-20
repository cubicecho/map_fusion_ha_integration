"""Valetudo source, and a Dreame + Valetudo house in one frame, inside HA."""
from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.camera import Image
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.map_fusion.const import DOMAIN

from . import synthetic
from .ha_env import (
    FRAME_ID,
    PATCH_IMAGE,
    PATCH_VALETUDO_IMAGE,
    VALETUDO_VACUUM,
    add_dreame,
    add_valetudo,
    link_areas,
    link_valetudo_areas,
    setup_map_fusion,
)

VALETUDO_FRAME = f"{VALETUDO_VACUUM}:map"


@pytest.fixture
def valetudo_image() -> AsyncMock:
    return AsyncMock(return_value=Image("image/png", synthetic.png_with(synthetic.valetudo_doc())))


async def test_valetudo_alone(
    hass: HomeAssistant, hass_ws_client, areas: dict[str, str], valetudo_image: AsyncMock
) -> None:
    await add_valetudo(hass)
    await link_valetudo_areas(hass, {areas["Kitchen"]: ["1"], areas["Office"]: ["2"]})
    with patch(PATCH_VALETUDO_IMAGE, valetudo_image):
        await setup_map_fusion(hass)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/get"})
    (frame,) = (await client.receive_json())["result"]["frames"]
    assert frame["frame_id"] == VALETUDO_FRAME
    assert frame["name"] == "Valetudo robot"
    assert [a["name"] for a in frame["areas"]] == ["Kitchen", "Office"]
    assert frame["areas"][0]["geometry"] == "pixels"
    (source,) = frame["sources"]
    assert source["kind"] == "valetudo"
    # Valetudo's own units are cm, y down.
    a, b, c, d, _tx, _ty = source["transform"]
    assert (a, b, c, d) == (0.01, 0.0, 0.0, 0.01)
    assert [r["segment_id"] for r in frame["unmapped_rooms"]] == ["3"]


async def test_valetudo_rereads_on_a_timer(
    hass: HomeAssistant, areas: dict[str, str], valetudo_image: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    await add_valetudo(hass)
    await link_valetudo_areas(hass, {areas["Kitchen"]: ["1"]})
    with patch(PATCH_VALETUDO_IMAGE, valetudo_image):
        entry = await setup_map_fusion(hass)
        manager = entry.runtime_data
        reads = valetudo_image.await_count
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await manager.async_refresh_now()
        assert valetudo_image.await_count == reads  # not due yet
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass)
        await manager.async_refresh_now()
        assert valetudo_image.await_count == reads + 1

async def test_dreame_and_valetudo_share_a_frame(
    hass: HomeAssistant,
    hass_ws_client,
    areas: dict[str, str],
    image_mock: AsyncMock,
    valetudo_image: AsyncMock,
) -> None:
    await add_dreame(hass)
    await add_valetudo(hass)
    await link_areas(hass, {areas["Kitchen"]: ["1_1"], areas["Office"]: ["1_2"]})
    await link_valetudo_areas(hass, {areas["Kitchen"]: ["1"], areas["Office"]: ["2"], areas["Garage"]: ["3"]})
    with patch(PATCH_IMAGE, image_mock), patch(PATCH_VALETUDO_IMAGE, valetudo_image):
        entry = await setup_map_fusion(hass)

    doc: Any = entry.runtime_data.fused.as_dict()
    (frame,) = doc["frames"]
    roles = {s["source_id"]: s["role"] for s in frame["sources"]}
    # Valetudo links more areas, so it anchors; Dreame is lined up with it.
    assert roles == {VALETUDO_VACUUM: "anchor", "vacuum.d10_plus": "aligned"}
    dreame_src = next(s for s in frame["sources"] if s["role"] == "aligned")
    assert dreame_src["residual_m"] == pytest.approx(0, abs=0.05)
    kitchen = next(a for a in frame["areas"] if a["name"] == "Kitchen")
    assert len(kitchen["sources"]) == 2
    assert kitchen["confidence"] > 0.9
    assert doc["unplaced_areas"] == []

    # The same physical spot, in each vacuum's own coordinates, lands in the same area.
    lx, ly = kitchen["label_point"]
    for vacuum in (VALETUDO_VACUUM, "vacuum.d10_plus"):
        native = await hass.services.async_call(
            DOMAIN, "transform_point", {"x": lx, "y": ly, "source_id": vacuum}, blocking=True, return_response=True
        )
        found = await hass.services.async_call(
            DOMAIN,
            "locate_point",
            {"x": native["x"], "y": native["y"], "source_id": vacuum},
            blocking=True,
            return_response=True,
        )
        assert found["area_id"] == areas["Kitchen"], vacuum
    assert FRAME_ID not in [f["frame_id"] for f in doc["frames"]]
