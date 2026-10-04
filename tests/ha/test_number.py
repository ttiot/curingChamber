"""Number entity tests: hand-entered weight without a card or YAML."""

from __future__ import annotations

from custom_components.curing_chamber.const import (
    DOMAIN,
    SERVICE_CREATE_BATCH,
    SERVICE_SET_REFERENCE_WEIGHT,
)
from homeassistant.core import HomeAssistant

MANUAL_WEIGHT = "number.test_chamber_manual_weight"


async def _setup(hass, config_entry, seed_states):
    seed_states()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][config_entry.entry_id]


async def _set_weight(hass, value: float) -> None:
    await hass.services.async_call(
        "number", "set_value", {"entity_id": MANUAL_WEIGHT, "value": value}, blocking=True
    )
    await hass.async_block_till_done()


async def test_manual_weight_without_batch_or_scale(
    hass: HomeAssistant, config_entry, seed_states
) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    state = hass.states.get(MANUAL_WEIGHT)
    assert state is not None
    assert state.state == "unknown"

    # The typed value becomes the chamber weight and is persisted.
    await _set_weight(hass, 1200.0)
    assert coordinator.data["weight"] == 1200.0
    assert coordinator.data["weight_source"] == "manual"
    assert coordinator.store.manual_weight["weight"] == 1200.0
    state = hass.states.get(MANUAL_WEIGHT)
    assert float(state.state) == 1200.0
    assert state.attributes["source"] == "manual"

    # "Set reference weight" (no scale) now picks up the manual value...
    await hass.services.async_call(DOMAIN, SERVICE_SET_REFERENCE_WEIGHT, {}, blocking=True)
    await hass.async_block_till_done()
    assert coordinator.program.state.reference_weight == 1200.0

    # ...so a later manual entry drives the weight-loss sensor.
    await _set_weight(hass, 1080.0)
    assert coordinator.data["weight_loss_pct"] == 10.0
    assert float(hass.states.get("sensor.test_chamber_weight_loss").state) == 10.0


async def test_manual_weight_records_weigh_in_on_reference_batch(
    hass: HomeAssistant, config_entry, seed_states
) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_BATCH,
        {"name": "Coppa #1", "reference_weight": 1000.0, "target_loss_pct": 30.0},
        blocking=True,
    )
    await hass.async_block_till_done()
    batch_id = next(iter(coordinator.batches))

    await _set_weight(hass, 900.0)

    batch = coordinator.batches[batch_id]
    assert len(batch.samples) == 1
    assert batch.latest_weight == 900.0
    assert coordinator.data["reference_batch_loss_pct"] == 10.0
    assert coordinator.data["weight_source"] == "batch"
    # Nothing is written to the chamber-level manual weight in that case.
    assert coordinator.store.manual_weight is None
    state = hass.states.get(MANUAL_WEIGHT)
    assert float(state.state) == 900.0
    assert state.attributes["reference_batch_id"] == batch_id
