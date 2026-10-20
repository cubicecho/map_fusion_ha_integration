"""Preview images for placing areas in the options flow.

Flow descriptions are markdown, and HA's frontend shows `![](url)` images
with relative URLs (not data URLs). So the flow stores what to draw under
a random id and links a signed URL to this view; the browser's <img> loads
it without an auth header (the signature is the auth).
"""
from __future__ import annotations

import secrets
from collections import OrderedDict
from dataclasses import dataclass
from datetime import timedelta

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.http import KEY_HASS

from .const import DOMAIN
from .coordinator import get_manager
from .model import Ring
from .render import render_preview

URL = "/api/map_fusion/preview/{preview_id}"
LINK_LIFETIME = timedelta(hours=1)
KEEP = 32  # previews kept in memory
DATA_PREVIEWS = f"{DOMAIN}_previews"


@dataclass(slots=True)
class Preview:
    frame_id: str | None
    editing: str | None
    proposal: list[Ring] | None
    title: str


@callback
def async_register(hass: HomeAssistant) -> None:
    hass.data[DATA_PREVIEWS] = OrderedDict()
    hass.http.register_view(PreviewView())


@callback
def async_preview_markdown(
    hass: HomeAssistant,
    frame_id: str | None,
    *,
    editing: str | None = None,
    proposal: list[Ring] | None = None,
    title: str = "",
) -> str:
    """A markdown image of the map for a flow description."""
    previews: OrderedDict[str, Preview] = hass.data.setdefault(DATA_PREVIEWS, OrderedDict())
    preview_id = secrets.token_urlsafe(12)
    previews[preview_id] = Preview(frame_id, editing, proposal, title)
    while len(previews) > KEEP:
        previews.popitem(last=False)
    url = async_sign_path(hass, URL.format(preview_id=preview_id), LINK_LIFETIME)
    return f"![Map preview]({url})"


class PreviewView(HomeAssistantView):
    url = URL
    name = "api:map_fusion:preview"
    requires_auth = True  # satisfied by the signed URL

    async def get(self, request: web.Request, preview_id: str) -> web.Response:
        hass = request.app[KEY_HASS]
        preview = hass.data.get(DATA_PREVIEWS, {}).get(preview_id)
        manager = get_manager(hass)
        if preview is None or manager is None:
            return web.Response(status=404)
        fused = manager.fused
        frame = fused.frame(preview.frame_id) if fused and preview.frame_id else None
        svg = render_preview(frame, editing=preview.editing, proposal=preview.proposal, title=preview.title)
        return web.Response(
            body=svg, content_type="image/svg+xml", headers={"Cache-Control": "no-store"}
        )
