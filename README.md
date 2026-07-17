# Curing Chamber — Séchoir à charcuterie

Home Assistant custom integration that turns a repurposed fridge (or any
enclosure) into a controlled charcuterie curing chamber: it holds temperature
and humidity setpoints across multi-phase drying programs, and — crucially —
when a value drifts and **no actuator can correct it**, it tells you exactly
what to do by hand.

100% local, no cloud. Config-flow UI, native `climate` / `humidifier` entities,
multi-phase programs with presets, degraded-mode manual-action alerts,
diagnostics, and full FR/EN translations.

> 🇬🇧 English below · 🇫🇷 [Version française](#-séchoir-à-charcuterie--version-française)

> ⚠️ **Food-safety disclaimer.** This integration controls the *environment* of
> a curing chamber. It does **not** guarantee the safety of the product: it
> measures neither water activity (a\_w) nor pH. Hygiene, correct salting
> (including nitrite salt where appropriate) and recipes remain **your**
> responsibility. The health-related alerts cannot be globally disabled, only
> adjusted within reasonable bounds.

---

## Features

- **All actuators optional.** Cooling, heating, humidifier, dehumidifier,
  stirring fan and air-renewal are each optional; configure any subset,
  including none (monitoring-only).
- **Hysteresis all-or-nothing control** with compressor protection (min ON/OFF
  times, startup lockout), mutual exclusions (never cool+heat, never
  humidify+dehumidify) and a humidity anti-oscillation window.
- **Temperature-priority T°/HR coupling** (see the [decision table](#regulation-decision-table)).
- **Degraded mode:** when a quantity leaves the extended tolerance band and no
  configured actuator can bring it back, you get a contextual manual-action
  notification (e.g. *"Humidity 62 % (target 75 %): place a tray of salted water
  in the chamber"*), with anti-spam reminders and automatic resolution.
- **Safety first:** an unavailable or frozen sensor stops every actuator and
  raises a critical alert — the chamber never regulates blind. Absolute limits
  cut the aggravating actuator.
- **Multi-phase programs** with 6 built-in presets, phase end on duration,
  weight loss (with a scale) or manual.
- **Product batches** with **manual weigh-ins** (no scale required, optional
  note + photo), per-batch drying curve and a **predicted completion date (ETA)**;
  the reference batch drives the program's weight-loss phase.
- **Derived sensors:** dew point (Magnus), absolute humidity, weight loss %,
  drying rate %/day.
- **Native entities** (`climate`, `humidifier`, `sensor`, `binary_sensor`,
  `switch`, `select`, `button`, `number`), services, bus events and a bundled
  **custom Lovelace card**.

---

## Installation (HACS)

1. In HACS → *Integrations* → the three-dots menu → **Custom repositories**.
2. Add `https://github.com/ttiot/curingchamber` with category **Integration**.
3. Install **Curing Chamber**, then restart Home Assistant.
4. *Settings → Devices & Services → Add Integration → Curing Chamber*.

Manual install: copy `custom_components/curing_chamber/` into your HA
`config/custom_components/` folder and restart.

---

## Configuration (step by step)

The config flow has four screens:

1. **Sensors** — name the chamber and pick the temperature and humidity
   sensors. Optional: a second temperature/humidity probe (averaged, with a
   divergence alert), product core temperature, a weight sensor, a CO₂ sensor,
   and a door binary sensor.
   *The integration installs even with no sensors (monitoring only).*
2. **Actuators** — pick any of cooling / heating / humidifier / dehumidifier /
   stirring fan / air-renewal. Any `switch`, `input_boolean`, `fan` or `light`
   works. Configure none for pure monitoring.
3. **Notifications** — optionally choose one or more `notify.*` services (e.g.
   your phone). Persistent notifications are always created.
4. **Food-safety disclaimer** — read and submit to finish.

Everything is reconfigurable afterwards via *Configure* (options flow):
**Sensors**, **Actuators**, **Regulation & safety** (deadbands, compressor
timers, absolute limits, degraded-mode delays…) and **Notifications**.

---

## Entities

| Domain | Entity | Purpose |
|---|---|---|
| `climate` | Temperature | Setpoint + mode (off/cool/heat/heat_cool per actuators), action idle/cooling/heating |
| `humidifier` | Humidity | Setpoint + action humidifying/drying/idle |
| `select` | Program | Active preset/program (`none` stops it) |
| `sensor` | Current phase | Running phase name (+ program status, index) |
| `sensor` | Phase time remaining | Estimated hours left (duration phases) |
| `sensor` | Dew point | Magnus dew point (°C) |
| `sensor` | Absolute humidity | g/m³ |
| `sensor` | Weight loss | % vs reference weight |
| `sensor` | Drying rate | %/day |
| `sensor` | Regulation state | idle/cooling/…, with last decisions in attributes |
| `sensor` | *Actuator* run time | Cumulative run-hours per actuator (maintenance) |
| `binary_sensor` | Manual action required | ON with recommended action(s) in attributes |
| `binary_sensor` | Out-of-range alarm | Absolute limit / high-temp breach |
| `binary_sensor` | Sensor fault | Sensor unavailable or frozen |
| `binary_sensor` | Probe divergence | Two probes disagree |
| `binary_sensor` | Door open too long | Door left open past the delay |
| `switch` | Regulation | Master enable/disable |
| `switch` | Maintenance mode | Everything off, no alerts |
| `button` | Next phase / Set reference weight / Acknowledge alerts | — |
| `number` | Manual temperature / humidity target | Synced with climate/humidifier |

---

## Regulation decision table

Temperature has priority (food-safety). The humidity actuators may flip at most
once per anti-oscillation window (default 10 min).

| Temperature | Humidity | Cooling | Heating | Humidifier | Dehumidifier | Notes |
|---|---|---|---|---|---|---|
| > target + band | any | **ON** | OFF | per humidity | per humidity | Cooling dries the air; humidifier may compensate |
| < target − band | any | OFF | **ON** | per humidity | per humidity | Heating lowers relative humidity |
| in band | > target + band | idle | idle | OFF | **ON** | — |
| in band | < target − band | idle | idle | **ON** | OFF | — |
| needs cooling, **no cooling actuator**, > extended band, > 15 min | — | — | — | — | — | **Degraded** → manual action *"lower the thermostat / move somewhere cooler"* |
| — | needs humidifying, **no humidifier**, < extended band, > 15 min | — | — | — | — | **Degraded** → manual action *"tray of salted water / plug a humidifier"* |
| unavailable / frozen sensor | — | **OFF** | **OFF** | **OFF** | **OFF** | Critical fault, safe state |
| outside [abs_min; abs_max] | — | cut aggravating actuator | | | | Critical alert |

Guards applied to every command: startup lockout (default 2 min), min OFF
(cooling 7 min), min ON (cooling 3 min), and the mutual-exclusion invariants.
Every decision (value, band, action, reason, blocking timer) is logged at
`debug` and exposed in the *Regulation state* sensor attributes.

---

## Presets

Built-in, **indicative** starting points — duplicate and adapt to your recipes.
Weight-loss phases carry an approximate max duration (also the fallback when no
scale is configured).

| Preset | Phase 1 (rest) | Phase 2 (drying) | End |
|---|---|---|---|
| Saucisson sec | 22 °C / 80 %RH, 36 h | 13 °C / 76 %RH | −35 % or ~5 weeks |
| Coppa | 22 °C / 80 %RH, 24 h | 13 °C / 75 %RH | −35 % or ~8 weeks |
| Bresaola | 20 °C / 75 %RH, 24 h | 13 °C / 72 %RH | −35 % or ~6 weeks |
| Pancetta roulée | 22 °C / 80 %RH, 24 h | 13 °C / 75 %RH | −30 % or ~4 weeks |
| Lonzo / dried tenderloin | — | 13 °C / 75 %RH | −35 % or ~4 weeks |
| Cellar hold | — | 12 °C / 78 %RH | manual |

---

## User programs (JSON)

Create/update a program with the `curing_chamber.create_program` service. A
program is an ordered list of phases; each phase regulates temperature,
humidity, or both, and ends on `duration`, `weight_loss` or `manual`. A
`weight_loss` phase should also carry `duration_hours` as a safety cap /
no-scale fallback.

```yaml
service: curing_chamber.create_program
data:
  program:
    id: my_coppa
    name: My Coppa
    on_complete: hold_last   # or "stop"
    phases:
      - name: rest
        target_temp: 22
        target_humidity: 80
        end_kind: duration
        duration_hours: 24
      - name: drying
        target_temp: 13
        target_humidity: 75
        end_kind: weight_loss
        weight_loss_pct: 35
        duration_hours: 1344   # ~8 weeks safety cap
        notify_end: true
```

Then start it: `curing_chamber.start_program` with `program_id: my_coppa`.
Other services: `stop_program`, `pause_program`, `resume_program`, `next_phase`,
`set_targets`, `set_reference_weight`, `acknowledge_alert`, `delete_program`.
When several chambers exist, target one with the `device_id` field.

---

## Batches & manual weigh-ins

A **batch** is one product curing in the chamber, with its own reference weight,
target weight loss and a **history of weigh-ins**. Weigh-ins can come from a
scale or be entered by hand — **no scale required** — optionally with a note and
a photo. From the weigh-in history the integration derives each batch's current
weight loss, drying rate and a **predicted completion date (ETA)**.

Several batches can be tracked at once; the one you mark as **reference** drives
the running program's weight-loss phase end (others are tracked for their curve
and ETA). A batch that reaches its target loss is auto-completed and fires a
`batch_completed` bus event.

```yaml
# Create a batch (first one becomes the reference automatically)
service: curing_chamber.create_batch
data:
  name: "Coppa #1"
  product: coppa
  reference_weight: 1200      # omit to use the first weigh-in as the reference
  target_loss_pct: 35

# Record a weigh-in — works without a scale; photo is optional
service: curing_chamber.record_weight
data:
  batch_id: coppa_1
  weight: 1080
  note: "day 12"
  photo: "/config/www/photos/coppa_day12.jpg"   # path, base64 or data: URL
```

Photos are stored under `<config>/www/curing_chamber/<batch_id>/` and served at
`/local/curing_chamber/<batch_id>/…`. Other batch services:
`set_reference_batch`, `complete_batch`, `archive_batch`, `delete_batch`.

New sensors: **Active batches** (with a `batches` attribute carrying every
batch's loss/rate/ETA/photo — the data source for the card below),
**Reference batch weight loss** (%) and **Reference batch estimated end** (a
timestamp).

### Custom card

The integration bundles a Lovelace card (`curing-chamber-card`, auto-registered)
showing each batch's drying curve, loss gauge and ETA, plus an inline
weight-and-photo form to record a weigh-in from your phone:

```yaml
type: custom:curing-chamber-card
entity: sensor.curing_chamber_active_batches
```

---

## Example dashboard (Lovelace YAML)

```yaml
type: vertical-stack
cards:
  - type: thermostat
    entity: climate.curing_chamber_temperature
  - type: humidifier
    entity: humidifier.curing_chamber_humidity
  - type: entities
    title: Program
    entities:
      - entity: select.curing_chamber_program
      - entity: sensor.curing_chamber_current_phase
      - entity: sensor.curing_chamber_phase_time_remaining
      - entity: button.curing_chamber_next_phase
      - entity: button.curing_chamber_set_reference_weight
  - type: gauge
    name: Weight loss
    entity: sensor.curing_chamber_weight_loss
    min: 0
    max: 45
    needle: true
    severity:
      green: 0
      yellow: 30
      red: 38
  - type: entities
    title: Climate & quality
    entities:
      - sensor.curing_chamber_dew_point
      - sensor.curing_chamber_absolute_humidity
      - sensor.curing_chamber_drying_rate
      - sensor.curing_chamber_regulation_state
  - type: entities
    title: Alerts
    entities:
      - binary_sensor.curing_chamber_manual_action_required
      - binary_sensor.curing_chamber_out_of_range_alarm
      - binary_sensor.curing_chamber_sensor_fault
      - binary_sensor.curing_chamber_probe_divergence
      - binary_sensor.curing_chamber_door_open_too_long
      - button.curing_chamber_acknowledge_alerts
  - type: history-graph
    hours_to_show: 168
    entities:
      - sensor.chamber_temperature
      - sensor.chamber_humidity
```

Automate on bus events (`curing_chamber_event`, types `phase_changed`,
`program_completed`, `alert_raised`, `alert_cleared`, `manual_action_required`)
or on the `binary_sensor.*_manual_action_required` state.

---

## FAQ / troubleshooting

- **The cooling switch never turns on.** Check: the chamber has a temperature
  sensor (valid, not stale), the target is below the current temperature by more
  than the deadband, the startup lockout (2 min) has elapsed, and the
  compressor min-OFF time (7 min) has elapsed since it last stopped.
- **I get "sensor fault" alerts.** The temperature or humidity sensor is
  `unavailable`/`unknown`, or its value hasn't changed for the frozen-sensor
  timeout (default 30 min). Actuators are stopped until it recovers.
- **Humidity keeps drifting and I'm told to act manually.** You have no
  humidifier/dehumidifier configured to correct it. Add one, or follow the
  suggested manual action; acknowledge to silence reminders.
- **Program doesn't advance on weight.** Set the reference weight first
  (*Set reference weight* button or `set_reference_weight`), and make sure a
  weight sensor is configured. Without a scale, the phase falls back to its
  duration cap.
- **After a restart the program resumed at the wrong time.** It shouldn't — the
  phase clock is persisted. File an issue with your diagnostics download.
- **The card shows "Configuration error" (`Erreur de configuration`).** That
  message means Home Assistant can't find the `curing-chamber-card` custom
  element yet — the card's JavaScript isn't loaded in your browser; it is *not*
  a problem with the YAML you pasted. Fix it in this order:
  1. **Restart Home Assistant** after installing/updating the integration. The
     card is auto-registered during setup, so it only becomes available on the
     next full frontend load.
  2. **Hard-refresh the browser** (Ctrl/Cmd + Shift + R), or empty the cache —
     the HA frontend service worker caches aggressively and can keep serving a
     page that predates the card.
  3. **Check the entity name.** The example uses
     `sensor.curing_chamber_active_batches`, which assumes a chamber named
     *Curing Chamber*. If you named yours differently the sensor is
     `sensor.<your_chamber>_active_batches` — a wrong name shows an *"Unknown
     entity"* note inside the card (not a configuration error).
  4. **Still failing?** Confirm the JS is served: open
     `https://<your-ha>/curing_chamber/curing-chamber-card.js` — it should
     return JavaScript, not a 404. If auto-load didn't happen, add it manually
     under **Settings → Dashboards → Resources → Add resource**, URL
     `/curing_chamber/curing-chamber-card.js`, type **JavaScript Module**, then
     hard-refresh. Check **Settings → System → Logs** for a `curing_chamber`
     warning explaining why registration failed.

Download **Diagnostics** from the device page for a full, anonymized state dump
(config, last decisions, counters, active alerts).

---

## Development

```bash
python -m pip install ruff mypy pytest-homeassistant-custom-component pytest-cov
ruff check custom_components tests
ruff format --check custom_components tests
mypy                       # strict, pure engines
pytest --cov=custom_components/curing_chamber/regulation \
       --cov=custom_components/curing_chamber/program \
       --cov=custom_components/curing_chamber/batch
```

The control logic lives in three **pure** packages (`regulation/`, `program/`,
`batch/`) with no `homeassistant` imports and injected time, unit-tested to
≥ 85 % without Home Assistant. CI runs ruff, mypy, pytest+coverage, hassfest and
HACS validation on Python 3.13.

Roadmap: PID control, and an exponential (rather than linear) drying-curve
model for a sharper ETA near the end of curing.

---
---

# 🇫🇷 Séchoir à charcuterie — version française

Intégration Home Assistant qui transforme un réfrigérateur détourné (ou toute
enceinte) en séchoir à charcuterie régulé : elle tient des consignes de
température et d'hygrométrie sur des programmes de séchage multi-phases, et —
point clé — quand une grandeur dérive et qu'**aucun actionneur ne peut la
corriger**, elle vous indique précisément l'action manuelle à réaliser.

100 % local, sans cloud. Interface de configuration (config flow), entités
natives `climate` / `humidifier`, programmes multi-phases avec presets, alertes
d'action manuelle en mode dégradé, diagnostics, traductions FR/EN complètes.

> ⚠️ **Avertissement sécurité alimentaire.** Cette intégration pilote
> l'*environnement* du séchoir. Elle ne garantit **pas** la salubrité du
> produit : elle ne mesure ni l'activité de l'eau (a\_w) ni le pH. L'hygiène, le
> salage correct (sel nitrité le cas échéant) et les recettes restent **votre**
> responsabilité. Les alertes sanitaires ne sont pas désactivables globalement,
> seulement ajustables dans des bornes raisonnables.

## Fonctionnalités

- **Actionneurs tous optionnels** : froid, chauffage, humidificateur,
  déshumidificateur, ventilateur de brassage, renouvellement d'air — n'importe
  quel sous-ensemble, y compris aucun (surveillance seule).
- **Régulation tout-ou-rien à hystérésis** avec protection compresseur (temps
  min ON/OFF, anti-rebond au démarrage), exclusions mutuelles (jamais
  froid+chaud, jamais humidif.+déshumidif.) et fenêtre anti-oscillation.
- **Couplage T°/HR à priorité température** (voir le [tableau de décision](#tableau-de-décision-de-la-régulation)).
- **Mode dégradé** : si une grandeur sort de la bande de tolérance étendue et
  qu'aucun actionneur ne peut la corriger, notification d'action manuelle
  contextualisée (ex. *« Hygrométrie 62 % (cible 75 %) : placez un bac d'eau
  salée dans la chambre »*), avec rappels anti-spam et résolution automatique.
- **Sécurité d'abord** : capteur indisponible ou figé → tous les actionneurs
  coupés + alerte critique. On ne régule jamais à l'aveugle. Les limites
  absolues coupent l'actionneur aggravant.
- **Programmes multi-phases** avec 6 presets ; fin de phase sur durée, perte de
  poids (avec balance) ou manuelle.
- **Lots de produits** avec **pesées manuelles** (sans balance, note + photo
  optionnelles), courbe de séchage par lot et **date de fin estimée (ETA)** ; le
  lot de référence pilote la phase de perte de poids du programme.
- **Capteurs dérivés** : point de rosée (Magnus), humidité absolue, perte de
  poids %, vitesse de séchage %/jour.
- **Carte Lovelace personnalisée** fournie avec l'intégration.

## Installation (HACS)

1. HACS → *Intégrations* → menu ⋮ → **Dépôts personnalisés**.
2. Ajoutez `https://github.com/ttiot/curingchamber`, catégorie **Intégration**.
3. Installez **Curing Chamber**, puis redémarrez Home Assistant.
4. *Paramètres → Appareils et services → Ajouter une intégration → Curing Chamber*.

Installation manuelle : copiez `custom_components/curing_chamber/` dans le
dossier `config/custom_components/` de HA et redémarrez.

## Configuration (pas à pas)

Le config flow comporte quatre écrans :

1. **Capteurs** — nommez la chambre et choisissez les sondes de température et
   d'hygrométrie. Optionnel : seconde sonde T°/HR (moyennée, avec alerte de
   divergence), température à cœur, capteur de poids, capteur CO₂, capteur
   d'ouverture de porte. *L'intégration s'installe même sans capteur.*
2. **Actionneurs** — froid / chauffage / humidificateur / déshumidificateur /
   ventilateur / renouvellement d'air (au choix). Toute entité `switch`,
   `input_boolean`, `fan` ou `light` convient.
3. **Notifications** — éventuellement un ou plusieurs services `notify.*`. Des
   notifications persistantes sont toujours créées.
4. **Avertissement sécurité alimentaire** — lisez et validez pour terminer.

Tout est reconfigurable ensuite via *Configurer* (options) : **Capteurs**,
**Actionneurs**, **Régulation & sécurité** (bandes mortes, temporisations
compresseur, limites absolues, délais mode dégradé…), **Notifications**.

## Entités

| Domaine | Entité | Rôle |
|---|---|---|
| `climate` | Température | Consigne + mode (off/froid/chaud/auto selon actionneurs), action ralenti/refroidissement/chauffe |
| `humidifier` | Hygrométrie | Consigne + action humidification/séchage/ralenti |
| `select` | Programme | Programme/preset actif (`none` = arrêt) |
| `sensor` | Phase courante | Nom de la phase (+ statut, index) |
| `sensor` | Temps restant de phase | Heures estimées (phases de durée) |
| `sensor` | Point de rosée | °C (Magnus) |
| `sensor` | Humidité absolue | g/m³ |
| `sensor` | Perte de poids | % vs poids de référence |
| `sensor` | Vitesse de séchage | %/jour |
| `sensor` | État de régulation | ralenti/froid/…, dernières décisions en attributs |
| `sensor` | Temps de fonct. *actionneur* | Heures cumulées par actionneur (maintenance) |
| `binary_sensor` | Action manuelle requise | ON, action(s) recommandée(s) en attributs |
| `binary_sensor` | Alarme hors-plage | Limite absolue / T° trop haute |
| `binary_sensor` | Défaut capteur | Capteur indisponible ou figé |
| `binary_sensor` | Divergence des sondes | Deux sondes en désaccord |
| `binary_sensor` | Porte ouverte trop longtemps | — |
| `switch` | Régulation | Activation générale |
| `switch` | Mode maintenance | Tout OFF, pas d'alertes |
| `button` | Phase suivante / Poids de référence / Acquitter | — |
| `number` | Consigne manuelle T° / HR | Synchronisées avec climate/humidifier |

## Tableau de décision de la régulation

La température est prioritaire (sécurité sanitaire). Les actionneurs d'humidité
ne changent d'état qu'une fois par fenêtre anti-oscillation (défaut 10 min).

| Température | Hygrométrie | Froid | Chauffage | Humidif. | Déshumidif. | Notes |
|---|---|---|---|---|---|---|
| > cible + bande | quelconque | **ON** | OFF | selon HR | selon HR | Le froid assèche ; l'humidificateur peut compenser |
| < cible − bande | quelconque | OFF | **ON** | selon HR | selon HR | Le chauffage fait chuter l'HR relative |
| dans la bande | > cible + bande | ralenti | ralenti | OFF | **ON** | — |
| dans la bande | < cible − bande | ralenti | ralenti | **ON** | OFF | — |
| besoin de froid, **pas d'actionneur froid**, > bande étendue, > 15 min | — | — | — | — | — | **Dégradé** → *« baissez le thermostat / lieu plus frais »* |
| — | besoin d'humidifier, **pas d'humidificateur**, < bande étendue, > 15 min | — | — | — | — | **Dégradé** → *« bac d'eau salée / branchez un humidificateur »* |
| capteur indispo/figé | — | **OFF** | **OFF** | **OFF** | **OFF** | Défaut critique, état sûr |
| hors [min; max] absolus | — | coupe l'actionneur aggravant | | | | Alerte critique |

Garde-fous sur chaque commande : anti-rebond démarrage (2 min), temps min OFF
(froid 7 min), min ON (froid 3 min), exclusions mutuelles. Chaque décision
(valeur, bande, action, raison, temporisation) est journalisée en `debug` et
exposée dans les attributs du capteur *État de régulation*.

## Presets

Points de départ **indicatifs** — à dupliquer et adapter à vos recettes. Les
phases en perte de poids portent une durée max approximative (aussi le repli
sans balance).

| Preset | Phase 1 (étuvage) | Phase 2 (séchage) | Fin |
|---|---|---|---|
| Saucisson sec | 22 °C / 80 %HR, 36 h | 13 °C / 76 %HR | −35 % ou ~5 semaines |
| Coppa | 22 °C / 80 %HR, 24 h | 13 °C / 75 %HR | −35 % ou ~8 semaines |
| Bresaola | 20 °C / 75 %HR, 24 h | 13 °C / 72 %HR | −35 % ou ~6 semaines |
| Pancetta roulée | 22 °C / 80 %HR, 24 h | 13 °C / 75 %HR | −30 % ou ~4 semaines |
| Lonzo / filet mignon séché | — | 13 °C / 75 %HR | −35 % ou ~4 semaines |
| Maintien cave d'affinage | — | 12 °C / 78 %HR | manuelle |

## Programmes utilisateur (JSON)

Créez/modifiez un programme avec le service `curing_chamber.create_program` (même
format que ci-dessus, section anglaise). Une phase en `weight_loss` doit aussi
porter `duration_hours` (plafond de sécurité / repli sans balance). Démarrez avec
`curing_chamber.start_program` (`program_id`). Autres services : `stop_program`,
`pause_program`, `resume_program`, `next_phase`, `set_targets`,
`set_reference_weight`, `acknowledge_alert`, `delete_program`. Avec plusieurs
chambres, ciblez-en une via le champ `device_id`.

## Lots & pesées manuelles

Un **lot** est un produit en cours d'affinage, avec son poids de référence, sa
cible de perte de poids et un **historique de pesées**. Les pesées peuvent venir
d'une balance ou être **saisies à la main — sans balance** — avec, en option,
une note et une photo. À partir de cet historique, l'intégration calcule pour
chaque lot la perte de poids courante, la vitesse de séchage et une **date de
fin estimée (ETA)**.

Plusieurs lots peuvent être suivis en parallèle ; celui marqué comme
**référence** pilote la fin de phase `weight_loss` du programme (les autres sont
suivis pour leur courbe et leur ETA). Un lot atteignant sa cible passe
automatiquement à « terminé » et émet un événement `batch_completed`.

```yaml
# Créer un lot (le premier devient automatiquement la référence)
service: curing_chamber.create_batch
data:
  name: "Coppa #1"
  product: coppa
  reference_weight: 1200      # omettre pour prendre la 1re pesée comme référence
  target_loss_pct: 35

# Enregistrer une pesée — fonctionne sans balance ; photo optionnelle
service: curing_chamber.record_weight
data:
  batch_id: coppa_1
  weight: 1080
  note: "jour 12"
  photo: "/config/www/photos/coppa_jour12.jpg"   # chemin, base64 ou URL data:
```

Les photos sont stockées sous `<config>/www/curing_chamber/<batch_id>/` et
servies via `/local/curing_chamber/<batch_id>/…`. Autres services de lot :
`set_reference_batch`, `complete_batch`, `archive_batch`, `delete_batch`.

Nouveaux capteurs : **Lots actifs** (attribut `batches` détaillant perte / vitesse
/ ETA / photo de chaque lot — source de données de la carte),
**Perte de poids du lot de référence** (%) et **Fin estimée du lot de référence**.

### Carte personnalisée

L'intégration fournit une carte Lovelace (`curing-chamber-card`, auto-enregistrée)
montrant la courbe de séchage, la jauge de perte et l'ETA de chaque lot, plus un
formulaire intégré poids + photo pour saisir une pesée depuis votre téléphone :

```yaml
type: custom:curing-chamber-card
entity: sensor.curing_chamber_active_batches
```

## FAQ / dépannage

- **Le froid ne démarre jamais.** Vérifiez : sonde de température présente
  (valide, non figée), consigne inférieure à la température actuelle au-delà de
  la bande morte, anti-rebond démarrage (2 min) écoulé, et temps min OFF
  compresseur (7 min) écoulé depuis le dernier arrêt.
- **Alertes « défaut capteur ».** La sonde est `unavailable`/`unknown`, ou sa
  valeur n'a pas changé depuis le délai capteur figé (défaut 30 min). Les
  actionneurs sont coupés jusqu'au rétablissement.
- **On me demande d'agir manuellement sur l'HR.** Aucun humidificateur/
  déshumidificateur n'est configuré pour corriger. Ajoutez-en un, ou suivez
  l'action proposée ; acquittez pour couper les rappels.
- **Le programme n'avance pas sur la perte de poids.** Définissez d'abord le
  poids de référence (bouton ou `set_reference_weight`) et vérifiez qu'une
  balance est configurée. Sans balance, la phase retombe sur son plafond de durée.
- **La carte affiche « Erreur de configuration ».** Ce message signifie que Home
  Assistant ne trouve pas encore l'élément personnalisé `curing-chamber-card` :
  le JavaScript de la carte n'est pas chargé dans votre navigateur — ce n'est
  *pas* un problème du YAML collé. Corrigez dans cet ordre :
  1. **Redémarrez Home Assistant** après l'installation/mise à jour. La carte
     est auto-enregistrée au démarrage de l'intégration ; elle n'est disponible
     qu'au prochain chargement complet du frontend.
  2. **Forcez le rechargement du navigateur** (Ctrl/Cmd + Maj + R) ou videz le
     cache — le service worker du frontend HA met fortement en cache et peut
     continuer à servir une page antérieure à la carte.
  3. **Vérifiez le nom de l'entité.** L'exemple utilise
     `sensor.curing_chamber_active_batches`, qui suppose une enceinte nommée
     *Curing Chamber*. Si vous l'avez nommée autrement, le capteur est
     `sensor.<votre_enceinte>_active_batches` — un mauvais nom affiche une note
     *« Unknown entity »* dans la carte (et non une erreur de configuration).
  4. **Toujours en échec ?** Vérifiez que le JS est bien servi : ouvrez
     `https://<votre-ha>/curing_chamber/curing-chamber-card.js` — cela doit
     renvoyer du JavaScript, pas une erreur 404. Si l'auto-chargement n'a pas eu
     lieu, ajoutez-le manuellement dans **Paramètres → Tableaux de bord →
     Ressources → Ajouter**, URL `/curing_chamber/curing-chamber-card.js`, type
     **Module JavaScript**, puis rechargez de force. Consultez **Paramètres →
     Système → Journaux** : un avertissement `curing_chamber` explique tout
     échec d'enregistrement.

Téléchargez les **Diagnostics** depuis la page de l'appareil pour un export
complet et anonymisé (config, dernières décisions, compteurs, alertes actives).

## Développement

Voir la section anglaise ci-dessus (ruff, mypy, pytest). La logique de contrôle
vit dans trois paquets **purs** (`regulation/`, `program/`, `batch/`) sans import
`homeassistant` et avec temps injecté, testés unitairement à ≥ 85 % sans Home
Assistant. La CI exécute ruff, mypy, pytest+couverture, hassfest et la
validation HACS sous Python 3.13.

Roadmap : régulation PID, et un modèle de courbe de séchage exponentiel (plutôt
que linéaire) pour affiner l'ETA en fin d'affinage.
