"""Config flow for Map Fusion.

MVP: a single entry with no fields. Map sources are picked in the options
flow later (see .agents/plan.md, phase 1).
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


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
