// @vitest-environment jsdom
import { beforeAll, describe, expect, it, vi } from "vitest";

import { MapFusionPanel } from "../src/panel.js";
import type { FusedDoc, Hass, HassState } from "../src/types.js";

beforeAll(() => {
  if (!customElements.get("map-fusion-panel")) customElements.define("map-fusion-panel", MapFusionPanel);
});

const KINDS = {
  door: {
    name: "Door",
    icon: "mdi:door",
    geometry: "segment",
    max_areas: 2,
    entity_domains: { binary_sensor: ["door", "garage_door", "opening"], cover: ["door", "garage", "gate"] },
  },
  window: {
    name: "Window",
    icon: "mdi:window-closed-variant",
    geometry: "segment",
    max_areas: 2,
    entity_domains: { binary_sensor: ["opening", "window"], cover: ["blind", "window"] },
  },
};

/** Kitchen 0..4 × 0..3 and Office 4..8 × 0..3 share the wall x = 4. */
function doc(): FusedDoc {
  return {
    version: 1,
    feature_kinds: KINDS,
    frames: [
      {
        frame_id: "vacuum.d10_plus:46",
        floor_id: null,
        name: "Map 1",
        bounds: { x: 0, y: 0, width: 8, height: 3 },
        areas: [
          {
            area_id: "kitchen",
            name: "Kitchen",
            polygons: [[[0, 0], [4, 0], [4, 3], [0, 3]]],
            rect: { x: 0, y: 0, width: 4, height: 3 },
            label_point: [2, 1.5],
            origin: "vacuum",
            geometry: "pixels",
            sources: [],
          },
          {
            area_id: "office",
            name: "Office",
            polygons: [[[4, 0], [8, 0], [8, 3], [4, 3]]],
            rect: { x: 4, y: 0, width: 4, height: 3 },
            label_point: [6, 1.5],
            origin: "vacuum",
            geometry: "pixels",
            sources: [],
          },
        ],
        unmapped_rooms: [],
        features: [
          {
            feature_id: "d1",
            kind: "door",
            name: "Office door",
            points: [[4, 1], [4, 2]],
            length_m: 1,
            entity_id: "binary_sensor.office_door",
            areas: ["office", "kitchen"],
            areas_auto: true,
          },
        ],
      },
    ],
    unplaced_areas: [],
  };
}

function st(entity_id: string, state: string, device_class?: string, friendly_name?: string): HassState {
  return { entity_id, state, attributes: { device_class, friendly_name } };
}

function states(doorState = "off"): Record<string, HassState> {
  return {
    "binary_sensor.office_door": st("binary_sensor.office_door", doorState, "door", "Office door"),
    "binary_sensor.kitchen_window": st("binary_sensor.kitchen_window", "off", "window", "Kitchen window"),
    "binary_sensor.motion": st("binary_sensor.motion", "off", "motion", "Motion"),
    "cover.garage": st("cover.garage", "closed", "garage", "Garage door"),
    "light.kitchen": st("light.kitchen", "on", undefined, "Kitchen light"),
  };
}

function setup() {
  let push: (d: FusedDoc | null) => void = () => undefined;
  const subscribeMessage = vi.fn((cb: (d: FusedDoc | null) => void, _m: Record<string, unknown>) => {
    push = cb;
    return Promise.resolve(() => undefined);
  });
  const callWS = vi.fn((msg: Record<string, unknown>) =>
    Promise.resolve(
      msg.type === "map_fusion/feature/set"
        ? { ...doc().frames[0]!.features![0]!, feature_id: (msg.feature_id as string) || "new1" }
        : {},
    ),
  );
  const hass = { connection: { subscribeMessage }, callWS, states: states() } as unknown as Hass;
  const panel = document.createElement("map-fusion-panel") as MapFusionPanel;
  document.body.append(panel);
  panel.hass = hass;
  push(doc());
  const root = panel.shadowRoot!;
  // 10 × 5 m view (-1..9, -1..4) in a 400 × 200 px box: 40 px/m.
  const svg = root.querySelector("svg")!;
  svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 400, height: 200, right: 400, bottom: 200, x: 0, y: 0, toJSON: () => ({}) });
  return { panel, root, push, callWS, svg, hass };
}

