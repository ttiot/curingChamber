"""Select entity to choose the active program/preset."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .entity import CuringChamberEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import CuringChamberCoordinator

_NONE = "none"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: CuringChamberCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ProgramSelect(coordinator)])


class ProgramSelect(CuringChamberEntity, SelectEntity):
    """Pick the active program; selecting 'none' stops the program."""

    _attr_translation_key = "program"

    def __init__(self, coordinator: CuringChamberCoordinator) -> None:
        super().__init__(coordinator, "select_program")

    @property
    def options(self) -> list[str]:
        options = [_NONE] + [program.id for program in self.coordinator.available_programs()]
        # A preset of the other chamber kind may run when started by id (service,
        # automation): keep it selectable so the current option stays valid.
        current = self.current_option
        if current not in options:
            options.append(current)
        return options

    @property
    def current_option(self) -> str:
        program_id = self.coordinator.program.state.program_id
        if program_id and self.coordinator.program.status.value != "idle":
            return program_id
        return _NONE

    async def async_select_option(self, option: str) -> None:
        if option == _NONE:
            await self.coordinator.async_stop_program()
        else:
            await self.coordinator.async_start_program(option)
