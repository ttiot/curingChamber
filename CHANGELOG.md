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
  `complete_batch`, `archive_batch`, `delete_batch`.
- **Sidebar panel** (`curing-chamber-panel`, registered by the integration —
  works on every install type, including HA Container): Chamber view (gauges,
  actuators, program timeline and controls, alerts, regulation decisions),
  Batches view (drying curves, weigh-in history, photo gallery, weigh-in form
  with camera capture and in-browser downscaling), Programs view (visual
  multi-phase editor with live validation) and History view (overlaid curves of
  finished batches). Chamber selector for multi-chamber setups, FR/EN, themed
  through HA CSS variables, open to non-admin users.
- **Websocket API** (`curing_chamber/*`): chambers, live `state`/`subscribe`,
  batches (list/get/create/set_status/set_reference/delete), `weigh_in`
  (+ `weigh_in/delete`), programs (list/validate/save/delete). Services stay for
  automations.
- **Private photos.** Weigh-in photos now live under
  `<config>/.storage/curing_chamber/photos/` and are served only to logged-in
  users by an authenticated view (`/api/curing_chamber/photo/…`); the card and
  panel sign the URL. Photos previously written under the public `www/` folder
  are migrated automatically.
- **Sensors:** active batches (with a light per-batch `batches` attribute and
  the `entry_id`), reference batch weight loss, and reference batch estimated
  end. The weigh-in history, regulation decisions and alert details are kept
  out of the recorder database (`_unrecorded_attributes`) and archived batches
  are left out of the attribute, so the state stays well under the recorder's
  attribute size limit.
- **Custom Lovelace card** (`curing-chamber-card`, auto-registered): drying
  curve, loss gauge, ETA and an inline weigh-in + photo form. The card and the
  panel JS are served with the integration version in the URL so browsers pick
  up new versions after an update.
- **Manual weight `number` entity.** Type a weigh-in straight from the HA UI
  (device page, entities card, mobile app): it is recorded on the reference
  batch, or — with no batch — remembered as the chamber weight so *Set reference
  weight*, the *Weight loss* sensor and `weight_loss` phases work without a
  scale. Weight resolution order is now reference batch → scale → manual entry.

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
