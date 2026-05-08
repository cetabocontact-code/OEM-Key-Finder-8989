const state = {
  currentTab: "search",
  history: [],
  makes: [],
  latest: null,
  detectTimer: null,
};

const tabs = document.querySelectorAll(".tab-button");
const panels = {
  search: document.querySelector("#search-panel"),
  history: document.querySelector("#history-panel"),
  subscribe: document.querySelector("#subscribe-panel"),
  makes: document.querySelector("#makes-panel"),
};
const form = document.querySelector("#search-form");
const vinInput = document.querySelector("#vin-input");
const makeOverride = document.querySelector("#make-override");
const offlineInput = document.querySelector("#offline-input");
const searchButton = document.querySelector("#search-button");
const statusBox = document.querySelector("#status");
const resultBox = document.querySelector("#result");
const historyBody = document.querySelector("#history-body");
const refreshHistory = document.querySelector("#refresh-history");
const detectedPill = document.querySelector("#detected-pill");
const counter = document.querySelector("#counter");
const makesGrid = document.querySelector("#makes-grid");
const makeCount = document.querySelector("#make-count");
const subscribeForm = document.querySelector("#subscribe-form");
const subscribeEmail = document.querySelector("#subscribe-email");
const subscribeButton = document.querySelector("#subscribe-button");
const subscribeStatus = document.querySelector("#subscribe-status");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
}

function setTab(tabName) {
  state.currentTab = tabName;
  tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === tabName));
  Object.entries(panels).forEach(([key, panel]) => panel.classList.toggle("active", key === tabName));
  if (tabName === "history") loadHistory();
}

function formatVehicle(item) {
  return [item.year, item.make, item.model, item.trim].filter(Boolean).join(" ");
}

function confidenceLabel(confidence) {
  if (!confidence) return "Unmatched";
  if (confidence.includes("candidate")) return "Candidate";
  if (confidence.includes("rule")) return "YMM rule";
  if (confidence.includes("confirmed")) return "Confirmed";
  return confidence;
}

function partKind(part) {
  const text = `${part.name || ""} ${part.part || ""}`.toLowerCase();
  if (text.includes("emergency") || text.includes("blank")) return "Emergency key";
  if (text.includes("transmitter") || text.includes("remote") || text.includes("fob") || text.includes("smart key")) return "Remote transmitter";
  if (text.includes("blade")) return "Key blade";
  return "Key part";
}

function renderMakes() {
  makeCount.textContent = `${state.makes.length} makes`;
  makesGrid.innerHTML = state.makes
    .map((make) => {
      return `
        <button class="make-card" type="button" data-make="${escapeHtml(make.id)}" style="--make-color:${escapeHtml(make.color)}">
          <span class="make-dot"></span>
          <strong>${escapeHtml(make.label)}</strong>
          <small>${escapeHtml(make.seed || "Profile ready")}</small>
        </button>
      `;
    })
    .join("");
}

async function loadMakes() {
  const response = await fetch("/api/makes");
  const payload = await response.json();
  state.makes = payload.makes || [];
  makeOverride.innerHTML = `<option value="">Auto detect</option>`;
  for (const make of state.makes) {
    const option = document.createElement("option");
    option.value = make.id;
    option.textContent = make.label;
    makeOverride.appendChild(option);
  }
  renderMakes();
}

async function detectVin() {
  const vin = vinInput.value.trim();
  if (vin.length < 3) {
    detectedPill.textContent = "Enter VIN to detect make";
    return;
  }
  const response = await fetch("/api/detect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vin }),
  });
  const detected = await response.json();
  if (detected.makeLabel) {
    detectedPill.textContent = `${detected.makeLabel} detected from ${detected.detectedWmi}`;
  } else {
    detectedPill.textContent = "Make not detected. Use override.";
  }
}

function renderParts(parts) {
  if (!parts.length) {
    return `<div class="empty">No part number returned.</div>`;
  }

  return `<div class="part-list">${parts
    .map((part) => {
      const replaces = part.replaces?.length
        ? `<div class="pill-row">${part.replaces.map((value) => `<span class="pill">Replaces ${escapeHtml(value)}</span>`).join("")}</div>`
        : "";
      const superseded = part.supersededBy?.length
        ? `<div class="pill-row">${part.supersededBy.map((value) => `<span class="pill">Superseded by ${escapeHtml(value)}</span>`).join("")}</div>`
        : "";
      const verify = part.verificationRequired ? `<span class="verify">VIN fitment check required before ordering</span>` : `<span class="confirmed">VIN/YMM fitment evidence stored</span>`;
      const source = part.viewUrl ? `<a class="source-link" href="${escapeHtml(part.viewUrl)}" target="_blank" rel="noreferrer">Open source</a>` : "";
      const kind = partKind(part);
      return `
        <article class="part-item">
          <div class="part-top">
            <div>
              <div class="part-kind">${escapeHtml(kind)}</div>
              <div class="part-number">${escapeHtml(part.part)}</div>
              <div class="part-meta">${escapeHtml(part.name || kind)}</div>
            </div>
            <button class="small-button" type="button" data-copy="${escapeHtml(part.part)}">Copy</button>
          </div>
          ${replaces}
          ${superseded}
          <div class="confidence-line">${verify}</div>
          ${part.notes ? `<p class="notes">${escapeHtml(part.notes)}</p>` : ""}
          ${source}
        </article>
      `;
    })
    .join("")}</div>`;
}

