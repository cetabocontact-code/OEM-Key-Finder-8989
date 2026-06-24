"use strict";

const REFRESH_MS = 3 * 60 * 60 * 1000; // 3 hours

const state = {
  board: null,
  category: "",
  query: "",
};

/* ---------- helpers ---------- */

function el(id) {
  return document.getElementById(id);
}

function catLabel(id) {
  if (!id) return "All capabilities";
  const found = (state.board?.categories || []).find((c) => c.id === id);
  return found ? found.label : id;
}

function catColor(id) {
  const found = (state.board?.categories || []).find((c) => c.id === id);
  return found ? found.color : "#2b2f33";
}

function effectiveScore(company) {
  const scores = company.scores || {};
  if (state.category) return Number(scores[state.category] || 0);
  return Math.max(0, ...Object.values(scores).map(Number));
}

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch (e) {
    return iso;
  }
}

function countdown(iso) {
  if (!iso) return "—";
  const ms = new Date(iso).getTime() - Date.now();
  if (Number.isNaN(ms)) return "—";
  if (ms <= 0) return "due now";
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  return h > 0 ? `in ${h}h ${m}m` : `in ${m}m`;
}

/* ---------- data ---------- */

async function loadBoard() {
  const res = await fetch("/api/ai_companies");
  state.board = await res.json();
  buildChips();
  buildLegend();
  renderSources();
  applyFilter(); // also logs activity + renders bubbles
}

/* POST a search so the Activity tab updates every time we filter/search. */
async function applyFilter() {
  let payload;
  try {
    const res = await fetch("/api/ai_search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: state.query, category: state.category }),
    });
    payload = await res.json();
  } catch (e) {
    payload = null;
  }

  const companies =
    payload && Array.isArray(payload.results)
      ? payload.results
      : (state.board?.companies || []);

  renderBubbles(companies);
  renderStatus(companies);
  if (payload && payload.activity) renderActivity(payload.activity);
  renderUpdatePill();
}

/* ---------- chips / filters ---------- */

function buildChips() {
  const row = el("filter-row");
  // keep search input + All chip (first two), drop the rest
  [...row.querySelectorAll(".chip")].forEach((c, i) => {
    if (i > 0) c.remove();
  });
  (state.board?.categories || []).forEach((cat) => {
    const btn = document.createElement("button");
    btn.className = "chip";
    btn.type = "button";
    btn.dataset.cat = cat.id;
    btn.textContent = cat.label;
    row.appendChild(btn);
  });

  row.addEventListener("click", (ev) => {
    const chip = ev.target.closest(".chip");
    if (!chip) return;
    state.category = chip.dataset.cat || "";
    [...row.querySelectorAll(".chip")].forEach((c) => {
      const on = (c.dataset.cat || "") === state.category;
      c.classList.toggle("active", on);
      c.style.background = on ? catColor(c.dataset.cat || "") : "#fff";
      c.style.color = on ? "#fff" : "";
      c.style.borderColor = on ? "transparent" : "";
    });
    applyFilter();
  });

  const search = el("board-search");
  let timer = null;
  search.addEventListener("input", () => {
    state.query = search.value;
    clearTimeout(timer);
    timer = setTimeout(applyFilter, 280);
  });
}

function buildLegend() {
  const box = el("legend-cats");
  box.innerHTML = "";
  (state.board?.categories || []).forEach((cat) => {
    const line = document.createElement("div");
    line.className = "key-line";
    line.innerHTML =
      `<span class="swatch" style="width:14px;height:14px;background:${cat.color}"></span> ${cat.label}`;
    box.appendChild(line);
  });
}

/* ---------- bubble field ---------- */

