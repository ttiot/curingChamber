"""HTTP views: authenticated delivery of weigh-in photos.

Photos live under ``<config>/.storage/curing_chamber/photos`` (never under the
public ``www/`` folder) and are only served to logged-in users. Browsers embed
them with a signed URL obtained from the ``auth/sign_path`` websocket command.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView

from .const import DOMAIN, PHOTO_URL_BASE

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_SAFE = re.compile(r"[A-Za-z0-9_.-]+")
_REGISTERED_KEY = f"{DOMAIN}_views_registered"


class CuringChamberPhotoView(HomeAssistantView):
    """Serve one stored weigh-in photo to an authenticated user."""

    url = f"{PHOTO_URL_BASE}/{{entry_id}}/{{batch_id}}/{{filename}}"
    name = f"api:{DOMAIN}:photo"
    requires_auth = True

    async def get(
        self, request: web.Request, entry_id: str, batch_id: str, filename: str
    ) -> web.StreamResponse:
        hass: HomeAssistant = request.app[KEY_HASS]
        coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if (
            coordinator is None
            or not _SAFE.fullmatch(batch_id)
            or not _SAFE.fullmatch(filename)
            or ".." in (batch_id, filename)
        ):
            raise web.HTTPNotFound
        path = coordinator.photo_path(batch_id, filename)
        if not await hass.async_add_executor_job(os.path.isfile, path):
            raise web.HTTPNotFound
        return web.FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})


def async_register_views(hass: HomeAssistant) -> None:
    """Register the HTTP views once per Home Assistant run."""
    if hass.data.get(_REGISTERED_KEY) or hass.http is None:
        return
    hass.http.register_view(CuringChamberPhotoView())
    hass.data[_REGISTERED_KEY] = True
