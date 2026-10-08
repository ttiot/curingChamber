"""Derived psychrometric quantities (pure functions).

All formulas use the Magnus approximation. Inputs are in degrees Celsius and
percent relative humidity; results are documented per function.
"""

from __future__ import annotations

import math

# Magnus coefficients over water (valid roughly -45..60 degC).
_MAGNUS_A = 17.62
_MAGNUS_B = 243.12  # degC


def dew_point(temp_c: float, humidity_pct: float) -> float:
    """Return the dew point in degrees Celsius (Magnus formula).

    ``humidity_pct`` is clamped to (0, 100]; values <= 0 are treated as a very
    small positive number to keep the logarithm finite.
    """
    rh = max(min(humidity_pct, 100.0), 1e-3)
    gamma = math.log(rh / 100.0) + (_MAGNUS_A * temp_c) / (_MAGNUS_B + temp_c)
    return (_MAGNUS_B * gamma) / (_MAGNUS_A - gamma)


def saturation_vapor_pressure(temp_c: float) -> float:
    """Return saturation vapour pressure in hPa (Magnus)."""
    return 6.112 * math.exp((_MAGNUS_A * temp_c) / (_MAGNUS_B + temp_c))


def absolute_humidity(temp_c: float, humidity_pct: float) -> float:
    """Return absolute humidity in g/m3.

    Derived from the ideal gas law applied to water vapour.
    """
    rh = max(min(humidity_pct, 100.0), 0.0)
    vp = saturation_vapor_pressure(temp_c) * rh / 100.0  # hPa
    # 2.1674 = (M_water * 100) / R  with pressure in hPa, T in Kelvin.
    return 216.7 * (vp / (temp_c + 273.15))


def drying_rate(
    weight_now: float,
    weight_before: float,
    reference_weight: float,
    elapsed_seconds: float,
) -> float | None:
    """Return the drying speed in percent-of-reference lost per day.

    Returns ``None`` when it cannot be computed (missing/zero reference or
    non-positive elapsed time).
    """
    if reference_weight <= 0 or elapsed_seconds <= 0:
        return None
    lost_pct = (weight_before - weight_now) / reference_weight * 100.0
    days = elapsed_seconds / 86400.0
    return lost_pct / days


def weight_loss_pct(weight_now: float, reference_weight: float) -> float | None:
    """Return the cumulative weight loss as a percentage of the reference."""
    if reference_weight <= 0:
        return None
    return (reference_weight - weight_now) / reference_weight * 100.0


def core_delta(product_temp_c: float | None, chamber_temp_c: float | None) -> float | None:
    """Product core minus chamber air temperature (°C), ``None`` without both."""
    if product_temp_c is None or chamber_temp_c is None:
        return None
    return product_temp_c - chamber_temp_c
