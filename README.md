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
- **Derived sensors:** dew point (Magnus), absolute humidity, weight loss %,
  drying rate %/day.
- **Native entities** (`climate`, `humidifier`, `sensor`, `binary_sensor`,
  `switch`, `select`, `button`, `number`), services and bus events.

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
       --cov=custom_components/curing_chamber/program
```

The control logic lives in two **pure** packages (`regulation/`, `program/`)
with no `homeassistant` imports and injected time, unit-tested to ≥ 85 % without
Home Assistant. CI runs ruff, mypy, pytest+coverage, hassfest and HACS
validation on Python 3.13.

Roadmap (out of scope for v1): PID control, custom Lovelace card, predictive
drying curves, multiple products per chamber.

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
- **Capteurs dérivés** : point de rosée (Magnus), humidité absolue, perte de
  poids %, vitesse de séchage %/jour.

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

Téléchargez les **Diagnostics** depuis la page de l'appareil pour un export
complet et anonymisé (config, dernières décisions, compteurs, alertes actives).

## Développement

Voir la section anglaise ci-dessus (ruff, mypy, pytest). La logique de contrôle
vit dans deux paquets **purs** (`regulation/`, `program/`) sans import
`homeassistant` et avec temps injecté, testés unitairement à ≥ 85 % sans Home
Assistant. La CI exécute ruff, mypy, pytest+couverture, hassfest et la
validation HACS sous Python 3.13.

Hors périmètre v1 (roadmap) : régulation PID, carte Lovelace custom, courbes de
séchage prédictives, multi-produits par chambre.
