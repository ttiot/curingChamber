"""Pure validation of user-supplied program payloads (JSON/dict).

Kept dependency-free (no voluptuous) so it validates identically inside and
outside Home Assistant. Raises :class:`ProgramValidationError` with a clear,
human-readable message on the first problem found.
"""

from __future__ import annotations

from .types import EndKind, OnComplete, Phase, Program, ProgramCategory


class ProgramValidationError(ValueError):
    """Raised when a program payload is invalid."""


def _as_dict(value: object, message: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProgramValidationError(message)
    return value


def _as_list(value: object, message: str) -> list[object]:
    if not isinstance(value, list):
        raise ProgramValidationError(message)
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProgramValidationError(message)


def _text(value: object, message: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ProgramValidationError(message)
    return value


def _number(value: object, field: str, *, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProgramValidationError(f"'{field}' must be a number")
    number = float(value)
    _require(lo <= number <= hi, f"'{field}' must be between {lo} and {hi}")
    return number


def _opt_number(data: dict[str, object], field: str, *, lo: float, hi: float) -> float | None:
    if data.get(field) is None:
        return None
    return _number(data[field], field, lo=lo, hi=hi)


def validate_phase(data: object, index: int, *, has_scale: bool) -> tuple[Phase, list[str]]:
    """Validate one phase dict; return the phase and any non-fatal warnings."""
    warnings: list[str] = []
    phase = _as_dict(data, f"phase #{index + 1} must be an object")
    name = _text(phase.get("name"), f"phase #{index + 1} needs a name")

    target_temp = _opt_number(phase, "target_temp", lo=-30, hi=60)
    target_humidity = _opt_number(phase, "target_humidity", lo=0, hi=100)
    _require(
        target_temp is not None or target_humidity is not None,
        f"phase '{name}' must set at least one of target_temp / target_humidity",
    )

    end_kind_raw = phase.get("end_kind", "duration")
    _require(
        end_kind_raw in {k.value for k in EndKind},
        f"phase '{name}' has invalid end_kind '{end_kind_raw}'",
    )
    end_kind = EndKind(str(end_kind_raw))

    duration_hours = _opt_number(phase, "duration_hours", lo=0, hi=100000)
    weight_loss_pct = _opt_number(phase, "weight_loss_pct", lo=0, hi=90)

    # Optional ramp: start values move linearly to the targets over ramp_hours.
    start_temp = _opt_number(phase, "start_temp", lo=-30, hi=60)
    start_humidity = _opt_number(phase, "start_humidity", lo=0, hi=100)
    ramp_hours = _opt_number(phase, "ramp_hours", lo=0, hi=100000)
    if start_temp is not None or start_humidity is not None:
        _require(
            ramp_hours is not None and ramp_hours > 0,
            f"phase '{name}' has a ramp start value but no ramp_hours",
        )
    if start_temp is not None:
        _require(target_temp is not None, f"phase '{name}' ramps temperature without target_temp")
    if start_humidity is not None:
        _require(
            target_humidity is not None,
            f"phase '{name}' ramps humidity without target_humidity",
        )
    if ramp_hours is not None and ramp_hours > 0:
        _require(
            start_temp is not None or start_humidity is not None,
            f"phase '{name}' has ramp_hours but no start_temp / start_humidity",
        )
        if duration_hours is not None and ramp_hours > duration_hours:
            warnings.append(
                f"phase '{name}': ramp ({ramp_hours:g} h) is longer than the phase "
                f"({duration_hours:g} h); the final targets are never reached"
            )

    if end_kind is EndKind.DURATION:
        _require(duration_hours is not None, f"phase '{name}' (duration) needs duration_hours")
    if end_kind is EndKind.WEIGHT_LOSS:
        _require(
            weight_loss_pct is not None,
            f"phase '{name}' (weight_loss) needs weight_loss_pct",
        )
        if not has_scale:
            _require(
                duration_hours is not None,
                f"phase '{name}' uses weight_loss but no scale is configured; "
                "add duration_hours as a fallback",
            )
            warnings.append(f"phase '{name}': no scale configured, falling back to duration")

    return (
        Phase(
            name=name,
            target_temp=target_temp,
            target_humidity=target_humidity,
            end_kind=end_kind,
            duration_hours=duration_hours,
            weight_loss_pct=weight_loss_pct,
            notify_end=bool(phase.get("notify_end", True)),
            start_temp=start_temp,
            start_humidity=start_humidity,
            ramp_hours=ramp_hours if ramp_hours else None,
        ),
        warnings,
    )


def validate_program(data: object, *, has_scale: bool = True) -> tuple[Program, list[str]]:
    """Validate a whole program payload; return the program and warnings."""
    payload = _as_dict(data, "program must be an object")
    program_id = _text(payload.get("id"), "program needs an id")
    name = _text(payload.get("name"), "program needs a name")

    phases_raw = _as_list(payload.get("phases"), "program needs at least one phase")
    _require(len(phases_raw) >= 1, "program needs at least one phase")

    on_complete_raw = payload.get("on_complete", "hold_last")
    _require(
        on_complete_raw in {v.value for v in OnComplete},
        f"invalid on_complete '{on_complete_raw}'",
    )
    category_raw = payload.get("category") or ProgramCategory.CHARCUTERIE.value
    _require(
        category_raw in {v.value for v in ProgramCategory},
        f"invalid category '{category_raw}'",
    )

    phases: list[Phase] = []
    warnings: list[str] = []
    for index, phase_raw in enumerate(phases_raw):
        phase, phase_warnings = validate_phase(phase_raw, index, has_scale=has_scale)
        phases.append(phase)
        warnings.extend(phase_warnings)

    program = Program(
        id=program_id,
        name=name,
        phases=tuple(phases),
        on_complete=OnComplete(str(on_complete_raw)),
        builtin=False,
        category=ProgramCategory(str(category_raw)),
    )
    return program, warnings


#: Envelope written by the export service / panel export button.
EXPORT_FORMAT = "curing_chamber/programs"
EXPORT_VERSION = 1


def export_payload(programs: list[Program]) -> dict[str, object]:
    """Wrap ``programs`` in the portable export envelope."""
    return {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "programs": [program.to_dict() for program in programs],
    }


def validate_import(data: object, *, has_scale: bool = True) -> tuple[list[Program], list[str]]:
    """Validate an import payload; return the programs and warnings.

    Accepts the export envelope (``{"programs": [...]}``), a bare list of
    programs, or a single program object. Raises
    :class:`ProgramValidationError` on the first invalid program.
    """
    if isinstance(data, dict) and "programs" in data:
        raw_programs = _as_list(data.get("programs"), "'programs' must be a list")
    elif isinstance(data, list):
        raw_programs = data
    else:
        raw_programs = [data]
    _require(len(raw_programs) >= 1, "nothing to import")
    programs: list[Program] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for raw in raw_programs:
        program, program_warnings = validate_program(raw, has_scale=has_scale)
        _require(program.id not in seen, f"duplicate program id '{program.id}' in import")
        seen.add(program.id)
        programs.append(program)
        warnings.extend(program_warnings)
    return programs, warnings
