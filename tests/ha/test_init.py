"""Setup / unload and end-to-end regulation wiring (§13.2, §13.5)."""

from __future__ import annotations

from custom_components.curing_chamber.const import DOMAIN
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import COOL_ENTITY, TEMP_ENTITY


async def test_setup_and_unload(hass: HomeAssistant, config_entry, seed_states) -> None:
    seed_states()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Device entities exist.
    assert hass.states.get("climate.test_chamber_temperature") is not None
    assert hass.states.get("humidifier.test_chamber_humidity") is not None
    assert hass.states.get("sensor.test_chamber_dew_point") is not None
    assert DOMAIN in hass.data

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_cooling_commands_the_switch(
    hass: HomeAssistant, config_entry, seed_states, cooling_switch
) -> None:
    """A hot chamber with a cooling switch turns the switch on (after startup)."""
    seed_states(temp=18.0)
    config_entry.add_to_hass(hass)
    # Zero the startup lockout so the first real tick can act.
    hass.config_entries.async_update_entry(
        config_entry, options={"startup_delay": 0, "cool_min_off": 0, "cool_min_on": 0}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    # Manual target below current temperature -> should cool.
    await coordinator.async_set_targets(13.0, None)
    await hass.async_block_till_done()
    assert hass.states.get(COOL_ENTITY).state == STATE_ON


async def test_sensor_fault_forces_safe_state(
    hass: HomeAssistant, config_entry, seed_states, cooling_switch
) -> None:
    """Losing the temperature sensor raises a critical fault and stops actuators."""
    seed_states(temp=18.0)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={"startup_delay": 0, "cool_min_off": 0, "cool_min_on": 0}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.async_set_targets(13.0, None)
    await hass.async_block_till_done()

    hass.states.async_set(TEMP_ENTITY, "unavailable")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(COOL_ENTITY).state == "off"
    binary = hass.states.get("binary_sensor.test_chamber_sensor_fault")
    assert binary is not None and binary.state == STATE_ON
