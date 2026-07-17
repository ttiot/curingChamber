# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Product batches.** Track one or more products curing in a chamber, each with
  its reference weight, target weight loss and a **weigh-in history**. Weigh-ins
  can be recorded by hand (**no scale required**) with an optional note and photo.
- **Predictive ETA.** A pure `batch` engine derives each batch's current weight
  loss, a least-squares drying rate and a projected completion date.
- **Reference batch.** The designated reference batch's latest weigh-in drives
  the running program's weight-loss phase end, falling back to the chamber scale
  so existing setups are unaffected. Batches reaching their target auto-complete
  and emit a `batch_completed` event.
- **Services:** `create_batch`, `record_weight`, `set_reference_batch`,
  `complete_batch`, `archive_batch`, `delete_batch`. Weigh-in photos are stored
  under `<config>/www` and served at `/local/curing_chamber/…`.
- **Sensors:** active batches (with a per-batch `batches` attribute), reference
  batch weight loss, and reference batch estimated end.
- **Custom Lovelace card** (`curing-chamber-card`, auto-registered): drying
  curve, loss gauge, ETA and an inline weigh-in + photo form.

### Fixed
- **Card auto-load reliability ("Configuration error").** Declare `frontend` as
  an after-dependency so the module-URL registry exists when the card is
  registered, cache-bust the card's module URL by its file mtime so browsers and
  the frontend service worker pick up updates instead of a stale copy, and log a
  visible warning (with the manual-resource fallback) when auto-load fails
  instead of swallowing it silently. The card's *unknown entity* note now spells
  out the expected `sensor.<chamber>_active_batches` name. Added a troubleshooting
  section (EN/FR) for the "Configuration error" symptom.

## [0.1.0] - 2026-07-14

### Added
- Initial release of the **Curing Chamber** integration.
- Pure regulation engine: hysteresis all-or-nothing control, compressor
  protection (min ON/OFF, startup lockout), mutual exclusions, humidity
  anti-oscillation, temperature-priority T°/HR coupling, absolute safety limits,
  frozen/unavailable-sensor safe state, quality alerts (case hardening,
  condensation, high-temp-during-drying) and degraded-mode manual-action
  recommendations with anti-spam reminders and auto-resolution.
- Pure program engine: multi-phase state machine (start/pause/resume/stop/next),
  end conditions on duration / weight loss / manual, serialisable state for
  resume-after-restart, six built-in presets and dependency-free JSON validation.
- Home Assistant layer: config flow (with food-safety disclaimer) and full
  options flow, coordinator with source tracking, unit conversion, noise/stale
  filtering and manual-override detection, native `climate`, `humidifier`,
  `sensor`, `binary_sensor`, `switch`, `select`, `button` and `number` entities,
  ten services, bus events, notifications (persistent + `notify.*`), diagnostics
  and storage-backed persistence.
- FR/EN translations, HACS metadata, and CI (ruff, mypy, pytest+coverage,
  hassfest, HACS validation) on Python 3.13.

[Unreleased]: https://github.com/ttiot/curingChamber/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ttiot/curingChamber/releases/tag/v0.1.0
