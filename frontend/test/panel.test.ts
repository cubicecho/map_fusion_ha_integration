// @vitest-environment jsdom
import { beforeAll, describe, expect, it, vi } from "vitest";

import { MapFusionPanel } from "../src/panel.js";
import type { FusedDoc, Hass } from "../src/types.js";

beforeAll(() => {
  if (!customElements.get("map-fusion-panel")) customElements.define("map-fusion-panel", MapFusionPanel);
});

function doc(): FusedDoc {
  return {
    version: 1,
    frames: [
      {
        frame_id: "vacuum.d10_plus:46",
        floor_id: null,
        name: "Map 1",
        bounds: { x: 0, y: 0, width: 10, height: 5 },
        areas: [
          {
            area_id: "kitchen",
            name: "Kitchen",
            polygons: [[[0, 0], [4, 0], [4, 3], [0, 3]]],
            rect: { x: 0, y: 0, width: 4, height: 3 },
            label_point: [2, 1.5],
            origin: "vacuum",
            geometry: "pixels",
            sources: [{ source_id: "vacuum.d10_plus", segment_id: "1_1" }],
          },
          {
            area_id: "porch",
            name: "Porch",
            polygons: [[[6, 0], [8, 0], [8, 2], [6, 2]]],
            rect: { x: 6, y: 0, width: 2, height: 2 },
            label_point: [7, 1],
            origin: "manual",
            geometry: "manual",
            sources: [],
          },
        ],
        unmapped_rooms: [],
      },
    ],
    unplaced_areas: [{ area_id: "garage", name: "Garage", floor_id: null }],
  };
}

function setup() {
  let push: (d: FusedDoc | null) => void = () => undefined;
  const subscribeMessage = vi.fn((cb: (d: FusedDoc | null) => void, _message: Record<string, unknown>) => {
    push = cb;
    return Promise.resolve(() => undefined);
  });
  const callWS = vi.fn(() => Promise.resolve({}));
  const hass = { connection: { subscribeMessage }, callWS } as unknown as Hass;
  const panel = document.createElement("map-fusion-panel") as MapFusionPanel;
  document.body.append(panel);
  panel.hass = hass;
  push(doc());
  const root = panel.shadowRoot!;
  // jsdom has no layout: give the map a 400 × 200 px box (40 px/m for the 10 × 5 m view).
  const svg = root.querySelector("svg")!;
  svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 400, height: 200, right: 400, bottom: 200, x: 0, y: 0, toJSON: () => ({}) });
  return { panel, root, push, callWS, subscribeMessage, svg };
}

const field = (root: ShadowRoot, name: string) => root.querySelector<HTMLInputElement>(`input[data-field="${name}"]`)!;
const draft = (root: ShadowRoot) => root.querySelector(".draft")!;
const action = (root: ShadowRoot, name: string) => root.querySelector<HTMLButtonElement>(`button[data-action="${name}"]`)!;

function pointer(target: Element, type: string, clientX: number, clientY: number, shiftKey = false) {
  const e = new Event(type, { bubbles: true }) as Event & Record<string, unknown>;
  Object.assign(e, { clientX, clientY, pointerId: 1, shiftKey });
  target.dispatchEvent(e);
}

/** Screen position of map point (x, y) in the 400 × 200 px test box, for the current view. */
function at(svg: Element, x: number, y: number): [number, number] {
  const [vx, vy, w, h] = svg.getAttribute("viewBox")!.split(" ").map(Number);
  const scale = Math.min(400 / w!, 200 / h!);
  const ox = (400 - w! * scale) / 2;
  const oy = (200 - h! * scale) / 2;
  return [ox + (x - vx!) * scale, oy + (y - vy!) * scale];
}

/** Press on `target`, move to map point (x, y), release. */
function dragTo(svg: Element, target: Element, from: [number, number], to: [number, number], shiftKey = false) {
  const a = at(svg, from[0], from[1]);
  const b = at(svg, to[0], to[1]);
  pointer(target, "pointerdown", a[0], a[1]);
  pointer(svg, "pointermove", b[0], b[1], shiftKey);
  pointer(svg, "pointerup", b[0], b[1]);
}

