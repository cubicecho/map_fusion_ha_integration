"""Doors, windows and other map features (no Home Assistant)."""
from __future__ import annotations

import pytest

from custom_components.map_fusion import features as ft
from custom_components.map_fusion.merge import AreaInfo, SourceInput, build
from custom_components.map_fusion.render import render

from .test_merge import AREAS, NOW, source

LINKS = {"kitchen": ["1_1"], "office": ["1_2"], "garage": ["1_3"]}
DOOR = {"kind": "door", "points": [[2.025, 0.2], [2.025, 0.8]], "name": "Kitchen door", "entity_id": "binary_sensor.kitchen_door"}
WINDOW = {"kind": "window", "points": [[4.05, 0.5], [4.05, 1.5]], "entity_id": "cover.office_blind"}


def built(features: dict, areas: dict = AREAS, **kw):
    return build([SourceInput(source(), LINKS)], areas, {}, {}, NOW, features=features, **kw)


def test_normalise_keeps_what_is_needed() -> None:
    f = ft.normalise({**DOOR, "name": "  Kitchen door "})
    assert f == {
        "kind": "door",
        "points": [[2.025, 0.2], [2.025, 0.8]],
        "name": "Kitchen door",
        "entity_id": "binary_sensor.kitchen_door",
        "areas": None,
    }
    assert ft.normalise({"kind": "window", "points": [[0, 0], [1, 0]], "areas": ["a", "a"]})["areas"] == ["a"]


@pytest.mark.parametrize(
    "data,message",
    [
        ({"kind": "chimney", "points": [[0, 0], [1, 0]]}, "kind must be one of: door, window"),
        ({"kind": "door", "points": [[0, 0]]}, "two"),
        ({"kind": "door", "points": [[0, 0], [0.01, 0]]}, "at least 5 cm"),
        ({"kind": "door", "points": [[0, 0], [30, 0]]}, "at most 20 m"),
        ({"kind": "door", "points": [[0, 0], ["x", 0]]}, "numbers"),
        ({"kind": "door", "points": [[0, 0], [1, 0]], "entity_id": "light.hall"}, "binary_sensor, cover"),
        ({"kind": "window", "points": [[0, 0], [1, 0]], "areas": ["a", "b", "c"]}, "at most 2"),
    ],
)
def test_bad_features_are_rejected(data: dict, message: str) -> None:
    with pytest.raises(ft.InvalidFeature, match=message):
        ft.normalise(data)


def test_kinds_table_describes_itself() -> None:
    doc = ft.kinds_doc()
    assert set(doc) == {"door", "window"}
    assert doc["door"]["geometry"] == "segment"
    assert doc["door"]["entity_domains"]["binary_sensor"] == ["door", "garage_door", "opening"]
    assert doc["window"]["icon"] == "mdi:window-closed-variant"


@pytest.mark.parametrize(
    "entity_id,state,expected",
    [
        ("binary_sensor.d", "on", "open"),
        ("binary_sensor.d", "off", "closed"),
        ("binary_sensor.d", "unavailable", "unknown"),
        ("cover.g", "opening", "open"),
        ("cover.g", "closed", "closed"),
        (None, "on", "unknown"),
    ],
)
def test_open_state(entity_id: str | None, state: str, expected: str) -> None:
    assert ft.open_state(entity_id, state) == expected


def test_door_joins_the_rooms_either_side_and_window_its_room() -> None:
    result = built({"vacuum.d10:46": {"d1": ft.normalise(DOOR), "w1": ft.normalise(WINDOW)}})
    frame = result.fused.frames[0]
    door, window = frame.features
    assert (door.feature_id, door.kind, door.name) == ("d1", "door", "Kitchen door")
    assert sorted(door.areas) == ["kitchen", "office"]
    assert door.areas_auto is True
    assert window.areas == ["office"]  # the other side is outside
    assert door.as_dict()["length_m"] == pytest.approx(0.6)
    doc = result.fused.as_dict()
    assert doc["feature_kinds"]["door"]["name"] == "Door"
    assert doc["frames"][0]["features"][0]["entity_id"] == "binary_sensor.kitchen_door"


def test_explicit_areas_win_and_deleted_ones_drop_out() -> None:
    door = ft.normalise({**DOOR, "areas": ["kitchen", "gone"]})
    (feature,) = built({"vacuum.d10:46": {"d1": door}}).fused.frames[0].features
    assert feature.areas == ["kitchen"]
    assert feature.areas_auto is False


def test_features_move_with_their_frame() -> None:
    first = built({"vacuum.d10:46": {"d1": ft.normalise(DOOR)}})
    on_floor = {k: AreaInfo(a.area_id, a.name, "ground") for k, a in AREAS.items()}
    second = build(
        [SourceInput(source(), LINKS)],
        on_floor,
        {"ground": "Ground"},
        first.origins,
        NOW,
        features=first.features,
    )
    assert second.features == {"ground": {"d1": ft.normalise(DOOR)}}
    assert second.fused.frames[0].features[0].points == first.fused.frames[0].features[0].points


def test_a_floor_with_only_features_gets_a_frame() -> None:
    result = build([], AREAS, {"attic": "Attic"}, {}, NOW, features={"attic": {"w": ft.normalise(WINDOW)}})
    (frame,) = result.fused.frames
    assert frame.frame_id == "attic" and frame.areas == []
    assert frame.features[0].areas == []
    assert frame.bounds is not None


def test_unknown_kinds_are_kept_but_not_shown() -> None:
    stored = {"vacuum.d10:46": {"x": {"kind": "teleporter", "points": [[0, 0], [1, 0]]}}}
    result = built(stored)
    assert result.fused.frames[0].features == []
    assert result.features == stored


def test_render_draws_doors_and_windows_by_state() -> None:
    frame = built({"vacuum.d10:46": {"d1": ft.normalise(DOOR), "w1": ft.normalise(WINDOW)}}).fused.frames[0]
    closed = render(frame, states={"d1": "closed", "w1": "closed"}).svg.decode()
    assert 'class="feature feature-door closed"' in closed and "#6d4c41" in closed
    assert 'class="feature feature-window closed"' in closed
    opened = render(frame, states={"d1": "open"}).svg.decode()
    assert 'feature-door open" ' in opened and "#e53935" in opened
    assert 'stroke-dasharray="4 3"' in opened  # the window's state is unknown
