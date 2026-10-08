"""Pure (Home Assistant independent) drying-program engine.

Like the regulation package, this contains no ``homeassistant`` imports and
injects time via ``now`` parameters, so the phase state machine, weight-loss
end conditions and program resume-after-restart are unit-testable in isolation.
"""

from .engine import ProgramEngine
from .presets import PRESETS, preset_by_id, presets_for
from .types import (
    EndKind,
    OnComplete,
    Phase,
    Program,
    ProgramCategory,
    ProgramEvent,
    ProgramEventType,
    ProgramState,
    ProgramStatus,
)

__all__ = [
    "PRESETS",
    "EndKind",
    "OnComplete",
    "Phase",
    "Program",
    "ProgramCategory",
    "ProgramEngine",
    "ProgramEvent",
    "ProgramEventType",
    "ProgramState",
    "ProgramStatus",
    "preset_by_id",
    "presets_for",
]
