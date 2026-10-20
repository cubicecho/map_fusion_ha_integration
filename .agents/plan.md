# Plan: Map Fusion MVP

## Goal

1. **Get maps** from robot vacuums. First source: **Dreame** (Tasshack/dreame-vacuum).
2. **Tie them to HA areas**, so every room on the map is an `area_id`.
3. **Serve one fused map** that is more correct than any single vacuum's, for other cards and integrations to use. First consumer: **presence-map-card**.
4. **Let users place areas by hand** when no vacuum room covers them (a hallway the robot can't reach, an upstairs with no robot, the garage, …).

"More correct" means, concretely:

- One coordinate frame per HA floor (or per vacuum map when there are no floors), in metres, instead of N vendor frames.
- Rooms named and identified by HA areas, not vendor segment ids.
- Real room outlines that don't overlap, so "which area is this point in" has one answer.
- Every area in a frame has a place, either from a vacuum or set by the user.
- Later, where two vacuums see the same room, their outlines are combined and disagreements are visible (`confidence`, `residual_m`).

See [research.md](research.md) for what exists and [fused-map-schema.md](fused-map-schema.md) for the output.

## Decisions

| Question | Decision | When |
|---|---|---|
| First vacuum source | Dreame (Tasshack/dreame-vacuum). It already implements `CLEAN_AREA` | 2026-10-20 |
| Minimum HA | 2026.3 (core vacuum area mapping) | 2026-10-20 |
| Geometry | **Polygons from the start** (was: rectangles first). A room can be several polygons (`polygons`, a list). Each area also carries its bounding `rect`, so rectangle-only consumers keep working | 2026-10-20 |
| Polygon source | Dreame's `map_data` camera: Valetudo-format JSON with per-room pixels. Room bounding boxes from the `map` camera are the fallback | 2026-10-20 |
| Dependencies | None. Pixel → outline tracing, simplifying and point-in-polygon are small pure-Python functions | 2026-10-20 |
| Schema style | Plain JSON (not GeoJSON). `rect` fields match presence-map-card's `AreaConfig` | 2026-10-20 |
| Who owns area geometry | **Map Fusion.** Cards read it; presence-map-card keeps only sensors and display options | 2026-10-20 |

### Why polygons now

Dreame's `rooms` attribute only gives bounding boxes, and real rooms aren't rectangles. In the D10 Plus fixture (floor metres, y down):

| Room | x | y | width | height |
|---|---|---|---|---|
| Bathroom | 0.00 | 0.00 | 1.40 | 1.50 |
| Hallway | 1.30 | 0.50 | 2.50 | 1.35 |
| Kitchen | 3.80 | 0.50 | 4.15 | 2.10 |
| Master Bedroom | 2.25 | 1.80 | 5.45 | 4.25 |
| Office | 7.00 | 2.60 | 4.45 | 3.65 |

The boxes overlap: Kitchen/Master Bedroom by 3.1 m², Master Bedroom/Office by 2.4 m², plus two slivers. For presence-map-card that means a target can be in two areas at once. Room pixel masks never share a pixel, so polygons traced from them can't overlap. That removes the need for overlap rules and trimming, and the cost is one parser that Valetudo support will reuse.

## Architecture

```
 dreame_vacuum                                         later: valetudo (same parser), xiaomi extractor
   camera.<name>_map_data  (PNG + ValetudoMap JSON)  ── polygons
   camera.<name>_map       (`rooms` attr, bounding boxes) ── fallback, label points
   vacuum.<name>           (segments, area mapping)
            │
            ▼
 ┌──────────────────────────┐
 │ sources/dreame.py        │  find entities, fetch map, hand JSON to the parser
 │ sources/valetudo_map.py  │  ValetudoMap JSON → per-segment pixel masks
 └──────────┬───────────────┘
            ▼
 ┌──────────────────────────┐
 │ geometry.py              │  mask → outline → simplified polygon; bbox; area; point-in-polygon
 └──────────┬───────────────┘
            ▼
 ┌──────────────────────────┐   HA area/floor registries
 │ areas.py                 │◄─ core mapping: entity registry options["vacuum"]["area_mapping"]
 └──────────┬───────────────┘
            ▼
 ┌──────────────────────────┐
 │ align.py                 │  per floor: anchor frame (→ metres, y down, fixed origin)
 └──────────┬───────────────┘     later: fit extra sources to the anchor
            ▼
 ┌──────────────────────────┐   store.py (.storage/map_fusion)
 │ merge.py                 │◄─ user placements, frame origins, floor choices
 └──────────┬───────────────┘
            ▼
 coordinator.py ──► websocket.py (read + write) / services.py / image.py
```

Planned files under `custom_components/map_fusion/`:

| File | Job |
|---|---|
| `model.py` | Dataclasses: `Rect`, `Polygon`, `SourceMap`, `SourceRoom`, `Transform`, `FusedMap`, `FusedFloor`, `FusedArea`. Pure, no HA imports |
| `geometry.py` | Pure functions: trace mask outline, Douglas–Peucker simplify, bbox, area, centroid, point-in-polygon, apply `Transform` |
| `sources/base.py` | `MapSource` protocol: `kind`, `async_discover(hass)`, `async_read(hass, entity_id) -> list[SourceMap]` |
| `sources/valetudo_map.py` | Parse ValetudoMap JSON (`layers`, `pixelSize`, `compressedPixels`, `segmentId`). Shared by Dreame and Valetudo |
| `sources/dreame.py` | Dreame adapter (below) |
| `areas.py` | Read area/floor registries and the core segment→area mapping |
| `align.py` | Source frame → floor frame. MVP: unit scale + y flip + fixed offset. Later: fit from shared areas |
| `merge.py` | Build each frame's areas from source rooms + user placements |
| `store.py` | `homeassistant.helpers.storage.Store` for user placements and frame origins |
| `coordinator.py` | Listens to source entity and registry changes, rebuilds (debounced), notifies subscribers |
| `websocket.py`, `services.py` | Read and write APIs (see schema doc) |
| `image.py` | Per-floor rendered map (phase 4) |

## Dreame source

What the integration gives us (verified in source `f5b8472`, 2026-10-11, and a D10 Plus dump, fw 1316, 2026-10-20):

- **Segments** (core API): `id = "<map_index>_<segment_id>"`, `name`, `group = <map name>`. Visible segments only. Every saved map. The D10 Plus has one map (`map_index: 1`), so its ids are `"1_1"`…`"1_5"`.
- **Area mapping**: whatever the user set in the vacuum's "Map areas" dialog, read from `entity_registry.async_get(entity_id).options["vacuum"]["area_mapping"]`, shaped `{area_id: [segment_id, ...]}`.
- **Room polygons**: `camera.<name>_map_data` (entity key `map_data`, **disabled by default**, entity category config). Its image is a PNG with a zipped text chunk named `ValetudoMap` holding the JSON:
  - `pixelSize` (cm; Dreame's 50 mm grid → 5)
  - `layers[]`: `type` `floor` | `wall` | `segment`. Each has `compressedPixels` = run-length triples `[xStart, y, count, …]`, and a segment has `metaData.segmentId`, `name`, `active`.
  - `entities[]`: `robot_position`, `charger_location`, `no_go_area`, `virtual_wall`, `path`, …
  - Coordinates: `x = (mm_x + 32768) / 10`, `y = MAX − (mm_y + 32768) / 10`, i.e. **cm, y down**, with `MAX = size.y` (6554).
  - **Confirmed on the D10 Plus file (`tests/fixtures/camera.json`, 2026-10-20):** layer pixels are **grid cells** (× `pixelSize` 5 → cm). Entity points (`robot_position`, `charger_location`, `path`) are already **cm**. Each room's cell bbox has exactly the same size as its `rooms` attribute box, offset by a constant (+18 mm x, +78 mm y; rounding in Dreame's conversion). **No cell belongs to two rooms.**
  - Room names in the JSON can differ from the attributes (`Primary Bedroom` vs `Master Bedroom`, `Corridor` vs `Hallway`): localisation. **Match on `segmentId` only**; names come from HA areas.
- **Alternative room pixels (no entity to enable)**: `GET /api/camera_map_data_proxy/camera.<name>_map` returns gzipped JSON in Dreame's own `MapRendererData` format: `data: {pixel_type: [x, y, x, y, …]}`, where room pixel types are segment ids, plus `size`, `segments`, `map_index`, `frame_id`. In-process this means calling the camera entity's `map_data_string()` directly, which ties us to Dreame internals. **Plan: A (`map_data` camera + ValetudoMap) is primary, B (this) is the fallback, bounding boxes are the last resort.**
- **Room bounding boxes**: `camera.<name>_map` attribute `rooms` = `{segment_id: {x0, y0, x1, y1, x, y, name, …}}` in **mm, y up** (confirmed: calibration maps vacuum y +1000 → image y −80 px). `x, y` is the room's label point. These are the fallback when `map_data` is off, and a cross-check in tests: each polygon's bbox should match its room's `x0..y1`.
- `calibration_points` on the `map` camera (vacuum mm ↔ image px), for the image output later.

The vacuum entity's own `rooms` attribute has names and ids only, no coordinates.

Adapter steps:

1. Find Dreame vacuum entities (platform `dreame_vacuum`) and their `map` / `map_data` cameras (same device).
2. If `map_data` is enabled: `camera.async_get_image()` → read the `ValetudoMap` text chunk (stdlib `zlib` + PNG chunk walk, no Pillow needed) → `valetudo_map.parse()` → per-segment masks → `geometry` → polygons.
3. If not: use the `rooms` bounding boxes, mark those areas `geometry: "bbox"`, and raise a repair issue suggesting the user enable the Map data entity.
4. Match each room to an area through `area_mapping` (reverse lookup segment → area). Rooms with no area go to `unmapped_rooms`.

Refresh: the `map_data` image only needs re-reading when the map changes, not on every robot move. Trigger on the `map` camera's `frame_id` / `saved_map_id` changing, debounced (e.g. 30 s), not on every state update.

## Polygon pipeline (`geometry.py`)

1. **Mask** from runs: a set of `(x, y)` cells per segment.
2. **Clean up**: a morphological close of 1–2 cells (fill single-cell gaps and specks from furniture legs) before tracing.
3. **Outline**: walk the cell-edge boundary (each cell edge with an empty neighbour on the other side), chain the edges into rings. Clockwise rings are outer edges, anticlockwise are holes. Handle pinch points (two cells touching only at a corner) explicitly.
4. **Keep**: every outer ring ≥ 0.25 m², and no holes in v1 (the biggest real hole is 0.16 m²).
5. **Simplify** each ring with Douglas–Peucker at ~5–7.5 cm, then merge collinear points.
6. **Rooms can be several pieces.** The D10 Plus Primary Bedroom is three: 9.5, 1.3 and 0.7 m². So each area's geometry is a list of polygons, not one.

Prototype numbers on the real map (5 cm tolerance, no close step yet): Office 552 → 99 points, Primary Bedroom 532 → 73, Kitchen 284 → 29, Corridor 162 → 20, Bathroom 134 → 20. With the close step and 7.5 cm it should drop to tens. The prototype is a throwaway script, not project code.

Neighbouring rooms are separated by wall/door pixels, so polygons leave thin gaps. Fine for display. For point lookup, the nearest polygon within ~10 cm counts as inside.

All of this is tested on fixtures, with no HA in the loop.

## Frames and floors

- **One frame per HA floor, or per vacuum map when its areas have no floor.** The anchor source is the Dreame map whose areas are in that frame.
- **Map → floor**: majority floor of the map's mapped areas. On a tie, ask in the options flow and store the choice in `store.py`.
- **No floors is the normal case, not an error** (the first user has none). A vacuum map whose areas have no floor becomes its own frame with `floor_id: null`, `frame_id: "<vacuum entity>:<map_id>"`, named after the map ("Map 1"). Cards select frames by `frame_id`; `floor_id` is extra info when present. User-placed areas with no floor go in the frame the user picks (default: the only one, if there's just one). If areas are later assigned to floors, frames migrate to the floor and keep their stored origin.
- **Frame origin is fixed once** (stored), not recomputed from the room bounds on every rebuild. Otherwise a vacuum re-mapping a room would shift every hand-placed area on the floor.
- **Dreame anchor frame = the `map_data` JSON frame**: `metres = cells × pixelSize / 100`, already y down, then the stored origin offset. No flip needed.
- **Vacuum mm ↔ floor metres** (for `transform_point` and for the bbox fallback): fit from the room cell bboxes against the `rooms` attribute boxes. Both are available, the sizes match exactly, and the offset is constant, so the fit doubles as a self-check (`residual_m` should be ~0). Shape: scale 0.001, y flipped.
- Areas on floors with no vacuum at all get a frame with origin 0,0 and only user placements.

## User-placed areas

An area gets a **user placement** (a polygon in floor metres) when:

- no vacuum room is mapped to it (the main case), or
- the user wants to override a vacuum room (allowed, flagged `origin: "manual"`).

Placements can be given as a `rect` (stored as a 4-point polygon) or a full `polygon`. Editors can start with rectangles and add point editing later.

Every HA area with no placement at all is listed in the floor's `unplaced_areas`, so editors can prompt for it.

Placements are stored by Map Fusion (`.storage/map_fusion`), keyed by `frame_id` + `area_id`, in that frame's coordinates. Ways to set them, in order of build:

1. **Websocket** `map_fusion/area/set` and `map_fusion/area/clear`. Admin only. This is what card editors use.
2. **Service** `map_fusion.set_area` / `map_fusion.clear_area`, for scripts and YAML users.
3. **Options flow**: pick floor → area → x, y, width, height. A no-frontend fallback, rectangles only.
4. **Drawing in a card**: presence-map-card's editor (drag a box on the fused map, later drag polygon points) or a small map-fusion card (later, not in the MVP).

## presence-map-card integration

Today the card's `AreaConfig` holds `area`, `x`, `y`, `width`, `height` (metres, y down) plus `sensors`. Plan:

- New card option `map_fusion: true` (or `map_fusion: { frame: <frame_id> }` when there's more than one frame). When set, the card subscribes to `map_fusion/subscribe`, draws each area's `polygons`, and uses its `rect` origin as the area origin for sensors.
- Card `areas[]` entries keep `area` + `sensors`. Their `x/y/width/height` become optional. Used only when Map Fusion has nothing for that area, or isn't installed.
- **Sensor origin**: today sensors are offset from the area box's top-left. With polygons, the area origin stays the bbox top-left (`rect.x, rect.y`), so sensor math is unchanged. If a vacuum re-maps a room and its bbox moves, the sensors move with it. That's usually what you want.
- `hide_outside_area` gets better for free: point-in-polygon instead of point-in-box.
- Editor: areas from the fused map show as read-only shapes. An unplaced area gets a "place on map" action that calls `map_fusion/area/set`.
- **Migration**: a one-off "push my card rectangles to Map Fusion" button. Caveat: the card's rectangles are in its own made-up frame, not the vacuum's. The import should ask for (or let the user drag) one offset to line them up with the vacuum rooms.

These changes live in the presence-map-card repo. This repo only provides the API.

## Phases

0. **Scaffold** ✅ — manifest, no-field config flow, test harness, these docs, D10 Plus attribute fixtures.
1. **Dreame polygons, read-only** ✅ (2026-10-20). `model.py`, `geometry.py`, `sources/valetudo_map.py`, `sources/dreame.py` (pixels, bbox fallback, repair issue when Map data is off), `merge.py`, `coordinator.py`, WS `map_fusion/get` + `map_fusion/subscribe`, frame origins stored. 42 tests (synthetic map in CI, real D10 Plus map locally). Differences from the plan:
   - No `align.py` or `areas.py` yet: with one vacuum per frame, frame assignment and origins live in `merge.py`, and area links are read in `coordinator.py`. `align.py` arrives with the second source (phase 5).
   - No `sources/base.py` protocol yet: one source doesn't need it. Add it with the second source.
   - `unplaced_areas` is top-level, not per frame (areas without floors have no natural frame).
   - Map images are re-read only when the room layout changes (`saved_map_id`, `map_index`, room boxes), on startup, when entities change, and every 6 h. Robot moves cost only a cheap signature check.
   - Real Dreame result: all 5 rooms traced, 14–77 points, no overlaps, pixel↔box fit residual ~0.
   - HA 2026.10 validates websocket schemas with `probatio`; 2026.3 has `voluptuous`. `websocket.py` imports whichever exists.
2. **User placements** ✅ (2026-10-20). `placements.py` (validate and tidy rings), placements and map → floor choices stored next to the frame origins, WS `map_fusion/area/set|clear` (admin), services `map_fusion.set_area|clear_area`, options flow (place a rectangle, remove a placement, choose a map's floor). 87 tests. Differences from the plan:
   - No `store.py`: the store stays in `coordinator.py` (one `Store`, keys `frames`, `placements`, `floor_choices`).
   - `frame_id` is optional on set/clear. Without it: the area's floor if it has one, else the only frame. Errors: `invalid_format`, `not_found`, `frame_required`, `floor_mismatch`.
   - A placement can go in any built frame or any HA floor. A floor with placements but no vacuum becomes a placements-only frame (origin 0, 0).
   - Placements in a frame whose vacuum is missing right now are kept but not shown, so a vacuum that's offline at startup doesn't lose them.
   - When a frame id changes (floor assigned or chosen), its origin and placements move to the new id.
   - Deleting an HA area deletes its placements.
   - Overlaps between a manual shape and other areas are checked on bounding boxes, not polygons (good enough to flag; exact polygon clipping later if needed).
   - The options flow only does rectangles. Polygons go through the websocket or the service.
3. **presence-map-card reads Map Fusion** ✅ (2026-10-20, presence-map-card v0.4.0, branch `map-fusion` in that repo). Card option `map_fusion: true | { frame, all_areas }`; the card subscribes to `map_fusion/subscribe`, draws outlines (unlinked vacuum rooms dashed), keeps sensors relative to `rect`'s top-left, and tests "inside the area" against the outline with 10 cm slack. Editor: Map Fusion toggle, frame picker, "Place on Map Fusion map" (admins; calls `map_fusion/area/set` with the card's box). Differences from the plan:
   - All Map Fusion areas in the frame are drawn by default (`all_areas: false` limits it to the card's list). Card `areas[]` add sensors and labels.
   - Card boxes are used only for areas Map Fusion hasn't placed, and only when the user gave x/y/width/height. Otherwise the card lists them as "Not on the map yet".
   - No separate migration button: "Place on Map Fusion map" per area does the same job, and the live preview shows the card box against the vacuum rooms so it can be lined up first. Vacuum shapes can't be replaced from the card editor (only manual ones updated).
   - The card refuses fused documents with a `version` it doesn't know (`SUPPORTED_VERSION` in `src/mapfusion.ts`).
4. **More outputs** ✅ (2026-10-20). Response-only services `get_map`, `transform_point`, `locate_point` (`queries.py`), and one SVG `image` entity per frame with `calibration_points` (`render.py`, `image.py`). 102 tests. Differences from the plan:
   - SVG, not PNG: no Pillow dependency, and browsers show SVG in picture cards. Cards that need a raster image would need a PNG option later.
   - `locate_point` also takes a vacuum's native coordinates (`source_id`), so "which room is the robot in" is one call.
   - Image entities are keyed by frame id. A frame that moves to a floor gets a new entity, and the old one goes unavailable (remove it from the entity settings).
   - Real D10 Plus check: the image matches the vacuum map, and the charger position (vacuum mm) lands inside the Office.
5. **Second source + alignment** ✅ (2026-10-20, Valetudo; Xiaomi still to do). `sources/base.py` (adapter contract), `sources/valetudo.py`, `align.py`, merge groups (one anchor + aligned maps per frame). 118 tests. Differences from the plan:
   - Rigid fit (rotation + shift), not similarity: every adapter already gives metres, so scale is fixed at 1. 2 shared areas give an exact fit; 3+ a least-squares fit, where a mirrored fit is also tried and only wins when clearly better. Residual over 0.75 m → no alignment.
   - The anchor is the map that anchored the frame before (from stored origins), else the one with the most linked areas. So adding a vacuum never moves an existing frame.
   - Shared areas keep the anchor's shape; the other map adds `sources` entries and `confidence` (IoU of the two shapes). Areas only the aligned map has are added from it.
   - Floor-less maps are aligned too (the first user has no floors).
   - Overlaps are now measured on the shapes (5 cm grid), not bounding boxes, and pairs from different vacuums are checked.
   - Valetudo has no room boxes, so there's no bbox fallback; its map is re-read every 10 minutes because HA sees no state change when the map image updates.
   - Not tested on a real Valetudo robot (only synthetic data). Entity unique ids were taken from Valetudo's source.
   - Xiaomi Cloud Map Extractor (bbox only) moves to its own step.
5b. **Filled shapes** ✅ (2026-10-20, v0.2.0). A second shape per room with furniture gaps filled (`geometry.fill_gaps`, row/column gaps + corner pockets up to a size limit, default 2 m, set in the options). Served through a `variant` on the read APIs, a second image entity per frame, and presence-map-card's `map_fusion.variant: filled`. On the D10 Plus, the Master Bedroom goes from 13.3 to 18.9 m² and from 77 to 27 outline points; rooms keep their boxes and don't overlap.
5c. **Map preview while placing areas** ✅ (2026-10-20, v0.3.0). The options flow's *Place an area* steps show the map (1 m grid with coordinates, other rooms, the area's current shape dashed, the proposed rectangle in orange) and end on a preview with Save / Adjust. Flow descriptions are markdown and HA's frontend allows `<img>` with relative URLs (checked in `src/resources/markdown-worker.ts`), so `preview.py` serves the SVG at `/api/map_fusion/preview/<id>` behind a signed URL (`async_sign_path`, 1 h). New areas default to a 3 × 3 m spot just right of the map. Not yet checked in a real browser dialog.
5d. **Sidebar page for placing areas** ✅ (2026-10-20, v0.4.0). Options flows can't run code, so live updates and dragging live in an admin-only sidebar panel (`panel.py` + `frontend/`). Drag to move, 8 handles to resize, fields update live both ways, snap 1 cm–50 cm, arrow keys, live overlap warning, Save/Remove over the websocket write APIs, traced/filled toggle, floors without a vacuum map listed. Checked in headless Chrome with a real mouse drag (DevTools protocol). `frontend` / `panel_custom` are `after_dependencies`, and the page is skipped when the frontend isn't loaded (tests).
6. **Extras.** Walls/doors layer in the output, polygon point editing, a repair issue when a source's rooms change.

## Open questions

- ~~Attribute dump~~: received 2026-10-20, saved as `tests/fixtures/dreame_d10_plus_{camera,vacuum}.json` (access token removed).
- ~~`map_data` fixture~~: received 2026-10-20 as `tests/fixtures/camera.json` (it's a PNG despite the name; git-ignored, keep local). Tests should look for it by that path, then `*map_data*.png`, and skip if neither exists.
- **Real map-data fixtures stay local** (the user's floor plan): `tests/fixtures/*map_data*` is git-ignored. Tests that use them `pytest.skip` when they're missing. CI runs on a small synthetic map (a few hand-made rooms, including an L-shape and a hole) committed under `tests/fixtures/synthetic_*`.
- `tests/fixtures/dreame_d10_plus_map_data.png` (2026-10-20) is the **rendered** map (1036×620, icons and cleaning path, no `ValetudoMap` text chunk), so it came from the `map` camera, not `map_data`. It's useful as a visual reference. Rooms: 1 Bathroom, 5 Hallway, 2 Kitchen, 3 Master Bedroom (very irregular, with a notch and holes), 4 Office.
- Optional: a sample of fallback B (`/api/camera_map_data_proxy/camera.d10_plus_map`, gzipped JSON) to test that path too. Not needed for phase 1.
- ~~Area mapping~~: yes, the D10 Plus's "Map areas" dialog is filled in (2026-10-20), so `area_mapping` is the real source of links.
- ~~Floors~~: the user's areas are **not** assigned to HA floors (2026-10-20). So floors must be optional, not a prerequisite (see "Frames and floors").
- Should the user be able to rotate a whole floor frame (so "up" on the map is north, or matches how you think of the house)? Cheap to add as one stored angle per floor.
