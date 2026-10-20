# Fused map document (v1)

Live: the document, `map_fusion/get`, `map_fusion/subscribe`, the write APIs and the `set_area`/`clear_area` services (phase 2). Not yet: `get_map`, `transform_point`, `locate_point`, the image entity (phase 4).

What cards and integrations get from Map Fusion. Everything here is a proposal. Change it freely until v1 ships, then bump `SCHEMA_VERSION` (`const.py`) on breaking changes.

## Conventions

- Units: **metres**. y points **down** (screen space, same as presence-map-card).
- Origin: fixed per floor (stored), not the bounds of the rooms. Coordinates can be negative.
- **Polygons are the geometry.** `polygons` is a list of rings, because one room can be several pieces (a closet strip, an area split by furniture). Each ring is a list of `[x, y]`: outer edge only (no holes in v1), clockwise on screen, not closed (the first point isn't repeated), simplified to about 5–7.5 cm. The largest piece comes first.
- **`rect` is always present**: the bounding box of all the pieces as `{x, y, width, height}`, the same fields as presence-map-card's `AreaConfig`. Rectangle-only consumers use it. It's also the area origin for things positioned relative to an area (presence-map-card sensors).
- **`geometry`** says where the shape came from: `pixels` (traced from the vacuum's room mask), `bbox` (vacuum only gave a bounding box, so polygon = rect), `manual`.
- Polygons from `pixels` never overlap. `bbox` ones may.
- Ids: `frame_id` and HA `area_id` are the keys. HA floors are optional: without them, each vacuum map is its own frame. Vendor segment ids only appear under `sources`.

## Shape

```jsonc
{
  "version": 1,
  "generated_at": "2026-10-20T21:30:00Z",
  // One frame per HA floor, or per vacuum map when its areas have no floor.
  "frames": [
    {
      "frame_id": "ground",              // floor id, or "<vacuum entity>:<map_id>" when there's no floor
      "floor_id": "ground",              // HA floor id, or null
      "name": "Ground floor",
      "bounds": { "x": 0, "y": 0, "width": 12.4, "height": 9.1 },
      "areas": [
        {
          "area_id": "kitchen",
          "name": "Kitchen",
          "polygons": [[[0.0, 0.0], [4.2, 0.0], [4.2, 1.9], [3.0, 1.9], [3.0, 3.1], [0.0, 3.1]]],
          "rect": { "x": 0.0, "y": 0.0, "width": 4.2, "height": 3.1 },
          "label_point": [1.5, 1.5],
          "area_m2": 11.6,
          "origin": "vacuum",              // vacuum | manual
          "geometry": "pixels",            // pixels | bbox | manual
          "sources": [
            { "source_id": "vacuum.downstairs", "map_id": "46", "segment_id": "1_2" }
          ]
        },
        {
          "area_id": "hallway",
          "name": "Hallway",
          "polygons": [[[4.2, 0.0], [5.4, 0.0], [5.4, 6.0], [4.2, 6.0]]],
          "rect": { "x": 4.2, "y": 0.0, "width": 1.2, "height": 6.0 },
          "label_point": [4.8, 3.0],
          "area_m2": 7.2,
          "origin": "manual",
          "geometry": "manual",
          "sources": []
        }
      ],
      // Vacuum rooms not linked to any HA area (link them in the vacuum's settings).
      "unmapped_rooms": [
        { "source_id": "vacuum.downstairs", "segment_id": "1_7", "name": "Room 7",
          "polygons": [[[8.0, 5.0], [10.0, 5.0], [10.0, 7.0], [8.0, 7.0]]],
          "rect": { "x": 8.0, "y": 5.0, "width": 2.0, "height": 2.0 } }
      ],
      // Only for bbox/manual geometry, which can overlap. Empty when all areas are traced from pixels.
      "overlaps": [],
      "sources": [
        {
          "source_id": "vacuum.downstairs", // vacuum entity id
          "kind": "dreame",
          "map_id": "46",
          "map_name": "Map 1",
          "role": "anchor",                 // anchor | aligned
          // source native coords (Dreame: vacuum mm, y up) → floor metres: [a, b, c, d, tx, ty]
          // x' = a*x + b*y + tx ; y' = c*x + d*y + ty
          "transform": [0.001, 0, 0, -0.001, 10.8, 3.75],
          "residual_m": 0.0,                // RMS error of the native↔frame fit (Dreame: pixel vs box fit)
          "warnings": []                    // e.g. "Map data camera is disabled, using room boxes"
        }
      ]
    }
  ],
  // HA areas with no shape in any frame yet. Editors prompt for these.
  "unplaced_areas": [{ "area_id": "garage", "name": "Garage", "floor_id": null }]
}
```

Why include `transform` per source: cards can turn a click on the fused map into vacuum coordinates (go-to, zone clean), and live data such as the robot's position can be drawn without Map Fusion re-sending the whole document.

## Read APIs

| Channel | Use | Notes |
|---|---|---|
| WS `map_fusion/get` | Cards: one-off fetch | Optional `frame_id` filter |
| WS `map_fusion/subscribe` | Cards: push on change | Sends the full doc, then a new one on each rebuild |
| Service `map_fusion.get_map` (`SupportsResponse.ONLY`) | Automations, scripts, other integrations | Same document |
| Service `map_fusion.transform_point` | Floor metres ↔ source native coords | For go-to / zone actions on a vacuum |
| Service `map_fusion.locate_point` | Floor metres → `area_id` | Point-in-polygon (with a ~10 cm tolerance for wall gaps), so every consumer agrees on "which room" |
| `image.map_fusion_<floor>` entity | Plain picture cards, Xiaomi vacuum map card | One per frame. Rendered PNG/SVG, `calibration_points` attribute in that card's format |

Entity attributes carry only small things (floor id, area count, version), never geometry.

## Write APIs (user placements)

All require an admin user. They change only `origin: "manual"` entries. Vacuum rooms are never edited, only overridden.

| Channel | Payload | Effect |
|---|---|---|
| WS `map_fusion/area/set` | `{area_id, frame_id?, rect: {x, y, width, height}}` or `{area_id, frame_id?, polygons: [[[x, y], …], …]}` | Create or replace the user placement (a rect is stored as one 4-point ring). Rebuild + push to subscribers. Returns the area as it appears in the document |
| WS `map_fusion/area/clear` | `{area_id, frame_id?}` | Remove the user placement. Falls back to the vacuum room, if any, else the area becomes unplaced. Returns `{frame_id}` |
| Service `map_fusion.set_area` | `area_id` (area selector), `frame_id?`, then `x, y, width, height` or `polygons` | Same as the websocket |
| Service `map_fusion.clear_area` | `area_id`, `frame_id?` | Same as the websocket |
| Options flow | Place an area (rectangle), remove a placement, choose a vacuum map's floor | For users without a card editor |

`frame_id` can be left out: the area's floor frame if the area has a floor, else the only frame. Otherwise the error is `frame_required`. A frame id can be any frame in the document or any HA floor id; a floor with no vacuum becomes a frame holding only placements, with origin (0, 0).

Validation: `width`, `height` > 0. Each ring needs ≥ 3 different points, some area, and must not cross itself (a repeated closing point is dropped). Rings are stored clockwise, largest first, rounded to mm. `area_id` must exist in the area registry. If the area has a floor and the frame belongs to a floor, they must match.

Websocket error codes: `invalid_format` (bad shape or request), `not_found` (area, frame or placement), `frame_required`, `floor_mismatch`, `unauthorized` (not an admin), `not_loaded`.

Placements are stored per frame. If a frame's id changes (its areas get a floor, or the user picks a floor in the options flow), its placements and origin move with it. Deleting an HA area deletes its placements.
