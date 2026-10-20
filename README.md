# Map Fusion

> **Early development.** Dreame room outlines, linked to areas, served over the websocket API, services and a map image entity. Areas no vacuum covers can be placed by hand (websocket, services or the integration's options). [presence-map-card](https://github.com/cubicecho/presence-map-card) (v0.4.0+) draws the map.

Map Fusion is a Home Assistant integration that combines the maps from your robot vacuums into one floor map per floor, with each room linked to a Home Assistant area. Dashboard cards and other integrations can then use a single, consistent map.

## Planned features

- Read room maps from Dreame and Valetudo vacuums (Xiaomi / Roborock planned)
- Line up several vacuums' maps on the same floor into one map
- Link rooms to Home Assistant areas, reusing the vacuum area mapping Home Assistant already has (2026.3+)
- Serve the fused map to cards and integrations through a websocket API, a service and an image entity

## Installation

Not yet released. When it is, it will install through HACS as a custom repository.
