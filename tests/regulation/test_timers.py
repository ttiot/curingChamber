"""Compressor protection and relay-chatter guard timings."""

from __future__ import annotations

from custom_components.curing_chamber.regulation import (
    Actuator,
    RegulationEngine,
    RegulationInputs,
)

from .conftest import make_config

HOT = RegulationInputs(temp=18.0, temp_valid=True)
COLD = RegulationInputs(temp=10.0, temp_valid=True)
IN_BAND = RegulationInputs(temp=13.0, temp_valid=True)


def test_startup_delay_blocks_all_commands() -> None:
    cfg = make_config(Actuator.COOL, target_temp=13.0, startup_delay=120.0)
    eng = RegulationEngine(start=0.0)
    out = eng.tick(HOT, cfg, now=0.0)
    assert out.commands[Actuator.COOL] is False
    assert out.safety_active is True
    out = eng.tick(HOT, cfg, now=119.0)
    assert out.commands[Actuator.COOL] is False
    out = eng.tick(HOT, cfg, now=121.0)
    assert out.commands[Actuator.COOL] is True


def test_min_on_keeps_compressor_running() -> None:
    cfg = make_config(Actuator.COOL, target_temp=13.0)  # cool min_on=180
    eng = RegulationEngine(start=0.0)
    eng.tick(HOT, cfg, now=200.0)  # compressor ON
    # Temp drops immediately; compressor must keep running for min_on seconds.
    out = eng.tick(COLD, cfg, now=300.0)
    assert out.commands[Actuator.COOL] is True
    blocked = [d.blocked_by for d in out.decisions if d.actuator is Actuator.COOL]
    assert "min_on" in blocked
    out = eng.tick(COLD, cfg, now=381.0)  # 181s after ON at t=200
    assert out.commands[Actuator.COOL] is False


def test_min_off_blocks_restart() -> None:
    cfg = make_config(Actuator.COOL, target_temp=13.0)  # min_off=420
    eng = RegulationEngine(start=0.0)
    eng.tick(HOT, cfg, now=200.0)  # ON at 200
    eng.tick(COLD, cfg, now=400.0)  # still ON (min_on)
    out = eng.tick(COLD, cfg, now=400.0)
    # Force it off after min_on:
    out = eng.tick(COLD, cfg, now=500.0)
    assert out.commands[Actuator.COOL] is False  # OFF at ~500
    # Now demand cooling again quickly -> blocked by min_off (420s from 500).
    out = eng.tick(HOT, cfg, now=700.0)
    assert out.commands[Actuator.COOL] is False
    assert "min_off" in [d.blocked_by for d in out.decisions if d.actuator is Actuator.COOL]
    out = eng.tick(HOT, cfg, now=925.0)  # 425s after OFF
    assert out.commands[Actuator.COOL] is True


def test_other_actuators_have_shorter_guards() -> None:
    cfg = make_config(Actuator.HUMIDIFY, target_humidity=75.0, humidity_anti_oscillation=0.0)
    eng = RegulationEngine(start=0.0)
    dry = RegulationInputs(humidity=60.0, humidity_valid=True)
    wet = RegulationInputs(humidity=90.0, humidity_valid=True)
    eng.tick(dry, cfg, now=200.0)  # humidify ON
    out = eng.tick(wet, cfg, now=240.0)  # 40s > min_on(30) -> can turn off
    assert out.commands[Actuator.HUMIDIFY] is False
