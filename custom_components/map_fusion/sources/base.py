"""What every map source adapter provides.

An adapter is a module with:

- `KIND`: short name ("dreame", "valetudo").
- `POLL_INTERVAL`: how often to re-read even without a sign of change
  (`None` = only on signs of change), for sources whose map image changes
  without any state change Home Assistant can see.
- `discover(hass) -> list[SourceDevice]`
- `map_signature(hass, device) -> Any | None`: cheap; changes when the room
  layout may have changed. `None` means "no map yet, skip".
- `async_read(hass, device) -> SourceMap | None`: the expensive read.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SourceDevice:
    kind: str
    vacuum: str  # vacuum entity id: the source id
    # Entities whose state changes may mean a new map (watched for changes).
    tracked: list[str] = field(default_factory=list)
    # Dreame: the Map data camera is off, so only room boxes are available.
    map_data_disabled: bool = False
    # Adapter-specific details.
    extra: Any = None
