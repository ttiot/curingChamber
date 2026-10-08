"""Fan/vent cycling, air renewal and quality alerts (condensation, hardening)."""

from __future__ import annotations

from custom_components.curing_chamber.regulation import (
    Actuator,
    RegulationEngine,
    RegulationInputs,
)
from custom_components.curing_chamber.regulation.types import (
    ActuatorConfig,
    AlertKey,
    ManualAction,
)

from .conftest import make_config

PAST = 200.0


def test_fan_runs_during_active_regulation() -> None:
    cfg = make_config(
        Actuator.COOL,
        Actuator.FAN,
        target_temp=13.0,
        actuators={
            Actuator.COOL: ActuatorConfig(present=True, min_on=0, min_off=0),
            Actuator.FAN: ActuatorConfig(present=True, min_on=0, min_off=0),
        },
    )
    eng = RegulationEngine(start=0.0)
    out = eng.tick(RegulationInputs(temp=18.0, temp_valid=True), cfg, PAST)
    assert out.commands[Actuator.COOL] is True
    assert out.commands[Actuator.FAN] is True  # forced for stirring


def test_fan_duty_cycle_when_idle() -> None:
    cfg = make_config(
        Actuator.FAN,
        target_temp=13.0,
        fan_period=1800.0,
        fan_run=300.0,
        startup_delay=0.0,
        actuators={Actuator.FAN: ActuatorConfig(present=True, min_on=0, min_off=0)},
    )
    eng = RegulationEngine(start=0.0)
    # In band -> no active regulation; fan follows the periodic duty cycle.
    on = eng.tick(RegulationInputs(temp=13.0, temp_valid=True), cfg, 100.0)  # 100 < 300
    off = eng.tick(RegulationInputs(temp=13.0, temp_valid=True), cfg, 600.0)  # 600 > 300
    assert on.commands[Actuator.FAN] is True
    assert off.commands[Actuator.FAN] is False


def test_vent_triggered_by_co2() -> None:
    cfg = make_config(
        Actuator.VENT,
        target_temp=13.0,
        co2_threshold=1500.0,
        vent_period=1e9,
        vent_run=1.0,
        actuators={Actuator.VENT: ActuatorConfig(present=True, min_on=0, min_off=0)},
    )
    eng = RegulationEngine(start=0.0)
    out = eng.tick(RegulationInputs(temp=13.0, temp_valid=True, co2=1800.0), cfg, PAST)
    assert out.commands[Actuator.VENT] is True


def test_air_quality_alert_without_vent() -> None:
    cfg = make_config(target_temp=13.0, co2_threshold=1500.0)
    eng = RegulationEngine(start=0.0)
    out = eng.tick(RegulationInputs(temp=13.0, temp_valid=True, co2=1800.0), cfg, PAST)
    alert = next(a for a in out.alerts if a.key is AlertKey.AIR_QUALITY)
    assert alert.manual_action is ManualAction.VENTILATE


def test_condensation_alert() -> None:
    cfg = make_config(Actuator.COOL, target_temp=13.0, condensation_margin=1.0)
    eng = RegulationEngine(start=0.0)
    # 99 %RH at 13 degC -> dew point ~ air temp -> condensation risk.
    out = eng.tick(
        RegulationInputs(temp=13.0, temp_valid=True, humidity=99.0, humidity_valid=True),
        cfg,
        PAST,
    )
    assert any(a.key is AlertKey.CONDENSATION_RISK for a in out.alerts)


def test_case_hardening_on_fast_drying() -> None:
    cfg = make_config(
        Actuator.COOL,
        target_temp=13.0,
        case_hardening_rate=1.5,
        degraded_delay=0.0,
    )
    eng = RegulationEngine(start=0.0)
    out = eng.tick(
        RegulationInputs(temp=13.0, temp_valid=True, drying_rate=3.0),
        cfg,
        PAST,
    )
    assert any(a.key is AlertKey.CASE_HARDENING for a in out.alerts)


def test_high_temp_drying_alert() -> None:
    cfg = make_config(
        Actuator.HEAT,
        target_temp=13.0,
        drying_phase=True,
        high_temp_drying_limit=16.0,
        high_temp_drying_duration=0.0,
    )
    eng = RegulationEngine(start=0.0)
    out = eng.tick(RegulationInputs(temp=17.0, temp_valid=True), cfg, PAST)
    assert any(a.key is AlertKey.HIGH_TEMP_DRYING for a in out.alerts)


def test_manual_temp_high_when_no_cooling() -> None:
    cfg = make_config(
        Actuator.HEAT,
        target_temp=13.0,
        temp_deadband=0.5,
        degraded_band_factor=2.0,
        degraded_delay=0.0,
    )
    eng = RegulationEngine(start=0.0)
    out = eng.tick(RegulationInputs(temp=15.0, temp_valid=True), cfg, PAST)
    alert = next(a for a in out.alerts if a.key is AlertKey.MANUAL_TEMP_HIGH)
    assert alert.manual_action is ManualAction.ADD_COOLING


def test_maintenance_mode_all_off_no_alerts() -> None:
    cfg = make_config(Actuator.COOL, target_temp=13.0, maintenance_mode=True)
    eng = RegulationEngine(start=0.0)
    out = eng.tick(RegulationInputs(temp=None, temp_valid=False), cfg, PAST)
    assert out.commands[Actuator.COOL] is False
    assert out.alerts == []
    assert out.summary == "maintenance"


def test_divergence_alert_between_probes() -> None:
    cfg = make_config(Actuator.COOL, target_temp=13.0, sensor_divergence_temp=2.0)
    eng = RegulationEngine(start=0.0)
    out = eng.tick(
        RegulationInputs(
            temp=13.0,
            temp_valid=True,
            temp_probes=(12.0, 16.0),
        ),
        cfg,
        PAST,
    )
    assert any(a.key is AlertKey.SENSOR_DIVERGENCE_TEMP for a in out.alerts)


def test_sync_actual_state_reflects_manual_override() -> None:
    eng = RegulationEngine(start=0.0)
    eng.sync_actual_state(Actuator.COOL, True, now=PAST)
    assert eng.state[Actuator.COOL] is True


def test_core_temp_high_alert() -> None:
    cfg = make_config(Actuator.COOL, target_temp=13.0, core_temp_max=24.0)
    eng = RegulationEngine(start=0.0)
    # Below the limit: nothing. Above it: critical after high_temp_drying_duration.
    out = eng.tick(RegulationInputs(temp=13.0, temp_valid=True, product_temp=20.0), cfg, PAST)
    assert not any(a.key is AlertKey.CORE_TEMP_HIGH for a in out.alerts)
    cfg = make_config(
        Actuator.COOL, target_temp=13.0, core_temp_max=24.0, high_temp_drying_duration=0.0
    )
    out = eng.tick(RegulationInputs(temp=13.0, temp_valid=True, product_temp=25.5), cfg, PAST)
    alert = next(a for a in out.alerts if a.key is AlertKey.CORE_TEMP_HIGH)
    assert alert.level.value == "critical"
    assert alert.params["value"] == 25.5
