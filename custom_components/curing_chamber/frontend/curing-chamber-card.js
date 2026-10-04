/*
 * Curing Chamber — custom Lovelace card.
 *
 * Dependency-free vanilla custom element (no build step, no external CDN). It
 * reads the "active batches" sensor exposed by the integration
 * (sensor.<chamber>_active_batches) whose `batches` attribute carries a light
 * per-batch summary (name, status, loss %, drying rate, ETA, latest photo) and
 * fetches the weigh-in history over the integration's websocket API
 * (`curing_chamber/batches`). It renders a drying curve, a loss gauge and an
 * inline form to record a new weigh-in (weight + optional photo, downscaled
 * in the browser) that works with or without a scale. Photos are private:
 * their URLs are signed through `auth/sign_path` before being displayed.
 */

const CARD_TAG = "curing-chamber-card";
const PHOTO_MAX_PX = 1600;
const SIGN_TTL_S = 3600;

class CuringChamberCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error('Set "entity" to the chamber\'s active-batches sensor.');
    }
    this._config = config;
    this._built = false;
    this._samples = {};
    this._samplesKey = null;
    this._signed = {};
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass.states || {}).find((e) =>
      e.startsWith("sensor.") && e.endsWith("_active_batches"),
    );
    return { entity: entity || "sensor.active_batches" };
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  // -- Rendering ----------------------------------------------------------

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._built) {
      this._build();
    }
    const stateObj = this._hass.states[this._config.entity];
    if (!stateObj) {
      this._body.textContent = "";
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = `Unknown entity: ${this._config.entity}`;
      this._body.appendChild(empty);
      return;
    }
    const attrs = stateObj.attributes;
    const batches = attrs.batches || [];
    const refId = attrs.reference_batch_id || null;
    this._entryId = attrs.entry_id || null;
    this._title.textContent = this._config.title || "Curing chamber — batches";

    if (batches.length === 0) {
      this._body.innerHTML = `<div class="empty">No batch yet. Use the <code>create_batch</code> action or the Curing Chamber panel to add one.</div>`;
    } else {
      this._body.innerHTML = batches
        .map((b) => this._renderBatch(b, b.id === refId))
        .join("");
      this._hydratePhotos();
    }
    this._syncForm(batches);
    this._refreshSamples(batches);
  }

  _renderBatch(b, isRef) {
    const loss = b.loss_pct == null ? null : b.loss_pct;
    const target = b.target_loss_pct;
    const pct = loss == null ? 0 : Math.max(0, Math.min(100, target ? (loss / target) * 100 : loss));
    const lossTxt = loss == null ? "—" : `${loss.toFixed(1)} %`;
    const targetTxt = target == null ? "" : ` / ${target.toFixed(0)} %`;
    const rate = b.drying_rate == null ? "—" : `${b.drying_rate.toFixed(2)} %/d`;
    const eta = this._formatEta(b.eta);
    const photo = b.last_photo_url
      ? `<img class="thumb" data-photo="${this._escape(b.last_photo_url)}" alt="" />`
      : "";
    const badge = isRef ? `<span class="badge">reference</span>` : "";
    const statusClass = `status status-${this._escape(b.status)}`;

    return `
      <div class="batch">
        <div class="batch-head">
          <div class="batch-name">${this._escape(b.name)}${badge}</div>
          <div class="${statusClass}">${this._escape(b.status)}</div>
        </div>
        <div class="batch-body">
          ${photo}
          <div class="metrics">
            <div class="curve">${this._sparkline(b)}</div>
            <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
            <div class="row">
              <span>Loss <b>${lossTxt}${targetTxt}</b></span>
              <span>Rate <b>${rate}</b></span>
              <span>ETA <b>${eta}</b></span>
            </div>
          </div>
        </div>
      </div>`;
  }

  _sparkline(b) {
    const ref = b.reference_weight;
    const samples = (this._samples[b.id] || []).filter((s) => s.weight != null);
    if (!ref || ref <= 0 || samples.length < 2) return "";
    const points = samples.map((s) => ({
      t: s.timestamp,
      loss: ((ref - s.weight) / ref) * 100,
    }));
    const t0 = points[0].t;
    const tSpan = points[points.length - 1].t - t0 || 1;
    const maxLoss = Math.max(b.target_loss_pct || 0, ...points.map((p) => p.loss), 1);
    const w = 240;
    const h = 48;
    const coords = points
      .map((p) => {
        const x = ((p.t - t0) / tSpan) * (w - 4) + 2;
        const y = h - 2 - (p.loss / maxLoss) * (h - 4);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
    const targetY =
      b.target_loss_pct != null
        ? (h - 2 - (b.target_loss_pct / maxLoss) * (h - 4)).toFixed(1)
        : null;
    const targetLine =
      targetY != null
        ? `<line x1="2" y1="${targetY}" x2="${w - 2}" y2="${targetY}" class="target-line" />`
        : "";
    return `<svg viewBox="0 0 ${w} ${h}" class="spark" preserveAspectRatio="none">
      ${targetLine}
      <polyline points="${coords}" class="spark-line" />
    </svg>`;
  }

  _formatEta(eta) {
    if (eta == null) return "—";
    const d = new Date(eta * 1000);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
  }

  // -- Data: weigh-in history & private photos ----------------------------

  async _refreshSamples(batches) {
    if (!this._entryId) return;
    // Re-fetch only when the light summaries changed (new weigh-in, new batch…).
    const key = JSON.stringify(batches.map((b) => [b.id, b.sample_count, b.last_weigh_in]));
    if (key === this._samplesKey) return;
    this._samplesKey = key;
    try {
      const full = await this._hass.callWS({
        type: "curing_chamber/batches",
        entry_id: this._entryId,
        with_samples: true,
      });
      this._samples = {};
      for (const b of full) this._samples[b.id] = b.samples || [];
      this._render();
    } catch (err) {
      this._samplesKey = null;
    }
  }

  async _signedUrl(url) {
    const cached = this._signed[url];
    if (cached && cached.expires > Date.now()) return cached.path;
    const result = await this._hass.callWS({
      type: "auth/sign_path",
      path: url,
      expires: SIGN_TTL_S,
    });
    this._signed[url] = { path: result.path, expires: Date.now() + (SIGN_TTL_S - 300) * 1000 };
    return result.path;
  }

  _hydratePhotos() {
    for (const img of this._body.querySelectorAll("img[data-photo]")) {
      const url = img.getAttribute("data-photo");
      this._signedUrl(url)
        .then((src) => {
          img.src = src;
        })
        .catch(() => img.remove());
    }
  }

  // -- Record-weight form -------------------------------------------------

  _syncForm(batches) {
    if (!this._select) return;
    const current = this._select.value;
    this._select.textContent = "";
    for (const b of batches.filter((b) => b.status === "active")) {
      const option = document.createElement("option");
      option.value = b.id;
      option.textContent = b.name;
      this._select.appendChild(option);
    }
    if (current && batches.some((b) => b.id === current)) {
      this._select.value = current;
    }
    this._select.disabled = this._select.options.length === 0;
  }

  async _submit() {
    const batchId = this._select.value;
    const weight = parseFloat(this._weight.value);
    if (!batchId || isNaN(weight)) {
      this._status.textContent = "Pick a batch and enter a weight.";
      return;
    }
    const msg = { type: "curing_chamber/weigh_in", entry_id: this._entryId, batch_id: batchId, weight };
    const file = this._photo.files && this._photo.files[0];
    try {
      if (file) msg.photo = await this._downscale(file);
      this._status.textContent = "Saving…";
      await this._hass.callWS(msg);
      this._status.textContent = "Weigh-in recorded.";
      this._weight.value = "";
      this._photo.value = "";
    } catch (err) {
      this._status.textContent = `Error: ${err.message || err}`;
    }
  }

  /** Resize a photo in the browser (≤1600px, JPEG) and return a data URL. */
  _downscale(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        const scale = Math.min(1, PHOTO_MAX_PX / Math.max(img.width, img.height));
        const canvas = document.createElement("canvas");
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);
        canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL("image/jpeg", 0.8));
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("Unreadable image"));
      };
      img.src = url;
    });
  }

  // -- One-time DOM build -------------------------------------------------

  _build() {
    this._built = true;
    const card = document.createElement("ha-card");
    card.innerHTML = `
      <style>
        .header { padding: 12px 16px 4px; font-size: 1.2em; font-weight: 500; }
        .body { padding: 4px 16px 8px; }
        .empty { color: var(--secondary-text-color); padding: 8px 0; }
        .batch { border-top: 1px solid var(--divider-color); padding: 10px 0; }
        .batch-head { display: flex; justify-content: space-between; align-items: center; }
        .batch-name { font-weight: 500; }
        .badge { margin-left: 8px; font-size: .7em; color: var(--primary-color);
          border: 1px solid var(--primary-color); border-radius: 8px; padding: 1px 6px; }
        .status { font-size: .8em; text-transform: capitalize; color: var(--secondary-text-color); }
        .status-completed { color: var(--success-color, #43a047); }
        .status-archived { color: var(--disabled-text-color); }
        .batch-body { display: flex; gap: 12px; margin-top: 6px; }
        .thumb { width: 64px; height: 64px; object-fit: cover; border-radius: 8px;
          background: var(--divider-color); }
        .metrics { flex: 1; min-width: 0; }
        .spark { width: 100%; height: 48px; }
        .spark-line { fill: none; stroke: var(--primary-color); stroke-width: 2; }
        .target-line { stroke: var(--error-color, #e53935); stroke-dasharray: 4 3; stroke-width: 1; }
        .bar { height: 6px; background: var(--divider-color); border-radius: 3px; margin: 6px 0; overflow: hidden; }
        .bar-fill { height: 100%; background: var(--primary-color); }
        .row { display: flex; gap: 14px; flex-wrap: wrap; font-size: .85em; color: var(--secondary-text-color); }
        .row b { color: var(--primary-text-color); font-weight: 500; }
        .form { border-top: 1px solid var(--divider-color); padding: 10px 16px 14px;
          display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .form select, .form input[type=number] { padding: 6px; border-radius: 6px;
          border: 1px solid var(--divider-color); background: var(--card-background-color);
          color: var(--primary-text-color); }
        .form input[type=number] { width: 90px; }
        .form button { padding: 6px 12px; border: none; border-radius: 6px;
          background: var(--primary-color); color: var(--text-primary-color, #fff); cursor: pointer; }
        .form button:hover { opacity: .9; }
        .form-status { flex-basis: 100%; font-size: .8em; color: var(--secondary-text-color); }
      </style>
      <div class="header"></div>
      <div class="body"></div>
      <div class="form">
        <select class="cc-select"></select>
        <input class="cc-weight" type="number" step="0.1" placeholder="weight" />
        <input class="cc-photo" type="file" accept="image/*" capture="environment" />
        <button class="cc-submit" type="button">Record</button>
        <div class="form-status"></div>
      </div>`;
    this.innerHTML = "";
    this.appendChild(card);
    this._title = card.querySelector(".header");
    this._body = card.querySelector(".body");
    this._select = card.querySelector(".cc-select");
    this._weight = card.querySelector(".cc-weight");
    this._photo = card.querySelector(".cc-photo");
    this._status = card.querySelector(".form-status");
    card.querySelector(".cc-submit").addEventListener("click", () => this._submit());
  }

  _escape(text) {
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }
}

if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, CuringChamberCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TAG,
    name: "Curing Chamber Card",
    description: "Batches, drying curves, ETA and a weigh-in form for a curing chamber.",
  });
}
