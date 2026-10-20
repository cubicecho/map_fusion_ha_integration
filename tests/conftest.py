"""Shared test fixtures."""
from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.camera import Image
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from pytest_homeassistant_custom_component.common import MockConfigEntry

from . import synthetic
from .ha_env import PATCH_IMAGE, add_dreame, link_areas, setup_map_fusion

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let HA load custom_components/ in every test."""
    yield


@pytest.fixture
def image_mock() -> AsyncMock:
    """The Map data camera's image: the synthetic map."""
    return AsyncMock(return_value=Image("image/png", synthetic.png_with(synthetic.valetudo_doc())))


@pytest.fixture
async def areas(hass: HomeAssistant) -> dict[str, str]:
    """Kitchen, Office and Garage areas, by name."""
    reg = ar.async_get(hass)
    return {name: reg.async_create(name).id for name in ("Kitchen", "Office", "Garage")}


@pytest.fixture
async def ready(
    hass: HomeAssistant, areas: dict[str, str], image_mock: AsyncMock
) -> AsyncIterator[MockConfigEntry]:
    """Map Fusion running on one Dreame map with Kitchen linked."""
    await add_dreame(hass)
    await link_areas(hass, {areas["Kitchen"]: ["1_1"]})
    with patch(PATCH_IMAGE, image_mock):
        yield await setup_map_fusion(hass)
