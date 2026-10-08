"""Config and options flows for the Curing Chamber integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from . import config as conf
from .const import DOMAIN

try:  # ConfigFlowResult was introduced in HA 2024.4
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:  # pragma: no cover - older HA fallback
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult

if TYPE_CHECKING:
    pass

_SENSOR_KEYS = (
    conf.CONF_TEMP_SENSOR,
    conf.CONF_HUMIDITY_SENSOR,
    conf.CONF_TEMP_SENSOR_2,
    conf.CONF_HUMIDITY_SENSOR_2,
    conf.CONF_PRODUCT_TEMP_SENSOR,
    conf.CONF_WEIGHT_SENSOR,
    conf.CONF_CO2_SENSOR,
)
_ACTUATOR_KEYS = (
    conf.CONF_COOL_SWITCH,
    conf.CONF_HEAT_SWITCH,
    conf.CONF_HUMIDIFY_SWITCH,
    conf.CONF_DEHUMIDIFY_SWITCH,
    conf.CONF_FAN_SWITCH,
    conf.CONF_VENT_SWITCH,
)


def _sensor_selector(device_classes: list[str] | None = None) -> selector.EntitySelector:
    config = selector.EntitySelectorConfig(domain="sensor")
    if device_classes:
        config["device_class"] = device_classes
    return selector.EntitySelector(config)


def _actuator_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["switch", "input_boolean", "fan", "light"])
    )


def _number(minimum: float, maximum: float, step: float, unit: str | None = None):
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement=unit,
        )
    )


def _sensors_schema(defaults: dict[str, Any]) -> vol.Schema:
    def opt(key: str, sel: selector.Selector) -> Any:
        if defaults.get(key):
            return vol.Optional(key, default=defaults[key])
        return vol.Optional(key)

    return vol.Schema(
        {
            opt(conf.CONF_TEMP_SENSOR, _sensor_selector(["temperature"])): _sensor_selector(
                ["temperature"]
            ),
            opt(conf.CONF_HUMIDITY_SENSOR, _sensor_selector(["humidity"])): _sensor_selector(
                ["humidity"]
            ),
            opt(conf.CONF_TEMP_SENSOR_2, _sensor_selector(["temperature"])): _sensor_selector(
                ["temperature"]
            ),
            opt(conf.CONF_HUMIDITY_SENSOR_2, _sensor_selector(["humidity"])): _sensor_selector(
                ["humidity"]
            ),
            opt(conf.CONF_PRODUCT_TEMP_SENSOR, _sensor_selector(["temperature"])): _sensor_selector(
                ["temperature"]
            ),
            opt(conf.CONF_WEIGHT_SENSOR, _sensor_selector()): _sensor_selector(),
            opt(conf.CONF_CO2_SENSOR, _sensor_selector()): _sensor_selector(),
            opt(
                conf.CONF_DOOR_SENSOR,
                selector.EntitySelector(selector.EntitySelectorConfig(domain="binary_sensor")),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="binary_sensor")),
        }
    )


def _kind_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(conf.CHAMBER_KINDS),
            translation_key="chamber_kind",
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _actuators_schema(defaults: dict[str, Any]) -> vol.Schema:
    fields: dict[Any, Any] = {}
    for key in _ACTUATOR_KEYS:
        marker = (
            vol.Optional(key, default=defaults[key]) if defaults.get(key) else vol.Optional(key)
        )
        fields[marker] = _actuator_selector()
    return vol.Schema(fields)


class CuringChamberConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data[conf.CONF_NAME] = user_input[conf.CONF_NAME]
            self._data.update({k: v for k, v in user_input.items() if k != conf.CONF_NAME})
            return await self.async_step_actuators()

        schema = vol.Schema(
            {
                vol.Required(conf.CONF_NAME, default="Curing Chamber"): str,
                vol.Required(
                    conf.CONF_CHAMBER_KIND, default=conf.DEFAULT_CHAMBER_KIND
                ): _kind_selector(),
            }
        ).extend(_sensors_schema({}).schema)
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_actuators(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_notifications()
        return self.async_show_form(step_id="actuators", data_schema=_actuators_schema({}))

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_food_safety()
        schema = vol.Schema(
            {
                vol.Optional(conf.CONF_NOTIFY_SERVICES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._notify_services(),
                        multiple=True,
                        custom_value=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="notifications", data_schema=schema)

    async def async_step_food_safety(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title=self._data[conf.CONF_NAME], data=self._data)
        return self.async_show_form(step_id="food_safety", data_schema=vol.Schema({}))

    def _notify_services(self) -> list[str]:
        return sorted(
            f"notify.{service}" for service in self.hass.services.async_services().get("notify", {})
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> CuringChamberOptionsFlow:
        return CuringChamberOptionsFlow(entry)


class CuringChamberOptionsFlow(OptionsFlow):
    """Reconfigure everything after installation (§2)."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["sensors", "actuators", "regulation", "notifications"],
        )

    def _merged(self) -> dict[str, Any]:
        return {**self._entry.data, **self._entry.options}

    def _save(self, updates: dict[str, Any]) -> ConfigFlowResult:
        options = {**self._entry.options, **updates}
        return self.async_create_entry(title="", data=options)

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(user_input)
        return self.async_show_form(step_id="sensors", data_schema=_sensors_schema(self._merged()))

    async def async_step_actuators(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(user_input)
        return self.async_show_form(
            step_id="actuators", data_schema=_actuators_schema(self._merged())
        )

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(user_input)
        current = self._merged().get(conf.CONF_NOTIFY_SERVICES, [])
        services = sorted(
            {f"notify.{s}" for s in self.hass.services.async_services().get("notify", {})}
            | set(current)
        )
        schema = vol.Schema(
            {
                vol.Optional(conf.CONF_NOTIFY_SERVICES, default=current): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=services,
                        multiple=True,
                        custom_value=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="notifications", data_schema=schema)

    async def async_step_regulation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(user_input)
        m = self._merged()

        def default(key: str, fallback: float) -> float:
            return float(m.get(key, fallback))

        schema = vol.Schema(
            {
                vol.Required(
                    conf.CONF_CHAMBER_KIND,
                    default=m.get(conf.CONF_CHAMBER_KIND, conf.DEFAULT_CHAMBER_KIND),
                ): _kind_selector(),
                vol.Optional(
                    conf.CONF_TEMP_DEADBAND,
                    default=default(conf.CONF_TEMP_DEADBAND, conf.DEFAULT_TEMP_DEADBAND),
                ): _number(0.1, 5, 0.1, "°C"),
                vol.Optional(
                    conf.CONF_HUMIDITY_DEADBAND,
                    default=default(conf.CONF_HUMIDITY_DEADBAND, conf.DEFAULT_HUMIDITY_DEADBAND),
                ): _number(0.5, 20, 0.5, "%"),
                vol.Optional(
                    conf.CONF_COOL_MIN_OFF,
                    default=default(conf.CONF_COOL_MIN_OFF, conf.DEFAULT_COOL_MIN_OFF),
                ): _number(0, 3600, 10, "s"),
                vol.Optional(
                    conf.CONF_COOL_MIN_ON,
                    default=default(conf.CONF_COOL_MIN_ON, conf.DEFAULT_COOL_MIN_ON),
                ): _number(0, 3600, 10, "s"),
                vol.Optional(
                    conf.CONF_ACTUATOR_MIN_OFF,
                    default=default(conf.CONF_ACTUATOR_MIN_OFF, conf.DEFAULT_ACTUATOR_MIN_OFF),
                ): _number(0, 3600, 10, "s"),
                vol.Optional(
                    conf.CONF_ACTUATOR_MIN_ON,
                    default=default(conf.CONF_ACTUATOR_MIN_ON, conf.DEFAULT_ACTUATOR_MIN_ON),
                ): _number(0, 3600, 10, "s"),
                vol.Optional(
                    conf.CONF_STARTUP_DELAY,
                    default=default(conf.CONF_STARTUP_DELAY, conf.DEFAULT_STARTUP_DELAY),
                ): _number(0, 1800, 10, "s"),
                vol.Optional(
                    conf.CONF_HUMIDITY_ANTI_OSC,
                    default=default(conf.CONF_HUMIDITY_ANTI_OSC, conf.DEFAULT_HUMIDITY_ANTI_OSC),
                ): _number(0, 3600, 10, "s"),
                vol.Optional(
                    conf.CONF_TEMP_ABS_MIN,
                    default=default(conf.CONF_TEMP_ABS_MIN, conf.DEFAULT_TEMP_ABS_MIN),
                ): _number(-30, 30, 0.5, "°C"),
                vol.Optional(
                    conf.CONF_TEMP_ABS_MAX,
                    default=default(conf.CONF_TEMP_ABS_MAX, conf.DEFAULT_TEMP_ABS_MAX),
                ): _number(0, 60, 0.5, "°C"),
                vol.Optional(
                    conf.CONF_HUMIDITY_ABS_MIN,
                    default=default(conf.CONF_HUMIDITY_ABS_MIN, conf.DEFAULT_HUMIDITY_ABS_MIN),
                ): _number(0, 100, 1, "%"),
                vol.Optional(
                    conf.CONF_HUMIDITY_ABS_MAX,
                    default=default(conf.CONF_HUMIDITY_ABS_MAX, conf.DEFAULT_HUMIDITY_ABS_MAX),
                ): _number(0, 100, 1, "%"),
                vol.Optional(
                    conf.CONF_CORE_TEMP_MAX,
                    default=default(conf.CONF_CORE_TEMP_MAX, conf.DEFAULT_CORE_TEMP_MAX),
                ): _number(0, 60, 0.5, "°C"),
                vol.Optional(
                    conf.CONF_CONDENSATION_MARGIN,
                    default=default(
                        conf.CONF_CONDENSATION_MARGIN, conf.condensation_margin_default(m)
                    ),
                ): _number(0.1, 5, 0.1, "°C"),
                vol.Optional(
                    conf.CONF_DEGRADED_DELAY,
                    default=default(conf.CONF_DEGRADED_DELAY, conf.DEFAULT_DEGRADED_DELAY),
                ): _number(0, 86400, 60, "s"),
                vol.Optional(
                    conf.CONF_DEGRADED_REMINDER,
                    default=default(conf.CONF_DEGRADED_REMINDER, conf.DEFAULT_DEGRADED_REMINDER),
                ): _number(300, 86400, 60, "s"),
                vol.Optional(
                    conf.CONF_DOOR_OPEN_ALERT_MINUTES,
                    default=default(
                        conf.CONF_DOOR_OPEN_ALERT_MINUTES, conf.DEFAULT_DOOR_OPEN_ALERT_MINUTES
                    ),
                ): _number(1, 120, 1, "min"),
                vol.Optional(
                    conf.CONF_SENSOR_STALE_MINUTES,
                    default=default(
                        conf.CONF_SENSOR_STALE_MINUTES, conf.DEFAULT_SENSOR_STALE_MINUTES
                    ),
                ): _number(1, 240, 1, "min"),
                vol.Optional(
                    conf.CONF_TICK_INTERVAL,
                    default=default(conf.CONF_TICK_INTERVAL, conf.DEFAULT_TICK_INTERVAL),
                ): _number(5, 300, 5, "s"),
            }
        )
        return self.async_show_form(step_id="regulation", data_schema=schema)
