"""Service tests: program lifecycle, batch tracking and diagnostics."""

from __future__ import annotations

import base64
import os

import pytest
from custom_components.curing_chamber.const import (
    CHAMBER_KIND_CHEESE,
    CONF_CHAMBER_KIND,
    CONF_DEGRADED_DELAY,
    CONF_HUMIDITY_SENSOR,
    CONF_NAME,
    CONF_PRODUCT_TEMP_SENSOR,
    CONF_STARTUP_DELAY,
    CONF_TEMP_SENSOR,
    DOMAIN,
    SERVICE_ADD_BATCH_EVENT,
    SERVICE_COMPLETE_BATCH,
    SERVICE_CREATE_BATCH,
    SERVICE_DELETE_BATCH,
    SERVICE_DELETE_BATCH_EVENT,
    SERVICE_EXPORT_BATCH,
    SERVICE_EXPORT_PROGRAMS,
    SERVICE_IMPORT_PROGRAMS,
    SERVICE_NEXT_PHASE,
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
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import HUMIDITY_ENTITY, TEMP_ENTITY


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
    # Photos are private: stored outside www/ and served by an authenticated view.
    assert sample.photo_url.startswith(
        f"/api/curing_chamber/photo/{config_entry.entry_id}/{batch_id}/"
    )
    on_disk = coordinator.photo_path(batch_id, sample.photo_url.rsplit("/", 1)[-1])
    assert os.path.isfile(on_disk)
    assert not os.path.exists(hass.config.path("www", "curing_chamber", batch_id))


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


_PROGRAM = {
    "id": "my_chorizo",
    "name": "My chorizo",
    "phases": [
        {"name": "rest", "target_temp": 22, "target_humidity": 85, "duration_hours": 48},
        {
            "name": "drying",
            "target_temp": 13,
            "target_humidity": 75,
            "end_kind": "weight_loss",
            "weight_loss_pct": 35,
            "duration_hours": 800,
            "start_temp": 22,
            "start_humidity": 85,
            "ramp_hours": 48,
        },
    ],
}


async def test_export_and_import_programs(hass: HomeAssistant, config_entry, seed_states) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)

    empty = await hass.services.async_call(
        DOMAIN, SERVICE_EXPORT_PROGRAMS, {}, blocking=True, return_response=True
    )
    assert empty == {"format": "curing_chamber/programs", "version": 1, "programs": []}

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_PROGRAMS,
        {"programs": [_PROGRAM]},
        blocking=True,
        return_response=True,
    )
    assert result == {"imported": ["my_chorizo"], "skipped": []}
    assert "my_chorizo" in coordinator.store.programs

    exported = await hass.services.async_call(
        DOMAIN, SERVICE_EXPORT_PROGRAMS, {}, blocking=True, return_response=True
    )
    assert exported["format"] == "curing_chamber/programs"
    assert [p["id"] for p in exported["programs"]] == ["my_chorizo"]
    assert exported["programs"][0]["phases"][1]["ramp_hours"] == 48.0
    assert exported["programs"][0]["builtin"] is False

    # Re-importing the export skips the existing id unless overwrite is set.
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_PROGRAMS,
        {"programs": exported},
        blocking=True,
        return_response=True,
    )
    assert result == {"imported": [], "skipped": ["my_chorizo"]}
    renamed = {**exported, "programs": [{**exported["programs"][0], "name": "Renamed"}]}
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_PROGRAMS,
        {"programs": renamed, "overwrite": True},
        blocking=True,
        return_response=True,
    )
    assert result == {"imported": ["my_chorizo"], "skipped": []}
    assert coordinator.store.programs["my_chorizo"]["name"] == "Renamed"

    # Built-in preset ids are never overwritten.
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_PROGRAMS,
        {"programs": {**_PROGRAM, "id": "coppa"}, "overwrite": True},
        blocking=True,
        return_response=True,
    )
    assert result == {"imported": [], "skipped": ["coppa"]}


async def test_import_programs_rejects_invalid_payload(
    hass: HomeAssistant, config_entry, seed_states
) -> None:
    await _setup(hass, config_entry, seed_states)
    with pytest.raises(HomeAssistantError, match="Invalid programs"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_IMPORT_PROGRAMS,
            {"programs": [{"id": "bad", "name": "Bad", "phases": []}]},
            blocking=True,
            return_response=True,
        )


