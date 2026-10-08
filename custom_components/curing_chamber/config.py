"""Helpers for reading merged config-entry data/options.

Options take precedence over the original data so the options flow can fully
reconfigure a chamber (sensors, actuators, thresholds) after installation.
Re-exports the constants so callers can use a single ``config`` namespace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .const import *  # noqa: F403  (re-export CONF_/DEFAULT_ names)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


def get(entry: ConfigEntry, key: str, default: Any = None) -> Any:
    """Return ``key`` from options, then data, then ``default``."""
    if key in entry.options:
        return entry.options[key]
    if key in entry.data:
        return entry.data[key]
    return default


def chamber_kind(entry: ConfigEntry) -> str:
    """Return the chamber kind (charcuterie / cheese), defaulting to charcuterie."""
    kind = get(entry, CONF_CHAMBER_KIND, DEFAULT_CHAMBER_KIND)  # noqa: F405
    return str(kind) if kind in CHAMBER_KINDS else DEFAULT_CHAMBER_KIND  # noqa: F405


def condensation_margin_default(merged: dict[str, Any]) -> float:
    """Default condensation margin for a chamber of the given (merged) config."""
    if merged.get(CONF_CHAMBER_KIND) == CHAMBER_KIND_CHEESE:  # noqa: F405
        return float(DEFAULT_CONDENSATION_MARGIN_CHEESE)  # noqa: F405
    return float(DEFAULT_CONDENSATION_MARGIN)  # noqa: F405
