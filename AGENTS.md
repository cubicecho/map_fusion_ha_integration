# Project: Map Fusion — Home Assistant Integration

A Home Assistant custom integration that reads the maps from robot vacuums (Dreame, Xiaomi/Roborock, Valetudo, …), puts them in one shared frame per HA floor (or per vacuum map when areas have no floor), and ties each room to an HA area. Other cards and integrations read the result, a **fused map**, instead of each one parsing vacuum maps itself.

**Status: phase 5 done.** Dreame and Valetudo sources; maps from two vacuums on one floor are lined up and merged; user-placed areas (websocket, services, options flow); presence-map-card reads Map Fusion (in that repo); read services `get_map`, `transform_point`, `locate_point` and a per-frame SVG image entity. Next: Xiaomi Cloud Map Extractor source, then phase 6 extras. See [`.agents/plan.md`](.agents/plan.md).

## Commands

```bash
# Install test dependencies. Don't use an editable install (-e): HA's
# custom-component loader can't read the editable path hook. Pytest puts the
# repo on the path itself, so uninstall the project and keep the deps.
pip install ".[test]" ruff mypy && pip uninstall -y map-fusion-ha-integration
# (With uv on this machine, set TMPDIR to a dir on the main disk: /tmp is small.)

# Run tests
pytest

# Type checking
mypy custom_components/map_fusion/

# Lint
ruff check custom_components/ tests/
```

## Layout

```
custom_components/map_fusion/
  __init__.py        # setup: one MapFusionManager per entry; websocket + services registered in async_setup
  config_flow.py     # single entry, no fields; options flow: place/clear areas, map → floor
  const.py           # DOMAIN, SCHEMA_VERSION
  model.py           # Rect, Transform, SourceMap/SourceRoom, FusedMap/Frame/Area (pure)
  geometry.py        # cells → rings → simplified polygons, point-in-polygon (pure)
  placements.py      # user shapes: validate, tidy, label point (pure)
  merge.py           # sources + area links + origins + placements → FusedMap (pure)
  coordinator.py     # MapFusionManager: discovery, events, re-read rules, store, subscribers, repairs, placement API
  websocket.py       # map_fusion/get, /subscribe; admin: /area/set, /area/clear
  services.py        # set_area, clear_area; response-only get_map, transform_point, locate_point (services.yaml)
  queries.py         # find frame, locate point, frame ↔ vacuum transforms, document (pure)
  render.py          # frame → SVG + calibration points (pure)
  image.py           # image platform: SVG image entities per frame (traced + filled)
  preview.py         # signed-URL SVG previews for the options flow (place an area)
  align.py           # line a second vacuum's map up with the anchor (rigid fit on shared areas, pure)
  sources/
    __init__.py      # ADAPTERS: kind → adapter module
    base.py          # adapter contract + SourceDevice
    valetudo_map.py  # ValetudoMap PNG/JSON → room polygons (pure; shared by Dreame and Valetudo)
    dreame.py        # Tasshack dreame-vacuum: entity discovery, pixel rooms, bbox fallback
    valetudo.py      # Valetudo via MQTT autodiscovery: Map data camera, polled every 10 min
tests/
  synthetic.py       # made-up Dreame map (L room, room with hole, room with speck) for CI
  ha_env.py          # fake Dreame entities + Map Fusion setup for tests inside HA
  conftest.py        # fixtures: areas, image_mock, ready (Map Fusion running on the fake vacuum)
  fixtures/          # real D10 Plus data: git-ignored, tests skip without it
```

## Key Conventions

- **Units and axes:** metres, y pointing down the screen, a fixed origin per floor. Same as [presence-map-card](../presence-map-card), so it can read the fused map directly.
- **One frame per HA floor, or per vacuum map when its areas have no floor.** Floors are optional. Each source (vacuum map) gets a 2D transform into its frame.
- **Areas come from HA.** Read the core vacuum segment → area mapping (HA 2026.3+, `registry_entry.options["vacuum"]["area_mapping"]`). Don't ask users to map rooms a second time.
- **Polygons, with a bounding `rect` alongside.** Dreame room polygons are traced from the `map_data` camera's ValetudoMap pixels (no extra dependencies). `rect` (same fields as presence-map-card) is always included for rectangle-only consumers. When `map_data` is disabled, fall back to the `rooms` bounding boxes.
- **Map Fusion owns area geometry.** Users can place areas no vacuum covers (or override one). Placements live in `.storage/map_fusion`, keyed by frame + area, in that frame's coordinates.
- **Frame origins are stored, not recomputed**, so hand-placed areas don't move when a vacuum re-maps. When a map changes frame id (its areas get a floor, or the user picks one), its origin and placements move with it (`merge._migrate`).
- **Two shape variants:** `polygons` (what the vacuum traced) and `filled_polygons` (furniture gaps filled, computed in `valetudo_map.rooms` from the cells). Filling never leaves the room's bounding box, so `rect` is the same for both. Read APIs take `variant`.
- **`merge.build` stays pure:** it takes stored state (origins, placements, floor choices) and returns the updated state; the manager stores it.
- **First source: Dreame** (Tasshack/dreame-vacuum). **First consumer: presence-map-card.**
- **Source adapters own all vendor parsing.** The fusion code only sees the normalized `SourceMap` model: metres, y down, plus `to_native`. A new source is a module with the functions in `sources/base.py`, added to `ADAPTERS`.
- **Big geometry never goes in entity state attributes** (recorder bloat, 16 KB limit). Serve it over websocket and service responses.

## Agent File Convention

All planning, structure, and API reference docs live in `.agents/`. Always add new files to the reference list below.

## Agent Reference Files

- [`.agents/plan.md`](.agents/plan.md) — MVP goal, architecture, phases, open questions
- [`.agents/research.md`](.agents/research.md) — What already exists (HA core, vendor integrations, map formats) and what we reuse
- [`.agents/fused-map-schema.md`](.agents/fused-map-schema.md) — Draft of the fused map document and the APIs that serve it
