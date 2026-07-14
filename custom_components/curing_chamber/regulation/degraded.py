"""Sustained-condition tracking with onset delay, reminders and resolution.

This is the anti-spam core (§5): the first notification fires once a condition
has held for ``onset_delay``; while it stays active an unacknowledged condition
reminds every ``reminder_interval``; when it clears a one-shot resolution event
is produced ("back to normal"). Fully time-injected and pure.
"""

from __future__ import annotations

from enum import Enum, auto


class ConditionEvent(Enum):
    """What happened to a tracked condition on a given update."""

    NONE = auto()
    RAISE = auto()
    REMIND = auto()
    CLEAR = auto()


class SustainedCondition:
    """Track a boolean condition over time.

    Parameters
    ----------
    onset_delay:
        Seconds the condition must stay active before it first fires.
    reminder_interval:
        Seconds between reminders while active and unacknowledged. ``0`` means
        no reminders (fire once, then wait for resolution).
    """

    def __init__(self, onset_delay: float = 0.0, reminder_interval: float = 0.0) -> None:
        self.onset_delay = onset_delay
        self.reminder_interval = reminder_interval
        self.active_since: float | None = None
        self.triggered = False
        self.acknowledged = False
        self._last_notified: float | None = None

    def acknowledge(self) -> None:
        """Silence reminders until the condition clears and re-arms."""
        if self.triggered:
            self.acknowledged = True

    def update(self, active: bool, now: float) -> ConditionEvent:
        """Advance the tracker with the current ``active`` state at ``now``."""
        if active:
            if self.active_since is None:
                self.active_since = now
            elapsed = now - self.active_since
            if not self.triggered and elapsed >= self.onset_delay:
                self.triggered = True
                self._last_notified = now
                return ConditionEvent.RAISE
            if (
                self.triggered
                and not self.acknowledged
                and self.reminder_interval > 0
                and self._last_notified is not None
                and (now - self._last_notified) >= self.reminder_interval
            ):
                self._last_notified = now
                return ConditionEvent.REMIND
            return ConditionEvent.NONE

        was_triggered = self.triggered
        self.active_since = None
        self.triggered = False
        self.acknowledged = False
        self._last_notified = None
        return ConditionEvent.CLEAR if was_triggered else ConditionEvent.NONE

    @property
    def is_active(self) -> bool:
        """Whether the condition has fired and not yet cleared."""
        return self.triggered
