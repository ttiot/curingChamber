"""Sensor faults (unavailable / frozen) force the safe state (§3)."""

from __future__ import annotations

from custom_components.curing_chamber.regulation import (
    Actuator,
    RegulationEngine,
    RegulationInputs,
)
from custom_components.curing_chamber.regulation.filters import SensorFilter
from custom_components.curing_chamber.regulation.types import AlertKey

from .conftest import make_config

PAST_STARTUP = 200.0


def test_unavailable_sensor_forces_all_off_and_critical_alert() -> None:
    cfg = make_config(Actuator.COOL, Actuator.HEAT, target_temp=13.0)
    eng = RegulationEngine(start=0.0)
    eng.tick(RegulationInputs(temp=18.0, temp_valid=True), cfg, PAST_STARTUP)  # cooling
    out = eng.tick(RegulationInputs(temp=None, temp_valid=False), cfg, PAST_STARTUP + 500)
    assert out.commands[Actuator.COOL] is False
    assert out.commands[Actuator.HEAT] is False
    assert out.safety_active is True
    assert any(a.key is AlertKey.SENSOR_FAULT_TEMP for a in out.alerts)


def test_frozen_sensor_detected_by_filter_triggers_safety() -> None:
    """A value that never changes for longer than the stale window is a fault."""
    filt = SensorFilter(samples=3, stale_seconds=1800.0)
    cfg = make_config(Actuator.COOL, target_temp=13.0)
    eng = RegulationEngine(start=0.0)

    # Feed a constant reading; before the stale window it is valid.
    res = filt.update(18.0, now=0.0)
    assert res.valid is True
    out = eng.tick(RegulationInputs(temp=res.value, temp_valid=res.valid), cfg, PAST_STARTUP)
    assert out.safety_active is False

    # Same value 31 minutes later -> stale -> invalid.
    res = filt.update(18.0, now=1860.0)
    assert res.stale is True
    assert res.valid is False
    out = eng.tick(RegulationInputs(temp=res.value, temp_valid=res.valid), cfg, PAST_STARTUP + 1860)
    assert out.safety_active is True
    assert out.commands[Actuator.COOL] is False


def test_door_open_pauses_regulation() -> None:
    cfg = make_config(Actuator.COOL, target_temp=13.0)
    eng = RegulationEngine(start=0.0)
    eng.tick(RegulationInputs(temp=18.0, temp_valid=True), cfg, PAST_STARTUP)
    out = eng.tick(
        RegulationInputs(temp=18.0, temp_valid=True, door_open=True), cfg, PAST_STARTUP + 10
    )
    assert out.commands[Actuator.COOL] is False
    assert out.paused is True


def test_absolute_high_limit_is_critical() -> None:
    cfg = make_config(Actuator.HEAT, target_temp=13.0, temp_abs_max=30.0)
    eng = RegulationEngine(start=0.0)
    out = eng.tick(RegulationInputs(temp=31.0, temp_valid=True), cfg, PAST_STARTUP)
    assert any(a.key is AlertKey.ABS_LIMIT_TEMP_HIGH for a in out.alerts)
    assert out.commands[Actuator.HEAT] is False  # aggravating actuator cut
