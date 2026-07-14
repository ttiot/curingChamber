"""Sensor conditioning: light noise filtering and stale-value detection.

Pure logic, time injected. The adaptation layer feeds raw readings in and gets
back a filtered value plus a validity decision, which it forwards to the engine
as :class:`RegulationInputs`.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class SensorResult:
    """Outcome of conditioning a sensor stream."""

    value: float | None
    valid: bool
    stale: bool


class SensorFilter:
    """Rolling filter for one numeric sensor.

    * Keeps a rolling window and returns its mean to damp measurement spikes.
    * Flags the value as *stale* when it has not changed for ``stale_seconds``
      (frozen probe), which the engine treats as a fault (§3).
    """

    def __init__(self, samples: int = 3, stale_seconds: float = 1800.0) -> None:
        self._window: deque[float] = deque(maxlen=max(1, samples))
        self._stale_seconds = stale_seconds
        self._last_raw: float | None = None
        self._last_change_at: float | None = None

    def reset(self) -> None:
        """Clear all buffered state."""
        self._window.clear()
        self._last_raw = None
        self._last_change_at = None

    def update(self, raw: float | None, now: float) -> SensorResult:
        """Feed a new raw reading (or ``None`` if unavailable) at time ``now``."""
        if raw is None:
            # Unavailable/unknown: invalidate immediately, keep history cleared.
            self._window.clear()
            self._last_raw = None
            self._last_change_at = None
            return SensorResult(value=None, valid=False, stale=False)

        if self._last_raw is None or raw != self._last_raw:
            self._last_change_at = now
        self._last_raw = raw
        self._window.append(raw)

        if self._last_change_at is None:
            self._last_change_at = now
        stale = (now - self._last_change_at) >= self._stale_seconds
        value = sum(self._window) / len(self._window)
        return SensorResult(value=value, valid=not stale, stale=stale)


def average(values: list[float]) -> float | None:
    """Return the mean of ``values`` or ``None`` when empty."""
    if not values:
        return None
    return sum(values) / len(values)


def divergence(values: list[float]) -> float:
    """Return max-min spread of ``values`` (0 when fewer than two)."""
    if len(values) < 2:
        return 0.0
    return max(values) - min(values)
