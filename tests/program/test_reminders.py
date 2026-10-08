"""Program care reminders: due detection, phase scoping, persistence, validation."""

from __future__ import annotations

import pytest
from custom_components.curing_chamber.program import ProgramEngine, Reminder, preset_by_id
from custom_components.curing_chamber.program.schema import (
    ProgramValidationError,
    validate_program,
)
from custom_components.curing_chamber.program.types import EndKind, Phase, Program

HOUR = 3600.0


def _program(*reminders: Reminder) -> Program:
    return Program(
        id="p",
        name="P",
        phases=(
            Phase("rest", target_temp=20.0, end_kind=EndKind.DURATION, duration_hours=24.0),
            Phase("ripening", target_temp=12.0, end_kind=EndKind.MANUAL),
        ),
        reminders=reminders,
    )


def test_program_wide_reminder_fires_every_interval() -> None:
    eng = ProgramEngine()
    eng.start(_program(Reminder("turned", 12.0)), now=0.0)
    assert eng.due_reminders(now=11 * HOUR) == []
    due = eng.due_reminders(now=12 * HOUR)
    assert [d.reminder.kind for d in due] == ["turned"]
    assert due[0].phase_name == "rest"
    assert eng.due_reminders(now=13 * HOUR) == []  # fired, counting again
    assert eng.due_reminders(now=24 * HOUR) != []
    nxt = eng.next_reminder(now=25 * HOUR)
    assert nxt is not None
    assert nxt[0].kind == "turned"
    assert nxt[1] == 11 * HOUR


def test_phase_scoped_reminder_counts_from_phase_start() -> None:
    eng = ProgramEngine()
    eng.start(_program(Reminder("washed", 48.0, note="brine", phases=("ripening",))), now=0.0)
    assert eng.next_reminder(now=0.0) is None  # not applicable in "rest"
    assert eng.due_reminders(now=100 * HOUR) == []
    eng.tick(now=24 * HOUR)  # into ripening at t=24 h
    assert eng.due_reminders(now=71 * HOUR) == []
    due = eng.due_reminders(now=72 * HOUR)
    assert due and due[0].reminder.note == "brine"


def test_reminders_do_not_fire_while_paused() -> None:
    eng = ProgramEngine()
    eng.start(_program(Reminder("turned", 1.0)), now=0.0)
    eng.pause(now=0.5 * HOUR)
    assert eng.due_reminders(now=5 * HOUR) == []
    eng.resume(now=5 * HOUR)
    assert eng.due_reminders(now=5 * HOUR) != []


def test_reminder_state_survives_serialisation() -> None:
    eng = ProgramEngine()
    eng.start(_program(Reminder("turned", 12.0)), now=0.0)
    eng.due_reminders(now=12 * HOUR)
    restored = ProgramEngine.from_dict(eng.to_dict())
    assert restored.state.reminder_last == {"0": 12 * HOUR}
    assert restored.program is not None
    assert restored.program.reminders == (Reminder("turned", 12.0),)
    assert restored.due_reminders(now=23 * HOUR) == []
    assert restored.due_reminders(now=24 * HOUR) != []


def test_cheese_presets_carry_reminders() -> None:
    washed = preset_by_id("cheese_washed")
    assert washed is not None
    assert {r.kind for r in washed.reminders} == {"turned", "washed"}
    assert all(r.phases == ("ripening",) for r in washed.reminders)


def _payload(reminders: object) -> dict[str, object]:
    return {
        "id": "p",
        "name": "P",
        "phases": [{"name": "ripening", "target_temp": 12, "end_kind": "manual"}],
        "reminders": reminders,
    }


def test_validate_reminders() -> None:
    program, _ = validate_program(
        _payload([{"kind": "turned", "every_hours": 48, "phases": ["ripening"], "note": ""}])
    )
    assert program.reminders == (Reminder("turned", 48.0, None, ("ripening",)),)
    program, _ = validate_program(_payload(None))
    assert program.reminders == ()


@pytest.mark.parametrize(
    ("reminders", "match"),
    [
        ("nope", "must be a list"),
        ([{"every_hours": 24}], "needs a kind"),
        ([{"kind": "turned", "every_hours": 0}], "every_hours"),
        ([{"kind": "turned", "every_hours": 24, "phases": ["drying"]}], "unknown phase"),
    ],
)
def test_validate_rejects_bad_reminders(reminders: object, match: str) -> None:
    with pytest.raises(ProgramValidationError, match=match):
        validate_program(_payload(reminders))
