/**
 * <map-fusion-panel>: Map Fusion's sidebar page (admins only).
 *
 * Shows a fused map with a metre grid. Pick an area, then edit its shape
 * as a rectangle (drag it, or a corner/edge handle) or as a polygon (drag
 * corners, add one from an edge's midpoint, remove one), or type numbers;
 * map and fields stay in step. Save calls map_fusion/area/set (`rect` or
 * `polygons`), Remove calls map_fusion/area/clear. The map updates from
 * map_fusion/subscribe.
 *
 * Structure is rebuilt when the document, frame, variant, selection or
 * shape mode changes. Drags only touch the draft and the number fields
 * (and the corner list when a corner is added or removed).
 */
import {
  HANDLES,
  MIN_POINTS,
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
  pointInRing,
  rectRing,
  removeVertex,
  ringArea,
  ringBounds,
  ringCentroid,
  ringProblem,
  ringsOverlap,
  ringsPath,
  setVertex,
  snapRect,
  translateRing,
  union,
  viewBounds,
  type Handle,
  type Pair,
  type Rect,
} from "./geometry.js";
import { STYLES } from "./styles.js";
import type { FusedArea, FusedDoc, FusedFrame, Hass } from "./types.js";

const SVG = "http://www.w3.org/2000/svg";
const SNAP_STEPS = [0.01, 0.05, 0.1, 0.25, 0.5];
const FIELDS: Array<keyof Rect> = ["x", "y", "width", "height"];
const FIELD_LABELS: Record<keyof Rect, string> = { x: "x", y: "y", width: "Width", height: "Height" };

type Kind = "vacuum" | "manual" | "unplaced";

interface Entry {
  area_id: string;
  name: string;
  kind: Kind;
  area?: FusedArea;
}

/** What's being edited: a rectangle, or one polygon ring. */
type Draft = { kind: "rect"; rect: Rect } | { kind: "polygon"; ring: Pair[] };
type Mode = Draft["kind"];

interface Drag {
  /** A rect handle, "move", or "vertex" (polygon corner `vertex`). */
  handle: Handle | "vertex";
  vertex: number;
  start: Draft;
  from: Pair;
  pointerId: number;
  moved: boolean;
}

/** Two presses on the same corner within this many ms remove it. */
const DOUBLE_PRESS_MS = 400;

function copyDraft(d: Draft): Draft {
  return d.kind === "rect" ? { kind: "rect", rect: { ...d.rect } } : { kind: "polygon", ring: d.ring.slice() };
}

function draftBounds(d: Draft): Rect {
  return d.kind === "rect" ? d.rect : ringBounds(d.ring);
}

function draftRing(d: Draft): Pair[] {
  return d.kind === "rect" ? rectRing(d.rect) : d.ring;
}

