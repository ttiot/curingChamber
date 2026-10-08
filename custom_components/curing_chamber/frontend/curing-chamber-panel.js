/*
 * Curing Chamber — sidebar panel.
 *
 * Dependency-free vanilla web component (ES module, no build step, no CDN). It
 * is registered by the integration through `panel_custom` and talks to the
 * backend over the `curing_chamber/*` websocket commands plus the existing
 * services. Four views: Chamber (live regulation), Batches (weigh-ins, curves,
 * photos), Programs (phase editor) and History (compare finished batches).
 *
 * Theming goes exclusively through Home Assistant CSS variables so light and
 * dark themes both work. All timestamps exchanged with the backend are epoch
 * seconds (UTC).
 */

const PANEL_TAG = "curing-chamber-panel";
const LS_CHAMBER = "curing_chamber.panel.entry_id";
const LS_TAB = "curing_chamber.panel.tab";
const TABS = ["chamber", "batches", "programs", "history"];
const JOURNAL_KINDS = ["note", "salting", "hung", "turned", "washed", "tasting", "other"];
const SIGN_TTL_MS = 50 * 60 * 1000; // re-sign photo urls after ~50 min (signed for 60)
const CURVE_COLORS = [
  "#1e88e5", "#e53935", "#43a047", "#fb8c00", "#8e24aa", "#00acc1", "#6d4c41", "#546e7a",
];

// ---------------------------------------------------------------------------
// i18n
// ---------------------------------------------------------------------------

const STR = {
  en: {
    title: "Curing Chamber",
    tab_chamber: "Chamber",
    tab_batches: "Batches",
    tab_programs: "Programs",
    tab_history: "History",
    no_chambers: "No curing chamber is configured yet.",
    no_chambers_hint: "Ask an administrator to add one from Settings → Devices & services.",
    add_chamber: "Add a chamber",
    loading: "Loading…",
    temperature: "Temperature",
    humidity: "Humidity",
    dew_point: "Dew point",
    target: "target",
    actuators: "Actuators",
    on: "on",
    off: "off",
    unknown: "unknown",
    program: "Program",
    status_idle: "Idle",
    status_running: "Running",
    status_paused: "Paused",
    status_completed: "Completed",
    phase: "Phase",
    remaining: "remaining",
    start: "Start",
    pause: "Pause",
    resume: "Resume",
    stop: "Stop",
    next_phase: "Next phase",
    pick_program: "Pick a program…",
    manual_targets: "Manual targets",
    apply: "Apply",
    regulation: "Regulation",
    maintenance: "Maintenance mode",
    alerts: "Alerts",
    no_alerts: "No active alert.",
    acknowledge: "Acknowledge",
    decisions: "Last regulation decisions",
    no_decisions: "No decision yet.",
    wants_on: "wants ON",
    wants_off: "wants OFF",
    blocked_by: "blocked by",
    weight: "Weight",
    reference_weight: "Reference weight",
    weight_loss: "Weight loss",
    drying_rate: "Drying rate",
    source_batch: "from reference batch",
    source_scale: "from scale",
    source_manual: "manual entry",
    set_reference_weight: "Set reference weight",
    summary: "Regulation state",
    // batches
    new_batch: "New batch",
    show_archived: "Show archived",
    no_batches: "No batch yet. Create one to start tracking weigh-ins.",
    name: "Name",
    product: "Product",
    program_optional: "Program (optional)",
    none: "None",
    target_loss: "Target loss (%)",
    set_as_reference: "Set as reference batch",
    create: "Create",
    cancel: "Cancel",
    back: "Back",
    reference: "reference",
    status_active: "active",
    status_archived: "archived",
    loss: "Loss",
    rate: "Rate",
    eta: "ETA",
    weigh_ins: "weigh-ins",
    weigh_in_due: "weigh-in due",
    last_weigh_in: "Last weigh-in",
    drying_curve: "Drying curve",
    curve_needs_two: "The curve appears once two weigh-ins are recorded.",
    history: "Weigh-in history",
    date: "Date",
    note: "Note",
    photo: "Photo",
    delete: "Delete",
    confirm_delete_sample: "Delete this weigh-in?",
    start_program_now: "Start this program now",
    journal: "Journal",
    add_entry: "Add entry",
    kind: "Kind",
    kind_note: "Note",
    kind_salting: "Salting",
    kind_hung: "Hung / put in chamber",
    kind_turned: "Turned",
    kind_washed: "Washed / brushed",
    kind_tasting: "Tasting",
    kind_other: "Other",
    confirm_delete_event: "Delete this journal entry?",
    export_json: "Export JSON",
    export_csv: "Export CSV",
    eta_model_exponential: "exponential model",
    eta_model_linear: "linear model",
    no_entries: "No journal entry yet.",
    core_temp: "Core",
    core_delta: "core − air",
    reminders: "Care reminders",
    add_reminder: "Add reminder",
    every_hours: "every (h)",
    all_phases: "all phases",
    next_reminder: "Next reminder",
    reminder_hint: "While the program runs, a notification suggests this journal entry at the given interval (restarted when a targeted phase begins).",
    confirm_delete_batch: "Delete this batch and all its weigh-ins? This cannot be undone.",
    gallery: "Photos",
    record_weigh_in: "Record a weigh-in",
    note_placeholder: "e.g. day 12, white mould forming",
    when: "When",
    now: "Now",
    record: "Record",
    recorded: "Weigh-in recorded.",
    enter_weight: "Enter a weight.",
    make_reference: "Make reference",
    complete: "Complete",
    archive: "Archive",
    reactivate: "Reactivate",
    days: "days",
    day_short: "d",
    hour_short: "h",
    // programs
    new_program: "New program",
    no_programs: "No program available.",
    preset: "preset",
    duplicate: "Duplicate",
    edit: "Edit",
    view: "View",
    start_this: "Start this program",
    program_id: "Identifier",
    on_complete: "When finished",
    hold_last: "Hold last phase targets",
    stop_regulation: "Stop regulating",
    phases: "Phases",
    phase_name: "Phase name",
    target_temp_short: "T° (°C)",
    target_hum_short: "RH (%)",
    end_kind: "Ends on",
    end_duration: "duration",
    end_weight_loss: "weight loss",
    end_manual: "manual",
    end_core_temp: "core temp.",
    core_temp_target: "Core °C",
    duration_hours: "Hours",
    weight_loss_pct: "Loss %",
    notify_end: "Notify",
    add_phase: "Add phase",
    move_up: "Move up",
    move_down: "Move down",
    remove: "Remove",
    save: "Save",
    saved: "Program saved.",
    deleted: "Deleted.",
    confirm_delete_program: "Delete this program?",
    valid: "Program is valid.",
    errors: "Errors",
    warnings: "Warnings",
    copy_suffix: "copy",
    read_only_preset: "Built-in preset — duplicate it to edit.",
    ramp: "Ramp",
    ramp_from: "Ramp from",
    ramp_hours: "over (h)",
    ramp_hint: "Optional: the targets move linearly from these start values to the phase targets over the given hours.",
    ramp_in_progress: "ramp in progress",
    ramp_to: "to",
    category: "Category",
    cat_charcuterie: "Charcuterie",
    cat_cheese: "Cheese",
    kind_charcuterie: "Charcuterie drying chamber",
    kind_cheese: "Cheese ripening cave",
    presets: "Presets",
    my_programs: "My programs",
    export: "Export",
    export_all: "Export all",
    import: "Import",
    imported: "imported",
    skipped: "skipped (already exist)",
    import_overwrite: "Replace programs that already exist?",
    import_invalid: "Not a valid program file.",
    // history
    no_history: "No completed or archived batch yet.",
    select_to_compare: "Tick batches to overlay their drying curves.",
    final_loss: "Final loss",
    duration: "Duration",
    mean_rate: "Mean rate",
    compare: "Compare",
    // misc
    error: "Error",
    started: "Program started.",
    applied: "Applied.",
    version: "version",
    chamber: "Chamber",
  },
  fr: {
    title: "Séchoir",
    tab_chamber: "Chambre",
    tab_batches: "Lots",
    tab_programs: "Programmes",
    tab_history: "Historique",
    no_chambers: "Aucun séchoir configuré.",
    no_chambers_hint: "Demandez à un administrateur d'en ajouter un dans Paramètres → Appareils et services.",
    add_chamber: "Ajouter un séchoir",
    loading: "Chargement…",
    temperature: "Température",
    humidity: "Hygrométrie",
    dew_point: "Point de rosée",
    target: "cible",
    actuators: "Actionneurs",
    on: "allumé",
    off: "éteint",
    unknown: "inconnu",
    program: "Programme",
    status_idle: "Inactif",
    status_running: "En cours",
    status_paused: "En pause",
    status_completed: "Terminé",
    phase: "Phase",
    remaining: "restant",
    start: "Démarrer",
    pause: "Pause",
    resume: "Reprendre",
    stop: "Arrêter",
    next_phase: "Phase suivante",
    pick_program: "Choisir un programme…",
    manual_targets: "Consignes manuelles",
    apply: "Appliquer",
    regulation: "Régulation",
    maintenance: "Mode maintenance",
    alerts: "Alertes",
    no_alerts: "Aucune alerte active.",
    acknowledge: "Acquitter",
    decisions: "Dernières décisions de régulation",
    no_decisions: "Aucune décision pour l'instant.",
    wants_on: "demande ON",
    wants_off: "demande OFF",
    blocked_by: "bloqué par",
    weight: "Poids",
    reference_weight: "Poids de référence",
    weight_loss: "Perte de poids",
    drying_rate: "Vitesse de séchage",
    source_batch: "du lot de référence",
    source_scale: "de la balance",
    source_manual: "saisie manuelle",
    set_reference_weight: "Fixer le poids de référence",
    summary: "État de la régulation",
    new_batch: "Nouveau lot",
    show_archived: "Afficher les archivés",
    no_batches: "Aucun lot. Créez-en un pour commencer à suivre les pesées.",
    name: "Nom",
    product: "Produit",
    program_optional: "Programme (optionnel)",
    none: "Aucun",
    target_loss: "Perte cible (%)",
    set_as_reference: "Définir comme lot de référence",
    create: "Créer",
    cancel: "Annuler",
    back: "Retour",
    reference: "référence",
    status_active: "actif",
    status_archived: "archivé",
    loss: "Perte",
    rate: "Vitesse",
    eta: "Fin estimée",
    weigh_ins: "pesées",
    weigh_in_due: "pesée à faire",
    last_weigh_in: "Dernière pesée",
    drying_curve: "Courbe de séchage",
    curve_needs_two: "La courbe apparaît dès deux pesées.",
    history: "Historique des pesées",
    date: "Date",
    note: "Note",
    photo: "Photo",
    delete: "Supprimer",
    confirm_delete_sample: "Supprimer cette pesée ?",
    start_program_now: "Démarrer ce programme maintenant",
    journal: "Journal",
    add_entry: "Ajouter",
    kind: "Type",
    kind_note: "Note",
    kind_salting: "Salage",
    kind_hung: "Mise en séchoir",
    kind_turned: "Retournement",
    kind_washed: "Lavage / brossage",
    kind_tasting: "Dégustation",
    kind_other: "Autre",
    confirm_delete_event: "Supprimer cette entrée du journal ?",
    export_json: "Exporter JSON",
    export_csv: "Exporter CSV",
    eta_model_exponential: "modèle exponentiel",
    eta_model_linear: "modèle linéaire",
    no_entries: "Aucune entrée pour l'instant.",
    core_temp: "À cœur",
    core_delta: "cœur − air",
    reminders: "Rappels d'entretien",
    add_reminder: "Ajouter un rappel",
    every_hours: "toutes les (h)",
    all_phases: "toutes les phases",
    next_reminder: "Prochain rappel",
    reminder_hint: "Pendant le programme, une notification propose cette entrée de journal à l'intervalle indiqué (relancé au début d'une phase ciblée).",
    confirm_delete_batch: "Supprimer ce lot et toutes ses pesées ? Cette action est irréversible.",
    gallery: "Photos",
    record_weigh_in: "Enregistrer une pesée",
    note_placeholder: "ex. jour 12, fleur blanche en formation",
    when: "Quand",
    now: "Maintenant",
    record: "Enregistrer",
    recorded: "Pesée enregistrée.",
    enter_weight: "Saisissez un poids.",
    make_reference: "Définir référence",
    complete: "Terminer",
    archive: "Archiver",
    reactivate: "Réactiver",
    days: "jours",
    day_short: "j",
    hour_short: "h",
    new_program: "Nouveau programme",
    no_programs: "Aucun programme disponible.",
    preset: "preset",
    duplicate: "Dupliquer",
    edit: "Modifier",
    view: "Voir",
    start_this: "Démarrer ce programme",
    program_id: "Identifiant",
    on_complete: "À la fin",
    hold_last: "Maintenir les consignes de la dernière phase",
    stop_regulation: "Arrêter la régulation",
    phases: "Phases",
    phase_name: "Nom de la phase",
    target_temp_short: "T° (°C)",
    target_hum_short: "HR (%)",
    end_kind: "Fin sur",
    end_duration: "durée",
    end_weight_loss: "perte de poids",
    end_manual: "manuelle",
    end_core_temp: "T° à cœur",
    core_temp_target: "Cœur °C",
    duration_hours: "Heures",
    weight_loss_pct: "Perte %",
    notify_end: "Notifier",
    add_phase: "Ajouter une phase",
    move_up: "Monter",
    move_down: "Descendre",
    remove: "Retirer",
    save: "Enregistrer",
    saved: "Programme enregistré.",
    deleted: "Supprimé.",
    confirm_delete_program: "Supprimer ce programme ?",
    valid: "Programme valide.",
    errors: "Erreurs",
    warnings: "Avertissements",
    copy_suffix: "copie",
    read_only_preset: "Preset intégré — dupliquez-le pour le modifier.",
    ramp: "Rampe",
    ramp_from: "Rampe depuis",
    ramp_hours: "sur (h)",
    ramp_hint: "Optionnel : les consignes passent linéairement de ces valeurs de départ aux consignes de la phase sur le nombre d'heures indiqué.",
    ramp_in_progress: "rampe en cours",
    ramp_to: "vers",
    category: "Catégorie",
    cat_charcuterie: "Charcuterie",
    cat_cheese: "Fromage",
    kind_charcuterie: "Séchoir à charcuterie",
    kind_cheese: "Cave d'affinage à fromages",
    presets: "Presets",
    my_programs: "Mes programmes",
    export: "Exporter",
    export_all: "Tout exporter",
    import: "Importer",
    imported: "importé(s)",
    skipped: "ignoré(s) (déjà existants)",
    import_overwrite: "Remplacer les programmes qui existent déjà ?",
    import_invalid: "Fichier de programmes invalide.",
    no_history: "Aucun lot terminé ou archivé pour l'instant.",
    select_to_compare: "Cochez des lots pour superposer leurs courbes de séchage.",
    final_loss: "Perte finale",
    duration: "Durée",
    mean_rate: "Vitesse moyenne",
    compare: "Comparer",
    error: "Erreur",
    started: "Programme démarré.",
    applied: "Appliqué.",
    version: "version",
    chamber: "Chambre",
  },
};

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

