"""Service (action) registration for the Curing Chamber integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_WEIGHT_SENSOR,
    DOMAIN,
    SERVICE_ACKNOWLEDGE_ALERT,
    SERVICE_CREATE_PROGRAM,
    SERVICE_DELETE_PROGRAM,
    SERVICE_NEXT_PHASE,
    SERVICE_PAUSE_PROGRAM,
    SERVICE_RESUME_PROGRAM,
    SERVICE_SET_REFERENCE_WEIGHT,
    SERVICE_SET_TARGETS,
    SERVICE_START_PROGRAM,
    SERVICE_STOP_PROGRAM,
)
from .program.schema import ProgramValidationError, validate_program

if TYPE_CHECKING:
    from .coordinator import CuringChamberCoordinator

_ATTR_DEVICE_ID = "device_id"
_ATTR_PROGRAM_ID = "program_id"
_ATTR_TEMPERATURE = "temperature"
_ATTR_HUMIDITY = "humidity"
_ATTR_WEIGHT = "weight"
_ATTR_PROGRAM = "program"

_TARGET = {vol.Optional(_ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string])}

_START_SCHEMA = vol.Schema({**_TARGET, vol.Required(_ATTR_PROGRAM_ID): cv.string})
_PROGRAM_ID_SCHEMA = vol.Schema({**_TARGET, vol.Required(_ATTR_PROGRAM_ID): cv.string})
_TARGETS_SCHEMA = vol.Schema(
    {
        **_TARGET,
        vol.Optional(_ATTR_TEMPERATURE): vol.Coerce(float),
        vol.Optional(_ATTR_HUMIDITY): vol.Coerce(float),
    }
)
_WEIGHT_SCHEMA = vol.Schema({**_TARGET, vol.Optional(_ATTR_WEIGHT): vol.Coerce(float)})
_CREATE_SCHEMA = vol.Schema({**_TARGET, vol.Required(_ATTR_PROGRAM): dict})
_BARE_SCHEMA = vol.Schema(_TARGET)


def _coordinators(hass: HomeAssistant, call: ServiceCall) -> list[CuringChamberCoordinator]:
    stored: dict[str, CuringChamberCoordinator] = hass.data.get(DOMAIN, {})
    if not stored:
        raise HomeAssistantError("No curing chamber is configured")

    device_ids = call.data.get(_ATTR_DEVICE_ID)
    if not device_ids:
        if len(stored) == 1:
            return list(stored.values())
        raise HomeAssistantError(
            "Multiple chambers configured: specify a target device for this action"
        )

    registry = dr.async_get(hass)
    entry_ids: set[str] = set()
    for device_id in device_ids:
        device = registry.async_get(device_id)
        if device is None:
            continue
        entry_ids.update(device.config_entries)
    result = [stored[eid] for eid in entry_ids if eid in stored]
    if not result:
        raise HomeAssistantError("No curing chamber matches the given device")
    return result


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_START_PROGRAM):
        return

    async def start_program(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            try:
                await coordinator.async_start_program(call.data[_ATTR_PROGRAM_ID])
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err

    async def stop_program(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.async_stop_program()

    async def pause_program(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.async_pause_program()

    async def resume_program(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.async_resume_program()

    async def next_phase(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.async_next_phase()

    async def set_targets(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.async_set_targets(
                call.data.get(_ATTR_TEMPERATURE), call.data.get(_ATTR_HUMIDITY)
            )

    async def set_reference_weight(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.async_set_reference_weight(call.data.get(_ATTR_WEIGHT))

    async def acknowledge_alert(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.async_acknowledge_alerts()

    async def create_program(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            has_scale = bool(
                coordinator.entry.data.get(CONF_WEIGHT_SENSOR)
                or coordinator.entry.options.get(CONF_WEIGHT_SENSOR)
            )
            try:
                program, _warnings = validate_program(call.data[_ATTR_PROGRAM], has_scale=has_scale)
            except ProgramValidationError as err:
                raise HomeAssistantError(f"Invalid program: {err}") from err
            await coordinator.async_create_program(program)

    async def delete_program(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.async_delete_program(call.data[_ATTR_PROGRAM_ID])

    services = (
        (SERVICE_START_PROGRAM, start_program, _START_SCHEMA),
        (SERVICE_STOP_PROGRAM, stop_program, _BARE_SCHEMA),
        (SERVICE_PAUSE_PROGRAM, pause_program, _BARE_SCHEMA),
        (SERVICE_RESUME_PROGRAM, resume_program, _BARE_SCHEMA),
        (SERVICE_NEXT_PHASE, next_phase, _BARE_SCHEMA),
        (SERVICE_SET_TARGETS, set_targets, _TARGETS_SCHEMA),
        (SERVICE_SET_REFERENCE_WEIGHT, set_reference_weight, _WEIGHT_SCHEMA),
        (SERVICE_ACKNOWLEDGE_ALERT, acknowledge_alert, _BARE_SCHEMA),
        (SERVICE_CREATE_PROGRAM, create_program, _CREATE_SCHEMA),
        (SERVICE_DELETE_PROGRAM, delete_program, _PROGRAM_ID_SCHEMA),
    )
    for name, handler, schema in services:
        hass.services.async_register(DOMAIN, name, handler, schema=schema)


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    """Remove the domain services when the last chamber is unloaded."""
    for name in (
        SERVICE_START_PROGRAM,
        SERVICE_STOP_PROGRAM,
        SERVICE_PAUSE_PROGRAM,
        SERVICE_RESUME_PROGRAM,
        SERVICE_NEXT_PHASE,
        SERVICE_SET_TARGETS,
        SERVICE_SET_REFERENCE_WEIGHT,
        SERVICE_ACKNOWLEDGE_ALERT,
        SERVICE_CREATE_PROGRAM,
        SERVICE_DELETE_PROGRAM,
    ):
        hass.services.async_remove(DOMAIN, name)
