"""Point lookups, transforms and SVG drawing (no Home Assistant)."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from custom_components.map_fusion import placements as pl
from custom_components.map_fusion.merge import SourceInput, build
from custom_components.map_fusion.model import FusedMap
from custom_components.map_fusion.queries import (
    QueryError,
    document,
    find_frame,
    locate,
    to_frame,
    to_source,
)
from custom_components.map_fusion.render import attributes, render

from .test_merge import AREAS, MAPPING, NOW, source


@pytest.fixture
def fused() -> FusedMap:
    return build(
        [SourceInput(source(), MAPPING)],
        AREAS,
        {},
        {},
        NOW,
        placements={"vacuum.d10:46": {"garage": [pl.rect_ring(30, 0, 3, 3)]}},
    ).fused


def test_locate_inside_near_and_nowhere(fused: FusedMap) -> None:
    frame = fused.frames[0]
    kitchen = next(a for a in frame.areas if a.area_id == "kitchen")
    assert locate(frame, kitchen.label_point) == {
        "area_id": "kitchen", "name": "Kitchen", "inside": True, "distance_m": 0.0
    }
    near = locate(frame, (33.05, 1.5))  # 5 cm right of the garage
    assert near["area_id"] == "garage" and near["inside"] is False
    assert near["distance_m"] == pytest.approx(0.05)
    assert locate(frame, (100, 100))["area_id"] is None


def test_locate_prefers_the_smallest_overlapping_area(fused: FusedMap) -> None:
    frame = build(
        [],
        AREAS,
        {"ground": "Ground"},
        {},
        NOW,
        placements={"ground": {"garage": [pl.rect_ring(0, 0, 10, 10)], "office": [pl.rect_ring(1, 1, 2, 2)]}},
    ).fused.frames[0]
    assert locate(frame, (2, 2))["area_id"] == "office"
    assert locate(frame, (8, 8))["area_id"] == "garage"


def test_transform_round_trip_and_axes(fused: FusedMap) -> None:
    frame = fused.frames[0]
    sid, origin = to_source(frame, None, (0, 0))
    assert sid == "vacuum.d10"
    _, right = to_source(frame, None, (1, 0))
    _, down = to_source(frame, None, (0, 1))
    # Dreame: mm, y up.
    assert right[0] - origin[0] == pytest.approx(1000)
    assert down[1] - origin[1] == pytest.approx(-1000)
    _, back = to_frame(frame, "vacuum.d10", right)
    assert back == pytest.approx((1, 0))


def test_transform_errors(fused: FusedMap) -> None:
    frame = fused.frames[0]
    with pytest.raises(QueryError, match="not in frame") as err:
        to_source(frame, "vacuum.other", (0, 0))
    assert err.value.code == "not_found"
    manual_only = build([], AREAS, {"ground": "Ground"}, {}, NOW, placements={"ground": {"garage": [pl.rect_ring(0, 0, 1, 1)]}})
    with pytest.raises(QueryError, match="no vacuum map"):
        to_source(manual_only.fused.frames[0], None, (0, 0))


def test_find_frame(fused: FusedMap) -> None:
    assert find_frame(fused, None).frame_id == "vacuum.d10:46"
    assert find_frame(fused, None, "vacuum.d10").frame_id == "vacuum.d10:46"
    with pytest.raises(QueryError) as err:
        find_frame(fused, "nope")
    assert err.value.code == "not_found"
    # One shared area isn't enough to line the maps up, so each gets a frame.
    one = {"kitchen": ["1_1"]}
    two = build(
        [SourceInput(source("vacuum.a"), one), SourceInput(source("vacuum.b"), one)], AREAS, {}, {}, NOW
    ).fused
    with pytest.raises(QueryError) as err:
        find_frame(two, None)
    assert err.value.code == "frame_required"
    assert find_frame(two, None, "vacuum.b").frame_id == "vacuum.b:46"
    with pytest.raises(QueryError, match="no map yet"):
        find_frame(None, None)


def test_document_filters_frames(fused: FusedMap) -> None:
    assert document(None) is None
    assert len(document(fused)["frames"]) == 1
    assert document(fused, "nope")["frames"] == []


def test_render_svg(fused: FusedMap) -> None:
    frame = fused.frames[0]
    rendered = render(frame)
    root = ET.fromstring(rendered.svg)
    ns = "{http://www.w3.org/2000/svg}"
    assert int(root.get("width")) == rendered.width
    labels = [t.text for t in root.iter(f"{ns}text")]
    assert labels == ["Garage", "Kitchen", "Office"]
    classes = [p.get("class") for p in root.iter(f"{ns}path")]
    assert classes.count("room manual") == 1  # the garage
    assert "unlinked" not in classes  # every synthetic room is linked

    # map_to_image puts the frame's top-left at the padding.
    x, y = rendered.to_image.apply((frame.bounds.x, frame.bounds.y))
    assert (x, y) == pytest.approx((15, 15))


def test_calibration_points_match_the_transform(fused: FusedMap) -> None:
    frame = fused.frames[0]
    rendered = render(frame)
    points = rendered.calibration_points
    assert points is not None and len(points) == 3
    for p in points:
        _, native = to_source(frame, None, rendered.to_image.inverse().apply((p["map"]["x"], p["map"]["y"])))
        assert (p["vacuum"]["x"], p["vacuum"]["y"]) == pytest.approx(native, abs=0.1)
    attrs = attributes(frame, rendered, 1)
    assert attrs["frame_id"] == "vacuum.d10:46" and attrs["area_count"] == 3
    assert "polygons" not in str(attrs)


def test_manual_only_frames_render_without_calibration() -> None:
    frame = build(
        [], AREAS, {"ground": "Ground"}, {}, NOW, placements={"ground": {"garage": [pl.rect_ring(0, 0, 2, 2)]}}
    ).fused.frames[0]
    rendered = render(frame)
    assert rendered.calibration_points is None
    assert b"Garage" in rendered.svg
