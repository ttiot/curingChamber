"""Setpoint ramps: interpolation, engine targets, validation, import/export."""

from __future__ import annotations

import pytest
from custom_components.curing_chamber.program import ProgramEngine
from custom_components.curing_chamber.program.schema import (
    EXPORT_FORMAT,
    ProgramValidationError,
    export_payload,
    validate_import,
    validate_program,
)
from custom_components.curing_chamber.program.types import (
    EndKind,
    Phase,
    Program,
    ProgramCategory,
)

HOUR = 3600.0


def _ramped() -> Program:
    return Program(
        id="ramped",
        name="Ramped",
        phases=(
            Phase(
                "rest",
                target_temp=22.0,
                target_humidity=85.0,
                end_kind=EndKind.DURATION,
                duration_hours=24.0,
            ),
            Phase(
                "drying",
                target_temp=13.0,
                target_humidity=75.0,
                end_kind=EndKind.MANUAL,
                start_temp=22.0,
                start_humidity=85.0,
                ramp_hours=48.0,
            ),
        ),
    )


def test_phase_without_ramp_returns_fixed_targets() -> None:
    phase = Phase("hold", target_temp=12.0, target_humidity=78.0)
    assert not phase.has_ramp
    assert phase.targets_at(0.0) == (12.0, 78.0)
    assert phase.targets_at(10 * HOUR) == (12.0, 78.0)
    assert phase.ramp_remaining(0.0) is None


def test_phase_ramp_interpolates_then_holds() -> None:
    phase = _ramped().phases[1]
    assert phase.has_ramp
    assert phase.targets_at(0.0) == (22.0, 85.0)
    assert phase.targets_at(24 * HOUR) == (17.5, 80.0)
    assert phase.targets_at(48 * HOUR) == (13.0, 75.0)
    assert phase.targets_at(100 * HOUR) == (13.0, 75.0)
    assert phase.ramp_remaining(12 * HOUR) == 36 * HOUR
    assert phase.ramp_remaining(60 * HOUR) == 0.0


def test_phase_ramps_only_the_quantity_with_a_start_value() -> None:
    phase = Phase("d", target_temp=13.0, target_humidity=75.0, start_temp=20.0, ramp_hours=10.0)
    assert phase.has_ramp
    assert phase.targets_at(5 * HOUR) == (16.5, 75.0)


def test_ramp_hours_without_start_is_not_a_ramp() -> None:
    phase = Phase("d", target_temp=13.0, ramp_hours=10.0)
    assert not phase.has_ramp
    assert phase.targets_at(HOUR) == (13.0, None)


def test_engine_targets_follow_the_ramp_and_exclude_paused_time() -> None:
    eng = ProgramEngine()
    eng.start(_ramped(), now=0.0)
    assert eng.active_targets(now=10 * HOUR) == (22.0, 85.0)  # rest phase, no ramp
    eng.tick(now=24 * HOUR)  # into drying
    assert eng.state.phase_index == 1
    assert eng.active_targets(now=24 * HOUR) == (22.0, 85.0)
    assert eng.active_targets(now=48 * HOUR) == (17.5, 80.0)
    # Without "now" the engine reports the phase's final targets.
    assert eng.active_targets() == (13.0, 75.0)
    assert eng.ramp_remaining(now=48 * HOUR) == 24 * HOUR

    eng.pause(now=48 * HOUR)
    eng.resume(now=58 * HOUR)  # 10 h paused: the ramp is frozen meanwhile
    assert eng.active_targets(now=58 * HOUR) == (17.5, 80.0)
    assert eng.active_targets(now=82 * HOUR) == (13.0, 75.0)
    assert eng.ramp_remaining(now=82 * HOUR) == 0.0


def test_engine_ramp_survives_serialisation() -> None:
    eng = ProgramEngine()
    eng.start(_ramped(), now=0.0)
    eng.tick(now=24 * HOUR)
    restored = ProgramEngine.from_dict(eng.to_dict())
    assert restored.active_targets(now=36 * HOUR) == (19.75, 82.5)
    assert restored.program is not None
    assert restored.program.phases[1].ramp_hours == 48.0


def _payload(**phase_extra: object) -> dict[str, object]:
    return {
        "id": "p",
        "name": "P",
        "phases": [
            {
                "name": "drying",
                "target_temp": 13,
                "target_humidity": 75,
                "end_kind": "duration",
                "duration_hours": 100,
                **phase_extra,
            }
        ],
    }


def test_validate_ramp_fields() -> None:
    program, warnings = validate_program(_payload(start_temp=22, ramp_hours=48))
    phase = program.phases[0]
    assert (phase.start_temp, phase.start_humidity, phase.ramp_hours) == (22.0, None, 48.0)
    assert warnings == []


def test_validate_ramp_longer_than_phase_warns() -> None:
    _, warnings = validate_program(_payload(start_temp=22, ramp_hours=200))
    assert any("longer than the phase" in w for w in warnings)


def test_validate_zero_ramp_hours_is_dropped() -> None:
    program, _ = validate_program(_payload(ramp_hours=0))
    assert program.phases[0].ramp_hours is None


@pytest.mark.parametrize(
    ("extra", "match"),
    [
        ({"start_temp": 22}, "no ramp_hours"),
        ({"ramp_hours": 10}, "no start_temp"),
        (
            {"start_humidity": 80, "ramp_hours": 10, "target_humidity": None},
            "without target_humidity",
        ),
        (
            {"start_temp": 22, "ramp_hours": 10, "target_temp": None, "target_humidity": 75},
            "without target_temp",
        ),
        ({"start_temp": 200, "ramp_hours": 10}, "between"),
    ],
)
def test_validate_rejects_inconsistent_ramps(extra: dict[str, object], match: str) -> None:
    with pytest.raises(ProgramValidationError, match=match):
        validate_program(_payload(**extra))


def test_validate_category() -> None:
    program, _ = validate_program({**_payload(), "category": "cheese"})
    assert program.category is ProgramCategory.CHEESE
    program, _ = validate_program(_payload())
    assert program.category is ProgramCategory.CHARCUTERIE
    with pytest.raises(ProgramValidationError, match="category"):
        validate_program({**_payload(), "category": "fish"})


def test_export_import_round_trip() -> None:
    original = _ramped()
    payload = export_payload([original])
    assert payload["format"] == EXPORT_FORMAT
    programs, warnings = validate_import(payload)
    assert warnings == []
    assert len(programs) == 1
    assert programs[0].phases == original.phases
    assert programs[0].builtin is False


def test_import_accepts_list_and_single_program() -> None:
    programs, _ = validate_import([_payload(), {**_payload(), "id": "q"}])
    assert [p.id for p in programs] == ["p", "q"]
    programs, _ = validate_import(_payload())
    assert [p.id for p in programs] == ["p"]


def test_import_rejects_duplicates_and_empty() -> None:
    with pytest.raises(ProgramValidationError, match="duplicate"):
        validate_import([_payload(), _payload()])
    with pytest.raises(ProgramValidationError, match="nothing to import"):
        validate_import({"programs": []})
    with pytest.raises(ProgramValidationError, match="must be a list"):
        validate_import({"programs": "nope"})
