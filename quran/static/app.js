const form = document.getElementById("searchForm");
const input = document.getElementById("query");
const broadEl = document.getElementById("broadMode");
const results = document.getElementById("results");

form.addEventListener("submit", (e) => {
  e.preventDefault();
  runSearch(input.value.trim());
});

broadEl.addEventListener("change", () => {
  const q = input.value.trim();
  if (q) runSearch(q);
});

async function runSearch(q) {
  if (!q) return;
  results.innerHTML = '<p class="empty">…</p>';
  const mode = broadEl.checked ? "contains" : "exact";
  let data;
  try {
    const r = await fetch(
      "/api/search?q=" + encodeURIComponent(q) + "&mode=" + mode
    );
    data = await r.json();
  } catch {
    results.innerHTML = '<p class="error">تعذّر الاتصال. حاول مرة أخرى.</p>';
    return;
  }
  render(data);
}

function render(data) {
  results.innerHTML = "";
  if (data.total === 0) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = `لا توجد نتائج للكلمة: ${data.query}`;
    results.appendChild(p);
    return;
  }

  // A. Top summary — in Arabic, with a collapsible surah dropdown.
  const sum = document.createElement("div");
  sum.className = "summary";
  const word = `«${data.query}»`;
  const modeLabel = data.mode === "contains" ? " (بحث موسّع)" : "";
  const surahsCount = data.by_surah.length;

  sum.innerHTML = `
    <ul>
      <li>
        <strong>عدد مرات ورود كلمة ${escapeHtml(word)}: ${data.total} مرة${modeLabel}</strong>
      </li>
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

  // B. Verse list
  for (const v of data.verses) {
    const a = document.createElement("article");
    a.className = "verse";
    const ref = document.createElement("div");
    ref.className = "ref";
    ref.textContent = `[${v.surah_en}: ${v.ayah}]`;
    const ay = document.createElement("div");
    ay.className = "ayah";
    ay.lang = "ar";
    ay.dir = "rtl";
    ay.textContent = v.text;
    a.append(ref, ay);
    results.appendChild(a);
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const params = new URLSearchParams(location.search);
const initial = params.get("q");
if (params.get("mode") === "contains") broadEl.checked = true;
if (initial) {
  input.value = initial;
  runSearch(initial);
}
