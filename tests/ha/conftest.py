"""Fixtures for the Home Assistant integration tests."""

from __future__ import annotations

import pytest
from custom_components.curing_chamber.const import (
    CONF_COOL_SWITCH,
    CONF_HUMIDITY_SENSOR,
    CONF_NAME,
    CONF_TEMP_SENSOR,
    DOMAIN,
)
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

TEMP_ENTITY = "sensor.chamber_temp"
HUMIDITY_ENTITY = "sensor.chamber_humidity"
COOL_ENTITY = "input_boolean.chamber_cool"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the custom component in every test."""
    yield


@pytest.fixture(autouse=True)
def isolated_config_dir(hass, tmp_path):
    """Point the config dir at a temp folder so photo files never leak between tests."""
    hass.config.config_dir = str(tmp_path)
    yield


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A chamber configured with a temp/humidity sensor and a cooling switch."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Chamber",
        data={
            CONF_NAME: "Test Chamber",
            CONF_TEMP_SENSOR: TEMP_ENTITY,
            CONF_HUMIDITY_SENSOR: HUMIDITY_ENTITY,
            CONF_COOL_SWITCH: COOL_ENTITY,
        },
        options={},
    )


@pytest.fixture
def seed_states(hass):
    """Seed source sensor states before setup."""

    def _seed(temp: float = 13.0, humidity: float = 75.0) -> None:
        hass.states.async_set(TEMP_ENTITY, str(temp), {"unit_of_measurement": "°C"})
        hass.states.async_set(HUMIDITY_ENTITY, str(humidity), {"unit_of_measurement": "%"})

    return _seed


@pytest.fixture
async def cooling_switch(hass):
    """Provide a real, controllable input_boolean acting as the cooling actuator."""
    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"chamber_cool": {}}}
    )
    await hass.async_block_till_done()
    return COOL_ENTITY