async function subscribe(email) {
  subscribeButton.disabled = true;
  subscribeStatus.textContent = "Saving...";
  subscribeStatus.classList.remove("error");
  try {
    const response = await fetch("/api/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Could not save email");
    subscribeStatus.textContent = payload.message || "Subscribed.";
    subscribeEmail.value = "";
  } catch (error) {
    subscribeStatus.textContent = error.message;
    subscribeStatus.classList.add("error");
  } finally {
    subscribeButton.disabled = false;
  }
}

function renderResult(data) {
  state.latest = data;
  const decode = data.decode || {};
  resultBox.innerHTML = `
    <div class="result-grid">
      <section class="panel vehicle-panel">
        <div class="vehicle-title">${escapeHtml(data.vehicle || data.makeLabel || "Vehicle")}</div>
        <dl class="kv">
          <div><dt>VIN</dt><dd>${escapeHtml(data.vin)}</dd></div>
          <div><dt>Year</dt><dd>${escapeHtml(decode.ModelYear || "")}</dd></div>
          <div><dt>Make</dt><dd>${escapeHtml(decode.Make || data.makeLabel || "")}</dd></div>
          <div><dt>Model</dt><dd>${escapeHtml(decode.Model || "")}</dd></div>
          <div><dt>Trim</dt><dd>${escapeHtml(decode.Trim || "Not listed")}</dd></div>
          <div><dt>Decode</dt><dd>${data.cached ? "Cache" : "Live/cache"}</dd></div>
        </dl>
        <div class="actions">
          <button class="ghost-button" id="copy-all" type="button">Copy All Parts</button>
          <button class="ghost-button" id="export-csv" type="button">Export CSV</button>
        </div>
      </section>
      <section class="panel">
        <div class="parts-head">
          <h2>Key Parts</h2>
          <span class="badge">${data.count} part${data.count === 1 ? "" : "s"}</span>
          <span class="badge secondary-badge">${escapeHtml(confidenceLabel(data.confidence))}</span>
        </div>
        ${renderParts(data.parts || [])}
      </section>
    </div>
  `;
}

function renderHistory(items) {
  if (!items.length) {
    historyBody.innerHTML = `<tr><td colspan="5" class="empty">No searches yet.</td></tr>`;
    return;
  }

  historyBody.innerHTML = items
    .map((item) => {
      return `
        <tr>
          <td><button type="button" data-vin="${escapeHtml(item.vin)}">${escapeHtml(item.vin)}</button></td>
          <td>${escapeHtml(formatVehicle(item))}</td>
          <td>${escapeHtml(item.key_part_numbers || "NO_PART")}</td>
          <td>${escapeHtml(confidenceLabel(item.confidence))}</td>
          <td>${escapeHtml(item.searched_at || "")}</td>
        </tr>
      `;
    })
    .join("");
}

async function loadHistory() {
  const response = await fetch("/api/history?limit=50");
  const payload = await response.json();
  state.history = payload.items || payload.history || [];
  renderHistory(state.history);
}

async function searchVin(vin, offline) {
  searchButton.disabled = true;
  setStatus("Searching OEM key data...");
  try {
    const response = await fetch("/api/lookup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vin, make: makeOverride.value || undefined, offline }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Search failed");
    renderResult(payload);
    await loadHistory();
    setStatus(payload.parts?.some((part) => part.verificationRequired) ? "Candidate returned. Verify VIN fitment before ordering." : "Confirmed match returned.");
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    searchButton.disabled = false;
  }
}

function partsToCsv(data) {
  const rows = [["VIN", "Vehicle", "Part Number", "Description", "Confidence", "Source"]];
  for (const part of data.parts || []) rows.push([data.vin, data.vehicle, part.part, part.name, part.confidence, part.viewUrl]);
  return rows.map((row) => row.map((cell) => `"${String(cell ?? "").replaceAll('"', '""')}"`).join(",")).join("\n");
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const ok = document.execCommand("copy");
    textarea.remove();
    return ok;
  }
}

tabs.forEach((tab) => tab.addEventListener("click", () => setTab(tab.dataset.tab)));

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const vin = vinInput.value.trim().toUpperCase();
  vinInput.value = vin;
  searchVin(vin, offlineInput.checked);
});

vinInput.addEventListener("input", () => {
  vinInput.value = vinInput.value.toUpperCase().replace(/[^A-HJ-NPR-Z0-9]/g, "").slice(0, 17);
  counter.textContent = `${vinInput.value.length}/17`;
  window.clearTimeout(state.detectTimer);
  state.detectTimer = window.setTimeout(detectVin, 250);
});

makesGrid.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-make]");
  if (!button) return;
  makeOverride.value = button.dataset.make;
  setTab("search");
});

historyBody.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-vin]");
  if (!button) return;
  vinInput.value = button.dataset.vin;
  counter.textContent = "17/17";
  setTab("search");
  searchVin(button.dataset.vin, true);
});

resultBox.addEventListener("click", async (event) => {
  const copyButton = event.target.closest("button[data-copy]");
  if (copyButton) {
    const ok = await copyText(copyButton.dataset.copy);
    copyButton.textContent = ok ? "Copied" : "Copy failed";
    window.setTimeout(() => (copyButton.textContent = "Copy"), 900);
    return;
  }
  if (event.target.id === "copy-all" && state.latest) {
    await copyText((state.latest.parts || []).map((part) => part.part).join("\n"));
  }
  if (event.target.id === "export-csv" && state.latest) {
    const blob = new Blob([partsToCsv(state.latest)], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `oem-key-${state.latest.vin}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }
});

refreshHistory.addEventListener("click", loadHistory);

subscribeForm.addEventListener("submit", (event) => {
  event.preventDefault();
  subscribe(subscribeEmail.value.trim());
});

Promise.all([loadMakes(), loadHistory()]).catch((error) => setStatus(error.message, true));