function sameRect(a: Rect, b: Rect): boolean {
  const near = (p: number, q: number) => Math.abs(p - q) < 0.0005;
  return near(a.x, b.x) && near(a.y, b.y) && near(a.width, b.width) && near(a.height, b.height);
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function svgEl(tag: string, attrs: Record<string, string | number> = {}): SVGElement {
  const e = document.createElementNS(SVG, tag) as SVGElement;
  for (const k of Object.keys(attrs)) e.setAttribute(k, String(attrs[k]));
  return e;
}

function fmt(n: number): string {
  return String(Math.round(n * 1000) / 1000);
}

function fmtArea(m2: number): string {
  return `${(Math.round(m2 * 100) / 100).toFixed(2)} m²`;
}

export class MapFusionPanel extends HTMLElement {
  private hassObj?: Hass;
  private narrowValue = false;
  private root: ShadowRoot;
  private built = false;

  private doc: FusedDoc | null = null;
  private loadError: string | null = null;
  private unsubscribe: Promise<(() => void) | void> | null = null;
  private subscribedVariant: string | null = null;

  private frameId: string | null = null;
  private variant: "traced" | "filled" = "traced";
  private selected: string | null = null;
  private draft: Draft | null = null;
  /** The shape mode picked for this selection (null: whatever the area's shape suggests). */
  private modePref: Mode | null = null;
  /** The selected polygon corner. */
  private vertex: number | null = null;
  /** The outline from before switching to a rectangle, to restore if you switch back unchanged. */
  private backup: Pair[] | null = null;
  /** How many of a hand-placed area's rings beyond the largest aren't edited (dropped on save). */
  private extraRings = 0;
  private lastVertexDown: { index: number; time: number } | null = null;
  private dirty = false;
  private step = 0.05;
  private status = "";
  private busy = false;
  private view: Rect = { x: 0, y: 0, width: 8, height: 6 };
  private drag: Drag | null = null;

  // Built once.
  private frameSelect!: HTMLSelectElement;
  private variantSelect!: HTMLSelectElement;
  private svg!: SVGSVGElement;
  private mapLayer!: SVGGElement;
  private draftLayer!: SVGGElement;
  private side!: HTMLElement;
  private menuButton!: HTMLElement & { hass?: Hass; narrow?: boolean };
  private inputs: Partial<Record<keyof Rect, HTMLInputElement>> = {};
  private vertexInputs: Array<[HTMLInputElement, HTMLInputElement]> = [];
  private vertexRows: HTMLElement[] = [];
  private areaReadout: HTMLElement | null = null;
  private warning: HTMLElement | null = null;
  private saveButton: HTMLButtonElement | null = null;

  constructor() {
    super();
    this.root = this.attachShadow({ mode: "open" });
  }

  set hass(hass: Hass) {
    const first = !this.hassObj;
    this.hassObj = hass;
    if (this.menuButton) this.menuButton.hass = hass;
    if (first) this.render();
    this.subscribe();
  }

  get hass(): Hass | undefined {
    return this.hassObj;
  }

  set narrow(value: boolean) {
    this.narrowValue = value;
    if (this.menuButton) this.menuButton.narrow = value;
    this.toggleAttribute("narrow", value);
  }

  get narrow(): boolean {
    return this.narrowValue;
  }

  connectedCallback(): void {
    this.render();
    this.subscribe();
  }

  disconnectedCallback(): void {
    this.stopSubscription();
  }

  // -- Data -------------------------------------------------------------

  private subscribe(): void {
    const hass = this.hassObj;
    if (!hass || !this.isConnected || this.subscribedVariant === this.variant) return;
    this.stopSubscription();
    this.subscribedVariant = this.variant;
    const message: Record<string, unknown> = { type: "map_fusion/subscribe" };
    if (this.variant !== "traced") message.variant = this.variant;
    this.unsubscribe = hass.connection
      .subscribeMessage<FusedDoc | null>((doc) => {
        this.doc = doc;
        this.loadError = null;
        this.render();
      }, message)
      .catch((err: { code?: string; message?: string }) => {
        this.loadError =
          err && err.code === "unknown_command"
            ? "Map Fusion isn't loaded. Restart Home Assistant after installing it."
            : `Couldn't load the map: ${(err && err.message) || String(err)}`;
        this.render();
      });
  }

  private stopSubscription(): void {
    const pending = this.unsubscribe;
    this.unsubscribe = null;
    this.subscribedVariant = null;
    if (pending) {
      pending
        .then((unsub) => {
          if (unsub) unsub();
        })
        .catch(() => undefined);
    }
  }

  /** Frames from the document, plus HA floors that have none yet. */
  private frames(): FusedFrame[] {
    const out = this.doc ? this.doc.frames.slice() : [];
    const floors = (this.hassObj && this.hassObj.floors) || {};
    for (const id of Object.keys(floors)) {
      if (out.some((f) => f.frame_id === id)) continue;
      out.push({ frame_id: id, floor_id: id, name: `${floors[id]!.name} (no vacuum map)`, bounds: null, areas: [], unmapped_rooms: [] });
    }
    return out;
  }

  private frame(): FusedFrame | null {
    const frames = this.frames();
    return frames.find((f) => f.frame_id === this.frameId) || frames[0] || null;
  }

  /** Areas you can work with in this frame. */
  private entries(frame: FusedFrame | null): Entry[] {
    const out: Entry[] = [];
    if (frame) {
      for (const a of frame.areas) out.push({ area_id: a.area_id, name: a.name, kind: a.origin, area: a });
    }
    const unplaced = this.doc ? this.doc.unplaced_areas : [];
    for (const a of unplaced) {
      // An area on another floor can't go in this floor's map.
      if (frame && frame.floor_id && a.floor_id && a.floor_id !== frame.floor_id) continue;
      out.push({ area_id: a.area_id, name: a.name, kind: "unplaced" });
    }
    return out;
  }

  private entry(): Entry | null {
    return this.entries(this.frame()).find((e) => e.area_id === this.selected) || null;
  }

  // -- Rendering --------------------------------------------------------

  private build(): void {
    this.root.innerHTML = "";
    const style = el("style");
    style.textContent = STYLES;
    const toolbar = el("div", "toolbar");
    this.menuButton = document.createElement("ha-menu-button") as HTMLElement & { hass?: Hass; narrow?: boolean };
    this.menuButton.hass = this.hassObj;
    this.menuButton.narrow = this.narrowValue;
    const title = el("div", "title", "Map Fusion");
    this.frameSelect = el("select", "frame");
    this.frameSelect.setAttribute("aria-label", "Map");
    this.frameSelect.addEventListener("change", () => this.selectFrame(this.frameSelect.value));
    this.variantSelect = el("select", "variant");
    this.variantSelect.setAttribute("aria-label", "Shapes");
    for (const [value, text] of [
      ["traced", "Shapes as traced"],
      ["filled", "Furniture filled"],
    ]) {
      const o = el("option", undefined, text);
      o.value = value!;
      this.variantSelect.append(o);
    }
    this.variantSelect.addEventListener("change", () => {
      this.variant = this.variantSelect.value === "filled" ? "filled" : "traced";
      this.subscribe();
    });
    toolbar.append(this.menuButton, title, this.frameSelect, this.variantSelect);

    const body = el("div", "body");
    const wrap = el("div", "map-wrap");
    this.svg = svgEl("svg", { class: "map", preserveAspectRatio: "xMidYMid meet", tabindex: 0 }) as SVGSVGElement;
    this.svg.setAttribute("role", "img");
    this.svg.setAttribute("aria-label", "Map");
    this.mapLayer = svgEl("g") as SVGGElement;
    this.draftLayer = svgEl("g", { class: "draft-layer" }) as SVGGElement;
    this.svg.append(this.mapLayer, this.draftLayer);
    this.svg.addEventListener("pointerdown", (e) => this.onPointerDown(e));
    this.svg.addEventListener("pointermove", (e) => this.onPointerMove(e));
    this.svg.addEventListener("pointerup", (e) => this.onPointerUp(e));
    this.svg.addEventListener("pointercancel", (e) => this.onPointerUp(e));
    this.svg.addEventListener("keydown", (e) => this.onKey(e));
    wrap.append(this.svg);
    this.side = el("div", "side");
    body.append(wrap, this.side);
    this.root.append(style, toolbar, body);
    this.built = true;
  }

  private render(): void {
    if (!this.isConnected) return;
    if (!this.built) this.build();
    const frames = this.frames();
    const frame = this.frame();
    if (frame) this.frameId = frame.frame_id;

    // Toolbar
    this.frameSelect.innerHTML = "";
    for (const f of frames) {
      const o = el("option", undefined, f.name);
      o.value = f.frame_id;
      o.selected = f.frame_id === this.frameId;
      this.frameSelect.append(o);
    }
    this.frameSelect.hidden = frames.length < 2;
    this.variantSelect.value = this.variant;

    // Keep the selection's draft in step with the document.
    const entry = this.entry();
    if (!entry) {
      this.selected = null;
      this.draft = null;
      this.dirty = false;
    } else if (entry.kind === "manual" && !this.dirty && entry.area) {
      this.draft = this.areaDraft(entry.area);
    }
    if (this.vertex !== null && (!this.draft || this.draft.kind !== "polygon" || this.vertex >= this.draft.ring.length)) {
      this.vertex = null;
    }

    this.renderMap(frame);
    this.renderSide(frame);
  }

  /** A hand-placed area as a draft: a rectangle if it is one (or that mode was picked), else its largest ring. */
  private areaDraft(area: FusedArea): Draft {
    const rings = area.polygons.filter((r) => r.length >= 3);
    const ring = largestRing(rings);
    this.extraRings = Math.max(0, rings.length - 1);
    const mode = this.modePref || (ring && !isRectangle(area.polygons, area.rect) ? "polygon" : "rect");
    if (mode === "polygon" && ring) return { kind: "polygon", ring: cleanRing(ring) };
    return { kind: "rect", rect: { ...area.rect } };
  }

  private renderMap(frame: FusedFrame | null): void {
    const rects: Rect[] = [];
    if (frame) {
      for (const a of frame.areas) rects.push(a.rect);
      for (const r of frame.unmapped_rooms) rects.push(r.rect);
    }
    if (this.draft) rects.push(draftBounds(this.draft));
    if (!this.drag) this.view = viewBounds(rects);
    const v = this.view;
    this.svg.setAttribute("viewBox", `${v.x} ${v.y} ${v.width} ${v.height}`);

    const g = this.mapLayer;
    g.innerHTML = "";
    const grid = svgEl("g", { class: "grid" });
    const fontSize = this.unitsPerPx() * 11;
    const labelEvery = v.width > 30 ? 5 : v.width > 15 ? 2 : 1;
    for (let x = v.x; x <= v.x + v.width; x++) {
      grid.append(svgEl("line", { x1: x, y1: v.y, x2: x, y2: v.y + v.height, class: x === 0 ? "axis" : "" }));
      if ((x - v.x) % labelEvery === 0 && x > v.x) {
        const t = svgEl("text", { x: x, y: v.y + fontSize * 1.2, class: "tick", "font-size": fontSize });
        t.textContent = String(x);
        grid.append(t);
      }
    }
    for (let y = v.y; y <= v.y + v.height; y++) {
      grid.append(svgEl("line", { x1: v.x, y1: y, x2: v.x + v.width, y2: y, class: y === 0 ? "axis" : "" }));
      if ((y - v.y) % labelEvery === 0 && y > v.y) {
        const t = svgEl("text", { x: v.x + fontSize * 0.3, y: y - fontSize * 0.3, class: "tick", "font-size": fontSize });
        t.textContent = String(y);
        grid.append(t);
      }
    }
    g.append(grid);
    if (!frame) return;

    for (const room of frame.unmapped_rooms) g.append(svgEl("path", { d: ringsPath(room.polygons), class: "unlinked" }));
    for (const a of frame.areas) {
      const cls = ["room", a.origin === "manual" ? "manual" : "", a.area_id === this.selected ? "selected" : ""];
      const editingThis = a.area_id === this.selected && this.draft;
      const path = svgEl("path", { d: ringsPath(a.polygons), class: cls.join(" ") + (editingThis ? " ghost" : "") });
      path.setAttribute("data-area", a.area_id);
      const title = svgEl("title");
      title.textContent = a.name;
      path.append(title);
      g.append(path);
    }
    for (const a of frame.areas) {
      if (a.area_id === this.selected && this.draft) continue; // the draft shows its own label
      // The map is in metres, so the text halo is sized from the zoom too.
      const t = svgEl("text", {
        x: a.label_point[0],
        y: a.label_point[1],
        class: "label",
        "font-size": fontSize * 1.15,
        "stroke-width": this.unitsPerPx() * 3,
      });
      t.textContent = a.name;
      g.append(t);
    }
    this.renderDraft();
  }

  /** Metres per screen pixel (for sizes that should look the same at any zoom). */
  private unitsPerPx(): number {
    const w = this.svg && this.svg.clientWidth;
    const h = this.svg && this.svg.clientHeight;
    if (!w || !h) return this.view.width / 800;
    return Math.max(this.view.width / w, this.view.height / h);
  }

  private renderDraft(): void {
    const g = this.draftLayer;
    g.innerHTML = "";
    const d = this.draft;
    if (!d) return;
    const u = this.unitsPerPx();
    let centre: Pair;
    let size: string;
    if (d.kind === "rect") {
      const r = d.rect;
      const body = svgEl("rect", { x: r.x, y: r.y, width: r.width, height: r.height, class: "draft" });
      body.setAttribute("data-handle", "move");
      g.append(body);
      const s = u * 12;
      for (const h of HANDLES) {
        const [hx, hy] = handlePoint(r, h);
        const handle = svgEl("rect", { x: hx - s / 2, y: hy - s / 2, width: s, height: s, class: `handle handle-${h}` });
        handle.setAttribute("data-handle", h);
        g.append(handle);
      }
      centre = [r.x + r.width / 2, r.y + r.height / 2];
      size = `${fmt(r.width)} × ${fmt(r.height)} m`;
    } else {
      const ring = d.ring;
      const n = ring.length;
      const body = svgEl("path", { d: ringsPath([ring]), class: "draft" + (this.problem() ? " invalid" : "") });
      body.setAttribute("data-handle", "move");
      g.append(body);
      // Midpoints first, so corners sit on top; skip edges too short to grab both.
      for (let i = 0; i < n; i++) {
        const a = ring[i]!;
        const b = ring[(i + 1) % n]!;
        const len = Math.sqrt(Math.pow(b[0] - a[0], 2) + Math.pow(b[1] - a[1], 2));
        if (len < u * 28) continue;
        const mid = svgEl("circle", { cx: (a[0] + b[0]) / 2, cy: (a[1] + b[1]) / 2, r: u * 4.5, class: "midpoint" });
        mid.setAttribute("data-mid", String(i));
        const title = svgEl("title");
        title.textContent = "Drag or click to add a corner";
        mid.append(title);
        g.append(mid);
      }
      for (let i = 0; i < n; i++) {
        const p = ring[i]!;
        const c = svgEl("circle", { cx: p[0], cy: p[1], r: u * 6.5, class: "vertex" + (i === this.vertex ? " selected" : "") });
        c.setAttribute("data-vertex", String(i));
        g.append(c);
      }
      const b = ringBounds(ring);
      centre = ringCentroid(ring);
      if (!pointInRing(centre[0], centre[1], ring)) centre = [b.x + b.width / 2, b.y + b.height / 2];
      size = fmtArea(ringArea(ring));
    }
    const label = svgEl("text", {
      x: centre[0],
      y: centre[1],
      class: "draft-label",
      "font-size": u * 13,
      "stroke-width": u * 3,
    });
    label.textContent = size;
    g.append(label);
    const entry = this.entry();
    if (entry) {
      const name = svgEl("text", {
        x: centre[0],
        y: centre[1] - u * 16,
        class: "draft-label",
        "font-size": u * 13,
        "stroke-width": u * 3,
      });
      name.textContent = entry.name;
      g.append(name);
    }
  }

  private renderSide(frame: FusedFrame | null): void {
    const side = this.side;
    side.innerHTML = "";
    this.inputs = {};
    this.vertexInputs = [];
    this.vertexRows = [];
    this.areaReadout = null;
    this.warning = null;
    this.saveButton = null;

    if (this.loadError) {
      side.append(el("div", "error", this.loadError));
      return;
    }
    if (!this.doc) {
      side.append(el("div", "hint", "Loading the map…"));
      return;
    }
    if (!frame) {
      side.append(el("div", "hint", "No map yet. Link your vacuum's rooms to areas, or create a floor."));
      return;
    }

    const entry = this.entry();
    if (entry) side.append(this.editor(entry));
    else side.append(el("div", "hint", "Pick an area below, or click one on the map. Hand-placed and unplaced areas can be dragged into place."));

    const groups: Array<[string, Kind[]]> = [
      ["Not on the map yet", ["unplaced"]],
      ["Placed by hand", ["manual"]],
      ["From the vacuum map", ["vacuum"]],
    ];
    const entries = this.entries(frame);
    for (const [title, kinds] of groups) {
      const items = entries.filter((e) => kinds.indexOf(e.kind) !== -1);
      if (!items.length) continue;
      side.append(el("h3", undefined, title));
      const list = el("div", "list");
      for (const item of items) {
        const b = el("button", "item" + (item.area_id === this.selected ? " active" : ""), item.name);
        b.type = "button";
        b.setAttribute("data-select", item.area_id);
        b.addEventListener("click", () => this.select(item.area_id));
        list.append(b);
      }
      side.append(list);
    }
  }

  private editor(entry: Entry): HTMLElement {
    const box = el("div", "editor");
    box.append(el("h2", undefined, entry.name));
    const what: Record<Kind, string> = {
      vacuum: "Shape from the vacuum map.",
      manual: "Placed by hand.",
      unplaced: "Not on the map yet.",
    };
    box.append(el("div", "hint", what[entry.kind]));

    if (!this.draft) {
      const actions = el("div", "actions");
      if (entry.kind === "unplaced") {
        actions.append(
          this.button("Place on the map", "place", true, () => this.startDraft({ kind: "rect", rect: defaultSpot(this.bounds()) })),
        );
      } else if (entry.kind === "vacuum" && entry.area) {
        const area = entry.area;
        actions.append(
          this.button("Replace with a rectangle", "replace", false, () =>
            this.startDraft({ kind: "rect", rect: snapRect(area.rect, 0.01) }),
          ),
          this.button("Replace with a polygon", "replace-polygon", false, () =>
            this.startDraft({ kind: "polygon", ring: editableOutline(area.polygons, area.rect) }),
          ),
        );
      }
      box.append(actions);
      if (entry.kind === "vacuum") {
        box.append(el("div", "hint small", "To change which room this is, edit the vacuum's area links instead."));
      }
      return box;
    }

    const draft = this.draft;
    if (entry.kind === "manual" && this.extraRings) {
      const parts = this.extraRings + 1;
      box.append(
        el("div", "warning", `This area has ${parts} separate parts. Only the largest is edited here; saving drops the other ${parts - 1 === 1 ? "one" : parts - 1}.`),
      );
    }
    if (entry.kind === "vacuum") {
      box.append(el("div", "warning", "Saving replaces the vacuum's shape for this area. Remove the placement later to go back."));
    }

    box.append(this.modeToggle(draft.kind));
    box.append(
      el(
        "div",
        "hint small",
        draft.kind === "rect"
          ? "Drag the rectangle, a corner or an edge, or type below. Arrow keys move it; Shift + arrows resize."
          : "Drag a corner, or the whole shape. Click a dot on an edge to add a corner; double-click a corner (or select it and press Delete) to remove it. Shift while dragging lines a corner up with its neighbour.",
      ),
    );

    const fields = el("div", "fields");
    if (draft.kind === "rect") {
      for (const key of FIELDS) {
        const label = el("label");
        label.append(el("span", undefined, `${FIELD_LABELS[key]} (m)`));
        const input = this.numberInput(fmt(draft.rect[key]));
        input.setAttribute("data-field", key);
        input.addEventListener("input", () => this.onField(key, input.value));
        label.append(input);
        fields.append(label);
        this.inputs[key] = input;
      }
    } else {
      fields.append(this.vertexList(draft.ring));
    }
    const snapLabel = el("label");
    snapLabel.append(el("span", undefined, "Snap to"));
    const snapSelect = el("select");
    for (const s of SNAP_STEPS) {
      const o = el("option", undefined, s < 0.1 ? `${Math.round(s * 100)} cm` : `${s} m`);
      o.value = String(s);
      o.selected = s === this.step;
      snapSelect.append(o);
    }
    snapSelect.addEventListener("change", () => {
      this.step = Number(snapSelect.value);
      for (const pair of this.vertexInputs) for (const input of pair) input.step = String(this.step);
      for (const key of FIELDS) {
        const input = this.inputs[key];
        if (input) input.step = String(this.step);
      }
    });
    snapLabel.append(snapSelect);
    fields.append(snapLabel);
    box.append(fields);

    this.warning = el("div", "warning");
    box.append(this.warning);
    this.updateWarning();

    const actions = el("div", "actions");
    this.saveButton = this.button("Save", "save", true, () => this.save());
    this.saveButton.disabled = !this.canSave();
    actions.append(this.saveButton);
    if (entry.kind !== "manual" || this.dirty) {
      actions.append(this.button(entry.kind === "manual" ? "Undo changes" : "Cancel", "cancel", false, () => this.cancel()));
    }
    if (entry.kind === "manual") {
      actions.append(this.button("Remove placement", "remove", false, () => this.removePlacement(), true));
    }
    box.append(actions);
    if (this.status) box.append(el("div", "status", this.status));
    return box;
  }

  private numberInput(value: string): HTMLInputElement {
    const input = el("input");
    input.type = "number";
    input.step = String(this.step);
    input.value = value;
    return input;
  }

  /** Rectangle | Polygon switch. */
  private modeToggle(current: Mode): HTMLElement {
    const group = el("div", "segmented");
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", "Shape");
    const modes: Array<[Mode, string]> = [
      ["rect", "Rectangle"],
      ["polygon", "Polygon"],
    ];
    for (const [mode, text] of modes) {
      const b = el("button", "seg" + (mode === current ? " active" : ""), text);
      b.type = "button";
      b.setAttribute("data-mode", mode);
      b.setAttribute("aria-pressed", String(mode === current));
      b.disabled = this.busy;
      b.addEventListener("click", () => this.setMode(mode));
      group.append(b);
    }
    return group;
  }

  /** The polygon's corners as x/y fields, plus its area. */
  private vertexList(ring: Pair[]): HTMLElement {
    const wrap = el("div", "vertices");
    const head = el("div", "vertex-row head");
    head.append(el("span", undefined, "#"), el("span", undefined, "x (m)"), el("span", undefined, "y (m)"), el("span"));
    wrap.append(head);
    ring.forEach((p, i) => {
      const row = el("div", "vertex-row" + (i === this.vertex ? " selected" : ""));
      row.append(el("span", "vertex-index", String(i + 1)));
      const pair: HTMLInputElement[] = [];
      for (const axis of [0, 1]) {
        const input = this.numberInput(fmt(p[axis]!));
        input.setAttribute(axis ? "data-vy" : "data-vx", String(i));
        input.setAttribute("aria-label", `Corner ${i + 1} ${axis ? "y" : "x"} (m)`);
        input.addEventListener("input", () => this.onVertexField(i, axis, input.value));
        input.addEventListener("focus", () => this.selectVertex(i));
        row.append(input);
        pair.push(input);
      }
      const remove = el("button", "icon-btn", "×");
      remove.type = "button";
      remove.title = "Remove this corner";
      remove.setAttribute("aria-label", `Remove corner ${i + 1}`);
      remove.setAttribute("data-remove-vertex", String(i));
      remove.disabled = this.busy || ring.length <= MIN_POINTS;
      remove.addEventListener("click", () => this.deleteVertex(i));
      row.append(remove);
      wrap.append(row);
      this.vertexRows.push(row);
      this.vertexInputs.push([pair[0]!, pair[1]!]);
    });
    this.areaReadout = el("div", "readout", `${ring.length} corners · ${fmtArea(ringArea(ring))}`);
    this.areaReadout.setAttribute("data-readout", "area");
    wrap.append(this.areaReadout);
    return wrap;
  }

  private button(text: string, action: string, primary: boolean, onClick: () => void, danger = false): HTMLButtonElement {
    const b = el("button", "btn" + (primary ? " primary" : "") + (danger ? " danger" : ""), text);
    b.type = "button";
    b.setAttribute("data-action", action);
    b.disabled = this.busy;
    b.addEventListener("click", onClick);
    return b;
  }

  private bounds(): Rect | null {
    const frame = this.frame();
    if (!frame) return null;
    if (frame.bounds) return frame.bounds;
    return union(frame.areas.map((a) => a.rect));
  }

  /** Why the draft can't be saved as it is (a polygon that crosses itself), or null. */
  private problem(): string | null {
    return this.draft && this.draft.kind === "polygon" ? ringProblem(this.draft.ring) : null;
  }

  private canSave(): boolean {
    return this.dirty && !this.busy && !this.problem();
  }

  /** Live feedback: a shape the server would refuse, and what the draft overlaps. */
  private updateWarning(): void {
    if (!this.warning || !this.draft) return;
    const frame = this.frame();
    const bounds = draftBounds(this.draft);
    const ring = draftRing(this.draft);
    // Bounding boxes first (cheap), then the real outlines, so an L-shaped
    // room next door doesn't count just because its box does.
    const hits = (frame ? frame.areas : [])
      .filter(
        (a) =>
          a.area_id !== this.selected &&
          intersectionArea(a.rect, bounds) > 0.01 &&
          a.polygons.some((r) => ringsOverlap(ring, r)),
      )
      .map((a) => a.name);
    const messages: string[] = [];
    const problem = this.problem();
    if (problem) messages.push(problem);
    if (hits.length) messages.push(`Overlaps ${hits.join(", ")}.`);
    this.warning.textContent = messages.join(" ");
    this.warning.hidden = !messages.length;
  }

  /**
   * Push the draft into the number fields (not the one being typed in).
   * `except` is a rect field name, or "i:x" / "i:y" for a corner.
   */
  private syncInputs(except?: string): void {
    const d = this.draft;
    if (!d) return;
    if (d.kind === "rect") {
      for (const key of FIELDS) {
        const input = this.inputs[key];
        if (input && key !== except) input.value = fmt(d.rect[key]);
      }
    } else {
      if (this.vertexInputs.length !== d.ring.length) {
        // A corner was added or removed: rebuild the list.
        this.renderSide(this.frame());
        return;
      }
      d.ring.forEach((p, i) => {
        const pair = this.vertexInputs[i]!;
        if (except !== `${i}:x`) pair[0].value = fmt(p[0]);
        if (except !== `${i}:y`) pair[1].value = fmt(p[1]);
      });
      if (this.areaReadout) this.areaReadout.textContent = `${d.ring.length} corners · ${fmtArea(ringArea(d.ring))}`;
    }
    if (this.saveButton) this.saveButton.disabled = !this.canSave();
    this.updateWarning();
  }

  /** Show which corner is selected, on the map and in the list. */
  private highlightVertex(): void {
    this.renderDraft();
    this.vertexRows.forEach((row, i) => row.classList.toggle("selected", i === this.vertex));
  }

  // -- Actions ----------------------------------------------------------

  /** Forget everything about the current edit (new selection, frame, cancel). */
  private resetEdit(): void {
    this.draft = null;
    this.dirty = false;
    this.status = "";
    this.modePref = null;
    this.vertex = null;
    this.backup = null;
    this.extraRings = 0;
    this.lastVertexDown = null;
  }

  private selectFrame(frameId: string): void {
    if (!this.confirmDiscard()) {
      this.frameSelect.value = this.frameId || "";
      return;
    }
    this.frameId = frameId;
    this.selected = null;
    this.resetEdit();
    this.render();
  }

  select(areaId: string): void {
    if (areaId === this.selected) return;
    if (!this.confirmDiscard()) return;
    this.selected = areaId;
    this.resetEdit();
    this.render();
  }

  private confirmDiscard(): boolean {
    if (!this.dirty) return true;
    return typeof window.confirm !== "function" || window.confirm("Discard the unsaved changes?");
  }

  private startDraft(draft: Draft): void {
    this.draft = draft;
    this.modePref = draft.kind;
    this.vertex = null;
    this.dirty = true;
    this.status = "";
    this.render();
  }

  private cancel(): void {
    this.resetEdit();
    this.render();
  }

  /**
   * Rectangle → polygon: the rectangle's 4 corners (or the outline it came
   * from, if you just switched and changed nothing). Polygon → rectangle:
   * the bounding box, which loses any detail.
   */
  private setMode(mode: Mode): void {
    const d = this.draft;
    if (!d || d.kind === mode) return;
    this.modePref = mode;
    this.vertex = null;
    if (d.kind === "rect") {
      const restore = this.backup && sameRect(ringBounds(this.backup), d.rect) ? this.backup : null;
      this.draft = { kind: "polygon", ring: restore || rectRing(d.rect) };
      this.status = restore ? "The outline is back." : "";
      this.backup = null;
    } else {
      const rect = ringBounds(d.ring);
      this.draft = { kind: "rect", rect };
      if (isRectangle([d.ring], rect)) {
        this.status = "";
      } else {
        this.backup = d.ring;
        this.dirty = true;
        this.status = "Now the rectangle around the outline, so its detail is lost. Switch back to Polygon before changing anything to get it back.";
      }
    }
    this.render();
  }

  /** Apply an edit to the draft and refresh what shows it. */
  private update(next: Draft, except?: string): boolean {
    if (this.draft && JSON.stringify(next) === JSON.stringify(this.draft)) return false;
    this.draft = next;
    this.dirty = true;
    this.status = "";
    this.renderDraft();
    this.syncInputs(except);
    return true;
  }

  private onField(key: keyof Rect, raw: string): void {
    const d = this.draft;
    if (!d || d.kind !== "rect") return;
    const value = Number(raw);
    if (raw === "" || !isFinite(value)) return;
    if ((key === "width" || key === "height") && value <= 0) return;
    this.update({ kind: "rect", rect: { ...d.rect, [key]: value } }, key);
  }

  private onVertexField(index: number, axis: number, raw: string): void {
    const d = this.draft;
    if (!d || d.kind !== "polygon" || index >= d.ring.length) return;
    const value = Number(raw);
    if (raw === "" || !isFinite(value)) return;
    const p = d.ring[index]!;
    this.update({ kind: "polygon", ring: setVertex(d.ring, index, axis ? [p[0], value] : [value, p[1]]) }, `${index}:${axis ? "y" : "x"}`);
  }

  private selectVertex(index: number | null): void {
    if (this.vertex === index) return;
    this.vertex = index;
    this.highlightVertex();
  }

  private deleteVertex(index: number): void {
    const d = this.draft;
    if (!d || d.kind !== "polygon") return;
    if (d.ring.length <= MIN_POINTS) {
      this.status = `A polygon needs at least ${MIN_POINTS} corners.`;
      this.render();
      return;
    }
    this.vertex = null;
    this.update({ kind: "polygon", ring: removeVertex(d.ring, index) });
  }

  private async save(): Promise<void> {
    const hass = this.hassObj;
    const frame = this.frame();
    const d = this.draft;
    if (!hass || !frame || !d || !this.selected || this.problem()) return;
    const message: Record<string, unknown> = { type: "map_fusion/area/set", frame_id: frame.frame_id, area_id: this.selected };
    if (d.kind === "rect") message.rect = d.rect;
    else message.polygons = [cleanRing(d.ring)];
    this.busy = true;
    this.status = "Saving…";
    this.render();
    try {
      await hass.callWS(message);
      this.dirty = false;
      this.backup = null;
      this.status = "Saved.";
    } catch (err) {
      const e = err as { message?: string };
      this.status = `Couldn't save: ${(e && e.message) || String(err)}`;
    }
    this.busy = false;
    this.render();
  }

  private async removePlacement(): Promise<void> {
    const hass = this.hassObj;
    const frame = this.frame();
    if (!hass || !frame || !this.selected) return;
    this.busy = true;
    this.render();
    try {
      await hass.callWS({ type: "map_fusion/area/clear", frame_id: frame.frame_id, area_id: this.selected });
      this.resetEdit();
    } catch (err) {
      const e = err as { message?: string };
      this.status = `Couldn't remove: ${(e && e.message) || String(err)}`;
    }
    this.busy = false;
    this.render();
  }

  // -- Pointer and keys -------------------------------------------------

  private toMap(e: { clientX: number; clientY: number }): Pair {
    return clientToMap(e.clientX, e.clientY, this.svg.getBoundingClientRect(), this.view);
  }

  private beginDrag(e: PointerEvent, handle: Drag["handle"], vertex: number): void {
    e.preventDefault();
    this.drag = { handle, vertex, start: copyDraft(this.draft!), from: this.toMap(e), pointerId: e.pointerId, moved: false };
    try {
      this.svg.setPointerCapture(e.pointerId);
    } catch {
      // Not supported (tests, old browsers): moves still arrive while over the map.
    }
    // Keys (Delete, arrows) go to the map; preventDefault above can stop it getting focus.
    try {
      this.svg.focus();
    } catch {
      // Old browsers can't focus SVG.
    }
  }

  private onPointerDown(e: PointerEvent): void {
    const target = e.target as Element | null;
    const d = this.draft;
    const attr = (name: string) => (target ? target.getAttribute(name) : null);

    if (d && d.kind === "polygon") {
      const vertexAttr = attr("data-vertex");
      if (vertexAttr !== null) {
        const index = Number(vertexAttr);
        const now = Date.now();
        const last = this.lastVertexDown;
        if (last && last.index === index && now - last.time < DOUBLE_PRESS_MS) {
          // Second press on the same corner: remove it.
          e.preventDefault();
          this.lastVertexDown = null;
          this.deleteVertex(index);
          return;
        }
        this.lastVertexDown = { index, time: now };
        this.beginDrag(e, "vertex", index);
        this.selectVertex(index);
        return;
      }
      const midAttr = attr("data-mid");
      if (midAttr !== null) {
        // Add a corner in the middle of the edge and drag it straight away.
        const edge = Number(midAttr);
        this.lastVertexDown = null;
        this.vertex = edge + 1;
        this.update({ kind: "polygon", ring: insertVertex(d.ring, edge) });
        this.beginDrag(e, "vertex", edge + 1);
        return;
      }
    }

    const handle = attr("data-handle");
    if (handle && d) {
      this.lastVertexDown = null;
      this.beginDrag(e, handle as Handle, -1);
      if (this.vertex !== null) this.selectVertex(null);
      return;
    }
    // A click on a room selects it.
    const areaId = attr("data-area");
    if (areaId) {
      this.select(areaId);
      return;
    }
    const frame = this.frame();
    if (frame) {
      const [x, y] = this.toMap(e);
      const hit = frame.areas.find((a) => a.polygons.some((r) => pointInRing(x, y, r)));
      if (hit) this.select(hit.area_id);
    }
  }

  private onPointerMove(e: PointerEvent): void {
    const drag = this.drag;
    if (!drag || e.pointerId !== drag.pointerId) return;
    const [x, y] = this.toMap(e);
    const dx = x - drag.from[0];
    const dy = y - drag.from[1];
    const s = drag.start;
    let next: Draft;
    if (s.kind === "rect") {
      next = { kind: "rect", rect: dragRect(s.rect, drag.handle === "vertex" ? "move" : drag.handle, dx, dy, this.step) };
    } else if (drag.handle === "vertex") {
      // Shift lines the corner up with a neighbour (square corners made easy).
      next = { kind: "polygon", ring: dragVertex(s.ring, drag.vertex, dx, dy, this.step, e.shiftKey) };
    } else {
      next = { kind: "polygon", ring: translateRing(s.ring, dx, dy, this.step) };
    }
    if (this.update(next)) drag.moved = true;
  }

  private onPointerUp(e: PointerEvent): void {
    const drag = this.drag;
    if (!drag || e.pointerId !== drag.pointerId) return;
    this.drag = null;
    if (drag.moved) this.lastVertexDown = null; // a drag isn't half a double-click
    try {
      this.svg.releasePointerCapture(e.pointerId);
    } catch {
      // see beginDrag
    }
    this.render(); // the view may grow to fit the new spot
  }

  private onKey(e: KeyboardEvent): void {
    const d = this.draft;
    if (!d) return;
    if (d.kind === "polygon" && this.vertex !== null) {
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        this.deleteVertex(this.vertex);
        return;
      }
      if (e.key === "Escape") {
        this.selectVertex(null);
        return;
      }
    }
    const keys: Record<string, [number, number]> = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    const move = keys[e.key];
    if (!move) return;
    e.preventDefault();
    const dx = move[0] * this.step;
    const dy = move[1] * this.step;
    if (d.kind === "rect") {
      // Shift resizes (moves the bottom-right corner) instead of moving.
      this.update({ kind: "rect", rect: dragRect(d.rect, e.shiftKey ? "se" : "move", dx, dy, this.step) });
    } else if (this.vertex !== null) {
      // A selected corner moves on its own.
      this.update({ kind: "polygon", ring: dragVertex(d.ring, this.vertex, dx, dy, this.step) });
    } else {
      this.update({ kind: "polygon", ring: translateRing(d.ring, dx, dy, this.step) });
    }
  }
}
