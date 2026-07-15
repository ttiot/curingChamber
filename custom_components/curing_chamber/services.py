"""Service (action) registration for the Curing Chamber integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .const import (
    CONF_WEIGHT_SENSOR,
    DOMAIN,
    SERVICE_ACKNOWLEDGE_ALERT,
    SERVICE_ARCHIVE_BATCH,
    SERVICE_COMPLETE_BATCH,
    SERVICE_CREATE_BATCH,
    SERVICE_CREATE_PROGRAM,
    SERVICE_DELETE_BATCH,
    SERVICE_DELETE_PROGRAM,
    SERVICE_NEXT_PHASE,
    SERVICE_PAUSE_PROGRAM,
    SERVICE_RECORD_WEIGHT,
    SERVICE_RESUME_PROGRAM,
    SERVICE_SET_REFERENCE_BATCH,
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
_ATTR_BATCH_ID = "batch_id"
_ATTR_NAME = "name"
_ATTR_PRODUCT = "product"
_ATTR_REFERENCE_WEIGHT = "reference_weight"
_ATTR_TARGET_LOSS_PCT = "target_loss_pct"
_ATTR_SET_AS_REFERENCE = "set_as_reference"
_ATTR_TIMESTAMP = "timestamp"
_ATTR_NOTE = "note"
_ATTR_PHOTO = "photo"

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

_CREATE_BATCH_SCHEMA = vol.Schema(
    {
        **_TARGET,
        vol.Required(_ATTR_NAME): cv.string,
        vol.Optional(_ATTR_PRODUCT): cv.string,
        vol.Optional(_ATTR_PROGRAM_ID): cv.string,
        vol.Optional(_ATTR_REFERENCE_WEIGHT): vol.Coerce(float),
        vol.Optional(_ATTR_TARGET_LOSS_PCT): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
        vol.Optional(_ATTR_SET_AS_REFERENCE): cv.boolean,
    }
)
_RECORD_WEIGHT_SCHEMA = vol.Schema(
    {
        **_TARGET,
        vol.Required(_ATTR_BATCH_ID): cv.string,
        vol.Required(_ATTR_WEIGHT): vol.Coerce(float),
        vol.Optional(_ATTR_TIMESTAMP): cv.datetime,
        vol.Optional(_ATTR_NOTE): cv.string,
        vol.Optional(_ATTR_PHOTO): cv.string,
    }
)
_BATCH_ID_SCHEMA = vol.Schema({**_TARGET, vol.Required(_ATTR_BATCH_ID): cv.string})


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

    async def create_batch(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.async_create_batch(
                name=call.data[_ATTR_NAME],
                product=call.data.get(_ATTR_PRODUCT),
                program_id=call.data.get(_ATTR_PROGRAM_ID),
                reference_weight=call.data.get(_ATTR_REFERENCE_WEIGHT),
                target_loss_pct=call.data.get(_ATTR_TARGET_LOSS_PCT),
                set_as_reference=call.data.get(_ATTR_SET_AS_REFERENCE, False),
            )

    async def record_weight(call: ServiceCall) -> None:
        moment = call.data.get(_ATTR_TIMESTAMP)
        timestamp = dt_util.as_utc(moment).timestamp() if moment is not None else None
        for coordinator in _coordinators(hass, call):
            try:
                await coordinator.async_record_weight(
                    call.data[_ATTR_BATCH_ID],
                    call.data[_ATTR_WEIGHT],
                    timestamp=timestamp,
                    note=call.data.get(_ATTR_NOTE),
                    photo=call.data.get(_ATTR_PHOTO),
                )
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err

    async def set_reference_batch(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            try:
                await coordinator.async_set_reference_batch(call.data[_ATTR_BATCH_ID])
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err

    async def complete_batch(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            try:
                await coordinator.async_complete_batch(call.data[_ATTR_BATCH_ID])
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err

    async def archive_batch(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            try:
                await coordinator.async_archive_batch(call.data[_ATTR_BATCH_ID])
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err

    async def delete_batch(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.async_delete_batch(call.data[_ATTR_BATCH_ID])

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
        (SERVICE_CREATE_BATCH, create_batch, _CREATE_BATCH_SCHEMA),
        (SERVICE_RECORD_WEIGHT, record_weight, _RECORD_WEIGHT_SCHEMA),
        (SERVICE_SET_REFERENCE_BATCH, set_reference_batch, _BATCH_ID_SCHEMA),
        (SERVICE_COMPLETE_BATCH, complete_batch, _BATCH_ID_SCHEMA),
        (SERVICE_ARCHIVE_BATCH, archive_batch, _BATCH_ID_SCHEMA),
        (SERVICE_DELETE_BATCH, delete_batch, _BATCH_ID_SCHEMA),
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
        SERVICE_CREATE_BATCH,
        SERVICE_RECORD_WEIGHT,
        SERVICE_SET_REFERENCE_BATCH,
        SERVICE_COMPLETE_BATCH,
        SERVICE_ARCHIVE_BATCH,
        SERVICE_DELETE_BATCH,
    ):
        hass.services.async_remove(DOMAIN, name)
