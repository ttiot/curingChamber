"""The Curing Chamber integration."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.loader import async_get_integration

from .const import (
    CARD_FILENAME,
    DOMAIN,
    FRONTEND_URL_BASE,
    PANEL_FILENAME,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    PANEL_WEBCOMPONENT,
    PLATFORMS,
    SIGNAL_CHAMBERS_CHANGED,
)
from .coordinator import CuringChamberCoordinator
from .services import async_setup_services, async_unload_services
from .views import async_register_views
from .websocket import async_register_websocket

try:  # present on every real core; guarded so a stripped-down core still loads
    from homeassistant.components.frontend import add_extra_js_url, async_remove_panel
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.components.panel_custom import async_register_panel
except ImportError:  # pragma: no cover
    add_extra_js_url = async_remove_panel = async_register_panel = None  # type: ignore[assignment]
    StaticPathConfig = None  # type: ignore[assignment,misc]

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
_PLATFORMS = [Platform(p) for p in PLATFORMS]

_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
_STATIC_KEY = f"{DOMAIN}_static_registered"
_PANEL_KEY = f"{DOMAIN}_panel_registered"


async def _async_version(hass: HomeAssistant) -> str:
    """Integration version from the manifest, used to cache-bust frontend files."""
    try:
        integration = await async_get_integration(hass, DOMAIN)
        return str(integration.version or "0")
    except Exception:  # never block setup on a loader hiccup
        return "0"


async def _async_register_static(hass: HomeAssistant) -> str:
    """Serve the bundled JS, the photo view and the websocket API (once).

    Returns the version string appended as ``?v=`` to the JS URLs so browsers
    fetch the new files after an update instead of serving a cached copy.
    """
    version = await _async_version(hass)
    if hass.data.get(_STATIC_KEY):
        return version
    hass.data[_STATIC_KEY] = True

    async_register_websocket(hass)
    async_register_views(hass)

    if add_extra_js_url is None or StaticPathConfig is None:
        return version
    try:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    f"{FRONTEND_URL_BASE}/{name}", os.path.join(_FRONTEND_DIR, name), True
                )
                for name in (CARD_FILENAME, PANEL_FILENAME)
            ]
        )
        add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/{CARD_FILENAME}?v={version}")
    except Exception:  # the bundled card must never break setup
        _LOGGER.debug("Curing Chamber frontend files not registered", exc_info=True)
    return version


async def _async_register_panel(hass: HomeAssistant, version: str) -> None:
    """Add the sidebar panel (once while at least one chamber is loaded)."""
    if hass.data.get(_PANEL_KEY) or async_register_panel is None:
        return
    try:
        await async_register_panel(
            hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name=PANEL_WEBCOMPONENT,
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            module_url=f"{FRONTEND_URL_BASE}/{PANEL_FILENAME}?v={version}",
            embed_iframe=False,
            require_admin=False,
            config={"version": version},
        )
        hass.data[_PANEL_KEY] = True
    except Exception:  # the panel is optional (e.g. frontend unavailable)
        _LOGGER.debug("Curing Chamber panel not registered", exc_info=True)


def _async_remove_panel(hass: HomeAssistant) -> None:
    if not hass.data.pop(_PANEL_KEY, False) or async_remove_panel is None:
        return
    try:
        async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    except Exception:
        _LOGGER.debug("Curing Chamber panel not removed", exc_info=True)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a curing chamber from a config entry."""
    coordinator = CuringChamberCoordinator(hass, entry)
    await coordinator.async_prepare()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    async_setup_services(hass)
    version = await _async_register_static(hass)
    await _async_register_panel(hass, version)
    async_dispatcher_send(hass, SIGNAL_CHAMBERS_CHANGED)
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
            _async_remove_panel(hass)
        async_dispatcher_send(hass, SIGNAL_CHAMBERS_CHANGED)
    return unloaded