function pointer(target: Element, type: string, clientX: number, clientY: number) {
  const e = new Event(type, { bubbles: true }) as Event & Record<string, unknown>;
  Object.assign(e, { clientX, clientY, pointerId: 1 });
  target.dispatchEvent(e);
}

/** Map metres → client px for the stubbed 40 px/m view starting at (-1, -1). */
const px = (x: number, y: number): [number, number] => [(x + 1) * 40, (y + 1) * 40];
const action = (root: ShadowRoot, name: string) => root.querySelector<HTMLButtonElement>(`button[data-action="${name}"]`)!;
const point = (root: ShadowRoot, key: string) => root.querySelector<HTMLInputElement>(`input[data-feature-point="${key}"]`)!;

describe("doors and windows in the panel", () => {
  it("draws them coloured by their sensor and lists them", () => {
    const { root } = setup();
    const door = root.querySelector(".feature.door")!;
    expect(door.getAttribute("class")).toContain("closed");
    expect(root.querySelector('[data-feature="d1"]')).not.toBeNull();
    const headings = Array.from(root.querySelectorAll("h3")).map((h) => h.textContent);
    expect(headings).toContain("Doors & Windows");
    expect(action(root, "add-door").textContent).toBe("Add door");
    expect(action(root, "add-window").textContent).toBe("Add window");
  });

  it("redraws when a linked door opens", () => {
    const { panel, root, hass } = setup();
    panel.hass = { ...hass, states: states("on") } as Hass;
    expect(root.querySelector(".feature.door")!.getAttribute("class")).toContain("open");
  });

  it("selects a door by clicking it, and shows its areas", () => {
    const { root } = setup();
    pointer(root.querySelector('[data-feature="d1"]')!, "pointerdown", 0, 0);
    expect(root.querySelector("h2")!.textContent).toBe("Office door");
    expect(point(root, "0:0").value).toBe("4");
    expect(root.textContent).toContain("Joins Kitchen and Office.");
    expect(action(root, "save-feature").disabled).toBe(true); // nothing changed yet
  });

  it("adds a window, snaps its end onto a wall, links an entity and saves", async () => {
    const { root, svg, callWS } = setup();
    action(root, "add-window").click();
    expect(root.querySelector("h2")!.textContent).toBe("New window");
    // Drag end 1 to just right of the Kitchen's top wall (x 2.03, y 0.08): snaps onto y = 0.
    const [sx, sy] = px(Number(point(root, "0:0").value), Number(point(root, "0:1").value));
    pointer(root.querySelector('[data-end="0"]')!, "pointerdown", sx, sy);
    pointer(svg, "pointermove", ...px(1, 0.08));
    pointer(svg, "pointerup", ...px(1, 0.08));
    expect(point(root, "0:1").value).toBe("0");
    expect(point(root, "0:0").value).toBe("1");
    // Type the other end.
    for (const [key, value] of [
      ["1:0", "2"],
      ["1:1", "0"],
    ]) {
      const input = point(root, key!);
      input.value = value!;
      input.dispatchEvent(new Event("input"));
    }
    expect(root.textContent).toContain("1 m long");
    expect(root.textContent).toContain("Joins Kitchen.");

    const entity = root.querySelector<HTMLSelectElement>('select[data-feature-field="entity"]')!;
    const groups = Array.from(entity.querySelectorAll("optgroup")).map((g) => [g.label, Array.from(g.children).map((o) => (o as HTMLOptionElement).value)]);
    // Window sensors and covers that fit come first; lights never show.
    expect(groups).toEqual([
      ["Suggested", ["binary_sensor.kitchen_window"]],
      ["Other", ["cover.garage", "binary_sensor.motion", "binary_sensor.office_door"]],
    ]);
    entity.value = "binary_sensor.kitchen_window";
    entity.dispatchEvent(new Event("change"));
    const name = root.querySelector<HTMLInputElement>('input[data-feature-field="name"]')!;
    name.value = "Kitchen window";
    name.dispatchEvent(new Event("input"));

    action(root, "save-feature").click();
    await Promise.resolve();
    expect(callWS).toHaveBeenCalledWith({
      type: "map_fusion/feature/set",
      frame_id: "vacuum.d10_plus:46",
      kind: "window",
      points: [
        [1, 0],
        [2, 0],
      ],
      name: "Kitchen window",
      entity_id: "binary_sensor.kitchen_window",
      areas: null,
    });
    // The reply came before the updated map: the editor stays on the new window.
    await Promise.resolve();
    expect(root.querySelector("h2")!.textContent).toBe("Office door"); // what the fake server returned
    expect(action(root, "delete-feature")).not.toBeNull();
  });

  it("moves an existing door and saves it by id; deletes it", async () => {
    const { root, svg, callWS } = setup();
    pointer(root.querySelector('[data-feature="d1"]')!, "pointerdown", 0, 0);
    // Drag the line 0.5 m down (wall snapping keeps it on x = 4).
    pointer(root.querySelector("[data-feature-body]")!, "pointerdown", ...px(4, 1.5));
    pointer(svg, "pointermove", ...px(4, 2));
    pointer(svg, "pointerup", ...px(4, 2));
    expect([point(root, "0:1").value, point(root, "1:1").value]).toEqual(["1.5", "2.5"]);
    action(root, "save-feature").click();
    await Promise.resolve();
    const sent = callWS.mock.calls[0]![0];
    expect(sent).toMatchObject({ type: "map_fusion/feature/set", feature_id: "d1", points: [[4, 1.5], [4, 2.5]] });
    expect(sent.frame_id).toBeUndefined();

    action(root, "delete-feature").click();
    await Promise.resolve();
    expect(callWS).toHaveBeenLastCalledWith({ type: "map_fusion/feature/remove", feature_id: "d1" });
  });

  it("lets you pick the areas by hand, up to the kind's limit", () => {
    const { root } = setup();
    pointer(root.querySelector('[data-feature="d1"]')!, "pointerdown", 0, 0);
    const auto = root.querySelector<HTMLInputElement>('input[data-feature-field="areas-auto"]')!;
    auto.checked = false;
    auto.dispatchEvent(new Event("change"));
    const boxes = Array.from(root.querySelectorAll<HTMLInputElement>("input[data-feature-area]"));
    // Starts from what the map says: both checked, so the limit (2) is reached.
    expect(boxes.map((b) => [b.getAttribute("data-feature-area"), b.checked])).toEqual([
      ["kitchen", true],
      ["office", true],
    ]);
    boxes[0]!.checked = false;
    boxes[0]!.dispatchEvent(new Event("change"));
    expect(root.textContent).toContain("Pick the areas it joins");
    expect(action(root, "save-feature").disabled).toBe(false);
  });

  it("switching to an area drops the door selection", () => {
    const { panel, root } = setup();
    pointer(root.querySelector('[data-feature="d1"]')!, "pointerdown", 0, 0);
    panel.select("kitchen");
    expect(root.querySelector("h2")!.textContent).toBe("Kitchen");
    expect(root.querySelector(".feature.editing")).toBeNull();
  });

  it("works with older Map Fusion versions that have no features", () => {
    const { root, push } = setup();
    const old = doc();
    delete old.feature_kinds;
    delete old.frames[0]!.features;
    push(old);
    expect(root.querySelector("[data-action='add-door']")).toBeNull();
    expect(root.querySelectorAll(".feature")).toHaveLength(0);
  });
});
