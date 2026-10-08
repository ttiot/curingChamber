"""Pure derivations over a batch's weigh-in history.

All functions are side-effect free and take a :class:`~.types.Batch`. Weight
loss is expressed as a percentage of the batch reference weight; the drying rate
is a least-squares slope in percent-of-reference lost per day; the ETA is the
projected timestamp at which the target loss is reached, assuming the current
rate holds.

Two ETA models are available. The **linear** one extrapolates the least-squares
drying rate. Real drying slows down as the product dries, so from three
weigh-ins on an **exponential** model ``loss(t) = L0 + A · (1 - e^(-k·t))`` is
fitted (grid search on ``k``, ``A`` solved analytically) and used whenever it
explains the weigh-ins at least as well as the straight line and the target
sits below its asymptote. Near the end of curing this moves the ETA later,
where the linear projection is too optimistic.
"""

from __future__ import annotations

import math

from .types import Batch

_SECONDS_PER_DAY = 86400.0

#: Minimum weigh-ins before the exponential model is considered.
_MIN_EXP_POINTS = 3
#: Decay constants searched (per day), log-spaced from very slow to very fast.
_K_GRID = tuple(10 ** (-3 + 0.05 * i) for i in range(0, 61))  # 0.001 … 1.0 /day

ETA_MODEL_LINEAR = "linear"
ETA_MODEL_EXPONENTIAL = "exponential"


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


def _linear_sse(points: list[tuple[float, float]], slope: float) -> float:
    n = len(points)
    mean_x = sum(x for x, _ in points) / n
    mean_y = sum(y for _, y in points) / n
    return sum((y - (mean_y + slope * (x - mean_x))) ** 2 for x, y in points)


def _fit_exponential(points: list[tuple[float, float]]) -> tuple[float, float, float] | None:
    """Fit ``y = y0 + A·(1 - e^(-k·x))`` through the first point.

    Returns ``(amplitude, k, sse)`` or ``None`` when the fit is meaningless
    (too few points, no spread in time, or no loss progression).
    """
    if len(points) < _MIN_EXP_POINTS:
        return None
    x0, y0 = points[0]
    rel = [(x - x0, y - y0) for x, y in points[1:]]
    if all(x <= 0 for x, _ in rel) or max(y for _, y in rel) <= 0:
        return None
    best: tuple[float, float, float] | None = None
    for k in _K_GRID:
        f = [(1.0 - math.exp(-k * x), y) for x, y in rel]
        denom = sum(fx * fx for fx, _ in f)
        if denom <= 0:
            continue
        amplitude = sum(fx * y for fx, y in f) / denom
        if amplitude <= 0:
            continue
        sse = sum((y - amplitude * fx) ** 2 for fx, y in f)
        if best is None or sse < best[2]:
            best = (amplitude, k, sse)
    return best


def eta_model(batch: Batch) -> str | None:
    """Return which model :func:`estimate_eta` would use, or ``None``."""
    return _project(batch, 0.0)[1]


def _project(batch: Batch, now: float) -> tuple[float | None, str | None]:
    if batch.target_loss_pct is None:
        return None, None
    loss = current_loss_pct(batch)
    if loss is None or loss >= batch.target_loss_pct:
        return None, None
    points = _loss_points(batch)
    slope = _slope_pct_per_day(points)
    linear: float | None = None
    if slope is not None and slope > 0:
        linear = now + (batch.target_loss_pct - loss) / slope * _SECONDS_PER_DAY

    fit = _fit_exponential(points)
    if fit is not None and slope is not None:
        amplitude, k, sse = fit
        x0, y0 = points[0]
        remaining = batch.target_loss_pct - y0
        # The exponential must explain the weigh-ins at least as well as the
        # line (compared on the same points) and the target must lie below its
        # asymptote, otherwise the curve never gets there.
        if 0 < remaining < amplitude and sse <= _linear_sse(points, slope) + 1e-9:
            days = -math.log(1.0 - remaining / amplitude) / k
            eta = batch.samples[0].timestamp + (x0 + days) * _SECONDS_PER_DAY
            if eta > now:
                return eta, ETA_MODEL_EXPONENTIAL
    if linear is None:
        return None, None
    return linear, ETA_MODEL_LINEAR


def estimate_eta(batch: Batch, now: float) -> float | None:
    """Return the projected timestamp at which ``target_loss_pct`` is reached.

    Uses the exponential model when it applies (see the module docstring), the
    linear extrapolation otherwise. Returns ``None`` when nothing can be
    projected: no target set, fewer than two weigh-ins, a non-positive drying
    rate, or the target already reached.
    """
    return _project(batch, now)[0]
