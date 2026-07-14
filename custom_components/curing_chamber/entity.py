"""Base entity wiring shared device_info and coordinator access."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import CuringChamberCoordinator


class CuringChamberEntity(CoordinatorEntity["CuringChamberCoordinator"]):
    """Common base: attaches every entity to the one chamber device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CuringChamberCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.chamber_name,
            manufacturer="Curing Chamber",
            model="Charcuterie curing chamber",
        )
