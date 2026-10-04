"""Number entities: manual temperature/humidity setpoints (§7) and manual weight.

The setpoints are kept in sync with the climate/humidifier entities: writing any
of them updates the same manual targets on the coordinator. The manual weight
entity lets you type a weigh-in straight from the HA UI (no card, no YAML).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
            ManualWeight(coordinator),
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


class ManualWeight(CuringChamberEntity, NumberEntity):
    """Type a weight by hand: it is recorded as a weigh-in on the reference batch.

    Without a reference batch the value becomes the chamber weight (used by the
    weight-loss sensor and ``weight_loss`` program phases) so a chamber with no
    scale can still be driven from the UI. Displays the weight currently in use,
    whatever its source (reference batch, scale or manual entry).
    """

    _attr_translation_key = "manual_weight"
    _attr_native_min_value = 0
    _attr_native_max_value = 100000
    _attr_native_step = 0.1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:scale"

    def __init__(self, coordinator: CuringChamberCoordinator) -> None:
        super().__init__(coordinator, "number_manual_weight")

    @property
    def native_value(self) -> float | None:
        return (self.coordinator.data or {}).get("weight")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "source": data.get("weight_source"),
            "reference_batch_id": data.get("reference_batch_id"),
            "reference_weight": data.get("reference_weight"),
        }

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_record_manual_weight(value)
