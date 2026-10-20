import { describe, expect, it } from "vitest";

import {
  clientToMap,
  defaultSpot,
  dragRect,
  handlePoint,
  intersectionArea,
  isRectangle,
  snap,
  viewBounds,
} from "../src/geometry.js";

const R = { x: 1, y: 2, width: 3, height: 4 };

describe("dragRect", () => {
  it("moves the whole rectangle, snapped", () => {
    expect(dragRect(R, "move", 0.52, -0.26, 0.05)).toEqual({ x: 1.5, y: 1.75, width: 3, height: 4 });
  });

  it("resizes from a corner, keeping the opposite corner", () => {
    expect(dragRect(R, "se", 1, 0.5, 0.05)).toEqual({ x: 1, y: 2, width: 4, height: 4.5 });
    expect(dragRect(R, "nw", 0.5, 1, 0.05)).toEqual({ x: 1.5, y: 3, width: 2.5, height: 3 });
  });

  it("resizes one edge", () => {
    expect(dragRect(R, "e", -1, 9, 0.05)).toEqual({ x: 1, y: 2, width: 2, height: 4 });
    expect(dragRect(R, "n", 9, -1, 0.05)).toEqual({ x: 1, y: 1, width: 3, height: 5 });
  });

  it("never flips or shrinks below the minimum", () => {
    const r = dragRect(R, "e", -10, 0, 0.05);
    expect(r.x).toBe(1);
    expect(r.width).toBeCloseTo(0.1);
    const l = dragRect(R, "w", 10, 0, 0.05);
    expect(l.x + l.width).toBeCloseTo(4);
    expect(l.width).toBeCloseTo(0.1);
  });
});

describe("helpers", () => {
  it("snaps and hides float noise", () => {
    expect(snap(1.2345, 0.05)).toBe(1.25);
    expect(snap(0.1 + 0.2, 0.01)).toBe(0.3);
    expect(snap(1.2345, 0)).toBe(1.235);
  });

  it("places handles on corners and edge midpoints", () => {
    expect(handlePoint(R, "nw")).toEqual([1, 2]);
    expect(handlePoint(R, "se")).toEqual([4, 6]);
    expect(handlePoint(R, "n")).toEqual([2.5, 2]);
    expect(handlePoint(R, "w")).toEqual([1, 4]);
  });

  it("puts a new area just right of the map", () => {
    expect(defaultSpot({ x: 0, y: 0.2, width: 11.45, height: 6 })).toEqual({ x: 12, y: 0.2, width: 3, height: 3 });
    expect(defaultSpot(null)).toEqual({ x: 0, y: 0, width: 3, height: 3 });
  });

  it("frames the view on whole metres with a margin", () => {
    expect(viewBounds([R])).toEqual({ x: 0, y: 1, width: 5, height: 6 });
    expect(viewBounds([])).toEqual({ x: -1, y: -1, width: 10, height: 8 });
  });

  it("measures overlaps", () => {
    expect(intersectionArea(R, { x: 3, y: 5, width: 2, height: 2 })).toBeCloseTo(1);
    expect(intersectionArea(R, { x: 10, y: 10, width: 1, height: 1 })).toBe(0);
  });

  it("knows a rectangle when it sees one", () => {
    expect(isRectangle([[[1, 2], [4, 2], [4, 6], [1, 6]]], R)).toBe(true);
    expect(isRectangle([[[1, 2], [4, 2], [4, 6], [2, 6], [1, 5]]], R)).toBe(false);
  });

  it("maps pointer positions with letterboxing", () => {
    // 10 × 5 m view in a 400 × 400 px box: 40 px/m, 100 px bars top and bottom.
    const view = { x: -1, y: -1, width: 10, height: 5 };
    const box = { left: 0, top: 0, width: 400, height: 400 };
    expect(clientToMap(0, 100, box, view)).toEqual([-1, -1]);
    expect(clientToMap(200, 200, box, view)).toEqual([4, 1.5]);
  });
});
