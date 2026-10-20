"""Geometry helpers (no Home Assistant)."""
from __future__ import annotations

import pytest

from custom_components.map_fusion import geometry as g
from custom_components.map_fusion.model import Rect, Transform


def square(x0: int, y0: int, w: int, h: int) -> set[tuple[int, int]]:
    return {(x, y) for x in range(x0, x0 + w) for y in range(y0, y0 + h)}


def test_runs_and_pairs_decode() -> None:
    assert g.cells_from_runs([3, 1, 2, 0, 0, 1]) == {(3, 1), (4, 1), (0, 0)}
    assert g.cells_from_pairs([1, 2, 3, 4]) == {(1, 2), (3, 4)}
    with pytest.raises(ValueError):
        g.cells_from_runs([1, 2])


def test_square_traces_to_one_clockwise_ring() -> None:
    rings = g.trace_rings(square(2, 3, 4, 5))
    assert len(rings) == 1
    assert sorted(rings[0]) == [(2, 3), (2, 8), (6, 3), (6, 8)]
    assert g.signed_area(rings[0]) == 20


def test_l_shape_has_six_corners() -> None:
    cells = square(0, 0, 4, 2) | square(0, 2, 2, 2)
    (ring,) = g.trace_rings(cells)
    assert len(ring) == 6
    assert g.signed_area(ring) == len(cells)


def test_hole_is_an_anticlockwise_ring() -> None:
    cells = square(0, 0, 5, 5) - {(2, 2)}
    rings = g.trace_rings(cells)
    areas = sorted(g.signed_area(r) for r in rings)
    assert areas == [-1, 25]


def test_cells_touching_at_a_corner_stay_separate() -> None:
    rings = g.trace_rings({(0, 0), (1, 1)})
    assert len(rings) == 2
    assert all(g.signed_area(r) == 1 for r in rings)


def test_mask_to_polygons_drops_holes_and_small_pieces() -> None:
    cells = (square(0, 0, 10, 10) - square(4, 4, 2, 2)) | square(20, 20, 2, 2)
    polys = g.mask_to_polygons(cells, min_piece_cells=5, tolerance_cells=0.5)
    assert len(polys) == 1
    assert g.signed_area(polys[0]) == 100


def test_simplify_flattens_staircase() -> None:
    # A 1-cell staircase diagonal: 20 steps simplify to a triangle-ish shape.
    cells = {(x, y) for x in range(20) for y in range(20) if x >= y}
    (ring,) = g.trace_rings(cells)
    simple = g.simplify_ring(ring, 1.0)
    assert len(simple) < len(ring) / 4
    assert len(simple) >= 3


def test_close_fills_single_cell_gaps_only() -> None:
    cells = square(0, 0, 10, 10) - {(5, 5)}
    assert (5, 5) in g.close_mask(cells, 1)
    big_hole = square(0, 0, 20, 20) - square(5, 5, 6, 6)
    assert (8, 8) not in g.close_mask(big_hole, 1)
    assert g.close_mask(cells, 0) == cells


def test_point_in_ring_and_distance() -> None:
    ring = [(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (2.0, 2.0), (2.0, 4.0), (0.0, 4.0)]
    assert g.point_in_ring((1, 3), ring)
    assert not g.point_in_ring((3, 3), ring)
    assert g.distance_to_ring((3, 3), ring) == pytest.approx(1.0)


def test_label_point_is_inside_a_c_shape() -> None:
    cells = square(0, 0, 10, 2) | square(0, 2, 2, 6) | square(0, 8, 10, 2)
    x, y = g.label_point(cells)
    assert (int(x), int(y)) in cells


def test_transform_inverse_and_then() -> None:
    t = Transform(a=1000, d=-1000, tx=5, ty=-7)
    p = (1.25, -2.5)
    assert t.inverse().apply(t.apply(p)) == pytest.approx(p)
    shift = Transform(tx=1, ty=2)
    assert t.then(shift).apply(p) == pytest.approx(shift.apply(t.apply(p)))


def test_rect_helpers() -> None:
    a = Rect(0, 0, 2, 2)
    b = Rect(1, 1, 2, 2)
    assert a.intersection(b) == Rect(1, 1, 1, 1)
    assert a.intersection(Rect(5, 5, 1, 1)) is None
    assert Rect.union([a, b]) == Rect(0, 0, 3, 3)
