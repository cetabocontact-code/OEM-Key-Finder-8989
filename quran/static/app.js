"use strict";

const form = document.getElementById("searchForm");
const input = document.getElementById("query");
const results = document.getElementById("results");
const modeRadios = document.querySelectorAll('input[name="mode"]');
const recentEl = document.getElementById("recent");
const recentList = document.getElementById("recentList");
const recentClear = document.getElementById("recentClear");
const morphCard = document.getElementById("morphCard");

const RECENT_KEY = "quran.recent.v1";
const RECENT_MAX = 8;

// ---------- recent searches ---------------------------------------------

function getRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); }
  catch { return []; }
}
function pushRecent(q, mode) {
  if (!q) return;
  let list = getRecent().filter(it => !(it.q === q && it.mode === mode));
  list.unshift({ q, mode });
  list = list.slice(0, RECENT_MAX);
  localStorage.setItem(RECENT_KEY, JSON.stringify(list));
  renderRecent();
}
function renderRecent() {
  const list = getRecent();
  if (!list.length) { recentEl.hidden = true; return; }
  recentEl.hidden = false;
  recentList.innerHTML = "";
  for (const it of list) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "recent-chip";
    chip.textContent = it.q;
    chip.title = it.mode === "root" ? "جذر" : it.mode === "contains" ? "بحث موسّع" : "كلمة";
    chip.addEventListener("click", () => {
      input.value = it.q;
      setMode(it.mode);
      run();
    });
    recentList.appendChild(chip);
  }
}
recentClear.addEventListener("click", () => {
  localStorage.removeItem(RECENT_KEY);
  renderRecent();
});

// ---------- mode selection ---------------------------------------------

function currentMode() {
  for (const r of modeRadios) if (r.checked) return r.value;
  return "exact";
}
function setMode(m) {
  for (const r of modeRadios) r.checked = (r.value === m);
}
modeRadios.forEach(r => r.addEventListener("change", () => {
  if (input.value.trim()) run();
}));

// ---------- search ------------------------------------------------------

form.addEventListener("submit", (e) => { e.preventDefault(); run(); });

async function run() {
  const q = input.value.trim();
  if (!q) return;
  const mode = currentMode();
  results.innerHTML = '<p class="empty">…</p>';
  let data;
  try {
    const r = await fetch(`/api/search?q=${encodeURIComponent(q)}&mode=${mode}`);
    data = await r.json();
  } catch {
    results.innerHTML = '<p class="error">تعذّر الاتصال. حاول مرة أخرى.</p>';
    return;
  }
  render(data);
  if (data.total > 0) pushRecent(q, mode);
  history.replaceState(null, "", `?q=${encodeURIComponent(q)}&mode=${mode}`);
}

function render(data) {
  results.innerHTML = "";
  if (data.total === 0) {
    renderNoResults(data);
    return;
  }

  // A. Top summary
  const sum = document.createElement("div");
  sum.className = "summary";
  const word = `«${escapeHtml(data.query)}»`;
  const modeLabel =
    data.mode === "root" ? " (بحث بالجذر)" :
    data.mode === "contains" ? " (بحث موسّع)" : "";
  const surahsCount = data.by_surah.length;
  sum.innerHTML = `
    <ul>
      <li><strong>عدد مرات ورود ${word}: ${data.total} مرة${modeLabel}</strong></li>
      <li>وردت في ${data.total_verses} آية، موزّعة على ${surahsCount} سورة.</li>
    </ul>
    <details class="surah-dropdown">
      <summary>عرض السور التي وردت فيها الكلمة (${surahsCount})</summary>
      <ol class="surah-list"></ol>
    </details>
  `;
  const ol = sum.querySelector(".surah-list");
  for (const s of data.by_surah) {
    const li = document.createElement("li");
    li.innerHTML =
      `<span class="surah-name">${escapeHtml(s.name_ar)}</span>` +
      ` <span class="surah-en" dir="ltr">${escapeHtml(s.name_en)}</span>` +
      ` <span class="surah-count">${s.count}</span>`;
    ol.appendChild(li);
  }
  results.appendChild(sum);

  // B. Verses with clickable, highlighted words
  for (const v of data.verses) {
    const a = document.createElement("article");
    a.className = "verse";
    a.innerHTML = `
      <div class="verse-head">
        <span class="ref">[${escapeHtml(v.surah_en)}: ${v.ayah}]</span>
        <div class="verse-actions">
          <button class="copy-btn" type="button" title="نسخ الآية">نسخ</button>
          <button class="link-btn" type="button" title="نسخ الرابط">رابط</button>
        </div>
      </div>
      <div class="ayah" lang="ar" dir="rtl">${v.text_html}</div>
    `;
    a.querySelector(".copy-btn").addEventListener("click", (e) => {
      const text = `${v.text}  [${v.surah_en} ${v.ayah}]`;
      navigator.clipboard.writeText(text).then(() => flash(e.target, "تم النسخ"));
    });
    a.querySelector(".link-btn").addEventListener("click", (e) => {
      const url = `${location.origin}${location.pathname}?q=${encodeURIComponent(data.query)}&mode=${data.mode}#${v.surah_id}-${v.ayah}`;
      navigator.clipboard.writeText(url).then(() => flash(e.target, "تم النسخ"));
    });
    // Click any word to see morphology card
    a.querySelectorAll(".w").forEach(span => {
      span.addEventListener("click", () => openMorph(span.dataset.w));
    });
    results.appendChild(a);
  }
}

