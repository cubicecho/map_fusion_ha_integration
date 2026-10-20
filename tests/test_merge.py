"""Building the fused map from inputs (no Home Assistant)."""
from __future__ import annotations

import pytest

from custom_components.map_fusion import placements as pl
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
    smap.rooms["1_2"] = dreame._shifted(smap.rooms["1_2"], -0.5, 0)
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


# User placements -----------------------------------------------------------

GARAGE = [pl.rect_ring(20, 0, 3, 6)]


def test_placement_adds_an_area_to_the_vacuum_frame() -> None:
    result = build(
        [SourceInput(source(), MAPPING)], AREAS, {}, {}, NOW, placements={"vacuum.d10:46": {"garage": GARAGE}}
    )
    frame = result.fused.frames[0]
    garage = next(a for a in frame.areas if a.area_id == "garage")
    assert (garage.origin, garage.geometry, garage.sources) == ("manual", "manual", [])
    assert garage.rect.as_dict() == {"x": 20, "y": 0, "width": 3, "height": 6}
    assert garage.area_m2 == pytest.approx(18)
    assert result.fused.unplaced_areas == []
    assert frame.bounds is not None and frame.bounds.x + frame.bounds.width == pytest.approx(23)


def test_placement_replaces_the_vacuum_shape() -> None:
    kitchen = [pl.rect_ring(0, 0, 1, 1)]
    result = build(
        [SourceInput(source(), MAPPING)], AREAS, {}, {}, NOW, placements={"vacuum.d10:46": {"kitchen": kitchen}}
    )
    frame = result.fused.frames[0]
    (area,) = [a for a in frame.areas if a.area_id == "kitchen"]
    assert area.origin == "manual"
    assert area.polygons == kitchen
    # The room is still linked, so it isn't listed as unmapped.
    assert frame.unmapped_rooms == []


def test_manual_and_vacuum_boxes_can_overlap() -> None:
    over = [pl.rect_ring(0, 0, 50, 50)]
    result = build(
        [SourceInput(source(), MAPPING)], AREAS, {}, {}, NOW, placements={"vacuum.d10:46": {"garage": over}}
    )
    pairs = {(o["a"], o["b"]) for o in result.fused.frames[0].overlaps}
    assert pairs == {("garage", "kitchen"), ("garage", "office")}


def test_floor_with_only_placements_gets_a_frame() -> None:
    areas = {**AREAS, "attic": AreaInfo("attic", "Attic", "upstairs")}
    result = build(
        [SourceInput(source(), MAPPING)],
        areas,
        {"upstairs": "Upstairs"},
        {},
        NOW,
        placements={"upstairs": {"attic": GARAGE}},
    )
    ids = [f.frame_id for f in result.fused.frames]
    assert ids == ["vacuum.d10:46", "upstairs"]
    upstairs = result.fused.frames[1]
    assert (upstairs.floor_id, upstairs.name, upstairs.sources) == ("upstairs", "Upstairs", [])
    assert "upstairs" not in result.origins  # placements-only frames have a fixed (0, 0)


def test_placements_for_a_missing_vacuum_are_kept_but_hidden() -> None:
    stored = {"vacuum.gone:1": {"garage": GARAGE}}
    result = build([], AREAS, {}, {}, NOW, placements=stored)
    assert result.fused.frames == []
    assert result.placements == stored
    assert "garage" in {a["area_id"] for a in result.fused.unplaced_areas}


def test_placements_of_deleted_areas_are_skipped() -> None:
    result = build(
        [SourceInput(source(), MAPPING)], AREAS, {}, {}, NOW, placements={"vacuum.d10:46": {"gone": GARAGE}}
    )
    assert "gone" not in {a.area_id for a in result.fused.frames[0].areas}


def test_frame_moves_to_floor_with_its_origin_and_placements() -> None:
    first = build(
        [SourceInput(source(), MAPPING)], AREAS, {}, {}, NOW, placements={"vacuum.d10:46": {"garage": GARAGE}}
    )
    on_floor = {k: AreaInfo(a.area_id, a.name, "ground") for k, a in AREAS.items()}
    second = build(
        [SourceInput(source(), MAPPING)],
        on_floor,
        {"ground": "Ground"},
        first.origins,
        NOW,
        placements=first.placements,
    )
    (frame,) = second.fused.frames
    assert frame.frame_id == "ground"
    assert second.origins == {"ground": first.origins["vacuum.d10:46"]}
    assert second.placements == {"ground": {"garage": GARAGE}}
    assert [a.rect for a in frame.areas] == [a.rect for a in first.fused.frames[0].areas]


def test_floor_choice_pins_a_map() -> None:
    floors = {"ground": "Ground", "upstairs": "Upstairs"}
    on_ground = {k: AreaInfo(a.area_id, a.name, "ground") for k, a in AREAS.items()}
    src = [SourceInput(source(), MAPPING)]
    pinned = build(src, AREAS, floors, {}, NOW, floor_choices={"vacuum.d10:46": "upstairs"})
    assert pinned.fused.frames[0].frame_id == "upstairs"
    none = build(src, on_ground, floors, {}, NOW, floor_choices={"vacuum.d10:46": None})
    assert none.fused.frames[0].frame_id == "vacuum.d10:46"
    assert none.fused.frames[0].floor_id is None
    # A chosen floor that was deleted falls back to the vote.
    deleted = build(src, on_ground, floors, {}, NOW, floor_choices={"vacuum.d10:46": "attic"})
    assert deleted.fused.frames[0].frame_id == "ground"
