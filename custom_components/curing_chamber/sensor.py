"""Sensor entities: derived quantities, program progress, maintenance counters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature, UnitOfTime

from . import config as conf
from .const import DOMAIN
from .entity import CuringChamberEntity
from .regulation import Actuator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import CuringChamberCoordinator


@dataclass(frozen=True, kw_only=True)
class CuringSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor over the coordinator data."""

    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSORS: tuple[CuringSensorDescription, ...] = (
    CuringSensorDescription(
        key="dew_point",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.get("dew_point"),
    ),
    CuringSensorDescription(
        key="absolute_humidity",
        translation_key="absolute_humidity",
        native_unit_of_measurement="g/m³",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.get("absolute_humidity"),
    ),
    CuringSensorDescription(
        key="weight_loss",
        translation_key="weight_loss",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.get("weight_loss_pct"),
    ),
    CuringSensorDescription(
        key="drying_rate",
        translation_key="drying_rate",
        native_unit_of_measurement="%/d",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda d: d.get("drying_rate"),
    ),
    CuringSensorDescription(
        key="phase",
        translation_key="phase",
        value_fn=lambda d: d.get("phase_name"),
        attrs_fn=lambda d: {
            "program_status": d.get("program_status"),
            "phase_index": d.get("phase_index"),
        },
    ),
    CuringSensorDescription(
        key="phase_remaining",
        translation_key="phase_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        value_fn=lambda d: (
            round(d["phase_remaining"] / 3600.0, 2)
            if d.get("phase_remaining") is not None
            else None
        ),
    ),
    CuringSensorDescription(
        key="regulation_state",
        translation_key="regulation_state",
        value_fn=lambda d: d.get("summary"),
        attrs_fn=lambda d: {
            "active_alerts": d.get("active_alerts"),
            "last_decisions": d.get("decisions"),
        },
    ),
    CuringSensorDescription(
        key="batches",
        translation_key="batches",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("active_batch_count"),
        attrs_fn=lambda d: {
            "batches": d.get("batches"),
            "reference_batch_id": d.get("reference_batch_id"),
        },
    ),
    CuringSensorDescription(
        key="reference_batch_loss",
        translation_key="reference_batch_loss",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.get("reference_batch_loss_pct"),
    ),
    CuringSensorDescription(
        key="reference_batch_eta",
        translation_key="reference_batch_eta",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.get("reference_batch_eta"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: CuringChamberCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        CuringChamberSensor(coordinator, description) for description in SENSORS
    ]
    actuator_conf = {
        Actuator.COOL: conf.CONF_COOL_SWITCH,
        Actuator.HEAT: conf.CONF_HEAT_SWITCH,
        Actuator.HUMIDIFY: conf.CONF_HUMIDIFY_SWITCH,
        Actuator.DEHUMIDIFY: conf.CONF_DEHUMIDIFY_SWITCH,
        Actuator.FAN: conf.CONF_FAN_SWITCH,
        Actuator.VENT: conf.CONF_VENT_SWITCH,
    }
    for actuator, key in actuator_conf.items():
        if conf.get(entry, key):
            entities.append(CuringChamberRuntimeSensor(coordinator, actuator))
    async_add_entities(entities)


class CuringChamberSensor(CuringChamberEntity, SensorEntity):
    """A sensor exposing one derived/progress value."""

    entity_description: CuringSensorDescription

    def __init__(
        self, coordinator: CuringChamberCoordinator, description: CuringSensorDescription
    ) -> None:
        super().__init__(coordinator, f"sensor_{description.key}")
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data or {})


class CuringChamberRuntimeSensor(CuringChamberEntity, SensorEntity):
    """Cumulative run-hours of one actuator (maintenance)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: CuringChamberCoordinator, actuator: Actuator) -> None:
        super().__init__(coordinator, f"runtime_{actuator.value}")
        self._actuator = actuator
        self._attr_translation_key = f"runtime_{actuator.value}"

    @property
    def native_value(self) -> float:
        counters = (self.coordinator.data or {}).get("counters", {})
        return round(counters.get(self._actuator.value, 0.0), 2)
