"""Pure batch derivations: current loss, drying rate and ETA."""

from __future__ import annotations

from custom_components.curing_chamber.batch import (
    Batch,
    WeightSample,
    current_loss_pct,
    drying_rate_pct_per_day,
    estimate_eta,
)

DAY = 86400.0


def _batch(**kwargs: object) -> Batch:
    defaults: dict[str, object] = {"id": "b1", "name": "Coppa"}
    defaults.update(kwargs)
    return Batch(**defaults)  # type: ignore[arg-type]


def test_current_loss_uses_reference_weight() -> None:
    b = _batch(reference_weight=1000.0)
    b.add_sample(WeightSample(timestamp=0.0, weight=1000.0))
    b.add_sample(WeightSample(timestamp=DAY, weight=900.0))
    assert current_loss_pct(b) == 10.0


def test_current_loss_falls_back_to_first_sample() -> None:
    # No explicit reference: the first weigh-in defines it (no-scale workflow).
    b = _batch()
    b.add_sample(WeightSample(timestamp=0.0, weight=800.0))
    b.add_sample(WeightSample(timestamp=DAY, weight=760.0))
    assert current_loss_pct(b) == 5.0


def test_current_loss_none_without_samples() -> None:
    assert current_loss_pct(_batch(reference_weight=1000.0)) is None


def test_current_loss_none_without_reference() -> None:
    b = _batch()  # no reference, no samples -> no effective reference
    assert current_loss_pct(b) is None


def test_drying_rate_linear() -> None:
    b = _batch(reference_weight=1000.0)
    b.add_sample(WeightSample(timestamp=0.0, weight=1000.0))
    b.add_sample(WeightSample(timestamp=2 * DAY, weight=960.0))  # 4 % over 2 days
    assert drying_rate_pct_per_day(b) == 2.0


def test_drying_rate_needs_two_samples() -> None:
    b = _batch(reference_weight=1000.0)
    b.add_sample(WeightSample(timestamp=0.0, weight=1000.0))
    assert drying_rate_pct_per_day(b) is None


def test_drying_rate_none_when_all_same_timestamp() -> None:
    b = _batch(reference_weight=1000.0)
    b.add_sample(WeightSample(timestamp=5.0, weight=1000.0))
    b.add_sample(WeightSample(timestamp=5.0, weight=980.0))
    assert drying_rate_pct_per_day(b) is None


def test_estimate_eta_projects_target() -> None:
    b = _batch(reference_weight=1000.0, target_loss_pct=30.0)
    b.add_sample(WeightSample(timestamp=0.0, weight=1000.0))
    b.add_sample(WeightSample(timestamp=2 * DAY, weight=960.0))  # 2 %/day, at 4 %
    now = 2 * DAY
    eta = estimate_eta(b, now)
    assert eta is not None
    # Remaining 26 % at 2 %/day = 13 days from now.
    assert eta == now + 13 * DAY


def test_estimate_eta_none_when_target_reached() -> None:
    b = _batch(reference_weight=1000.0, target_loss_pct=5.0)
    b.add_sample(WeightSample(timestamp=0.0, weight=1000.0))
    b.add_sample(WeightSample(timestamp=DAY, weight=900.0))  # already 10 % > 5 %
    assert estimate_eta(b, DAY) is None


def test_estimate_eta_none_without_target() -> None:
    b = _batch(reference_weight=1000.0)
    b.add_sample(WeightSample(timestamp=0.0, weight=1000.0))
    b.add_sample(WeightSample(timestamp=DAY, weight=980.0))
    assert estimate_eta(b, DAY) is None


def test_estimate_eta_none_when_gaining_weight() -> None:
    # Non-positive slope (weight went up) -> cannot project.
    b = _batch(reference_weight=1000.0, target_loss_pct=30.0)
    b.add_sample(WeightSample(timestamp=0.0, weight=960.0))
    b.add_sample(WeightSample(timestamp=DAY, weight=980.0))
    assert estimate_eta(b, DAY) is None
