"""Shared helpers for the pure regulation-engine tests."""

from __future__ import annotations

from custom_components.curing_chamber.regulation import Actuator, RegulationConfig
from custom_components.curing_chamber.regulation.types import ActuatorConfig


def make_config(*actuators: Actuator, **overrides: object) -> RegulationConfig:
    """Build a config with the given actuators present and sane test defaults.

    Compressor guard delays default to short values so tests can advance time in
    small steps; individual tests override what they exercise.
    """
    acts: dict[Actuator, ActuatorConfig] = {}
    for actuator in actuators:
        if actuator is Actuator.COOL:
            acts[actuator] = ActuatorConfig(present=True, min_on=180, min_off=420)
        else:
            acts[actuator] = ActuatorConfig(present=True, min_on=30, min_off=30)
    defaults: dict[str, object] = {
        "actuators": acts,
        "startup_delay": 120.0,
        "humidity_anti_oscillation": 600.0,
    }
    defaults.update(overrides)
    return RegulationConfig(**defaults)  # type: ignore[arg-type]
