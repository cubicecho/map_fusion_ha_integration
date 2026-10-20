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

function pointer(target: Element, type: string, clientX: number, clientY: number) {
  const e = new Event(type, { bubbles: true }) as Event & Record<string, unknown>;
  Object.assign(e, { clientX, clientY, pointerId: 1 });
  target.dispatchEvent(e);
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
