/**
 * Editing maths for the panel: pure functions, no DOM.
 *
 * Coordinates are frame metres, x right, y down (same as the fused map).
 */

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type Pair = [number, number];

/** Which part of the rectangle is being dragged. */
export type Handle = "move" | "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

export const HANDLES: Handle[] = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];

/** Smallest width or height a drag can make. */
export const MIN_SIZE = 0.1;

/** Round to the nearest multiple of `step` (and to mm, to hide float noise). */
export function snap(value: number, step: number): number {
  const v = step > 0 ? Math.round(value / step) * step : value;
  return Math.round(v * 1000) / 1000;
}

export function snapRect(r: Rect, step: number): Rect {
  return { x: snap(r.x, step), y: snap(r.y, step), width: snap(r.width, step), height: snap(r.height, step) };
}

/**
 * The rectangle after dragging `handle` from `start` (the rect when the drag
 * began) by `dx`, `dy`. Edges not being dragged stay put; sizes never go
 * below MIN_SIZE (the dragged edge stops instead of flipping). Results are
 * snapped to `step`.
 */
export function dragRect(start: Rect, handle: Handle, dx: number, dy: number, step: number): Rect {
  if (handle === "move") {
    return { x: snap(start.x + dx, step), y: snap(start.y + dy, step), width: start.width, height: start.height };
  }
  let left = start.x;
  let top = start.y;
  let right = start.x + start.width;
  let bottom = start.y + start.height;
  const min = Math.max(MIN_SIZE, step);
  if (handle.indexOf("w") !== -1) left = Math.min(snap(left + dx, step), right - min);
  if (handle.indexOf("e") !== -1) right = Math.max(snap(right + dx, step), left + min);
  if (handle.indexOf("n") !== -1) top = Math.min(snap(top + dy, step), bottom - min);
  if (handle.indexOf("s") !== -1) bottom = Math.max(snap(bottom + dy, step), top + min);
  const r = (n: number) => Math.round(n * 1000) / 1000;
  return { x: r(left), y: r(top), width: r(right - left), height: r(bottom - top) };
}

/** Where a handle sits on the rectangle. */
export function handlePoint(r: Rect, handle: Handle): Pair {
  const x = handle.indexOf("w") !== -1 ? r.x : handle.indexOf("e") !== -1 ? r.x + r.width : r.x + r.width / 2;
  const y = handle.indexOf("n") !== -1 ? r.y : handle.indexOf("s") !== -1 ? r.y + r.height : r.y + r.height / 2;
  return [x, y];
}

/** A new area's first spot: just right of everything, top-aligned (matches render.default_spot). */
export function defaultSpot(bounds: Rect | null, width = 3, height = 3): Rect {
  if (!bounds) return { x: 0, y: 0, width, height };
  return {
    x: Math.round((bounds.x + bounds.width + 0.5) * 10) / 10,
    y: Math.round(bounds.y * 10) / 10,
    width,
    height,
  };
}

export function union(rects: Rect[]): Rect | null {
  if (!rects.length) return null;
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const r of rects) {
    x0 = Math.min(x0, r.x);
    y0 = Math.min(y0, r.y);
    x1 = Math.max(x1, r.x + r.width);
    y1 = Math.max(y1, r.y + r.height);
  }
  return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
}

export function intersectionArea(a: Rect, b: Rect): number {
  const w = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
  const h = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
  return w > 0 && h > 0 ? w * h : 0;
}

/** What the map shows: everything plus a 1 m margin, on whole metres. */
export function viewBounds(rects: Rect[]): Rect {
  const u = union(rects) || { x: 0, y: 0, width: 8, height: 6 };
  const x0 = Math.floor(u.x - 1);
  const y0 = Math.floor(u.y - 1);
  const x1 = Math.ceil(u.x + u.width + 1);
  const y1 = Math.ceil(u.y + u.height + 1);
  return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
}

/** Even-odd test: is the point inside the ring? */
export function pointInRing(x: number, y: number, ring: Pair[]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [ax, ay] = ring[i]!;
    const [bx, by] = ring[j]!;
    if (ay > y !== by > y && x < ((bx - ax) * (y - ay)) / (by - ay) + ax) inside = !inside;
  }
  return inside;
}

export function ringsPath(rings: Pair[][]): string {
  const f = (n: number) => n.toFixed(3);
  return rings
    .filter((r) => r.length >= 3)
    .map((r) => "M" + r.map((p) => `${f(p[0])} ${f(p[1])}`).join(" L") + " Z")
    .join(" ");
}

/** True when the shape is exactly its bounding box (so editing it as a rect loses nothing). */
export function isRectangle(polygons: Pair[][], rect: Rect): boolean {
  if (polygons.length !== 1 || polygons[0]!.length !== 4) return false;
  const near = (a: number, b: number) => Math.abs(a - b) < 0.002;
  return polygons[0]!.every(
    ([x, y]) => (near(x, rect.x) || near(x, rect.x + rect.width)) && (near(y, rect.y) || near(y, rect.y + rect.height)),
  );
}

/** Map a pointer position to map metres, for an SVG with preserveAspectRatio "xMidYMid meet". */
export function clientToMap(
  clientX: number,
  clientY: number,
  box: { left: number; top: number; width: number; height: number },
  view: Rect,
): Pair {
  const scale = Math.min(box.width / view.width, box.height / view.height) || 1;
  const offsetX = (box.width - view.width * scale) / 2;
  const offsetY = (box.height - view.height * scale) / 2;
  return [view.x + (clientX - box.left - offsetX) / scale, view.y + (clientY - box.top - offsetY) / scale];
}
