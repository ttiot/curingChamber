"""Built-in drying presets (§6).

Values are *indicative* starting points, documented as such in the README.
Users can duplicate and adapt them to their own recipes. Weight-loss phases
carry an approximate maximum duration (the "~N weeks" column) that also serves
as the fallback when no scale is configured.
"""

from __future__ import annotations

from .types import EndKind, OnComplete, Phase, Program

_WEEK_H = 7 * 24.0


def _cure(
    id_: str,
    name: str,
    rest_temp: float | None,
    rest_hum: float | None,
    rest_hours: float | None,
    dry_temp: float,
    dry_hum: float,
    loss_pct: float,
    dry_weeks: float,
) -> Program:
    phases: list[Phase] = []
    if rest_temp is not None or rest_hum is not None:
        phases.append(
            Phase(
                name="rest",
                target_temp=rest_temp,
                target_humidity=rest_hum,
                end_kind=EndKind.DURATION,
                duration_hours=rest_hours,
            )
        )
    phases.append(
        Phase(
            name="drying",
            target_temp=dry_temp,
            target_humidity=dry_hum,
            end_kind=EndKind.WEIGHT_LOSS,
            weight_loss_pct=loss_pct,
            duration_hours=dry_weeks * _WEEK_H,
        )
    )
    return Program(id=id_, name=name, phases=tuple(phases), builtin=True)


PRESETS: tuple[Program, ...] = (
    _cure("saucisson_sec", "Saucisson sec", 22.0, 80.0, 36.0, 13.0, 76.0, 35.0, 5.0),
    _cure("coppa", "Coppa", 22.0, 80.0, 24.0, 13.0, 75.0, 35.0, 8.0),
    _cure("bresaola", "Bresaola", 20.0, 75.0, 24.0, 13.0, 72.0, 35.0, 6.0),
    _cure("pancetta", "Pancetta roulée", 22.0, 80.0, 24.0, 13.0, 75.0, 30.0, 4.0),
    _cure("lonzo", "Lonzo / filet mignon séché", None, None, None, 13.0, 75.0, 35.0, 4.0),
    Program(
        id="cellar_hold",
        name="Maintien cave d'affinage",
        phases=(
            Phase(
                name="hold",
                target_temp=12.0,
                target_humidity=78.0,
                end_kind=EndKind.MANUAL,
            ),
        ),
        on_complete=OnComplete.HOLD_LAST,
        builtin=True,
    ),
)


def preset_by_id(program_id: str) -> Program | None:
    """Return the built-in preset with ``program_id`` or ``None``."""
    for preset in PRESETS:
        if preset.id == program_id:
            return preset
    return None