/** Build a DOM element: h("div", {class: "x", onclick: fn}, [children|string]). */
function h(tag, attrs, children) {
  const el = document.createElement(tag);
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value == null || value === false) continue;
      if (key === "class") el.className = value;
      else if (key === "style") el.style.cssText = value;
      else if (key.startsWith("on") && typeof value === "function") {
        el.addEventListener(key.slice(2), value);
      } else if (key === "checked" || key === "disabled" || key === "selected") {
        el[key] = Boolean(value);
      } else if (key === "value") el.value = value;
      else el.setAttribute(key, value === true ? "" : value);
    }
  }
  appendChildren(el, children);
  return el;
}

function appendChildren(el, children) {
  if (children == null) return;
  const list = Array.isArray(children) ? children : [children];
  for (const child of list) {
    if (child == null || child === false) continue;
    if (Array.isArray(child)) appendChildren(el, child);
    else el.appendChild(typeof child === "string" || typeof child === "number"
      ? document.createTextNode(String(child))
      : child);
  }
}

const SVG_NS = "http://www.w3.org/2000/svg";

/** SVG element builder (attributes only, strings or numbers). */
function s(tag, attrs, children) {
  const el = document.createElementNS(SVG_NS, tag);
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value == null) continue;
      el.setAttribute(key, String(value));
    }
  }
  if (children != null) {
    const list = Array.isArray(children) ? children : [children];
    for (const child of list) {
      if (child == null) continue;
      el.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
  }
  return el;
}

function clear(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
}

function lsGet(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (_err) {
    return null;
  }
}

function lsSet(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (_err) {
    /* private mode / blocked storage: ignore */
  }
}

function fmtNum(value, digits = 1, suffix = "") {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return `${Number(value).toFixed(digits)}${suffix}`;
}

function fmtDate(ts, locale) {
  if (ts == null) return "—";
  const d = new Date(ts * 1000);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(locale, { day: "2-digit", month: "short", year: "numeric" });
}

