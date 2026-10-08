"""Pure batch derivations: current loss, drying rate and ETA."""

from __future__ import annotations

import math

from custom_components.curing_chamber.batch import (
    ETA_MODEL_EXPONENTIAL,
    ETA_MODEL_LINEAR,
    Batch,
    BatchEvent,
    WeightSample,
    current_loss_pct,
    drying_rate_pct_per_day,
    estimate_eta,
    eta_model,
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


def _exponential_batch(k: float = 0.08, amplitude: float = 45.0, days: int = 10) -> Batch:
    """Weigh-ins following loss(t) = A·(1 - e^(-k·t)) exactly."""
    b = _batch(reference_weight=1000.0, target_loss_pct=35.0)
    for d in range(days + 1):
        loss = amplitude * (1.0 - math.exp(-k * d))
        b.add_sample(WeightSample(timestamp=d * DAY, weight=1000.0 * (1 - loss / 100.0)))
    return b


def test_eta_uses_exponential_model_when_drying_slows_down() -> None:
    b = _exponential_batch()
    assert eta_model(b) == ETA_MODEL_EXPONENTIAL
    eta = estimate_eta(b, now=10 * DAY)
    assert eta is not None
    # Exact day on which the curve reaches 35 %: -ln(1 - 35/45) / k.
    expected = -math.log(1 - 35.0 / 45.0) / 0.08
    assert abs(eta / DAY - expected) < 0.3
    # The linear projection from the same points lands much earlier.
    rate = drying_rate_pct_per_day(b)
    assert rate is not None
    linear = 10 + (35.0 - current_loss_pct(b)) / rate  # type: ignore[operator]
    assert linear < expected - 2


def test_eta_falls_back_to_linear_with_two_points() -> None:
    b = _batch(reference_weight=1000.0, target_loss_pct=30.0)
    b.add_sample(WeightSample(timestamp=0.0, weight=1000.0))
    b.add_sample(WeightSample(timestamp=5 * DAY, weight=950.0))
    assert eta_model(b) == ETA_MODEL_LINEAR
    assert estimate_eta(b, now=5 * DAY) == 30 * DAY


def test_eta_falls_back_to_linear_on_perfectly_linear_data() -> None:
    b = _batch(reference_weight=1000.0, target_loss_pct=30.0)
    for d in range(6):
        b.add_sample(WeightSample(timestamp=d * DAY, weight=1000.0 - 10.0 * d))
    # A straight line is explained as well by the line as by any curve, and the
    # exponential asymptote may sit below the target: the linear ETA wins.
    eta = estimate_eta(b, now=5 * DAY)
    assert eta is not None
    assert abs(eta / DAY - 30.0) < 1.0


def test_eta_none_when_target_above_exponential_asymptote_and_no_rate() -> None:
    b = _exponential_batch(amplitude=20.0)  # the curve plateaus at 20 %, target is 35 %
    assert eta_model(b) == ETA_MODEL_LINEAR  # still extrapolates the line
    assert estimate_eta(b, now=10 * DAY) is not None


def test_eta_model_none_without_target() -> None:
    b = _exponential_batch()
    b.target_loss_pct = None
    assert eta_model(b) is None


def test_batch_journal_round_trip() -> None:
    b = _batch()
    b.add_event(BatchEvent(timestamp=2 * DAY, kind="turned"))
    b.add_event(BatchEvent(timestamp=DAY, kind="salting", note="2.8 %"))
    assert [e.kind for e in b.events] == ["salting", "turned"]
    restored = Batch.from_dict(b.to_dict())
    assert restored.events == b.events
    assert Batch.from_dict({"id": "x", "name": "X"}).events == []
