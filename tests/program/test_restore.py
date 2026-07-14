"""Program resume-after-restart via serialisation (§13.4)."""

from __future__ import annotations

from custom_components.curing_chamber.program import (
    ProgramEngine,
    ProgramEventType,
    ProgramStatus,
)
from custom_components.curing_chamber.program.presets import preset_by_id

HOUR = 3600.0


def test_roundtrip_resumes_mid_phase() -> None:
    saucisson = preset_by_id("saucisson_sec")
    assert saucisson is not None
    eng = ProgramEngine()
    eng.start(saucisson, now=0.0, reference_weight=1000.0)
    # Advance 20 h into the 36 h rest phase, then "restart".
    eng.tick(now=20 * HOUR)
    blob = eng.to_dict()

    restored = ProgramEngine.from_dict(blob)
    assert restored.status is ProgramStatus.RUNNING
    assert restored.state.phase_index == 0
    assert restored.state.reference_weight == 1000.0
    # The phase clock is preserved: it still ends at 36 h, not 36 h after resume.
    assert restored.tick(now=35 * HOUR) == []
    events = restored.tick(now=36 * HOUR + 1)
    assert any(e.type is ProgramEventType.PHASE_ENDED for e in events)


def test_roundtrip_preserves_paused_state() -> None:
    saucisson = preset_by_id("saucisson_sec")
    assert saucisson is not None
    eng = ProgramEngine()
    eng.start(saucisson, now=0.0)
    eng.pause(now=5 * HOUR)
    restored = ProgramEngine.from_dict(eng.to_dict())
    assert restored.status is ProgramStatus.PAUSED
    assert restored.elapsed_in_phase(now=1000 * HOUR) == 5 * HOUR
