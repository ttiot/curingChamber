"""Diagnostics support (anonymized) for the Curing Chamber integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import CuringChamberCoordinator

# Entity ids are not secret but are redacted to keep diagnostics shareable.
_REDACT = {
    "temp_sensor",
    "humidity_sensor",
    "temp_sensor_2",
    "humidity_sensor_2",
    "product_temp_sensor",
    "door_sensor",
    "weight_sensor",
    "co2_sensor",
    "cool_switch",
    "heat_switch",
    "humidify_switch",
    "dehumidify_switch",
    "fan_switch",
    "vent_switch",
    "notify_services",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: CuringChamberCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), _REDACT),
            "options": async_redact_data(dict(entry.options), _REDACT),
        },
        "state": {
            "summary": data.get("summary"),
            "target_temp": data.get("target_temp"),
            "target_humidity": data.get("target_humidity"),
            "temp": data.get("temp"),
            "humidity": data.get("humidity"),
            "commands": {
                k.value if hasattr(k, "value") else str(k): v
                for k, v in (data.get("commands") or {}).items()
            },
            "program_status": data.get("program_status"),
            "phase_name": data.get("phase_name"),
            "phase_remaining": data.get("phase_remaining"),
            "weight_loss_pct": data.get("weight_loss_pct"),
            "drying_rate": data.get("drying_rate"),
            "active_alerts": data.get("active_alerts"),
            "counters": data.get("counters"),
            "last_decisions": data.get("decisions"),
            "reference_batch_id": data.get("reference_batch_id"),
            # Batch names/notes/photos are omitted to keep diagnostics shareable.
            "batches": [
                {
                    "status": b.get("status"),
                    "product": b.get("product"),
                    "reference_weight": b.get("reference_weight"),
                    "target_loss_pct": b.get("target_loss_pct"),
                    "loss_pct": b.get("loss_pct"),
                    "drying_rate": b.get("drying_rate"),
                    "eta": b.get("eta"),
                    "sample_count": len(b.get("samples") or []),
                }
                for b in (data.get("batches") or [])
            ],
        },
        "regulation_enabled": coordinator.regulation_enabled,
        "maintenance": coordinator.maintenance,
    }
