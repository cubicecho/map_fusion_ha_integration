"""User placements inside Home Assistant: websocket, services, storage."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import floor_registry as fr

from custom_components.map_fusion.const import DOMAIN

from .ha_env import FRAME_ID

GARAGE_RECT = {"x": 12.0, "y": 0.0, "width": 3.0, "height": 5.0}


async def _ws(client: Any, **msg: Any) -> dict[str, Any]:
    await client.send_json_auto_id(msg)
    return await client.receive_json()


async def test_set_rect_over_websocket(
    hass: HomeAssistant, hass_ws_client, areas: dict[str, str], ready: Any
) -> None:
    client = await hass_ws_client(hass)
    await _ws(client, type=f"{DOMAIN}/subscribe")
    first = await client.receive_json()
    assert "Garage" in [a["name"] for a in first["event"]["unplaced_areas"]]

    # frame_id is optional with one frame.
    msg = await _ws(client, type=f"{DOMAIN}/area/set", area_id=areas["Garage"], rect=GARAGE_RECT)
    # The subscription push can arrive before the result.
    replies = [msg, await client.receive_json()]
    result = next(r for r in replies if r.get("type") == "result")
    pushed = next(r for r in replies if r.get("type") == "event")["event"]

    assert result["success"], result
    assert result["result"]["origin"] == "manual"
    assert result["result"]["rect"] == GARAGE_RECT
    assert result["result"]["polygons"] == [[[12, 0], [15, 0], [15, 5], [12, 5]]]
    assert [a["name"] for a in pushed["unplaced_areas"]] == ["Office"]
    garage = next(a for a in pushed["frames"][0]["areas"] if a["name"] == "Garage")
    assert garage["geometry"] == "manual"


async def test_set_polygons_and_clear(
    hass: HomeAssistant, hass_ws_client, areas: dict[str, str], ready: Any
) -> None:
    client = await hass_ws_client(hass)
    l_shape = [[[0, 0], [4, 0], [4, 1], [1, 1], [1, 3], [0, 3]]]
    msg = await _ws(
        client, type=f"{DOMAIN}/area/set", frame_id=FRAME_ID, area_id=areas["Office"], polygons=l_shape
    )
    assert msg["success"], msg
    assert msg["result"]["area_m2"] == pytest.approx(6)

    msg = await _ws(client, type=f"{DOMAIN}/area/clear", area_id=areas["Office"])
    assert msg["result"] == {"frame_id": FRAME_ID}
    doc = (await _ws(client, type=f"{DOMAIN}/get"))["result"]
    assert "Office" in [a["name"] for a in doc["unplaced_areas"]]

    msg = await _ws(client, type=f"{DOMAIN}/area/clear", area_id=areas["Office"])
    assert msg["error"]["code"] == "not_found"


async def test_override_falls_back_to_vacuum_room_when_cleared(
    hass: HomeAssistant, hass_ws_client, areas: dict[str, str], ready: Any
) -> None:
    client = await hass_ws_client(hass)
    msg = await _ws(client, type=f"{DOMAIN}/area/set", area_id=areas["Kitchen"], rect=GARAGE_RECT)
    assert msg["result"]["origin"] == "manual"
    await _ws(client, type=f"{DOMAIN}/area/clear", area_id=areas["Kitchen"])
    doc = (await _ws(client, type=f"{DOMAIN}/get"))["result"]
    kitchen = next(a for a in doc["frames"][0]["areas"] if a["name"] == "Kitchen")
    assert (kitchen["origin"], kitchen["geometry"]) == ("vacuum", "pixels")


@pytest.mark.parametrize(
    "extra,code",
    [
        ({"rect": {"x": 0, "y": 0, "width": 0, "height": 1}}, "invalid_format"),
        ({"polygons": [[[0, 0], [2, 2], [2, 0], [0, 2]]]}, "invalid_format"),
        ({"rect": GARAGE_RECT, "polygons": [[[0, 0], [1, 0], [1, 1]]]}, "invalid_format"),
        ({}, "invalid_format"),
        ({"rect": GARAGE_RECT, "frame_id": "nope"}, "not_found"),
        ({"rect": GARAGE_RECT, "area_id": "nope"}, "not_found"),
    ],
)
async def test_set_rejects_bad_requests(
    hass: HomeAssistant, hass_ws_client, areas: dict[str, str], ready: Any, extra: dict[str, Any], code: str
) -> None:
    client = await hass_ws_client(hass)
    msg = await _ws(client, type=f"{DOMAIN}/area/set", **{"area_id": areas["Garage"], **extra})
    assert not msg["success"]
    assert msg["error"]["code"] == code


async def test_writes_need_an_admin(
    hass: HomeAssistant, hass_ws_client, hass_read_only_access_token: str, areas: dict[str, str], ready: Any
) -> None:
    client = await hass_ws_client(hass, hass_read_only_access_token)
    msg = await _ws(client, type=f"{DOMAIN}/area/set", area_id=areas["Garage"], rect=GARAGE_RECT)
    assert msg["error"]["code"] == "unauthorized"
    msg = await _ws(client, type=f"{DOMAIN}/area/clear", area_id=areas["Garage"])
    assert msg["error"]["code"] == "unauthorized"
    # Reading is still fine.
    assert (await _ws(client, type=f"{DOMAIN}/get"))["success"]


async def test_floor_mismatch_and_frame_required(
    hass: HomeAssistant, hass_ws_client, areas: dict[str, str], ready: Any
) -> None:
    upstairs = fr.async_get(hass).async_create("Upstairs")
    attic = ar.async_get(hass).async_create("Attic", floor_id=upstairs.floor_id)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)

    # The vacuum frame has no floor, so any area may go in it...
    msg = await _ws(client, type=f"{DOMAIN}/area/set", frame_id=FRAME_ID, area_id=attic.id, rect=GARAGE_RECT)
    assert msg["success"], msg
    await _ws(client, type=f"{DOMAIN}/area/clear", area_id=attic.id)

    # ...but an area on one floor can't go in another floor's frame.
    ground = fr.async_get(hass).async_create("Ground")
    msg = await _ws(
        client, type=f"{DOMAIN}/area/set", frame_id=ground.floor_id, area_id=attic.id, rect=GARAGE_RECT
    )
    assert msg["error"]["code"] == "floor_mismatch"

    # Without frame_id, an area with a floor goes on its floor, even with no vacuum there.
    msg = await _ws(client, type=f"{DOMAIN}/area/set", area_id=attic.id, rect=GARAGE_RECT)
    assert msg["success"], msg
    doc = (await _ws(client, type=f"{DOMAIN}/get", frame_id=upstairs.floor_id))["result"]
    (frame,) = doc["frames"]
    assert frame["name"] == "Upstairs"
    assert [a["name"] for a in frame["areas"]] == ["Attic"]

    # Two frames now, so a floor-less area needs a frame_id.
    msg = await _ws(client, type=f"{DOMAIN}/area/set", area_id=areas["Garage"], rect=GARAGE_RECT)
    assert msg["error"]["code"] == "frame_required"


async def test_services(hass: HomeAssistant, areas: dict[str, str], ready: Any) -> None:
    manager = ready.runtime_data
    await hass.services.async_call(
        DOMAIN, "set_area", {"area_id": areas["Garage"], **GARAGE_RECT}, blocking=True
    )
    assert areas["Garage"] in manager.placements[FRAME_ID]

    await hass.services.async_call(
        DOMAIN,
        "set_area",
        {"area_id": areas["Office"], "polygons": [[[0, 0], [2, 0], [2, 2], [0, 2]]]},
        blocking=True,
    )
    assert manager.placements[FRAME_ID][areas["Office"]] == [[(0, 0), (2, 0), (2, 2), (0, 2)]]

    with pytest.raises(ServiceValidationError, match="either"):
        await hass.services.async_call(DOMAIN, "set_area", {"area_id": areas["Office"]}, blocking=True)
    with pytest.raises(ServiceValidationError, match="crosses itself"):
        await hass.services.async_call(
            DOMAIN,
            "set_area",
            {"area_id": areas["Office"], "polygons": [[[0, 0], [2, 2], [2, 0], [0, 2]]]},
            blocking=True,
        )

    await hass.services.async_call(DOMAIN, "clear_area", {"area_id": areas["Garage"]}, blocking=True)
    assert areas["Garage"] not in manager.placements[FRAME_ID]
    with pytest.raises(ServiceValidationError, match="no placement"):
        await hass.services.async_call(DOMAIN, "clear_area", {"area_id": areas["Garage"]}, blocking=True)


async def test_placements_are_stored_and_reloaded(
    hass: HomeAssistant, areas: dict[str, str], ready: Any, image_mock: AsyncMock, hass_storage: dict[str, Any]
) -> None:
    await hass.services.async_call(
        DOMAIN, "set_area", {"area_id": areas["Garage"], **GARAGE_RECT}, blocking=True
    )
    stored = hass_storage[DOMAIN]["data"]
    assert stored["placements"][FRAME_ID][areas["Garage"]] == [[[12, 0], [15, 0], [15, 5], [12, 5]]]

    assert await hass.config_entries.async_reload(ready.entry_id)
    await hass.async_block_till_done()
    fused = ready.runtime_data.fused
    garage = next(a for a in fused.frames[0].areas if a.area_id == areas["Garage"])
    assert garage.rect.as_dict() == GARAGE_RECT


async def test_deleting_an_area_drops_its_placement(
    hass: HomeAssistant, areas: dict[str, str], ready: Any
) -> None:
    manager = ready.runtime_data
    await hass.services.async_call(
        DOMAIN, "set_area", {"area_id": areas["Garage"], **GARAGE_RECT}, blocking=True
    )
    ar.async_get(hass).async_delete(areas["Garage"])
    await hass.async_block_till_done()
    assert manager.placements == {}


async def test_service_descriptions_load(hass: HomeAssistant, ready: Any) -> None:
    from homeassistant.helpers.service import async_get_all_descriptions
    from homeassistant.helpers.translation import async_get_translations

    descriptions = (await async_get_all_descriptions(hass))[DOMAIN]
    assert set(descriptions) == {
        "set_area", "clear_area", "get_map", "transform_point", "locate_point", "set_feature", "remove_feature"
    }
    names = await async_get_translations(hass, "en", "services", [DOMAIN])
    assert names[f"component.{DOMAIN}.services.set_area.name"] == "Set area shape"
    assert names[f"component.{DOMAIN}.services.clear_area.fields.area_id.name"] == "Area"
    assert set(descriptions["set_area"]["fields"]) == {
        "area_id", "frame_id", "x", "y", "width", "height", "polygons"
    }
