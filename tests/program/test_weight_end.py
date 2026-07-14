"""Weight-loss end condition and its duration fallback."""

from __future__ import annotations

from custom_components.curing_chamber.program import ProgramEngine, ProgramStatus
from custom_components.curing_chamber.program.types import EndKind, Phase, Program

HOUR = 3600.0


def _weight_program() -> Program:
    return Program(
        id="w",
        name="Weight",
        phases=(
            Phase(
                "drying",
                target_temp=13.0,
                target_humidity=76.0,
                end_kind=EndKind.WEIGHT_LOSS,
                weight_loss_pct=35.0,
                duration_hours=5 * 7 * 24.0,
            ),
        ),
    )


def test_ends_on_weight_loss_target() -> None:
    eng = ProgramEngine()
    eng.start(_weight_program(), now=0.0, reference_weight=1000.0)
    assert eng.tick(now=HOUR, weight=800.0) == []  # 20 % lost, not enough
    events = eng.tick(now=2 * HOUR, weight=650.0)  # 35 % lost
    assert events
    assert eng.status is ProgramStatus.COMPLETED


def test_weight_loss_pct_query() -> None:
    eng = ProgramEngine()
    eng.start(_weight_program(), now=0.0, reference_weight=1000.0)
    assert eng.weight_loss_pct(weight=650.0) == 35.0
    assert eng.weight_loss_pct(weight=None) is None


def test_duration_cap_ends_without_scale() -> None:
    """No reference weight -> falls back to the duration cap (~5 weeks)."""
    eng = ProgramEngine()
    eng.start(_weight_program(), now=0.0)  # no reference weight
    assert eng.tick(now=4 * 7 * 24 * HOUR, weight=None) == []
    events = eng.tick(now=(5 * 7 * 24 + 1) * HOUR, weight=None)
    assert events
    assert eng.status is ProgramStatus.COMPLETED


def test_set_reference_weight_after_start() -> None:
    eng = ProgramEngine()
    eng.start(_weight_program(), now=0.0)
    eng.set_reference_weight(1000.0)
    events = eng.tick(now=HOUR, weight=600.0)  # 40 % lost
    assert events
