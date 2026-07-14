"""Temperature priority over humidity and the T/HR coupling behaviour."""

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

PAST_STARTUP = 200.0


def test_temperature_regulated_even_when_humidity_cannot_be_held() -> None:
    """Cool-only chamber: cooling runs; humidity has no actuator to correct it."""
    cfg = make_config(
        Actuator.COOL, target_temp=13.0, target_humidity=75.0,
        degraded_delay=900.0,
    )
    eng = RegulationEngine(start=0.0)
    out = eng.tick(
        RegulationInputs(temp=18.0, temp_valid=True, humidity=60.0, humidity_valid=True),
        cfg, PAST_STARTUP,
    )
    assert out.commands[Actuator.COOL] is True  # temperature acted on


def test_humidity_falls_to_degraded_mode_when_uncorrectable() -> None:
    cfg = make_config(
        Actuator.COOL, target_temp=13.0, target_humidity=75.0,
        humidity_deadband=3.0, degraded_band_factor=2.0, degraded_delay=900.0,
    )
    eng = RegulationEngine(start=0.0)
    inp = RegulationInputs(temp=13.0, temp_valid=True, humidity=60.0, humidity_valid=True)
    # Below extended band (75 - 6 = 69) but not yet past the onset delay.
    out = eng.tick(inp, cfg, PAST_STARTUP)
    assert not any(a.key is AlertKey.MANUAL_HUMIDITY_LOW for a in out.alerts)
    # After the degraded delay elapses -> manual action alert.
    out = eng.tick(inp, cfg, PAST_STARTUP + 901)
    alert = next(a for a in out.alerts if a.key is AlertKey.MANUAL_HUMIDITY_LOW)
    assert alert.manual_action is ManualAction.ADD_HUMIDITY
    assert alert.params["value"] == 60.0
    assert alert.params["target"] == 75.0


def test_anti_oscillation_limits_humidity_flips() -> None:
    cfg = make_config(
        Actuator.HUMIDIFY, target_humidity=75.0, humidity_deadband=3.0,
        humidity_anti_oscillation=600.0,
        actuators={Actuator.HUMIDIFY: ActuatorConfig(present=True, min_on=0, min_off=0)},
    )
    eng = RegulationEngine(start=0.0)
    dry = RegulationInputs(humidity=60.0, humidity_valid=True)
    wet = RegulationInputs(humidity=90.0, humidity_valid=True)
    eng.tick(dry, cfg, PAST_STARTUP)  # humidify ON, change recorded
    # Within the anti-oscillation window it must not switch off.
    out = eng.tick(wet, cfg, PAST_STARTUP + 100)
    assert out.commands[Actuator.HUMIDIFY] is True
    assert "anti_oscillation" in [
        d.blocked_by for d in out.decisions if d.actuator is Actuator.HUMIDIFY
    ]
    # After the window it may switch.
    out = eng.tick(wet, cfg, PAST_STARTUP + 700)
    assert out.commands[Actuator.HUMIDIFY] is False
