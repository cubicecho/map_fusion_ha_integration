/**
 * <map-fusion-panel>: Map Fusion's sidebar page (admins only).
 *
 * Shows a fused map with a metre grid. Pick an area, then drag its
 * rectangle (or a corner/edge handle) or type numbers; both stay in step.
 * Save calls map_fusion/area/set, Remove calls map_fusion/area/clear. The
 * map updates from map_fusion/subscribe.
 *
 * Structure is rebuilt when the document, frame, variant or selection
 * changes. Drags only touch the draft rectangle and the number fields.
 */
import {
  HANDLES,
  clientToMap,
  defaultSpot,
  dragRect,
  handlePoint,
  intersectionArea,
  isRectangle,
  pointInRing,
  ringsPath,
  snapRect,
  union,
  viewBounds,
  type Handle,
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

interface Drag {
  handle: Handle;
  start: Rect;
  from: [number, number];
  pointerId: number;
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
  private draft: Rect | null = null;
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
      this.draft = { ...entry.area.rect };
    }

    this.renderMap(frame);
    this.renderSide(frame);
  }

  private renderMap(frame: FusedFrame | null): void {
    const rects: Rect[] = [];
    if (frame) {
      for (const a of frame.areas) rects.push(a.rect);
      for (const r of frame.unmapped_rooms) rects.push(r.rect);
    }
    if (this.draft) rects.push(this.draft);
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
    const r = this.draft;
    if (!r) return;
    const u = this.unitsPerPx();
    const body = svgEl("rect", { x: r.x, y: r.y, width: r.width, height: r.height, class: "draft" });
    body.setAttribute("data-handle", "move");
    g.append(body);
    const size = u * 12;
    for (const h of HANDLES) {
      const [hx, hy] = handlePoint(r, h);
      const handle = svgEl("rect", {
        x: hx - size / 2,
        y: hy - size / 2,
        width: size,
        height: size,
        class: `handle handle-${h}`,
      });
      handle.setAttribute("data-handle", h);
      g.append(handle);
    }
    const label = svgEl("text", {
      x: r.x + r.width / 2,
      y: r.y + r.height / 2,
      class: "draft-label",
      "font-size": u * 13,
      "stroke-width": u * 3,
    });
    label.textContent = `${fmt(r.width)} × ${fmt(r.height)} m`;
    g.append(label);
    const entry = this.entry();
    if (entry) {
      const name = svgEl("text", {
        x: r.x + r.width / 2,
        y: r.y + r.height / 2 - u * 16,
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
      manual: "Placed by hand. Drag it, its corners or edges, or type below.",
      unplaced: "Not on the map yet.",
    };
    box.append(el("div", "hint", what[entry.kind]));

    if (!this.draft) {
      const actions = el("div", "actions");
      if (entry.kind === "unplaced") {
        actions.append(this.button("Place on the map", "place", true, () => this.startDraft(defaultSpot(this.bounds()))));
      } else if (entry.kind === "vacuum" && entry.area) {
        const area = entry.area;
        actions.append(this.button("Replace with a rectangle", "replace", false, () => this.startDraft(snapRect(area.rect, 0.01))));
      }
      box.append(actions);
      if (entry.kind === "vacuum") {
        box.append(el("div", "hint small", "To change which room this is, edit the vacuum's area links instead."));
      }
      return box;
    }

    if (entry.kind === "manual" && entry.area && !isRectangle(entry.area.polygons, entry.area.rect)) {
      box.append(el("div", "warning", "This area has a polygon shape; saving here turns it into a rectangle."));
    }
    if (entry.kind === "vacuum") {
      box.append(el("div", "warning", "Saving replaces the vacuum's shape for this area. Remove the placement later to go back."));
    }

    const fields = el("div", "fields");
    for (const key of FIELDS) {
      const label = el("label");
      label.append(el("span", undefined, `${FIELD_LABELS[key]} (m)`));
      const input = el("input");
      input.type = "number";
      input.step = String(this.step);
      input.value = fmt(this.draft[key]);
      input.setAttribute("data-field", key);
      input.addEventListener("input", () => this.onField(key, input.value));
      label.append(input);
      fields.append(label);
      this.inputs[key] = input;
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
    this.saveButton.disabled = !this.dirty || this.busy;
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

  /** Live feedback: the draft's size and what it overlaps. */
  private updateWarning(): void {
    if (!this.warning || !this.draft) return;
    const frame = this.frame();
    const draft = this.draft;
    const hits = (frame ? frame.areas : [])
      .filter((a) => a.area_id !== this.selected && intersectionArea(a.rect, draft) > 0.01)
      .map((a) => a.name);
    this.warning.textContent = hits.length ? `Overlaps ${hits.join(", ")}.` : "";
    this.warning.hidden = !hits.length;
  }

  /** Push the draft into the number fields (not the one being typed in). */
  private syncInputs(except?: keyof Rect): void {
    if (!this.draft) return;
    for (const key of FIELDS) {
      const input = this.inputs[key];
      if (input && key !== except) input.value = fmt(this.draft[key]);
    }
    if (this.saveButton) this.saveButton.disabled = !this.dirty || this.busy;
    this.updateWarning();
  }

  // -- Actions ----------------------------------------------------------

  private selectFrame(frameId: string): void {
    if (!this.confirmDiscard()) {
      this.frameSelect.value = this.frameId || "";
      return;
    }
    this.frameId = frameId;
    this.selected = null;
    this.draft = null;
    this.dirty = false;
    this.status = "";
    this.render();
  }

  select(areaId: string): void {
    if (areaId === this.selected) return;
    if (!this.confirmDiscard()) return;
    this.selected = areaId;
    this.draft = null;
    this.dirty = false;
    this.status = "";
    this.render();
  }

  private confirmDiscard(): boolean {
    if (!this.dirty) return true;
    return typeof window.confirm !== "function" || window.confirm("Discard the unsaved changes?");
  }

  private startDraft(rect: Rect): void {
    this.draft = rect;
    this.dirty = true;
    this.status = "";
    this.render();
  }

  private cancel(): void {
    this.draft = null;
    this.dirty = false;
    this.status = "";
    this.render();
  }

  private onField(key: keyof Rect, raw: string): void {
    if (!this.draft) return;
    const value = Number(raw);
    if (raw === "" || !isFinite(value)) return;
    if ((key === "width" || key === "height") && value <= 0) return;
    this.draft = { ...this.draft, [key]: value };
    this.dirty = true;
    this.status = "";
    this.renderDraft();
    this.syncInputs(key);
  }

  private async save(): Promise<void> {
    const hass = this.hassObj;
    const frame = this.frame();
    if (!hass || !frame || !this.draft || !this.selected) return;
    this.busy = true;
    this.status = "Saving…";
    this.render();
    try {
      await hass.callWS({
        type: "map_fusion/area/set",
        frame_id: frame.frame_id,
        area_id: this.selected,
        rect: this.draft,
      });
      this.dirty = false;
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
      this.draft = null;
      this.dirty = false;
      this.status = "";
    } catch (err) {
      const e = err as { message?: string };
      this.status = `Couldn't remove: ${(e && e.message) || String(err)}`;
    }
    this.busy = false;
    this.render();
  }

  // -- Pointer and keys -------------------------------------------------

  private toMap(e: { clientX: number; clientY: number }): [number, number] {
    return clientToMap(e.clientX, e.clientY, this.svg.getBoundingClientRect(), this.view);
  }

  private onPointerDown(e: PointerEvent): void {
    const target = e.target as Element | null;
    const handle = target && target.getAttribute("data-handle");
    if (handle && this.draft) {
      e.preventDefault();
      this.drag = { handle: handle as Handle, start: { ...this.draft }, from: this.toMap(e), pointerId: e.pointerId };
      try {
        this.svg.setPointerCapture(e.pointerId);
      } catch {
        // Not supported (tests, old browsers): moves still arrive while over the map.
      }
      return;
    }
    // A click on a room selects it.
    const areaId = target && target.getAttribute("data-area");
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
    this.draft = dragRect(drag.start, drag.handle, x - drag.from[0], y - drag.from[1], this.step);
    this.dirty = true;
    this.status = "";
    this.renderDraft();
    this.syncInputs();
  }

  private onPointerUp(e: PointerEvent): void {
    if (!this.drag || e.pointerId !== this.drag.pointerId) return;
    this.drag = null;
    try {
      this.svg.releasePointerCapture(e.pointerId);
    } catch {
      // see onPointerDown
    }
    this.render(); // the view may grow to fit the new spot
  }

  private onKey(e: KeyboardEvent): void {
    if (!this.draft) return;
    const d: Record<string, [number, number]> = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    const move = d[e.key];
    if (!move) return;
    e.preventDefault();
    // Shift resizes (moves the bottom-right corner) instead of moving.
    const handle: Handle = e.shiftKey ? "se" : "move";
    this.draft = dragRect(this.draft, handle, move[0] * this.step, move[1] * this.step, this.step);
    this.dirty = true;
    this.renderDraft();
    this.syncInputs();
  }
}
