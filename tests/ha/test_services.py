"""Service tests: program lifecycle, batch tracking and diagnostics."""

from __future__ import annotations

import base64
import os

from custom_components.curing_chamber.const import (
    DOMAIN,
    SERVICE_CREATE_BATCH,
    SERVICE_DELETE_BATCH,
    SERVICE_RECORD_WEIGHT,
    SERVICE_SET_REFERENCE_BATCH,
    SERVICE_SET_TARGETS,
    SERVICE_START_PROGRAM,
    SERVICE_STOP_PROGRAM,
)
from custom_components.curing_chamber.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant


async def _setup(hass, config_entry, seed_states):
    seed_states()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][config_entry.entry_id]


async def test_start_and_stop_program(hass: HomeAssistant, config_entry, seed_states) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)

    await hass.services.async_call(
        DOMAIN, SERVICE_START_PROGRAM, {"program_id": "saucisson_sec"}, blocking=True
    )
    await hass.async_block_till_done()
    assert coordinator.program.status.value == "running"
    assert coordinator.program.state.program_id == "saucisson_sec"

    await hass.services.async_call(DOMAIN, SERVICE_STOP_PROGRAM, {}, blocking=True)
    await hass.async_block_till_done()
    assert coordinator.program.status.value == "idle"


async def test_set_targets_service(hass: HomeAssistant, config_entry, seed_states) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    await hass.services.async_call(
        DOMAIN, SERVICE_SET_TARGETS, {"temperature": 12.0, "humidity": 78.0}, blocking=True
    )
    await hass.async_block_till_done()
    assert coordinator.data["target_temp"] == 12.0
    assert coordinator.data["target_humidity"] == 78.0


async def test_diagnostics(hass: HomeAssistant, config_entry, seed_states) -> None:
    await _setup(hass, config_entry, seed_states)
    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert "state" in diag
    assert diag["entry"]["data"]["temp_sensor"] == "**REDACTED**"


async def _create_batch(hass, **data) -> None:
    payload = {"name": "Coppa #1", "reference_weight": 1000.0, "target_loss_pct": 30.0}
    payload.update(data)
    await hass.services.async_call(DOMAIN, SERVICE_CREATE_BATCH, payload, blocking=True)
    await hass.async_block_till_done()


async def test_create_batch_and_record_weight(
    hass: HomeAssistant, config_entry, seed_states
) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    await _create_batch(hass)

    assert len(coordinator.batches) == 1
    batch_id = next(iter(coordinator.batches))
    # The first batch becomes the reference automatically.
    assert coordinator.store.reference_batch_id == batch_id

    await hass.services.async_call(
        DOMAIN, SERVICE_RECORD_WEIGHT, {"batch_id": batch_id, "weight": 900.0}, blocking=True
    )
    await hass.async_block_till_done()

    batch = coordinator.batches[batch_id]
    assert batch.latest_weight == 900.0
    assert coordinator.data["reference_batch_loss_pct"] == 10.0
    summary = coordinator.data["batches"][0]
    assert summary["loss_pct"] == 10.0
    assert summary["last_weight"] == 900.0


async def test_record_weight_with_photo(hass: HomeAssistant, config_entry, seed_states) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    await _create_batch(hass)
    batch_id = next(iter(coordinator.batches))

    encoded = base64.b64encode(b"\xff\xd8\xff\xd9").decode()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_RECORD_WEIGHT,
        {"batch_id": batch_id, "weight": 950.0, "photo": f"data:image/jpeg;base64,{encoded}"},
        blocking=True,
    )
    await hass.async_block_till_done()

    sample = coordinator.batches[batch_id].latest_sample
    assert sample is not None
    assert sample.photo_url is not None
    assert sample.photo_url.startswith(f"/local/curing_chamber/{batch_id}/")
    on_disk = hass.config.path(sample.photo_url.replace("/local/", "www/"))
    assert os.path.isfile(on_disk)


async def test_set_reference_batch_drives_completion(
    hass: HomeAssistant, config_entry, seed_states
) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    await _create_batch(hass, name="A")
    await _create_batch(hass, name="B", target_loss_pct=20.0)
    _first, second = list(coordinator.batches)

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_REFERENCE_BATCH, {"batch_id": second}, blocking=True
    )
    await hass.async_block_till_done()
    assert coordinator.store.reference_batch_id == second

    # A weigh-in past the 20 % target flips the batch to completed on the next tick.
    await hass.services.async_call(
        DOMAIN, SERVICE_RECORD_WEIGHT, {"batch_id": second, "weight": 750.0}, blocking=True
    )
    await hass.async_block_till_done()
    assert coordinator.batches[second].status.value == "completed"


async def test_delete_batch(hass: HomeAssistant, config_entry, seed_states) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    await _create_batch(hass)
    batch_id = next(iter(coordinator.batches))

    await hass.services.async_call(
        DOMAIN, SERVICE_DELETE_BATCH, {"batch_id": batch_id}, blocking=True
    )
    await hass.async_block_till_done()
    assert batch_id not in coordinator.batches
    assert coordinator.store.reference_batch_id is None
