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
from .model import Rect
from .preview import async_preview_markdown
from .render import default_spot

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
        self._proposal: Rect | None = None

    @property
    def _manager(self) -> MapFusionManager | None:
        return getattr(self.config_entry, "runtime_data", None)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._manager is None:
            return self.async_abort(reason="not_loaded")
        return self.async_show_menu(
            step_id="init", menu_options=["place_area", "clear_area", "map_floor", "filled_shapes"]
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
                self._proposal = None
                return await self.async_step_place_rect()
            except PlacementError as err:
                errors["base"] = "invalid_placement"
                placeholders["error"] = str(err)

        fields: dict[Any, Any] = {vol.Required("area_id"): selector.AreaSelector()}
        if len(frames) > 1:
            fields[vol.Required("frame_id")] = _select(frames)
        first = next(iter(frames))
        placeholders["frame"] = frames[first]
        placeholders["map"] = async_preview_markdown(self.hass, first, title=frames[first])
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
                pl.rect_ring(user_input["x"], user_input["y"], user_input["width"], user_input["height"])
                self._proposal = Rect(
                    user_input["x"], user_input["y"], user_input["width"], user_input["height"]
                )
                return await self.async_step_place_preview()
            except pl.InvalidPlacement as err:
                errors["base"] = "invalid_placement"
                placeholders["error"] = str(err)

        start = self._start_rect(manager)
        placeholders["map"] = self._map(start)
        schema = vol.Schema(
            {
                vol.Required("x", default=start.x): METRES,
                vol.Required("y", default=start.y): METRES,
                vol.Required("width", default=start.width): POSITIVE_METRES,
                vol.Required("height", default=start.height): POSITIVE_METRES,
            }
        )
        return self.async_show_form(
            step_id="place_rect", data_schema=schema, errors=errors, description_placeholders=placeholders
        )

    async def async_step_place_preview(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the rectangle on the map: save it, or go back and adjust."""
        assert self._proposal is not None
        r = self._proposal
        return self.async_show_menu(
            step_id="place_preview",
            menu_options=["place_save", "place_rect"],
            description_placeholders={
                "map": self._map(r),
                "rect": f"{r.width:g} × {r.height:g} m at x {r.x:g}, y {r.y:g}",
            },
        )

    async def async_step_place_save(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        manager = self._manager
        assert manager is not None and self._area_id and self._frame_id and self._proposal
        r = self._proposal
        try:
            ring = pl.rect_ring(r.x, r.y, r.width, r.height)
            await manager.async_set_area(self._area_id, [ring], self._frame_id)
        except (pl.InvalidPlacement, PlacementError) as err:
            return self.async_abort(reason="placement_failed", description_placeholders={"error": str(err)})
        return self.async_create_entry(data={})

    def _map(self, rect: Rect) -> str:
        """Markdown image: the frame with `rect` drawn where the area would go."""
        area = ar.async_get(self.hass).async_get_area(self._area_id or "")
        return async_preview_markdown(
            self.hass,
            self._frame_id,
            editing=self._area_id,
            proposal=[pl.rect_ring(rect.x, rect.y, rect.width, rect.height)],
            title=area.name if area else "",
        )

    def _start_rect(self, manager: MapFusionManager) -> Rect:
        """The last rectangle tried, else the area's current box, else a spot beside the map."""
        if self._proposal is not None:
            return self._proposal
        frame = manager.fused.frame(self._frame_id) if manager.fused and self._frame_id else None
        area = next((a for a in frame.areas if a.area_id == self._area_id), None) if frame else None
        if area is not None:
            r = area.rect
            return Rect(round(r.x, 2), round(r.y, 2), round(r.width, 2), round(r.height, 2))
        return default_spot(frame)

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

    # Filled shapes -----------------------------------------------------------

    async def async_step_filled_shapes(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        manager = self._manager
        assert manager is not None
        if user_input is not None:
            await manager.async_set_fill_max(user_input["fill_max_m"])
            return self.async_create_entry(data={})
        schema = vol.Schema(
            {
                vol.Required("fill_max_m", default=manager.fill_max_m): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=5, step=0.1, unit_of_measurement="m", mode=selector.NumberSelectorMode.BOX
                    )
                )
            }
        )
        return self.async_show_form(step_id="filled_shapes", data_schema=schema)
