"""Pure (Home Assistant independent) regulation engine for Curing Chamber.

This package contains no ``homeassistant`` imports on purpose: the whole
control logic is unit-testable without a running Home Assistant instance.
Time is *injected* into every method (parameter ``now`` in seconds) so that
timing behaviour (compressor guard delays, anti-oscillation windows, degraded
mode timers) is fully deterministic in tests.
"""

from .engine import RegulationEngine
from .types import (
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

__all__ = [
    "Actuator",
    "Alert",
    "AlertKey",
    "AlertLevel",
    "Decision",
    "ManualAction",
    "RegulationConfig",
    "RegulationEngine",
    "RegulationInputs",
    "RegulationOutputs",
]
