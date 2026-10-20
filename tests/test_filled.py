"""Filled room shapes: furniture gaps filled in (no Home Assistant)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.map_fusion import geometry as g
from custom_components.map_fusion import placements as pl
from custom_components.map_fusion.merge import SourceInput, build
from custom_components.map_fusion.queries import FILLED, document, locate
from custom_components.map_fusion.sources import dreame
from custom_components.map_fusion.sources import valetudo_map as vm

from . import synthetic
from .test_merge import AREAS, MAPPING, NOW, source

FIXTURES = Path(__file__).parent / "fixtures"


def box(x0: int, y0: int, x1: int, y1: int) -> set[g.Cell]:
    return {(x, y) for x in range(x0, x1) for y in range(y0, y1)}


def test_furniture_against_a_wall_is_filled() -> None:
    room = box(0, 0, 20, 20) - box(8, 0, 12, 6)  # a 4 × 6 cell wardrobe on the top wall
    assert g.fill_gaps(room, set(), 5) == box(0, 0, 20, 20)


def test_island_is_filled() -> None:
    room = box(0, 0, 20, 20) - box(6, 6, 14, 10)
    assert g.fill_gaps(room, set(), 8) == box(0, 0, 20, 20)


def test_small_corner_pocket_is_filled_but_an_l_shape_stays() -> None:
    corner = box(0, 0, 20, 20) - box(16, 16, 20, 20)  # 4 × 4 furniture in a corner
    assert g.fill_gaps(corner, set(), 5) == box(0, 0, 20, 20)
    l_shape = box(0, 0, 20, 20) - box(8, 8, 20, 20)  # 12 × 12 missing: a real L
    assert g.fill_gaps(l_shape, set(), 5) == l_shape


def test_gaps_wider_than_the_limit_stay() -> None:
    room = box(0, 0, 20, 20) - box(4, 0, 16, 3)  # 12 wide, 3 deep
    filled = g.fill_gaps(room, set(), 5)
    assert not (box(4, 0, 16, 3) <= filled)


def test_other_rooms_are_never_filled() -> None:
    room = box(0, 0, 20, 20) - box(8, 0, 12, 6)
    neighbour = box(8, 0, 12, 6)
    assert g.fill_gaps(room, neighbour, 5) == room


def test_fill_stays_in_the_bounding_box_and_zero_turns_it_off() -> None:
    room = box(0, 0, 10, 10) - box(3, 3, 6, 6)
    assert g.fill_gaps(room, set(), 0) == room
    filled = g.fill_gaps(room, set(), 5)
    xs = [c[0] for c in filled]
    ys = [c[1] for c in filled]
    assert (min(xs), max(xs), min(ys), max(ys)) == (0, 9, 0, 9)


def test_rooms_get_filled_shapes_that_dont_overlap() -> None:
    rooms = vm.rooms(vm.parse(synthetic.valetudo_doc()))
    for room in rooms.values():
        assert room.filled is not None and room.filled_m2 is not None
        assert room.filled_m2 >= room.area_m2
        assert g.bounds([p for r in room.filled for p in r]).as_dict() == pytest.approx(room.rect.as_dict())
    ids = sorted(rooms)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            assert g.overlap(rooms[a].filled, rooms[b].filled)[2] == pytest.approx(0, abs=0.01)


def test_fill_can_be_turned_off() -> None:
    rooms = vm.rooms(vm.parse(synthetic.valetudo_doc()), fill_max_m=0)
    assert all(r.filled is None for r in rooms.values())


def test_document_variants() -> None:
    fused = build(
        [SourceInput(source(), MAPPING)],
        AREAS,
        {},
        {},
        NOW,
        placements={"vacuum.d10:46": {"garage": [pl.rect_ring(30, 0, 2, 2)]}},
    ).fused
    traced = document(fused)
    filled = document(fused, variant=FILLED)
    assert traced["variant"] == "traced" and filled["variant"] == "filled"
    for t, f in zip(traced["frames"][0]["areas"], filled["frames"][0]["areas"], strict=True):
        assert f["polygons"] == t["filled_polygons"]
        assert f["rect"] == t["rect"]  # same box: sensors don't move
    garage = next(a for a in filled["frames"][0]["areas"] if a["area_id"] == "garage")
    assert garage["polygons"] == [[[30, 0], [32, 0], [32, 2], [30, 2]]]  # manual shapes are the same

    frame = fused.frames[0]
    kitchen = next(a for a in frame.areas if a.area_id == "kitchen")
    assert locate(frame, kitchen.label_point, variant=FILLED)["area_id"] == "kitchen"


@pytest.mark.skipif(
    not (FIXTURES / "camera.json").exists() or not (FIXTURES / "dreame_d10_plus_camera.json").exists(),
    reason="real map fixture is local only",
)
def test_real_d10_plus_filled_shapes() -> None:
    vmap = vm.parse(vm.extract_from_png((FIXTURES / "camera.json").read_bytes()))
    attr = dreame._attr_rooms(json.loads((FIXTURES / "dreame_d10_plus_camera.json").read_text())["attributes"]["rooms"])
    rooms, _ = dreame.pixel_rooms(vmap, attr)
    grew = 0.0
    for room in rooms.values():
        assert room.filled is not None and room.filled_m2 is not None
        assert room.filled_m2 >= room.area_m2
        grew += room.filled_m2 - room.area_m2
        box_ = g.bounds([p for r in room.filled for p in r])
        assert box_.width == pytest.approx(room.rect.width, abs=0.15)
        assert box_.height == pytest.approx(room.rect.height, abs=0.15)
        assert len(room.filled[0]) <= len(room.polygons[0])  # simpler outline
    assert grew > 3  # beds and wardrobes are filled in
    ids = sorted(rooms)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            assert g.overlap(rooms[a].filled, rooms[b].filled)[2] < 0.05, (a, b)
