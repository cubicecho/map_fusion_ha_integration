"""Config and options flows for Map Fusion.

The config flow makes a single entry with no fields. The options flow is
the no-frontend way to place areas by hand (rectangles only), remove
placements, and choose which floor a vacuum map is on.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import selector

from . import placements as pl
from .const import DOMAIN
from .coordinator import MapFusionManager, PlacementError

try:  # HA 2026.10+ validates with probatio
    import probatio as vol
except ImportError:  # older HA
    import voluptuous as vol  # type: ignore[no-redef]

AUTO = "auto"
NO_FLOOR = "none"
METRES = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=-1000, max=1000, step=0.01, unit_of_measurement="m", mode=selector.NumberSelectorMode.BOX
    )
)
POSITIVE_METRES = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0.01, max=1000, step=0.01, unit_of_measurement="m", mode=selector.NumberSelectorMode.BOX
    )
)


class MapFusionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the single Map Fusion entry."""
        if user_input is not None:
            return self.async_create_entry(title="Map Fusion", data={})
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MapFusionOptionsFlow:
        return MapFusionOptionsFlow()


def _select(options: dict[str, str]) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[selector.SelectOptionDict(value=k, label=v) for k, v in options.items()],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


class MapFusionOptionsFlow(OptionsFlow):
    """Place areas, remove placements, choose map floors."""

    def __init__(self) -> None:
        self._area_id: str | None = None
        self._frame_id: str | None = None

    @property
    def _manager(self) -> MapFusionManager | None:
        return getattr(self.config_entry, "runtime_data", None)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._manager is None:
            return self.async_abort(reason="not_loaded")
        return self.async_show_menu(
            step_id="init", menu_options=["place_area", "clear_area", "map_floor"]
        )

    # Place an area ----------------------------------------------------------

    async def async_step_place_area(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        manager = self._manager
        assert manager is not None
        frames = manager.frame_choices()
        if not frames:
            return self.async_abort(reason="no_frames")
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            area_id = user_input["area_id"]
            area = ar.async_get(self.hass).async_get_area(area_id)
            try:
                if area is None:
                    raise PlacementError("not_found", f"Area {area_id} does not exist")
                frame_id = user_input.get("frame_id") or None
                self._frame_id = manager.resolve_frame(area_id, area.floor_id, frame_id)
                self._area_id = area_id
                return await self.async_step_place_rect()
            except PlacementError as err:
                errors["base"] = "invalid_placement"
                placeholders["error"] = str(err)

        fields: dict[Any, Any] = {vol.Required("area_id"): selector.AreaSelector()}
        if len(frames) > 1:
            fields[vol.Required("frame_id")] = _select(frames)
        return self.async_show_form(
            step_id="place_area",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_place_rect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        manager = self._manager
        assert manager is not None and self._area_id and self._frame_id
        errors: dict[str, str] = {}
        placeholders = {"error": "", "frame": manager.frame_choices().get(self._frame_id, self._frame_id)}
        if user_input is not None:
            try:
                ring = pl.rect_ring(
                    user_input["x"], user_input["y"], user_input["width"], user_input["height"]
                )
                await manager.async_set_area(self._area_id, [ring], self._frame_id)
                return self.async_create_entry(data={})
            except pl.InvalidPlacement as err:
                errors["base"] = "invalid_placement"
                placeholders["error"] = str(err)
            except PlacementError as err:
                errors["base"] = "invalid_placement"
                placeholders["error"] = str(err)

        current = self._current_rect(manager)
        schema = vol.Schema(
            {
                vol.Required("x", default=current["x"]): METRES,
                vol.Required("y", default=current["y"]): METRES,
                vol.Required("width", default=current["width"]): POSITIVE_METRES,
                vol.Required("height", default=current["height"]): POSITIVE_METRES,
            }
        )
        return self.async_show_form(
            step_id="place_rect", data_schema=schema, errors=errors, description_placeholders=placeholders
        )

    def _current_rect(self, manager: MapFusionManager) -> dict[str, float]:
        """Start from the area's current shape in this frame, if it has one."""
        frame = manager.fused.frame(self._frame_id) if manager.fused and self._frame_id else None
        area = next((a for a in frame.areas if a.area_id == self._area_id), None) if frame else None
        if area is not None:
            return area.rect.as_dict()
        return {"x": 0.0, "y": 0.0, "width": 2.0, "height": 2.0}

    # Remove a placement -----------------------------------------------------

    async def async_step_clear_area(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        manager = self._manager
        assert manager is not None
        frames = manager.frame_choices()
        area_reg = ar.async_get(self.hass)
        options: dict[str, str] = {}
        for frame_id, by_area in sorted(manager.placements.items()):
            for area_id in sorted(by_area):
                area = area_reg.async_get_area(area_id)
                name = area.name if area else area_id
                options[f"{frame_id}|{area_id}"] = f"{name} ({frames.get(frame_id, frame_id)})"
        if not options:
            return self.async_abort(reason="no_placements")
        if user_input is not None:
            frame_id, _, area_id = user_input["placement"].rpartition("|")
            await manager.async_clear_area(area_id, frame_id)
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="clear_area",
            data_schema=vol.Schema({vol.Required("placement"): _select(options)}),
        )

    # Map → floor ------------------------------------------------------------

    async def async_step_map_floor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        manager = self._manager
        assert manager is not None
        maps: dict[str, str] = {}
        for frame in manager.fused.frames if manager.fused else []:
            for src in frame.sources:
                key = f"{src['source_id']}:{src['map_id']}"
                maps[key] = f"{src.get('map_name') or src['map_id']} ({src['source_id']})"
        if not maps:
            return self.async_abort(reason="no_maps")
        floors = {AUTO: "Automatic (most of its areas' floor)", NO_FLOOR: "No floor"}
        floors.update({f.floor_id: f.name for f in fr.async_get(self.hass).async_list_floors()})
        if user_input is not None:
            choice = user_input["floor"]
            try:
                await manager.async_set_floor_choice(
                    user_input["map"],
                    None if choice in (AUTO, NO_FLOOR) else choice,
                    auto=choice == AUTO,
                )
            except PlacementError:
                return self.async_abort(reason="floor_missing")
            return self.async_create_entry(data={})

        first = next(iter(maps))
        current = manager.floor_choices.get(first, AUTO) if first in manager.floor_choices else AUTO
        return self.async_show_form(
            step_id="map_floor",
            data_schema=vol.Schema(
                {
                    vol.Required("map", default=first): _select(maps),
                    vol.Required("floor", default=current or NO_FLOOR): _select(floors),
                }
            ),
        )
