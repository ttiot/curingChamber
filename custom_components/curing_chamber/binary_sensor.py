"""Binary sensors for alerts and manual-action state (§7)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import CuringChamberEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import CuringChamberCoordinator

_MANUAL_KEYS = {
    "manual_temp_high",
    "manual_temp_low",
    "manual_humidity_high",
    "manual_humidity_low",
    "air_quality",
}
_ABS_KEYS = {
    "abs_limit_temp_high",
    "abs_limit_temp_low",
    "abs_limit_humidity_high",
    "abs_limit_humidity_low",
    "high_temp_drying",
    "core_temp_high",
}
_FAULT_KEYS = {"sensor_fault_temp", "sensor_fault_humidity"}
_INEFFECTIVE_KEYS = {
    "actuator_ineffective_cool",
    "actuator_ineffective_heat",
    "actuator_ineffective_humidify",
    "actuator_ineffective_dehumidify",
}
_DIVERGENCE_KEYS = {"sensor_divergence_temp", "sensor_divergence_humidity"}


def _any_active(data: dict[str, Any], keys: set[str]) -> bool:
    return bool(set(data.get("active_alerts", [])) & keys)


@dataclass(frozen=True, kw_only=True)
class CuringBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor described by which alert keys drive it."""

    is_on_fn: Callable[[dict[str, Any]], bool]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _manual_attrs(data: dict[str, Any]) -> dict[str, Any]:
    details = data.get("alert_details", {})
    active = [k for k in data.get("active_alerts", []) if k in _MANUAL_KEYS]
    return {
        "actions": [details.get(k, {}).get("manual_action") for k in active],
        "alerts": active,
    }


BINARY_SENSORS: tuple[CuringBinaryDescription, ...] = (
    CuringBinaryDescription(
        key="manual_action_required",
        translation_key="manual_action_required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda d: _any_active(d, _MANUAL_KEYS),
        attrs_fn=_manual_attrs,
    ),
    CuringBinaryDescription(
        key="out_of_range",
        translation_key="out_of_range",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda d: _any_active(d, _ABS_KEYS),
    ),
    CuringBinaryDescription(
        key="sensor_fault",
        translation_key="sensor_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: _any_active(d, _FAULT_KEYS),
    ),
    CuringBinaryDescription(
        key="sensor_divergence",
        translation_key="sensor_divergence",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: _any_active(d, _DIVERGENCE_KEYS),
    ),
    CuringBinaryDescription(
        key="actuator_ineffective",
        translation_key="actuator_ineffective",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: _any_active(d, _INEFFECTIVE_KEYS),
        attrs_fn=lambda d: {
            "actuators": [
                k.removeprefix("actuator_ineffective_")
                for k in d.get("active_alerts", [])
                if k in _INEFFECTIVE_KEYS
            ]
        },
    ),
    CuringBinaryDescription(
        key="door_open_too_long",
        translation_key="door_open_too_long",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda d: _any_active(d, {"door_open_too_long"}),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: CuringChamberCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CuringChamberBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class CuringChamberBinarySensor(CuringChamberEntity, BinarySensorEntity):
    """A binary sensor driven by active alert keys."""

    entity_description: CuringBinaryDescription

    def __init__(
        self, coordinator: CuringChamberCoordinator, description: CuringBinaryDescription
    ) -> None:
        super().__init__(coordinator, f"binary_{description.key}")
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data or {})
