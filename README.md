# Map Fusion

> **Early development (v0.4).** Expect changes. Feedback and issues welcome.

Map Fusion is a Home Assistant integration that turns your robot vacuum maps into one floor map, with each room linked to a Home Assistant area. Dashboard cards and other integrations then share one consistent map instead of each parsing vacuum maps on its own.

- **Real room outlines**, traced from the vacuum's map, not just boxes. Rooms traced by one vacuum never overlap.
- **Rooms are HA areas.** It reuses the room → area links you set in the vacuum's settings (Home Assistant 2026.3+).
- **Several vacuums on one floor are lined up** into one map, using the areas they both know.
- **Filled room shapes:** a second version of each room with furniture gaps (beds, wardrobes, islands) filled in, closer to the real walls.
- **Place areas by hand** that no vacuum covers (garage, porch, upstairs), as a rectangle or polygon.
- **For cards and automations:** a websocket API, services (`get_map`, `locate_point`, `transform_point`, `set_area`, `clear_area`) and a map image entity per floor.

Works with:

| Vacuum | Through | Room shapes |
| --- | --- | --- |
| Dreame | [Tasshack/dreame-vacuum](https://github.com/Tasshack/dreame-vacuum) | Outlines (with the **Map data** camera enabled), else boxes |
| Valetudo robots | Valetudo's MQTT autodiscovery | Outlines |

Xiaomi / Roborock via Xiaomi Cloud Map Extractor is planned.

The map is drawn by [presence-map-card](https://github.com/cubicecho/presence-map-card) (`map_fusion: true`).

## Requirements

- Home Assistant **2026.3** or newer.
- A supported vacuum integration, with the vacuum's rooms linked to areas: open the vacuum entity → ⚙ Settings → **Map vacuum segments to areas**.

## Installation (HACS)

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/cubicecho/map_fusion_ha_integration` with type **Integration**.
3. Find **Map Fusion** in HACS, download it, and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → Map Fusion**. There's nothing to fill in.

Manual install: copy `custom_components/map_fusion` into your config's `custom_components` folder and restart.

## Setup per vacuum

**Dreame:** the room outlines come from the vacuum's **Map data** camera, which Dreame's integration disables by default. Go to **Settings → Entities**, show disabled entities, find `camera.<vacuum>_map_data` and enable it. Until then Map Fusion uses room boxes and shows a repair notice.

**Valetudo:** enable MQTT and Home Assistant autodiscovery in Valetudo. Map Fusion finds the robot by its **Map data** camera. Room links work like any vacuum (the robot needs segment support).

## Using it

- **presence-map-card:** add `map_fusion: true` to the card. It draws every room's outline and keeps your sensors.
- **Place an area by hand:** open **Map Fusion** in the sidebar (admins). Pick an area, then drag its rectangle into place, or drag a corner or edge to resize it. The x, y, width and height fields follow as you drag, and typing in them moves the rectangle straight away. Arrow keys nudge it (Shift + arrows resize), with snapping from 1 cm to 50 cm. It warns when the rectangle overlaps another area. **Save** stores it; **Remove placement** goes back to the vacuum's shape. Vacuum rooms can be replaced with a rectangle the same way.
  - Without the sidebar: Settings → Devices & services → Map Fusion → **Configure** → *Place an area on the map* (numbers plus a preview image), or the `map_fusion.set_area` service, which also takes polygons.
- **Which room is a point in:** `map_fusion.locate_point` with `x`, `y` in map metres, or in the vacuum's own coordinates with `source_id` (e.g. the robot's position).
- **Send a vacuum to a spot on the map:** `map_fusion.transform_point` converts map metres to the vacuum's coordinates.
- **Filled shapes:** add `variant: filled` (card: `map_fusion: { variant: filled }`, services/websocket: `variant: filled`). Set how big a gap counts as furniture under Configure → *Filled room shapes* (default 2 m).
- **Map image:** `image.map_fusion_<map name>` and `image.map_fusion_<map name>_filled` (SVG), with `calibration_points` for Xiaomi Vacuum Map Card.
- **Raw document:** websocket `map_fusion/get` / `map_fusion/subscribe`, or `map_fusion.get_map`. See [the schema](.agents/fused-map-schema.md).

Coordinates are metres, x to the right and y down, with a fixed origin per map, so shapes you place never move when a vacuum re-maps.

Without HA floors, each vacuum map is its own map (named after it, e.g. "Map 1"). With floors, the map follows the floor most of its areas are on (or pick one under Configure → *Choose a vacuum map's floor*).

## Development

See [AGENTS.md](AGENTS.md) for layout, commands and conventions, and [.agents/plan.md](.agents/plan.md) for the design and roadmap.

## License

MIT
