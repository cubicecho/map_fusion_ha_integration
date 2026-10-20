/** The bits of Home Assistant and the fused map document the panel uses. */
import type { Pair, Rect } from "./geometry.js";

export interface HassConnection {
  subscribeMessage<T>(callback: (message: T) => void, message: Record<string, unknown>): Promise<() => void>;
}

export interface HassState {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown> & { friendly_name?: string; device_class?: string };
}

export interface Hass {
  connection: HassConnection;
  states?: Record<string, HassState>;
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

/** A door, window, … (see the server's features.py). */
export interface FusedFeature {
  feature_id: string;
  kind: string;
  name: string | null;
  points: Pair[];
  length_m: number;
  entity_id: string | null;
  areas: string[];
  areas_auto: boolean;
}

export interface FeatureKind {
  name: string;
  icon: string;
  geometry: string;
  entity_domains: Record<string, string[] | null>;
  max_areas: number;
}

export interface FusedFrame {
  frame_id: string;
  floor_id: string | null;
  name: string;
  bounds: Rect | null;
  areas: FusedArea[];
  unmapped_rooms: FusedRoom[];
  /** Missing from Map Fusion versions before 0.5. */
  features?: FusedFeature[];
}

export interface FusedDoc {
  version: number;
  variant?: string;
  frames: FusedFrame[];
  unplaced_areas: Array<{ area_id: string; name: string; floor_id: string | null }>;
  feature_kinds?: Record<string, FeatureKind>;
}