function renderBubbles(companies) {
  const field = el("bubble-field");
  field.innerHTML = "";
  const W = field.clientWidth || 900;
  const H = field.clientHeight || 520;

  if (!companies.length) {
    const e = document.createElement("div");
    e.className = "field-empty";
    e.textContent = "No companies match this filter.";
    field.appendChild(e);
    return;
  }

  const scored = companies
    .map((c) => ({ c, s: effectiveScore(c) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s);

  if (!scored.length) {
    const e = document.createElement("div");
    e.className = "field-empty";
    e.textContent = "No scored companies in this capability.";
    field.appendChild(e);
    return;
  }

  // diameter scales with score; shrink when crowded
  const crowd = Math.min(1, 9 / scored.length);
  const minD = 54 * Math.max(0.7, crowd);
  const maxD = 150 * Math.max(0.72, crowd);
  const top = scored[0].s;
  const bottom = scored[scored.length - 1].s;
  const span = Math.max(1, top - bottom);

  const placed = [];
  scored.forEach(({ c, s }, idx) => {
    const d = minD + ((s - bottom) / span) * (maxD - minD);
    const r = d / 2;
    const pos = placePos(r, W, H, placed, idx);
    placed.push({ x: pos.x, y: pos.y, r });

    const a = document.createElement("a");
    a.className = "bubble";
    a.href = c.official_url || "#";
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.style.width = d + "px";
    a.style.height = d + "px";
    a.style.left = pos.x - r + "px";
    a.style.top = pos.y - r + "px";
    a.style.background =
      `radial-gradient(circle at 32% 28%, ${lighten(c.color)}, ${c.color})`;
    a.title = `${c.name} — ${catLabel(state.category)}: ${s}\nModels: ${(c.models || []).join(", ")}\nOpen ${c.official_url}`;

    const nameSize = Math.max(10, Math.min(17, d / 6));
    a.innerHTML =
      `<span class="b-name" style="font-size:${nameSize}px">${c.name}</span>` +
      `<span class="b-score" style="font-size:${Math.max(9, nameSize - 3)}px">${s}</span>` +
      (c.verified ? `<span class="b-verified">✓ verified</span>` : "");
    field.appendChild(a);
  });
}

function placePos(r, W, H, placed, idx) {
  const pad = 6;
  // try several candidate spots, avoid overlaps
  for (let attempt = 0; attempt < 220; attempt++) {
    const x = r + pad + Math.random() * (W - 2 * (r + pad));
    const y = r + pad + Math.random() * (H - 2 * (r + pad));
    let ok = true;
    for (const p of placed) {
      const dx = p.x - x;
      const dy = p.y - y;
      if (Math.hypot(dx, dy) < p.r + r + 4) {
        ok = false;
        break;
      }
    }
    if (ok) return { x, y };
  }
  // fallback: rough grid
  const cols = Math.max(1, Math.floor(W / (r * 2 + 12)));
  const gx = (idx % cols) * (r * 2 + 12) + r + pad;
  const gy = Math.floor(idx / cols) * (r * 2 + 12) + r + pad;
  return { x: Math.min(gx, W - r), y: Math.min(gy, H - r) };
}

function lighten(hex) {
  const h = hex.replace("#", "");
  if (h.length !== 6) return hex;
  const num = parseInt(h, 16);
  const r = Math.min(255, ((num >> 16) & 255) + 60);
  const g = Math.min(255, ((num >> 8) & 255) + 60);
  const b = Math.min(255, (num & 255) + 60);
  return `rgb(${r},${g},${b})`;
}

/* ---------- status / legend ---------- */

function renderStatus(companies) {
  const scored = companies
    .map((c) => ({ c, s: effectiveScore(c) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s);
  el("stat-count").textContent = scored.length;
  el("stat-leader").textContent = scored.length
    ? `${scored[0].c.name} (${scored[0].s})`
    : "—";
  el("board-sub").textContent =
    `Filter: ${catLabel(state.category)}${state.query ? ` · "${state.query}"` : ""}`;
}

function renderUpdatePill() {
  const meta = state.board?.meta || {};
  el("update-pill").textContent =
    `Updated ${fmtTime(meta.last_updated)} · next ${countdown(meta.next_update)}`;
  el("stat-next").textContent = countdown(meta.next_update);
  el("stat-feed").textContent = meta.last_updated ? "live" : "offline";
  el("stat-feed").className = meta.last_updated ? "status-good" : "status-warn";
}

/* ---------- activity ---------- */

function renderActivity(activity) {
  const body = el("activity-body");
  body.innerHTML = "";
  if (!activity || !activity.length) {
    body.innerHTML = `<tr><td colspan="5" class="empty">No searches yet.</td></tr>`;
    return;
  }
  activity.forEach((a) => {
    const tr = document.createElement("tr");
    const names = (a.results || []).slice(0, 6).join(", ") +
      ((a.results || []).length > 6 ? "…" : "");
    tr.innerHTML =
      `<td>${fmtTime(a.searched_at)}</td>` +
      `<td>${a.query ? escapeHtml(a.query) : "—"}</td>` +
      `<td>${a.category_label || a.category || "All"}</td>` +
      `<td>${a.result_count}</td>` +
      `<td>${escapeHtml(names) || "—"}</td>`;
    body.appendChild(tr);
  });
}

async function loadActivity() {
  try {
    const res = await fetch("/api/ai_activity");
    const data = await res.json();
    renderActivity(data.activity || []);
  } catch (e) {
    /* ignore */
  }
}

/* ---------- sources ---------- */

function renderSources() {
  const meta = state.board?.meta || {};
  el("sources-note").textContent = meta.note || "";
  el("sources-updated").textContent = meta.last_updated
    ? `Last pulled ${fmtTime(meta.last_updated)}`
    : "";
  const list = el("sources-list");
  list.innerHTML = "";
  (meta.sources || []).forEach((s) => {
    const row = document.createElement("div");
    row.className = "key-line";
    row.innerHTML =
      `<span class="verified-tag">${s.verified ? "✓ verified" : "source"}</span>` +
      `<a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.name}</a>` +
      `<span class="muted">— ${(s.covers || []).join(", ")}</span>`;
    list.appendChild(row);
  });
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (ch) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch])
  );
}

/* ---------- tabs ---------- */

function initTabs() {
  document.querySelectorAll(".tab-button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      document
        .querySelectorAll(".tab-button")
        .forEach((b) => b.classList.toggle("active", b === btn));
      document.querySelectorAll(".tab-panel").forEach((p) => {
        p.classList.toggle("active", p.id === `${tab}-panel`);
      });
      if (tab === "activity") loadActivity();
    });
  });
}

/* ---------- boot ---------- */

initTabs();
loadBoard();

// keep the "next pull" countdown ticking
setInterval(renderUpdatePill, 60 * 1000);
// auto-update from verified resources every 3 hours
setInterval(loadBoard, REFRESH_MS);
// re-pack bubbles on resize
let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(applyFilter, 250);
});
