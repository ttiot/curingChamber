"""Phases ending on the product core temperature."""

from __future__ import annotations

import pytest
from custom_components.curing_chamber.program import ProgramEngine, ProgramEventType
from custom_components.curing_chamber.program.schema import (
    ProgramValidationError,
    validate_program,
)
from custom_components.curing_chamber.program.types import EndKind, Phase, Program

HOUR = 3600.0


def _program(target: float, cap: float | None = None) -> Program:
    return Program(
        id="p",
        name="P",
        phases=(
            Phase(
                "chill",
                target_temp=4.0,
                end_kind=EndKind.CORE_TEMP,
                core_temp_target=target,
                duration_hours=cap,
            ),
            Phase("hold", target_temp=12.0, end_kind=EndKind.MANUAL),
        ),
    )


def test_core_phase_ends_when_core_crosses_target_downwards() -> None:
    eng = ProgramEngine()
    eng.start(_program(4.0), now=0.0)
    assert eng.tick(now=HOUR, core_temp=18.0) == []
    assert eng.state.core_temp_start == 18.0
    assert eng.tick(now=2 * HOUR, core_temp=6.0) == []
    events = eng.tick(now=3 * HOUR, core_temp=3.9)
    assert ProgramEventType.PHASE_ENDED in [e.type for e in events]
    assert eng.state.phase_index == 1
    assert eng.state.core_temp_start is None  # reset for the next phase


def test_core_phase_ends_when_core_crosses_target_upwards() -> None:
    eng = ProgramEngine()
    eng.start(_program(20.0), now=0.0)
    assert eng.tick(now=HOUR, core_temp=5.0) == []
    assert eng.tick(now=2 * HOUR, core_temp=19.0) == []
    assert eng.tick(now=3 * HOUR, core_temp=20.5)


def test_core_phase_without_probe_falls_back_to_duration_cap() -> None:
    eng = ProgramEngine()
    eng.start(_program(4.0, cap=10.0), now=0.0)
    assert eng.tick(now=9 * HOUR) == []
    assert eng.tick(now=10 * HOUR + 1)


def test_core_phase_without_probe_and_cap_never_ends() -> None:
    eng = ProgramEngine()
    eng.start(_program(4.0), now=0.0)
    assert eng.tick(now=1000 * HOUR) == []


def test_core_start_survives_serialisation() -> None:
    eng = ProgramEngine()
    eng.start(_program(4.0), now=0.0)
    eng.tick(now=HOUR, core_temp=18.0)
    restored = ProgramEngine.from_dict(eng.to_dict())
    assert restored.state.core_temp_start == 18.0
    assert restored.tick(now=2 * HOUR, core_temp=3.0)


def test_complete_ends_the_program_from_any_phase() -> None:
    eng = ProgramEngine()
    eng.start(_program(4.0), now=0.0)
    events = eng.complete(now=HOUR)
    types = [e.type for e in events]
    assert types == [ProgramEventType.PHASE_ENDED, ProgramEventType.PROGRAM_COMPLETED]
    assert eng.status.value == "completed"
    assert eng.active_on_complete_targets() == (12.0, None)
    assert eng.complete(now=2 * HOUR) == []  # idempotent once completed


def _payload(**extra: object) -> dict[str, object]:
    return {
        "id": "p",
        "name": "P",
        "phases": [{"name": "chill", "target_temp": 4, "end_kind": "core_temp", **extra}],
    }


def test_validate_core_temp_phase() -> None:
    program, warnings = validate_program(_payload(core_temp_target=4))
    assert program.phases[0].end_kind is EndKind.CORE_TEMP
    assert program.phases[0].core_temp_target == 4.0
    assert warnings == []
    with pytest.raises(ProgramValidationError, match="core_temp_target"):
        validate_program(_payload())


def test_validate_core_temp_without_probe_needs_duration() -> None:
    with pytest.raises(ProgramValidationError, match="fallback"):
        validate_program(_payload(core_temp_target=4), has_core_probe=False)
    _, warnings = validate_program(
        _payload(core_temp_target=4, duration_hours=12), has_core_probe=False
    )
    assert any("core probe" in w for w in warnings)
