"""Lining up a second vacuum's map with the anchor (no Home Assistant)."""
from __future__ import annotations

import math

import pytest

from custom_components.map_fusion.align import Fit, NoFit, area_centres, fit, moved
from custom_components.map_fusion.merge import SourceInput, build
from custom_components.map_fusion.model import Transform
from custom_components.map_fusion.queries import locate, to_frame
from custom_components.map_fusion.sources import dreame

from .test_merge import AREAS, NOW, source

CENTRES = {"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (4.0, 3.0), "d": (1.0, 5.0)}


def rotation(deg: float, tx: float = 0, ty: float = 0) -> Transform:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return Transform(a=c, b=-s, c=s, d=c, tx=tx, ty=ty)


def apply(t: Transform, centres: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    return {k: t.apply(p) for k, p in centres.items()}


@pytest.mark.parametrize("names", [["a", "b"], ["a", "b", "c"], ["a", "b", "c", "d"]])
def test_fit_recovers_rotation_and_shift(names: list[str]) -> None:
    anchor = {k: CENTRES[k] for k in names}
    t = rotation(33, 2.5, -7)
    other = apply(t.inverse(), anchor)  # the other vacuum sees the house turned and moved
    result = fit(anchor, other)
    assert isinstance(result, Fit)
    assert result.residual_m == pytest.approx(0, abs=1e-9)
    assert result.shared == names
    assert not result.mirrored
    for k in names:
        assert result.transform.apply(other[k]) == pytest.approx(anchor[k])


def test_fit_needs_two_shared_areas() -> None:
    result = fit({"a": (0, 0)}, {"a": (1, 1), "z": (5, 5)})
    assert isinstance(result, NoFit)
    assert "1 shared" in result.reason


def test_fit_detects_a_mirrored_map() -> None:
    other = {k: (-x, y) for k, (x, y) in CENTRES.items()}
    result = fit(CENTRES, other)
    assert isinstance(result, Fit) and result.mirrored
    assert result.residual_m == pytest.approx(0, abs=1e-9)


def test_fit_rejects_shapes_that_dont_line_up() -> None:
    other = dict(CENTRES)
    other["d"] = (20.0, -10.0)
    result = fit(CENTRES, other)
    assert isinstance(result, NoFit)
    assert "don't line up" in result.reason


def test_noisy_fit_reports_residual() -> None:
    other = {k: (x + (0.1 if i % 2 else -0.1), y) for i, (k, (x, y)) in enumerate(CENTRES.items())}
    result = fit(CENTRES, other)
    assert isinstance(result, Fit)
    assert 0.05 < result.residual_m < 0.15


# Two vacuums in one frame ------------------------------------------------------

TURN = rotation(90, 30, 4)


def second_vacuum():
    """The same house seen by another vacuum, turned 90° and moved.

    Its own coordinates turn and move with it (unlike `moved`, which keeps
    the original native coordinates).
    """
    smap = moved(source("vacuum.b", "7"), TURN)
    smap.to_native = dreame.TO_NATIVE
    return smap


def test_second_vacuum_joins_the_frame() -> None:
    a = SourceInput(source("vacuum.a"), {"kitchen": ["1_1"], "office": ["1_2"]})
    # vacuum.b links the same two areas, plus room 1_3 as the garage.
    b = SourceInput(second_vacuum(), {"kitchen": ["1_1"], "office": ["1_2"], "garage": ["1_3"]})
    # vacuum.a anchored the frame before, so it stays the anchor.
    first = build([a], AREAS, {}, {}, NOW)
    result = build([a, b], AREAS, {}, first.origins, NOW)
    (frame,) = result.fused.frames
    assert frame.frame_id == "vacuum.a:46"
    roles = [(s["source_id"], s["role"]) for s in frame.sources]
    assert roles == [("vacuum.a", "anchor"), ("vacuum.b", "aligned")]
    aligned = frame.sources[1]
    assert aligned["residual_m"] == pytest.approx(0, abs=1e-6)
    assert aligned["shared_areas"] == ["kitchen", "office"]

    kitchen = next(x for x in frame.areas if x.area_id == "kitchen")
    assert [s["source_id"] for s in kitchen.sources] == ["vacuum.a", "vacuum.b"]
    assert kitchen.confidence == pytest.approx(1, abs=0.02)
    assert first.fused.frames[0].areas[0].rect == kitchen.rect  # adding vacuum.b moved nothing

    # Only vacuum.b knows the garage; it lands where vacuum.a has unlinked room 1_3.
    garage = next(x for x in frame.areas if x.area_id == "garage")
    assert [s["source_id"] for s in garage.sources] == ["vacuum.b"]
    (unlinked,) = [r for r in frame.unmapped_rooms if r["source_id"] == "vacuum.a"]
    assert garage.rect.as_dict() == pytest.approx(unlinked["rect"], abs=1e-6)


def test_aligned_transform_maps_native_points_to_the_same_spot() -> None:
    a = SourceInput(source("vacuum.a"), {"kitchen": ["1_1"], "office": ["1_2"]})
    b = SourceInput(second_vacuum(), {"kitchen": ["1_1"], "office": ["1_2"]})
    frame = build([a, b], AREAS, {}, {}, NOW).fused.frames[0]
    # A spot in vacuum.a's native mm, and the same spot in vacuum.b's native coordinates.
    spot_a = (1200.0, -900.0)
    spot_frame = to_frame(frame, "vacuum.a", spot_a)[1]
    spot_b = b.map.to_native.apply(TURN.apply(source("vacuum.a").to_native.inverse().apply(spot_a)))
    assert to_frame(frame, "vacuum.b", spot_b)[1] == pytest.approx(spot_frame)
    assert locate(frame, spot_frame)["area_id"] == locate(frame, to_frame(frame, "vacuum.b", spot_b)[1])["area_id"]


def test_shapes_from_different_vacuums_can_overlap() -> None:
    a = SourceInput(source("vacuum.a"), {"kitchen": ["1_1"], "office": ["1_2", "1_3"]})
    b = SourceInput(second_vacuum(), {"kitchen": ["1_1"], "office": ["1_2"], "garage": ["1_3"]})
    first = build([a], AREAS, {}, {}, NOW)
    frame = build([a, b], AREAS, {}, first.origins, NOW).fused.frames[0]
    # vacuum.a says 1_3 is part of the office; vacuum.b calls it the garage.
    assert {(o["a"], o["b"]) for o in frame.overlaps} == {("garage", "office")}


def test_maps_that_cant_be_lined_up_get_their_own_frame() -> None:
    a = SourceInput(source("vacuum.a"), {"kitchen": ["1_1"], "office": ["1_2"]})
    b = SourceInput(second_vacuum(), {"kitchen": ["1_1"]})
    frames = build([a, b], AREAS, {}, {}, NOW).fused.frames
    assert [f.frame_id for f in frames] == ["vacuum.a:46", "vacuum.b:7"]
    assert "1 shared area" in frames[1].sources[0]["warnings"][0]


def test_stored_anchor_stays_the_anchor() -> None:
    b = SourceInput(second_vacuum(), {"kitchen": ["1_1"], "office": ["1_2"]})
    first = build([b], AREAS, {}, {}, NOW)  # vacuum.b came first
    a2 = SourceInput(source("vacuum.a"), {"kitchen": ["1_1"], "office": ["1_2"]})
    second = build([a2, b], AREAS, {}, first.origins, NOW)
    (frame,) = second.fused.frames
    assert frame.frame_id == "vacuum.b:7"
    assert frame.sources[0]["source_id"] == "vacuum.b"
    # Nothing moved for vacuum.b's areas.
    office = lambda r: next(x for x in r.fused.frames[0].areas if x.area_id == "office")
    assert office(second).rect == office(first).rect


def test_area_centres_use_linked_rooms_only() -> None:
    smap = source()
    centres = area_centres(smap, {"kitchen": ["1_1"], "ghost": ["9_9"]})
    assert set(centres) == {"kitchen"}
