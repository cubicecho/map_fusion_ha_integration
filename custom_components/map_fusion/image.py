"""Two image entities per frame: the fused map drawn as SVG, as traced
and with furniture gaps filled.

For picture cards and anything that wants a plain map image. Geometry
stays out of the state; attributes carry only sizes and calibration.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.image import ImageEntity
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import SCHEMA_VERSION
from .features import open_state
from .model import FusedFrame, FusedMap
from .render import RenderedFrame, attributes, render

if TYPE_CHECKING:
    from . import MapFusionConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MapFusionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    known: dict[tuple[str, bool], FrameImage] = {}

    @callback
    def sync(fused: FusedMap) -> None:
        new: list[FrameImage] = []
        present = set()
        for frame in fused.frames:
            for filled in (False, True):
                key = (frame.frame_id, filled)
                present.add(key)
                entity = known.get(key)
                if entity is None:
                    entity = known[key] = FrameImage(hass, frame, filled=filled)
                    new.append(entity)
                else:
                    entity.set_frame(frame)
        for key, entity in known.items():
            if key not in present:
                entity.set_frame(None)  # e.g. its vacuum is offline: unavailable
        if new:
            async_add_entities(new)

    entry.async_on_unload(manager.async_subscribe(sync))
    if manager.fused is not None:
        sync(manager.fused)


class FrameImage(ImageEntity):
    _attr_content_type = "image/svg+xml"
    _attr_icon = "mdi:floor-plan"

    def __init__(self, hass: HomeAssistant, frame: FusedFrame, *, filled: bool = False) -> None:
        super().__init__(hass)
        self._filled = filled
        suffix = "_filled" if filled else ""
        self._attr_unique_id = f"frame_{frame.frame_id}{suffix}"
        self._attr_name = f"Map Fusion {frame.name}{' filled' if filled else ''}"
        self._frame: FusedFrame | None = None
        self._rendered: RenderedFrame | None = None
        self._signature: Any = None
        self._states: dict[str, str] = {}
        self._unsub_states: Any = None
        self._update(frame)

    async def async_added_to_hass(self) -> None:
        self._track_feature_entities()
        self._redraw()  # states weren't available before the entity was added

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_states:
            self._unsub_states()
            self._unsub_states = None

    def _track_feature_entities(self) -> None:
        """Redraw when a linked door/window sensor opens or closes."""
        if self._unsub_states:
            self._unsub_states()
            self._unsub_states = None
        entity_ids = sorted({f.entity_id for f in (self._frame.features if self._frame else []) if f.entity_id})
        if self.hass is not None and entity_ids:
            self._unsub_states = async_track_state_change_event(self.hass, entity_ids, self._on_feature_state)

    @callback
    def _on_feature_state(self, _event: Event[EventStateChangedData]) -> None:
        if self._redraw():
            self.async_write_ha_state()

    def _feature_states(self) -> dict[str, str]:
        if self._frame is None or self.hass is None:
            return {}
        out: dict[str, str] = {}
        for f in self._frame.features:
            state = self.hass.states.get(f.entity_id) if f.entity_id else None
            out[f.feature_id] = open_state(f.entity_id, state.state if state else None)
        return out

    def _redraw(self) -> bool:
        """Re-render for new door/window states. True if the picture changed."""
        if self._frame is None:
            return False
        states = self._feature_states()
        if states == self._states and self._rendered is not None:
            return False
        self._states = states
        self._rendered = render(self._frame, filled=self._filled, states=states)
        self._attr_image_last_updated = dt_util.utcnow()
        return True

    @property
    def available(self) -> bool:
        return self._frame is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._frame is None or self._rendered is None:
            return None
        attrs = attributes(self._frame, self._rendered, SCHEMA_VERSION)
        attrs["variant"] = "filled" if self._filled else "traced"
        return attrs

    async def async_image(self) -> bytes | None:
        return self._rendered.svg if self._rendered else None

    @callback
    def set_frame(self, frame: FusedFrame | None) -> None:
        if self._update(frame) and self.hass is not None and self.entity_id:
            self._track_feature_entities()
            self.async_write_ha_state()

    def _update(self, frame: FusedFrame | None) -> bool:
        """Re-render if the frame looks different. True if anything changed."""
        signature = frame.as_dict() if frame else None
        if signature == self._signature:
            return False
        self._signature = signature
        self._frame = frame
        if frame is not None:
            self._states = self._feature_states()
            self._rendered = render(frame, filled=self._filled, states=self._states)
            self._attr_image_last_updated = dt_util.utcnow()
        return True
