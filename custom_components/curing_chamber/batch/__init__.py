"""Batch tracking: products curing in a chamber, with a manual weigh-in log.

This package is a pure, Home-Assistant-independent layer (mirroring ``program``
and ``regulation``): it models a :class:`~.types.Batch` (one product being
cured, with its reference weight, target weight loss and a history of
:class:`~.types.WeightSample` weigh-ins) and the pure functions that derive the
current weight loss, the drying rate and a predicted completion date (ETA).
"""

from __future__ import annotations

from .engine import (
    ETA_MODEL_EXPONENTIAL,
    ETA_MODEL_LINEAR,
    current_loss_pct,
    drying_rate_pct_per_day,
    estimate_eta,
    eta_model,
)
from .types import EVENT_KINDS, Batch, BatchEvent, BatchStatus, WeightSample

__all__ = [
    "ETA_MODEL_EXPONENTIAL",
    "ETA_MODEL_LINEAR",
    "EVENT_KINDS",
    "Batch",
    "BatchEvent",
    "BatchStatus",
    "WeightSample",
    "current_loss_pct",
    "drying_rate_pct_per_day",
    "estimate_eta",
    "eta_model",
]
