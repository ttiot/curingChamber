"""Hysteresis behaviour of the all-or-nothing regulator."""

from __future__ import annotations

from custom_components.curing_chamber.regulation import (
    Actuator,
    RegulationEngine,
    RegulationInputs,
)
from custom_components.curing_chamber.regulation.types import ActuatorConfig

from .conftest import make_config

PAST_STARTUP = 200.0


def test_cool_turns_on_above_upper_band() -> None:
    cfg = make_config(Actuator.COOL, target_temp=13.0, temp_deadband=0.5)
    eng = RegulationEngine(start=0.0)
    out = eng.tick(RegulationInputs(temp=13.6, temp_valid=True), cfg, PAST_STARTUP)
    assert out.commands[Actuator.COOL] is True


def test_cool_stays_off_within_band() -> None:
    cfg = make_config(Actuator.COOL, target_temp=13.0, temp_deadband=0.5)
    eng = RegulationEngine(start=0.0)
    out = eng.tick(RegulationInputs(temp=13.2, temp_valid=True), cfg, PAST_STARTUP)
    assert out.commands[Actuator.COOL] is False


def test_cool_maintains_state_inside_band() -> None:
    """Once cooling, it keeps cooling until it drops below the lower band."""
    cfg = make_config(
        Actuator.COOL, target_temp=13.0, temp_deadband=0.5,
        actuators={Actuator.COOL: ActuatorConfig(present=True, min_on=0, min_off=0)},
    )
    eng = RegulationEngine(start=0.0)
    eng.tick(RegulationInputs(temp=13.6, temp_valid=True), cfg, PAST_STARTUP)  # on
    out = eng.tick(RegulationInputs(temp=13.2, temp_valid=True), cfg, PAST_STARTUP + 10)
    assert out.commands[Actuator.COOL] is True  # still in band -> hold on
    out = eng.tick(RegulationInputs(temp=12.4, temp_valid=True), cfg, PAST_STARTUP + 20)
    assert out.commands[Actuator.COOL] is False  # crossed lower band -> off


def test_heat_turns_on_below_lower_band() -> None:
    cfg = make_config(Actuator.HEAT, target_temp=13.0, temp_deadband=0.5)
    eng = RegulationEngine(start=0.0)
    out = eng.tick(RegulationInputs(temp=12.4, temp_valid=True), cfg, PAST_STARTUP)
    assert out.commands[Actuator.HEAT] is True


def test_humidifier_hysteresis() -> None:
    cfg = make_config(Actuator.HUMIDIFY, target_humidity=75.0, humidity_deadband=3.0)
    eng = RegulationEngine(start=0.0)
    out = eng.tick(RegulationInputs(humidity=71.0, humidity_valid=True), cfg, PAST_STARTUP)
    assert out.commands[Actuator.HUMIDIFY] is True
    out = eng.tick(RegulationInputs(humidity=79.0, humidity_valid=True), cfg, PAST_STARTUP + 700)
    assert out.commands[Actuator.HUMIDIFY] is False


def test_dehumidifier_turns_on_above_band() -> None:
    cfg = make_config(Actuator.DEHUMIDIFY, target_humidity=75.0, humidity_deadband=3.0)
    eng = RegulationEngine(start=0.0)
    out = eng.tick(RegulationInputs(humidity=79.0, humidity_valid=True), cfg, PAST_STARTUP)
    assert out.commands[Actuator.DEHUMIDIFY] is True
