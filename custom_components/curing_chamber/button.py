"""Buttons: next phase, set reference weight (tare), acknowledge alerts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity

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
            NextPhaseButton(coordinator),
            SetReferenceWeightButton(coordinator),
            AcknowledgeButton(coordinator),
        ]
    )


class NextPhaseButton(CuringChamberEntity, ButtonEntity):
    _attr_translation_key = "next_phase"

    def __init__(self, coordinator: CuringChamberCoordinator) -> None:
        super().__init__(coordinator, "button_next_phase")

    async def async_press(self) -> None:
        await self.coordinator.async_next_phase()


class SetReferenceWeightButton(CuringChamberEntity, ButtonEntity):
    _attr_translation_key = "set_reference_weight"

    def __init__(self, coordinator: CuringChamberCoordinator) -> None:
        super().__init__(coordinator, "button_set_reference_weight")

    async def async_press(self) -> None:
        await self.coordinator.async_set_reference_weight(None)


class AcknowledgeButton(CuringChamberEntity, ButtonEntity):
    _attr_translation_key = "acknowledge_alert"

    def __init__(self, coordinator: CuringChamberCoordinator) -> None:
        super().__init__(coordinator, "button_acknowledge_alert")

    async def async_press(self) -> None:
        await self.coordinator.async_acknowledge_alerts()