function renderNoResults(data) {
  const wrap = document.createElement("div");
  wrap.className = "suggestions";
  const head = document.createElement("p");
  head.textContent = `لا توجد نتائج للكلمة: ${data.query}`;
  wrap.appendChild(head);
  if (data.suggestions && data.suggestions.length) {
    const hint = document.createElement("p");
    hint.textContent = "هل تقصد:";
    wrap.appendChild(hint);
    const chips = document.createElement("div");
    chips.className = "chips";
    for (const s of data.suggestions) {
      const c = document.createElement("button");
      c.type = "button";
      c.className = "chip";
      c.textContent = s;
      c.addEventListener("click", () => {
        input.value = s;
        // Keep the current mode; root suggestions are roots, word suggestions are tokens.
        run();
      });
      chips.appendChild(c);
    }
    wrap.appendChild(chips);
  }
  results.appendChild(wrap);
}

function flash(btn, text) {
  const orig = btn.textContent;
  btn.textContent = text;
  btn.classList.add("copied");
  setTimeout(() => { btn.textContent = orig; btn.classList.remove("copied"); }, 1500);
}

// ---------- morphology popover -----------------------------------------

let backdrop = null;

async function openMorph(word) {
  let info;
  try {
    const r = await fetch(`/api/morph?w=${encodeURIComponent(word)}`);
    info = await r.json();
  } catch { return; }
  morphCard.querySelector(".morph-word").textContent = info.word || word;
  morphCard.querySelector(".morph-root").textContent = info.root || "—";
  morphCard.querySelector(".morph-lemma").textContent = info.lemma || "—";
  morphCard.querySelector(".morph-pos").textContent = info.pos ? POS_AR[info.pos] || info.pos : "—";
  const btn = morphCard.querySelector(".morph-search-root");
  if (info.root) {
    btn.disabled = false;
    btn.onclick = () => {
      input.value = info.root;
      setMode("root");
      closeMorph();
      run();
    };
  } else {
    btn.disabled = true;
    btn.onclick = null;
  }
  morphCard.hidden = false;
  if (!backdrop) {
    backdrop = document.createElement("div");
    backdrop.className = "morph-backdrop";
    backdrop.addEventListener("click", closeMorph);
    document.body.appendChild(backdrop);
  }
  backdrop.hidden = false;
}

function closeMorph() {
  morphCard.hidden = true;
  if (backdrop) backdrop.hidden = true;
}
morphCard.querySelector(".morph-close").addEventListener("click", closeMorph);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !morphCard.hidden) closeMorph();
});

// Arabic labels for the most common QAC POS codes. Anything else
// shows the raw code — no fabricated meanings.
const POS_AR = {
  N: "اسم", PN: "اسم علم", V: "فعل", ADJ: "صفة", PRON: "ضمير",
  DEM: "اسم إشارة", REL: "اسم موصول", T: "ظرف زمان", LOC: "ظرف مكان",
  P: "حرف جر", CONJ: "حرف عطف", REM: "حرف استئناف", SUB: "حرف توكيد",
  NEG: "حرف نفي", INTG: "حرف استفهام", VOC: "حرف نداء", INT: "حرف تنبيه",
  EMPH: "حرف توكيد", FUT: "حرف استقبال", PRP: "حرف تعليل",
  COND: "حرف شرط", RSLT: "حرف جواب", ACC: "حرف نصب", AVR: "حرف ردع",
  RES: "حرف حصر", DET: "حرف تعريف", EQ: "حرف تسوية",
  CIRC: "حرف حال", EXP: "أداة استثناء",
};

// Escape helper
function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ---------- bootstrap ---------------------------------------------------

renderRecent();
const params = new URLSearchParams(location.search);
const initial = params.get("q");
const initMode = params.get("mode");
if (initMode) setMode(initMode);
if (initial) { input.value = initial; run(); }
