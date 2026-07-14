"""Service tests: program lifecycle and diagnostics."""

from __future__ import annotations

from custom_components.curing_chamber.const import (
    DOMAIN,
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
