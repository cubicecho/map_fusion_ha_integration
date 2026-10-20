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

// -- Polygons -----------------------------------------------------------
//
// A polygon draft is one ring of points (no repeated closing point). Rings
// can wind either way; the server normalises them.

/** Fewest corners a polygon can have. */
export const MIN_POINTS = 3;

const mm = (n: number) => Math.round(n * 1000) / 1000 + 0;

/** A rectangle as a 4-point ring: top-left, top-right, bottom-right, bottom-left. */
export function rectRing(r: Rect): Pair[] {
  return [
    [r.x, r.y],
    [mm(r.x + r.width), r.y],
    [mm(r.x + r.width), mm(r.y + r.height)],
    [r.x, mm(r.y + r.height)],
  ];
}

export function ringBounds(ring: Pair[]): Rect {
  if (!ring.length) return { x: 0, y: 0, width: 0, height: 0 };
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const [x, y] of ring) {
    x0 = Math.min(x0, x);
    y0 = Math.min(y0, y);
    x1 = Math.max(x1, x);
    y1 = Math.max(y1, y);
  }
  return { x: x0, y: y0, width: mm(x1 - x0), height: mm(y1 - y0) };
}

/** Shoelace sum: positive when clockwise on screen (y down). */
export function signedArea(ring: Pair[]): number {
  let s = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    s += ring[j]![0] * ring[i]![1] - ring[i]![0] * ring[j]![1];
  }
  return s / 2;
}

export function ringArea(ring: Pair[]): number {
  return Math.abs(signedArea(ring));
}

/** Centre of mass of the ring (the bounding-box centre for a ring with no area). */
export function ringCentroid(ring: Pair[]): Pair {
  const a = signedArea(ring);
  if (Math.abs(a) < 1e-9) {
    const b = ringBounds(ring);
    return [b.x + b.width / 2, b.y + b.height / 2];
  }
  let cx = 0;
  let cy = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [x0, y0] = ring[j]!;
    const [x1, y1] = ring[i]!;
    const cross = x0 * y1 - x1 * y0;
    cx += (x0 + x1) * cross;
    cy += (y0 + y1) * cross;
  }
  return [cx / (6 * a), cy / (6 * a)];
}

/** The ring with the most area (what the one-ring editor edits). */
export function largestRing(polygons: Pair[][]): Pair[] | null {
  let best: Pair[] | null = null;
  for (const r of polygons) if (r.length >= 3 && (!best || ringArea(r) > ringArea(best))) best = r;
  return best;
}

/** Round to mm, drop repeated neighbours and a repeated closing point (as the server does). */
export function cleanRing(ring: Pair[]): Pair[] {
  const out: Pair[] = [];
  for (const p of ring) {
    const q: Pair = [mm(p[0]), mm(p[1])];
    const last = out[out.length - 1];
    if (!last || last[0] !== q[0] || last[1] !== q[1]) out.push(q);
  }
  while (out.length > 1 && out[0]![0] === out[out.length - 1]![0] && out[0]![1] === out[out.length - 1]![1]) out.pop();
  return out;
}

/** A new corner halfway along edge `edge` (from corner `edge` to the next). It lands at index edge + 1. */
export function insertVertex(ring: Pair[], edge: number): Pair[] {
  const a = ring[edge]!;
  const b = ring[(edge + 1) % ring.length]!;
  const out = ring.slice();
  out.splice(edge + 1, 0, [mm((a[0] + b[0]) / 2), mm((a[1] + b[1]) / 2)]);
  return out;
}

/** The ring without corner `index`; unchanged if that would leave fewer than MIN_POINTS. */
export function removeVertex(ring: Pair[], index: number): Pair[] {
  if (ring.length <= MIN_POINTS || index < 0 || index >= ring.length) return ring.slice();
  const out = ring.slice();
  out.splice(index, 1);
  return out;
}

export function setVertex(ring: Pair[], index: number, p: Pair): Pair[] {
  const out = ring.slice();
  out[index] = [mm(p[0]), mm(p[1])];
  return out;
}

/**
 * Move the whole ring by `dx`, `dy`. Like a rectangle move, the bounding
 * box's top-left corner snaps to `step`, so shapes drawn on the grid stay on it.
 */
