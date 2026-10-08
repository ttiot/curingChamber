"""Ineffective-actuator detection: running for long without effect."""

from __future__ import annotations

from custom_components.curing_chamber.regulation import (
    Actuator,
    AlertKey,
    RegulationEngine,
    RegulationInputs,
)

from .conftest import make_config

PAST = 10_000.0


def _cfg(**overrides: object):
    params: dict[str, object] = {
        "target_temp": 10.0,
        "target_humidity": 80.0,
        "actuator_ineffective_seconds": 1800.0,
    }
    params.update(overrides)
    return make_config(Actuator.COOL, Actuator.HUMIDIFY, **params)


def _inputs(temp: float, hum: float) -> RegulationInputs:
    return RegulationInputs(temp=temp, temp_valid=True, humidity=hum, humidity_valid=True)


def _keys(out):
    return {a.key for a in out.alerts if not a.resolved}


def test_cooling_without_effect_raises_then_clears() -> None:
    eng = RegulationEngine(start=0.0)
    cfg = _cfg()
    out = eng.tick(_inputs(15.0, 80.0), cfg, PAST)  # cooling switches on
    assert out.commands[Actuator.COOL]
    assert AlertKey.ACTUATOR_INEFFECTIVE_COOL not in _keys(out)
    out = eng.tick(_inputs(14.9, 80.0), cfg, PAST + 1700)  # not long enough yet
    assert AlertKey.ACTUATOR_INEFFECTIVE_COOL not in _keys(out)
    out = eng.tick(_inputs(14.9, 80.0), cfg, PAST + 1900)
    alert = next(a for a in out.alerts if a.key is AlertKey.ACTUATOR_INEFFECTIVE_COOL)
    assert alert.level.value == "warning"
    assert alert.params["start"] == 15.0
    assert alert.params["minutes"] == 32
    # The temperature finally drops: the alert resolves.
    out = eng.tick(_inputs(14.5, 80.0), cfg, PAST + 2000)
    assert any(a.key is AlertKey.ACTUATOR_INEFFECTIVE_COOL and a.resolved for a in out.alerts)


def test_effective_cooling_never_alerts() -> None:
    eng = RegulationEngine(start=0.0)
    cfg = _cfg()
    eng.tick(_inputs(15.0, 80.0), cfg, PAST)
    out = eng.tick(_inputs(14.0, 80.0), cfg, PAST + 3600)
    assert AlertKey.ACTUATOR_INEFFECTIVE_COOL not in _keys(out)


def test_humidifier_without_effect_alerts_on_humidity_delta() -> None:
    eng = RegulationEngine(start=0.0)
    cfg = _cfg()
    out = eng.tick(_inputs(10.0, 70.0), cfg, PAST)
    assert out.commands[Actuator.HUMIDIFY]
    out = eng.tick(_inputs(10.0, 71.0), cfg, PAST + 1900)  # +1 % only, delta is 2 %
    assert AlertKey.ACTUATOR_INEFFECTIVE_HUMIDIFY in _keys(out)
    assert AlertKey.ACTUATOR_INEFFECTIVE_COOL not in _keys(out)


def test_run_window_restarts_when_actuator_stops() -> None:
    eng = RegulationEngine(start=0.0)
    cfg = _cfg()
    eng.tick(_inputs(15.0, 80.0), cfg, PAST)
    eng.tick(_inputs(9.0, 80.0), cfg, PAST + 1000)  # target reached: cooling off
    assert not eng.state[Actuator.COOL]
    out = eng.tick(_inputs(15.0, 80.0), cfg, PAST + 2000)  # on again, fresh window
    assert out.commands[Actuator.COOL]
    out = eng.tick(_inputs(15.0, 80.0), cfg, PAST + 3000)
    assert AlertKey.ACTUATOR_INEFFECTIVE_COOL not in _keys(out)
    out = eng.tick(_inputs(15.0, 80.0), cfg, PAST + 3900)
    assert AlertKey.ACTUATOR_INEFFECTIVE_COOL in _keys(out)


def test_detection_disabled_with_zero_delay() -> None:
    eng = RegulationEngine(start=0.0)
    cfg = _cfg(actuator_ineffective_seconds=0.0)
    eng.tick(_inputs(15.0, 80.0), cfg, PAST)
    out = eng.tick(_inputs(15.0, 80.0), cfg, PAST + 99_999)
    assert AlertKey.ACTUATOR_INEFFECTIVE_COOL not in _keys(out)
