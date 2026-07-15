"""Coordinator: the thin Home Assistant adaptation layer around the engines.

Reads source entities into :class:`RegulationInputs`, runs the pure regulation
and program engines, applies the resulting commands to the actuator entities,
raises notifications/events and persists the running program.
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components import persistent_notification
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify
from homeassistant.util.unit_conversion import TemperatureConverter

from . import batch as batch_engine
from . import config as conf
from . import messages
from .batch import Batch, BatchStatus, WeightSample
from .const import (
    DOMAIN,
    EVENT_CURING_CHAMBER,
    EVENT_TYPE_ALERT_CLEARED,
    EVENT_TYPE_ALERT_RAISED,
    EVENT_TYPE_BATCH_COMPLETED,
    EVENT_TYPE_MANUAL_ACTION,
    EVENT_TYPE_PHASE_CHANGED,
    EVENT_TYPE_PROGRAM_COMPLETED,
    PHOTO_WWW_SUBDIR,
)
from .program import PRESETS, ProgramEngine, ProgramEventType, ProgramStatus
from .program.presets import preset_by_id
from .program.types import Program
from .regulation import (
    Actuator,
    Alert,
    AlertKey,
    RegulationConfig,
    RegulationEngine,
    RegulationInputs,
    derived,
)
from .regulation.filters import SensorFilter, average, divergence
from .regulation.types import ActuatorConfig, ManualAction
from .storage import CuringChamberStore

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

_ACTUATOR_CONF = {
    Actuator.COOL: conf.CONF_COOL_SWITCH,
    Actuator.HEAT: conf.CONF_HEAT_SWITCH,
    Actuator.HUMIDIFY: conf.CONF_HUMIDIFY_SWITCH,
    Actuator.DEHUMIDIFY: conf.CONF_DEHUMIDIFY_SWITCH,
    Actuator.FAN: conf.CONF_FAN_SWITCH,
    Actuator.VENT: conf.CONF_VENT_SWITCH,
}


def _photo_bytes(photo: str) -> bytes | None:
    """Decode a weigh-in photo supplied as a data URL, base64 or a local path."""
    if not photo:
        return None
    if photo.startswith("data:"):
        _, _, encoded = photo.partition(",")
        try:
            return base64.b64decode(encoded)
        except (binascii.Error, ValueError):
            return None
    if os.path.isfile(photo):
        with open(photo, "rb") as handle:
            return handle.read()
    try:
        return base64.b64decode(photo, validate=True)
    except (binascii.Error, ValueError):
        return None


class CuringChamberCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Drive one curing chamber."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        tick = conf.get(entry, conf.CONF_TICK_INTERVAL, conf.DEFAULT_TICK_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=tick),
        )
        self.regulation = RegulationEngine(start=dt_util.utcnow().timestamp())
        self.program = ProgramEngine()
        self.store = CuringChamberStore(hass, entry.entry_id)
        self._temp_filter = SensorFilter()
        self._temp2_filter = SensorFilter()
        self._humidity_filter = SensorFilter()
        self._humidity2_filter = SensorFilter()
        self._unsub: list[Any] = []
        self._retry: dict[Actuator, int] = {}
        self._active_alerts: set[str] = set()
        self._alert_details: dict[str, dict[str, Any]] = {}
        self._manual_targets: tuple[float | None, float | None] = (None, None)
        self._regulation_enabled = True
        self._maintenance = False
        self._last_actuator_states: dict[Actuator, bool] = {}
        self._last_weight: tuple[float, float] | None = None  # (weight, timestamp)
        self._drying_rate: float | None = None
        self.batches: dict[str, Batch] = {}
        self.chamber_name: str = conf.get(entry, conf.CONF_NAME, entry.title)

    # -- Lifecycle -----------------------------------------------------------

    async def async_prepare(self) -> None:
        """Load persistence and restore any running program."""
        await self.store.async_load()
        self._configure_filters()
        state_blob = self.store.program_state
        if state_blob:
            self.program = ProgramEngine.from_dict(state_blob)
        self.batches = {
            batch_id: Batch.from_dict(raw) for batch_id, raw in self.store.batches.items()
        }
        self._track_sources()

    def _configure_filters(self) -> None:
        samples = int(conf.get(self.entry, conf.CONF_FILTER_SAMPLES, conf.DEFAULT_FILTER_SAMPLES))
        stale = (
            float(
                conf.get(
                    self.entry, conf.CONF_SENSOR_STALE_MINUTES, conf.DEFAULT_SENSOR_STALE_MINUTES
                )
            )
            * 60.0
        )
        self._temp_filter = SensorFilter(samples=samples, stale_seconds=stale)
        self._temp2_filter = SensorFilter(samples=samples, stale_seconds=stale)
        self._humidity_filter = SensorFilter(samples=samples, stale_seconds=stale)
        self._humidity2_filter = SensorFilter(samples=samples, stale_seconds=stale)

    @callback
    def _track_sources(self) -> None:
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()
        entities = [
            conf.get(self.entry, key)
            for key in (
                conf.CONF_TEMP_SENSOR,
                conf.CONF_HUMIDITY_SENSOR,
                conf.CONF_TEMP_SENSOR_2,
                conf.CONF_HUMIDITY_SENSOR_2,
                conf.CONF_DOOR_SENSOR,
                conf.CONF_WEIGHT_SENSOR,
                conf.CONF_CO2_SENSOR,
                conf.CONF_PRODUCT_TEMP_SENSOR,
                *(_ACTUATOR_CONF.values()),
            )
        ]
        entities = [e for e in entities if e]
        if entities:
            self._unsub.append(
                async_track_state_change_event(self.hass, entities, self._on_source_change)
            )

    @callback
    def _on_source_change(self, _event: Event) -> None:
        self.hass.async_create_task(self.async_request_refresh())

    async def async_shutdown(self) -> None:
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()
        await super().async_shutdown()

    # -- Main tick -----------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        now = dt_util.utcnow().timestamp()
        inputs = self._read_inputs(now)
        reg_config = self._build_config(inputs)

        # Advance the program (may change active targets and emit events). The
        # weight driving the weight-loss end condition is the reference batch's
        # latest weigh-in, falling back to the chamber scale (see _read_inputs).
        program_events = self.program.tick(now, weight=inputs.weight)
        for event in program_events:
            self._handle_program_event(event, inputs)

        self._check_batch_completion()

        outputs = self.regulation.tick(inputs, reg_config, now)
        await self._apply_commands(outputs)
        self._handle_alerts(outputs.alerts)
        self._update_counters(outputs, reg_config)

        self._persist_program()
        return self._snapshot(inputs, reg_config, outputs)

    def _check_batch_completion(self) -> None:
        """Mark active batches whose target weight loss has been reached."""
        changed = False
        for batch in self.batches.values():
            if batch.status is not BatchStatus.ACTIVE or batch.target_loss_pct is None:
                continue
            loss = batch_engine.current_loss_pct(batch)
            if loss is not None and loss >= batch.target_loss_pct:
                batch.status = BatchStatus.COMPLETED
                changed = True
                self._fire_event(
                    EVENT_TYPE_BATCH_COMPLETED,
                    {"batch_id": batch.id, "name": batch.name, "loss_pct": round(loss, 1)},
                )
        if changed:
            self._persist_batches()

    # -- Reading sensors -----------------------------------------------------

    def _num_state(self, key: str) -> tuple[float | None, str | None]:
        entity_id = conf.get(self.entry, key)
        if not entity_id:
            return None, None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
            return None, None
        try:
            return float(state.state), state.attributes.get("unit_of_measurement")
        except (ValueError, TypeError):
            return None, None

    def _temp_c(self, key: str) -> float | None:
        value, unit = self._num_state(key)
        if value is None:
            return None
        if unit == UnitOfTemperature.FAHRENHEIT:
            return TemperatureConverter.convert(
                value, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
            )
        return value

    def _bool_state(self, key: str) -> bool:
        entity_id = conf.get(self.entry, key)
        if not entity_id:
            return False
        state = self.hass.states.get(entity_id)
        return state is not None and state.state == STATE_ON

    def _read_inputs(self, now: float) -> RegulationInputs:
        raw_t1 = self._temp_c(conf.CONF_TEMP_SENSOR)
        raw_t2 = self._temp_c(conf.CONF_TEMP_SENSOR_2)
        raw_h1, _ = self._num_state(conf.CONF_HUMIDITY_SENSOR)
        raw_h2, _ = self._num_state(conf.CONF_HUMIDITY_SENSOR_2)

        t1 = self._temp_filter.update(raw_t1, now)
        t2 = self._temp2_filter.update(raw_t2, now)
        h1 = self._humidity_filter.update(raw_h1, now)
        h2 = self._humidity2_filter.update(raw_h2, now)

        temp_values = [r.value for r in (t1, t2) if r.value is not None and r.valid]
        hum_values = [r.value for r in (h1, h2) if r.value is not None and r.valid]
        temp = average(temp_values)
        humidity = average(hum_values)

        weight = self._reference_weight_now()
        co2, _ = self._num_state(conf.CONF_CO2_SENSOR)
        product_temp = self._temp_c(conf.CONF_PRODUCT_TEMP_SENSOR)
        door_open = self._bool_state(conf.CONF_DOOR_SENSOR)
        self._update_drying_rate(weight, now)

        actuator_states = {
            actuator: self._bool_state(key)
            for actuator, key in _ACTUATOR_CONF.items()
            if conf.get(self.entry, key)
        }

        return RegulationInputs(
            temp=temp,
            temp_valid=temp is not None,
            humidity=humidity,
            humidity_valid=humidity is not None,
            temp_probes=tuple(v for v in (t1.value, t2.value) if v is not None),
            humidity_probes=tuple(v for v in (h1.value, h2.value) if v is not None),
            door_open=door_open,
            weight=weight,
            co2=co2,
            product_temp=product_temp,
            drying_rate=self._drying_rate,
            actuator_states=actuator_states,
        )

    def _reference_weight_now(self) -> float | None:
        """Weight driving loss/rate: the reference batch's latest weigh-in.

        Falls back to the chamber scale (``CONF_WEIGHT_SENSOR``) so a chamber
        with no batch behaves exactly as before this feature existed.
        """
        ref_id = self.store.reference_batch_id
        if ref_id:
            batch = self.batches.get(ref_id)
            if batch is not None and batch.latest_weight is not None:
                return batch.latest_weight
        weight, _ = self._num_state(conf.CONF_WEIGHT_SENSOR)
        return weight

    def _update_drying_rate(self, weight: float | None, now: float) -> None:
        ref = self.program.state.reference_weight
        if weight is None or ref is None or ref <= 0:
            return
        if self._last_weight is None:
            self._last_weight = (weight, now)
            return
        prev_w, prev_t = self._last_weight
        if now - prev_t >= 3600:  # recompute at most hourly to damp noise
            days = (now - prev_t) / 86400.0
            if days > 0:
                self._drying_rate = (prev_w - weight) / ref * 100.0 / days
            self._last_weight = (weight, now)

    # -- Building the regulation config --------------------------------------

    def _active_targets(self) -> tuple[float | None, float | None, bool]:
        """Return (target_temp, target_humidity, drying_phase)."""
        if self.program.status in (ProgramStatus.RUNNING, ProgramStatus.PAUSED):
            temp, humidity = self.program.active_targets()
            phase = self.program.current_phase
            drying = bool(phase and phase.name == "drying")
            return temp, humidity, drying
        if self.program.status is ProgramStatus.COMPLETED:
            temp, humidity = self.program.active_on_complete_targets()
            return temp, humidity, False
        return self._manual_targets[0], self._manual_targets[1], False

    def _build_config(self, inputs: RegulationInputs) -> RegulationConfig:
        e = self.entry
        target_temp, target_humidity, drying = self._active_targets()
        cool_on = float(conf.get(e, conf.CONF_COOL_MIN_ON, conf.DEFAULT_COOL_MIN_ON))
        cool_off = float(conf.get(e, conf.CONF_COOL_MIN_OFF, conf.DEFAULT_COOL_MIN_OFF))
        other_on = float(conf.get(e, conf.CONF_ACTUATOR_MIN_ON, conf.DEFAULT_ACTUATOR_MIN_ON))
        other_off = float(conf.get(e, conf.CONF_ACTUATOR_MIN_OFF, conf.DEFAULT_ACTUATOR_MIN_OFF))

        actuators: dict[Actuator, ActuatorConfig] = {}
        for actuator, key in _ACTUATOR_CONF.items():
            if conf.get(e, key):
                if actuator is Actuator.COOL:
                    actuators[actuator] = ActuatorConfig(True, cool_on, cool_off)
                else:
                    actuators[actuator] = ActuatorConfig(True, other_on, other_off)

        return RegulationConfig(
            target_temp=target_temp,
            target_humidity=target_humidity,
            temp_deadband=float(conf.get(e, conf.CONF_TEMP_DEADBAND, conf.DEFAULT_TEMP_DEADBAND)),
            humidity_deadband=float(
                conf.get(e, conf.CONF_HUMIDITY_DEADBAND, conf.DEFAULT_HUMIDITY_DEADBAND)
            ),
            actuators=actuators,
            startup_delay=float(conf.get(e, conf.CONF_STARTUP_DELAY, conf.DEFAULT_STARTUP_DELAY)),
            humidity_anti_oscillation=float(
                conf.get(e, conf.CONF_HUMIDITY_ANTI_OSC, conf.DEFAULT_HUMIDITY_ANTI_OSC)
            ),
            temp_abs_min=float(conf.get(e, conf.CONF_TEMP_ABS_MIN, conf.DEFAULT_TEMP_ABS_MIN)),
            temp_abs_max=float(conf.get(e, conf.CONF_TEMP_ABS_MAX, conf.DEFAULT_TEMP_ABS_MAX)),
            humidity_abs_min=float(
                conf.get(e, conf.CONF_HUMIDITY_ABS_MIN, conf.DEFAULT_HUMIDITY_ABS_MIN)
            ),
            humidity_abs_max=float(
                conf.get(e, conf.CONF_HUMIDITY_ABS_MAX, conf.DEFAULT_HUMIDITY_ABS_MAX)
            ),
            sensor_divergence_temp=float(
                conf.get(e, conf.CONF_SENSOR_DIVERGENCE_TEMP, conf.DEFAULT_SENSOR_DIVERGENCE_TEMP)
            ),
            sensor_divergence_humidity=float(
                conf.get(
                    e, conf.CONF_SENSOR_DIVERGENCE_HUMIDITY, conf.DEFAULT_SENSOR_DIVERGENCE_HUMIDITY
                )
            ),
            degraded_band_factor=float(
                conf.get(e, conf.CONF_DEGRADED_BAND_FACTOR, conf.DEFAULT_DEGRADED_BAND_FACTOR)
            ),
            degraded_delay=float(
                conf.get(e, conf.CONF_DEGRADED_DELAY, conf.DEFAULT_DEGRADED_DELAY)
            ),
            degraded_reminder=float(
                conf.get(e, conf.CONF_DEGRADED_REMINDER, conf.DEFAULT_DEGRADED_REMINDER)
            ),
            door_open_alert_seconds=float(
                conf.get(e, conf.CONF_DOOR_OPEN_ALERT_MINUTES, conf.DEFAULT_DOOR_OPEN_ALERT_MINUTES)
            )
            * 60.0,
            case_hardening_rate=float(
                conf.get(e, conf.CONF_CASE_HARDENING_RATE, conf.DEFAULT_CASE_HARDENING_RATE)
            ),
            high_temp_drying_limit=float(
                conf.get(e, conf.CONF_HIGH_TEMP_DRYING_LIMIT, conf.DEFAULT_HIGH_TEMP_DRYING_LIMIT)
            ),
            high_temp_drying_duration=float(
                conf.get(
                    e, conf.CONF_HIGH_TEMP_DRYING_DURATION, conf.DEFAULT_HIGH_TEMP_DRYING_DURATION
                )
            ),
            fan_period=float(conf.get(e, conf.CONF_FAN_PERIOD, conf.DEFAULT_FAN_PERIOD)),
            fan_run=float(conf.get(e, conf.CONF_FAN_RUN, conf.DEFAULT_FAN_RUN)),
            vent_period=float(conf.get(e, conf.CONF_VENT_PERIOD, conf.DEFAULT_VENT_PERIOD)),
            vent_run=float(conf.get(e, conf.CONF_VENT_RUN, conf.DEFAULT_VENT_RUN)),
            co2_threshold=float(conf.get(e, conf.CONF_CO2_THRESHOLD, conf.DEFAULT_CO2_THRESHOLD)),
            regulation_enabled=self._regulation_enabled and not self._maintenance,
            maintenance_mode=self._maintenance,
            drying_phase=drying,
        )

    # -- Applying commands ---------------------------------------------------

    async def _apply_commands(self, outputs: Any) -> None:
        for actuator, desired in outputs.commands.items():
            key = _ACTUATOR_CONF[actuator]
            entity_id = conf.get(self.entry, key)
            if not entity_id:
                continue
            state = self.hass.states.get(entity_id)
            actual = state is not None and state.state == STATE_ON

            # Manual-override detection: real state differs from our command.
            previous = self._last_actuator_states.get(actuator)
            if previous is not None and actual not in (previous, desired):
                _LOGGER.debug(
                    "%s: manual override detected on %s (is %s)",
                    self.chamber_name,
                    entity_id,
                    actual,
                )
                self.regulation.sync_actual_state(actuator, actual, dt_util.utcnow().timestamp())

            if actual != desired:
                await self._switch(entity_id, actuator, desired)
            self._last_actuator_states[actuator] = desired

    async def _switch(self, entity_id: str, actuator: Actuator, on: bool) -> None:
        domain = entity_id.split(".", 1)[0]
        service = SERVICE_TURN_ON if on else SERVICE_TURN_OFF
        native = domain in ("switch", "input_boolean", "fan", "light")
        service_domain = domain if native else "homeassistant"
        try:
            await self.hass.services.async_call(
                service_domain, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
            )
            self._retry[actuator] = 0
        except Exception as err:  # surface as retry/alert, never crash the tick
            count = self._retry.get(actuator, 0) + 1
            self._retry[actuator] = count
            _LOGGER.warning(
                "%s: failed to command %s (attempt %s): %s",
                self.chamber_name,
                entity_id,
                count,
                err,
            )

    # -- Alerts / notifications / events -------------------------------------

    def _handle_alerts(self, alerts: list[Alert]) -> None:
        for alert in alerts:
            key = alert.key.value
            if alert.resolved:
                self._active_alerts.discard(key)
                self._alert_details.pop(key, None)
                self._fire_event(EVENT_TYPE_ALERT_CLEARED, {"alert": key})
                self._notify(alert)
                continue
            if not alert.reminder:
                self._active_alerts.add(key)
                self._alert_details[key] = {
                    "level": alert.level.value,
                    "manual_action": alert.manual_action.value,
                    **alert.params,
                }
            event_type = (
                EVENT_TYPE_MANUAL_ACTION
                if alert.manual_action is not ManualAction.NONE
                else EVENT_TYPE_ALERT_RAISED
            )
            self._fire_event(
                event_type,
                {
                    "alert": key,
                    "level": alert.level.value,
                    "manual_action": alert.manual_action.value,
                    **alert.params,
                },
            )
            self._notify(alert)

    def _notify(self, alert: Alert) -> None:
        language = self.hass.config.language
        message = messages.alert_message(alert, language)
        title = f"{messages.title(language)} — {self.chamber_name}"
        notif_id = f"{DOMAIN}_{self.entry.entry_id}_{alert.key.value}"
        if alert.resolved:
            persistent_notification.async_dismiss(self.hass, notif_id)
        else:
            persistent_notification.async_create(
                self.hass, message, title=title, notification_id=notif_id
            )
        for service in conf.get(self.entry, conf.CONF_NOTIFY_SERVICES, []) or []:
            self._call_notify_service(service, title, message)

    def _call_notify_service(self, service: str, title: str, message: str) -> None:
        domain, _, name = service.partition(".")
        if not name:
            domain, name = "notify", service
        self.hass.async_create_task(
            self.hass.services.async_call(
                domain, name, {"title": title, "message": message}, blocking=False
            )
        )

    def _handle_program_event(self, event: Any, inputs: RegulationInputs) -> None:
        language = self.hass.config.language
        if event.type is ProgramEventType.PROGRAM_COMPLETED:
            self._fire_event(EVENT_TYPE_PROGRAM_COMPLETED, {"program": event.phase_name})
            body = messages.program_message("program_completed", language, program=event.phase_name)
        elif event.type is ProgramEventType.PHASE_STARTED:
            self._fire_event(
                EVENT_TYPE_PHASE_CHANGED,
                {"phase": event.phase_name, "index": event.phase_index},
            )
            body = messages.program_message("phase_started", language, phase=event.phase_name)
        else:  # PHASE_ENDED
            if not event.notify:
                return
            body = messages.program_message("phase_ended", language, phase=event.phase_name)
        title = f"{messages.title(language)} — {self.chamber_name}"
        persistent_notification.async_create(self.hass, body, title=title)

    @callback
    def _fire_event(self, event_type: str, data: dict[str, Any]) -> None:
        self.hass.bus.async_fire(
            EVENT_CURING_CHAMBER,
            {"entry_id": self.entry.entry_id, "type": event_type, **data},
        )

    # -- Counters / persistence ---------------------------------------------

    def _update_counters(self, outputs: Any, reg_config: RegulationConfig) -> None:
        interval = self.update_interval.total_seconds() if self.update_interval else 30.0
        counters = self.store.counters
        for actuator, on in outputs.commands.items():
            if on:
                counters[actuator.value] = counters.get(actuator.value, 0.0) + interval / 3600.0

    def _persist_program(self) -> None:
        self.store.set_program_state(
            self.program.to_dict() if self.program.status is not ProgramStatus.IDLE else None
        )
        self.store.async_save()

    def _persist_batches(self) -> None:
        self.store.batches.clear()
        for batch_id, batch in self.batches.items():
            self.store.upsert_batch(batch_id, batch.to_dict())
        self.store.async_save()

    # -- Public control API (used by services / entities) --------------------

    def available_programs(self) -> list[Program]:
        """Return built-in presets plus user-defined programs."""
        user = [Program.from_dict(p) for p in self.store.programs.values()]
        return list(PRESETS) + user

    def find_program(self, program_id: str) -> Program | None:
        preset = preset_by_id(program_id)
        if preset:
            return preset
        raw = self.store.programs.get(program_id)
        return Program.from_dict(raw) if raw else None

    async def async_start_program(self, program_id: str) -> None:
        program = self.find_program(program_id)
        if program is None:
            raise ValueError(f"Unknown program '{program_id}'")
        now = dt_util.utcnow().timestamp()
        events = self.program.start(program, now, self.program.state.reference_weight)
        for event in events:
            self._handle_program_event(event, self._read_inputs(now))
        await self.async_request_refresh()

    async def async_stop_program(self) -> None:
        self.program.stop()
        await self.async_request_refresh()

    async def async_pause_program(self) -> None:
        self.program.pause(dt_util.utcnow().timestamp())
        await self.async_request_refresh()

    async def async_resume_program(self) -> None:
        self.program.resume(dt_util.utcnow().timestamp())
        await self.async_request_refresh()

    async def async_next_phase(self) -> None:
        now = dt_util.utcnow().timestamp()
        events = self.program.next_phase(now)
        for event in events:
            self._handle_program_event(event, self._read_inputs(now))
        await self.async_request_refresh()

    async def async_set_targets(self, temp: float | None, humidity: float | None) -> None:
        self._manual_targets = (temp, humidity)
        await self.async_request_refresh()

    async def async_set_reference_weight(self, weight: float | None) -> None:
        if weight is None:
            weight, _ = self._num_state(conf.CONF_WEIGHT_SENSOR)
        if weight is not None:
            self.program.set_reference_weight(weight)
            self._last_weight = None
            await self.async_request_refresh()

    async def async_acknowledge_alerts(self) -> None:
        for key in AlertKey:
            self.regulation.acknowledge(key)
        await self.async_request_refresh()

    async def async_set_regulation_enabled(self, enabled: bool) -> None:
        self._regulation_enabled = enabled
        await self.async_request_refresh()

    async def async_set_maintenance(self, enabled: bool) -> None:
        self._maintenance = enabled
        await self.async_request_refresh()

    async def async_create_program(self, program: Program) -> None:
        self.store.upsert_program(program.id, program.to_dict())
        self.store.async_save()

    async def async_delete_program(self, program_id: str) -> bool:
        removed = self.store.delete_program(program_id)
        if removed:
            self.store.async_save()
        return removed

    # -- Batch control API (used by services / entities) ---------------------

    def _new_batch_id(self, name: str) -> str:
        base = slugify(name) or "batch"
        candidate = base
        index = 2
        while candidate in self.batches:
            candidate = f"{base}_{index}"
            index += 1
        return candidate

    async def async_create_batch(
        self,
        *,
        name: str,
        product: str | None = None,
        program_id: str | None = None,
        reference_weight: float | None = None,
        target_loss_pct: float | None = None,
        set_as_reference: bool = False,
    ) -> Batch:
        """Create a new batch; make it the reference when asked or if it's first."""
        batch = Batch(
            id=self._new_batch_id(name),
            name=name,
            product=product,
            program_id=program_id,
            reference_weight=reference_weight,
            target_loss_pct=target_loss_pct,
            created_at=dt_util.utcnow().timestamp(),
        )
        self.batches[batch.id] = batch
        if set_as_reference or self.store.reference_batch_id is None:
            self.store.set_reference_batch(batch.id)
            self._last_weight = None
        self._persist_batches()
        # Force an immediate refresh so batch sensors reflect the change now
        # (a debounced request would coalesce with a preceding one).
        await self.async_refresh()
        return batch

    async def async_record_weight(
        self,
        batch_id: str,
        weight: float,
        *,
        timestamp: float | None = None,
        note: str | None = None,
        photo: str | None = None,
    ) -> None:
        """Append a weigh-in (with optional note/photo) to a batch."""
        batch = self.batches.get(batch_id)
        if batch is None:
            raise ValueError(f"Unknown batch '{batch_id}'")
        ts = timestamp if timestamp is not None else dt_util.utcnow().timestamp()
        photo_url = await self._save_photo(batch_id, ts, photo) if photo else None
        batch.add_sample(WeightSample(timestamp=ts, weight=weight, note=note, photo_url=photo_url))
        self._last_weight = None
        self._persist_batches()
        await self.async_refresh()

    async def async_set_reference_batch(self, batch_id: str) -> None:
        if batch_id not in self.batches:
            raise ValueError(f"Unknown batch '{batch_id}'")
        self.store.set_reference_batch(batch_id)
        self.store.async_save()
        self._last_weight = None
        await self.async_refresh()

    async def _async_set_batch_status(self, batch_id: str, status: BatchStatus) -> None:
        batch = self.batches.get(batch_id)
        if batch is None:
            raise ValueError(f"Unknown batch '{batch_id}'")
        batch.status = status
        self._persist_batches()
        await self.async_refresh()

    async def async_complete_batch(self, batch_id: str) -> None:
        await self._async_set_batch_status(batch_id, BatchStatus.COMPLETED)

    async def async_archive_batch(self, batch_id: str) -> None:
        await self._async_set_batch_status(batch_id, BatchStatus.ARCHIVED)

    async def async_delete_batch(self, batch_id: str) -> bool:
        removed = self.batches.pop(batch_id, None) is not None
        self.store.delete_batch(batch_id)
        if removed:
            self.store.async_save()
            self._last_weight = None
            await self.async_refresh()
        return removed

    async def _save_photo(self, batch_id: str, ts: float, photo: str) -> str | None:
        """Write a weigh-in photo under <config>/www and return its /local URL."""
        directory = self.hass.config.path("www", PHOTO_WWW_SUBDIR, batch_id)
        filename = f"{int(ts)}.jpg"

        def _write() -> str | None:
            data = _photo_bytes(photo)
            if data is None:
                return None
            os.makedirs(directory, exist_ok=True)
            with open(os.path.join(directory, filename), "wb") as handle:
                handle.write(data)
            return f"/local/{PHOTO_WWW_SUBDIR}/{batch_id}/{filename}"

        return await self.hass.async_add_executor_job(_write)

    def _batch_summaries(self, now: float) -> list[dict[str, Any]]:
        """Serialisable per-batch summary consumed by the sensors and card."""
        summaries: list[dict[str, Any]] = []
        for batch in self.batches.values():
            summaries.append(
                {
                    "id": batch.id,
                    "name": batch.name,
                    "product": batch.product,
                    "program_id": batch.program_id,
                    "status": batch.status.value,
                    "reference_weight": batch.effective_reference,
                    "target_loss_pct": batch.target_loss_pct,
                    "last_weight": batch.latest_weight,
                    "loss_pct": batch_engine.current_loss_pct(batch),
                    "drying_rate": batch_engine.drying_rate_pct_per_day(batch),
                    "eta": batch_engine.estimate_eta(batch, now),
                    "created_at": batch.created_at,
                    "samples": [s.to_dict() for s in batch.samples],
                    "last_photo_url": next(
                        (s.photo_url for s in reversed(batch.samples) if s.photo_url), None
                    ),
                }
            )
        return summaries

    @property
    def regulation_enabled(self) -> bool:
        return self._regulation_enabled

    @property
    def maintenance(self) -> bool:
        return self._maintenance

    # -- Snapshot for entities ----------------------------------------------

    def _snapshot(
        self, inputs: RegulationInputs, reg_config: RegulationConfig, outputs: Any
    ) -> dict[str, Any]:
        temp_div = divergence(list(inputs.temp_probes))
        hum_div = divergence(list(inputs.humidity_probes))
        weight_loss = self.program.weight_loss_pct(inputs.weight)
        now = dt_util.utcnow().timestamp()
        batches = self._batch_summaries(now)
        ref_id = self.store.reference_batch_id
        ref_summary = next((b for b in batches if b["id"] == ref_id), None)
        active_batches = sum(1 for b in batches if b["status"] == BatchStatus.ACTIVE.value)
        dew_point = abs_humidity = None
        if inputs.temp is not None and inputs.humidity is not None:
            dew_point = derived.dew_point(inputs.temp, inputs.humidity)
            abs_humidity = derived.absolute_humidity(inputs.temp, inputs.humidity)
        return {
            "inputs": inputs,
            "config": reg_config,
            "outputs": outputs,
            "summary": outputs.summary,
            "commands": outputs.commands,
            "target_temp": reg_config.target_temp,
            "target_humidity": reg_config.target_humidity,
            "temp": inputs.temp,
            "humidity": inputs.humidity,
            "dew_point": dew_point,
            "absolute_humidity": abs_humidity,
            "temp_divergence": temp_div,
            "humidity_divergence": hum_div,
            "weight_loss_pct": weight_loss,
            "drying_rate": inputs.drying_rate,
            "batches": batches,
            "reference_batch_id": ref_id,
            "active_batch_count": active_batches,
            "reference_batch_loss_pct": ref_summary["loss_pct"] if ref_summary else None,
            "reference_batch_eta": (
                dt_util.utc_from_timestamp(ref_summary["eta"])
                if ref_summary and ref_summary["eta"] is not None
                else None
            ),
            "program_status": self.program.status.value,
            "phase_name": (self.program.current_phase.name if self.program.current_phase else None),
            "phase_index": self.program.state.phase_index,
            "phase_remaining": self.program.phase_remaining(now),
            "active_alerts": sorted(self._active_alerts),
            "alert_details": dict(self._alert_details),
            "counters": dict(self.store.counters),
            "decisions": [
                {
                    "actuator": d.actuator.value,
                    "desired": d.desired,
                    "reason": d.reason,
                    "blocked_by": d.blocked_by,
                }
                for d in outputs.decisions
            ],
        }
