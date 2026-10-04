"""Websocket API consumed by the sidebar panel and the bundled card.

Reads and the live subscription are open to every logged-in user; mutations
mirror what the YAML services already allow. Program control, manual targets
and the regulation/maintenance switches are *not* duplicated here: the frontend
calls the existing services/entities for those.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .batch import BatchStatus
from .const import DOMAIN, SIGNAL_CHAMBERS_CHANGED
from .program.presets import preset_by_id
from .program.schema import ProgramValidationError, validate_program

if TYPE_CHECKING:
    from homeassistant.components.websocket_api import ActiveConnection

    from .coordinator import CuringChamberCoordinator

_REGISTERED_KEY = f"{DOMAIN}_websocket_registered"

_ENTRY = {vol.Required("entry_id"): str}
_BATCH = {**_ENTRY, vol.Required("batch_id"): str}


def _coordinator(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> CuringChamberCoordinator | None:
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Unknown chamber")
    return coordinator


# -- Chambers & live state ---------------------------------------------------


def _chambers(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Describe every loaded chamber (the panel's selector)."""
    registry = dr.async_get(hass)
    chambers = []
    for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
        device = registry.async_get_device(identifiers={(DOMAIN, entry_id)})
        chambers.append(
            {
                "entry_id": entry_id,
                "name": coordinator.chamber_name,
                "device_id": device.id if device else None,
                "has_scale": coordinator.has_scale,
            }
        )
    return chambers


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/chambers"})
@callback
def ws_chambers(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    connection.send_result(msg["id"], _chambers(hass))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe_chambers"})
@callback
def ws_subscribe_chambers(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Push the chamber list now and whenever a chamber is (un)loaded or renamed."""

    @callback
    def _push() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], _chambers(hass)))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass, SIGNAL_CHAMBERS_CHANGED, _push
    )
    connection.send_result(msg["id"])
    _push()


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/state", **_ENTRY})
@callback
def ws_state(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], coordinator.chamber_state())


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe", **_ENTRY})
@callback
def ws_subscribe(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return

    @callback
    def _push() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], coordinator.chamber_state()))

    connection.subscriptions[msg["id"]] = coordinator.async_add_listener(_push)
    connection.send_result(msg["id"])
    _push()


# -- Batches & weigh-ins -----------------------------------------------------


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/batches",
        **_ENTRY,
        vol.Optional("include_archived", default=False): bool,
        vol.Optional("with_samples", default=False): bool,
    }
)
@callback
def ws_batches(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    connection.send_result(
        msg["id"],
        coordinator.batch_summaries(
            include_archived=msg["include_archived"], with_samples=msg["with_samples"]
        ),
    )


def _send_batch(
    connection: ActiveConnection, msg: dict[str, Any], coordinator: CuringChamberCoordinator
) -> None:
    try:
        connection.send_result(msg["id"], coordinator.batch_summary(msg["batch_id"]))
    except ValueError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/batch", **_BATCH})
@callback
def ws_batch(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    _send_batch(connection, msg, coordinator)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/batch/create",
        **_ENTRY,
        vol.Required("name"): vol.All(str, vol.Length(min=1)),
        vol.Optional("product"): vol.Any(None, str),
        vol.Optional("program_id"): vol.Any(None, str),
        vol.Optional("reference_weight"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("target_loss_pct"): vol.Any(
            None, vol.All(vol.Coerce(float), vol.Range(min=0, max=90))
        ),
        vol.Optional("set_as_reference", default=False): bool,
    }
)
@websocket_api.async_response
async def ws_batch_create(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    batch = await coordinator.async_create_batch(
        name=msg["name"],
        product=msg.get("product") or None,
        program_id=msg.get("program_id") or None,
        reference_weight=msg.get("reference_weight"),
        target_loss_pct=msg.get("target_loss_pct"),
        set_as_reference=msg["set_as_reference"],
    )
    connection.send_result(msg["id"], coordinator.batch_summary(batch.id))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/batch/set_status",
        **_BATCH,
        vol.Required("status"): vol.In([status.value for status in BatchStatus]),
    }
)
@websocket_api.async_response
async def ws_batch_set_status(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    try:
        await coordinator.async_set_batch_status(msg["batch_id"], BatchStatus(msg["status"]))
    except ValueError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))
        return
    _send_batch(connection, msg, coordinator)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/batch/set_reference", **_BATCH})
@websocket_api.async_response
async def ws_batch_set_reference(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    try:
        await coordinator.async_set_reference_batch(msg["batch_id"])
    except ValueError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))
        return
    _send_batch(connection, msg, coordinator)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/batch/delete", **_BATCH})
@websocket_api.async_response
async def ws_batch_delete(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    deleted = await coordinator.async_delete_batch(msg["batch_id"])
    connection.send_result(msg["id"], {"deleted": deleted})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/weigh_in",
        **_BATCH,
        vol.Required("weight"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("timestamp"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("note"): vol.Any(None, str),
        vol.Optional("photo"): vol.Any(None, str),
    }
)
@websocket_api.async_response
async def ws_weigh_in(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    try:
        await coordinator.async_record_weight(
            msg["batch_id"],
            msg["weight"],
            timestamp=msg.get("timestamp"),
            note=msg.get("note") or None,
            photo=msg.get("photo") or None,
        )
    except ValueError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))
        return
    _send_batch(connection, msg, coordinator)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/weigh_in/delete",
        **_BATCH,
        vol.Required("timestamp"): vol.Coerce(float),
    }
)
@websocket_api.async_response
async def ws_weigh_in_delete(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    try:
        await coordinator.async_delete_weigh_in(msg["batch_id"], msg["timestamp"])
    except ValueError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))
        return
    _send_batch(connection, msg, coordinator)


# -- Programs ------------------------------------------------------------------


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/programs", **_ENTRY})
@callback
def ws_programs(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], [p.to_dict() for p in coordinator.available_programs()])


def _validate(coordinator: CuringChamberCoordinator, raw: Any) -> dict[str, Any]:
    try:
        program, warnings = validate_program(raw, has_scale=coordinator.has_scale)
    except ProgramValidationError as err:
        return {"valid": False, "errors": [str(err)], "warnings": [], "program": None}
    errors: list[str] = []
    if preset_by_id(program.id) is not None:
        errors.append(f"'{program.id}' is a built-in preset; pick another id")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": list(warnings),
        "program": dataclasses.replace(program, builtin=False),
    }


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/program/validate", **_ENTRY, vol.Required("program"): dict}
)
@callback
def ws_program_validate(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    result = _validate(coordinator, msg["program"])
    result.pop("program")
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/program/save", **_ENTRY, vol.Required("program"): dict}
)
@websocket_api.async_response
async def ws_program_save(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    result = _validate(coordinator, msg["program"])
    if not result["valid"]:
        connection.send_error(
            msg["id"], websocket_api.ERR_INVALID_FORMAT, "; ".join(result["errors"])
        )
        return
    program = result["program"]
    await coordinator.async_create_program(program)
    connection.send_result(
        msg["id"], {"program": program.to_dict(), "warnings": result["warnings"]}
    )


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/program/delete", **_ENTRY, vol.Required("program_id"): str}
)
@websocket_api.async_response
async def ws_program_delete(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    deleted = await coordinator.async_delete_program(msg["program_id"])
    connection.send_result(msg["id"], {"deleted": deleted})


_COMMANDS = (
    ws_chambers,
    ws_subscribe_chambers,
    ws_state,
    ws_subscribe,
    ws_batches,
    ws_batch,
    ws_batch_create,
    ws_batch_set_status,
    ws_batch_set_reference,
    ws_batch_delete,
    ws_weigh_in,
    ws_weigh_in_delete,
    ws_programs,
    ws_program_validate,
    ws_program_save,
    ws_program_delete,
)


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    """Register the websocket commands once per Home Assistant run."""
    if hass.data.get(_REGISTERED_KEY):
        return
    for command in _COMMANDS:
        websocket_api.async_register_command(hass, command)
    hass.data[_REGISTERED_KEY] = True