export function translateRing(ring: Pair[], dx: number, dy: number, step: number): Pair[] {
  const b = ringBounds(ring);
  const sx = snap(b.x + dx, step) - b.x;
  const sy = snap(b.y + dy, step) - b.y;
  return ring.map((p): Pair => [mm(p[0] + sx), mm(p[1] + sy)]);
}

/**
 * Line a corner up with a neighbour: the one change (x to a neighbour's x,
 * or y to a neighbour's y) that moves it least, so that edge becomes
 * vertical or horizontal.
 */
export function lockToNeighbour(p: Pair, prev: Pair, next: Pair): Pair {
  const options: Pair[] = [
    [prev[0], p[1]],
    [next[0], p[1]],
    [p[0], prev[1]],
    [p[0], next[1]],
  ];
  let best = options[0]!;
  let bestD = Infinity;
  for (const o of options) {
    const d = Math.abs(o[0] - p[0]) + Math.abs(o[1] - p[1]);
    if (d < bestD) {
      best = o;
      bestD = d;
    }
  }
  return best;
}

/** Corner `index` dragged by `dx`, `dy` from where it started, snapped; `lock` lines it up with a neighbour. */
export function dragVertex(start: Pair[], index: number, dx: number, dy: number, step: number, lock = false): Pair[] {
  const p = start[index]!;
  let q: Pair = [snap(p[0] + dx, step), snap(p[1] + dy, step)];
  if (lock && start.length >= 3) {
    const n = start.length;
    q = lockToNeighbour(q, start[(index + n - 1) % n]!, start[(index + 1) % n]!);
  }
  return setVertex(start, index, q);
}

function orient(a: Pair, b: Pair, c: Pair): number {
  const v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  return Math.abs(v) < 1e-12 ? 0 : v > 0 ? 1 : -1;
}

function onSegment(a: Pair, b: Pair, p: Pair): boolean {
  return (
    Math.min(a[0], b[0]) <= p[0] &&
    p[0] <= Math.max(a[0], b[0]) &&
    Math.min(a[1], b[1]) <= p[1] &&
    p[1] <= Math.max(a[1], b[1])
  );
}

function segmentsTouch(a: Pair, b: Pair, c: Pair, d: Pair): boolean {
  const o1 = orient(a, b, c);
  const o2 = orient(a, b, d);
  const o3 = orient(c, d, a);
  const o4 = orient(c, d, b);
  if (o1 !== o2 && o3 !== o4) return true;
  return (
    (o1 === 0 && onSegment(a, b, c)) ||
    (o2 === 0 && onSegment(a, b, d)) ||
    (o3 === 0 && onSegment(c, d, a)) ||
    (o4 === 0 && onSegment(c, d, b))
  );
}

/** Neighbouring edges a→b, b→c that fold back over each other (a spike). */
function spike(a: Pair, b: Pair, c: Pair): boolean {
  if (orient(b, a, c) !== 0) return false;
  return (a[0] - b[0]) * (c[0] - b[0]) + (a[1] - b[1]) * (c[1] - b[1]) > 0;
}

/**
 * True if two edges that aren't neighbours touch or cross, or two
 * neighbours fold back over each other. Same rules as the server
 * (placements._self_intersects), so the panel can warn before saving.
 */
export function selfIntersects(ring: Pair[]): boolean {
  const n = ring.length;
  if (n < 3) return false;
  for (let i = 0; i < n; i++) {
    const a = ring[i]!;
    const b = ring[(i + 1) % n]!;
    if (spike(a, b, ring[(i + 2) % n]!)) return true;
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue; // the last edge neighbours the first
      if (segmentsTouch(a, b, ring[j]!, ring[(j + 1) % n]!)) return true;
    }
  }
  return false;
}

/** Why the server would refuse this ring, in words for the user, or null when it's fine. */
export function ringProblem(ring: Pair[]): string | null {
  const r = cleanRing(ring);
  if (r.length < MIN_POINTS) return "The shape needs at least 3 different corners.";
  if (selfIntersects(r)) return "The outline crosses itself. Move a corner so the edges don't cross.";
  if (ringArea(r) < 0.0001) return "The shape has no area.";
  return null;
}

/** Distance from p to the segment a–b. */
function segmentDistance(p: Pair, a: Pair, b: Pair): number {
  const vx = b[0] - a[0];
  const vy = b[1] - a[1];
  const len2 = vx * vx + vy * vy;
  let t = len2 ? ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / len2 : 0;
  t = Math.max(0, Math.min(1, t));
  const ex = p[0] - (a[0] + t * vx);
  const ey = p[1] - (a[1] + t * vy);
  return Math.sqrt(ex * ex + ey * ey);
}

