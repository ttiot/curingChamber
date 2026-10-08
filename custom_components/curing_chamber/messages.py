"""Translated runtime notification texts (FR/EN) for alerts and program events.

Home Assistant's translation files cover the config flow and entity names, but
free-form notification bodies with live values are built here so both languages
carry the current value and target (§5/§8).
"""

from __future__ import annotations

from .regulation.types import Alert, AlertLevel

DEFAULT_LANG = "en"

_TITLE = {
    "en": "Curing Chamber",
    "fr": "Séchoir à charcuterie",
}

_RESOLVED_PREFIX = {
    "en": "Back to normal — ",
    "fr": "Retour à la normale — ",
}

# One template per alert key, per language. ``{value}`` / ``{target}`` /
# ``{rate}`` are filled from the alert params where present.
_ALERTS: dict[str, dict[str, str]] = {
    "sensor_fault_temp": {
        "en": "Temperature sensor unavailable or frozen — all actuators stopped for safety.",
        "fr": "Sonde de température indisponible ou figée — tous les actionneurs coupés par sécurité.",
    },
    "sensor_fault_humidity": {
        "en": "Humidity sensor unavailable or frozen — all actuators stopped for safety.",
        "fr": "Sonde d'hygrométrie indisponible ou figée — tous les actionneurs coupés par sécurité.",
    },
    "sensor_divergence_temp": {
        "en": "Temperature probes diverge by {value}°C — check for a failing probe or poor air mixing.",
        "fr": "Écart de {value}°C entre les sondes de température — sonde défaillante ou brassage insuffisant.",
    },
    "sensor_divergence_humidity": {
        "en": "Humidity probes diverge by {value}%RH — check for a failing probe or stratification.",
        "fr": "Écart de {value}%HR entre les sondes d'hygrométrie — sonde défaillante ou stratification.",
    },
    "abs_limit_temp_high": {
        "en": "Critical: temperature {value}°C above the safe maximum. Aggravating actuators cut.",
        "fr": "Critique : température {value}°C au-dessus du maximum de sécurité. Actionneurs aggravants coupés.",
    },
    "abs_limit_temp_low": {
        "en": "Critical: temperature {value}°C below the safe minimum. Aggravating actuators cut.",
        "fr": "Critique : température {value}°C sous le minimum de sécurité. Actionneurs aggravants coupés.",
    },
    "abs_limit_humidity_high": {
        "en": "Critical: humidity {value}%RH above the safe maximum. Aggravating actuators cut.",
        "fr": "Critique : hygrométrie {value}%HR au-dessus du maximum de sécurité. Actionneurs aggravants coupés.",
    },
    "abs_limit_humidity_low": {
        "en": "Critical: humidity {value}%RH below the safe minimum. Aggravating actuators cut.",
        "fr": "Critique : hygrométrie {value}%HR sous le minimum de sécurité. Actionneurs aggravants coupés.",
    },
    "high_temp_drying": {
        "en": "Health risk: temperature {value}°C above {target}°C for over 2 h during drying.",
        "fr": "Risque sanitaire : température {value}°C au-dessus de {target}°C depuis plus de 2 h en séchage.",
    },
    "core_temp_high": {
        "en": "Health risk: product core {value}°C above {target}°C for over 2 h.",
        "fr": "Risque sanitaire : cœur du produit à {value}°C au-dessus de {target}°C depuis plus "
        "de 2 h.",
    },
    "case_hardening": {
        "en": "Case hardening risk: drying too fast or humidity too low. Slow the drying down.",
        "fr": "Risque de croûtage : séchage trop rapide ou hygrométrie trop basse. Ralentissez le séchage.",
    },
    "condensation_risk": {
        "en": "Condensation risk: chamber temperature is close to the dew point.",
        "fr": "Risque de condensation : la température de la chambre est proche du point de rosée.",
    },
    "door_open_too_long": {
        "en": "The door has been open too long — regulation is paused.",
        "fr": "La porte est ouverte depuis trop longtemps — la régulation est en pause.",
    },
    "air_quality": {
        "en": "Air quality: CO₂ {value} ppm. Ventilate the chamber.",
        "fr": "Qualité d'air : CO₂ {value} ppm. Aérez la chambre.",
    },
    "actuator_ineffective_cool": {
        "en": "Cooling has run for {minutes} min without lowering the temperature "
        "({start}°C → {value}°C): check the compressor, an iced evaporator or the door seal.",
        "fr": "Le froid tourne depuis {minutes} min sans faire baisser la température "
        "({start}°C → {value}°C) : vérifiez le compresseur, un évaporateur givré ou le joint "
        "de porte.",
    },
    "actuator_ineffective_heat": {
        "en": "Heating has run for {minutes} min without raising the temperature "
        "({start}°C → {value}°C): check the heater.",
        "fr": "Le chauffage tourne depuis {minutes} min sans faire monter la température "
        "({start}°C → {value}°C) : vérifiez le chauffage.",
    },
    "actuator_ineffective_humidify": {
        "en": "The humidifier has run for {minutes} min without raising the humidity "
        "({start}%RH → {value}%RH): check its water tank.",
        "fr": "L'humidificateur tourne depuis {minutes} min sans faire monter l'hygrométrie "
        "({start}%HR → {value}%HR) : vérifiez son réservoir d'eau.",
    },
    "actuator_ineffective_dehumidify": {
        "en": "The dehumidifier has run for {minutes} min without lowering the humidity "
        "({start}%RH → {value}%RH): check it (full tank, blocked drain).",
        "fr": "Le déshumidificateur tourne depuis {minutes} min sans faire baisser l'hygrométrie "
        "({start}%HR → {value}%HR) : vérifiez-le (bac plein, évacuation bouchée).",
    },
    "manual_temp_high": {
        "en": "Temperature {value}°C (target {target}°C): lower the fridge thermostat or move the "
        "chamber somewhere cooler.",
        "fr": "Température {value}°C (cible {target}°C) : baissez le thermostat du frigo ou déplacez "
        "la chambre dans un lieu plus frais.",
    },
    "manual_temp_low": {
        "en": "Temperature {value}°C (target {target}°C): add a heater or insulate the chamber.",
        "fr": "Température {value}°C (cible {target}°C) : ajoutez un chauffage ou isolez la chambre.",
    },
    "manual_humidity_high": {
        "en": "Humidity {value}%RH (target {target}%RH): ventilate or add a dehumidifier / "
        "moisture absorber.",
        "fr": "Hygrométrie {value}%HR (cible {target}%HR) : aérez ou ajoutez un déshumidificateur / "
        "absorbeur d'humidité.",
    },
    "manual_humidity_low": {
        "en": "Humidity {value}%RH (target {target}%RH): place a tray of salted water in the chamber "
        "or plug in a humidifier.",
        "fr": "Hygrométrie {value}%HR (cible {target}%HR) : placez un bac d'eau salée dans la chambre "
        "ou branchez un humidificateur.",
    },
}

