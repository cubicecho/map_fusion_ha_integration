# Research: what already exists

Collected 2026-10-19. Re-check anything marked **verify** before building on it.

## Summary

- **No spec exists** for a shared floor/room geometry in Home Assistant. Core areas and floors carry no geometry. A polygon-zone proposal was declined in Jan 2026, and "logical floor plan" is still a feature request.
- **HA core already maps vacuum segments to areas (2026.3+).** This covers most of our "tie into areas" step.
- **Vendor map data is fragmented.** Every integration exposes rooms differently, in its own units and axes. That is the gap this project fills.

## HA core: vacuum segments → areas (2026.3)

Sources: [architecture discussion #1284](https://github.com/home-assistant/architecture/discussions/1284), [vacuum entity dev docs](https://contributors.home-assistant.io/core/entities/vacuum/), [`vacuum.clean_area` action](https://www.home-assistant.io/actions/vacuum.clean_area/).

- `VacuumEntityFeature.CLEAN_AREA`. Integrations implement `async_get_segments()` → `list[Segment(id, name, group)]` and `async_clean_segments(segment_ids, **kwargs)`.
- `Segment.id` is unique per entity. `group` groups segments in the mapping dialog (per floor or map). Multi-floor robots are expected to namespace ids, e.g. `floor2_room3`.
- **The user's area → segments mapping is in the vacuum's entity registry options** (verified in core `vacuum/services.py`, 2026-10-20): `registry_entry.options["vacuum"]["area_mapping"]`, shaped `{area_id: [segment_id, ...]}`. `options["vacuum"]["last_seen_segments"]` holds the segment list as of the last save. `Segment` is `@dataclass(id: str, name: str, group: str | None = None)`. `CLEAN_AREA = 16384`.
- `last_seen_segments` and `async_create_segments_issue()` raise a repair when the robot's segments change.
- Websocket `vacuum/get_segments` lists segments for the frontend.
- **Geometry was deliberately left out.** A reviewer said a future floor-plan feature could add polygons on top of `Segment`. Our fused map is effectively that feature, done outside core.
- The `MAP` feature flag is info only. Core has no map method.

**What this means for us:** for any vacuum with `CLEAN_AREA` we get segment ↔ area links for free and stay in sync with what the user set in the HA UI. Segments that two vacuums both map to the same area also give us **matching points for aligning their maps** (see plan.md).

## Vendor sources

| Source | How rooms are exposed | Geometry quality | Notes |
|---|---|---|---|
| **Tasshack/dreame-vacuum** (HACS) | Camera entity attribute `rooms`: `{segment_id: {x0, y0, x1, y1, room_id, name, …}}` for that camera's map. `calibration_points` attribute. Vacuum entity `rooms` keyed by map name. Vacuum has `current_segment`. | Bounding boxes. Native units almost certainly mm (`x0 = left + cell * grid_size`, grid_size 50). Full outlines need the map data itself. | **Implements `CLEAN_AREA`** (verified, `f5b8472`, 2026-10-11). Segment id `"<map_index>_<segment_id>"`, `group` = map name, all saved maps, visible segments only. |
| **Xiaomi Cloud Map Extractor** (HACS, PiotrMachowski) | Camera entity, attributes opt-in via config: `rooms`, `walls`, `zones`, `calibration_points`, … | Room bounding boxes. Walls as segments. | Covers Xiaomi, Roborock, Viomi, Roidmi, Dreame. Built on `vacuum-map-parser-*`. |
| **Roborock** (core) | `image` entity per map. Room geometry not clearly exposed as attributes (**verify**). Supports `CLEAN_AREA`. | Unknown without reading core source. | Uses `vacuum-map-parser-roborock` internally. |
| **Valetudo** (MQTT, rooted robots). Same JSON format as Dreame's `map_data` camera | ValetudoMap JSON over MQTT / REST: layers (floor, wall, segment) as RLE pixel runs, `pixelSize`, entities (path, charger, virtual walls). Units cm, origin top-left. | Best: per-room pixel masks → real polygons. | Documented format: [core concepts](https://valetudo.cloud/pages/development/valetudo-core-concepts/). |
| **Manual** | User draws/enters rectangles (like presence-map-card config today). | Whatever the user enters. | Needed for areas no vacuum reaches. |

### Common parser model: `vacuum-map-parser-base`

[PiotrMachowski/Python-package-vacuum-map-parser-base](https://github.com/PiotrMachowski/Python-package-vacuum-map-parser-base). Vendor packages: `-roborock`, `-dreame`, `-viomi`, `-roidmi` (+ forks `-ijai`, `-xiaomi`).

- `MapData.rooms: dict[int, Room]`. `Room(Zone)` has `x0,y0,x1,y1`, `number`, `name`, `pos_x,pos_y`.
- Also `walls`, `no_go_areas` (4-corner `Area`), `charger`, `vacuum_position`, `path`, `obstacles`, `image: ImageData`.
- `calibration()` returns 3 `{vacuum:{x,y}, map:{x,y}}` pairs (vacuum coords ↔ image pixels). `to_img` flips y.
- Units are vendor-native (not stated in the base). Normalize per vendor.

This is the closest thing to a common room model. Our `SourceMap` should be able to take one of these directly.

### Calibration convention used by map cards

[lovelace-xiaomi-vacuum-map-card](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card) `calibration_source`: `camera` / `entity`+`attribute` / `calibration_points` (3–4 `{vacuum:{x,y}, map:{x,y}}` pairs) / `identity`. It is the de-facto format for "vacuum coords ↔ image pixels". We should **emit** calibration points in this format for each fused-map image, so that card can draw on our image without changes.

## Floor-plan cards (possible consumers)

- [presence-map-card](../presence-map-card) (ours): areas as metre rectangles, y down. First consumer.
- [Easy Floorplan](https://github.com/Gifford47/easy-floorplan): room polygons linked to HA areas.
- [ha-floorplan](https://github.com/ExperienceLovelace/ha-floorplan): SVG with entity-id'd shapes.
- Xiaomi vacuum map card: image + calibration points.

None of these share a geometry format. A small, documented, versioned JSON from us is the useful contribution.

## Gaps to verify before phase 1

Status as of 2026-10-20.

1. ~~Options key for the area mapping~~: done (see above). Reading another domain's registry options is not a public API, so wrap it in one function in `areas.py` and test it.
2. Dreame: ~~`CLEAN_AREA` support~~ (yes). ~~Units and y direction~~: mm, y up (D10 Plus dump, fw 1316, 2026-10-20). Room boxes are bounding boxes and overlap.
3. **Dreame polygons exist.** The `map_data` camera (disabled by default) serves a PNG with a zipped `ValetudoMap` text chunk: Valetudo v2 JSON with `floor`/`wall`/`segment` layers as run-length `compressedPixels`, plus `metaData.segmentId`. Coords `x=(mm+32768)/10`, `y=MAX-(mm+32768)/10` (cm, y down). Source: `dreame/map.py` `DreameVacuumMapDataJsonRenderer`. Confirmed on a real D10 Plus file: layer pixels are grid cells (× `pixelSize` 5 → cm), entity points are cm, rooms never share a cell, and a room can be several disconnected pieces.
3. What the core Roborock integration exposes beyond the image (room coords?).
4. Units per vendor: Valetudo is cm (documented). Dreame and Roborock native units are unknown (**verify** from the parser packages).