/** Douglas–Peucker on an open polyline (keeps both ends). */
function simplifyLine(points: Pair[], tolerance: number): Pair[] {
  const keep: boolean[] = [];
  for (let i = 0; i < points.length; i++) keep.push(i === 0 || i === points.length - 1);
  const stack: Array<[number, number]> = [[0, points.length - 1]];
  while (stack.length) {
    const [first, last] = stack.pop()!;
    let index = -1;
    let worst = tolerance;
    for (let i = first + 1; i < last; i++) {
      const d = segmentDistance(points[i]!, points[first]!, points[last]!);
      if (d > worst) {
        worst = d;
        index = i;
      }
    }
    if (index !== -1) {
      keep[index] = true;
      stack.push([first, index], [index, last]);
    }
  }
  return points.filter((_, i) => keep[i]);
}

/**
 * Fewer corners, staying within `tolerance` metres of the outline
 * (Douglas–Peucker, split at the corner farthest from the first one).
 */
export function simplifyRing(ring: Pair[], tolerance: number): Pair[] {
  const n = ring.length;
  if (n <= 4 || tolerance <= 0) return ring.slice();
  let far = 0;
  let farD = -1;
  for (let i = 1; i < n; i++) {
    const dx = ring[i]![0] - ring[0]![0];
    const dy = ring[i]![1] - ring[0]![1];
    if (dx * dx + dy * dy > farD) {
      far = i;
      farD = dx * dx + dy * dy;
    }
  }
  const a = simplifyLine(ring.slice(0, far + 1), tolerance);
  const b = simplifyLine(ring.slice(far).concat([ring[0]!]), tolerance);
  return a.slice(0, -1).concat(b.slice(0, -1));
}

/**
 * A traced vacuum outline turned into something you can edit by hand: the
 * largest ring simplified to 10 cm (5 cm, then 2 cm if that made it cross
 * itself), on a 1 cm grid. Falls back to the bounding rectangle.
 */
export function editableOutline(polygons: Pair[][], rect: Rect): Pair[] {
  const ring = largestRing(polygons);
  if (ring) {
    for (const tolerance of [0.1, 0.05, 0.02]) {
      const r = cleanRing(simplifyRing(ring, tolerance).map((p): Pair => [snap(p[0], 0.01), snap(p[1], 0.01)]));
      if (!ringProblem(r)) return r;
    }
  }
  return rectRing(snapRect(rect, 0.01));
}

function edgeDistance(p: Pair, ring: Pair[]): number {
  let best = Infinity;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) best = Math.min(best, segmentDistance(p, ring[j]!, ring[i]!));
  return best;
}

/** Inside the ring and more than 1 mm from its edges. */
function strictlyInside(p: Pair, ring: Pair[]): boolean {
  return pointInRing(p[0], p[1], ring) && edgeDistance(p, ring) > 0.001;
}

/**
 * Do two rings overlap (not just touch)? Edges that properly cross, a corner
 * of one inside the other, or one's middle inside the other. Sharing a wall
 * doesn't count.
 */
export function ringsOverlap(a: Pair[], b: Pair[]): boolean {
  if (a.length < 3 || b.length < 3) return false;
  if (intersectionArea(ringBounds(a), ringBounds(b)) <= 0) return false;
  for (let i = 0, j = a.length - 1; i < a.length; j = i++) {
    for (let k = 0, l = b.length - 1; k < b.length; l = k++) {
      const p = a[j]!;
      const q = a[i]!;
      const r = b[l]!;
      const s = b[k]!;
      if (orient(p, q, r) * orient(p, q, s) < 0 && orient(r, s, p) * orient(r, s, q) < 0) return true;
    }
  }
  if (a.some((p) => strictlyInside(p, b)) || b.some((p) => strictlyInside(p, a))) return true;
  // Same corners (one drawn on top of the other): compare middles, when the
  // middle is inside its own ring (an L's centroid may not be).
  const ca = ringCentroid(a);
  const cb = ringCentroid(b);
  return (strictlyInside(ca, a) && strictlyInside(ca, b)) || (strictlyInside(cb, b) && strictlyInside(cb, a));
}