function fmtDateTime(ts, locale) {
  if (ts == null) return "—";
  const d = new Date(ts * 1000);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(locale, {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

/** Seconds → "3 d 4 h" using the localized short units. */
function fmtDuration(seconds, t) {
  if (seconds == null) return "—";
  const total = Math.max(0, Math.round(seconds / 3600));
  const days = Math.floor(total / 24);
  const hours = total % 24;
  if (days === 0) return `${hours} ${t("hour_short")}`;
  return `${days} ${t("day_short")} ${hours} ${t("hour_short")}`;
}

function hoursToText(hours, t) {
  if (hours == null) return "—";
  return fmtDuration(hours * 3600, t);
}

function hasRamp(phase) {
  return phase.ramp_hours != null && phase.ramp_hours > 0 && (phase.start_temp != null || phase.start_humidity != null);
}

/** Offer a JSON object as a file download (no server round-trip). */
function downloadJson(name, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = h("a", { href: url, download: name });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Let the user pick a .json file and resolve with its parsed content (null if cancelled). */
function pickJsonFile() {
  return new Promise((resolve, reject) => {
    const input = h("input", { type: "file", accept: "application/json,.json", style: "display:none" });
    input.onchange = () => {
      const file = input.files && input.files[0];
      input.remove();
      if (!file) return resolve(null);
      const reader = new FileReader();
      reader.onerror = () => reject(reader.error);
      reader.onload = () => {
        try { resolve(JSON.parse(String(reader.result))); } catch (err) { reject(err); }
      };
      reader.readAsText(file);
    };
    document.body.appendChild(input);
    input.click();
  });
}

function slugify(text) {
  return String(text || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

/** Local datetime-local input value ↔ epoch seconds. */
function toLocalInputValue(ts) {
  const d = new Date(ts * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalInputValue(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.getTime() / 1000;
}

/** Downscale an image file to ≤ maxPx on its longer side, JPEG q0.8, as a data URL. */
function downscaleImage(file, maxPx = 1600, quality = 0.8) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      try {
        const scale = Math.min(1, maxPx / Math.max(img.naturalWidth, img.naturalHeight));
        const w = Math.max(1, Math.round(img.naturalWidth * scale));
        const hgt = Math.max(1, Math.round(img.naturalHeight * scale));
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = hgt;
        canvas.getContext("2d").drawImage(img, 0, 0, w, hgt);
        resolve(canvas.toDataURL("image/jpeg", quality));
      } catch (err) {
        reject(err);
      } finally {
        URL.revokeObjectURL(url);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Cannot read image"));
    };
    img.src = url;
  });
}

/** Loss points (days since first sample, loss %) for a batch with samples. */
function lossPoints(batch) {
  const ref = batch.reference_weight;
  const samples = (batch.samples || []).filter((x) => x.weight != null);
  if (!ref || ref <= 0 || samples.length === 0) return [];
  const t0 = samples[0].timestamp;
  return samples.map((x) => ({
    t: x.timestamp,
    days: (x.timestamp - t0) / 86400,
    loss: ((ref - x.weight) / ref) * 100,
  }));
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const STYLES = `
  :host { display: block; height: 100%; background: var(--primary-background-color);
    color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif); }
  * { box-sizing: border-box; }
  .app-header { position: sticky; top: 0; z-index: 4; background: var(--app-header-background-color, var(--primary-color));
    color: var(--app-header-text-color, var(--text-primary-color, #fff)); }
  .toolbar { display: flex; align-items: center; gap: 8px; height: 56px; padding: 0 8px 0 4px; }
  .toolbar .title { font-size: 20px; font-weight: 400; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .toolbar select { max-width: 45vw; background: transparent; color: inherit; border: 1px solid currentColor;
    border-radius: 6px; padding: 4px 6px; font: inherit; font-size: 14px; }
  .toolbar select option { color: var(--primary-text-color); background: var(--card-background-color); }
  .toolbar button.icon-btn { flex: 0 0 auto; width: 34px; height: 34px; padding: 0; background: transparent; color: inherit;
    border: 1px solid currentColor; border-radius: 6px; font-size: 22px; line-height: 1;
    display: inline-flex; align-items: center; justify-content: center; }
  .tabs { display: flex; overflow-x: auto; scrollbar-width: none; }
  .tabs::-webkit-scrollbar { display: none; }
  .tab { flex: 1 0 auto; min-width: 90px; text-align: center; padding: 12px 16px; cursor: pointer; opacity: .75;
    border-bottom: 2px solid transparent; font-size: 14px; text-transform: uppercase; letter-spacing: .5px;
    background: none; border-top: none; border-left: none; border-right: none; color: inherit; font-family: inherit; }
  .tab.active { opacity: 1; border-bottom-color: currentColor; }
  .content { max-width: 1100px; margin: 0 auto; padding: 16px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
  .card { background: var(--card-background-color); border-radius: var(--ha-card-border-radius, 12px);
    box-shadow: var(--ha-card-box-shadow, none); border: 1px solid var(--ha-card-border-color, var(--divider-color));
    padding: 16px; min-width: 0; }
  .card.span { grid-column: 1 / -1; }
  .card h2 { margin: 0 0 12px; font-size: 1.1em; font-weight: 500; display: flex; align-items: center; gap: 8px; }
  .card h2 .grow { flex: 1; }
  .muted { color: var(--secondary-text-color); }
  .small { font-size: .85em; }
  .empty { color: var(--secondary-text-color); padding: 24px 0; text-align: center; }
  .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
  .row.between { justify-content: space-between; }
  .kv { display: flex; gap: 14px; flex-wrap: wrap; font-size: .9em; color: var(--secondary-text-color); }
  .kv b { color: var(--primary-text-color); font-weight: 500; }
  button, .btn { font: inherit; font-size: 14px; padding: 8px 14px; border: none; border-radius: 8px; cursor: pointer;
    background: var(--primary-color); color: var(--text-primary-color, #fff); white-space: nowrap; }
  button:hover { opacity: .9; }
  button:disabled { opacity: .45; cursor: default; }
  button.outline { background: transparent; color: var(--primary-color); border: 1px solid var(--primary-color); }
  button.danger { background: var(--error-color, #db4437); }
  button.ghost { background: transparent; color: var(--primary-text-color); border: 1px solid var(--divider-color); }
  button.sm { padding: 4px 10px; font-size: 13px; }
  input, select, textarea { font: inherit; font-size: 14px; padding: 8px; border-radius: 8px;
    border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color);
    max-width: 100%; }
  input[type=number] { width: 110px; }
  input[type=checkbox] { width: 18px; height: 18px; padding: 0; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: .85em; color: var(--secondary-text-color); }
  label.inline { flex-direction: row; align-items: center; gap: 8px; color: var(--primary-text-color); font-size: 14px; }
  .form { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; }
  .gauges { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .gauge { text-align: center; min-width: 0; }
  .gauge svg { width: 100%; max-width: 160px; height: auto; }
  .gauge .arc-bg { fill: none; stroke: var(--divider-color); stroke-width: 10; stroke-linecap: round; }
  .gauge .arc-val { fill: none; stroke: var(--primary-color); stroke-width: 10; stroke-linecap: round; }
  .gauge .tick { stroke: var(--error-color, #db4437); stroke-width: 3; }
  .gauge .val { fill: var(--primary-text-color); font-size: 22px; font-weight: 500; }
  .gauge .unit { fill: var(--secondary-text-color); font-size: 11px; }
  .gauge .label { font-size: .85em; color: var(--secondary-text-color); margin-top: 2px; }
  .chips { display: flex; gap: 8px; flex-wrap: wrap; }
  .chip { padding: 4px 10px; border-radius: 14px; font-size: .85em; border: 1px solid var(--divider-color);
    color: var(--secondary-text-color); }
  .chip.on { border-color: var(--success-color, #43a047); color: var(--success-color, #43a047); }
  .chip.unknown { opacity: .6; font-style: italic; }
  .badge { font-size: .7em; color: var(--primary-color); border: 1px solid var(--primary-color); border-radius: 8px;
    padding: 1px 6px; vertical-align: middle; white-space: nowrap; }
  .badge.status-completed { color: var(--success-color, #43a047); border-color: var(--success-color, #43a047); }
  .badge.status-archived { color: var(--disabled-text-color, #9e9e9e); border-color: var(--disabled-text-color, #9e9e9e); }
  .badge.due { color: var(--warning-color, #ffa600); border-color: var(--warning-color, #ffa600); }
  .badge.status-active { color: var(--info-color, var(--primary-color)); border-color: var(--info-color, var(--primary-color)); }
  .timeline { display: flex; gap: 4px; margin: 8px 0; }
  .tl-phase { flex: 1 1 0; min-width: 40px; padding: 6px 8px; border-radius: 6px; background: var(--secondary-background-color, var(--divider-color));
    font-size: .8em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; opacity: .7; }
  .tl-phase.done { opacity: .5; }
  .tl-phase.current { opacity: 1; background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .alert { border-left: 4px solid var(--warning-color, #ffa600); padding: 8px 12px; margin: 6px 0;
    background: var(--secondary-background-color, transparent); border-radius: 6px; }
  .alert.critical, .alert.error { border-left-color: var(--error-color, #db4437); }
  .alert .key { font-weight: 500; }
  table { width: 100%; border-collapse: collapse; font-size: .9em; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--divider-color); vertical-align: middle; }
  th { color: var(--secondary-text-color); font-weight: 500; }
  .table-wrap { overflow-x: auto; }
  .batch-card { cursor: pointer; }
  .batch-card:hover { border-color: var(--primary-color); }
  .bar { height: 8px; background: var(--divider-color); border-radius: 4px; overflow: hidden; margin: 8px 0; }
  .bar-fill { height: 100%; background: var(--primary-color); transition: width .3s; }
  .bar-fill.done { background: var(--success-color, #43a047); }
  .thumb { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; background: var(--divider-color); display: block; }
  .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 8px; }
  .gallery figure { margin: 0; }
  .gallery img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 8px; background: var(--divider-color); display: block; }
  .gallery figcaption { font-size: .75em; color: var(--secondary-text-color); margin-top: 2px; }
  .chart { width: 100%; height: auto; }
  .chart .axis { stroke: var(--divider-color); stroke-width: 1; }
  .chart .grid { stroke: var(--divider-color); stroke-width: 1; stroke-dasharray: 2 4; }
  .chart .lbl { fill: var(--secondary-text-color); font-size: 10px; }
  .chart .line { fill: none; stroke: var(--primary-color); stroke-width: 2; }
  .chart .pt { fill: var(--primary-color); }
  .chart .target { stroke: var(--error-color, #db4437); stroke-dasharray: 5 4; stroke-width: 1.5; }
  .chart .proj { fill: none; stroke: var(--primary-color); stroke-dasharray: 4 4; stroke-width: 1.5; opacity: .7; }
  .legend { display: flex; gap: 12px; flex-wrap: wrap; font-size: .85em; }
  .legend .sw { display: inline-block; width: 12px; height: 12px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
  .msg { padding: 8px 12px; border-radius: 6px; margin: 8px 0; font-size: .9em; }
  .msg.error { background: color-mix(in srgb, var(--error-color, #db4437) 15%, transparent); color: var(--error-color, #db4437); }
  .msg.warning { background: color-mix(in srgb, var(--warning-color, #ffa600) 15%, transparent); }
  .msg.ok { background: color-mix(in srgb, var(--success-color, #43a047) 15%, transparent); color: var(--success-color, #43a047); }
  .phase-row { display: grid; grid-template-columns: 1.6fr .7fr .7fr 1fr .7fr .7fr auto auto; gap: 6px; align-items: center;
    padding: 6px 0; border-bottom: 1px solid var(--divider-color); }
  .phase-row input, .phase-row select { width: 100%; min-width: 0; }
  .phase-row .ctl { display: flex; gap: 2px; }
  .phase-head { font-size: .75em; color: var(--secondary-text-color); border-bottom: none; padding-bottom: 0; }
  .phase-ramp { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; padding: 0 0 8px 12px; font-size: .85em;
    color: var(--secondary-text-color); border-bottom: 1px solid var(--divider-color); margin-bottom: 2px; }
  .phase-ramp input { width: 72px; }
  .phase-ramp .arrow { opacity: .7; }
  .tl-phase.ramp::before { content: "↘ "; opacity: .8; }
  @media (max-width: 720px) {
    .phase-row { grid-template-columns: 1fr 1fr 1fr; }
    .phase-head { display: none; }
    .gauges { grid-template-columns: repeat(3, 1fr); }
    .gauge .val { font-size: 18px; }
  }
  .toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); z-index: 10;
    background: var(--primary-text-color); color: var(--primary-background-color); padding: 10px 16px;
    border-radius: 8px; font-size: 14px; max-width: calc(100vw - 32px); box-shadow: 0 2px 8px rgba(0,0,0,.3);
    opacity: 0; pointer-events: none; transition: opacity .2s; }
  .toast.show { opacity: 1; }
  .toast.error { background: var(--error-color, #db4437); color: #fff; }
  .version { text-align: center; padding: 16px; font-size: .75em; color: var(--secondary-text-color); }
`;

// ---------------------------------------------------------------------------
// The panel
// ---------------------------------------------------------------------------

class CuringChamberPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._narrow = false;
    this._panel = null;
    this._lang = "en";
    this._chambers = null; // null until loaded
    this._entryId = lsGet(LS_CHAMBER);
    this._tab = TABS.includes(lsGet(LS_TAB)) ? lsGet(LS_TAB) : "chamber";
    this._state = null;
    this._programs = [];
    this._batches = [];
    this._showArchived = false;
    this._detailBatchId = null;
    this._newBatch = false;
    this._editing = null; // {program, isNew}
    this._compareIds = new Set();
    this._unsub = null;
    this._unsubChambers = null;
    this._vanishedTimer = null;
    this._signed = new Map();
    this._initialised = false;
    this._loadSeq = 0;
    this.attachShadow({ mode: "open" });
    this._buildSkeleton();
  }

  // -- HA properties --------------------------------------------------------

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    const lang = hass && hass.language && hass.language.toLowerCase().startsWith("fr") ? "fr" : "en";
    if (lang !== this._lang) {
      this._lang = lang;
      this._renderHeader();
      this._renderTab();
    }
    if (first && this.isConnected) this._init();
    else if (this._menuButton) this._menuButton.hass = hass;
    if (this._addButton) this._addButton.hidden = !this._isAdmin;
    // Cheap refresh: switch toggles depend on entity states.
    if (!first && this._tab === "chamber") this._syncSwitches();
  }

  get hass() {
    return this._hass;
  }

  set narrow(value) {
    this._narrow = Boolean(value);
    if (this._menuButton) this._menuButton.narrow = this._narrow;
  }

  set route(_value) {
    /* no sub-routing */
  }

  set panel(value) {
    this._panel = value;
    this._renderVersion();
  }

  connectedCallback() {
    if (this._hass && !this._initialised) this._init();
  }

  disconnectedCallback() {
    this._unsubscribe();
    this._unsubscribeChambers();
    this._clearVanished();
    // Forget the list so the next connection reloads the selected chamber.
    this._chambers = null;
    this._initialised = false;
  }

  // -- i18n -------------------------------------------------------------------

  _t(key) {
    const table = STR[this._lang] || STR.en;
    return table[key] != null ? table[key] : STR.en[key] != null ? STR.en[key] : key;
  }

  get _locale() {
    return (this._hass && this._hass.locale && this._hass.locale.language) || this._hass?.language || undefined;
  }

  // -- Skeleton ---------------------------------------------------------------

  _buildSkeleton() {
    const root = this.shadowRoot;
    root.appendChild(h("style", null, STYLES));
    this._menuButton = document.createElement("ha-menu-button");
    this._titleEl = h("div", { class: "title" });
    this._chamberSelect = h("select", {
      onchange: (ev) => this._selectChamber(ev.target.value),
      "aria-label": "chamber",
    });
    this._chamberSelect.hidden = true;
    this._addButton = h("button", {
      class: "icon-btn",
      type: "button",
      onclick: () => this._addChamber(),
    }, "+");
    this._addButton.hidden = true;
    this._tabsEl = h("div", { class: "tabs", role: "tablist" });
    this._header = h("div", { class: "app-header" }, [
      h("div", { class: "toolbar" }, [this._menuButton, this._titleEl, this._chamberSelect, this._addButton]),
      this._tabsEl,
    ]);
    this._content = h("div", { class: "content" });
    this._versionEl = h("div", { class: "version" });
    this._toast = h("div", { class: "toast" });
    root.appendChild(this._header);
    root.appendChild(this._content);
    root.appendChild(this._versionEl);
    root.appendChild(this._toast);
    this._renderHeader();
  }

  _renderHeader() {
    const t = (k) => this._t(k);
    this._titleEl.textContent = t("title");
    if (this._addButton) {
      this._addButton.title = t("add_chamber");
      this._addButton.setAttribute("aria-label", t("add_chamber"));
    }
    clear(this._tabsEl);
    for (const tab of TABS) {
      this._tabsEl.appendChild(
        h("button", {
          class: `tab${tab === this._tab ? " active" : ""}`,
          role: "tab",
          onclick: () => this._setTab(tab),
        }, t(`tab_${tab}`)),
      );
    }
  }

  _renderVersion() {
    const version = this._panel && this._panel.config && this._panel.config.version;
    this._versionEl.textContent = version ? `Curing Chamber · ${this._t("version")} ${version}` : "";
  }

  _setTab(tab) {
    this._tab = tab;
    lsSet(LS_TAB, tab);
    this._renderHeader();
    this._renderTab();
  }

  // -- Toast ------------------------------------------------------------------

  _showToast(message, isError = false) {
    this._toast.textContent = message;
    this._toast.className = `toast show${isError ? " error" : ""}`;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this._toast.className = "toast";
    }, isError ? 6000 : 3000);
  }

  _showError(err) {
    const msg = err && (err.message || err.code) ? err.message || err.code : String(err);
    this._showToast(`${this._t("error")}: ${msg}`, true);
  }

  // -- Backend access ---------------------------------------------------------

  async _ws(type, params) {
    return this._hass.callWS({ type, entry_id: this._entryId, ...(params || {}) });
  }

  async _service(service, data, domain = "curing_chamber") {
    const payload = { ...(data || {}) };
    if (domain === "curing_chamber") {
      const chamber = this._chamber;
      if (chamber && chamber.device_id) payload.device_id = chamber.device_id;
    }
    try {
      await this._hass.callService(domain, service, payload);
      return true;
    } catch (err) {
      this._showError(err);
      return false;
    }
  }

  get _chamber() {
    return (this._chambers || []).find((c) => c.entry_id === this._entryId) || null;
  }

  get _isAdmin() {
    return Boolean(this._hass && this._hass.user && this._hass.user.is_admin);
  }

  async _init() {
    this._initialised = true;
    try {
      const unsub = await this._hass.connection.subscribeMessage(
        (chambers) => this._onChambers(chambers),
        { type: "curing_chamber/subscribe_chambers" },
      );
      if (!this.isConnected) unsub();
      else this._unsubChambers = unsub;
    } catch (err) {
      this._onChambers([]);
      this._showError(err);
    }
  }

  _unsubscribeChambers() {
    if (this._unsubChambers) {
      try {
        this._unsubChambers();
      } catch (_err) {
        /* connection may already be gone */
      }
      this._unsubChambers = null;
    }
  }

  _clearVanished() {
    if (this._vanishedTimer != null) {
      clearTimeout(this._vanishedTimer);
      this._vanishedTimer = null;
    }
  }

  /** The backend pushed the chamber list (on subscribe, then on every (un)load). */
  _onChambers(chambers) {
    const first = this._chambers === null;
    this._chambers = Array.isArray(chambers) ? chambers : [];
    const current = this._entryId;
    const present = Boolean(current) && this._chambers.some((c) => c.entry_id === current);
    if (present) {
      const reappeared = this._vanishedTimer != null;
      this._clearVanished();
      this._renderChamberSelect();
      if (first || reappeared) this._switchTo(current);
      else this._renderTab(); // a rename only
    } else if (first || !current) {
      this._clearVanished();
      this._switchTo(this._chambers.length ? this._chambers[0].entry_id : null);
    } else if (this._vanishedTimer == null) {
      // The selected chamber vanished — most likely a reload after an options
      // change. Hold the selection briefly so it comes back without switching.
      this._unsubscribe();
      this._vanishedTimer = setTimeout(() => {
        this._vanishedTimer = null;
        const list = this._chambers || [];
        if (!list.some((c) => c.entry_id === this._entryId)) {
          this._switchTo(list.length ? list[0].entry_id : null);
        }
      }, 4000);
    }
  }

  _renderChamberSelect() {
    const sel = this._chamberSelect;
    clear(sel);
    const chambers = this._chambers || [];
    sel.hidden = chambers.length < 2;
    for (const c of chambers) {
      sel.appendChild(h("option", { value: c.entry_id, selected: c.entry_id === this._entryId }, c.name));
    }
    this._titleEl.textContent =
      chambers.length === 1 ? `${this._t("title")} · ${chambers[0].name}` : this._t("title");
    if (this._addButton) this._addButton.hidden = !this._isAdmin;
  }

  async _selectChamber(entryId) {
    if (entryId === this._entryId) return;
    this._clearVanished();
    await this._switchTo(entryId);
  }

  /** Make `entryId` (or none) the displayed chamber and (re)load its data. */
  async _switchTo(entryId) {
    this._entryId = entryId || null;
    if (entryId) lsSet(LS_CHAMBER, entryId);
    this._state = null;
    this._batches = [];
    this._programs = [];
    this._detailBatchId = null;
    this._newBatch = false;
    this._editing = null;
    this._compareIds = new Set();
    this._renderChamberSelect();
    this._renderTab();
    if (this._entryId) await this._loadChamber();
    else {
      this._loadSeq++;
      this._unsubscribe();
    }
  }

  /** Open Home Assistant's "add integration" flow for this domain (admins only). */
  _addChamber() {
    const path = "/config/integrations/dashboard/add?domain=curing_chamber";
    history.pushState(null, "", path);
    window.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true, detail: { replace: false } }));
  }

  async _loadChamber() {
    const seq = ++this._loadSeq;
    this._unsubscribe();
    try {
      this._state = await this._ws("curing_chamber/state");
    } catch (err) {
      this._showError(err);
    }
    if (seq !== this._loadSeq) return;
    this._renderTab();
    await Promise.all([this._loadPrograms(), this._loadBatches()]);
    if (seq !== this._loadSeq) return;
    this._renderTab();
    await this._subscribe();
  }

  async _subscribe() {
    if (!this._hass || !this._entryId) return;
    const entryId = this._entryId;
    try {
      const unsub = await this._hass.connection.subscribeMessage(
        (state) => this._onState(state, entryId),
        { type: "curing_chamber/subscribe", entry_id: entryId },
      );
      if (entryId !== this._entryId || !this.isConnected) {
        unsub();
      } else {
        this._unsub = unsub;
      }
    } catch (err) {
      this._showError(err);
    }
  }

  _unsubscribe() {
    if (this._unsub) {
      try {
        this._unsub();
      } catch (_err) {
        /* connection may already be gone */
      }
      this._unsub = null;
    }
  }

  _onState(state, entryId) {
    if (entryId !== this._entryId || !state) return;
    this._state = state;
    // Light batch summaries ride along: refresh the ones we hold (keep samples).
    if (Array.isArray(state.batches)) {
      const held = new Map(this._batches.map((b) => [b.id, b]));
      let stale = false;
      for (const light of state.batches) {
        const full = held.get(light.id);
        if (!full || full.sample_count !== light.sample_count || full.status !== light.status) {
          stale = true;
        }
        if (full) Object.assign(full, light, { samples: full.samples });
      }
      // A batch or weigh-in added outside the panel (service, card, automation):
      // reload the full list with its weigh-in history.
      if (stale && !this._reloadingBatches) {
        this._reloadingBatches = true;
        this._loadBatches().then(() => {
          this._reloadingBatches = false;
          if (this._tab !== "chamber" && !this._detailBatchId && !this._newBatch) this._renderTab();
        });
      }
    }
    if (this._tab === "chamber") this._renderTab();
    else if (this._tab === "batches" && !this._detailBatchId && !this._newBatch) this._renderTab();
  }

  async _loadPrograms() {
    if (!this._entryId) return;
    try {
      this._programs = await this._ws("curing_chamber/programs");
    } catch (err) {
      this._showError(err);
    }
  }

  async _loadBatches() {
    if (!this._entryId) return;
    try {
      this._batches = await this._ws("curing_chamber/batches", {
        include_archived: true,
        with_samples: true,
      });
    } catch (err) {
      this._showError(err);
    }
  }

  /** Signed path for an authenticated photo url (cached, re-signed when stale). */
  async _signedUrl(url) {
    const cached = this._signed.get(url);
    if (cached && Date.now() - cached.ts < SIGN_TTL_MS) return cached.path;
    const result = await this._hass.callWS({ type: "auth/sign_path", path: url, expires: 3600 });
    this._signed.set(url, { path: result.path, ts: Date.now() });
    return result.path;
  }

  _photoImg(url, cls, alt) {
    const img = h("img", { class: cls, alt: alt || "", loading: "lazy" });
    this._signedUrl(url)
      .then((path) => {
        img.src = path;
      })
      .catch(() => {
        img.alt = "✕";
      });
    img.addEventListener("error", () => {
      // Signature expired on a cached entry: sign again once.
      if (img.dataset.retried) return;
      img.dataset.retried = "1";
      this._signed.delete(url);
      this._signedUrl(url).then((path) => {
        img.src = path;
      }).catch(() => {});
    });
    return img;
  }

  // -- Tab dispatcher -----------------------------------------------------------

  _renderTab() {
    const c = this._content;
    clear(c);
    if (this._chambers === null) {
      c.appendChild(h("div", { class: "empty" }, this._t("loading")));
      return;
    }
    if (!this._chambers.length || !this._entryId) {
      c.appendChild(h("div", { class: "empty" }, [
        h("p", null, this._t("no_chambers")),
        this._isAdmin
          ? h("button", { type: "button", onclick: () => this._addChamber() }, this._t("add_chamber"))
          : h("p", null, this._t("no_chambers_hint")),
      ]));
      return;
    }
    switch (this._tab) {
      case "batches":
        c.appendChild(this._viewBatches());
        break;
      case "programs":
        c.appendChild(this._viewPrograms());
        break;
      case "history":
        c.appendChild(this._viewHistory());
        break;
      default:
        c.appendChild(this._viewChamber());
    }
  }

  // ===========================================================================
  // View 1 — Chamber
  // ===========================================================================

  _viewChamber() {
    const t = (k) => this._t(k);
    const st = this._state;
    if (!st) return h("div", { class: "empty" }, t("loading"));
    const grid = h("div", { class: "grid" });

    // Gauges ----------------------------------------------------------------
    const gaugeCard = h("div", { class: "card span" }, [
      h("h2", null, [h("span", { class: "grow" }, this._chamber ? this._chamber.name : t("chamber")),
        h("span", { class: "badge" }, st.summary || "")]),
      h("div", { class: "gauges" }, [
        this._gauge(st.temp, st.target_temp, -5, 30, "°C", t("temperature")),
        this._gauge(st.humidity, st.target_humidity, 40, 100, "%", t("humidity")),
        this._gauge(st.dew_point, null, -5, 25, "°C", t("dew_point")),
        st.has_core_probe ? this._gauge(st.core_temp, null, -5, 30, "°C", t("core_temp")) : null,
      ]),
      h("div", { class: "kv", style: "margin-top:8px" }, [
        st.absolute_humidity != null && h("span", null, [`${t("humidity")} abs. `, h("b", null, fmtNum(st.absolute_humidity, 1, " g/m³"))]),
        st.core_delta != null && h("span", null, [`${t("core_delta")} `, h("b", null, fmtNum(st.core_delta, 1, " °C"))]),
        st.temp_divergence != null && h("span", null, ["ΔT ", h("b", null, fmtNum(st.temp_divergence, 1, " °C"))]),
        st.humidity_divergence != null && h("span", null, ["ΔRH ", h("b", null, fmtNum(st.humidity_divergence, 1, " %"))]),
      ]),
    ]);
    grid.appendChild(gaugeCard);

    // Actuators + weight --------------------------------------------------------
    const actuators = st.actuators || {};
    const chips = h("div", { class: "chips" });
    const keys = Object.keys(actuators);
    if (!keys.length) chips.appendChild(h("span", { class: "muted small" }, "—"));
    for (const key of keys) {
      const val = actuators[key];
      const cls = val === true ? "chip on" : val === false ? "chip" : "chip unknown";
      const hours = st.counters && st.counters[key] != null ? ` · ${fmtNum(st.counters[key], 0)} h` : "";
      chips.appendChild(h("span", { class: cls }, `${key}: ${val === true ? t("on") : val === false ? t("off") : t("unknown")}${hours}`));
    }
    const sourceKey = st.weight_source ? `source_${st.weight_source}` : null;
    grid.appendChild(h("div", { class: "card" }, [
      h("h2", null, t("actuators")),
      chips,
      h("h2", { style: "margin-top:16px" }, t("weight")),
      h("div", { class: "kv" }, [
        h("span", null, [`${t("weight")} `, h("b", null, fmtNum(st.weight, 0)), sourceKey ? h("span", { class: "small" }, ` (${t(sourceKey)})`) : null]),
        h("span", null, [`${t("reference_weight")} `, h("b", null, fmtNum(st.reference_weight, 0))]),
        h("span", null, [`${t("weight_loss")} `, h("b", null, fmtNum(st.weight_loss_pct, 1, " %"))]),
        h("span", null, [`${t("drying_rate")} `, h("b", null, fmtNum(st.drying_rate, 2, " %/d"))]),
      ]),
      h("div", { class: "row", style: "margin-top:10px" }, [
        h("button", { class: "outline sm", onclick: () => this._service("set_reference_weight", {}).then((ok) => ok && this._showToast(t("applied"))) }, t("set_reference_weight")),
      ]),
    ]));

    // Program -----------------------------------------------------------------
    grid.appendChild(this._programCard(st));

    // Manual targets + toggles ---------------------------------------------------
    const tempIn = h("input", { type: "number", step: "0.5", value: st.target_temp != null ? st.target_temp : "" });
    const humIn = h("input", { type: "number", step: "1", value: st.target_humidity != null ? st.target_humidity : "" });
    const regSwitch = h("input", { type: "checkbox", onchange: (ev) => this._toggleSwitch(st.entities && st.entities.regulation_switch, ev.target.checked) });
    const maintSwitch = h("input", { type: "checkbox", onchange: (ev) => this._toggleSwitch(st.entities && st.entities.maintenance_switch, ev.target.checked) });
    this._regSwitch = regSwitch;
    this._maintSwitch = maintSwitch;
    grid.appendChild(h("div", { class: "card" }, [
      h("h2", null, t("manual_targets")),
      h("div", { class: "form" }, [
        h("label", null, [t("temperature"), tempIn]),
        h("label", null, [t("humidity"), humIn]),
        h("button", {
          onclick: async () => {
            const data = {};
            if (tempIn.value !== "") data.temperature = parseFloat(tempIn.value);
            if (humIn.value !== "") data.humidity = parseFloat(humIn.value);
            if (await this._service("set_targets", data)) this._showToast(t("applied"));
          },
        }, t("apply")),
      ]),
      h("div", { class: "row", style: "margin-top:16px" }, [
        h("label", { class: "inline" }, [regSwitch, t("regulation")]),
        h("label", { class: "inline" }, [maintSwitch, t("maintenance")]),
      ]),
    ]));
    this._syncSwitches();

    // Alerts ------------------------------------------------------------------
    const alerts = st.active_alerts || [];
    const alertCard = h("div", { class: "card" }, [
      h("h2", null, [h("span", { class: "grow" }, t("alerts")),
        alerts.length ? h("button", { class: "sm outline", onclick: () => this._service("acknowledge_alert", {}) }, t("acknowledge")) : null]),
    ]);
    if (!alerts.length) alertCard.appendChild(h("div", { class: "muted small" }, t("no_alerts")));
    for (const key of alerts) {
      const det = (st.alert_details && st.alert_details[key]) || {};
      const extras = Object.entries(det)
        .filter(([k]) => k !== "level" && k !== "manual_action")
        .map(([k, v]) => `${k}: ${typeof v === "number" ? fmtNum(v, 1) : v}`)
        .join(" · ");
      alertCard.appendChild(h("div", { class: `alert ${det.level || ""}` }, [
        h("div", { class: "key" }, key.replace(/_/g, " ")),
        det.manual_action && det.manual_action !== "none" ? h("div", { class: "small" }, `→ ${det.manual_action.replace(/_/g, " ")}`) : null,
        extras ? h("div", { class: "small muted" }, extras) : null,
      ]));
    }
    grid.appendChild(alertCard);

    // Decisions -----------------------------------------------------------------
    const decisions = st.decisions || [];
    const decCard = h("div", { class: "card" }, [h("h2", null, t("decisions"))]);
    if (!decisions.length) decCard.appendChild(h("div", { class: "muted small" }, t("no_decisions")));
    else {
      const tbl = h("table", null, [h("tbody", null, decisions.map((d) => h("tr", null, [
        h("td", null, d.actuator),
        h("td", null, d.desired ? t("wants_on") : t("wants_off")),
        h("td", { class: "muted" }, [d.reason || "", d.blocked_by ? ` — ${t("blocked_by")} ${d.blocked_by}` : ""]),
      ])))]);
      decCard.appendChild(h("div", { class: "table-wrap" }, tbl));
    }
    grid.appendChild(decCard);
    return grid;
  }

  _syncSwitches() {
    const st = this._state;
    if (!st || !this._hass) return;
    const ent = st.entities || {};
    const read = (id) => {
      const obj = id && this._hass.states[id];
      return obj ? obj.state === "on" : null;
    };
    const reg = read(ent.regulation_switch);
    const maint = read(ent.maintenance_switch);
    if (this._regSwitch) this._regSwitch.checked = reg != null ? reg : Boolean(st.regulation_enabled);
    if (this._maintSwitch) this._maintSwitch.checked = maint != null ? maint : Boolean(st.maintenance);
  }

  _toggleSwitch(entityId, on) {
    if (!entityId) return;
    this._service(on ? "turn_on" : "turn_off", { entity_id: entityId }, "switch");
  }

  /** SVG arc gauge from -120° to +120°. */
  _gauge(value, target, min, max, unit, label) {
    const W = 160;
    const H = 110;
    const cx = 80;
    const cy = 85;
    const r = 62;
    const toAngle = (v) => {
      const clamped = Math.max(min, Math.min(max, v));
      return -120 + ((clamped - min) / (max - min)) * 240;
    };
    const point = (deg, radius) => {
      const rad = ((deg - 90) * Math.PI) / 180;
      return [cx + radius * Math.cos(rad), cy + radius * Math.sin(rad)];
    };
    const arc = (from, to) => {
      const [x1, y1] = point(from, r);
      const [x2, y2] = point(to, r);
      const large = to - from > 180 ? 1 : 0;
      return `M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r} ${r} 0 ${large} 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`;
    };
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
    svg.appendChild(s("path", { class: "arc-bg", d: arc(-120, 120) }));
    if (value != null) {
      const a = toAngle(value);
      if (a > -119.5) svg.appendChild(s("path", { class: "arc-val", d: arc(-120, a) }));
    }
    if (target != null) {
      const a = toAngle(target);
      const [x1, y1] = point(a, r - 9);
      const [x2, y2] = point(a, r + 9);
      svg.appendChild(s("line", { class: "tick", x1, y1, x2, y2 }));
    }
    svg.appendChild(s("text", { class: "val", x: cx, y: cy - 2, "text-anchor": "middle" }, fmtNum(value, 1)));
    svg.appendChild(s("text", { class: "unit", x: cx, y: cy + 14, "text-anchor": "middle" },
      target != null ? `${unit} · ${this._t("target")} ${fmtNum(target, 1)}` : unit));
    return h("div", { class: "gauge" }, [svg, h("div", { class: "label" }, label)]);
  }

  _programCard(st) {
    const t = (k) => this._t(k);
    const prog = st.program || { status: "idle", phases: [] };
    const statusKey = `status_${prog.status || "idle"}`;
    const running = prog.status === "running";
    const paused = prog.status === "paused";
    const idle = !running && !paused;

    const picker = h("select", null, [
      h("option", { value: "" }, t("pick_program")),
      ...this._programs.map((p) => h("option", { value: p.id }, p.name + (p.builtin ? ` (${t("preset")})` : ""))),
    ]);
    const startBtn = h("button", {
      onclick: async () => {
        if (!picker.value) return;
        if (await this._service("start_program", { program_id: picker.value })) this._showToast(t("started"));
      },
    }, t("start"));

    const card = h("div", { class: "card" }, [
      h("h2", null, [h("span", { class: "grow" }, t("program")), h("span", { class: "badge" }, t(statusKey))]),
    ]);
    if (!idle) {
      card.appendChild(h("div", null, [
        h("div", null, [h("b", null, prog.program_name || prog.program_id || ""), " "]),
        h("div", { class: "muted small" }, [
          `${t("phase")} ${(prog.phase_index || 0) + 1}/${(prog.phases || []).length}: ${prog.phase_name || "—"}`,
          prog.phase_remaining != null ? ` · ${fmtDuration(prog.phase_remaining, t)} ${t("remaining")}` : "",
        ]),
        prog.next_reminder ? h("div", { class: "muted small" }, [
          `⏰ ${t("next_reminder")}: `,
          h("b", null, JOURNAL_KINDS.includes(prog.next_reminder.kind) ? t(`kind_${prog.next_reminder.kind}`) : prog.next_reminder.kind),
          prog.next_reminder.note ? ` (${prog.next_reminder.note})` : "",
          ` · ${fmtDuration(prog.next_reminder.due_in, t)}`,
        ]) : null,
        prog.ramp_remaining != null && prog.ramp_remaining > 0 ? h("div", { class: "muted small" }, [
          `↘ ${t("ramp_in_progress")} ${t("ramp_to")} `,
          h("b", null, [prog.phase_target_temp != null ? `${prog.phase_target_temp} °C` : null,
            prog.phase_target_temp != null && prog.phase_target_humidity != null ? " / " : null,
            prog.phase_target_humidity != null ? `${prog.phase_target_humidity} %` : null]),
          ` · ${fmtDuration(prog.ramp_remaining, t)} ${t("remaining")}`,
        ]) : null,
      ]));
      card.appendChild(this._timeline(prog.phases || [], prog.phase_index || 0));
      card.appendChild(h("div", { class: "row", style: "margin-top:8px" }, [
        running ? h("button", { class: "outline sm", onclick: () => this._service("pause_program", {}) }, t("pause")) : null,
        paused ? h("button", { class: "outline sm", onclick: () => this._service("resume_program", {}) }, t("resume")) : null,
        h("button", { class: "outline sm", onclick: () => this._service("next_phase", {}) }, t("next_phase")),
        h("button", { class: "danger sm", onclick: () => this._service("stop_program", {}) }, t("stop")),
      ]));
    }
    card.appendChild(h("div", { class: "row", style: "margin-top:12px" }, [picker, startBtn]));
    return card;
  }

  _timeline(phases, currentIndex) {
    const t = (k) => this._t(k);
    const wrap = h("div", { class: "timeline" });
    const total = phases.reduce((acc, p) => acc + (p.duration_hours || 24), 0) || 1;
    phases.forEach((p, i) => {
      const ramp = hasRamp(p);
      const cls = (i < currentIndex ? "tl-phase done" : i === currentIndex ? "tl-phase current" : "tl-phase") + (ramp ? " ramp" : "");
      const grow = Math.max(0.5, ((p.duration_hours || 24) / total) * phases.length);
      const detail = [p.target_temp != null ? `${p.target_temp}°` : null, p.target_humidity != null ? `${p.target_humidity}%` : null]
        .filter(Boolean).join(" / ") + (ramp ? ` (${t("ramp").toLowerCase()} ${p.ramp_hours} h)` : "");
      const end = p.end_kind === "weight_loss" ? `-${p.weight_loss_pct || "?"}%`
        : p.end_kind === "core_temp" ? `→ ${p.core_temp_target != null ? p.core_temp_target : "?"}°`
        : p.end_kind === "manual" ? t("end_manual") : hoursToText(p.duration_hours, t);
      wrap.appendChild(h("div", { class: cls, style: `flex-grow:${grow.toFixed(2)}`, title: `${p.name} · ${detail} · ${end}` },
        `${p.name} · ${end}`));
    });
    return wrap;
  }

  // ===========================================================================
  // View 2 — Batches
  // ===========================================================================

  _viewBatches() {
    const t = (k) => this._t(k);
    if (this._newBatch) return this._newBatchForm();
    if (this._detailBatchId) {
      const batch = this._batches.find((b) => b.id === this._detailBatchId);
      if (batch) return this._batchDetail(batch);
      this._detailBatchId = null;
    }
    const refId = this._state ? this._state.reference_batch_id : null;
    const wrap = h("div");
    const archivedToggle = h("input", { type: "checkbox", checked: this._showArchived, onchange: (ev) => { this._showArchived = ev.target.checked; this._renderTab(); } });
    wrap.appendChild(h("div", { class: "row between", style: "margin-bottom:12px" }, [
      h("label", { class: "inline" }, [archivedToggle, t("show_archived")]),
      h("button", { onclick: () => { this._newBatch = true; this._renderTab(); } }, `+ ${t("new_batch")}`),
    ]));
    const list = this._batches.filter((b) => this._showArchived || b.status !== "archived");
    if (!list.length) {
      wrap.appendChild(h("div", { class: "empty" }, t("no_batches")));
      return wrap;
    }
    const grid = h("div", { class: "grid" });
    for (const b of list) grid.appendChild(this._batchCard(b, b.id === refId));
    wrap.appendChild(grid);
    return wrap;
  }

  _batchCard(b, isRef) {
    const t = (k) => this._t(k);
    const loss = b.loss_pct;
    const target = b.target_loss_pct;
    const pct = loss == null ? 0 : Math.max(0, Math.min(100, target ? (loss / target) * 100 : loss));
    const card = h("div", { class: "card batch-card", onclick: () => { this._detailBatchId = b.id; this._renderTab(); } }, [
      h("h2", null, [
        h("span", { class: "grow" }, [b.name, " ", isRef ? h("span", { class: "badge" }, t("reference")) : null,
          b.weigh_in_due ? [" ", h("span", { class: "badge due" }, `⚖ ${t("weigh_in_due")}`)] : null]),
        h("span", { class: `badge status-${b.status}` }, t(`status_${b.status}`)),
      ]),
      h("div", { class: "row" }, [
        b.last_photo_url ? this._photoImg(b.last_photo_url, "thumb") : null,
        h("div", { style: "flex:1;min-width:0" }, [
          b.product ? h("div", { class: "muted small" }, b.product) : null,
          h("div", { class: "bar" }, h("div", { class: `bar-fill${pct >= 100 ? " done" : ""}`, style: `width:${pct}%` })),
          h("div", { class: "kv" }, [
            h("span", null, [`${t("loss")} `, h("b", null, fmtNum(loss, 1, " %")), target != null ? ` / ${fmtNum(target, 0, " %")}` : ""]),
            h("span", null, [`${t("rate")} `, h("b", null, fmtNum(b.drying_rate, 2, " %/d"))]),
            h("span", null, [`${t("eta")} `, h("b", null, fmtDate(b.eta, this._locale))]),
            h("span", null, [h("b", null, b.sample_count != null ? b.sample_count : (b.samples || []).length), ` ${t("weigh_ins")}`]),
          ]),
        ]),
      ]),
    ]);
    return card;
  }

  _newBatchForm() {
    const t = (k) => this._t(k);
    const name = h("input", { type: "text", required: true });
    const product = h("input", { type: "text" });
    const program = h("select", null, [h("option", { value: "" }, t("none")),
      ...this._programs.map((p) => h("option", { value: p.id }, p.name))]);
    const refW = h("input", { type: "number", step: "1", min: "0" });
    const target = h("input", { type: "number", step: "1", min: "0", max: "90", value: 30 });
    const asRef = h("input", { type: "checkbox", checked: !this._batches.some((b) => b.status === "active") });
    const startProg = h("input", { type: "checkbox", checked: true });
    const startLabel = h("label", { class: "inline", style: "display:none" }, [startProg, t("start_program_now")]);
    program.addEventListener("change", () => { startLabel.style.display = program.value ? "" : "none"; });
    const back = () => { this._newBatch = false; this._renderTab(); };
    return h("div", { class: "card" }, [
      h("h2", null, t("new_batch")),
      h("div", { class: "form" }, [
        h("label", null, [t("name"), name]),
        h("label", null, [t("product"), product]),
        h("label", null, [t("program_optional"), program]),
        h("label", null, [t("reference_weight"), refW]),
        h("label", null, [t("target_loss"), target]),
        h("label", { class: "inline" }, [asRef, t("set_as_reference")]),
        startLabel,
      ]),
      h("div", { class: "row", style: "margin-top:16px" }, [
        h("button", {
          onclick: async () => {
            if (!name.value.trim()) { name.focus(); return; }
            const params = { name: name.value.trim(), set_as_reference: asRef.checked };
            if (product.value.trim()) params.product = product.value.trim();
            if (program.value) { params.program_id = program.value; params.start_program = startProg.checked; }
            if (refW.value !== "") params.reference_weight = parseFloat(refW.value);
            if (target.value !== "") params.target_loss_pct = parseFloat(target.value);
            try {
              const created = await this._ws("curing_chamber/batch/create", params);
              await this._loadBatches();
              this._newBatch = false;
              this._detailBatchId = created.id;
              this._renderTab();
            } catch (err) {
              this._showError(err);
            }
          },
        }, t("create")),
        h("button", { class: "ghost", onclick: back }, t("cancel")),
      ]),
    ]);
  }

  _batchDetail(b) {
    const t = (k) => this._t(k);
    const refId = this._state ? this._state.reference_batch_id : null;
    const isRef = b.id === refId;
    const wrap = h("div");
    const back = () => { this._detailBatchId = null; this._renderTab(); };
    const refresh = async () => { await this._loadBatches(); this._renderTab(); };
    const setStatus = async (status) => {
      try { await this._ws("curing_chamber/batch/set_status", { batch_id: b.id, status }); await refresh(); } catch (err) { this._showError(err); }
    };

    wrap.appendChild(h("div", { class: "row between", style: "margin-bottom:12px" }, [
      h("button", { class: "ghost sm", onclick: back }, `← ${t("back")}`),
      h("div", { class: "row" }, [
        !isRef && b.status !== "archived" ? h("button", { class: "outline sm", onclick: async () => { try { await this._ws("curing_chamber/batch/set_reference", { batch_id: b.id }); await refresh(); } catch (err) { this._showError(err); } } }, t("make_reference")) : null,
        b.status === "active" ? h("button", { class: "outline sm", onclick: () => setStatus("completed") }, t("complete")) : null,
        b.status !== "archived" ? h("button", { class: "outline sm", onclick: () => setStatus("archived") }, t("archive")) : null,
        b.status !== "active" ? h("button", { class: "outline sm", onclick: () => setStatus("active") }, t("reactivate")) : null,
        h("button", { class: "ghost sm", onclick: () => this._exportBatch(b, "json") }, `⇩ ${t("export_json")}`),
        h("button", { class: "ghost sm", onclick: () => this._exportBatch(b, "csv") }, `⇩ ${t("export_csv")}`),
        h("button", { class: "danger sm", onclick: async () => {
          if (!window.confirm(t("confirm_delete_batch"))) return;
          try { await this._ws("curing_chamber/batch/delete", { batch_id: b.id }); this._detailBatchId = null; await refresh(); } catch (err) { this._showError(err); }
        } }, t("delete")),
      ]),
    ]));

    const grid = h("div", { class: "grid" });
    // Summary + curve
    const summary = h("div", { class: "card span" }, [
      h("h2", null, [h("span", { class: "grow" }, [b.name, " ", isRef ? h("span", { class: "badge" }, t("reference")) : null]),
        h("span", { class: `badge status-${b.status}` }, t(`status_${b.status}`))]),
      h("div", { class: "kv", style: "margin-bottom:8px" }, [
        b.product ? h("span", null, [`${t("product")} `, h("b", null, b.product)]) : null,
        b.program_id ? h("span", null, [`${t("program")} `, h("b", null, this._programName(b.program_id))]) : null,
        h("span", null, [`${t("reference_weight")} `, h("b", null, fmtNum(b.reference_weight, 0))]),
        h("span", null, [`${t("weight")} `, h("b", null, fmtNum(b.last_weight, 0))]),
        h("span", null, [`${t("loss")} `, h("b", null, fmtNum(b.loss_pct, 1, " %")), b.target_loss_pct != null ? ` / ${fmtNum(b.target_loss_pct, 0, " %")}` : ""]),
        h("span", null, [`${t("rate")} `, h("b", null, fmtNum(b.drying_rate, 2, " %/d"))]),
        h("span", null, [`${t("eta")} `, h("b", null, fmtDate(b.eta, this._locale)), b.eta_model ? h("span", { class: "small muted" }, ` (${t(`eta_model_${b.eta_model}`)})`) : null]),
        h("span", null, [`${t("date")} `, h("b", null, fmtDate(b.created_at, this._locale))]),
      ]),
      h("h2", null, t("drying_curve")),
      lossPoints(b).length >= 2 ? this._curveChart([{ batch: b, color: null }], { target: b.target_loss_pct, eta: b.eta })
        : h("div", { class: "muted small" }, t("curve_needs_two")),
    ]);
    grid.appendChild(summary);

    // Weigh-in form
    grid.appendChild(this._weighInForm(b));

    // History table
    const samples = (b.samples || []).slice().reverse();
    const ref = b.reference_weight;
    const histCard = h("div", { class: "card" }, [h("h2", null, t("history"))]);
    if (!samples.length) histCard.appendChild(h("div", { class: "muted small" }, "—"));
    else {
      histCard.appendChild(h("div", { class: "table-wrap" }, h("table", null, [
        h("thead", null, h("tr", null, [h("th", null, t("date")), h("th", null, t("weight")), h("th", null, t("loss")), h("th", null, t("note")), h("th", null, t("photo")), h("th")])),
        h("tbody", null, samples.map((x) => h("tr", null, [
          h("td", null, fmtDateTime(x.timestamp, this._locale)),
          h("td", null, fmtNum(x.weight, 0)),
          h("td", null, ref ? fmtNum(((ref - x.weight) / ref) * 100, 1, " %") : "—"),
          h("td", { class: "muted" }, x.note || ""),
          h("td", null, x.photo_url ? this._photoImg(x.photo_url, "thumb") : ""),
          h("td", null, h("button", { class: "ghost sm", title: t("delete"), onclick: async () => {
            if (!window.confirm(t("confirm_delete_sample"))) return;
            try { await this._ws("curing_chamber/weigh_in/delete", { batch_id: b.id, timestamp: x.timestamp }); await refresh(); } catch (err) { this._showError(err); }
          } }, "✕")),
        ]))),
      ])));
    }
    grid.appendChild(histCard);

    // Journal
    grid.appendChild(this._journalCard(b, refresh));

    // Gallery
    const photos = (b.samples || []).filter((x) => x.photo_url);
    if (photos.length) {
      grid.appendChild(h("div", { class: "card span" }, [
        h("h2", null, t("gallery")),
        h("div", { class: "gallery" }, photos.map((x) => h("figure", null, [
          h("a", { href: "#", onclick: async (ev) => { ev.preventDefault(); try { window.open(await this._signedUrl(x.photo_url), "_blank", "noopener"); } catch (err) { this._showError(err); } } },
            this._photoImg(x.photo_url, "", x.note || "")),
          h("figcaption", null, [fmtDate(x.timestamp, this._locale), ref ? ` · ${fmtNum(((ref - x.weight) / ref) * 100, 1, " %")}` : ""]),
        ]))),
      ]));
    }
    wrap.appendChild(grid);
    return wrap;
  }

  _journalCard(b, refresh) {
    const t = (k) => this._t(k);
    const kindLabel = (k) => (JOURNAL_KINDS.includes(k) ? t(`kind_${k}`) : k);
    const events = (b.events || []).slice().reverse();
    const kind = h("select", null, JOURNAL_KINDS.map((k) => h("option", { value: k }, t(`kind_${k}`))));
    const note = h("input", { type: "text", placeholder: t("note_placeholder"), style: "flex:1;min-width:140px" });
    const when = h("input", { type: "datetime-local", value: toLocalInputValue(Date.now() / 1000) });
    const add = h("button", { class: "sm", onclick: async () => {
      const params = { batch_id: b.id, kind: kind.value };
      if (note.value.trim()) params.note = note.value.trim();
      const ts = fromLocalInputValue(when.value);
      if (ts != null) params.timestamp = ts;
      try { await this._ws("curing_chamber/batch/event/add", params); this._showToast(t("recorded")); await refresh(); } catch (err) { this._showError(err); }
    } }, t("add_entry"));
    const card = h("div", { class: "card" }, [
      h("h2", null, t("journal")),
      h("div", { class: "form" }, [kind, note, when, add]),
    ]);
    if (!events.length) card.appendChild(h("div", { class: "muted small", style: "margin-top:8px" }, t("no_entries")));
    else {
      card.appendChild(h("div", { class: "table-wrap", style: "margin-top:8px" }, h("table", null, [
        h("thead", null, h("tr", null, [h("th", null, t("date")), h("th", null, t("kind")), h("th", null, t("note")), h("th")])),
        h("tbody", null, events.map((e) => h("tr", null, [
          h("td", null, fmtDateTime(e.timestamp, this._locale)),
          h("td", null, kindLabel(e.kind)),
          h("td", { class: "muted" }, e.note || ""),
          h("td", null, h("button", { class: "ghost sm", title: t("delete"), onclick: async () => {
            if (!window.confirm(t("confirm_delete_event"))) return;
            try { await this._ws("curing_chamber/batch/event/delete", { batch_id: b.id, timestamp: e.timestamp }); await refresh(); } catch (err) { this._showError(err); }
          } }, "✕")),
        ]))),
      ])));
    }
    return card;
  }

  /** Download one batch as JSON (full record) or CSV (weigh-ins and journal, one timeline). */
  async _exportBatch(b, format) {
    const t = (k) => this._t(k);
    let data;
    try {
      data = await this._ws("curing_chamber/batch/export", { batch_id: b.id });
    } catch (err) {
      this._showError(err);
      return;
    }
    const base = `curing-chamber-${b.id}`;
    if (format === "json") { downloadJson(`${base}.json`, data); return; }
    const batch = data.batch || {};
    const ref = data.summary && data.summary.reference_weight;
    const rows = [["timestamp", "type", "kind", "weight", "loss_pct", "note", "photo_url"]];
    const iso = (ts) => new Date(ts * 1000).toISOString();
    const lines = [];
    for (const x of batch.samples || []) {
      lines.push({ ts: x.timestamp, row: [iso(x.timestamp), "weigh_in", "", x.weight, ref ? (((ref - x.weight) / ref) * 100).toFixed(2) : "", x.note || "", x.photo_url || ""] });
    }
    for (const e of batch.events || []) {
      lines.push({ ts: e.timestamp, row: [iso(e.timestamp), "event", e.kind, "", "", e.note || "", ""] });
    }
    lines.sort((a, c) => a.ts - c.ts);
    for (const l of lines) rows.push(l.row);
    const esc = (v) => { const s = String(v == null ? "" : v); return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const csv = rows.map((r) => r.map(esc).join(",")).join("\n");
    const blob = new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = h("a", { href: url, download: `${base}.csv` });
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    this._showToast(t("applied"));
  }

  _weighInForm(b) {
    const t = (k) => this._t(k);
    const weight = h("input", { type: "number", step: "0.1", min: "0", inputmode: "decimal" });
    const note = h("input", { type: "text", placeholder: t("note_placeholder") });
    const photo = h("input", { type: "file", accept: "image/*", capture: "environment" });
    const nowBox = h("input", { type: "checkbox", checked: true });
    const when = h("input", { type: "datetime-local", value: toLocalInputValue(Date.now() / 1000), disabled: true });
    nowBox.addEventListener("change", () => { when.disabled = nowBox.checked; });
    const status = h("div", { class: "muted small", style: "flex-basis:100%" });
    const submit = h("button", {
      onclick: async () => {
        const w = parseFloat(weight.value);
        if (Number.isNaN(w)) { status.textContent = t("enter_weight"); weight.focus(); return; }
        const params = { batch_id: b.id, weight: w };
        if (note.value.trim()) params.note = note.value.trim();
        if (!nowBox.checked) {
          const ts = fromLocalInputValue(when.value);
          if (ts != null) params.timestamp = ts;
        }
        submit.disabled = true;
        try {
          const file = photo.files && photo.files[0];
          if (file) params.photo = await downscaleImage(file);
          status.textContent = t("loading");
          await this._ws("curing_chamber/weigh_in", params);
          this._showToast(t("recorded"));
          await this._loadBatches();
          this._renderTab();
        } catch (err) {
          this._showError(err);
          status.textContent = "";
          submit.disabled = false;
        }
      },
    }, t("record"));
    return h("div", { class: "card" }, [
      h("h2", null, t("record_weigh_in")),
      h("div", { class: "form" }, [
        h("label", null, [t("weight"), weight]),
        h("label", { style: "flex:1;min-width:160px" }, [t("note"), note]),
        h("label", null, [t("photo"), photo]),
        h("label", { class: "inline" }, [nowBox, t("now")]),
        h("label", null, [t("when"), when]),
        submit,
        status,
      ]),
    ]);
  }

  _programName(programId) {
    const p = this._programs.find((x) => x.id === programId);
    return p ? p.name : programId;
  }

  /**
   * Drying curve chart: loss % (y) vs days since first weigh-in (x) for one or
   * several batches. `series` = [{batch, color}]. Options: target (%) and eta
   * (epoch s) draw the target line and a dashed projection for single-series.
   */
  _curveChart(series, opts = {}) {
    const W = 600;
    const H = 260;
    const padL = 36;
    const padR = 12;
    const padT = 10;
    const padB = 28;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;
    const all = series.map((sr) => ({ ...sr, pts: lossPoints(sr.batch) })).filter((sr) => sr.pts.length);
    let maxDays = Math.max(1, ...all.map((sr) => sr.pts[sr.pts.length - 1].days));
    let maxLoss = Math.max(opts.target || 0, ...all.flatMap((sr) => sr.pts.map((p) => p.loss)), 5);
    let projection = null;
    if (all.length === 1 && opts.eta != null && opts.target != null) {
      const pts = all[0].pts;
      const last = pts[pts.length - 1];
      const etaDays = (opts.eta - pts[0].t) / 86400;
      if (etaDays > last.days) {
        projection = { from: last, to: { days: etaDays, loss: opts.target } };
        maxDays = Math.max(maxDays, etaDays);
      }
    }
    maxLoss = Math.ceil(maxLoss * 1.1 / 5) * 5;
    const x = (days) => padL + (days / maxDays) * plotW;
    const y = (loss) => padT + plotH - (Math.max(0, loss) / maxLoss) * plotH;
    const svg = s("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, role: "img" });
    // Grid + axes
    const ySteps = 5;
    for (let i = 0; i <= ySteps; i++) {
      const v = (maxLoss / ySteps) * i;
      svg.appendChild(s("line", { class: "grid", x1: padL, x2: W - padR, y1: y(v), y2: y(v) }));
      svg.appendChild(s("text", { class: "lbl", x: padL - 4, y: y(v) + 3, "text-anchor": "end" }, `${v.toFixed(0)}%`));
    }
    const xStep = maxDays <= 14 ? 1 : maxDays <= 60 ? 7 : maxDays <= 180 ? 14 : 30;
    for (let d = 0; d <= maxDays; d += xStep) {
      svg.appendChild(s("text", { class: "lbl", x: x(d), y: H - padB + 14, "text-anchor": "middle" }, `${d}`));
    }
    svg.appendChild(s("text", { class: "lbl", x: W - padR, y: H - 4, "text-anchor": "end" }, this._t("days")));
    svg.appendChild(s("line", { class: "axis", x1: padL, x2: padL, y1: padT, y2: padT + plotH }));
    svg.appendChild(s("line", { class: "axis", x1: padL, x2: W - padR, y1: padT + plotH, y2: padT + plotH }));
    if (opts.target != null) {
      svg.appendChild(s("line", { class: "target", x1: padL, x2: W - padR, y1: y(opts.target), y2: y(opts.target) }));
    }
    for (const sr of all) {
      const coords = sr.pts.map((p) => `${x(p.days).toFixed(1)},${y(p.loss).toFixed(1)}`).join(" ");
      const style = sr.color ? `stroke:${sr.color}` : null;
      svg.appendChild(s("polyline", { class: "line", points: coords, style }));
      for (const p of sr.pts) {
        svg.appendChild(s("circle", { class: "pt", cx: x(p.days), cy: y(p.loss), r: 3, style: sr.color ? `fill:${sr.color}` : null }));
      }
    }
    if (projection) {
      svg.appendChild(s("line", { class: "proj", x1: x(projection.from.days), y1: y(projection.from.loss), x2: x(projection.to.days), y2: y(projection.to.loss) }));
    }
    return svg;
  }

  // ===========================================================================
  // View 3 — Programs
  // ===========================================================================

  _viewPrograms() {
    const t = (k) => this._t(k);
    if (this._editing) return this._programEditor();
    const wrap = h("div");
    const mine = this._programs.filter((p) => !p.builtin);
    const presets = this._programs.filter((p) => p.builtin);
    const kind = (this._state && this._state.kind) || "charcuterie";
    wrap.appendChild(h("div", { class: "row between", style: "margin-bottom:12px" }, [
      h("span", { class: "muted small" }, `${this._programs.length} ${t("tab_programs").toLowerCase()} · ${t(`kind_${kind}`)}`),
      h("div", { class: "row" }, [
        h("button", { class: "outline sm", onclick: () => this._importPrograms() }, `⇧ ${t("import")}`),
        mine.length ? h("button", { class: "outline sm", onclick: () => this._exportPrograms(mine) }, `⇩ ${t("export_all")}`) : null,
        h("button", { onclick: () => this._openEditor(this._blankProgram(), true) }, `+ ${t("new_program")}`),
      ]),
    ]));
    if (!this._programs.length) {
      wrap.appendChild(h("div", { class: "empty" }, t("no_programs")));
      return wrap;
    }
    const section = (title, programs) => {
      if (!programs.length) return;
      wrap.appendChild(h("h2", { style: "margin:16px 0 8px" }, title));
      const grid = h("div", { class: "grid" });
      for (const p of programs) grid.appendChild(this._programListCard(p));
      wrap.appendChild(grid);
    };
    section(t("my_programs"), mine);
    section(t("presets"), presets);
    return wrap;
  }

  _programListCard(p) {
    const t = (k) => this._t(k);
    const totalHours = p.phases.reduce((acc, ph) => acc + (ph.duration_hours || 0), 0);
    return h("div", { class: "card" }, [
      h("h2", null, [
        h("span", { class: "grow" }, p.name),
        p.category ? h("span", { class: "badge", style: "margin-right:4px" }, t(`cat_${p.category}`)) : null,
        p.builtin ? h("span", { class: "badge" }, t("preset")) : null,
      ]),
      h("div", { class: "muted small" }, [`${p.phases.length} ${t("phases").toLowerCase()} · ~${hoursToText(totalHours, t)} · `, h("code", null, p.id)]),
      this._timeline(p.phases, -1),
      h("div", { class: "row", style: "margin-top:8px" }, [
        h("button", { class: "outline sm", onclick: () => this._openEditor(p, false) }, p.builtin ? t("view") : t("edit")),
        h("button", { class: "outline sm", onclick: () => this._openEditor(this._duplicate(p), true) }, t("duplicate")),
        h("button", { class: "sm", onclick: async () => { if (await this._service("start_program", { program_id: p.id })) { this._showToast(t("started")); this._setTab("chamber"); } } }, t("start_this")),
        h("button", { class: "ghost sm", title: t("export"), onclick: () => this._exportPrograms([p]) }, "⇩"),
        !p.builtin ? h("button", { class: "danger sm", onclick: () => this._deleteProgram(p.id) }, t("delete")) : null,
      ]),
    ]);
  }

  /** Download programs as a portable JSON file (same envelope as the export_programs service). */
  _exportPrograms(programs) {
    const cleaned = programs.map((p) => ({ ...this._cleanProgram(p) }));
    const name = programs.length === 1 ? `curing-chamber-${programs[0].id}.json` : "curing-chamber-programs.json";
    downloadJson(name, { format: "curing_chamber/programs", version: 1, programs: cleaned });
  }

  /** Pick a JSON file (export envelope, list or single program) and import it. */
  async _importPrograms() {
    const t = (k) => this._t(k);
    let data;
    try {
      data = await pickJsonFile();
    } catch (err) {
      this._showToast(t("import_invalid"), true);
      return;
    }
    if (data == null) return;
    const list = Array.isArray(data) ? data : data && Array.isArray(data.programs) ? data.programs : data && data.phases ? [data] : null;
    if (!list || !list.length) { this._showToast(t("import_invalid"), true); return; }
    const existing = new Set(this._programs.filter((p) => !p.builtin).map((p) => p.id));
    const clash = list.some((p) => p && existing.has(p.id));
    const overwrite = clash ? window.confirm(t("import_overwrite")) : false;
    try {
      const result = await this._ws("curing_chamber/program/import", { programs: list, overwrite });
      const parts = [`${result.imported.length} ${t("imported")}`];
      if (result.skipped.length) parts.push(`${result.skipped.length} ${t("skipped")}`);
      this._showToast(parts.join(" · "));
      await this._loadPrograms();
      this._renderTab();
    } catch (err) {
      this._showError(err);
    }
  }

  _blankProgram() {
    const category = (this._state && this._state.kind) || "charcuterie";
    return { id: "", name: "", on_complete: "hold_last", builtin: false, category, phases: [this._blankPhase()], reminders: [] };
  }

  _blankPhase() {
    const cheese = this._state && this._state.kind === "cheese";
    return {
      name: "", target_temp: cheese ? 12 : 13, target_humidity: cheese ? 90 : 76, end_kind: "duration", duration_hours: 168,
      weight_loss_pct: null, core_temp_target: null, notify_end: true, start_temp: null, start_humidity: null, ramp_hours: null,
    };
  }

  _duplicate(p) {
    const suffix = this._t("copy_suffix");
    return {
      ...JSON.parse(JSON.stringify(p)),
      id: slugify(`${p.id}_${suffix}`),
      name: `${p.name} (${suffix})`,
      builtin: false,
    };
  }

  _openEditor(program, isNew) {
    this._editing = { program: JSON.parse(JSON.stringify(program)), isNew, validation: null, autoId: isNew && !program.id };
    this._renderTab();
  }

  async _deleteProgram(programId) {
    if (!window.confirm(this._t("confirm_delete_program"))) return;
    try {
      await this._ws("curing_chamber/program/delete", { program_id: programId });
      this._showToast(this._t("deleted"));
      this._editing = null;
      await this._loadPrograms();
      this._renderTab();
    } catch (err) {
      this._showError(err);
    }
  }

  /** Serialize the editor inputs back into the model (before re-rendering). */
  _readEditor() {
    const ed = this._editing;
    if (!ed || !ed.els) return;
    const num = (el) => (el.value === "" ? null : parseFloat(el.value));
    ed.program.id = ed.els.id.value.trim();
    ed.program.name = ed.els.name.value.trim();
    ed.program.on_complete = ed.els.onComplete.value;
    ed.program.category = ed.els.category.value;
    ed.program.reminders = (ed.els.reminders || []).map((row) => ({
      kind: row.kind.value,
      every_hours: num(row.every),
      note: row.note.value.trim() || null,
      phases: row.phase.value ? [row.phase.value] : [],
    }));
    ed.program.phases = ed.els.phases.map((row) => ({
      name: row.name.value,
      target_temp: num(row.temp),
      target_humidity: num(row.hum),
      end_kind: row.endKind.value,
      duration_hours: num(row.hours),
      weight_loss_pct: num(row.loss),
      core_temp_target: num(row.core),
      notify_end: row.notify.checked,
      start_temp: num(row.startTemp),
      start_humidity: num(row.startHum),
      ramp_hours: num(row.rampHours),
    }));
  }

  _programEditor() {
    const t = (k) => this._t(k);
    const ed = this._editing;
    const p = ed.program;
    const readOnly = Boolean(p.builtin);
    const els = { phases: [] };
    ed.els = els;

    const validate = () => {
      clearTimeout(ed.timer);
      ed.timer = setTimeout(async () => {
        this._readEditor();
        try {
          ed.validation = await this._ws("curing_chamber/program/validate", { program: this._cleanProgram(p) });
        } catch (err) {
          ed.validation = { valid: false, errors: [err.message || String(err)], warnings: [] };
        }
        this._renderValidation();
      }, 400);
    };

    els.id = h("input", { type: "text", value: p.id, disabled: readOnly || !ed.isNew, oninput: () => { ed.autoId = false; validate(); } });
    els.name = h("input", { type: "text", value: p.name, disabled: readOnly, oninput: () => {
      if (ed.autoId) els.id.value = slugify(els.name.value);
      validate();
    } });
    els.onComplete = h("select", { disabled: readOnly, onchange: validate }, [
      h("option", { value: "hold_last", selected: p.on_complete === "hold_last" }, t("hold_last")),
      h("option", { value: "stop", selected: p.on_complete === "stop" }, t("stop_regulation")),
    ]);
    const category = p.category || (this._state && this._state.kind) || "charcuterie";
    els.category = h("select", { disabled: readOnly, onchange: validate }, [
      h("option", { value: "charcuterie", selected: category === "charcuterie" }, t("cat_charcuterie")),
      h("option", { value: "cheese", selected: category === "cheese" }, t("cat_cheese")),
    ]);

    const phasesBox = h("div");
    phasesBox.appendChild(h("div", { class: "phase-row phase-head" }, [
      h("span", null, t("phase_name")), h("span", null, t("target_temp_short")), h("span", null, t("target_hum_short")),
      h("span", null, t("end_kind")), h("span", null, t("duration_hours")), h("span", null, t("weight_loss_pct")),
      h("span", null, t("notify_end")), h("span"),
    ]));
    p.phases.forEach((ph, i) => {
      const row = {};
      row.name = h("input", { type: "text", value: ph.name, placeholder: t("phase_name"), disabled: readOnly, oninput: validate });
      row.temp = h("input", { type: "number", step: "0.5", value: ph.target_temp != null ? ph.target_temp : "", placeholder: "°C", disabled: readOnly, oninput: validate });
      row.hum = h("input", { type: "number", step: "1", value: ph.target_humidity != null ? ph.target_humidity : "", placeholder: "%", disabled: readOnly, oninput: validate });
      row.endKind = h("select", { disabled: readOnly, onchange: validate }, [
        h("option", { value: "duration", selected: ph.end_kind === "duration" }, t("end_duration")),
        h("option", { value: "weight_loss", selected: ph.end_kind === "weight_loss" }, t("end_weight_loss")),
        h("option", { value: "core_temp", selected: ph.end_kind === "core_temp" }, t("end_core_temp")),
        h("option", { value: "manual", selected: ph.end_kind === "manual" }, t("end_manual")),
      ]);
      row.hours = h("input", { type: "number", step: "1", min: "0", value: ph.duration_hours != null ? ph.duration_hours : "", placeholder: "h", disabled: readOnly, oninput: validate });
      row.loss = h("input", { type: "number", step: "0.5", min: "0", max: "90", value: ph.weight_loss_pct != null ? ph.weight_loss_pct : "", placeholder: "%", disabled: readOnly, oninput: validate });
      row.core = h("input", { type: "number", step: "0.5", value: ph.core_temp_target != null ? ph.core_temp_target : "", placeholder: t("core_temp_target"), title: t("core_temp_target"), disabled: readOnly, oninput: validate });
      // One cell: the loss target for weight_loss phases, the core target for core_temp phases.
      const endCell = h("div", null, [row.loss, row.core]);
      const syncEndCell = () => {
        row.core.style.display = row.endKind.value === "core_temp" ? "" : "none";
        row.loss.style.display = row.endKind.value === "core_temp" ? "none" : "";
      };
      row.endKind.addEventListener("change", syncEndCell);
      syncEndCell();
      row.notify = h("input", { type: "checkbox", checked: ph.notify_end !== false, disabled: readOnly, onchange: validate });
      row.startTemp = h("input", { type: "number", step: "0.5", value: ph.start_temp != null ? ph.start_temp : "", placeholder: "°C", disabled: readOnly, oninput: validate, title: t("ramp_hint") });
      row.startHum = h("input", { type: "number", step: "1", value: ph.start_humidity != null ? ph.start_humidity : "", placeholder: "%", disabled: readOnly, oninput: validate, title: t("ramp_hint") });
      row.rampHours = h("input", { type: "number", step: "1", min: "0", value: ph.ramp_hours != null ? ph.ramp_hours : "", placeholder: "h", disabled: readOnly, oninput: validate, title: t("ramp_hint") });
      els.phases.push(row);
      phasesBox.appendChild(h("div", { class: "phase-row" }, [
        row.name, row.temp, row.hum, row.endKind, row.hours, endCell, row.notify,
        !readOnly ? h("div", { class: "ctl" }, [
          h("button", { class: "ghost sm", title: t("move_up"), disabled: i === 0, onclick: () => { this._readEditor(); const a = p.phases; [a[i - 1], a[i]] = [a[i], a[i - 1]]; this._renderTab(); } }, "↑"),
          h("button", { class: "ghost sm", title: t("move_down"), disabled: i === p.phases.length - 1, onclick: () => { this._readEditor(); const a = p.phases; [a[i + 1], a[i]] = [a[i], a[i + 1]]; this._renderTab(); } }, "↓"),
          h("button", { class: "ghost sm", title: t("remove"), disabled: p.phases.length <= 1, onclick: () => { this._readEditor(); p.phases.splice(i, 1); this._renderTab(); } }, "✕"),
        ]) : h("span"),
      ]));
      if (!readOnly || hasRamp(ph)) {
        phasesBox.appendChild(h("div", { class: "phase-ramp", title: t("ramp_hint") }, [
          h("span", null, `↘ ${t("ramp_from")}`), row.startTemp, h("span", null, "°C"), row.startHum, h("span", null, "%"),
          h("span", { class: "arrow" }, "→"), h("span", null, t("ramp_hours")), row.rampHours,
        ]));
      }
    });

    // Care reminders ----------------------------------------------------------
    els.reminders = [];
    const remindersBox = h("div", { title: t("reminder_hint") });
    const phaseNames = p.phases.map((ph) => ph.name).filter(Boolean);
    (p.reminders || []).forEach((r, i) => {
      const row = {};
      const known = JOURNAL_KINDS.includes(r.kind);
      row.kind = h("select", { disabled: readOnly, onchange: validate }, [
        ...JOURNAL_KINDS.map((k) => h("option", { value: k, selected: r.kind === k }, t(`kind_${k}`))),
        !known ? h("option", { value: r.kind, selected: true }, r.kind) : null,
      ]);
      row.every = h("input", { type: "number", step: "1", min: "1", value: r.every_hours != null ? r.every_hours : "", placeholder: "h", disabled: readOnly, oninput: validate, style: "width:80px" });
      row.note = h("input", { type: "text", value: r.note || "", placeholder: t("note"), disabled: readOnly, oninput: validate, style: "flex:1;min-width:120px" });
      const current = (r.phases && r.phases[0]) || "";
      row.phase = h("select", { disabled: readOnly, onchange: validate }, [
        h("option", { value: "", selected: !current }, t("all_phases")),
        ...phaseNames.map((n) => h("option", { value: n, selected: current === n }, n)),
      ]);
      els.reminders.push(row);
      remindersBox.appendChild(h("div", { class: "phase-ramp" }, [
        row.kind, h("span", null, t("every_hours")), row.every, row.phase, row.note,
        !readOnly ? h("button", { class: "ghost sm", title: t("remove"), onclick: () => { this._readEditor(); p.reminders.splice(i, 1); this._renderTab(); } }, "✕") : null,
      ]));
    });

    this._validationBox = h("div");
    this._renderValidation();

    const card = h("div", { class: "card" }, [
      h("h2", null, [h("span", { class: "grow" }, ed.isNew ? t("new_program") : p.name), p.builtin ? h("span", { class: "badge" }, t("preset")) : null]),
      readOnly ? h("div", { class: "msg warning" }, t("read_only_preset")) : null,
      h("div", { class: "form" }, [
        h("label", { style: "flex:1;min-width:180px" }, [t("name"), els.name]),
        h("label", { style: "min-width:160px" }, [t("program_id"), els.id]),
        h("label", null, [t("category"), els.category]),
        h("label", null, [t("on_complete"), els.onComplete]),
      ]),
      h("h2", { style: "margin-top:16px" }, t("phases")),
      phasesBox,
      !readOnly ? h("div", { style: "margin-top:8px" }, h("button", { class: "outline sm", onclick: () => { this._readEditor(); p.phases.push(this._blankPhase()); this._renderTab(); } }, `+ ${t("add_phase")}`)) : null,
      (!readOnly || (p.reminders || []).length) ? h("h2", { style: "margin-top:16px" }, t("reminders")) : null,
      remindersBox,
      !readOnly ? h("div", { style: "margin-top:8px" }, h("button", { class: "outline sm", onclick: () => { this._readEditor(); (p.reminders = p.reminders || []).push({ kind: "turned", every_hours: 48, note: "", phases: [] }); this._renderTab(); } }, `+ ${t("add_reminder")}`)) : null,
      this._validationBox,
      h("div", { class: "row", style: "margin-top:16px" }, [
        !readOnly ? h("button", { onclick: () => this._saveProgram() }, t("save")) : null,
        readOnly ? h("button", { class: "outline", onclick: () => this._openEditor(this._duplicate(p), true) }, t("duplicate")) : null,
        !ed.isNew ? h("button", { class: "outline", onclick: async () => { if (await this._service("start_program", { program_id: p.id })) { this._showToast(t("started")); this._editing = null; this._setTab("chamber"); } } }, t("start_this")) : null,
        !ed.isNew && !readOnly ? h("button", { class: "danger", onclick: () => this._deleteProgram(p.id) }, t("delete")) : null,
        h("button", { class: "ghost", onclick: () => { this._editing = null; this._renderTab(); } }, t("cancel")),
      ]),
    ]);
    if (!readOnly && !ed.validation) validate();
    return card;
  }

  _renderValidation() {
    const box = this._validationBox;
    const ed = this._editing;
    if (!box || !ed) return;
    clear(box);
    const v = ed.validation;
    if (!v) return;
    const t = (k) => this._t(k);
    if (v.errors && v.errors.length) {
      box.appendChild(h("div", { class: "msg error" }, [h("b", null, `${t("errors")}: `), h("ul", { style: "margin:4px 0 0 16px;padding:0" }, v.errors.map((e) => h("li", null, e)))]));
    }
    if (v.warnings && v.warnings.length) {
      box.appendChild(h("div", { class: "msg warning" }, [h("b", null, `${t("warnings")}: `), h("ul", { style: "margin:4px 0 0 16px;padding:0" }, v.warnings.map((w) => h("li", null, w)))]));
    }
    if (v.valid && !(v.errors && v.errors.length)) box.appendChild(h("div", { class: "msg ok" }, t("valid")));
  }

  /** Strip editor-only fields and nulls the backend does not expect. */
  _cleanProgram(p) {
    const phases = p.phases.map((ph) => {
      const out = { name: ph.name, end_kind: ph.end_kind, notify_end: ph.notify_end !== false };
      if (ph.target_temp != null) out.target_temp = ph.target_temp;
      if (ph.target_humidity != null) out.target_humidity = ph.target_humidity;
      if (ph.duration_hours != null) out.duration_hours = ph.duration_hours;
      if (ph.weight_loss_pct != null) out.weight_loss_pct = ph.weight_loss_pct;
      if (ph.core_temp_target != null) out.core_temp_target = ph.core_temp_target;
      if (ph.start_temp != null) out.start_temp = ph.start_temp;
      if (ph.start_humidity != null) out.start_humidity = ph.start_humidity;
      if (ph.ramp_hours != null && ph.ramp_hours > 0) out.ramp_hours = ph.ramp_hours;
      return out;
    });
    const reminders = (p.reminders || []).map((r) => {
      const out = { kind: r.kind, every_hours: r.every_hours, phases: r.phases || [] };
      if (r.note) out.note = r.note;
      return out;
    });
    return { id: p.id, name: p.name, on_complete: p.on_complete || "hold_last", category: p.category || "charcuterie", phases, reminders };
  }

  async _saveProgram() {
    const ed = this._editing;
    this._readEditor();
    const p = ed.program;
    if (!p.id && p.name) p.id = slugify(p.name);
    try {
      const result = await this._ws("curing_chamber/program/save", { program: this._cleanProgram(p) });
      this._showToast(this._t("saved"));
      if (result && result.warnings && result.warnings.length) {
        ed.validation = { valid: true, errors: [], warnings: result.warnings };
      }
      this._editing = null;
      await this._loadPrograms();
      this._renderTab();
    } catch (err) {
      this._showError(err);
      ed.validation = { valid: false, errors: [err.message || String(err)], warnings: [] };
      this._renderValidation();
    }
  }

  // ===========================================================================
  // View 4 — History
  // ===========================================================================

  _viewHistory() {
    const t = (k) => this._t(k);
    const finished = this._batches.filter((b) => b.status === "completed" || b.status === "archived");
    const wrap = h("div");
    if (!finished.length) {
      wrap.appendChild(h("div", { class: "empty" }, t("no_history")));
      return wrap;
    }
    for (const id of Array.from(this._compareIds)) {
      if (!finished.some((b) => b.id === id)) this._compareIds.delete(id);
    }
    const selected = finished.filter((b) => this._compareIds.has(b.id));
    const colorOf = (b) => CURVE_COLORS[finished.indexOf(b) % CURVE_COLORS.length];

    const chartCard = h("div", { class: "card" }, [h("h2", null, t("compare"))]);
    const withPoints = selected.filter((b) => lossPoints(b).length >= 2);
    if (!withPoints.length) chartCard.appendChild(h("div", { class: "muted small" }, t("select_to_compare")));
    else {
      const targets = withPoints.map((b) => b.target_loss_pct).filter((v) => v != null);
      const target = targets.length && targets.every((v) => v === targets[0]) ? targets[0] : null;
      chartCard.appendChild(this._curveChart(withPoints.map((b) => ({ batch: b, color: colorOf(b) })), { target }));
      chartCard.appendChild(h("div", { class: "legend", style: "margin-top:8px" }, withPoints.map((b) => h("span", null, [
        h("span", { class: "sw", style: `background:${colorOf(b)}` }), b.name,
      ]))));
    }
    wrap.appendChild(chartCard);

    const rows = finished.map((b) => {
      const pts = lossPoints(b);
      const days = pts.length ? pts[pts.length - 1].days : null;
      const finalLoss = pts.length ? pts[pts.length - 1].loss : b.loss_pct;
      const meanRate = days && days > 0 && finalLoss != null ? finalLoss / days : null;
      const box = h("input", { type: "checkbox", checked: this._compareIds.has(b.id), onchange: (ev) => {
        if (ev.target.checked) this._compareIds.add(b.id); else this._compareIds.delete(b.id);
        this._renderTab();
      } });
      return h("tr", null, [
        h("td", null, box),
        h("td", null, [h("span", { class: "sw", style: `background:${colorOf(b)};display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px` }), b.name,
          b.product ? h("span", { class: "muted small" }, ` · ${b.product}`) : null]),
        h("td", null, h("span", { class: `badge status-${b.status}` }, t(`status_${b.status}`))),
        h("td", null, b.program_id ? this._programName(b.program_id) : "—"),
        h("td", null, fmtNum(b.reference_weight, 0)),
        h("td", null, [fmtNum(finalLoss, 1, " %"), b.target_loss_pct != null ? h("span", { class: "muted" }, ` / ${fmtNum(b.target_loss_pct, 0, " %")}`) : null]),
        h("td", null, days != null ? `${days.toFixed(0)} ${t("day_short")}` : "—"),
        h("td", null, fmtNum(meanRate, 2, " %/d")),
        h("td", null, fmtDate(b.created_at, this._locale)),
      ]);
    });
    wrap.appendChild(h("div", { class: "card", style: "margin-top:16px" }, [
      h("div", { class: "table-wrap" }, h("table", null, [
        h("thead", null, h("tr", null, [h("th"), h("th", null, t("name")), h("th"), h("th", null, t("program")), h("th", null, t("reference_weight")),
          h("th", null, t("final_loss")), h("th", null, t("duration")), h("th", null, t("mean_rate")), h("th", null, t("date"))])),
        h("tbody", null, rows),
      ])),
    ]));
    return wrap;
  }
}

if (!customElements.get(PANEL_TAG)) {
  customElements.define(PANEL_TAG, CuringChamberPanel);
}
