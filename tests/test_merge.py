"""Building the fused map from inputs (no Home Assistant)."""
from __future__ import annotations

import pytest

from custom_components.map_fusion.merge import AreaInfo, FrameOrigin, SourceInput, build
from custom_components.map_fusion.model import SourceMap
from custom_components.map_fusion.sources import dreame
from custom_components.map_fusion.sources import valetudo_map as vm

from . import synthetic

NOW = "2026-10-20T00:00:00+00:00"


def source(entity_id: str = "vacuum.d10", map_id: str = "46", *, bbox: bool = False) -> SourceMap:
    attr = dreame._attr_rooms(synthetic.attr_rooms())
    if bbox:
        rooms = dreame.bbox_rooms(attr)
    else:
        rooms, _ = dreame.pixel_rooms(vm.parse(synthetic.valetudo_doc()), attr)
    for sid, room in list(rooms.items()):
        room.segment_id = f"1_{sid}"
        rooms[f"1_{sid}"] = rooms.pop(sid)
    return SourceMap(entity_id, "dreame", map_id, "Map 1", rooms, dreame.TO_NATIVE)


AREAS = {
    "kitchen": AreaInfo("kitchen", "Kitchen", None),
    "office": AreaInfo("office", "Office", None),
    "garage": AreaInfo("garage", "Garage", None),
}
MAPPING = {"kitchen": ["1_1"], "office": ["1_2", "1_3"]}


def test_floorless_map_becomes_its_own_frame() -> None:
    result = build([SourceInput(source(), MAPPING)], AREAS, {}, {}, NOW)
    (frame,) = result.fused.frames
    assert frame.frame_id == "vacuum.d10:46"
    assert frame.floor_id is None
    assert frame.name == "Map 1"
    assert [a.area_id for a in frame.areas] == ["kitchen", "office"]
    assert frame.bounds is not None
    assert frame.bounds.x == pytest.approx(0) and frame.bounds.y == pytest.approx(0)
    assert frame.unmapped_rooms == []
    assert frame.overlaps == []
    assert result.fused.unplaced_areas == [{"area_id": "garage", "name": "Garage", "floor_id": None}]


def test_area_linked_to_two_rooms_has_both() -> None:
    result = build([SourceInput(source(), MAPPING)], AREAS, {}, {}, NOW)
    office = result.fused.frames[0].areas[1]
    assert len(office.polygons) == 2
    assert [s["segment_id"] for s in office.sources] == ["1_2", "1_3"]  # biggest first
    assert office.geometry == "pixels"


def test_unlinked_rooms_are_listed() -> None:
    result = build([SourceInput(source(), {"kitchen": ["1_1"]})], AREAS, {}, {}, NOW)
    frame = result.fused.frames[0]
    assert [r["segment_id"] for r in frame.unmapped_rooms] == ["1_2", "1_3"]


def test_floor_majority_names_the_frame() -> None:
    areas = {
        "kitchen": AreaInfo("kitchen", "Kitchen", "ground"),
        "office": AreaInfo("office", "Office", "ground"),
    }
    result = build([SourceInput(source(), MAPPING)], areas, {"ground": "Ground floor"}, {}, NOW)
    frame = result.fused.frames[0]
    assert (frame.frame_id, frame.floor_id, frame.name) == ("ground", "ground", "Ground floor")


def test_second_map_on_same_floor_gets_its_own_frame() -> None:
    areas = {"kitchen": AreaInfo("kitchen", "Kitchen", "ground")}
    inputs = [
        SourceInput(source("vacuum.a"), {"kitchen": ["1_1"]}),
        SourceInput(source("vacuum.b"), {"kitchen": ["1_1"]}),
    ]
    frames = build(inputs, areas, {}, {}, NOW).fused.frames
    assert [f.frame_id for f in frames] == ["ground", "vacuum.b:46"]


def test_stored_origin_wins_so_frames_dont_shift() -> None:
    first = build([SourceInput(source(), MAPPING)], AREAS, {}, {}, NOW)
    origins = first.origins
    # The vacuum loses a room; the frame must not move.
    smaller = source()
    del smaller.rooms["1_1"]
    second = build([SourceInput(smaller, MAPPING)], AREAS, {}, origins, NOW)
    office_before = first.fused.frames[0].areas[1].rect
    office_after = second.fused.frames[0].areas[0].rect
    assert office_after == office_before
    assert second.origins == origins


def test_origin_resets_when_the_anchor_changes() -> None:
    origins = {"vacuum.d10:46": FrameOrigin(anchor="vacuum.other:1", origin=(99.0, 99.0))}
    result = build([SourceInput(source(), MAPPING)], AREAS, {}, origins, NOW)
    assert result.origins["vacuum.d10:46"].anchor == "vacuum.d10:46"


def test_bbox_areas_report_overlaps_and_transform() -> None:
    smap = source(bbox=True)
    # Make two boxes overlap.
    smap.rooms["1_2"].rect = smap.rooms["1_2"].rect.shifted(-0.5, 0)
    result = build([SourceInput(smap, MAPPING)], AREAS, {}, {}, NOW)
    frame = result.fused.frames[0]
    assert frame.areas[0].geometry == "bbox"
    assert frame.overlaps and frame.overlaps[0]["a"] == "kitchen"
    # transform maps vacuum mm to frame metres
    a, b, c, d, _tx, _ty = frame.sources[0]["transform"]
    assert (a, b, c, d) == (0.001, 0.0, 0.0, -0.001)


def test_document_is_json_ready() -> None:
    doc = build([SourceInput(source(), MAPPING)], AREAS, {}, {}, NOW).fused.as_dict()
    assert doc["version"] == 1
    area = doc["frames"][0]["areas"][0]
    assert set(area) >= {"area_id", "name", "polygons", "rect", "label_point", "geometry", "sources"}
    assert isinstance(area["polygons"][0][0], list)
