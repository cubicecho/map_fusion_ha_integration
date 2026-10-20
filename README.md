# Map Fusion

> **Early development.** Phase 1 works: Dreame room outlines, linked to areas, served over the websocket API. No UI yet.

Map Fusion is a Home Assistant integration that combines the maps from your robot vacuums into one floor map per floor, with each room linked to a Home Assistant area. Dashboard cards and other integrations can then use a single, consistent map.

## Planned features

- Read room maps from Dreame, Xiaomi / Roborock and Valetudo vacuums
- Align several vacuums' maps on the same floor into one coordinate frame
- Link rooms to Home Assistant areas, reusing the vacuum area mapping Home Assistant already has (2026.3+)
- Serve the fused map to cards and integrations through a websocket API, a service and an image entity

## Installation

Not yet released. When it is, it will install through HACS as a custom repository.
