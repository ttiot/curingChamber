"""The pure drying-program engine (phase state machine, time-injected)."""

from __future__ import annotations

from .types import (
    EndKind,
    OnComplete,
    Phase,
    Program,
    ProgramEvent,
    ProgramEventType,
    ProgramState,
    ProgramStatus,
)


class ProgramEngine:
    """Drive a :class:`Program` through its phases.

    The engine owns a :class:`ProgramState` and a reference to the running
    :class:`Program`. Both are serialisable so the adaptation layer can persist
    them and resume transparently after a restart.
    """

    def __init__(self, program: Program | None = None, state: ProgramState | None = None) -> None:
        self.program = program
        self.state = state or ProgramState()

    # -- Serialisation -------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        return {
            "program": self.program.to_dict() if self.program else None,
            "state": self.state.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ProgramEngine:
        program_data = data.get("program")
        program = Program.from_dict(program_data) if program_data else None  # type: ignore[arg-type]
        state = ProgramState.from_dict(data.get("state", {}))  # type: ignore[arg-type]
        return cls(program=program, state=state)

    # -- Queries -------------------------------------------------------------

    @property
    def status(self) -> ProgramStatus:
        return self.state.status

    @property
    def current_phase(self) -> Phase | None:
        if (
            self.program is None
            or self.state.status not in (ProgramStatus.RUNNING, ProgramStatus.PAUSED)
            or not 0 <= self.state.phase_index < len(self.program.phases)
        ):
            return None
        return self.program.phases[self.state.phase_index]

    def active_targets(self, now: float | None = None) -> tuple[float | None, float | None]:
        """Return (target_temp, target_humidity) of the active phase, if any.

        With ``now`` the targets follow the phase's ramp (if it has one);
        without it the phase's final targets are returned.
        """
        phase = self.current_phase
        if phase is None:
            return (None, None)
        if now is None or not phase.has_ramp:
            return (phase.target_temp, phase.target_humidity)
        return phase.targets_at(self.elapsed_in_phase(now))

    def ramp_remaining(self, now: float) -> float | None:
        """Seconds left in the active phase's ramp, ``None`` without a ramp."""
        phase = self.current_phase
        if phase is None:
            return None
        return phase.ramp_remaining(self.elapsed_in_phase(now))

    def elapsed_in_phase(self, now: float) -> float:
        """Return seconds spent in the current phase, excluding paused time."""
        if self.state.phase_started_at is None:
            return 0.0
        paused = self.state.accumulated_paused
        if self.state.status is ProgramStatus.PAUSED and self.state.paused_at is not None:
            paused += now - self.state.paused_at
        return max(0.0, now - self.state.phase_started_at - paused)

    def phase_remaining(self, now: float) -> float | None:
        """Return estimated seconds remaining in the phase (duration-based)."""
        phase = self.current_phase
        if phase is None or phase.duration_hours is None:
            return None
        return max(0.0, phase.duration_hours * 3600.0 - self.elapsed_in_phase(now))

    def weight_loss_pct(self, weight: float | None) -> float | None:
        """Return current weight loss vs the reference, or ``None``."""
        ref = self.state.reference_weight
        if ref is None or ref <= 0 or weight is None:
            return None
        return (ref - weight) / ref * 100.0

    # -- Commands ------------------------------------------------------------

    def start(
        self, program: Program, now: float, reference_weight: float | None = None
    ) -> list[ProgramEvent]:
        """Start ``program`` from its first phase."""
        self.program = program
        self.state = ProgramState(
            program_id=program.id,
            status=ProgramStatus.RUNNING,
            phase_index=0,
            started_at=now,
            phase_started_at=now,
            reference_weight=reference_weight,
        )
        return [self._phase_event(ProgramEventType.PHASE_STARTED, 0)]

    def pause(self, now: float) -> None:
        if self.state.status is ProgramStatus.RUNNING:
            self.state.status = ProgramStatus.PAUSED
            self.state.paused_at = now

    def resume(self, now: float) -> None:
        if self.state.status is ProgramStatus.PAUSED:
            if self.state.paused_at is not None:
                self.state.accumulated_paused += now - self.state.paused_at
            self.state.paused_at = None
            self.state.status = ProgramStatus.RUNNING

    def stop(self) -> None:
        self.program = None
        self.state = ProgramState()

    def set_reference_weight(self, weight: float) -> None:
        self.state.reference_weight = weight

    def next_phase(self, now: float) -> list[ProgramEvent]:
        """Force an advance to the next phase (or completion)."""
        if self.program is None or self.state.status not in (
            ProgramStatus.RUNNING,
            ProgramStatus.PAUSED,
        ):
            return []
        return self._advance(now, notify_current=True)

    def complete(self, now: float) -> list[ProgramEvent]:
        """End the program now (e.g. its batch was completed by hand).

        The current phase ends, the program is marked completed and its
        ``on_complete`` policy applies as if the last phase had finished.
        """
        if self.program is None or self.state.status not in (
            ProgramStatus.RUNNING,
            ProgramStatus.PAUSED,
        ):
            return []
        self.state.phase_index = len(self.program.phases) - 1
        return self._advance(now, notify_current=True)

    def tick(
        self, now: float, weight: float | None = None, core_temp: float | None = None
    ) -> list[ProgramEvent]:
        """Evaluate the end condition of the current phase and auto-advance."""
        if self.state.status is not ProgramStatus.RUNNING or self.program is None:
            return []
        phase = self.current_phase
        if phase is None:
            return []
        if core_temp is not None and self.state.core_temp_start is None:
            self.state.core_temp_start = core_temp
        if self._end_condition_met(phase, now, weight, core_temp):
            return self._advance(now, notify_current=phase.notify_end)
        return []

    # -- Internals -----------------------------------------------------------

    def _end_condition_met(
        self, phase: Phase, now: float, weight: float | None, core_temp: float | None
    ) -> bool:
        elapsed = self.elapsed_in_phase(now)
        if phase.end_kind is EndKind.MANUAL:
            return False
        cap_reached = phase.duration_hours is not None and elapsed >= phase.duration_hours * 3600.0
        if phase.end_kind is EndKind.DURATION:
            return cap_reached
        if phase.end_kind is EndKind.CORE_TEMP:
            # Met when the core crosses the target from where it started, or on
            # the duration safety cap / fallback without a core probe.
            return cap_reached or self._core_target_reached(phase, core_temp)
        # WEIGHT_LOSS: met on target loss, or on the duration safety cap / fallback.
        loss = self.weight_loss_pct(weight)
        target_reached = (
            phase.weight_loss_pct is not None and loss is not None and loss >= phase.weight_loss_pct
        )
        return target_reached or cap_reached

    def _core_target_reached(self, phase: Phase, core_temp: float | None) -> bool:
        target = phase.core_temp_target
        start = self.state.core_temp_start
        if target is None or core_temp is None or start is None:
            return False
        if start >= target:
            return core_temp <= target
        return core_temp >= target

    def _advance(self, now: float, notify_current: bool) -> list[ProgramEvent]:
        assert self.program is not None
        events: list[ProgramEvent] = [
            self._phase_event(
                ProgramEventType.PHASE_ENDED, self.state.phase_index, notify=notify_current
            )
        ]
        next_index = self.state.phase_index + 1
        if next_index >= len(self.program.phases):
            self.state.status = ProgramStatus.COMPLETED
            events.append(
                ProgramEvent(
                    ProgramEventType.PROGRAM_COMPLETED,
                    self.state.phase_index,
                    self.program.name,
                )
            )
            if self.program.on_complete is OnComplete.STOP:
                # Keep the completed status but drop active targets on stop.
                pass
            return events
        self.state.phase_index = next_index
        self.state.phase_started_at = now
        self.state.accumulated_paused = 0.0
        self.state.paused_at = None
        self.state.core_temp_start = None
        # A forced advance while paused resumes running.
        self.state.status = ProgramStatus.RUNNING
        events.append(self._phase_event(ProgramEventType.PHASE_STARTED, next_index))
        return events

    def _phase_event(
        self, event_type: ProgramEventType, index: int, notify: bool = True
    ) -> ProgramEvent:
        assert self.program is not None
        phase = self.program.phases[index]
        return ProgramEvent(event_type, index, phase.name, notify=notify)

    def active_on_complete_targets(self) -> tuple[float | None, float | None]:
        """Targets to hold after completion, per the program's on_complete."""
        if (
            self.program is None
            or self.state.status is not ProgramStatus.COMPLETED
            or self.program.on_complete is OnComplete.STOP
            or not self.program.phases
        ):
            return (None, None)
        last = self.program.phases[-1]
        return (last.target_temp, last.target_humidity)