const vertices = (root: ShadowRoot) => root.querySelectorAll("circle.vertex");
const vertex = (root: ShadowRoot, i: number) => root.querySelector(`circle[data-vertex="${i}"]`)!;
const vx = (root: ShadowRoot, i: number) => root.querySelector<HTMLInputElement>(`input[data-vx="${i}"]`)!;
const vy = (root: ShadowRoot, i: number) => root.querySelector<HTMLInputElement>(`input[data-vy="${i}"]`)!;
const mode = (root: ShadowRoot, m: string) => root.querySelector<HTMLButtonElement>(`button[data-mode="${m}"]`)!;
const ring = (root: ShadowRoot) =>
  Array.from(vertices(root)).map((c) => [Number(c.getAttribute("cx")), Number(c.getAttribute("cy"))]);

/** The test document plus a hand-placed L-shaped hall below the kitchen. */
function withHall(rings?: Array<Array<[number, number]>>): FusedDoc {
  const d = doc();
  const hall: Array<[number, number]> = [
    [0, 3.5],
    [2, 3.5],
    [2, 4],
    [4, 4],
    [4, 5],
    [0, 5],
  ];
  d.frames[0]!.areas.push({
    area_id: "hall",
    name: "Hall",
    polygons: rings || [hall],
    rect: { x: 0, y: 3.5, width: 4, height: 1.5 },
    label_point: [1, 4.5],
    origin: "manual",
    geometry: "manual",
    sources: [],
  });
  return d;
}

function type(input: HTMLInputElement, value: string) {
  input.value = value;
  input.dispatchEvent(new Event("input"));
}

