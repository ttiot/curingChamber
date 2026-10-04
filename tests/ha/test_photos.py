"""Weigh-in photos: private storage, authenticated delivery and migration."""

from __future__ import annotations

import base64
import os
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

from custom_components.curing_chamber.const import (
    DOMAIN,
    SERVICE_CREATE_BATCH,
    SERVICE_RECORD_WEIGHT,
    STORAGE_KEY_TEMPLATE,
    STORAGE_VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

JPEG = b"\xff\xd8\xff\xd9"
PHOTO = "data:image/jpeg;base64," + base64.b64encode(JPEG).decode()


async def _setup(hass, config_entry, seed_states):
    assert await async_setup_component(hass, "http", {})
    seed_states()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][config_entry.entry_id]


async def test_photo_view_requires_auth(
    hass: HomeAssistant, config_entry, seed_states, hass_client, hass_client_no_auth
) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    await hass.services.async_call(
        DOMAIN, SERVICE_CREATE_BATCH, {"name": "Coppa", "reference_weight": 1000.0}, blocking=True
    )
    await hass.async_block_till_done()
    batch_id = next(iter(coordinator.batches))
    await hass.services.async_call(
        DOMAIN,
        SERVICE_RECORD_WEIGHT,
        {"batch_id": batch_id, "weight": 950.0, "photo": PHOTO},
        blocking=True,
    )
    await hass.async_block_till_done()
    url = coordinator.batches[batch_id].latest_sample.photo_url
    assert url.startswith(f"/api/curing_chamber/photo/{config_entry.entry_id}/{batch_id}/")

    anonymous = await hass_client_no_auth()
    resp = await anonymous.get(url)
    assert resp.status == HTTPStatus.UNAUTHORIZED

    client = await hass_client()
    resp = await client.get(url)
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == JPEG
    assert "private" in resp.headers["Cache-Control"]

    resp = await client.get(url.replace(".jpg", "-missing.jpg"))
    assert resp.status == HTTPStatus.NOT_FOUND
    resp = await client.get(url.replace(config_entry.entry_id, "unknown"))
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_legacy_www_photos_are_migrated(
    hass: HomeAssistant, config_entry, seed_states, hass_storage
) -> None:
    legacy_dir = hass.config.path("www", "curing_chamber", "coppa_1")
    os.makedirs(legacy_dir, exist_ok=True)
    with open(os.path.join(legacy_dir, "1700000000.jpg"), "wb") as handle:
        handle.write(JPEG)
    hass_storage[STORAGE_KEY_TEMPLATE.format(entry_id=config_entry.entry_id)] = {
        "version": STORAGE_VERSION,
        "data": {
            "programs": {},
            "program_state": None,
            "counters": {},
            "reference_batch_id": "coppa_1",
            "batches": {
                "coppa_1": {
                    "id": "coppa_1",
                    "name": "Coppa #1",
                    "reference_weight": 1000.0,
                    "created_at": 1_699_000_000.0,
                    "status": "active",
                    "samples": [
                        {
                            "timestamp": 1_700_000_000.0,
                            "weight": 950.0,
                            "note": None,
                            "photo_url": "/local/curing_chamber/coppa_1/1700000000.jpg",
                        }
                    ],
                }
            },
        },
    }

    coordinator = await _setup(hass, config_entry, seed_states)
    sample = coordinator.batches["coppa_1"].latest_sample
    assert sample.photo_url == (
        f"/api/curing_chamber/photo/{config_entry.entry_id}/coppa_1/1700000000.jpg"
    )
    assert not os.path.exists(os.path.join(legacy_dir, "1700000000.jpg"))
    new_path = coordinator.photo_path("coppa_1", "1700000000.jpg")
    assert os.path.isfile(new_path)
    with open(new_path, "rb") as handle:
        assert handle.read() == JPEG


async def test_panel_and_card_are_registered_with_version(
    hass: HomeAssistant, config_entry, seed_states
) -> None:
    register = AsyncMock()
    remove = patch("custom_components.curing_chamber.async_remove_panel")
    with (
        patch("custom_components.curing_chamber.async_register_panel", register),
        patch("custom_components.curing_chamber.add_extra_js_url") as extra_js,
        remove as remove_panel,
    ):
        await _setup(hass, config_entry, seed_states)
        register.assert_awaited_once()
        kwargs = register.await_args.kwargs
        assert kwargs["frontend_url_path"] == "curing-chamber"
        assert kwargs["webcomponent_name"] == "curing-chamber-panel"
        assert kwargs["require_admin"] is False
        assert kwargs["module_url"].startswith("/curing_chamber/curing-chamber-panel.js?v=")
        assert kwargs["config"]["version"] == kwargs["module_url"].rsplit("v=", 1)[1]
        extra_js.assert_called_once()
        assert extra_js.call_args.args[1].startswith("/curing_chamber/curing-chamber-card.js?v=")

        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        remove_panel.assert_called_once_with(hass, "curing-chamber", warn_if_unknown=False)
