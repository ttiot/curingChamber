# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-10-08

### Added
- **Setpoint ramps.** A phase may carry `start_temp` / `start_humidity` and
  `ramp_hours`: the active targets move linearly from the start values to the
  phase targets over the first `ramp_hours` hours (paused time excluded), then
  hold. The panel editor has a ramp line per phase, the program card shows the
  ramp in progress and the *Phase time remaining* sensor exposes the final
  phase targets and the ramp time left in its attributes.
- **Chamber kind** (`chamber_kind`: `charcuterie` or `cheese`) in the first
  config step and in the *Regulation & safety* options. A chamber lists the
  presets of its kind only (any preset can still be started by id); the
  condensation alert margin is now an option (`condensation_margin`) and
  defaults to 0.5 °C for a cheese cave (1 °C otherwise).
- **New presets.** Charcuterie: chorizo (ramped drying), lomo embuchado
  (ramped), viande des Grisons, jambon cru. Cheese cave: bloomy rind, washed
  rind, pressed (ramped), blue, lactic / goat, cheese cave hold. Programs carry
  a `category` (`charcuterie` by default, or `cheese`).
- **Program import / export.** Services `export_programs` (returns a portable
  `{"format": "curing_chamber/programs", "version": 1, "programs": [...]}`
  payload) and `import_programs` (payload, list or single program; `overwrite`
  flag; preset ids are never overwritten). Websocket `program/import`. The
  panel's Programs view gets **Export** / **Import** buttons working on `.json`
  files, and groups *My programs* and *Presets*.
- **Degraded mode hours** diagnostic sensor (`total_increasing`): cumulative
  hours during which a manual action was required, for long-term statistics.

### Changed
- `select.<chamber>_program` options now depend on the chamber kind.

## [0.4.0] - 2026-10-04

### Added
- Panel: **Add a chamber** button (header and empty state, admins only) that
  opens the integration's config flow directly.
- Websocket `curing_chamber/subscribe_chambers`: pushes the chamber list on
  subscribe and whenever a chamber is loaded, unloaded or renamed.

### Changed
- Panel: the chamber selector now follows that subscription, so chambers added,
  renamed or removed while the panel is open appear without a page reload. A
  chamber that disappears briefly (options reload) keeps its selection.

## [0.3.1] - 2026-10-04

### Added
- Brand icon (`custom_components/curing_chamber/brand/icon.png`, `icon@2x.png`)
  so the integration shows an icon in Home Assistant and HACS.

### Changed
- `hacs.json` declares the minimum Home Assistant version (**2024.7.0**, needed
  for `async_register_static_paths`) and renders the README in HACS.
- HACS validation now runs without any ignored check (brands, topics,
  description), as required for inclusion in the HACS default store.

## [0.3.0] - 2026-10-04

### Added
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
- **Manual weight `number` entity.** Type a weigh-in straight from the HA UI
  (device page, entities card, mobile app): it is recorded on the reference
  batch, or — with no batch — remembered as the chamber weight so *Set reference
  weight*, the *Weight loss* sensor and `weight_loss` phases work without a
  scale. Weight resolution order is now reference batch → scale → manual entry.

### Changed
- **Private photos.** Weigh-in photos now live under
  `<config>/.storage/curing_chamber/photos/` and are served only to logged-in
  users by an authenticated view (`/api/curing_chamber/photo/…`); the card and
  panel sign the URL. Photos previously written under the public `www/` folder
  are migrated automatically on startup.
- **Recorder footprint.** The active-batches sensor's `batches` attribute is now
  a light summary (no weigh-in history, no archived batches) and carries the
  `entry_id`; weigh-in history, regulation decisions and alert details are kept
  out of the recorder database (`_unrecorded_attributes`).
- **Card.** Loads the weigh-in history over websocket and downscales photos in
  the browser. Card and panel JS URLs carry the integration version so browsers
  pick up new files after an update.
- Release workflow runs once per published release (no more duplicated notes).

## [0.2.0] - 2026-07-15

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
- **Sensors:** active batches (with a per-batch `batches` attribute), reference
  batch weight loss, and reference batch estimated end.
- **Custom Lovelace card** (`curing-chamber-card`, auto-registered): drying
  curve, loss gauge, ETA and an inline weigh-in + photo form.

### Fixed
- HACS validation: LICENSE file, corrected `hacs.json`, store-only checks skipped.

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

[Unreleased]: https://github.com/ttiot/curingChamber/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/ttiot/curingChamber/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/ttiot/curingChamber/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/ttiot/curingChamber/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/ttiot/curingChamber/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ttiot/curingChamber/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ttiot/curingChamber/releases/tag/v0.1.0