async def test_ramp_drives_the_regulation_targets(
    hass: HomeAssistant, config_entry, seed_states
) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    await hass.services.async_call(
        DOMAIN, SERVICE_IMPORT_PROGRAMS, {"programs": [_PROGRAM]}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, SERVICE_START_PROGRAM, {"program_id": "my_chorizo"}, blocking=True
    )
    await hass.async_block_till_done()
    assert coordinator.data["target_temp"] == 22.0
    assert coordinator.data["ramp_remaining"] is None

    # Jump into the drying phase: the targets start where the rest phase ended.
    await hass.services.async_call(DOMAIN, SERVICE_NEXT_PHASE, {}, blocking=True)
    await hass.async_block_till_done()
    await coordinator.async_refresh()  # the service refresh is debounced
    assert coordinator.data["phase_name"] == "drying"
    assert coordinator.data["target_temp"] == pytest.approx(22.0, abs=0.01)
    assert coordinator.data["target_humidity"] == pytest.approx(85.0, abs=0.01)
    assert coordinator.data["phase_target_temp"] == 13.0
    assert coordinator.data["ramp_remaining"] == pytest.approx(48 * 3600.0, abs=5)

    # Half-way through the ramp the targets sit half-way too.
    coordinator.program.state.phase_started_at -= 24 * 3600.0
    await coordinator.async_refresh()
    assert coordinator.data["target_temp"] == pytest.approx(17.5, abs=0.01)
    assert coordinator.data["target_humidity"] == pytest.approx(80.0, abs=0.01)
    state = hass.states.get("sensor.test_chamber_phase_time_remaining")
    assert state is not None
    assert state.attributes["phase_target_temp"] == 13.0
    assert state.attributes["ramp_remaining_hours"] == pytest.approx(24.0, abs=0.01)


async def test_cheese_chamber_lists_cheese_presets_only(hass: HomeAssistant, seed_states) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cave",
        data={
            CONF_NAME: "Cave",
            CONF_CHAMBER_KIND: CHAMBER_KIND_CHEESE,
            CONF_TEMP_SENSOR: TEMP_ENTITY,
            CONF_HUMIDITY_SENSOR: HUMIDITY_ENTITY,
        },
    )
    coordinator = await _setup(hass, entry, seed_states)
    ids = {p.id for p in coordinator.available_programs()}
    assert "cheese_washed" in ids
    assert "saucisson_sec" not in ids
    assert coordinator.chamber_kind == "cheese"
    assert coordinator.chamber_state()["kind"] == "cheese"
    # The tighter cheese condensation margin applies by default.
    assert coordinator.data["config"].condensation_margin == 0.5

    select = hass.states.get("select.cave_program")
    assert select is not None
    assert "cheese_pressed" in select.attributes["options"]
    assert "coppa" not in select.attributes["options"]
    # Starting a preset of the other kind is still possible by id (automations).
    await hass.services.async_call(
        DOMAIN, SERVICE_START_PROGRAM, {"program_id": "cheese_pressed"}, blocking=True
    )
    await hass.async_block_till_done()
    assert coordinator.data["phase_name"] == "surface_drying"
    await hass.services.async_call(
        DOMAIN, SERVICE_START_PROGRAM, {"program_id": "coppa"}, blocking=True
    )
    await hass.async_block_till_done()
    await coordinator.async_refresh()  # the service refresh is debounced
    select = hass.states.get("select.cave_program")
    assert select is not None
    assert select.state == "coppa"
    assert "coppa" in select.attributes["options"]


