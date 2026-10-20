"""Keeps the fused map current and tells subscribers when it changes.

- Re-reads a vacuum map only when its room layout changes (the map camera
  updates on every robot move, so that alone isn't a reason).
- Rebuilds without re-reading when areas, floors or area links change.
- Stores frame origins so hand-placed things never shift.
- Stores the user's area placements and map → floor choices.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import timedelta
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import (
    CALLBACK_TYPE,
    CoreState,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import placements as pl
from .const import DOMAIN
from .merge import AreaInfo, FrameOrigin, SourceInput, build
from .model import FusedArea, FusedMap, Ring, SourceMap
from .placements import Placements
from .sources import dreame

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN
REBUILD_COOLDOWN = 2.0  # seconds
FULL_REFRESH_INTERVAL = timedelta(hours=6)
ISSUE_MAP_DATA_DISABLED = "map_data_disabled"

Listener = Callable[[FusedMap], None]


class PlacementError(ServiceValidationError):
    """A placement request that can't be done. `code` is the websocket error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def get_manager(hass: HomeAssistant) -> MapFusionManager | None:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


class MapFusionManager:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.fused: FusedMap | None = None
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._origins: dict[str, FrameOrigin] = {}
        self._placements: Placements = {}
        self._floor_choices: dict[str, str | None] = {}
        self._devices: list[dreame.DreameEntities] = []
        self._maps: dict[str, SourceMap] = {}  # by vacuum entity id
        self._signatures: dict[str, Any] = {}
        self._listeners: list[Listener] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._state_unsub: CALLBACK_TYPE | None = None
        self._force_reread = False
        self._debouncer = Debouncer(
            hass, _LOGGER, cooldown=REBUILD_COOLDOWN, immediate=False, function=self._async_refresh
        )

    async def async_start(self) -> None:
        stored = await self._store.async_load() or {}
        self._origins = {
            frame_id: FrameOrigin(anchor=o["anchor"], origin=(o["origin"][0], o["origin"][1]))
            for frame_id, o in (stored.get("frames") or {}).items()
        }
        self._placements = {
            frame_id: {
                area_id: [[(float(x), float(y)) for x, y in ring] for ring in rings]
                for area_id, rings in by_area.items()
            }
            for frame_id, by_area in (stored.get("placements") or {}).items()
        }
        self._floor_choices = dict(stored.get("floor_choices") or {})
        self._rediscover()
        self._unsubs += [
            self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self._on_entity_registry),
            self.hass.bus.async_listen(ar.EVENT_AREA_REGISTRY_UPDATED, self._on_layout_change),
            self.hass.bus.async_listen(fr.EVENT_FLOOR_REGISTRY_UPDATED, self._on_layout_change),
            async_track_time_interval(self.hass, self._on_interval, FULL_REFRESH_INTERVAL),
        ]
        if self.hass.state is CoreState.running:
            await self._async_refresh()
        else:
            # Vacuum integrations may not have their states yet; refresh once
            # everything is up. State changes trigger a refresh meanwhile.
            self._unsubs.append(
                self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self._on_started)
            )

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None
        self._debouncer.async_shutdown()
        if self._origins or self._placements or self._floor_choices:
            await self._store.async_save(self._store_data())

    @callback
    def async_subscribe(self, listener: Listener) -> CALLBACK_TYPE:
        self._listeners.append(listener)

        @callback
        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    async def async_refresh_now(self, *, reread: bool = False) -> None:
        """Refresh immediately (tests, services)."""
        self._force_reread |= reread
        await self._async_refresh()

    # User placements --------------------------------------------------------

    @property
    def placements(self) -> Placements:
        return self._placements

    @property
    def floor_choices(self) -> dict[str, str | None]:
        return self._floor_choices

    def frame_choices(self) -> dict[str, str]:
        """Frames a placement can go in: built frames plus every HA floor."""
        out = {f.frame_id: f.name for f in self.fused.frames} if self.fused else {}
        for floor in fr.async_get(self.hass).async_list_floors():
            out.setdefault(floor.floor_id, floor.name)
        return out

    async def async_set_area(
        self, area_id: str, rings: list[Ring], frame_id: str | None = None
    ) -> FusedArea:
        """Store a user shape for an area and rebuild. `rings` must be normalised."""
        area = ar.async_get(self.hass).async_get_area(area_id)
        if area is None:
            raise PlacementError("not_found", f"Area {area_id} does not exist")
        frame_id = self.resolve_frame(area_id, area.floor_id, frame_id)
        self._placements.setdefault(frame_id, {})[area_id] = rings
        await self._store.async_save(self._store_data())
        self._rebuild()
        assert self.fused is not None
        frame = self.fused.frame(frame_id)
        placed = next((a for a in frame.areas if a.area_id == area_id), None) if frame else None
        if placed is None:  # e.g. the frame's vacuum is offline right now
            raise PlacementError("not_found", f"Frame {frame_id} is not available right now")
        return placed

    async def async_clear_area(self, area_id: str, frame_id: str | None = None) -> str:
        """Remove a user shape. Returns the frame it was removed from."""
        frames = [f for f, by_area in self._placements.items() if area_id in by_area]
        if frame_id is None:
            if not frames:
                raise PlacementError("not_found", f"Area {area_id} has no placement")
            if len(frames) > 1:
                raise PlacementError(
                    "frame_required", f"Area {area_id} is placed in several frames; give a frame_id"
                )
            frame_id = frames[0]
        elif frame_id not in frames:
            raise PlacementError("not_found", f"Area {area_id} has no placement in {frame_id}")
        del self._placements[frame_id][area_id]
        if not self._placements[frame_id]:
            del self._placements[frame_id]
        await self._store.async_save(self._store_data())
        self._rebuild()
        return frame_id

    async def async_set_floor_choice(self, source_key: str, floor_id: str | None, *, auto: bool) -> None:
        """Pin a vacuum map to a floor (or to no floor), or go back to automatic."""
        if auto:
            self._floor_choices.pop(source_key, None)
        else:
            if floor_id is not None and fr.async_get(self.hass).async_get_floor(floor_id) is None:
                raise PlacementError("not_found", f"Floor {floor_id} does not exist")
            self._floor_choices[source_key] = floor_id
        await self._store.async_save(self._store_data())
        self._rebuild()

    def resolve_frame(self, area_id: str, area_floor: str | None, frame_id: str | None) -> str:
        frames = {f.frame_id: f for f in self.fused.frames} if self.fused else {}
        floors = {f.floor_id for f in fr.async_get(self.hass).async_list_floors()}
        if frame_id is None:
            if area_floor and area_floor in frames:
                return area_floor
            if area_floor and area_floor in floors:
                return area_floor  # a floor with no vacuum: placements only
            if len(frames) == 1:
                return next(iter(frames))
            raise PlacementError(
                "frame_required", "There is more than one map frame; give a frame_id"
            )
        if frame_id in frames:
            frame_floor = frames[frame_id].floor_id
        elif frame_id in floors:
            frame_floor = frame_id
        else:
            raise PlacementError("not_found", f"Frame {frame_id} does not exist")
        if area_floor and frame_floor and area_floor != frame_floor:
            raise PlacementError(
                "floor_mismatch",
                f"Area {area_id} is on floor {area_floor}, but frame {frame_id} is floor {frame_floor}",
            )
        return frame_id

    # Events -----------------------------------------------------------------

    @callback
    def _on_started(self, _event: Event[Any]) -> None:
        self._force_reread = True
        self._debouncer.async_schedule_call()

    @callback
    def _on_interval(self, _now: Any) -> None:
        self._force_reread = True
        self._debouncer.async_schedule_call()

    @callback
    def _on_layout_change(self, event: Event[Any]) -> None:
        if event.data.get("action") == "remove" and "area_id" in event.data:
            self._prune_area(event.data["area_id"])
        self._debouncer.async_schedule_call()

    @callback
    def _prune_area(self, area_id: str) -> None:
        changed = False
        for frame_id in list(self._placements):
            if self._placements[frame_id].pop(area_id, None) is not None:
                changed = True
                if not self._placements[frame_id]:
                    del self._placements[frame_id]
        if changed:
            self._store.async_delay_save(self._store_data, 1)

    @callback
    def _on_entity_registry(self, event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        entity_id = event.data["entity_id"]
        if event.data["action"] != "update" or entity_id.startswith(("camera.", "vacuum.")):
            # New/removed entities, enabled Map data cameras, or changed area
            # links (vacuum entity options) all land here.
            self._rediscover()
            self._debouncer.async_schedule_call()

    @callback
    def _on_state(self, _event: Event[EventStateChangedData]) -> None:
        self._debouncer.async_schedule_call()

    @callback
    def _rediscover(self) -> None:
        devices = dreame.discover(self.hass)
        if devices != self._devices:
            self._force_reread = True
        self._devices = devices
        if self._state_unsub:
            self._state_unsub()
        tracked = [e for d in devices for e in (d.vacuum, d.map_camera, d.map_data_camera) if e]
        self._state_unsub = async_track_state_change_event(self.hass, tracked, self._on_state)
        self._update_issues()

    # Work -------------------------------------------------------------------

    async def _async_refresh(self) -> None:
        force = self._force_reread
        self._force_reread = False
        live = {d.vacuum for d in self._devices}
        for gone in set(self._maps) - live:
            del self._maps[gone]
            self._signatures.pop(gone, None)

        for device in self._devices:
            signature = dreame.map_signature(self.hass, device)
            if signature is None:
                continue
            if not force and device.vacuum in self._maps and self._signatures.get(device.vacuum) == signature:
                continue
            smap = await dreame.async_read(self.hass, device)
            if smap is not None:
                self._maps[device.vacuum] = smap
                self._signatures[device.vacuum] = signature

        self._rebuild()

    def _rebuild(self) -> None:
        result = build(
            sources=[
                SourceInput(map=smap, area_mapping=self._area_mapping(entity_id))
                for entity_id, smap in self._maps.items()
            ],
            areas=self._areas(),
            floor_names={f.floor_id: f.name for f in fr.async_get(self.hass).async_list_floors()},
            origins=self._origins,
            generated_at=dt_util.utcnow().isoformat(),
            placements=self._placements,
            floor_choices=self._floor_choices,
        )
        if result.origins != self._origins or result.placements != self._placements:
            self._origins = result.origins
            self._placements = result.placements
            self._store.async_delay_save(self._store_data, 1)
        changed = self.fused is None or _comparable(self.fused) != _comparable(result.fused)
        self.fused = result.fused
        if changed:
            for listener in list(self._listeners):
                listener(result.fused)

    def _area_mapping(self, entity_id: str) -> dict[str, list[str]]:
        """The user's area → segment links from the vacuum's entity options."""
        entry = er.async_get(self.hass).async_get(entity_id)
        if entry is None:
            return {}
        vacuum_options: Mapping[str, Any] = entry.options.get("vacuum") or {}
        mapping = vacuum_options.get("area_mapping") or {}
        return {str(area): [str(s) for s in segs] for area, segs in mapping.items()}

    def _areas(self) -> dict[str, AreaInfo]:
        return {
            a.id: AreaInfo(area_id=a.id, name=a.name, floor_id=a.floor_id)
            for a in ar.async_get(self.hass).async_list_areas()
        }

    def _store_data(self) -> dict[str, Any]:
        return {
            "frames": {
                frame_id: {"anchor": o.anchor, "origin": list(o.origin)}
                for frame_id, o in self._origins.items()
            },
            "placements": {
                frame_id: {area_id: pl.as_lists(rings) for area_id, rings in by_area.items()}
                for frame_id, by_area in self._placements.items()
            },
            "floor_choices": dict(self._floor_choices),
        }

    def _update_issues(self) -> None:
        for device in self._devices:
            issue_id = f"{ISSUE_MAP_DATA_DISABLED}_{device.vacuum}"
            if device.map_data_disabled:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key=ISSUE_MAP_DATA_DISABLED,
                    translation_placeholders={"vacuum": device.vacuum},
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)


def _comparable(fused: FusedMap) -> dict[str, Any]:
    data = fused.as_dict()
    data.pop("generated_at")
    return data