describe("MapFusionPanel", () => {
  it("draws the map and lists areas by kind", () => {
    const { root, subscribeMessage } = setup();
    expect(subscribeMessage.mock.calls[0]![1]).toEqual({ type: "map_fusion/subscribe" });
    expect(root.querySelectorAll("path.room")).toHaveLength(2);
    const headings = Array.from(root.querySelectorAll("h3")).map((h) => h.textContent);
    expect(headings).toEqual(["Not on the map yet", "Placed by hand", "From the vacuum map"]);
    expect(root.querySelector("svg")!.getAttribute("viewBox")).toBe("-1 -1 10 5");
  });

  it("places an unplaced area beside the map and saves it", async () => {
    const { panel, root, callWS } = setup();
    panel.select("garage");
    action(root, "place").click();
    expect(draft(root).getAttribute("x")).toBe("10.5");
    expect(field(root, "x").value).toBe("10.5");
    action(root, "save").click();
    await Promise.resolve();
    expect(callWS).toHaveBeenCalledWith({
      type: "map_fusion/area/set",
      frame_id: "vacuum.d10_plus:46",
      area_id: "garage",
      rect: { x: 10.5, y: 0, width: 3, height: 3 },
    });
  });

  it("moves the rectangle live while typing", () => {
    const { panel, root } = setup();
    panel.select("porch");
    const x = field(root, "x");
    x.value = "6.4";
    x.dispatchEvent(new Event("input"));
    expect(draft(root).getAttribute("x")).toBe("6.4");
    expect(action(root, "save").disabled).toBe(false);
    // The field being typed in isn't overwritten.
    expect(field(root, "x")).toBe(x);
  });

  it("drags the rectangle and updates the fields", () => {
    const { panel, root, svg } = setup();
    panel.select("porch");
    // 40 px/m: drag the body 1 m right and 0.5 m down.
    pointer(draft(root), "pointerdown", 300, 60);
    pointer(svg, "pointermove", 340, 80);
    expect(field(root, "x").value).toBe("7");
    expect(field(root, "y").value).toBe("0.5");
    pointer(svg, "pointerup", 340, 80);

    // The view grew to fit the moved rectangle, so work out the new scale.
    const [, , w, h] = svg.getAttribute("viewBox")!.split(" ").map(Number);
    const pxPerM = Math.min(400 / w!, 200 / h!);
    const se = root.querySelector(".handle-se")!;
    pointer(se, "pointerdown", 0, 0);
    pointer(svg, "pointermove", 1 * pxPerM, 0.5 * pxPerM);
    expect(field(root, "width").value).toBe("3");
    expect(field(root, "height").value).toBe("2.5");
  });

  it("warns about overlaps as you drag", () => {
    const { panel, root, svg } = setup();
    panel.select("porch");
    pointer(draft(root), "pointerdown", 0, 0);
    pointer(svg, "pointermove", -120, 0); // 3 m left: into the kitchen
    expect(root.querySelector(".warning:not([hidden])")!.textContent).toBe("Overlaps Kitchen.");
  });

  it("removes a hand placement", async () => {
    const { panel, root, callWS } = setup();
    panel.select("porch");
    action(root, "remove").click();
    await Promise.resolve();
    expect(callWS).toHaveBeenCalledWith({ type: "map_fusion/area/clear", frame_id: "vacuum.d10_plus:46", area_id: "porch" });
  });

  it("offers to replace a vacuum shape, and selects rooms by clicking them", () => {
    const { root } = setup();
    const kitchen = root.querySelector('path[data-area="kitchen"]')!;
    pointer(kitchen, "pointerdown", 0, 0);
    expect(root.querySelector("h2")!.textContent).toBe("Kitchen");
    action(root, "replace").click();
    expect(field(root, "width").value).toBe("4");
    expect(root.textContent).toContain("Saving replaces the vacuum's shape");
  });

  it("arrow keys nudge by the snap step", () => {
    const { panel, root, svg } = setup();
    panel.select("porch");
    svg.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    expect(field(root, "x").value).toBe("6.05");
    svg.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", shiftKey: true }));
    expect(field(root, "height").value).toBe("2.05");
  });

  it("switches to filled shapes by resubscribing", () => {
    const { root, subscribeMessage } = setup();
    const select = root.querySelector<HTMLSelectElement>("select.variant")!;
    select.value = "filled";
    select.dispatchEvent(new Event("change"));
    expect(subscribeMessage.mock.calls[1]![1]).toEqual({ type: "map_fusion/subscribe", variant: "filled" });
  });

  it("explains a missing integration", async () => {
    const hass = {
      connection: { subscribeMessage: () => Promise.reject({ code: "unknown_command" }) },
      callWS: vi.fn(),
    } as unknown as Hass;
    const panel = document.createElement("map-fusion-panel") as MapFusionPanel;
    document.body.append(panel);
    panel.hass = hass;
    await new Promise((r) => setTimeout(r, 0));
    expect(panel.shadowRoot!.textContent).toContain("Map Fusion isn't loaded");
  });
});

