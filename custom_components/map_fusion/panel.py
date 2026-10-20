"""The Map Fusion sidebar page: drag and resize hand-placed areas.

The page is a web component bundled into frontend/map-fusion-panel.js
(source in the repo's frontend/ folder). It's served from this folder and
registered as an admin-only panel at /map-fusion.
"""
from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

URL_PATH = "map-fusion"
STATIC_URL = "/map_fusion_static"
MODULE = "map-fusion-panel.js"
ELEMENT = "map-fusion-panel"
DATA_STATIC = f"{DOMAIN}_static_registered"


async def async_register(hass: HomeAssistant) -> None:
    """Serve the bundle (once per run) and add the sidebar page.

    Skipped when the frontend isn't loaded (headless installs, tests).
    """
    if "frontend" not in hass.config.components:
        return
    if not hass.data.get(DATA_STATIC):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), cache_headers=False)]
        )
        hass.data[DATA_STATIC] = True
    version = (await async_get_integration(hass, DOMAIN)).version
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=URL_PATH,
        webcomponent_name=ELEMENT,
        sidebar_title="Map Fusion",
        sidebar_icon="mdi:floor-plan",
        # The version busts browser caches after an update.
        module_url=f"{STATIC_URL}/{MODULE}?v={version}",
        require_admin=True,
    )


def async_unregister(hass: HomeAssistant) -> None:
    if "frontend" in hass.config.components:
        frontend.async_remove_panel(hass, URL_PATH, warn_if_unknown=False)
