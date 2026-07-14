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
