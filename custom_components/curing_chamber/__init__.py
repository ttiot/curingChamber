"""The Curing Chamber integration."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from homeassistant.const import Platform

from .const import DOMAIN, PLATFORMS
from .coordinator import CuringChamberCoordinator
from .services import async_setup_services, async_unload_services

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
_PLATFORMS = [Platform(p) for p in PLATFORMS]

_CARD_URL = f"/{DOMAIN}/curing-chamber-card.js"
_CARD_PATH = os.path.join(os.path.dirname(__file__), "frontend", "curing-chamber-card.js")
_FRONTEND_KEY = f"{DOMAIN}_frontend_registered"

try:  # frontend helper is present on every real core; guard for safety
    from homeassistant.components.frontend import add_extra_js_url
except ImportError:  # pragma: no cover
    add_extra_js_url = None  # type: ignore[assignment]

try:  # newer cores expose the async static-path API
    from homeassistant.components.http import StaticPathConfig
except ImportError:  # pragma: no cover - older cores use the sync API
    StaticPathConfig = None  # type: ignore[assignment,misc]


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve and register the bundled Lovelace card (best-effort, once)."""
    if hass.data.get(_FRONTEND_KEY) or add_extra_js_url is None:
        return
    http = getattr(hass, "http", None)
    if http is None:
        return
    try:
        if StaticPathConfig is not None:
            await http.async_register_static_paths([StaticPathConfig(_CARD_URL, _CARD_PATH, False)])
        else:
            http.register_static_path(_CARD_URL, _CARD_PATH, False)
        add_extra_js_url(hass, _CARD_URL)
        hass.data[_FRONTEND_KEY] = True
    except Exception:  # the bundled card must never break integration setup
        _LOGGER.debug("Curing Chamber frontend card not registered", exc_info=True)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a curing chamber from a config entry."""
    coordinator = CuringChamberCoordinator(hass, entry)
    await coordinator.async_prepare()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    async_setup_services(hass)
    await _async_register_frontend(hass)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unloaded:
        coordinator: CuringChamberCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
        if not hass.data[DOMAIN]:
            async_unload_services(hass)
    return unloaded
