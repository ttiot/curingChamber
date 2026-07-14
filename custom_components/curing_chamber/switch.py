"""Switches: master regulation enable and maintenance mode."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import EntityCategory

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
            RegulationSwitch(coordinator),
            MaintenanceSwitch(coordinator),
        ]
    )


class RegulationSwitch(CuringChamberEntity, SwitchEntity):
    """Enable/disable the whole regulation."""

    _attr_translation_key = "regulation"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator: CuringChamberCoordinator) -> None:
        super().__init__(coordinator, "switch_regulation")

    @property
    def is_on(self) -> bool:
        return self.coordinator.regulation_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_regulation_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_regulation_enabled(False)


class MaintenanceSwitch(CuringChamberEntity, SwitchEntity):
    """Maintenance mode: everything off, no alerts."""

    _attr_translation_key = "maintenance"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: CuringChamberCoordinator) -> None:
        super().__init__(coordinator, "switch_maintenance")

    @property
    def is_on(self) -> bool:
        return self.coordinator.maintenance

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_maintenance(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_maintenance(False)
