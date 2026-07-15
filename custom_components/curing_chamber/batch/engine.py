"""Pure derivations over a batch's weigh-in history.

All functions are side-effect free and take a :class:`~.types.Batch`. Weight
loss is expressed as a percentage of the batch reference weight; the drying rate
is a least-squares slope in percent-of-reference lost per day; the ETA is the
projected timestamp at which the target loss is reached, assuming the current
rate holds.

The ETA model is a simple linear extrapolation for now. Drying is closer to
exponential in reality, so this tends to be conservative near the end; an
exponential fit would refine it in a later iteration.
"""

from __future__ import annotations

from .types import Batch

_SECONDS_PER_DAY = 86400.0


def current_loss_pct(batch: Batch) -> float | None:
    """Return the latest weight loss as a percentage of the reference weight.

    Returns ``None`` when there is no reference weight or no weigh-in yet.
    """
    ref = batch.effective_reference
    weight = batch.latest_weight
    if ref is None or ref <= 0 or weight is None:
        return None
    return (ref - weight) / ref * 100.0


def _loss_points(batch: Batch) -> list[tuple[float, float]]:
    """Return (days_since_first_sample, loss_pct) points for the weigh-ins."""
    ref = batch.effective_reference
    if ref is None or ref <= 0 or not batch.samples:
        return []
    t0 = batch.samples[0].timestamp
    return [
        ((s.timestamp - t0) / _SECONDS_PER_DAY, (ref - s.weight) / ref * 100.0)
        for s in batch.samples
    ]


def _slope_pct_per_day(points: list[tuple[float, float]]) -> float | None:
    """Least-squares slope of loss% vs days; ``None`` if undetermined."""
    n = len(points)
    if n < 2:
        return None
    sum_x = sum(x for x, _ in points)
    sum_y = sum(y for _, y in points)
    mean_x = sum_x / n
    mean_y = sum_y / n
    var_x = sum((x - mean_x) ** 2 for x, _ in points)
    if var_x <= 0:  # all weigh-ins share the same timestamp
        return None
    cov = sum((x - mean_x) * (y - mean_y) for x, y in points)
    return cov / var_x


def drying_rate_pct_per_day(batch: Batch) -> float | None:
    """Return the drying speed in percent-of-reference lost per day.

    Uses a least-squares fit over every weigh-in, so it is robust to scale
    noise once a few points exist. Returns ``None`` with fewer than two
    weigh-ins or when they all share a timestamp.
    """
    return _slope_pct_per_day(_loss_points(batch))


def estimate_eta(batch: Batch, now: float) -> float | None:
    """Return the projected timestamp at which ``target_loss_pct`` is reached.

    Returns ``None`` when it cannot be projected: no target set, fewer than two
    weigh-ins, a non-positive drying rate, or the target is already reached.
    """
    if batch.target_loss_pct is None:
        return None
    loss = current_loss_pct(batch)
    if loss is None or loss >= batch.target_loss_pct:
        return None
    slope = _slope_pct_per_day(_loss_points(batch))
    if slope is None or slope <= 0:
        return None
    remaining_pct = batch.target_loss_pct - loss
    return now + remaining_pct / slope * _SECONDS_PER_DAY
