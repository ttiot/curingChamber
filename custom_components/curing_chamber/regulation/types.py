"""Data types for the pure regulation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Actuator(str, Enum):
    """The controllable actuators. All are optional in a given chamber."""

    COOL = "cool"
    HEAT = "heat"
    HUMIDIFY = "humidify"
    DEHUMIDIFY = "dehumidify"
    FAN = "fan"
    VENT = "vent"


#: Actuators that *decrease* their controlled quantity when running.
DECREASING: frozenset[Actuator] = frozenset({Actuator.COOL, Actuator.DEHUMIDIFY})
#: Actuators that *increase* their controlled quantity when running.
INCREASING: frozenset[Actuator] = frozenset({Actuator.HEAT, Actuator.HUMIDIFY})

#: Mutually exclusive actuator pairs (never both ON at once).
MUTUAL_EXCLUSION: tuple[tuple[Actuator, Actuator], ...] = (
    (Actuator.COOL, Actuator.HEAT),
    (Actuator.HUMIDIFY, Actuator.DEHUMIDIFY),
)


class AlertLevel(str, Enum):
    """Severity of an alert (§8)."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertKey(str, Enum):
    """Stable alert identifiers, mapped to translated messages."""

    SENSOR_FAULT_TEMP = "sensor_fault_temp"
    SENSOR_FAULT_HUMIDITY = "sensor_fault_humidity"
    SENSOR_DIVERGENCE_TEMP = "sensor_divergence_temp"
    SENSOR_DIVERGENCE_HUMIDITY = "sensor_divergence_humidity"
    ABS_LIMIT_TEMP_HIGH = "abs_limit_temp_high"
    ABS_LIMIT_TEMP_LOW = "abs_limit_temp_low"
    ABS_LIMIT_HUMIDITY_HIGH = "abs_limit_humidity_high"
    ABS_LIMIT_HUMIDITY_LOW = "abs_limit_humidity_low"
    HIGH_TEMP_DRYING = "high_temp_drying"
    CASE_HARDENING = "case_hardening"
    CONDENSATION_RISK = "condensation_risk"
    DOOR_OPEN_TOO_LONG = "door_open_too_long"
    AIR_QUALITY = "air_quality"
    MANUAL_TEMP_HIGH = "manual_temp_high"
    MANUAL_TEMP_LOW = "manual_temp_low"
    MANUAL_HUMIDITY_HIGH = "manual_humidity_high"
    MANUAL_HUMIDITY_LOW = "manual_humidity_low"


class ManualAction(str, Enum):
    """Recommended manual action when a quantity cannot be corrected (§5 bis)."""

    NONE = "none"
    ADD_HUMIDITY = "add_humidity"
    REMOVE_HUMIDITY = "remove_humidity"
    ADD_COOLING = "add_cooling"
    ADD_HEATING = "add_heating"
    VENTILATE = "ventilate"


@dataclass(frozen=True)
class ActuatorConfig:
    """Per-actuator presence and timing guards."""

    present: bool = False
    min_on: float = 0.0
    min_off: float = 0.0


@dataclass(frozen=True)
class RegulationConfig:
    """Full, immutable configuration for one regulation tick.

    Targets may be ``None`` when a phase only regulates one quantity, or in
    monitoring-only mode.
    """

    target_temp: float | None = None
    target_humidity: float | None = None

    temp_deadband: float = 0.5
    humidity_deadband: float = 3.0

    actuators: dict[Actuator, ActuatorConfig] = field(default_factory=dict)

    startup_delay: float = 120.0
    humidity_anti_oscillation: float = 600.0

    temp_abs_min: float = 0.0
    temp_abs_max: float = 30.0
    humidity_abs_min: float = 40.0
    humidity_abs_max: float = 99.0

    sensor_divergence_temp: float = 2.0
    sensor_divergence_humidity: float = 8.0

    degraded_band_factor: float = 2.0
    degraded_delay: float = 900.0
    degraded_reminder: float = 7200.0

    door_open_alert_seconds: float = 300.0

    case_hardening_rate: float = 1.5
    high_temp_drying_limit: float = 16.0
    high_temp_drying_duration: float = 7200.0
    condensation_margin: float = 1.0

    fan_period: float = 1800.0
    fan_run: float = 300.0
    vent_period: float = 21600.0
    vent_run: float = 300.0
    co2_threshold: float = 1500.0

    regulation_enabled: bool = True
    maintenance_mode: bool = False
    drying_phase: bool = False

    def has(self, actuator: Actuator) -> bool:
        """Return whether ``actuator`` is configured for this chamber."""
        cfg = self.actuators.get(actuator)
        return bool(cfg and cfg.present)

    def actuator(self, actuator: Actuator) -> ActuatorConfig:
        """Return the config for ``actuator`` (default: absent)."""
        return self.actuators.get(actuator, ActuatorConfig())


@dataclass(frozen=True)
class RegulationInputs:
    """Processed sensor snapshot handed to the engine.

    Values are already averaged/filtered by the adaptation layer. ``*_valid``
    flags carry the "sensor available and not stale" decision so the engine
    never regulates blind (§3).
    """

    temp: float | None = None
    temp_valid: bool = False
    humidity: float | None = None
    humidity_valid: bool = False

    #: Raw per-probe readings (for divergence detection), optional.
    temp_probes: tuple[float, ...] = ()
    humidity_probes: tuple[float, ...] = ()

    door_open: bool = False
    weight: float | None = None
    co2: float | None = None
    product_temp: float | None = None

    #: Estimated drying rate in %/day (from the scale), optional.
    drying_rate: float | None = None

    #: Actual on/off state of each actuator entity, when known.
    actuator_states: dict[Actuator, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    """A per-actuator decision, for observability (§9)."""

    actuator: Actuator
    desired: bool
    reason: str
    blocked_by: str | None = None


@dataclass(frozen=True)
class Alert:
    """An alert raised by the engine, mapped to a translated notification."""

    key: AlertKey
    level: AlertLevel
    params: dict[str, float | str] = field(default_factory=dict)
    manual_action: ManualAction = ManualAction.NONE
    #: True when this alert reports a condition returning to normal (§5).
    resolved: bool = False
    #: True for a reminder re-notification of an already-active alert (§5).
    reminder: bool = False


@dataclass
class RegulationOutputs:
    """Result of one engine tick."""

    commands: dict[Actuator, bool] = field(default_factory=dict)
    decisions: list[Decision] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
    safety_active: bool = False
    paused: bool = False
    summary: str = "idle"
