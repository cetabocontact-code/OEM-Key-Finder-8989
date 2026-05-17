const form = document.getElementById("searchForm");
const input = document.getElementById("query");
const results = document.getElementById("results");
const tplSummary = document.getElementById("tpl-summary");
const tplVerse = document.getElementById("tpl-verse");

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = input.value.trim();
  if (!q) return;
  runSearch(q);
});

async function runSearch(q) {
  results.innerHTML = '<p class="empty">…</p>';
  let data;
  try {
    const r = await fetch("/api/search?q=" + encodeURIComponent(q));
    data = await r.json();
  } catch (err) {
    results.innerHTML = '<p class="error">Network error. Please try again.</p>';
    return;
  }
  render(data);
}

function render(data) {
  results.innerHTML = "";
  if (data.total === 0) {
    const p = document.createElement("p");
    p.className = "empty";
    p.lang = "ar";
    p.dir = "rtl";
    p.textContent = `لا توجد نتائج للكلمة: ${data.query}`;
    results.appendChild(p);
    return;
  }

  // A. Top summary
  const summary = tplSummary.content.cloneNode(true);
  const word = `"${data.query}"`;
  summary.querySelector(".total").textContent =
    `Total occurrences of ${word}: ${data.total} ${data.total === 1 ? "time" : "times"}`;
  summary.querySelector(".surah-list").textContent =
    data.by_surah.map((s) => `${s.name_en} (${s.count})`).join(", ") + ".";
  results.appendChild(summary);

  // B. Verse list
  for (const v of data.verses) {
    const node = tplVerse.content.cloneNode(true);
    node.querySelector(".ref").textContent = `[${v.surah_en}: ${v.ayah}]`;
    node.querySelector(".ayah").textContent = v.text;
    results.appendChild(node);
  }
}

// Allow ?q= deep links
const params = new URLSearchParams(location.search);
const initial = params.get("q");
if (initial) {
  input.value = initial;
  runSearch(initial);
}
