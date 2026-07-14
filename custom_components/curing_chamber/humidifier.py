"""Humidifier entity exposing the chamber humidity regulation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.humidifier import (
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)

from .const import DOMAIN
from .entity import CuringChamberEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import CuringChamberCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: CuringChamberCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CuringChamberHumidifier(coordinator)])


class CuringChamberHumidifier(CuringChamberEntity, HumidifierEntity):
    """Humidity controller backed by the regulation engine."""

    _attr_translation_key = "chamber_humidity"
    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_min_humidity = 40
    _attr_max_humidity = 99
    _attr_supported_features = HumidifierEntityFeature(0)

    def __init__(self, coordinator: CuringChamberCoordinator) -> None:
        super().__init__(coordinator, "humidifier")

    @property
    def is_on(self) -> bool:
        return self.coordinator.regulation_enabled and not self.coordinator.maintenance

    @property
    def current_humidity(self) -> float | None:
        return (self.coordinator.data or {}).get("humidity")

    @property
    def target_humidity(self) -> int | None:
        target = (self.coordinator.data or {}).get("target_humidity")
        return round(target) if target is not None else None

    @property
    def action(self) -> HumidifierAction:
        if not self.is_on:
            return HumidifierAction.OFF
        summary = (self.coordinator.data or {}).get("summary")
        if summary == "humidifying":
            return HumidifierAction.HUMIDIFYING
        if summary == "drying":
            return HumidifierAction.DRYING
        return HumidifierAction.IDLE

    async def async_set_humidity(self, humidity: int) -> None:
        current_temp_target = (self.coordinator.data or {}).get("target_temp")
        await self.coordinator.async_set_targets(current_temp_target, float(humidity))

    async def async_turn_on(self, **kwargs: object) -> None:
        await self.coordinator.async_set_regulation_enabled(True)

    async def async_turn_off(self, **kwargs: object) -> None:
        await self.coordinator.async_set_regulation_enabled(False)
