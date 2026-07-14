"""Config and options flow tests."""

from __future__ import annotations

from custom_components.curing_chamber.const import (
    CONF_COOL_SWITCH,
    CONF_NAME,
    CONF_TEMP_DEADBAND,
    CONF_TEMP_SENSOR,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import COOL_ENTITY, TEMP_ENTITY


async def test_full_config_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "My Chamber", CONF_TEMP_SENSOR: TEMP_ENTITY},
    )
    assert result["step_id"] == "actuators"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOL_SWITCH: COOL_ENTITY}
    )
    assert result["step_id"] == "notifications"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "food_safety"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Chamber"
    assert result["data"][CONF_TEMP_SENSOR] == TEMP_ENTITY


async def test_options_flow_regulation(hass: HomeAssistant, config_entry, seed_states) -> None:
    seed_states()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "regulation"}
    )
    assert result["step_id"] == "regulation"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_TEMP_DEADBAND: 1.0}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_TEMP_DEADBAND] == 1.0
