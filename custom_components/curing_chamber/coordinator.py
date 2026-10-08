"""Coordinator: the thin Home Assistant adaptation layer around the engines.

Reads source entities into :class:`RegulationInputs`, runs the pure regulation
and program engines, applies the resulting commands to the actuator entities,
raises notifications/events and persists the running program.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import dataclasses
import logging
import os
import re
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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify
from homeassistant.util.unit_conversion import TemperatureConverter

from . import batch as batch_engine
from . import config as conf
from . import messages
from .batch import Batch, BatchEvent, BatchStatus, WeightSample
from .const import (
    COUNTER_DEGRADED,
    DOMAIN,
    EVENT_CURING_CHAMBER,
    EVENT_TYPE_ALERT_CLEARED,
    EVENT_TYPE_ALERT_RAISED,
    EVENT_TYPE_BATCH_ARCHIVED,
    EVENT_TYPE_BATCH_COMPLETED,
    EVENT_TYPE_BATCH_EVENT,
    EVENT_TYPE_MANUAL_ACTION,
    EVENT_TYPE_PHASE_CHANGED,
    EVENT_TYPE_PROGRAM_COMPLETED,
    EVENT_TYPE_REMINDER,
    EVENT_TYPE_WEIGH_IN_DUE,
    PHOTO_STORAGE_DIR,
    PHOTO_URL_BASE,
    PHOTO_WWW_SUBDIR,
)
from .program import ProgramEngine, ProgramEventType, ProgramStatus
from .program.presets import preset_by_id, presets_for
from .program.types import Program, ProgramCategory
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

# Photo file names we generate/accept (defence against path traversal).
_SAFE_NAME = re.compile(r"[A-Za-z0-9_.-]+")

_ACTUATOR_CONF = {
    Actuator.COOL: conf.CONF_COOL_SWITCH,
    Actuator.HEAT: conf.CONF_HEAT_SWITCH,
    Actuator.HUMIDIFY: conf.CONF_HUMIDIFY_SWITCH,
    Actuator.DEHUMIDIFY: conf.CONF_DEHUMIDIFY_SWITCH,
    Actuator.FAN: conf.CONF_FAN_SWITCH,
    Actuator.VENT: conf.CONF_VENT_SWITCH,
}


BATCH_EXPORT_FORMAT = "curing_chamber/batch"


def _opt_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _opt_number(value: object) -> float | None:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


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
        self._last_housekeeping = 0.0
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
        await self._async_migrate_photos()
        self._track_sources()

    async def _async_migrate_photos(self) -> None:
        """Move legacy ``/local/`` photos to the private store and rewrite URLs.

        Pre-panel releases wrote weigh-in photos under ``<config>/www`` where
        anyone knowing the URL could fetch them without logging in.
        """
        legacy_prefix = f"/local/{PHOTO_WWW_SUBDIR}/"
        moves: list[tuple[str, str]] = []
        changed = False
        for batch in self.batches.values():
            for index, sample in enumerate(batch.samples):
                url = sample.photo_url
                if not url or not url.startswith(legacy_prefix):
                    continue
                filename = url.rsplit("/", 1)[-1]
                if not _SAFE_NAME.fullmatch(filename):
                    continue
                old_path = self.hass.config.path("www", PHOTO_WWW_SUBDIR, batch.id, filename)
                moves.append((old_path, self.photo_path(batch.id, filename)))
                batch.samples[index] = dataclasses.replace(
                    sample, photo_url=self._photo_url(batch.id, filename)
                )
                changed = True
        if not changed:
            return

        def _move_all() -> None:
            for old_path, new_path in moves:
                if not os.path.isfile(old_path):
                    continue
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                os.replace(old_path, new_path)
                # Drop the now-empty public folders (batch dir, then the root).
                for directory in (
                    os.path.dirname(old_path),
                    os.path.dirname(os.path.dirname(old_path)),
                ):
                    with contextlib.suppress(OSError):
                        os.rmdir(directory)

        await self.hass.async_add_executor_job(_move_all)
        self._persist_batches()
        _LOGGER.info("Moved %d weigh-in photo(s) out of the public www folder", len(moves))

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
        reg_config = self._build_config(inputs, now)

        # Advance the program (may change active targets and emit events). The
        # weight driving the weight-loss end condition is the reference batch's
        # latest weigh-in, falling back to the chamber scale (see _read_inputs).
        program_events = self.program.tick(now, weight=inputs.weight, core_temp=inputs.product_temp)
        for event in program_events:
            self._handle_program_event(event, inputs)
        for due in self.program.due_reminders(now):
            self._handle_reminder(due)

        self._check_batch_completion(now)
        self._check_weigh_in_reminders(now)
        await self._async_housekeeping(now)

        outputs = self.regulation.tick(inputs, reg_config, now)
        await self._apply_commands(outputs)
        self._handle_alerts(outputs.alerts)
        self._update_counters(outputs, reg_config)

        self._persist_program()
        return self._snapshot(inputs, reg_config, outputs)

    def _check_batch_completion(self, now: float) -> None:
        """Mark active batches whose target weight loss has been reached."""
        changed = False
        for batch in self.batches.values():
            if batch.status is not BatchStatus.ACTIVE or batch.target_loss_pct is None:
                continue
            loss = batch_engine.current_loss_pct(batch)
            if loss is not None and loss >= batch.target_loss_pct:
                batch.set_status(BatchStatus.COMPLETED, now)
                changed = True
                self._fire_event(
                    EVENT_TYPE_BATCH_COMPLETED,
                    {"batch_id": batch.id, "name": batch.name, "loss_pct": round(loss, 1)},
                )
                self._complete_linked_program(batch, now)
        if changed:
            self._persist_batches()

    # -- Housekeeping of finished batches --------------------------------------

    def _days_option(self, key: str, default: float) -> float:
        return max(0.0, float(conf.get(self.entry, key, default))) * 86400.0

    async def _async_housekeeping(self, now: float) -> None:
        """Archive old completed batches and purge photos of old archived ones.

        Runs at most once an hour. Both behaviours are off by default
        (``auto_archive_days`` / ``purge_photos_days`` = 0).
        """
        if now - self._last_housekeeping < 3600.0:
            return
        self._last_housekeeping = now
        archive_after = self._days_option(
            conf.CONF_AUTO_ARCHIVE_DAYS, conf.DEFAULT_AUTO_ARCHIVE_DAYS
        )
        purge_after = self._days_option(conf.CONF_PURGE_PHOTOS_DAYS, conf.DEFAULT_PURGE_PHOTOS_DAYS)
        changed = False
        for batch in self.batches.values():
            if archive_after > 0 and batch.status is BatchStatus.COMPLETED:
                latest = batch.latest_sample
                since = batch.completed_at or (latest.timestamp if latest else batch.created_at)
                if now - since >= archive_after:
                    batch.set_status(BatchStatus.ARCHIVED, now)
                    changed = True
                    _LOGGER.info("%s: batch %s auto-archived", self.chamber_name, batch.id)
                    self._fire_event(
                        EVENT_TYPE_BATCH_ARCHIVED, {"batch_id": batch.id, "name": batch.name}
                    )
            if purge_after > 0 and batch.status is BatchStatus.ARCHIVED:
                since = batch.archived_at or batch.created_at
                if now - since < purge_after:
                    continue
                for index, sample in enumerate(batch.samples):
                    if sample.photo_url:
                        await self._delete_photo(batch.id, sample.photo_url)
                        batch.samples[index] = dataclasses.replace(sample, photo_url=None)
                        changed = True
        if changed:
            self._persist_batches()

    # -- Weigh-in reminders --------------------------------------------------

    @property
    def weigh_in_reminder_seconds(self) -> float:
        days = float(
            conf.get(
                self.entry, conf.CONF_WEIGH_IN_REMINDER_DAYS, conf.DEFAULT_WEIGH_IN_REMINDER_DAYS
            )
        )
        return max(0.0, days) * 86400.0

    def _weigh_in_due(self, batch: Batch, now: float) -> bool:
        """True when an active batch has gone without a weigh-in for too long."""
        interval = self.weigh_in_reminder_seconds
        if interval <= 0 or batch.status is not BatchStatus.ACTIVE:
            return False
        latest = batch.latest_sample
        last = latest.timestamp if latest else batch.created_at
        return now - last >= interval

    def _check_weigh_in_reminders(self, now: float) -> None:
        """Notify once per interval for each batch whose weigh-in is overdue."""
        interval = self.weigh_in_reminder_seconds
        reminders = self.store.weigh_in_reminders
        changed = False
        for batch in self.batches.values():
            notif_id = f"{DOMAIN}_{self.entry.entry_id}_weigh_in_{batch.id}"
            if not self._weigh_in_due(batch, now):
                if reminders.pop(batch.id, None) is not None:
                    changed = True
                    persistent_notification.async_dismiss(self.hass, notif_id)
                continue
            last_sent = reminders.get(batch.id)
            if last_sent is not None and now - last_sent < interval:
                continue
            latest = batch.latest_sample
            since = latest.timestamp if latest else batch.created_at
            days = int((now - since) // 86400)
            reminders[batch.id] = now
            changed = True
            language = self.hass.config.language
            body = messages.batch_message("weigh_in_due", language, batch=batch.name, days=days)
            title = f"{messages.title(language)} — {self.chamber_name}"
            persistent_notification.async_create(
                self.hass, body, title=title, notification_id=notif_id
            )
            for service in conf.get(self.entry, conf.CONF_NOTIFY_SERVICES, []) or []:
                self._call_notify_service(service, title, body)
            self._fire_event(
                EVENT_TYPE_WEIGH_IN_DUE, {"batch_id": batch.id, "name": batch.name, "days": days}
            )
        # Forget batches that no longer exist.
        for batch_id in [b for b in reminders if b not in self.batches]:
            reminders.pop(batch_id)
            changed = True
        if changed:
            self.store.async_save()

    def _complete_linked_program(self, batch: Batch, now: float) -> None:
        """End the running program when the batch that drives it is done.

        Applies when the batch is linked to the running program (same
        ``program_id``), is the reference batch, and no other active batch is
        linked to that program. The program's ``on_complete`` policy then
        applies (hold the last targets, or stop regulating).
        """
        if (
            batch.program_id is None
            or self.program.status not in (ProgramStatus.RUNNING, ProgramStatus.PAUSED)
            or self.program.state.program_id != batch.program_id
            or self.store.reference_batch_id != batch.id
        ):
            return
        others = [
            b
            for b in self.batches.values()
            if b.id != batch.id
            and b.status is BatchStatus.ACTIVE
            and b.program_id == batch.program_id
        ]
        if others:
            return
        for event in self.program.complete(now):
            self._handle_program_event(event, self._read_inputs(now))

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
        """Weight driving loss/rate (see :meth:`_weight_with_source`)."""
        weight, _ = self._weight_with_source()
        return weight

    def _weight_with_source(self) -> tuple[float | None, str | None]:
        """Current chamber weight and where it comes from.

        Priority: the reference batch's latest weigh-in (``"batch"``), then the
        chamber scale ``CONF_WEIGHT_SENSOR`` (``"scale"``) so a chamber with no
        batch behaves exactly as before batches existed, then the last weight
        typed into the *Manual weight* number entity (``"manual"``) for setups
        with neither a batch nor a scale.
        """
        ref_id = self.store.reference_batch_id
        if ref_id:
            batch = self.batches.get(ref_id)
            if batch is not None and batch.latest_weight is not None:
                return batch.latest_weight, "batch"
        weight, _ = self._num_state(conf.CONF_WEIGHT_SENSOR)
        if weight is not None:
            return weight, "scale"
        manual = self.store.manual_weight
        if manual is not None:
            return manual["weight"], "manual"
        return None, None

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

    def _active_targets(self, now: float) -> tuple[float | None, float | None, bool]:
        """Return (target_temp, target_humidity, drying_phase).

        During a running phase the targets follow the phase ramp, if any.
        """
        if self.program.status in (ProgramStatus.RUNNING, ProgramStatus.PAUSED):
            temp, humidity = self.program.active_targets(now)
            phase = self.program.current_phase
            drying = bool(phase and phase.name == "drying")
            return temp, humidity, drying
        if self.program.status is ProgramStatus.COMPLETED:
            temp, humidity = self.program.active_on_complete_targets()
            return temp, humidity, False
        return self._manual_targets[0], self._manual_targets[1], False

    def _build_config(self, inputs: RegulationInputs, now: float) -> RegulationConfig:
        e = self.entry
        target_temp, target_humidity, drying = self._active_targets(now)
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
            core_temp_max=float(conf.get(e, conf.CONF_CORE_TEMP_MAX, conf.DEFAULT_CORE_TEMP_MAX)),
            actuator_ineffective_seconds=float(
                conf.get(
                    e,
                    conf.CONF_ACTUATOR_INEFFECTIVE_MINUTES,
                    conf.DEFAULT_ACTUATOR_INEFFECTIVE_MINUTES,
                )
            )
            * 60.0,
            condensation_margin=float(
                conf.get(
                    e,
                    conf.CONF_CONDENSATION_MARGIN,
                    conf.condensation_margin_default({**e.data, **e.options}),
                )
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

    def _handle_reminder(self, due: Any) -> None:
        """Notify a program care reminder and point at the batches concerned."""
        language = self.hass.config.language
        program = self.program.program
        program_name = program.name if program else ""
        action = messages.reminder_action(due.reminder.kind, due.reminder.note, language)
        body = messages.program_message(
            "reminder", language, program=program_name, phase=due.phase_name, action=action
        )
        title = f"{messages.title(language)} — {self.chamber_name}"
        notif_id = f"{DOMAIN}_{self.entry.entry_id}_reminder_{due.index}"
        persistent_notification.async_create(self.hass, body, title=title, notification_id=notif_id)
        for service in conf.get(self.entry, conf.CONF_NOTIFY_SERVICES, []) or []:
            self._call_notify_service(service, title, body)
        program_id = self.program.state.program_id
        batch_ids = [
            b.id
            for b in self.batches.values()
            if b.status is BatchStatus.ACTIVE and (b.program_id == program_id or not b.program_id)
        ]
        self._fire_event(
            EVENT_TYPE_REMINDER,
            {
                "kind": due.reminder.kind,
                "note": due.reminder.note,
                "program": program_name,
                "phase": due.phase_name,
                "batch_ids": batch_ids,
            },
        )

    def _next_reminder(self, now: float) -> dict[str, Any] | None:
        nxt = self.program.next_reminder(now)
        if nxt is None:
            return None
        reminder, remaining = nxt
        return {"kind": reminder.kind, "note": reminder.note, "due_in": remaining}

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
        # Hours spent in degraded mode: at least one alert asks for a manual
        # action because no configured actuator can correct the drift.
        if self.manual_action_required:
            counters[COUNTER_DEGRADED] = counters.get(COUNTER_DEGRADED, 0.0) + interval / 3600.0

    @property
    def manual_action_required(self) -> bool:
        """True while an active alert carries a recommended manual action."""
        return any(
            details.get("manual_action") not in (None, ManualAction.NONE.value)
            for details in self._alert_details.values()
        )

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

    @property
    def chamber_kind(self) -> str:
        """The chamber kind (``charcuterie`` or ``cheese``)."""
        return conf.chamber_kind(self.entry)

    def available_programs(self) -> list[Program]:
        """Return the presets of this chamber's kind plus all user programs."""
        user = [Program.from_dict(p) for p in self.store.programs.values()]
        return presets_for(ProgramCategory(self.chamber_kind)) + user

    def user_programs(self) -> list[Program]:
        """Return the user-defined programs (the exportable ones)."""
        return [Program.from_dict(p) for p in self.store.programs.values()]

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
            weight = self._reference_weight_now()
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

    async def async_import_programs(
        self, programs: list[Program], *, overwrite: bool = False
    ) -> tuple[list[str], list[str]]:
        """Store ``programs``; return (imported ids, skipped ids).

        A program whose id already exists is skipped unless ``overwrite``;
        built-in preset ids are always skipped.
        """
        imported: list[str] = []
        skipped: list[str] = []
        for program in programs:
            if preset_by_id(program.id) is not None or (
                program.id in self.store.programs and not overwrite
            ):
                skipped.append(program.id)
                continue
            self.store.upsert_program(
                program.id, dataclasses.replace(program, builtin=False).to_dict()
            )
            imported.append(program.id)
        if imported:
            self.store.async_save()
        return imported, skipped

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
        start_program: bool = False,
    ) -> Batch:
        """Create a new batch; make it the reference when asked or if it's first.

        With ``start_program`` and a ``program_id``, the linked program is
        started unless one is already running or paused (that one is left
        alone so other batches are not disturbed).
        """
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
        if (
            start_program
            and program_id
            and self.program.status not in (ProgramStatus.RUNNING, ProgramStatus.PAUSED)
        ):
            await self.async_start_program(program_id)
        # Force an immediate refresh so batch sensors reflect the change now
        # (a debounced request would coalesce with a preceding one).
        await self.async_refresh()
        return batch

    # -- Batch journal -------------------------------------------------------

    async def async_add_batch_event(
        self,
        batch_id: str,
        kind: str,
        *,
        note: str | None = None,
        timestamp: float | None = None,
    ) -> BatchEvent:
        """Append a journal entry (salting, turning, washing, tasting, note…)."""
        batch = self.batches.get(batch_id)
        if batch is None:
            raise ValueError(f"Unknown batch '{batch_id}'")
        kind = kind.strip()[:40] or "note"
        ts = timestamp if timestamp is not None else dt_util.utcnow().timestamp()
        event = BatchEvent(timestamp=ts, kind=kind, note=note)
        batch.add_event(event)
        self._persist_batches()
        self._fire_event(
            EVENT_TYPE_BATCH_EVENT,
            {"batch_id": batch.id, "name": batch.name, "kind": kind, "note": note},
        )
        await self.async_refresh()
        return event

    async def async_delete_batch_event(self, batch_id: str, timestamp: float) -> None:
        """Remove one journal entry from a batch."""
        batch = self.batches.get(batch_id)
        if batch is None:
            raise ValueError(f"Unknown batch '{batch_id}'")
        event = next((e for e in batch.events if abs(e.timestamp - timestamp) < 1e-3), None)
        if event is None:
            raise ValueError("Unknown journal entry")
        batch.events.remove(event)
        self._persist_batches()
        await self.async_refresh()

    def export_batch(self, batch_id: str) -> dict[str, Any]:
        """Portable record of one batch: data, derived figures, program used."""
        batch = self.batches.get(batch_id)
        if batch is None:
            raise ValueError(f"Unknown batch '{batch_id}'")
        now = dt_util.utcnow().timestamp()
        program = self.find_program(batch.program_id) if batch.program_id else None
        return {
            "format": BATCH_EXPORT_FORMAT,
            "version": 1,
            "exported_at": now,
            "chamber": self.chamber_name,
            "batch": batch.to_dict(),
            "summary": self._batch_summary(batch, now),
            "program": program.to_dict() if program else None,
        }

    async def async_export_batch(
        self, batch_id: str, *, include_photos: bool = False
    ) -> dict[str, Any]:
        """Like :meth:`export_batch`; with ``include_photos`` the weigh-in photos
        are embedded as ``photo_data`` data URLs so the record is self-contained."""
        payload = self.export_batch(batch_id)
        if not include_photos:
            return payload
        samples = payload["batch"]["samples"]

        def _read_all() -> list[str | None]:
            out: list[str | None] = []
            for sample in samples:
                url = sample.get("photo_url")
                prefix = f"{PHOTO_URL_BASE}/{self.entry.entry_id}/{batch_id}/"
                if not url or not url.startswith(prefix):
                    out.append(None)
                    continue
                filename = url.rsplit("/", 1)[-1]
                if not _SAFE_NAME.fullmatch(filename):
                    out.append(None)
                    continue
                try:
                    with open(self.photo_path(batch_id, filename), "rb") as handle:
                        data = base64.b64encode(handle.read()).decode()
                except OSError:
                    out.append(None)
                    continue
                out.append(f"data:image/jpeg;base64,{data}")
            return out

        embedded = await self.hass.async_add_executor_job(_read_all)
        for sample, data in zip(samples, embedded, strict=True):
            if data is not None:
                sample["photo_data"] = data
        return payload

    async def async_import_batch(
        self, payload: dict[str, Any], *, overwrite: bool = False
    ) -> Batch:
        """Create a batch from an export payload (or a bare batch object).

        Weigh-ins, journal and embedded photos (``photo_data``) are restored;
        foreign ``photo_url`` values are dropped. An existing id gets a fresh
        one unless ``overwrite``. Raises ``ValueError`` on an invalid payload.
        """
        raw = payload.get("batch") if isinstance(payload.get("batch"), dict) else payload
        if not isinstance(raw, dict) or not str(raw.get("name") or "").strip():
            raise ValueError("batch payload needs a name")
        samples_raw = raw.get("samples") or []
        events_raw = raw.get("events") or []
        if not isinstance(samples_raw, list) or not isinstance(events_raw, list):
            raise ValueError("'samples' and 'events' must be lists")
        try:
            samples = [WeightSample.from_dict({**s, "photo_url": None}) for s in samples_raw]
            events = [BatchEvent.from_dict(e) for e in events_raw]
            status = BatchStatus(str(raw.get("status") or "active"))
        except (TypeError, ValueError, AttributeError) as err:
            raise ValueError(f"invalid batch payload: {err}") from err
        requested = slugify(str(raw.get("id") or "")) or None
        if requested and requested in self.batches and overwrite:
            await self.async_delete_batch(requested)
        batch_id = (
            requested
            if requested and requested not in self.batches
            else self._new_batch_id(str(raw["name"]))
        )
        batch = Batch(
            id=batch_id,
            name=str(raw["name"]).strip(),
            product=_opt_text(raw.get("product")),
            program_id=_opt_text(raw.get("program_id")),
            reference_weight=_opt_number(raw.get("reference_weight")),
            target_loss_pct=_opt_number(raw.get("target_loss_pct")),
            created_at=_opt_number(raw.get("created_at")) or dt_util.utcnow().timestamp(),
            status=status,
        )
        for sample, source in zip(samples, samples_raw, strict=True):
            photo = source.get("photo_data") if isinstance(source, dict) else None
            url = await self._save_photo(batch_id, sample.timestamp, photo) if photo else None
            batch.add_sample(dataclasses.replace(sample, photo_url=url))
        for event in events:
            batch.add_event(event)
        self.batches[batch_id] = batch
        if self.store.reference_batch_id is None and status is BatchStatus.ACTIVE:
            self.store.set_reference_batch(batch_id)
        self._last_weight = None
        self._persist_batches()
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

    async def async_record_manual_weight(self, weight: float) -> None:
        """Hand-entered weight from the *Manual weight* number entity.

        With a reference batch this is simply a new weigh-in on that batch.
        Without one, the value is remembered as the chamber weight so the
        weight-loss sensor and ``weight_loss`` program phases work with no scale.
        """
        ref_id = self.store.reference_batch_id
        if ref_id and ref_id in self.batches:
            await self.async_record_weight(ref_id, weight)
            return
        self.store.set_manual_weight(weight, dt_util.utcnow().timestamp())
        self.store.async_save()
        self._last_weight = None
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
        was_active = batch.status is BatchStatus.ACTIVE
        now = dt_util.utcnow().timestamp()
        batch.set_status(status, now)
        self._persist_batches()
        if was_active and status is not BatchStatus.ACTIVE:
            self._complete_linked_program(batch, now)
        await self.async_refresh()

    async def async_set_batch_status(self, batch_id: str, status: BatchStatus) -> None:
        """Set a batch's lifecycle status (also lets the panel re-activate one)."""
        await self._async_set_batch_status(batch_id, status)

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

    # -- Photos ------------------------------------------------------------

    def photo_path(self, batch_id: str, filename: str) -> str:
        """Filesystem path of a stored weigh-in photo (private, outside www/)."""
        return self.hass.config.path(*PHOTO_STORAGE_DIR, self.entry.entry_id, batch_id, filename)

    def _photo_url(self, batch_id: str, filename: str) -> str:
        return f"{PHOTO_URL_BASE}/{self.entry.entry_id}/{batch_id}/{filename}"

    async def _save_photo(self, batch_id: str, ts: float, photo: str) -> str | None:
        """Store a weigh-in photo privately and return its authenticated URL."""
        filename = f"{int(ts)}.jpg"
        path = self.photo_path(batch_id, filename)

        def _write() -> str | None:
            data = _photo_bytes(photo)
            if data is None:
                return None
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(data)
            return self._photo_url(batch_id, filename)

        return await self.hass.async_add_executor_job(_write)

    async def _delete_photo(self, batch_id: str, url: str | None) -> None:
        if not url or not url.startswith(f"{PHOTO_URL_BASE}/{self.entry.entry_id}/{batch_id}/"):
            return
        filename = url.rsplit("/", 1)[-1]
        if not _SAFE_NAME.fullmatch(filename):
            return
        path = self.photo_path(batch_id, filename)

        def _remove() -> None:
            with contextlib.suppress(FileNotFoundError):
                os.remove(path)

        await self.hass.async_add_executor_job(_remove)

    async def async_delete_weigh_in(self, batch_id: str, timestamp: float) -> None:
        """Remove one weigh-in (and its photo) from a batch."""
        batch = self.batches.get(batch_id)
        if batch is None:
            raise ValueError(f"Unknown batch '{batch_id}'")
        sample = next((s for s in batch.samples if abs(s.timestamp - timestamp) < 1e-3), None)
        if sample is None:
            raise ValueError("Unknown weigh-in")
        batch.samples.remove(sample)
        await self._delete_photo(batch_id, sample.photo_url)
        self._last_weight = None
        self._persist_batches()
        await self.async_refresh()

    # -- Batch summaries (sensor attributes, websocket API, card, panel) ----

    def _batch_summary(
        self, batch: Batch, now: float, *, with_samples: bool = False
    ) -> dict[str, Any]:
        """Serialisable summary of one batch.

        Light by default (no weigh-in history) so it can sit in a sensor
        attribute; ``with_samples`` adds the full history for the panel/card.
        """
        latest = batch.latest_sample
        summary: dict[str, Any] = {
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
            "eta_model": batch_engine.eta_model(batch),
            "weigh_in_due": self._weigh_in_due(batch, now),
            "created_at": batch.created_at,
            "completed_at": batch.completed_at,
            "sample_count": len(batch.samples),
            "event_count": len(batch.events),
            "last_weigh_in": latest.timestamp if latest else None,
            "last_event": (
                {
                    "timestamp": batch.events[-1].timestamp,
                    "kind": batch.events[-1].kind,
                    "note": batch.events[-1].note,
                }
                if batch.events
                else None
            ),
            "last_photo_url": next(
                (s.photo_url for s in reversed(batch.samples) if s.photo_url), None
            ),
        }
        if with_samples:
            summary["samples"] = [s.to_dict() for s in batch.samples]
            summary["events"] = [e.to_dict() for e in batch.events]
        return summary

    def _batch_summaries(
        self, now: float, *, include_archived: bool = False, with_samples: bool = False
    ) -> list[dict[str, Any]]:
        return [
            self._batch_summary(batch, now, with_samples=with_samples)
            for batch in self.batches.values()
            if include_archived or batch.status is not BatchStatus.ARCHIVED
        ]

    def batch_summaries(
        self, *, include_archived: bool = False, with_samples: bool = False
    ) -> list[dict[str, Any]]:
        """Public batch listing for the websocket API."""
        now = dt_util.utcnow().timestamp()
        return self._batch_summaries(
            now, include_archived=include_archived, with_samples=with_samples
        )

    def batch_summary(self, batch_id: str) -> dict[str, Any]:
        """Full summary (with weigh-ins) of one batch; raises on unknown id."""
        batch = self.batches.get(batch_id)
        if batch is None:
            raise ValueError(f"Unknown batch '{batch_id}'")
        return self._batch_summary(batch, dt_util.utcnow().timestamp(), with_samples=True)

    @property
    def has_scale(self) -> bool:
        return bool(conf.get(self.entry, conf.CONF_WEIGHT_SENSOR))

    @property
    def has_core_probe(self) -> bool:
        return bool(conf.get(self.entry, conf.CONF_PRODUCT_TEMP_SENSOR))

    def chamber_state(self) -> dict[str, Any]:
        """Live chamber snapshot for the panel (websocket ``state``/``subscribe``)."""
        data = self.data or {}
        registry = er.async_get(self.hass)
        prefix = self.entry.entry_id

        def entity_id(domain: str, key: str) -> str | None:
            return registry.async_get_entity_id(domain, DOMAIN, f"{prefix}_{key}")

        inputs = data.get("inputs")
        actuator_states = getattr(inputs, "actuator_states", None) or {}
        program = self.program.program
        state = self.program.state
        return {
            "entry_id": prefix,
            "name": self.chamber_name,
            "kind": self.chamber_kind,
            "updated_at": dt_util.utcnow().timestamp(),
            "temp": data.get("temp"),
            "humidity": data.get("humidity"),
            "dew_point": data.get("dew_point"),
            "absolute_humidity": data.get("absolute_humidity"),
            "core_temp": data.get("core_temp"),
            "core_delta": data.get("core_delta"),
            "has_core_probe": self.has_core_probe,
            "has_scale": self.has_scale,
            "target_temp": data.get("target_temp"),
            "target_humidity": data.get("target_humidity"),
            "temp_divergence": data.get("temp_divergence"),
            "humidity_divergence": data.get("humidity_divergence"),
            "summary": data.get("summary"),
            "decisions": data.get("decisions") or [],
            "actuators": {a.value: state_ for a, state_ in actuator_states.items()},
            "active_alerts": data.get("active_alerts") or [],
            "alert_details": data.get("alert_details") or {},
            "regulation_enabled": self._regulation_enabled,
            "maintenance": self._maintenance,
            "program": {
                "status": self.program.status.value,
                "program_id": state.program_id,
                "program_name": program.name if program else None,
                "phase_index": state.phase_index,
                "phase_name": data.get("phase_name"),
                "phase_remaining": data.get("phase_remaining"),
                "phase_target_temp": data.get("phase_target_temp"),
                "phase_target_humidity": data.get("phase_target_humidity"),
                "ramp_remaining": data.get("ramp_remaining"),
                "next_reminder": data.get("next_reminder"),
                "reminders": [r.to_dict() for r in program.reminders] if program else [],
                "started_at": state.started_at,
                "phase_started_at": state.phase_started_at,
                "phases": [p.to_dict() for p in program.phases] if program else [],
            },
            "weight": data.get("weight"),
            "weight_source": data.get("weight_source"),
            "reference_weight": data.get("reference_weight"),
            "weight_loss_pct": data.get("weight_loss_pct"),
            "drying_rate": data.get("drying_rate"),
            "counters": data.get("counters") or {},
            "reference_batch_id": data.get("reference_batch_id"),
            "active_batch_count": data.get("active_batch_count", 0),
            "batches": data.get("batches") or [],
            "entities": {
                "regulation_switch": entity_id("switch", "switch_regulation"),
                "maintenance_switch": entity_id("switch", "switch_maintenance"),
                "climate": entity_id("climate", "climate"),
                "humidifier": entity_id("humidifier", "humidifier"),
                "program_select": entity_id("select", "select_program"),
                "manual_weight": entity_id("number", "number_manual_weight"),
            },
        }

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
        _, weight_source = self._weight_with_source()
        now = dt_util.utcnow().timestamp()
        batches = self._batch_summaries(now)
        ref_id = self.store.reference_batch_id
        ref_batch = self.batches.get(ref_id) if ref_id else None
        ref_summary = self._batch_summary(ref_batch, now) if ref_batch else None
        active_batches = sum(1 for b in batches if b["status"] == BatchStatus.ACTIVE.value)
        dew_point = abs_humidity = None
        if inputs.temp is not None and inputs.humidity is not None:
            dew_point = derived.dew_point(inputs.temp, inputs.humidity)
            abs_humidity = derived.absolute_humidity(inputs.temp, inputs.humidity)
        return {
            "entry_id": self.entry.entry_id,
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
            "core_temp": inputs.product_temp,
            "core_delta": derived.core_delta(inputs.product_temp, inputs.temp),
            "temp_divergence": temp_div,
            "humidity_divergence": hum_div,
            "weight": inputs.weight,
            "weight_source": weight_source,
            "reference_weight": self.program.state.reference_weight,
            "weight_loss_pct": weight_loss,
            "drying_rate": inputs.drying_rate,
            "batches": batches,
            "reference_batch_id": ref_id,
            "active_batch_count": active_batches,
            "weigh_in_due": [b["id"] for b in batches if b.get("weigh_in_due")],
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
            "phase_target_temp": self.program.active_targets()[0],
            "phase_target_humidity": self.program.active_targets()[1],
            "ramp_remaining": self.program.ramp_remaining(now),
            "next_reminder": self._next_reminder(now),
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
