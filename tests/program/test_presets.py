"""Built-in presets and program payload validation."""

from __future__ import annotations

import pytest
from custom_components.curing_chamber.program import PRESETS, preset_by_id, presets_for
from custom_components.curing_chamber.program.schema import (
    ProgramValidationError,
    validate_program,
)
from custom_components.curing_chamber.program.types import EndKind, Program, ProgramCategory

CHARCUTERIE_IDS = {
    "saucisson_sec",
    "coppa",
    "bresaola",
    "pancetta",
    "lonzo",
    "chorizo",
    "lomo",
    "viande_des_grisons",
    "jambon_cru",
    "cellar_hold",
}
CHEESE_IDS = {
    "cheese_bloomy",
    "cheese_washed",
    "cheese_pressed",
    "cheese_blue",
    "cheese_lactic",
    "cheese_cave_hold",
}


def test_all_presets_have_expected_ids() -> None:
    ids = {p.id for p in PRESETS}
    assert ids == CHARCUTERIE_IDS | CHEESE_IDS
    assert len(ids) == len(PRESETS)


def test_presets_are_split_by_category() -> None:
    assert {p.id for p in presets_for(ProgramCategory.CHARCUTERIE)} == CHARCUTERIE_IDS
    assert {p.id for p in presets_for(ProgramCategory.CHEESE)} == CHEESE_IDS
    assert all(p.builtin for p in PRESETS)


def test_chorizo_drying_ramps_down_from_the_rest_targets() -> None:
    chorizo = preset_by_id("chorizo")
    assert chorizo is not None
    rest, drying = chorizo.phases
    assert drying.has_ramp
    assert (drying.start_temp, drying.start_humidity) == (rest.target_temp, rest.target_humidity)
    assert drying.ramp_hours == 48.0
    assert drying.targets_at(0.0) == (22.0, 85.0)
    assert drying.targets_at(48 * 3600.0) == (13.0, 75.0)


def test_cheese_presets_end_on_duration_and_hold() -> None:
    for preset in presets_for(ProgramCategory.CHEESE):
        assert preset.category is ProgramCategory.CHEESE
        assert all(p.end_kind is not EndKind.WEIGHT_LOSS for p in preset.phases)
        assert preset.on_complete.value == "hold_last"
        # No phase is called "drying": the high-temperature drying alert is a
        # charcuterie rule and must not fire on a cheese surface-drying step.
        assert all(p.name != "drying" for p in preset.phases)


def test_preset_serialisation_round_trip() -> None:
    for preset in PRESETS:
        assert Program.from_dict(preset.to_dict()) == preset


def test_saucisson_values() -> None:
    saucisson = preset_by_id("saucisson_sec")
    assert saucisson is not None
    rest, drying = saucisson.phases
    assert (rest.target_temp, rest.target_humidity, rest.duration_hours) == (22.0, 80.0, 36.0)
    assert drying.end_kind is EndKind.WEIGHT_LOSS
    assert drying.weight_loss_pct == 35.0


def test_lonzo_has_single_phase() -> None:
    lonzo = preset_by_id("lonzo")
    assert lonzo is not None
    assert len(lonzo.phases) == 1


def test_preset_by_id_unknown() -> None:
    assert preset_by_id("nope") is None


def test_validate_valid_program() -> None:
    payload = {
        "id": "my_prog",
        "name": "My program",
        "phases": [
            {
                "name": "rest",
                "target_temp": 22,
                "target_humidity": 80,
                "end_kind": "duration",
                "duration_hours": 24,
            },
            {
                "name": "dry",
                "target_temp": 13,
                "target_humidity": 75,
                "end_kind": "weight_loss",
                "weight_loss_pct": 35,
                "duration_hours": 800,
            },
        ],
    }
    program, warnings = validate_program(payload, has_scale=True)
    assert program.name == "My program"
    assert warnings == []


def test_validate_weight_loss_without_scale_warns() -> None:
    payload = {
        "id": "p",
        "name": "P",
        "phases": [
            {
                "name": "dry",
                "target_humidity": 75,
                "end_kind": "weight_loss",
                "weight_loss_pct": 35,
                "duration_hours": 800,
            },
        ],
    }
    _, warnings = validate_program(payload, has_scale=False)
    assert any("scale" in w for w in warnings)


def test_validate_rejects_phase_without_target() -> None:
    payload = {
        "id": "p",
        "name": "P",
        "phases": [{"name": "bad", "end_kind": "duration", "duration_hours": 10}],
    }
    with pytest.raises(ProgramValidationError, match="target"):
        validate_program(payload)


def test_validate_rejects_empty_phases() -> None:
    with pytest.raises(ProgramValidationError, match="at least one phase"):
        validate_program({"id": "p", "name": "P", "phases": []})


def test_validate_weight_loss_without_duration_and_scale_fails() -> None:
    payload = {
        "id": "p",
        "name": "P",
        "phases": [
            {
                "name": "dry",
                "target_humidity": 75,
                "end_kind": "weight_loss",
                "weight_loss_pct": 35,
            },
        ],
    }
    with pytest.raises(ProgramValidationError, match="fallback"):
        validate_program(payload, has_scale=False)
