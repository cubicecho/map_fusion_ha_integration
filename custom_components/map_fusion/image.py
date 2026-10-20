"""One image entity per frame: the fused map drawn as SVG.

For picture cards and anything that wants a plain map image. Geometry
stays out of the state; attributes carry only sizes and calibration.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import SCHEMA_VERSION
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
    known: dict[str, FrameImage] = {}

    @callback
    def sync(fused: FusedMap) -> None:
        new: list[FrameImage] = []
        present = set()
        for frame in fused.frames:
            present.add(frame.frame_id)
            entity = known.get(frame.frame_id)
            if entity is None:
                entity = known[frame.frame_id] = FrameImage(hass, frame)
                new.append(entity)
            else:
                entity.set_frame(frame)
        for frame_id, entity in known.items():
            if frame_id not in present:
                entity.set_frame(None)  # e.g. its vacuum is offline: unavailable
        if new:
            async_add_entities(new)

    entry.async_on_unload(manager.async_subscribe(sync))
    if manager.fused is not None:
        sync(manager.fused)


class FrameImage(ImageEntity):
    _attr_content_type = "image/svg+xml"
    _attr_icon = "mdi:floor-plan"

    def __init__(self, hass: HomeAssistant, frame: FusedFrame) -> None:
        super().__init__(hass)
        self._attr_unique_id = f"frame_{frame.frame_id}"
        self._attr_name = f"Map Fusion {frame.name}"
        self._frame: FusedFrame | None = None
        self._rendered: RenderedFrame | None = None
        self._signature: Any = None
        self._update(frame)

    @property
    def available(self) -> bool:
        return self._frame is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._frame is None or self._rendered is None:
            return None
        return attributes(self._frame, self._rendered, SCHEMA_VERSION)

    async def async_image(self) -> bytes | None:
        return self._rendered.svg if self._rendered else None

    @callback
    def set_frame(self, frame: FusedFrame | None) -> None:
        if self._update(frame) and self.hass is not None and self.entity_id:
            self.async_write_ha_state()

    def _update(self, frame: FusedFrame | None) -> bool:
        """Re-render if the frame looks different. True if anything changed."""
        signature = frame.as_dict() if frame else None
        if signature == self._signature:
            return False
        self._signature = signature
        self._frame = frame
        if frame is not None:
            self._rendered = render(frame)
            self._attr_image_last_updated = dt_util.utcnow()
        return True
