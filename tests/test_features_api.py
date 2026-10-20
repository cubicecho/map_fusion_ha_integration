"""Doors and windows inside Home Assistant: websocket, services, image, storage."""
from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.map_fusion.const import DOMAIN

from .ha_env import FRAME_ID

IMAGE = "image.map_fusion_map_1"
# On the synthetic Kitchen's right wall (x = 2). Only Kitchen is linked in the
# `ready` setup, so the door joins just the Kitchen.
DOOR = {"kind": "door", "points": [[2.025, 0.2], [2.025, 0.8]], "name": "Kitchen door"}


async def _ws(client: Any, **msg: Any) -> dict[str, Any]:
    await client.send_json_auto_id(msg)
    return await client.receive_json()


@pytest.fixture
def door_sensor(hass: HomeAssistant) -> str:
    hass.states.async_set("binary_sensor.kitchen_door", "off", {"device_class": "door"})
    return "binary_sensor.kitchen_door"


async def test_add_change_and_remove_a_door(
    hass: HomeAssistant, hass_ws_client, areas: dict[str, str], ready: Any, door_sensor: str
) -> None:
    client = await hass_ws_client(hass)
    msg = await _ws(client, type=f"{DOMAIN}/feature/set", **DOOR, entity_id=door_sensor)
    assert msg["success"], msg
    door = msg["result"]
    assert door["kind"] == "door" and door["entity_id"] == door_sensor
    assert door["areas"] == [areas["Kitchen"]]  # Office isn't linked in this setup
    feature_id = door["feature_id"]

    doc = (await _ws(client, type=f"{DOMAIN}/get"))["result"]
    assert [f["feature_id"] for f in doc["frames"][0]["features"]] == [feature_id]
    assert set(doc["feature_kinds"]) == {"door", "window"}

    # Change it: same id, new name, explicit areas.
    msg = await _ws(
        client,
        type=f"{DOMAIN}/feature/set",
        feature_id=feature_id,
        **{**DOOR, "name": "Pantry door"},
        areas=[areas["Kitchen"], areas["Garage"]],
    )
    assert msg["result"]["name"] == "Pantry door"
    assert msg["result"]["areas_auto"] is False
    assert len(ready.runtime_data.features[FRAME_ID]) == 1

    msg = await _ws(client, type=f"{DOMAIN}/feature/remove", feature_id=feature_id)
    assert msg["result"] == {"frame_id": FRAME_ID}
    assert ready.runtime_data.features == {}
    msg = await _ws(client, type=f"{DOMAIN}/feature/remove", feature_id=feature_id)
    assert msg["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    "extra,code",
    [
        ({"kind": "chimney"}, "invalid_format"),
        ({"points": [[0, 0]]}, "invalid_format"),
        ({"entity_id": "light.kitchen"}, "invalid_format"),
        ({"entity_id": "binary_sensor.nope"}, "not_found"),
        ({"areas": ["nope"]}, "not_found"),
        ({"frame_id": "nope"}, "not_found"),
        ({"feature_id": "nope"}, "not_found"),
    ],
)
async def test_bad_features_are_rejected(
    hass: HomeAssistant, hass_ws_client, ready: Any, extra: dict[str, Any], code: str
) -> None:
    client = await hass_ws_client(hass)
    msg = await _ws(client, type=f"{DOMAIN}/feature/set", **{**DOOR, **extra})
    assert msg["error"]["code"] == code, msg


async def test_writes_need_an_admin(hass: HomeAssistant, hass_ws_client, hass_read_only_access_token: str, ready: Any) -> None:
    client = await hass_ws_client(hass, hass_read_only_access_token)
    assert (await _ws(client, type=f"{DOMAIN}/feature/set", **DOOR))["error"]["code"] == "unauthorized"
    assert (await _ws(client, type=f"{DOMAIN}/feature/remove", feature_id="x"))["error"]["code"] == "unauthorized"


async def test_services(hass: HomeAssistant, ready: Any, door_sensor: str) -> None:
    door = await hass.services.async_call(
        DOMAIN, "set_feature", {**DOOR, "entity_id": door_sensor}, blocking=True, return_response=True
    )
    assert door["kind"] == "door"
    # Without asking for a response it still works.
    await hass.services.async_call(
        DOMAIN, "set_feature", {"kind": "window", "points": [[4.05, 0.5], [4.05, 1.5]]}, blocking=True
    )
    assert len(ready.runtime_data.features[FRAME_ID]) == 2
    with pytest.raises(ServiceValidationError, match="binary_sensor, cover"):
        await hass.services.async_call(
            DOMAIN, "set_feature", {**DOOR, "entity_id": "light.x"}, blocking=True, return_response=True
        )
    await hass.services.async_call(DOMAIN, "remove_feature", {"feature_id": door["feature_id"]}, blocking=True)
    assert len(ready.runtime_data.features[FRAME_ID]) == 1


async def test_features_are_stored_and_reloaded(
    hass: HomeAssistant, ready: Any, hass_storage: dict[str, Any]
) -> None:
    door = await hass.services.async_call(DOMAIN, "set_feature", DOOR, blocking=True, return_response=True)
    stored = hass_storage[DOMAIN]["data"]["features"]
    assert stored[FRAME_ID][door["feature_id"]]["name"] == "Kitchen door"
    assert await hass.config_entries.async_reload(ready.entry_id)
    await hass.async_block_till_done()
    (feature,) = ready.runtime_data.fused.frames[0].features
    assert feature.feature_id == door["feature_id"]


async def test_deleting_an_area_drops_it_from_features(
    hass: HomeAssistant, areas: dict[str, str], ready: Any
) -> None:
    from homeassistant.helpers import area_registry as ar

    await hass.services.async_call(
        DOMAIN, "set_feature", {**DOOR, "areas": [areas["Kitchen"], areas["Garage"]]}, blocking=True
    )
    ar.async_get(hass).async_delete(areas["Garage"])
    await hass.async_block_till_done()
    (stored,) = ready.runtime_data.features[FRAME_ID].values()
    assert stored["areas"] == [areas["Kitchen"]]


async def test_image_shows_open_doors(hass: HomeAssistant, hass_client, ready: Any, door_sensor: str) -> None:
    await hass.services.async_call(DOMAIN, "set_feature", {**DOOR, "entity_id": door_sensor}, blocking=True)
    await hass.async_block_till_done()
    client = await hass_client()

    async def svg() -> str:
        return await (await client.get(f"/api/image_proxy/{IMAGE}")).text()

    assert "feature-door closed" in await svg()
    before = hass.states.get(IMAGE).state
    hass.states.async_set(door_sensor, "on", {"device_class": "door"})
    await hass.async_block_till_done()
    assert "feature-door open" in await svg()
    assert hass.states.get(IMAGE).state != before  # picture cards refresh
