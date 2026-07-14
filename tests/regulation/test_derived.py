"""Derived psychrometric quantities and sensor conditioning."""

from __future__ import annotations

import pytest

from custom_components.curing_chamber.regulation import derived
from custom_components.curing_chamber.regulation.filters import (
    SensorFilter,
    average,
    divergence,
)


def test_dew_point_known_value() -> None:
    # 20 degC / 50 %RH -> ~9.3 degC dew point.
    assert derived.dew_point(20.0, 50.0) == pytest.approx(9.27, abs=0.2)


def test_dew_point_saturation() -> None:
    # At 100 %RH the dew point equals the air temperature.
    assert derived.dew_point(13.0, 100.0) == pytest.approx(13.0, abs=0.05)


def test_absolute_humidity_positive_and_monotonic() -> None:
    low = derived.absolute_humidity(13.0, 50.0)
    high = derived.absolute_humidity(13.0, 80.0)
    assert 0 < low < high


def test_drying_rate() -> None:
    # Lose 1 % of a 1000 g reference in 12 h -> 2 %/day.
    rate = derived.drying_rate(
        weight_now=990.0, weight_before=1000.0, reference_weight=1000.0,
        elapsed_seconds=12 * 3600,
    )
    assert rate == pytest.approx(2.0, abs=0.01)


def test_drying_rate_guards() -> None:
    assert derived.drying_rate(990, 1000, 0, 3600) is None
    assert derived.drying_rate(990, 1000, 1000, 0) is None


def test_weight_loss_pct() -> None:
    assert derived.weight_loss_pct(650.0, 1000.0) == pytest.approx(35.0)
    assert derived.weight_loss_pct(650.0, 0.0) is None


def test_sensor_filter_smooths_spike() -> None:
    filt = SensorFilter(samples=3, stale_seconds=1e9)
    filt.update(13.0, 0.0)
    filt.update(13.0, 10.0)
    res = filt.update(19.0, 20.0)  # spike
    assert res.value == pytest.approx((13 + 13 + 19) / 3)


def test_average_and_divergence() -> None:
    assert average([]) is None
    assert average([10.0, 20.0]) == 15.0
    assert divergence([13.0]) == 0.0
    assert divergence([13.0, 16.0, 12.0]) == pytest.approx(4.0)
