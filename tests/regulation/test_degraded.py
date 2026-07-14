"""Degraded mode, anti-spam reminders and automatic resolution (§5)."""

from __future__ import annotations

from custom_components.curing_chamber.regulation import (
    Actuator,
    RegulationEngine,
    RegulationInputs,
)
from custom_components.curing_chamber.regulation.types import AlertKey

from .conftest import make_config


def _cfg() -> object:
    return make_config(
        Actuator.COOL,
        target_temp=13.0,
        target_humidity=75.0,
        humidity_deadband=3.0,
        degraded_band_factor=2.0,
        degraded_delay=900.0,
        degraded_reminder=7200.0,
    )


def _dry(temp: float = 13.0) -> RegulationInputs:
    return RegulationInputs(temp=temp, temp_valid=True, humidity=60.0, humidity_valid=True)


def test_first_notification_after_onset_then_reminder() -> None:
    cfg = _cfg()
    eng = RegulationEngine(start=0.0)
    eng.tick(_dry(), cfg, 200.0)  # onset starts
    out = eng.tick(_dry(), cfg, 200.0 + 901)  # first alert
    assert any(a.key is AlertKey.MANUAL_HUMIDITY_LOW and not a.resolved for a in out.alerts)
    # No reminder before the interval.
    out = eng.tick(_dry(), cfg, 200.0 + 901 + 3600)
    assert not any(a.key is AlertKey.MANUAL_HUMIDITY_LOW for a in out.alerts)
    # Reminder after the interval.
    out = eng.tick(_dry(), cfg, 200.0 + 901 + 7300)
    reminder = next(a for a in out.alerts if a.key is AlertKey.MANUAL_HUMIDITY_LOW)
    assert reminder.reminder is True


def test_resolution_emitted_when_back_in_band() -> None:
    cfg = _cfg()
    eng = RegulationEngine(start=0.0)
    eng.tick(_dry(), cfg, 200.0)
    eng.tick(_dry(), cfg, 200.0 + 901)  # raised
    ok = RegulationInputs(temp=13.0, temp_valid=True, humidity=75.0, humidity_valid=True)
    out = eng.tick(ok, cfg, 200.0 + 1000)
    resolved = next(a for a in out.alerts if a.key is AlertKey.MANUAL_HUMIDITY_LOW)
    assert resolved.resolved is True


def test_acknowledge_silences_reminders() -> None:
    cfg = _cfg()
    eng = RegulationEngine(start=0.0)
    eng.tick(_dry(), cfg, 200.0)
    eng.tick(_dry(), cfg, 200.0 + 901)  # raised
    eng.acknowledge(AlertKey.MANUAL_HUMIDITY_LOW)
    out = eng.tick(_dry(), cfg, 200.0 + 901 + 8000)  # past reminder interval
    assert not any(a.key is AlertKey.MANUAL_HUMIDITY_LOW for a in out.alerts)


def test_no_degraded_when_actuator_available() -> None:
    """With a humidifier present, low humidity is correctable -> no manual alert."""
    cfg = make_config(
        Actuator.COOL,
        Actuator.HUMIDIFY,
        target_temp=13.0,
        target_humidity=75.0,
        degraded_delay=900.0,
    )
    eng = RegulationEngine(start=0.0)
    eng.tick(_dry(), cfg, 200.0)
    out = eng.tick(_dry(), cfg, 200.0 + 2000)
    assert not any(a.key is AlertKey.MANUAL_HUMIDITY_LOW for a in out.alerts)
