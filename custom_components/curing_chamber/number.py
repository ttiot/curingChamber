"""Number entities for manual temperature/humidity setpoints (§7).

Kept in sync with the climate/humidifier entities: writing any of them updates
the same manual targets on the coordinator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature

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
    async_add_entities(
        [
            ManualTemperature(coordinator),
            ManualHumidity(coordinator),
        ]
    )


class ManualTemperature(CuringChamberEntity, NumberEntity):
    _attr_translation_key = "manual_temperature"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = -10
    _attr_native_max_value = 40
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: CuringChamberCoordinator) -> None:
        super().__init__(coordinator, "number_manual_temp")

    @property
    def native_value(self) -> float | None:
        return (self.coordinator.data or {}).get("target_temp")

    async def async_set_native_value(self, value: float) -> None:
        humidity = (self.coordinator.data or {}).get("target_humidity")
        await self.coordinator.async_set_targets(value, humidity)


class ManualHumidity(CuringChamberEntity, NumberEntity):
    _attr_translation_key = "manual_humidity"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: CuringChamberCoordinator) -> None:
        super().__init__(coordinator, "number_manual_humidity")

    @property
    def native_value(self) -> float | None:
        return (self.coordinator.data or {}).get("target_humidity")

    async def async_set_native_value(self, value: float) -> None:
        temp = (self.coordinator.data or {}).get("target_temp")
        await self.coordinator.async_set_targets(temp, value)
