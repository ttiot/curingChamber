"""Built-in drying and ripening presets (§6).

Values are *indicative* starting points, documented as such in the README.
Users can duplicate and adapt them to their own recipes. Weight-loss phases
carry an approximate maximum duration (the "~N weeks" column) that also serves
as the fallback when no scale is configured.

Presets are tagged with a :class:`ProgramCategory`; a chamber only lists the
presets of its own kind (charcuterie or cheese cave).
"""

from __future__ import annotations

from .types import EndKind, OnComplete, Phase, Program, ProgramCategory, Reminder

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
    *,
    ramp_hours: float | None = None,
) -> Program:
    """A classic cure: optional rest/fermentation, then drying to a weight loss.

    With ``ramp_hours`` the drying phase does not jump from the rest targets to
    the drying targets but ramps down to them over that many hours, which
    limits case hardening on the first drying days.
    """
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
    ramp = ramp_hours is not None and phases
    phases.append(
        Phase(
            name="drying",
            target_temp=dry_temp,
            target_humidity=dry_hum,
            end_kind=EndKind.WEIGHT_LOSS,
            weight_loss_pct=loss_pct,
            duration_hours=dry_weeks * _WEEK_H,
            start_temp=rest_temp if ramp else None,
            start_humidity=rest_hum if ramp else None,
            ramp_hours=ramp_hours if ramp else None,
        )
    )
    return Program(id=id_, name=name, phases=tuple(phases), builtin=True)


def _hold(id_: str, name: str, temp: float, hum: float, category: ProgramCategory) -> Program:
    """A single open-ended holding phase (cellar / cave)."""
    return Program(
        id=id_,
        name=name,
        phases=(
            Phase(name="hold", target_temp=temp, target_humidity=hum, end_kind=EndKind.MANUAL),
        ),
        on_complete=OnComplete.HOLD_LAST,
        builtin=True,
        category=category,
    )


def _cheese(
    id_: str,
    name: str,
    dry_temp: float | None,
    dry_hum: float | None,
    dry_hours: float | None,
    ripen_temp: float,
    ripen_hum: float,
    ripen_weeks: float,
    *,
    ramp_hours: float | None = None,
    reminders: tuple[Reminder, ...] = (),
) -> Program:
    """A cheese ripening: optional surface drying (ressuyage), then ripening.

    Cheese ripening ends on tasting rather than on a weight loss, so the
    ripening phase ends on its indicative duration and the targets are then
    held (``hold_last``) until the program is stopped.
    """
    phases: list[Phase] = []
    if dry_temp is not None or dry_hum is not None:
        phases.append(
            Phase(
                name="surface_drying",
                target_temp=dry_temp,
                target_humidity=dry_hum,
                end_kind=EndKind.DURATION,
                duration_hours=dry_hours,
            )
        )
    ramp = ramp_hours is not None and phases
    phases.append(
        Phase(
            name="ripening",
            target_temp=ripen_temp,
            target_humidity=ripen_hum,
            end_kind=EndKind.DURATION,
            duration_hours=ripen_weeks * _WEEK_H,
            start_temp=dry_temp if ramp else None,
            start_humidity=dry_hum if ramp else None,
            ramp_hours=ramp_hours if ramp else None,
        )
    )
    return Program(
        id=id_,
        name=name,
        phases=tuple(phases),
        on_complete=OnComplete.HOLD_LAST,
        builtin=True,
        category=ProgramCategory.CHEESE,
        reminders=reminders,
    )


_TURN_DAILY = Reminder(kind="turned", every_hours=24.0, phases=("ripening",))
_TURN_EVERY_2_DAYS = Reminder(kind="turned", every_hours=48.0, phases=("ripening",))
_WASH_EVERY_2_DAYS = Reminder(
    kind="washed", every_hours=48.0, note="brine / morge", phases=("ripening",)
)


PRESETS: tuple[Program, ...] = (
    # --- Charcuterie --------------------------------------------------------
    _cure("saucisson_sec", "Saucisson sec", 22.0, 80.0, 36.0, 13.0, 76.0, 35.0, 5.0),
    _cure("coppa", "Coppa", 22.0, 80.0, 24.0, 13.0, 75.0, 35.0, 8.0),
    _cure("bresaola", "Bresaola", 20.0, 75.0, 24.0, 13.0, 72.0, 35.0, 6.0),
    _cure("pancetta", "Pancetta roulée", 22.0, 80.0, 24.0, 13.0, 75.0, 30.0, 4.0),
    _cure("lonzo", "Lonzo / filet mignon séché", None, None, None, 13.0, 75.0, 35.0, 4.0),
    _cure("chorizo", "Chorizo", 22.0, 85.0, 48.0, 13.0, 75.0, 35.0, 5.0, ramp_hours=48.0),
    _cure("lomo", "Lomo embuchado", 20.0, 80.0, 24.0, 12.0, 75.0, 35.0, 6.0, ramp_hours=24.0),
    _cure("viande_des_grisons", "Viande des Grisons", 18.0, 75.0, 24.0, 12.0, 72.0, 40.0, 8.0),
    _cure("jambon_cru", "Jambon cru (après salage)", None, None, None, 14.0, 72.0, 32.0, 26.0),
    _hold("cellar_hold", "Maintien cave d'affinage", 12.0, 78.0, ProgramCategory.CHARCUTERIE),
    # --- Cheese ---------------------------------------------------------------
    _cheese(
        "cheese_bloomy",
        "Croûte fleurie (camembert, brie)",
        16.0,
        85.0,
        24.0,
        12.0,
        92.0,
        3.0,
        reminders=(_TURN_DAILY,),
    ),
    _cheese(
        "cheese_washed",
        "Croûte lavée (munster, reblochon)",
        16.0,
        85.0,
        24.0,
        13.0,
        95.0,
        5.0,
        reminders=(_TURN_EVERY_2_DAYS, _WASH_EVERY_2_DAYS),
    ),
    _cheese(
        "cheese_pressed",
        "Pâte pressée (tomme, cantal)",
        16.0,
        80.0,
        48.0,
        12.0,
        88.0,
        10.0,
        ramp_hours=48.0,
        reminders=(_TURN_EVERY_2_DAYS,),
    ),
    _cheese("cheese_blue", "Pâte persillée (bleu, fourme)", None, None, None, 9.0, 95.0, 8.0),
    _cheese("cheese_lactic", "Pâte lactique / chèvre", 18.0, 75.0, 48.0, 11.0, 85.0, 2.0),
    _hold("cheese_cave_hold", "Maintien cave à fromages", 11.0, 90.0, ProgramCategory.CHEESE),
)


def preset_by_id(program_id: str) -> Program | None:
    """Return the built-in preset with ``program_id`` or ``None``."""
    for preset in PRESETS:
        if preset.id == program_id:
            return preset
    return None


def presets_for(category: ProgramCategory) -> list[Program]:
    """Return the built-in presets written for ``category``."""
    return [preset for preset in PRESETS if preset.category is category]
