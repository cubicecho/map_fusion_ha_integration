import { describe, expect, it } from "vitest";

import {
  cleanRing,
  clientToMap,
  defaultSpot,
  dragRect,
  dragVertex,
  editableOutline,
  handlePoint,
  insertVertex,
  intersectionArea,
  isRectangle,
  largestRing,
  lockToNeighbour,
  rectRing,
  removeVertex,
  ringArea,
  ringBounds,
  ringCentroid,
  ringProblem,
  ringsOverlap,
  selfIntersects,
  simplifyRing,
  snap,
  translateRing,
  viewBounds,
  type Pair,
} from "../src/geometry.js";

const R = { x: 1, y: 2, width: 3, height: 4 };
const SQUARE: Pair[] = [
  [0, 0],
  [2, 0],
  [2, 2],
  [0, 2],
];
// An L: 4 × 4 with the top-right 2 × 2 cut out.
const L: Pair[] = [
  [0, 0],
  [2, 0],
  [2, 2],
  [4, 2],
  [4, 4],
  [0, 4],
];

describe("polygon editing", () => {
  it("turns a rectangle into a ring and back", () => {
    expect(rectRing(R)).toEqual([
      [1, 2],
      [4, 2],
      [4, 6],
      [1, 6],
    ]);
    expect(ringBounds(rectRing(R))).toEqual(R);
    expect(ringBounds(L)).toEqual({ x: 0, y: 0, width: 4, height: 4 });
  });

  it("measures area and middle", () => {
    expect(ringArea(SQUARE)).toBe(4);
    expect(ringArea(SQUARE.slice().reverse())).toBe(4);
    expect(ringArea(L)).toBe(12);
    expect(ringCentroid(SQUARE)).toEqual([1, 1]);
    expect(largestRing([SQUARE, L])).toBe(L);
  });

  it("inserts a corner mid-edge and removes one, never below 3", () => {
    const five = insertVertex(SQUARE, 1);
    expect(five).toEqual([
      [0, 0],
      [2, 0],
      [2, 1],
      [2, 2],
      [0, 2],
    ]);
    // The closing edge (last → first) works too.
    expect(insertVertex(SQUARE, 3)[4]).toEqual([0, 1]);
    expect(removeVertex(five, 2)).toEqual(SQUARE);
    const tri = removeVertex(SQUARE, 0);
    expect(tri).toHaveLength(3);
    expect(removeVertex(tri, 0)).toEqual(tri);
  });

  it("drags a corner, snapped, and moves the whole ring on the grid", () => {
    expect(dragVertex(SQUARE, 2, 0.52, 0.26, 0.05)[2]).toEqual([2.5, 2.25]);
    expect(dragVertex(SQUARE, 2, 0.52, 0.26, 0.05)[0]).toEqual([0, 0]);
    // Top-left of the bounds snaps, the shape keeps its size.
    const offGrid: Pair[] = [
      [0.02, 0],
      [2.02, 0],
      [1, 1],
    ];
    expect(translateRing(offGrid, 0.5, 0.26, 0.05)).toEqual([
      [0.5, 0.25],
      [2.5, 0.25],
      [1.48, 1.25],
    ]);
  });

  it("locks a corner to its nearest neighbour axis with Shift", () => {
    // Corner near (2, 2): the neighbour above is at x = 2, so x snaps to 2.
    expect(lockToNeighbour([2.1, 2.5], [2, 0], [0, 2])).toEqual([2, 2.5]);
    expect(lockToNeighbour([1, 2.05], [2, 0], [0, 2])).toEqual([1, 2]);
    expect(dragVertex(SQUARE, 2, 0.12, 0.5, 0.01, true)[2]).toEqual([2, 2.5]);
  });

  it("finds crossings like the server does", () => {
    expect(selfIntersects(SQUARE)).toBe(false);
    expect(selfIntersects(L)).toBe(false);
    const bowtie: Pair[] = [
      [0, 0],
      [2, 2],
      [2, 0],
      [0, 2],
    ];
    expect(selfIntersects(bowtie)).toBe(true);
    // A corner touching another edge counts.
    expect(
      selfIntersects([
        [0, 0],
        [4, 0],
        [4, 4],
        [2, 0],
        [0, 4],
      ]),
    ).toBe(true);
    // A spike: an edge folding back over its neighbour.
    expect(
      selfIntersects([
        [0, 0],
        [3, 0],
        [1, 0],
        [1, 2],
      ]),
    ).toBe(true);
    expect(ringProblem(bowtie)).toContain("crosses itself");
    expect(ringProblem(SQUARE)).toBeNull();
    expect(
      ringProblem([
        [0, 0],
        [0, 0],
        [1, 1],
      ]),
    ).toContain("3 different corners");
    expect(
      ringProblem([
        [0, 0],
        [1, 1],
        [2, 2.0001],
      ]),
    ).not.toBeNull();
  });

  it("tidies rings like the server", () => {
    expect(
      cleanRing([
        [0.00049, 0],
        [0, 0],
        [1, 0],
        [1, 1],
        [0, 0],
      ]),
    ).toEqual([
      [0, 0],
      [1, 0],
      [1, 1],
    ]);
  });

  it("simplifies a traced outline", () => {
    // A 4 × 3 room traced with 5 cm wobble every 10 cm along the top.
    const top: Pair[] = [];
    for (let x = 0; x < 4; x += 0.1) top.push([Math.round(x * 10) / 10, (Math.round(x * 10) % 2) * 0.05]);
    const traced: Pair[] = top.concat([
      [4, 0],
      [4, 3],
      [0, 3],
    ]);
    const simple = simplifyRing(traced, 0.1);
    expect(simple.length).toBeLessThanOrEqual(5);
    expect(ringArea(simple)).toBeCloseTo(12, 0);
    const outline = editableOutline([traced], { x: 0, y: 0, width: 4, height: 3 });
    expect(outline.length).toBeLessThanOrEqual(5);
    expect(ringProblem(outline)).toBeNull();
    // Nothing usable: the rectangle.
    expect(editableOutline([], { x: 1, y: 1, width: 2, height: 2 })).toEqual(rectRing({ x: 1, y: 1, width: 2, height: 2 }));
  });

  it("tells overlaps from shared walls", () => {
    const right: Pair[] = SQUARE.map((p): Pair => [p[0] + 2, p[1]]);
    expect(ringsOverlap(SQUARE, right)).toBe(false); // shared wall at x = 2
    expect(ringsOverlap(SQUARE, SQUARE)).toBe(true); // same shape
    expect(ringsOverlap(SQUARE, SQUARE.map((p): Pair => [p[0] + 1, p[1] + 1]))).toBe(true);
    // In the L's cut-out corner: boxes overlap, shapes don't.
    const notch: Pair[] = [
      [2.5, 0.5],
      [3.5, 0.5],
      [3.5, 1.5],
      [2.5, 1.5],
    ];
    expect(ringsOverlap(L, notch)).toBe(false);
    // A small square fully inside the L.
    expect(
      ringsOverlap(L, [
        [0.5, 2.5],
        [1, 2.5],
        [1, 3],
        [0.5, 3],
      ]),
    ).toBe(true);
  });
});

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
