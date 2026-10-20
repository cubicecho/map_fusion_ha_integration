"""ValetudoMap parsing and the Dreame pixel/box handling (no Home Assistant)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.map_fusion import geometry as g
from custom_components.map_fusion.sources import dreame
from custom_components.map_fusion.sources import valetudo_map as vm

from . import synthetic

FIXTURES = Path(__file__).parent / "fixtures"
# Real D10 Plus data stays local (git-ignored). These tests skip without it.
REAL_MAP_PNG = FIXTURES / "camera.json"
REAL_ATTRS = FIXTURES / "dreame_d10_plus_camera.json"


@pytest.mark.parametrize("kind", [b"zTXt", b"tEXt", b"iTXt"])
def test_extracts_json_from_any_text_chunk(kind: bytes) -> None:
    doc = synthetic.valetudo_doc()
    assert vm.extract_from_png(synthetic.png_with(doc, kind=kind)) == doc


def test_png_without_map_data_is_rejected() -> None:
    with pytest.raises(vm.ValetudoMapError, match="Map data camera"):
        vm.extract_from_png(synthetic.png_with(None))
    with pytest.raises(vm.ValetudoMapError):
        vm.extract_from_png(b"not a png")


def test_parse_reads_v1_and_v2_pixels() -> None:
    doc = synthetic.valetudo_doc()
    layer = doc["layers"][0]
    cells = g.cells_from_runs(layer.pop("compressedPixels"))
    layer["pixels"] = [v for c in sorted(cells) for v in c]
    vmap = vm.parse(doc)
    assert set(vmap.segments) == {"1", "2", "3"}
    assert vmap.segments["1"].cells == synthetic.SEGMENTS[1][1]
    assert vmap.metres_per_cell == 0.05


def test_parse_rejects_other_documents() -> None:
    with pytest.raises(vm.ValetudoMapError):
        vm.parse({"__class": "Something"})


def test_rooms_shapes() -> None:
    rooms = vm.rooms(vm.parse(synthetic.valetudo_doc()))
    l_room, holey, specky = rooms["1"], rooms["2"], rooms["3"]

    assert len(l_room.polygons) == 1 and len(l_room.polygons[0]) == 6
    assert l_room.geometry == "pixels"
    # Hole dropped (v1), outer edge kept as a square.
    assert len(holey.polygons) == 1 and len(holey.polygons[0]) == 4
    # Far-away speck dropped, rect covers only the kept piece.
    assert len(specky.polygons) == 1
    assert specky.rect.width == pytest.approx(3.0)
    for room in rooms.values():
        assert any(g.point_in_ring(room.label_point, p) for p in room.polygons)


def test_rooms_never_share_cells_after_closing() -> None:
    vmap = vm.parse(synthetic.valetudo_doc())
    # Rooms are one cell apart; closing must not grow one into another.
    rooms = vm.rooms(vmap, close_cells=2)
    l_room, holey = rooms["1"], rooms["2"]
    assert l_room.rect.x + l_room.rect.width <= holey.rect.x + 1e-9


def test_dreame_pixel_rooms_fit_the_attribute_boxes() -> None:
    vmap = vm.parse(synthetic.valetudo_doc())
    attr = dreame._attr_rooms(synthetic.attr_rooms())
    rooms, residual = dreame.pixel_rooms(vmap, attr)
    assert residual == pytest.approx(0, abs=1e-3)
    for sid, room in rooms.items():
        expected = attr[sid]
        assert room.rect.x == pytest.approx(expected.x, abs=1e-3)
        assert room.rect.y == pytest.approx(expected.y, abs=1e-3)


def test_dreame_formula_fallback_is_close() -> None:
    vmap = vm.parse(synthetic.valetudo_doc())
    attr = dreame._attr_rooms(synthetic.attr_rooms())
    rooms, residual = dreame.pixel_rooms(vmap, {})
    assert residual is None
    for sid, room in rooms.items():
        assert room.rect.x == pytest.approx(attr[sid].x, abs=0.1)
        assert room.rect.y == pytest.approx(attr[sid].y, abs=0.1)


def test_dreame_bbox_rooms() -> None:
    attr = dreame._attr_rooms(synthetic.attr_rooms() | {"9": {"x0": 0, "visibility": "Visible"}})
    rooms = dreame.bbox_rooms(attr)
    assert set(rooms) == {"1", "2", "3"}
    assert all(r.geometry == "bbox" and len(r.polygons[0]) == 4 for r in rooms.values())


@pytest.mark.skipif(not REAL_MAP_PNG.exists() or not REAL_ATTRS.exists(), reason="real map fixture is local only")
def test_real_d10_plus_map() -> None:
    vmap = vm.parse(vm.extract_from_png(REAL_MAP_PNG.read_bytes()))
    attr = dreame._attr_rooms(json.loads(REAL_ATTRS.read_text())["attributes"]["rooms"])
    rooms, residual = dreame.pixel_rooms(vmap, attr)

    assert set(rooms) == set(attr)
    assert residual is not None and residual < 0.005
    for sid, room in rooms.items():
        assert room.geometry == "pixels"
        assert 3 <= len(room.polygons[0]) <= 120, sid
        assert room.rect.width == pytest.approx(attr[sid].width, abs=0.06)
        assert room.rect.height == pytest.approx(attr[sid].height, abs=0.06)
        assert any(g.point_in_ring(room.label_point, p) for p in room.polygons)
