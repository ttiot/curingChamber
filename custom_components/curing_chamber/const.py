"""Constants for the Curing Chamber integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "curing_chamber"

# --- Config entry / data keys ------------------------------------------------
CONF_NAME: Final = "name"
CONF_CHAMBER_KIND: Final = "chamber_kind"
CHAMBER_KIND_CHARCUTERIE: Final = "charcuterie"
CHAMBER_KIND_CHEESE: Final = "cheese"
CHAMBER_KINDS: Final = (CHAMBER_KIND_CHARCUTERIE, CHAMBER_KIND_CHEESE)
DEFAULT_CHAMBER_KIND: Final = CHAMBER_KIND_CHARCUTERIE

# Sensors (sources) -----------------------------------------------------------
CONF_TEMP_SENSOR: Final = "temp_sensor"
CONF_HUMIDITY_SENSOR: Final = "humidity_sensor"
CONF_TEMP_SENSOR_2: Final = "temp_sensor_2"
CONF_HUMIDITY_SENSOR_2: Final = "humidity_sensor_2"
CONF_PRODUCT_TEMP_SENSOR: Final = "product_temp_sensor"
CONF_DOOR_SENSOR: Final = "door_sensor"
CONF_WEIGHT_SENSOR: Final = "weight_sensor"
CONF_CO2_SENSOR: Final = "co2_sensor"

# Actuators (all optional) ----------------------------------------------------
CONF_COOL_SWITCH: Final = "cool_switch"
CONF_HEAT_SWITCH: Final = "heat_switch"
CONF_HUMIDIFY_SWITCH: Final = "humidify_switch"
CONF_DEHUMIDIFY_SWITCH: Final = "dehumidify_switch"
CONF_FAN_SWITCH: Final = "fan_switch"
CONF_VENT_SWITCH: Final = "vent_switch"

# Notifications ---------------------------------------------------------------
CONF_NOTIFY_SERVICES: Final = "notify_services"
CONF_WEIGH_IN_REMINDER_DAYS: Final = "weigh_in_reminder_days"
DEFAULT_WEIGH_IN_REMINDER_DAYS: Final = 7  # days, 0 = off

# Regulation tuning -----------------------------------------------------------
CONF_TEMP_DEADBAND: Final = "temp_deadband"
CONF_HUMIDITY_DEADBAND: Final = "humidity_deadband"
CONF_COOL_MIN_OFF: Final = "cool_min_off"
CONF_COOL_MIN_ON: Final = "cool_min_on"
CONF_ACTUATOR_MIN_OFF: Final = "actuator_min_off"
CONF_ACTUATOR_MIN_ON: Final = "actuator_min_on"
CONF_STARTUP_DELAY: Final = "startup_delay"
CONF_HUMIDITY_ANTI_OSC: Final = "humidity_anti_oscillation"
CONF_TEMP_ABS_MIN: Final = "temp_abs_min"
CONF_TEMP_ABS_MAX: Final = "temp_abs_max"
CONF_HUMIDITY_ABS_MIN: Final = "humidity_abs_min"
CONF_HUMIDITY_ABS_MAX: Final = "humidity_abs_max"
CONF_SENSOR_DIVERGENCE_TEMP: Final = "sensor_divergence_temp"
CONF_SENSOR_DIVERGENCE_HUMIDITY: Final = "sensor_divergence_humidity"
CONF_SENSOR_STALE_MINUTES: Final = "sensor_stale_minutes"
CONF_FILTER_SAMPLES: Final = "filter_samples"
CONF_DEGRADED_BAND_FACTOR: Final = "degraded_band_factor"
CONF_DEGRADED_DELAY: Final = "degraded_delay"
CONF_DEGRADED_REMINDER: Final = "degraded_reminder"
CONF_DOOR_OPEN_ALERT_MINUTES: Final = "door_open_alert_minutes"
CONF_CASE_HARDENING_RATE: Final = "case_hardening_rate"
CONF_HIGH_TEMP_DRYING_LIMIT: Final = "high_temp_drying_limit"
CONF_HIGH_TEMP_DRYING_DURATION: Final = "high_temp_drying_duration"
CONF_FAN_PERIOD: Final = "fan_period"
CONF_FAN_RUN: Final = "fan_run"
CONF_VENT_PERIOD: Final = "vent_period"
CONF_VENT_RUN: Final = "vent_run"
CONF_CO2_THRESHOLD: Final = "co2_threshold"
CONF_CONDENSATION_MARGIN: Final = "condensation_margin"
CONF_CORE_TEMP_MAX: Final = "core_temp_max"
CONF_ACTUATOR_INEFFECTIVE_MINUTES: Final = "actuator_ineffective_minutes"
CONF_MANUAL_OVERRIDE_RESPECT: Final = "manual_override_respect_minutes"
CONF_TICK_INTERVAL: Final = "tick_interval"

# --- Defaults (§5) -----------------------------------------------------------
DEFAULT_TEMP_DEADBAND: Final = 0.5  # +/- degC
DEFAULT_HUMIDITY_DEADBAND: Final = 3.0  # +/- %RH
DEFAULT_COOL_MIN_OFF: Final = 420  # seconds (7 min)
DEFAULT_COOL_MIN_ON: Final = 180  # seconds (3 min)
DEFAULT_ACTUATOR_MIN_OFF: Final = 60  # seconds
DEFAULT_ACTUATOR_MIN_ON: Final = 60  # seconds
DEFAULT_STARTUP_DELAY: Final = 120  # seconds (2 min)
DEFAULT_HUMIDITY_ANTI_OSC: Final = 600  # seconds (10 min)
DEFAULT_TEMP_ABS_MIN: Final = 0.0  # degC
DEFAULT_TEMP_ABS_MAX: Final = 30.0  # degC
DEFAULT_HUMIDITY_ABS_MIN: Final = 40.0  # %RH
DEFAULT_HUMIDITY_ABS_MAX: Final = 99.0  # %RH
DEFAULT_SENSOR_DIVERGENCE_TEMP: Final = 2.0  # degC
DEFAULT_SENSOR_DIVERGENCE_HUMIDITY: Final = 8.0  # %RH
DEFAULT_SENSOR_STALE_MINUTES: Final = 30  # minutes
DEFAULT_FILTER_SAMPLES: Final = 3
DEFAULT_DEGRADED_BAND_FACTOR: Final = 2.0
DEFAULT_DEGRADED_DELAY: Final = 900  # seconds (15 min)
DEFAULT_DEGRADED_REMINDER: Final = 7200  # seconds (2 h)
DEFAULT_DOOR_OPEN_ALERT_MINUTES: Final = 5
DEFAULT_CASE_HARDENING_RATE: Final = 1.5  # %/day
DEFAULT_HIGH_TEMP_DRYING_LIMIT: Final = 16.0  # degC
DEFAULT_HIGH_TEMP_DRYING_DURATION: Final = 7200  # seconds (2 h)
DEFAULT_FAN_PERIOD: Final = 1800  # seconds (30 min)
DEFAULT_FAN_RUN: Final = 300  # seconds (5 min)
DEFAULT_VENT_PERIOD: Final = 21600  # seconds (6 h)
DEFAULT_VENT_RUN: Final = 300  # seconds (5 min)
DEFAULT_CO2_THRESHOLD: Final = 1500  # ppm
DEFAULT_MANUAL_OVERRIDE_RESPECT: Final = 0  # minutes (0 = reprendre le contrôle)
DEFAULT_TICK_INTERVAL: Final = 30  # seconds
DEFAULT_CONDENSATION_MARGIN: Final = 1.0  # degC
DEFAULT_CORE_TEMP_MAX: Final = 24.0  # degC, product core
DEFAULT_ACTUATOR_INEFFECTIVE_MINUTES: Final = 60  # minutes, 0 = disabled
# A cheese cave runs at 85-95 %RH, where the dew point sits well under 1 degC
# below the air temperature: a tighter margin keeps the alert meaningful.
DEFAULT_CONDENSATION_MARGIN_CHEESE: Final = 0.5  # degC

# --- Counters (hours, persisted in the store next to the actuator run times) --
COUNTER_DEGRADED: Final = "degraded"

# --- Runtime data / hass.data keys ------------------------------------------
DATA_COORDINATOR: Final = "coordinator"

# --- Events ------------------------------------------------------------------
EVENT_CURING_CHAMBER: Final = f"{DOMAIN}_event"
EVENT_TYPE_PHASE_CHANGED: Final = "phase_changed"
EVENT_TYPE_PROGRAM_COMPLETED: Final = "program_completed"
EVENT_TYPE_ALERT_RAISED: Final = "alert_raised"
EVENT_TYPE_ALERT_CLEARED: Final = "alert_cleared"
EVENT_TYPE_MANUAL_ACTION: Final = "manual_action_required"
EVENT_TYPE_BATCH_COMPLETED: Final = "batch_completed"
EVENT_TYPE_BATCH_EVENT: Final = "batch_event"
EVENT_TYPE_WEIGH_IN_DUE: Final = "weigh_in_due"
EVENT_TYPE_REMINDER: Final = "reminder"

# --- Storage -----------------------------------------------------------------
STORAGE_VERSION: Final = 1
STORAGE_KEY_TEMPLATE: Final = f"{DOMAIN}.{{entry_id}}"

# --- Services ----------------------------------------------------------------
SERVICE_START_PROGRAM: Final = "start_program"
SERVICE_STOP_PROGRAM: Final = "stop_program"
SERVICE_PAUSE_PROGRAM: Final = "pause_program"
SERVICE_RESUME_PROGRAM: Final = "resume_program"
SERVICE_NEXT_PHASE: Final = "next_phase"
SERVICE_SET_TARGETS: Final = "set_targets"
SERVICE_SET_REFERENCE_WEIGHT: Final = "set_reference_weight"
SERVICE_ACKNOWLEDGE_ALERT: Final = "acknowledge_alert"
SERVICE_CREATE_PROGRAM: Final = "create_program"
SERVICE_DELETE_PROGRAM: Final = "delete_program"
SERVICE_EXPORT_PROGRAMS: Final = "export_programs"
SERVICE_IMPORT_PROGRAMS: Final = "import_programs"
SERVICE_CREATE_BATCH: Final = "create_batch"
SERVICE_RECORD_WEIGHT: Final = "record_weight"
SERVICE_SET_REFERENCE_BATCH: Final = "set_reference_batch"
SERVICE_COMPLETE_BATCH: Final = "complete_batch"
SERVICE_ARCHIVE_BATCH: Final = "archive_batch"
SERVICE_DELETE_BATCH: Final = "delete_batch"
SERVICE_ADD_BATCH_EVENT: Final = "add_batch_event"
SERVICE_DELETE_BATCH_EVENT: Final = "delete_batch_event"
SERVICE_EXPORT_BATCH: Final = "export_batch"

# --- Batch photos ------------------------------------------------------------
# Legacy (pre-panel) location: <config>/www/<PHOTO_WWW_SUBDIR>/<batch_id>/ served
# unauthenticated at /local/... — migrated on load to the private location below.
PHOTO_WWW_SUBDIR: Final = "curing_chamber"
# Current location: <config>/.storage/curing_chamber/photos/<entry_id>/<batch_id>/<file>,
# served only to authenticated users by the integration's own HTTP view at
# PHOTO_URL_BASE/<entry_id>/<batch_id>/<file> (sign the URL for <img> tags).
PHOTO_STORAGE_DIR: Final = (".storage", DOMAIN, "photos")
PHOTO_URL_BASE: Final = f"/api/{DOMAIN}/photo"

# --- Frontend (bundled card + sidebar panel) --------------------------------
FRONTEND_URL_BASE: Final = f"/{DOMAIN}"
CARD_FILENAME: Final = "curing-chamber-card.js"
PANEL_FILENAME: Final = "curing-chamber-panel.js"
PANEL_URL_PATH: Final = "curing-chamber"
PANEL_WEBCOMPONENT: Final = "curing-chamber-panel"
PANEL_TITLE: Final = "Curing Chamber"
PANEL_ICON: Final = "mdi:sausage"

# Dispatcher signal fired when a chamber is loaded or unloaded (panel chamber list).
SIGNAL_CHAMBERS_CHANGED: Final = f"{DOMAIN}_chambers_changed"

# Platforms managed by this integration.
PLATFORMS: Final = [
    "binary_sensor",
    "button",
    "climate",
    "humidifier",
    "number",
    "select",
    "sensor",
    "switch",
]
