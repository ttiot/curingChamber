"""Data types for the drying-program engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EndKind(StrEnum):
    """How a phase ends."""

    DURATION = "duration"
    WEIGHT_LOSS = "weight_loss"
    CORE_TEMP = "core_temp"
    MANUAL = "manual"


class OnComplete(StrEnum):
    """What to do when the whole program finishes."""

    HOLD_LAST = "hold_last"
    STOP = "stop"


class ProgramStatus(StrEnum):
    """Runtime status of the program engine."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class ProgramCategory(StrEnum):
    """Product family a program is written for (presets are filtered by it)."""

    CHARCUTERIE = "charcuterie"
    CHEESE = "cheese"


class ProgramEventType(StrEnum):
    """Events emitted by the engine for the HA bus / notifications."""

    PHASE_STARTED = "phase_started"
    PHASE_ENDED = "phase_ended"
    PROGRAM_COMPLETED = "program_completed"


@dataclass(frozen=True)
class Phase:
    """One phase of a drying program.

    A phase may regulate temperature only, humidity only, or both. The end
    condition is one of duration / weight loss / manual; ``duration_hours`` also
    acts as a safety cap for a ``WEIGHT_LOSS`` phase (the "~N weeks" fallback
    used by the presets, and the fallback when no scale is available).

    A ``CORE_TEMP`` phase ends when the product core temperature reaches
    ``core_temp_target`` (crossing it from where it stood at phase start, in
    either direction); ``duration_hours`` is again the safety cap / fallback
    without a core probe.

    A phase may start with a **ramp**: when ``ramp_hours`` is set, the active
    targets move linearly from ``start_temp`` / ``start_humidity`` (each
    optional; a missing start value means that quantity is not ramped) to
    ``target_temp`` / ``target_humidity`` over the first ``ramp_hours`` hours of
    the phase (paused time excluded), then hold the final targets.
    """

    name: str
    target_temp: float | None = None
    target_humidity: float | None = None
    end_kind: EndKind = EndKind.DURATION
    duration_hours: float | None = None
    weight_loss_pct: float | None = None
    notify_end: bool = True
    start_temp: float | None = None
    start_humidity: float | None = None
    ramp_hours: float | None = None
    core_temp_target: float | None = None

    @property
    def has_ramp(self) -> bool:
        """True when the phase ramps at least one target."""
        return (
            self.ramp_hours is not None
            and self.ramp_hours > 0
            and (
                (self.start_temp is not None and self.target_temp is not None)
                or (self.start_humidity is not None and self.target_humidity is not None)
            )
        )

    def ramp_remaining(self, elapsed_seconds: float) -> float | None:
        """Seconds left in the ramp, ``None`` when the phase has no ramp."""
        if not self.has_ramp:
            return None
        assert self.ramp_hours is not None
        return max(0.0, self.ramp_hours * 3600.0 - elapsed_seconds)

    def targets_at(self, elapsed_seconds: float) -> tuple[float | None, float | None]:
        """Effective (temp, humidity) targets ``elapsed_seconds`` into the phase."""
        if not self.has_ramp:
            return (self.target_temp, self.target_humidity)
        assert self.ramp_hours is not None
        fraction = min(1.0, max(0.0, elapsed_seconds / (self.ramp_hours * 3600.0)))
        return (
            _interpolate(self.start_temp, self.target_temp, fraction),
            _interpolate(self.start_humidity, self.target_humidity, fraction),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "target_temp": self.target_temp,
            "target_humidity": self.target_humidity,
            "end_kind": self.end_kind.value,
            "duration_hours": self.duration_hours,
            "weight_loss_pct": self.weight_loss_pct,
            "notify_end": self.notify_end,
            "start_temp": self.start_temp,
            "start_humidity": self.start_humidity,
            "ramp_hours": self.ramp_hours,
            "core_temp_target": self.core_temp_target,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Phase:
        return cls(
            name=str(data["name"]),
            target_temp=_opt_float(data.get("target_temp")),
            target_humidity=_opt_float(data.get("target_humidity")),
            end_kind=EndKind(str(data.get("end_kind", "duration"))),
            duration_hours=_opt_float(data.get("duration_hours")),
            weight_loss_pct=_opt_float(data.get("weight_loss_pct")),
            notify_end=bool(data.get("notify_end", True)),
            start_temp=_opt_float(data.get("start_temp")),
            start_humidity=_opt_float(data.get("start_humidity")),
            ramp_hours=_opt_float(data.get("ramp_hours")),
            core_temp_target=_opt_float(data.get("core_temp_target")),
        )


@dataclass(frozen=True)
class Reminder:
    """A periodic care reminder attached to a program.

    Every ``every_hours`` (wall clock, while the program runs) a notification
    suggests the journal entry ``kind`` (turned, washed, …) with ``note``.
    ``phases`` restricts it to the named phases (empty = whole program); the
    countdown restarts when such a phase begins.
    """

    kind: str
    every_hours: float
    note: str | None = None
    phases: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "every_hours": self.every_hours,
            "note": self.note,
            "phases": list(self.phases),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Reminder:
        raw_phases = data.get("phases") or []
        phases = tuple(str(p) for p in raw_phases) if isinstance(raw_phases, list) else ()
        return cls(
            kind=str(data.get("kind") or "note"),
            every_hours=float(_opt_float(data.get("every_hours")) or 24.0),
            note=_opt_str(data.get("note")),
            phases=phases,
        )


@dataclass(frozen=True)
class ReminderDue:
    """A reminder that just became due (returned by the engine)."""

    index: int
    reminder: Reminder
    phase_name: str


@dataclass(frozen=True)
class Program:
    """An ordered sequence of phases, with optional care reminders."""

    id: str
    name: str
    phases: tuple[Phase, ...]
    on_complete: OnComplete = OnComplete.HOLD_LAST
    builtin: bool = False
    category: ProgramCategory = ProgramCategory.CHARCUTERIE
    reminders: tuple[Reminder, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "phases": [p.to_dict() for p in self.phases],
            "on_complete": self.on_complete.value,
            "builtin": self.builtin,
            "category": self.category.value,
            "reminders": [r.to_dict() for r in self.reminders],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Program:
        raw_phases = data.get("phases", [])
        phases_iter = raw_phases if isinstance(raw_phases, list) else []
        phases = tuple(Phase.from_dict(_as_mapping(p)) for p in phases_iter)
        raw_reminders = data.get("reminders", [])
        reminders_iter = raw_reminders if isinstance(raw_reminders, list) else []
        reminders = tuple(Reminder.from_dict(_as_mapping(r)) for r in reminders_iter)
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            phases=phases,
            on_complete=OnComplete(str(data.get("on_complete", "hold_last"))),
            builtin=bool(data.get("builtin", False)),
            category=ProgramCategory(str(data.get("category") or "charcuterie")),
            reminders=reminders,
        )


@dataclass
class ProgramState:
    """Mutable, persisted runtime state of a running program."""

    program_id: str | None = None
    status: ProgramStatus = ProgramStatus.IDLE
    phase_index: int = 0
    started_at: float | None = None
    phase_started_at: float | None = None
    accumulated_paused: float = 0.0
    paused_at: float | None = None
    reference_weight: float | None = None
    #: Product core temperature seen when the current phase started (for the
    #: direction of a ``CORE_TEMP`` end condition).
    core_temp_start: float | None = None
    #: Last time each reminder fired, keyed by reminder index (as a string
    #: for JSON).
    reminder_last: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "program_id": self.program_id,
            "status": self.status.value,
            "phase_index": self.phase_index,
            "started_at": self.started_at,
            "phase_started_at": self.phase_started_at,
            "accumulated_paused": self.accumulated_paused,
            "paused_at": self.paused_at,
            "reference_weight": self.reference_weight,
            "core_temp_start": self.core_temp_start,
            "reminder_last": dict(self.reminder_last),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ProgramState:
        return cls(
            program_id=_opt_str(data.get("program_id")),
            status=ProgramStatus(str(data.get("status", "idle"))),
            phase_index=int(_opt_float(data.get("phase_index")) or 0),
            started_at=_opt_float(data.get("started_at")),
            phase_started_at=_opt_float(data.get("phase_started_at")),
            accumulated_paused=_opt_float(data.get("accumulated_paused")) or 0.0,
            paused_at=_opt_float(data.get("paused_at")),
            reference_weight=_opt_float(data.get("reference_weight")),
            core_temp_start=_opt_float(data.get("core_temp_start")),
            reminder_last=_float_map(data.get("reminder_last")),
        )


@dataclass(frozen=True)
class ProgramEvent:
    """An event produced by the engine."""

    type: ProgramEventType
    phase_index: int
    phase_name: str
    notify: bool = True
    params: dict[str, float | str] = field(default_factory=dict)


def _opt_float(value: object) -> float | None:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _float_map(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, float] = {}
    for key, raw in value.items():
        number = _opt_float(raw)
        if number is not None:
            out[str(key)] = number
    return out


def _interpolate(start: float | None, end: float | None, fraction: float) -> float | None:
    """Linear interpolation; without a start value the end value applies at once."""
    if end is None:
        return None
    if start is None:
        return end
    return start + (end - start) * fraction


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("expected a mapping for a phase")
    return value