async def test_degraded_hours_counter(hass: HomeAssistant, seed_states) -> None:
    """A chamber with no actuator at all is in degraded mode as soon as it drifts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bare",
        data={
            CONF_NAME: "Bare",
            CONF_TEMP_SENSOR: TEMP_ENTITY,
            CONF_HUMIDITY_SENSOR: HUMIDITY_ENTITY,
        },
        options={CONF_DEGRADED_DELAY: 0, CONF_STARTUP_DELAY: 0},
    )
    coordinator = await _setup(hass, entry, seed_states)
    state = hass.states.get("sensor.bare_degraded_mode_hours")
    assert state is not None
    assert float(state.state) == 0.0

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_TARGETS, {"temperature": 5.0, "humidity": 75.0}, blocking=True
    )
    await hass.async_block_till_done()
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.manual_action_required
    state = hass.states.get("sensor.bare_degraded_mode_hours")
    assert state is not None
    assert float(state.state) > 0.0
    assert state.attributes["state_class"] == "total_increasing"


async def test_batch_starts_and_completes_its_program(
    hass: HomeAssistant, config_entry, seed_states
) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    await _create_batch(hass, program_id="lonzo", start_program=True)
    assert coordinator.program.status.value == "running"
    assert coordinator.program.state.program_id == "lonzo"
    batch_id = next(iter(coordinator.batches))

    # A second batch on the same program does not restart or disturb it.
    await _create_batch(hass, name="Coppa #2", program_id="coppa", start_program=True)
    assert coordinator.program.state.program_id == "lonzo"

    # Completing the reference batch ends the program (hold_last keeps targets).
    await hass.services.async_call(
        DOMAIN, SERVICE_COMPLETE_BATCH, {"batch_id": batch_id}, blocking=True
    )
    await hass.async_block_till_done()
    assert coordinator.program.status.value == "completed"
    await coordinator.async_refresh()
    assert coordinator.data["target_temp"] == 13.0  # last phase targets held


async def test_batch_reaching_target_completes_program(
    hass: HomeAssistant, config_entry, seed_states
) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    await _create_batch(hass, program_id="lonzo", start_program=True, target_loss_pct=10.0)
    batch_id = next(iter(coordinator.batches))
    await hass.services.async_call(
        DOMAIN, SERVICE_RECORD_WEIGHT, {"batch_id": batch_id, "weight": 890.0}, blocking=True
    )
    await hass.async_block_till_done()
    assert coordinator.batches[batch_id].status.value == "completed"
    assert coordinator.program.status.value == "completed"


async def test_batch_journal_services(hass: HomeAssistant, config_entry, seed_states) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    await _create_batch(hass, program_id="coppa")
    batch_id = next(iter(coordinator.batches))
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_BATCH_EVENT,
        {
            "batch_id": batch_id,
            "kind": "salting",
            "note": "2.8 %",
            "timestamp": "2026-10-01T10:00:00+00:00",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, SERVICE_ADD_BATCH_EVENT, {"batch_id": batch_id, "kind": "turned"}, blocking=True
    )
    await hass.async_block_till_done()
    batch = coordinator.batches[batch_id]
    assert [e.kind for e in batch.events] == ["salting", "turned"]
    assert batch.events[0].note == "2.8 %"

    export = await hass.services.async_call(
        DOMAIN, SERVICE_EXPORT_BATCH, {"batch_id": batch_id}, blocking=True, return_response=True
    )
    assert export["format"] == "curing_chamber/batch"
    assert export["program"]["id"] == "coppa"
    assert export["summary"]["event_count"] == 2
    assert export["batch"]["events"][1]["kind"] == "turned"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_BATCH_EVENT,
        {"batch_id": batch_id, "timestamp": "2026-10-01T10:00:00+00:00"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert [e.kind for e in coordinator.batches[batch_id].events] == ["turned"]

    with pytest.raises(HomeAssistantError, match="Unknown batch"):
        await hass.services.async_call(
            DOMAIN, SERVICE_ADD_BATCH_EVENT, {"batch_id": "nope", "kind": "x"}, blocking=True
        )
    with pytest.raises(HomeAssistantError, match="Unknown batch"):
        await hass.services.async_call(
            DOMAIN, SERVICE_EXPORT_BATCH, {"batch_id": "nope"}, blocking=True, return_response=True
        )


async def test_core_probe_delta_sensor_and_alert(hass: HomeAssistant, seed_states) -> None:
    core_entity = "sensor.chamber_core"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Core",
        data={
            CONF_NAME: "Core",
            CONF_TEMP_SENSOR: TEMP_ENTITY,
            CONF_HUMIDITY_SENSOR: HUMIDITY_ENTITY,
            CONF_PRODUCT_TEMP_SENSOR: core_entity,
        },
        options={"high_temp_drying_duration": 0, CONF_STARTUP_DELAY: 0},
    )
    hass.states.async_set(core_entity, "15.5", {"unit_of_measurement": "°C"})
    coordinator = await _setup(hass, entry, seed_states)
    assert coordinator.has_core_probe
    state = hass.states.get("sensor.core_core_temperature_delta")
    assert state is not None
    assert float(state.state) == 2.5
    assert state.attributes["core_temp"] == 15.5
    assert coordinator.chamber_state()["core_temp"] == 15.5

    hass.states.async_set(core_entity, "26", {"unit_of_measurement": "°C"})
    await coordinator.async_refresh()
    assert "core_temp_high" in coordinator.data["active_alerts"]
    alarm = hass.states.get("binary_sensor.core_out_of_range_alarm")
    assert alarm is not None
    assert alarm.state == "on"
