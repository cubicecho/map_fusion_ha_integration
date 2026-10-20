"""Checking and tidying user-placed shapes (no Home Assistant)."""
from __future__ import annotations

import pytest

from custom_components.map_fusion import placements as pl
from custom_components.map_fusion.geometry import point_in_ring, signed_area


def test_rect_is_a_clockwise_ring() -> None:
    ring = pl.rect_ring(1, 2, 3, 4)
    assert ring == [(1, 2), (4, 2), (4, 6), (1, 6)]
    assert signed_area(ring) == pytest.approx(12)


@pytest.mark.parametrize("w,h", [(0, 1), (1, 0), (-1, 2)])
def test_rect_needs_a_size(w: float, h: float) -> None:
    with pytest.raises(pl.InvalidPlacement, match="greater than 0"):
        pl.rect_ring(0, 0, w, h)


def test_anticlockwise_is_turned_and_closing_point_dropped() -> None:
    (ring,) = pl.normalise([[[0, 0], [0, 2], [2, 2], [2, 0], [0, 0]]])
    assert len(ring) == 4
    assert signed_area(ring) > 0


def test_largest_ring_comes_first() -> None:
    small = [[0, 0], [1, 0], [1, 1], [0, 1]]
    big = [[5, 5], [9, 5], [9, 9], [5, 9]]
    rings = pl.normalise([small, big])
    assert rings[0][0] == (5, 5)
    assert pl.area_m2(rings) == pytest.approx(17)
    assert pl.bounds(rings).as_dict() == {"x": 0, "y": 0, "width": 9, "height": 9}


@pytest.mark.parametrize(
    "polygons,message",
    [
        ([], "non-empty"),
        ("nope", "non-empty"),
        ([[[0, 0], [1, 1]]], "at least 3"),
        ([[[0, 0], [1, 0], [1, 0], [0, 0]]], "at least 3"),
        ([[[0, 0], [0.005, 0], [0, 0.005]]], "no area"),
        ([[[0, 0], [2, 2], [2, 0], [0, 2]]], "crosses itself"),  # bow tie
        ([[[0, 0], [4, 0], [4, 4], [0, 4], [0, 6], [0, 2]]], "crosses itself"),  # folds back
        ([[[0, 0], ["a", 0], [1, 1]]], "numbers"),
        ([[[0, 0], [1], [1, 1]]], r"\[x, y\]"),
        ([[[0, 0], [float("inf"), 0], [1, 1]]], "finite"),
    ],
)
def test_bad_shapes_are_rejected(polygons: object, message: str) -> None:
    with pytest.raises(pl.InvalidPlacement, match=message):
        pl.normalise(polygons)


def test_label_point_is_inside_a_u_shape() -> None:
    # The centroid of a U falls in the gap between its arms.
    (ring,) = pl.normalise([[[0, 0], [1, 0], [1, 3], [3, 3], [3, 0], [4, 0], [4, 4], [0, 4]]])
    point = pl.label_point([ring])
    assert point_in_ring(point, ring)


def test_label_point_of_a_square_is_its_centre() -> None:
    assert pl.label_point([pl.rect_ring(0, 0, 2, 4)]) == pytest.approx((1, 2))


def test_as_lists_round_trips() -> None:
    rings = [pl.rect_ring(0, 0, 1, 1)]
    assert pl.normalise(pl.as_lists(rings)) == rings
