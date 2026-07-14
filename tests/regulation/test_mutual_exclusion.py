"""Mutual-exclusion invariants: never cool+heat, never humidify+dehumidify."""

from __future__ import annotations

from custom_components.curing_chamber.regulation import (
    Actuator,
    RegulationEngine,
    RegulationInputs,
)
from custom_components.curing_chamber.regulation.types import ActuatorConfig

from .conftest import make_config

PAST_STARTUP = 200.0


def _no_guard(*actuators: Actuator) -> dict[Actuator, ActuatorConfig]:
    return {a: ActuatorConfig(present=True, min_on=0, min_off=0) for a in actuators}


def test_never_cool_and_heat_together() -> None:
    cfg = make_config(
        Actuator.COOL, Actuator.HEAT, target_temp=13.0,
        actuators=_no_guard(Actuator.COOL, Actuator.HEAT),
    )
    eng = RegulationEngine(start=0.0)
    for now, temp in ((PAST_STARTUP, 18.0), (PAST_STARTUP + 10, 9.0), (PAST_STARTUP + 20, 18.0)):
        out = eng.tick(RegulationInputs(temp=temp, temp_valid=True), cfg, now)
        assert not (out.commands[Actuator.COOL] and out.commands[Actuator.HEAT])


def test_never_humidify_and_dehumidify_together() -> None:
    cfg = make_config(
        Actuator.HUMIDIFY, Actuator.DEHUMIDIFY, target_humidity=75.0,
        humidity_anti_oscillation=0.0,
        actuators=_no_guard(Actuator.HUMIDIFY, Actuator.DEHUMIDIFY),
    )
    eng = RegulationEngine(start=0.0)
    for now, hum in ((PAST_STARTUP, 60.0), (PAST_STARTUP + 10, 90.0)):
        out = eng.tick(RegulationInputs(humidity=hum, humidity_valid=True), cfg, now)
        assert not (out.commands[Actuator.HUMIDIFY] and out.commands[Actuator.DEHUMIDIFY])


def test_cooling_waits_for_heat_to_release() -> None:
    """Cool cannot start while heat is stuck ON by its own min_on guard."""
    cfg = make_config(
        Actuator.COOL, Actuator.HEAT, target_temp=13.0,
        actuators={
            Actuator.COOL: ActuatorConfig(present=True, min_on=0, min_off=0),
            Actuator.HEAT: ActuatorConfig(present=True, min_on=600, min_off=0),
        },
    )
    eng = RegulationEngine(start=0.0)
    eng.tick(RegulationInputs(temp=9.0, temp_valid=True), cfg, PAST_STARTUP)  # heat ON
    out = eng.tick(RegulationInputs(temp=20.0, temp_valid=True), cfg, PAST_STARTUP + 60)
    # Heat still locked ON (min_on 600s); cool must not co-run.
    assert out.commands[Actuator.HEAT] is True
    assert out.commands[Actuator.COOL] is False
