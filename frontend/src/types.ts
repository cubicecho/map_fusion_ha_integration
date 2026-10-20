/** The bits of Home Assistant and the fused map document the panel uses. */
import type { Pair, Rect } from "./geometry.js";

export interface HassConnection {
  subscribeMessage<T>(callback: (message: T) => void, message: Record<string, unknown>): Promise<() => void>;
}

export interface Hass {
  connection: HassConnection;
  callWS<T>(message: Record<string, unknown>): Promise<T>;
  floors?: Record<string, { floor_id: string; name: string }>;
  areas?: Record<string, { area_id: string; name: string; floor_id?: string | null }>;
  user?: { is_admin?: boolean } | null;
}

export interface FusedArea {
  area_id: string;
  name: string;
  polygons: Pair[][];
  rect: Rect;
  label_point: Pair;
  origin: "vacuum" | "manual";
  geometry: "pixels" | "bbox" | "manual";
  sources: Array<{ source_id: string; segment_id?: string }>;
}

export interface FusedRoom {
  segment_id: string;
  name?: string | null;
  polygons: Pair[][];
  rect: Rect;
}

export interface FusedFrame {
  frame_id: string;
  floor_id: string | null;
  name: string;
  bounds: Rect | null;
  areas: FusedArea[];
  unmapped_rooms: FusedRoom[];
}

export interface FusedDoc {
  version: number;
  variant?: string;
  frames: FusedFrame[];
  unplaced_areas: Array<{ area_id: string; name: string; floor_id: string | null }>;
}
