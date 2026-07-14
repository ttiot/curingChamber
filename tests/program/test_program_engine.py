"""Phase state machine: start, pause/resume, next_phase, duration ends."""

from __future__ import annotations

from custom_components.curing_chamber.program import (
    ProgramEngine,
    ProgramEventType,
    ProgramStatus,
)
from custom_components.curing_chamber.program.types import EndKind, Phase, Program

HOUR = 3600.0


def _two_phase() -> Program:
    return Program(
        id="test",
        name="Test",
        phases=(
            Phase(
                "rest",
                target_temp=22.0,
                target_humidity=80.0,
                end_kind=EndKind.DURATION,
                duration_hours=36.0,
            ),
            Phase("drying", target_temp=13.0, target_humidity=76.0, end_kind=EndKind.MANUAL),
        ),
    )


def test_start_emits_phase_started_and_sets_targets() -> None:
    eng = ProgramEngine()
    events = eng.start(_two_phase(), now=0.0)
    assert events[0].type is ProgramEventType.PHASE_STARTED
    assert eng.status is ProgramStatus.RUNNING
    assert eng.active_targets() == (22.0, 80.0)


def test_duration_phase_advances_automatically() -> None:
    eng = ProgramEngine()
    eng.start(_two_phase(), now=0.0)
    assert eng.tick(now=35 * HOUR) == []  # not yet
    events = eng.tick(now=36 * HOUR + 1)
    types = [e.type for e in events]
    assert ProgramEventType.PHASE_ENDED in types
    assert ProgramEventType.PHASE_STARTED in types
    assert eng.state.phase_index == 1
    assert eng.active_targets() == (13.0, 76.0)


def test_manual_phase_needs_next_phase() -> None:
    eng = ProgramEngine()
    eng.start(_two_phase(), now=0.0)
    eng.tick(now=36 * HOUR + 1)  # into drying (manual)
    assert eng.tick(now=100 * HOUR) == []  # manual never auto-advances
    events = eng.next_phase(now=101 * HOUR)
    assert any(e.type is ProgramEventType.PROGRAM_COMPLETED for e in events)
    assert eng.status is ProgramStatus.COMPLETED


def test_pause_freezes_phase_clock() -> None:
    eng = ProgramEngine()
    eng.start(_two_phase(), now=0.0)
    eng.pause(now=10 * HOUR)
    assert eng.status is ProgramStatus.PAUSED
    # 100 h of wall-clock pass while paused; elapsed stays at 10 h.
    assert eng.elapsed_in_phase(now=110 * HOUR) == 10 * HOUR
    eng.resume(now=110 * HOUR)
    # Now the phase must not end until 36 h of *running* time (26 h more).
    assert eng.tick(now=135 * HOUR) == []
    events = eng.tick(now=137 * HOUR)
    assert any(e.type is ProgramEventType.PHASE_ENDED for e in events)


def test_stop_resets_state() -> None:
    eng = ProgramEngine()
    eng.start(_two_phase(), now=0.0)
    eng.stop()
    assert eng.status is ProgramStatus.IDLE
    assert eng.active_targets() == (None, None)


def test_phase_remaining_estimate() -> None:
    eng = ProgramEngine()
    eng.start(_two_phase(), now=0.0)
    remaining = eng.phase_remaining(now=10 * HOUR)
    assert remaining == 26 * HOUR
