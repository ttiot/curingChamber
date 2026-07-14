"""Climate entity exposing the chamber temperature regulation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from . import config as conf
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
    async_add_entities([CuringChamberClimate(coordinator)])


class CuringChamberClimate(CuringChamberEntity, ClimateEntity):
    """Temperature thermostat backed by the regulation engine."""

    _attr_translation_key = "chamber_temperature"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 0.0
    _attr_max_temp = 30.0

    def __init__(self, coordinator: CuringChamberCoordinator) -> None:
        super().__init__(coordinator, "climate")
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        has_cool = bool(conf.get(coordinator.entry, conf.CONF_COOL_SWITCH))
        has_heat = bool(conf.get(coordinator.entry, conf.CONF_HEAT_SWITCH))
        modes = [HVACMode.OFF]
        if has_cool and has_heat:
            modes.append(HVACMode.HEAT_COOL)
        elif has_cool:
            modes.append(HVACMode.COOL)
        elif has_heat:
            modes.append(HVACMode.HEAT)
        else:
            modes.append(HVACMode.AUTO)  # monitoring only
        self._attr_hvac_modes = modes
        self._active_mode = modes[-1]

    @property
    def current_temperature(self) -> float | None:
        return (self.coordinator.data or {}).get("temp")

    @property
    def target_temperature(self) -> float | None:
        return (self.coordinator.data or {}).get("target_temp")

    @property
    def hvac_mode(self) -> HVACMode:
        if not self.coordinator.regulation_enabled or self.coordinator.maintenance:
            return HVACMode.OFF
        return self._active_mode

    @property
    def hvac_action(self) -> HVACAction:
        if not self.coordinator.regulation_enabled or self.coordinator.maintenance:
            return HVACAction.OFF
        summary = (self.coordinator.data or {}).get("summary")
        if summary == "cooling":
            return HVACAction.COOLING
        if summary == "heating":
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        current_humidity_target = (self.coordinator.data or {}).get("target_humidity")
        await self.coordinator.async_set_targets(temperature, current_humidity_target)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set_regulation_enabled(False)
        else:
            self._active_mode = hvac_mode
            await self.coordinator.async_set_regulation_enabled(True)

    async def async_turn_on(self) -> None:
        await self.coordinator.async_set_regulation_enabled(True)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_regulation_enabled(False)