_PROGRAM: dict[str, dict[str, str]] = {
    "phase_started": {
        "en": "Phase started: {phase}.",
        "fr": "Phase démarrée : {phase}.",
    },
    "phase_ended": {
        "en": "Phase finished: {phase}.",
        "fr": "Phase terminée : {phase}.",
    },
    "program_completed": {
        "en": "Program complete: {program}.",
        "fr": "Programme terminé : {program}.",
    },
}


def _lang(language: str | None) -> str:
    if language and language.lower().startswith("fr"):
        return "fr"
    return "en"


def title(language: str | None) -> str:
    """Return the localized notification title."""
    return _TITLE[_lang(language)]


def alert_message(alert: Alert, language: str | None) -> str:
    """Return the localized message body for an alert."""
    lang = _lang(language)
    template = _ALERTS.get(alert.key.value, {}).get(lang, alert.key.value)
    try:
        body = template.format(**alert.params)
    except (KeyError, IndexError):
        body = template
    if alert.resolved:
        return _RESOLVED_PREFIX[lang] + body
    return body


def program_message(event_type: str, language: str | None, **params: str) -> str:
    """Return the localized message body for a program event."""
    lang = _lang(language)
    template = _PROGRAM.get(event_type, {}).get(lang, event_type)
    try:
        return template.format(**params)
    except (KeyError, IndexError):
        return template


def level_of(alert: Alert) -> str:
    """Map an alert level to a persistent-notification friendly string."""
    return alert.level.value if isinstance(alert.level, AlertLevel) else str(alert.level)
