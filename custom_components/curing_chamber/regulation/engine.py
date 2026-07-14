"""The pure regulation engine (hysteresis + guards + coupling + degraded mode).

``RegulationEngine.tick`` is the single entry point. It is deterministic given
its inputs and the injected ``now`` timestamp; it holds only the minimal mutable
state required for timing guards and alert throttling. No Home Assistant import.
"""

from __future__ import annotations

from . import derived, filters
from .degraded import ConditionEvent, SustainedCondition
from .types import (
    MUTUAL_EXCLUSION,
    Actuator,
    Alert,
    AlertKey,
    AlertLevel,
    Decision,
    ManualAction,
    RegulationConfig,
    RegulationInputs,
    RegulationOutputs,
)

_NEG_INF = float("-inf")


class RegulationEngine:
    """Stateful, time-injected all-or-nothing regulator with hysteresis."""

    def __init__(self, start: float | None = None) -> None:
        self._start: float | None = start
        self._state: dict[Actuator, bool] = {}
        self._last_on: dict[Actuator, float] = {}
        self._last_off: dict[Actuator, float] = {}
        self._last_humidity_change: float | None = None
        self._conditions: dict[AlertKey, SustainedCondition] = {}
        self._last_decisions: list[Decision] = []

    # -- Public API ----------------------------------------------------------

    @property
    def state(self) -> dict[Actuator, bool]:
        """Return the last commanded on/off state per actuator."""
        return dict(self._state)

    @property
    def last_decisions(self) -> list[Decision]:
        """Return the decisions produced by the most recent tick."""
        return list(self._last_decisions)

    def sync_actual_state(self, actuator: Actuator, is_on: bool, now: float) -> None:
        """Reconcile internal state with a real (possibly manual) actuator state."""
        if self._state.get(actuator, False) != is_on:
            self._state[actuator] = is_on
            if is_on:
                self._last_on[actuator] = now
            else:
                self._last_off[actuator] = now

    def acknowledge(self, key: AlertKey) -> None:
        """Acknowledge an alert so its reminders stop until it clears."""
        cond = self._conditions.get(key)
        if cond is not None:
            cond.acknowledge()

    def tick(
        self, inputs: RegulationInputs, config: RegulationConfig, now: float
    ) -> RegulationOutputs:
        """Compute actuator commands and alerts for one control step."""
        if self._start is None:
            self._start = now
        out = RegulationOutputs()
        decisions: list[Decision] = []

        # Maintenance mode: everything off, no alerts at all (§7).
        if config.maintenance_mode:
            for actuator in self._configured(config):
                self._command(actuator, False, config, now, decisions, "maintenance", force=True)
            out.commands = {a: self._state.get(a, False) for a in self._configured(config)}
            out.summary = "maintenance"
            out.decisions = decisions
            self._last_decisions = decisions
            return out

        startup_blocking = (now - self._start) < config.startup_delay
        temp_required = config.target_temp is not None
        humidity_required = config.target_humidity is not None
        temp_bad = temp_required and not inputs.temp_valid
        humidity_bad = humidity_required and not inputs.humidity_valid
        sensor_fault = temp_bad or humidity_bad

        # --- Monitoring alerts (independent of command decisions) -----------
        self._sensor_fault_alerts(out, temp_bad, humidity_bad, config, now)
        self._divergence_alerts(out, inputs, config, now)
        self._door_alert(out, inputs, config, now)
        self._absolute_limit_alerts(out, inputs, config, now)
        self._quality_alerts(out, inputs, config, now)
        self._air_quality_alert(out, inputs, config, now)

        regulation_off = not config.regulation_enabled
        force_all_off = regulation_off or startup_blocking or sensor_fault or inputs.door_open

        if force_all_off:
            for actuator in self._configured(config):
                reason = (
                    "disabled"
                    if regulation_off
                    else "startup"
                    if startup_blocking
                    else "sensor_fault"
                    if sensor_fault
                    else "door_open"
                )
                self._command(actuator, False, config, now, decisions, reason, force=True)
            out.safety_active = sensor_fault or startup_blocking
            out.paused = inputs.door_open and not out.safety_active
            out.summary = (
                "disabled" if regulation_off else "safety" if out.safety_active else "paused"
            )
        else:
            self._regulate_temperature(out, inputs, config, now, decisions)
            self._regulate_humidity(out, inputs, config, now, decisions)
            self._regulate_fan_vent(out, inputs, config, now, decisions)
            self._degraded_mode(out, inputs, config, now)
            out.summary = self._summary(config)

        # Fill command map from final state for every configured actuator.
        out.commands = {a: self._state.get(a, False) for a in self._configured(config)}
        out.decisions = decisions
        self._last_decisions = decisions
        return out

    # -- Command helpers -----------------------------------------------------

    @staticmethod
    def _configured(config: RegulationConfig) -> list[Actuator]:
        return [a for a in Actuator if config.has(a)]

    @staticmethod
    def _hysteresis(
        value: float, target: float, deadband: float, decreasing: bool, current: bool
    ) -> bool:
        upper = target + deadband
        lower = target - deadband
        if decreasing:  # cool / dehumidify: ON when the quantity is too high
            if value >= upper:
                return True
            if value <= lower:
                return False
            return current
        # heat / humidify: ON when the quantity is too low
        if value <= lower:
            return True
        if value >= upper:
            return False
        return current

    def _command(
        self,
        actuator: Actuator,
        desired: bool,
        config: RegulationConfig,
        now: float,
        decisions: list[Decision],
        reason: str,
        *,
        force: bool = False,
    ) -> bool:
        """Apply timing guards, commit the new state, record a decision."""
        current = self._state.get(actuator, False)
        acfg = config.actuator(actuator)
        blocked: str | None = None
        result = desired

        if not force and desired != current:
            if desired and (now - self._last_off.get(actuator, _NEG_INF)) < acfg.min_off:
                result, blocked = current, "min_off"
            elif not desired and (now - self._last_on.get(actuator, _NEG_INF)) < acfg.min_on:
                result, blocked = current, "min_on"

        self._set_state(actuator, result, now)
        decisions.append(Decision(actuator, desired, reason, blocked))
        return result

    def _set_state(self, actuator: Actuator, value: bool, now: float) -> None:
        if value != self._state.get(actuator, False):
            if value:
                self._last_on[actuator] = now
            else:
                self._last_off[actuator] = now
            if actuator in (Actuator.HUMIDIFY, Actuator.DEHUMIDIFY):
                self._last_humidity_change = now
            self._state[actuator] = value

    def _enforce_exclusion(self, config: RegulationConfig, now: float) -> None:
        """Guarantee mutually-exclusive actuators are never both ON."""
        for a, b in MUTUAL_EXCLUSION:
            if self._state.get(a) and self._state.get(b):
                # Prefer keeping the one turned on more recently off-limits: turn
                # off the older one. Ties: turn off the increasing-temp side.
                on_a = self._last_on.get(a, _NEG_INF)
                on_b = self._last_on.get(b, _NEG_INF)
                loser = a if on_a <= on_b else b
                self._set_state(loser, False, now)

    # -- Temperature ---------------------------------------------------------

    def _regulate_temperature(
        self,
        out: RegulationOutputs,
        inputs: RegulationInputs,
        config: RegulationConfig,
        now: float,
        decisions: list[Decision],
    ) -> None:
        if config.target_temp is None or inputs.temp is None or not inputs.temp_valid:
            for actuator in (Actuator.COOL, Actuator.HEAT):
                if config.has(actuator):
                    self._command(actuator, False, config, now, decisions, "no_target")
            return

        temp = inputs.temp
        target = config.target_temp
        db = config.temp_deadband

        want_cool = config.has(Actuator.COOL) and self._hysteresis(
            temp, target, db, True, self._state.get(Actuator.COOL, False)
        )
        want_heat = config.has(Actuator.HEAT) and self._hysteresis(
            temp, target, db, False, self._state.get(Actuator.HEAT, False)
        )
        if temp > target:
            want_heat = False
        elif temp < target:
            want_cool = False

        # Absolute limits: cut the aggravating actuator (§5).
        if temp >= config.temp_abs_max:
            want_heat = False
        elif temp <= config.temp_abs_min:
            want_cool = False

        # Turn-off transitions first so an ON request can respect exclusion.
        if not want_heat and config.has(Actuator.HEAT):
            self._command(Actuator.HEAT, False, config, now, decisions, "temp")
        if not want_cool and config.has(Actuator.COOL):
            self._command(Actuator.COOL, False, config, now, decisions, "temp")
        if want_cool and not self._state.get(Actuator.HEAT):
            self._command(Actuator.COOL, True, config, now, decisions, "cooling")
        elif want_cool:
            decisions.append(Decision(Actuator.COOL, True, "cooling", "mutual_exclusion"))
        if want_heat and not self._state.get(Actuator.COOL):
            self._command(Actuator.HEAT, True, config, now, decisions, "heating")
        elif want_heat:
            decisions.append(Decision(Actuator.HEAT, True, "heating", "mutual_exclusion"))

        self._enforce_exclusion(config, now)

    # -- Humidity ------------------------------------------------------------

    def _regulate_humidity(
        self,
        out: RegulationOutputs,
        inputs: RegulationInputs,
        config: RegulationConfig,
        now: float,
        decisions: list[Decision],
    ) -> None:
        if config.target_humidity is None or inputs.humidity is None or not inputs.humidity_valid:
            for actuator in (Actuator.HUMIDIFY, Actuator.DEHUMIDIFY):
                if config.has(actuator):
                    self._command(actuator, False, config, now, decisions, "no_target")
            return

        hum = inputs.humidity
        target = config.target_humidity
        db = config.humidity_deadband

        want_hum = config.has(Actuator.HUMIDIFY) and self._hysteresis(
            hum, target, db, False, self._state.get(Actuator.HUMIDIFY, False)
        )
        want_dehum = config.has(Actuator.DEHUMIDIFY) and self._hysteresis(
            hum, target, db, True, self._state.get(Actuator.DEHUMIDIFY, False)
        )
        if hum > target:
            want_hum = False
        elif hum < target:
            want_dehum = False

        if hum >= config.humidity_abs_max:
            want_hum = False
        elif hum <= config.humidity_abs_min:
            want_dehum = False

        # Anti-oscillation: no humidity actuator may flip more than once per window.
        want_hum = self._anti_oscillation(Actuator.HUMIDIFY, want_hum, now, config, decisions)
        want_dehum = self._anti_oscillation(Actuator.DEHUMIDIFY, want_dehum, now, config, decisions)

        if not want_hum and config.has(Actuator.HUMIDIFY):
            self._command(Actuator.HUMIDIFY, False, config, now, decisions, "humidity")
        if not want_dehum and config.has(Actuator.DEHUMIDIFY):
            self._command(Actuator.DEHUMIDIFY, False, config, now, decisions, "humidity")
        if want_hum and not self._state.get(Actuator.DEHUMIDIFY):
            self._command(Actuator.HUMIDIFY, True, config, now, decisions, "humidifying")
        elif want_hum:
            decisions.append(Decision(Actuator.HUMIDIFY, True, "humidifying", "mutual_exclusion"))
        if want_dehum and not self._state.get(Actuator.HUMIDIFY):
            self._command(Actuator.DEHUMIDIFY, True, config, now, decisions, "drying")
        elif want_dehum:
            decisions.append(Decision(Actuator.DEHUMIDIFY, True, "drying", "mutual_exclusion"))

        self._enforce_exclusion(config, now)

    def _anti_oscillation(
        self,
        actuator: Actuator,
        desired: bool,
        now: float,
        config: RegulationConfig,
        decisions: list[Decision],
    ) -> bool:
        current = self._state.get(actuator, False)
        if (
            desired != current
            and self._last_humidity_change is not None
            and (now - self._last_humidity_change) < config.humidity_anti_oscillation
        ):
            decisions.append(Decision(actuator, desired, "humidity", "anti_oscillation"))
            return current
        return desired

    # -- Fan / vent ----------------------------------------------------------

    def _regulate_fan_vent(
        self,
        out: RegulationOutputs,
        inputs: RegulationInputs,
        config: RegulationConfig,
        now: float,
        decisions: list[Decision],
    ) -> None:
        active_regulation = any(
            self._state.get(a)
            for a in (Actuator.COOL, Actuator.HEAT, Actuator.HUMIDIFY, Actuator.DEHUMIDIFY)
        )
        if config.has(Actuator.FAN):
            if active_regulation:
                self._command(Actuator.FAN, True, config, now, decisions, "fan_forced")
            else:
                periodic = self._duty_cycle(now, config.fan_period, config.fan_run)
                self._command(Actuator.FAN, periodic, config, now, decisions, "fan_cycle")

        if config.has(Actuator.VENT):
            co2_high = inputs.co2 is not None and inputs.co2 >= config.co2_threshold
            periodic = self._duty_cycle(now, config.vent_period, config.vent_run)
            self._command(Actuator.VENT, co2_high or periodic, config, now, decisions, "vent")

    def _duty_cycle(self, now: float, period: float, run: float) -> bool:
        if period <= 0 or run <= 0 or self._start is None:
            return False
        return ((now - self._start) % period) < run

    # -- Degraded mode -------------------------------------------------------

    def _degraded_mode(
        self,
        out: RegulationOutputs,
        inputs: RegulationInputs,
        config: RegulationConfig,
        now: float,
    ) -> None:
        onset = config.degraded_delay
        remind = config.degraded_reminder

        if config.target_temp is not None and inputs.temp is not None and inputs.temp_valid:
            ext = config.temp_deadband * config.degraded_band_factor
            too_high = inputs.temp > config.target_temp + ext and not config.has(Actuator.COOL)
            too_low = inputs.temp < config.target_temp - ext and not config.has(Actuator.HEAT)
            self._handle(
                out,
                AlertKey.MANUAL_TEMP_HIGH,
                AlertLevel.WARNING,
                too_high,
                now,
                onset,
                remind,
                self._params(inputs.temp, config.target_temp),
                ManualAction.ADD_COOLING,
            )
            self._handle(
                out,
                AlertKey.MANUAL_TEMP_LOW,
                AlertLevel.WARNING,
                too_low,
                now,
                onset,
                remind,
                self._params(inputs.temp, config.target_temp),
                ManualAction.ADD_HEATING,
            )

        if (
            config.target_humidity is not None
            and inputs.humidity is not None
            and inputs.humidity_valid
        ):
            ext = config.humidity_deadband * config.degraded_band_factor
            too_high = inputs.humidity > config.target_humidity + ext and not config.has(
                Actuator.DEHUMIDIFY
            )
            too_low = inputs.humidity < config.target_humidity - ext and not config.has(
                Actuator.HUMIDIFY
            )
            self._handle(
                out,
                AlertKey.MANUAL_HUMIDITY_HIGH,
                AlertLevel.WARNING,
                too_high,
                now,
                onset,
                remind,
                self._params(inputs.humidity, config.target_humidity),
                ManualAction.REMOVE_HUMIDITY,
            )
            self._handle(
                out,
                AlertKey.MANUAL_HUMIDITY_LOW,
                AlertLevel.WARNING,
                too_low,
                now,
                onset,
                remind,
                self._params(inputs.humidity, config.target_humidity),
                ManualAction.ADD_HUMIDITY,
            )

    # -- Alert helpers -------------------------------------------------------

    @staticmethod
    def _params(value: float | None, target: float | None) -> dict[str, float | str]:
        params: dict[str, float | str] = {}
        if value is not None:
            params["value"] = round(value, 1)
        if target is not None:
            params["target"] = round(target, 1)
        return params

    def _condition(self, key: AlertKey, onset: float, reminder: float) -> SustainedCondition:
        cond = self._conditions.get(key)
        if cond is None:
            cond = SustainedCondition(onset, reminder)
            self._conditions[key] = cond
        else:
            cond.onset_delay = onset
            cond.reminder_interval = reminder
        return cond

    def _handle(
        self,
        out: RegulationOutputs,
        key: AlertKey,
        level: AlertLevel,
        active: bool,
        now: float,
        onset: float,
        reminder: float,
        params: dict[str, float | str],
        manual: ManualAction = ManualAction.NONE,
    ) -> None:
        event = self._condition(key, onset, reminder).update(active, now)
        if event is ConditionEvent.RAISE:
            out.alerts.append(Alert(key, level, params, manual))
        elif event is ConditionEvent.REMIND:
            out.alerts.append(Alert(key, level, params, manual, reminder=True))
        elif event is ConditionEvent.CLEAR:
            out.alerts.append(Alert(key, level, params, manual, resolved=True))

    def _sensor_fault_alerts(
        self,
        out: RegulationOutputs,
        temp_bad: bool,
        humidity_bad: bool,
        config: RegulationConfig,
        now: float,
    ) -> None:
        self._handle(
            out,
            AlertKey.SENSOR_FAULT_TEMP,
            AlertLevel.CRITICAL,
            temp_bad,
            now,
            0.0,
            config.degraded_reminder,
            {},
        )
        self._handle(
            out,
            AlertKey.SENSOR_FAULT_HUMIDITY,
            AlertLevel.CRITICAL,
            humidity_bad,
            now,
            0.0,
            config.degraded_reminder,
            {},
        )

    def _divergence_alerts(
        self,
        out: RegulationOutputs,
        inputs: RegulationInputs,
        config: RegulationConfig,
        now: float,
    ) -> None:
        t_div = filters.divergence(list(inputs.temp_probes))
        h_div = filters.divergence(list(inputs.humidity_probes))
        self._handle(
            out,
            AlertKey.SENSOR_DIVERGENCE_TEMP,
            AlertLevel.WARNING,
            len(inputs.temp_probes) >= 2 and t_div > config.sensor_divergence_temp,
            now,
            0.0,
            config.degraded_reminder,
            {"value": round(t_div, 1)},
        )
        self._handle(
            out,
            AlertKey.SENSOR_DIVERGENCE_HUMIDITY,
            AlertLevel.WARNING,
            len(inputs.humidity_probes) >= 2 and h_div > config.sensor_divergence_humidity,
            now,
            0.0,
            config.degraded_reminder,
            {"value": round(h_div, 1)},
        )

    def _door_alert(
        self,
        out: RegulationOutputs,
        inputs: RegulationInputs,
        config: RegulationConfig,
        now: float,
    ) -> None:
        self._handle(
            out,
            AlertKey.DOOR_OPEN_TOO_LONG,
            AlertLevel.WARNING,
            inputs.door_open,
            now,
            config.door_open_alert_seconds,
            config.degraded_reminder,
            {},
        )

    def _absolute_limit_alerts(
        self,
        out: RegulationOutputs,
        inputs: RegulationInputs,
        config: RegulationConfig,
        now: float,
    ) -> None:
        t, h = inputs.temp, inputs.humidity
        self._handle(
            out,
            AlertKey.ABS_LIMIT_TEMP_HIGH,
            AlertLevel.CRITICAL,
            t is not None and inputs.temp_valid and t >= config.temp_abs_max,
            now,
            0.0,
            config.degraded_reminder,
            {"value": round(t, 1) if t is not None else 0},
        )
        self._handle(
            out,
            AlertKey.ABS_LIMIT_TEMP_LOW,
            AlertLevel.CRITICAL,
            t is not None and inputs.temp_valid and t <= config.temp_abs_min,
            now,
            0.0,
            config.degraded_reminder,
            {"value": round(t, 1) if t is not None else 0},
        )
        self._handle(
            out,
            AlertKey.ABS_LIMIT_HUMIDITY_HIGH,
            AlertLevel.CRITICAL,
            h is not None and inputs.humidity_valid and h >= config.humidity_abs_max,
            now,
            0.0,
            config.degraded_reminder,
            {"value": round(h, 1) if h is not None else 0},
        )
        self._handle(
            out,
            AlertKey.ABS_LIMIT_HUMIDITY_LOW,
            AlertLevel.CRITICAL,
            h is not None and inputs.humidity_valid and h <= config.humidity_abs_min,
            now,
            0.0,
            config.degraded_reminder,
            {"value": round(h, 1) if h is not None else 0},
        )

    def _quality_alerts(
        self,
        out: RegulationOutputs,
        inputs: RegulationInputs,
        config: RegulationConfig,
        now: float,
    ) -> None:
        # High temperature during drying (§5 health risk).
        high_temp = (
            config.drying_phase
            and inputs.temp is not None
            and inputs.temp_valid
            and inputs.temp > config.high_temp_drying_limit
        )
        self._handle(
            out,
            AlertKey.HIGH_TEMP_DRYING,
            AlertLevel.CRITICAL,
            high_temp,
            now,
            config.high_temp_drying_duration,
            config.degraded_reminder,
            self._params(inputs.temp, config.high_temp_drying_limit),
        )

        # Case hardening: humidity durably below band, or drying too fast.
        hardening = False
        if (
            config.target_humidity is not None
            and inputs.humidity is not None
            and inputs.humidity_valid
        ):
            hardening = inputs.humidity < config.target_humidity - config.humidity_deadband
        if inputs.drying_rate is not None and inputs.drying_rate > config.case_hardening_rate:
            hardening = True
        self._handle(
            out,
            AlertKey.CASE_HARDENING,
            AlertLevel.WARNING,
            hardening,
            now,
            config.degraded_delay,
            config.degraded_reminder,
            {"rate": round(inputs.drying_rate, 2)} if inputs.drying_rate is not None else {},
        )

        # Condensation risk: chamber temperature close to dew point.
        condensation = False
        if (
            inputs.temp is not None
            and inputs.temp_valid
            and inputs.humidity is not None
            and inputs.humidity_valid
        ):
            dp = derived.dew_point(inputs.temp, inputs.humidity)
            condensation = (inputs.temp - dp) < config.condensation_margin
        self._handle(
            out,
            AlertKey.CONDENSATION_RISK,
            AlertLevel.WARNING,
            condensation,
            now,
            0.0,
            config.degraded_reminder,
            {},
        )

    def _air_quality_alert(
        self,
        out: RegulationOutputs,
        inputs: RegulationInputs,
        config: RegulationConfig,
        now: float,
    ) -> None:
        # Only when there is no vent actuator to act automatically.
        active = (
            not config.has(Actuator.VENT)
            and inputs.co2 is not None
            and inputs.co2 >= config.co2_threshold
        )
        self._handle(
            out,
            AlertKey.AIR_QUALITY,
            AlertLevel.WARNING,
            active,
            now,
            0.0,
            config.degraded_reminder,
            {"value": round(inputs.co2, 0)} if inputs.co2 is not None else {},
            ManualAction.VENTILATE,
        )

    def _summary(self, config: RegulationConfig) -> str:
        if self._state.get(Actuator.COOL):
            return "cooling"
        if self._state.get(Actuator.HEAT):
            return "heating"
        if self._state.get(Actuator.HUMIDIFY):
            return "humidifying"
        if self._state.get(Actuator.DEHUMIDIFY):
            return "drying"
        return "idle"