describe("MapFusionPanel polygons", () => {
  it("opens a hand-placed polygon in polygon mode, with corner fields and area", () => {
    const { panel, root, push } = setup();
    push(withHall());
    panel.select("hall");
    expect(mode(root, "polygon").getAttribute("aria-pressed")).toBe("true");
    expect(vertices(root)).toHaveLength(6);
    expect(vx(root, 3).value).toBe("4");
    expect(vy(root, 3).value).toBe("4");
    expect(root.querySelector('[data-readout="area"]')!.textContent).toBe("6 corners · 5.00 m²");
    expect(root.querySelector(".draft-label")!.textContent).toBe("5.00 m²");
    expect(root.querySelector('input[data-field="x"]')).toBeNull();
    // Nothing changed yet.
    expect(action(root, "save").disabled).toBe(true);
  });

  it("switches a rectangle to a polygon, drags a corner and saves polygons", async () => {
    const { panel, root, svg, callWS } = setup();
    panel.select("porch");
    expect(mode(root, "rect").getAttribute("aria-pressed")).toBe("true");
    mode(root, "polygon").click();
    expect(ring(root)).toEqual([
      [6, 0],
      [8, 0],
      [8, 2],
      [6, 2],
    ]);
    // Same shape so far: nothing to save.
    expect(action(root, "save").disabled).toBe(true);
    dragTo(svg, vertex(root, 2), [8, 2], [9, 2.5]);
    expect(vx(root, 2).value).toBe("9");
    expect(vy(root, 2).value).toBe("2.5");
    expect(mode(root, "polygon").getAttribute("aria-pressed")).toBe("true");
    action(root, "save").click();
    await Promise.resolve();
    expect(callWS).toHaveBeenCalledWith({
      type: "map_fusion/area/set",
      frame_id: "vacuum.d10_plus:46",
      area_id: "porch",
      polygons: [
        [
          [6, 0],
          [8, 0],
          [9, 2.5],
          [6, 2],
        ],
      ],
    });
  });

  it("drags the whole polygon by its body", () => {
    const { panel, root, svg, push } = setup();
    push(withHall());
    panel.select("hall");
    dragTo(svg, draft(root), [1, 4.5], [2, 4]);
    expect(vx(root, 0).value).toBe("1");
    expect(vy(root, 0).value).toBe("3");
    expect(vx(root, 3).value).toBe("5");
  });

  it("adds a corner from an edge midpoint and removes corners", () => {
    const { panel, root, svg } = setup();
    panel.select("porch");
    mode(root, "polygon").click();
    // Edge 1 runs (8, 0) → (8, 2): its midpoint is (8, 1). Drag it out to (9, 1).
    const mid = root.querySelector('circle[data-mid="1"]')!;
    dragTo(svg, mid, [8, 1], [9, 1]);
    expect(vertices(root)).toHaveLength(5);
    expect(ring(root)[2]).toEqual([9, 1]);
    expect(vx(root, 2).value).toBe("9");
    expect(root.querySelector('[data-readout="area"]')!.textContent).toBe("5 corners · 5.00 m²");

    // Double press on a corner removes it.
    const [px, py] = at(svg, 9, 1);
    pointer(vertex(root, 2), "pointerdown", px, py);
    pointer(svg, "pointerup", px, py);
    pointer(vertex(root, 2), "pointerdown", px, py);
    expect(vertices(root)).toHaveLength(4);

    // Select a corner, then Delete.
    const [qx, qy] = at(svg, 6, 2);
    pointer(vertex(root, 3), "pointerdown", qx, qy);
    pointer(svg, "pointerup", qx, qy);
    expect(vertex(root, 3).getAttribute("class")).toContain("selected");
    svg.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete" }));
    expect(vertices(root)).toHaveLength(3);

    // Never below three: the remove buttons are off and Delete does nothing.
    expect(root.querySelector<HTMLButtonElement>('button[data-remove-vertex="0"]')!.disabled).toBe(true);
    pointer(vertex(root, 0), "pointerdown", 0, 0);
    pointer(svg, "pointerup", 0, 0);
    svg.dispatchEvent(new KeyboardEvent("keydown", { key: "Backspace" }));
    expect(vertices(root)).toHaveLength(3);
    expect(root.textContent).toContain("at least 3 corners");
  });

  it("removes a corner with its button", () => {
    const { panel, root, push } = setup();
    push(withHall());
    panel.select("hall");
    root.querySelector<HTMLButtonElement>('button[data-remove-vertex="2"]')!.click();
    expect(vertices(root)).toHaveLength(5);
    expect(vx(root, 2).value).toBe("4");
    expect(action(root, "save").disabled).toBe(false);
  });

  it("moves corners live while typing, and warns (no Save) when edges cross", () => {
    const { panel, root, push } = setup();
    push(withHall());
    panel.select("hall");
    const x = vx(root, 1);
    type(x, "2.5");
    expect(ring(root)[1]).toEqual([2.5, 3.5]);
    expect(vx(root, 1)).toBe(x); // not rebuilt under the cursor
    expect(action(root, "save").disabled).toBe(false);
    // Pull corner 1 past the far wall: its edges cross the others.
    type(x, "5");
    type(vy(root, 1), "4.5");
    const warning = root.querySelector(".warning:not([hidden])")!;
    expect(warning.textContent).toContain("crosses itself");
    expect(action(root, "save").disabled).toBe(true);
    expect(root.querySelector("path.draft")!.getAttribute("class")).toContain("invalid");
    type(vx(root, 1), "2");
    type(vy(root, 1), "3.5");
    expect(root.querySelector(".warning:not([hidden])")).toBeNull();
  });

  it("warns about polygon overlaps, but not a shared wall", () => {
    const { panel, root, svg, push } = setup();
    push(withHall());
    panel.select("hall");
    // Corner 0 up to the kitchen's bottom wall (y = 3): touching, not overlapping.
    dragTo(svg, vertex(root, 0), [0, 3.5], [0, 3]);
    expect(root.querySelector(".warning:not([hidden])")).toBeNull();
    type(vy(root, 0), "2.5");
    expect(root.querySelector(".warning:not([hidden])")!.textContent).toBe("Overlaps Kitchen.");
  });

  it("Shift while dragging lines a corner up with its neighbour", () => {
    const { panel, root, svg } = setup();
    panel.select("porch");
    mode(root, "polygon").click();
    // Corner 2 (8, 2) dragged to (8.3, 2.9) with Shift: x locks to its neighbour above (8).
    dragTo(svg, vertex(root, 2), [8, 2], [8.3, 2.9], true);
    expect(ring(root)[2]).toEqual([8, 2.9]);
  });

  it("arrow keys move the polygon, or the selected corner", () => {
    const { panel, root, svg, push } = setup();
    push(withHall());
    panel.select("hall");
    svg.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    expect(vx(root, 0).value).toBe("0.05");
    expect(vx(root, 3).value).toBe("4.05");
    pointer(vertex(root, 3), "pointerdown", 0, 0);
    pointer(svg, "pointerup", 0, 0);
    svg.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown" }));
    expect(vy(root, 3).value).toBe("4.05");
    expect(vy(root, 2).value).toBe("4");
  });

  it("polygon → rectangle uses the bounding box and warns; switching straight back restores it", async () => {
    const { panel, root, push, callWS } = setup();
    push(withHall());
    panel.select("hall");
    mode(root, "rect").click();
    expect(field(root, "x").value).toBe("0");
    expect(field(root, "y").value).toBe("3.5");
    expect(field(root, "width").value).toBe("4");
    expect(field(root, "height").value).toBe("1.5");
    expect(root.textContent).toContain("detail is lost");
    expect(action(root, "save").disabled).toBe(false);
    mode(root, "polygon").click();
    expect(vertices(root)).toHaveLength(6);
    mode(root, "rect").click();
    action(root, "save").click();
    await Promise.resolve();
    expect(callWS).toHaveBeenCalledWith({
      type: "map_fusion/area/set",
      frame_id: "vacuum.d10_plus:46",
      area_id: "hall",
      rect: { x: 0, y: 3.5, width: 4, height: 1.5 },
    });
  });

  it("replaces a vacuum room with a polygon from its outline", async () => {
    const { panel, root, callWS } = setup();
    panel.select("kitchen");
    expect(action(root, "replace")).not.toBeNull();
    action(root, "replace-polygon").click();
    expect(ring(root)).toEqual([
      [0, 0],
      [4, 0],
      [4, 3],
      [0, 3],
    ]);
    expect(root.textContent).toContain("Saving replaces the vacuum's shape");
    action(root, "save").click();
    await Promise.resolve();
    expect((callWS.mock.calls[0] as unknown[])[0]).toMatchObject({ area_id: "kitchen", polygons: [[[0, 0], [4, 0], [4, 3], [0, 3]]] });
  });

  it("places an unplaced area as a rectangle, then switches it to a polygon", () => {
    const { panel, root } = setup();
    panel.select("garage");
    action(root, "place").click();
    mode(root, "polygon").click();
    expect(ring(root)).toEqual([
      [10.5, 0],
      [13.5, 0],
      [13.5, 3],
      [10.5, 3],
    ]);
    expect(action(root, "save").disabled).toBe(false);
  });

  it("edits the largest of several rings and says the rest go", () => {
    const { panel, root, push } = setup();
    const small: Array<[number, number]> = [
      [5, 4],
      [5.5, 4],
      [5.5, 4.5],
    ];
    const big: Array<[number, number]> = [
      [0, 3.5],
      [3, 3.5],
      [3, 5],
      [1, 5],
    ];
    push(withHall([small, big]));
    panel.select("hall");
    expect(vertices(root)).toHaveLength(4);
    expect(root.textContent).toContain("2 separate parts");
  });
});
