"""Batch serialisation round-trip (persistence / resume-after-restart)."""

from __future__ import annotations

from custom_components.curing_chamber.batch import Batch, BatchStatus, WeightSample

DAY = 86400.0


def test_roundtrip_preserves_batch() -> None:
    b = Batch(
        id="coppa_1",
        name="Coppa #1",
        product="coppa",
        program_id="my_coppa",
        reference_weight=1200.0,
        target_loss_pct=35.0,
        created_at=100.0,
        status=BatchStatus.ACTIVE,
    )
    photo = "/local/curing_chamber/c/1.jpg"
    b.add_sample(WeightSample(timestamp=0.0, weight=1200.0, note="start"))
    b.add_sample(WeightSample(timestamp=DAY, weight=1150.0, photo_url=photo))

    restored = Batch.from_dict(b.to_dict())

    assert restored == b
    assert restored.status is BatchStatus.ACTIVE
    assert restored.samples[1].photo_url == photo
    assert restored.latest_weight == 1150.0


def test_from_dict_sorts_samples_by_time() -> None:
    data = {
        "id": "b",
        "name": "B",
        "samples": [
            {"timestamp": DAY, "weight": 900.0},
            {"timestamp": 0.0, "weight": 1000.0},
        ],
    }
    restored = Batch.from_dict(data)
    assert [s.timestamp for s in restored.samples] == [0.0, DAY]
    assert restored.latest_weight == 900.0
