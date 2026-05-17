#!/usr/bin/env python3
"""Quranic word-search desktop app — single file, pure stdlib.

Just run it:

    python3 quran_search.py

What happens:

  1. On first launch it downloads the Quran dataset (~2.7 MB) from
     GitHub and caches it next to this script as `quran_data.json`.
  2. It starts a tiny local web server (default port 5000, or the next
     free port) and opens your browser automatically.
  3. Type any Arabic word and you get the verses that contain it, with
     a top summary of total occurrences per surah.

No pip, no dependencies, no internet needed after the first launch.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import socket
import sys
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
DATA_FILE = SCRIPT_DIR / "quran_data.json"

# Two parallel editions, fetched once and merged into a single local JSON.
UTHMANI_URL = (
    "https://raw.githubusercontent.com/fawazahmed0/quran-api/1/"
    "editions/ara-quranuthmanihaf.min.json"
)
SPELLED_URL = (
    "https://raw.githubusercontent.com/fawazahmed0/quran-api/1/"
    "editions/ara-quranspelled.min.json"
)
META_URL = "https://raw.githubusercontent.com/risan/quran-json/main/dist/quran.json"

DEFAULT_PORT = 5000

# ---------------------------------------------------------------------------
# Dataset bootstrap
# ---------------------------------------------------------------------------


def _fetch(url: str) -> bytes:
    print(f"  fetching {url}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def ensure_dataset() -> list[dict]:
    if DATA_FILE.exists():
        with DATA_FILE.open(encoding="utf-8") as f:
            return json.load(f)

    print("First run: downloading Quran dataset (~3 MB)...", file=sys.stderr)
    uthmani = json.loads(_fetch(UTHMANI_URL))["quran"]
    spelled = json.loads(_fetch(SPELLED_URL))["quran"]
    meta = json.loads(_fetch(META_URL))

    spelled_idx = {(v["chapter"], v["verse"]): v["text"] for v in spelled}
    surahs = []
    for m in meta:
        sid = m["id"]
        verses = sorted(
            (
                {
                    "n": v["verse"],
                    "t": v["text"],
                    "s": spelled_idx[(sid, v["verse"])],
                }
                for v in uthmani
                if v["chapter"] == sid
            ),
            key=lambda x: x["n"],
        )
        surahs.append(
            {
                "id": sid,
                "name_ar": m["name"],
                "name_en": m["transliteration"],
                "type": m["type"],
                "total": m["total_verses"],
                "verses": verses,
            }
        )

    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(surahs, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Saved {DATA_FILE.name}", file=sys.stderr)
    return surahs


# ---------------------------------------------------------------------------
# Arabic normalization + search
# ---------------------------------------------------------------------------

# All Arabic ranges are written as \uXXXX escapes so editor bidi
# reordering can\'t reshuffle the character class.
#   U+0610-061A  honorific marks
#   U+064B-065F  tashkeel
#   U+0670       superscript (dagger) alef
#   U+06D6-06ED  Quranic annotation marks
#   U+08F0-08FF  extended Arabic marks
#   U+0640       tatweel
_DIACRITICS = re.compile(
    "[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u08F0-\u08FF\u0640]"
)
# U+0622 alef-madda, U+0623 alef-hamza-above, U+0625 alef-hamza-below,
# U+0671 alef-wasla, U+0672, U+0673, U+0675 — all fold to plain alef U+0627.
_ALEFS = re.compile("[\u0622\u0623\u0625\u0671\u0672\u0673\u0675]")
# Keep only Arabic letters U+0621..U+064A when tokenizing.
_TOKEN_STRIP = re.compile("[^\u0621-\u064A]+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _DIACRITICS.sub("", text)
    text = _ALEFS.sub("\u0627", text)              # → alef
    text = (
        text.replace("\u0649", "\u064A")     # alef maksura → ya
        .replace("\u0629", "\u0647")         # ta marbuta  → ha
        .replace("\u0624", "\u0648")         # waw-hamza   → waw
        .replace("\u0626", "\u064A")         # ya-hamza    → ya
    )
    return re.sub(r"\s+", " ", text).strip()


def tokenize(normalized: str) -> list[str]:
    return [
        t for t in (_TOKEN_STRIP.sub("", w) for w in normalized.split(" ")) if t
    ]


class Index:
    def __init__(self, surahs: list[dict]) -> None:
        self.verses: list[dict] = []
        self.inv: dict[str, list[int]] = {}
        for surah in surahs:
            for v in surah["verses"]:
                idx = len(self.verses)
                toks = tokenize(normalize(v["s"]))
                self.verses.append(
                    {
                        "surah_id": surah["id"],
                        "surah_ar": surah["name_ar"],
                        "surah_en": surah["name_en"],
                        "ayah": v["n"],
                        "text": v["t"],
                        "tokens": toks,
                    }
                )
                for t in set(toks):
                    self.inv.setdefault(t, []).append(idx)

    def search(self, query: str, mode: str = "exact") -> dict:
        q_tokens = tokenize(normalize(query))
        empty = {
            "query": query, "mode": mode,
            "total": 0, "total_verses": 0,
            "by_surah": [], "verses": [],
        }
        if not q_tokens:
            return empty

        # Build per-token "match forms". For contains mode, queries that
        # start with the definite article ال also match the lām-elision
        # form (لـ + الـ drops the alif): الله → also matches لله.
        forms_per_qt: list[list[str]] = []
        for qt in q_tokens:
            forms = [qt]
            if mode == "contains" and qt.startswith("ال") and len(qt) > 2:
                forms.append("ل" + qt[2:])
            forms_per_qt.append(forms)

        if mode == "contains":
            token_matches: list[set[int]] = []
            for forms in forms_per_qt:
                vids: set[int] = set()
                for token, ids in self.inv.items():
                    if any(f in token for f in forms):
                        vids.update(ids)
                token_matches.append(vids)
            hit_ids = sorted(set.intersection(*token_matches)) if token_matches else []
        else:
            candidates = self.inv.get(q_tokens[0], [])
            if len(q_tokens) > 1:
                rest = [set(self.inv.get(t, ())) for t in q_tokens[1:]]
                candidates = [i for i in candidates if all(i in s for s in rest)]
            hit_ids = [
                i for i in candidates
                if _contains_phrase(self.verses[i]["tokens"], q_tokens)
            ]

        hits: list[dict] = []
        by_surah: dict[int, dict] = {}
        total_occ = 0
        for idx in hit_ids:
            v = self.verses[idx]
            occ = _count_in_verse(v["tokens"], q_tokens, mode, forms_per_qt)
            if occ == 0:
                continue
            total_occ += occ
            hits.append(
                {
                    "surah_id": v["surah_id"],
                    "surah_ar": v["surah_ar"],
                    "surah_en": v["surah_en"],
                    "ayah": v["ayah"],
                    "text": v["text"],
                    "occurrences": occ,
                }
            )
            s = by_surah.setdefault(
                v["surah_id"],
                {
                    "id": v["surah_id"],
                    "name_ar": v["surah_ar"],
                    "name_en": v["surah_en"],
                    "count": 0,
                    "verses": 0,
                },
            )
            s["count"] += occ
            s["verses"] += 1

        hits.sort(key=lambda h: (h["surah_id"], h["ayah"]))
        return {
            "query": query,
            "mode": mode,
            "total": total_occ,
            "total_verses": len(hits),
            "by_surah": sorted(by_surah.values(), key=lambda s: s["id"]),
            "verses": hits,
        }


def _count_in_verse(
    verse_tokens: list[str],
    q_tokens: list[str],
    mode: str,
    forms_per_qt: list[list[str]],
) -> int:
    if len(q_tokens) == 1:
        forms = forms_per_qt[0]
        if mode == "contains":
            return sum(1 for t in verse_tokens if any(f in t for f in forms))
        return sum(1 for t in verse_tokens if t == q_tokens[0])
    if mode == "exact":
        n, m = len(verse_tokens), len(q_tokens)
        return sum(
            1 for i in range(n - m + 1) if verse_tokens[i : i + m] == q_tokens
        )
    return 1


def _contains_phrase(tokens: list[str], phrase: list[str]) -> bool:
    n, m = len(tokens), len(phrase)
    if m == 0 or m > n:
        return False
    first = phrase[0]
    for i in range(n - m + 1):
        if tokens[i] == first and tokens[i : i + m] == phrase:
            return True
    return False


# ---------------------------------------------------------------------------
# Inline frontend (HTML + CSS + JS) — served as one document
# ---------------------------------------------------------------------------

PAGE = r"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>بحث القرآن الكريم — Quranic Word Search</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Amiri:wght@400;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg:#fbfaf5; --fg:#1c1c1c; --muted:#6b6b6b;
  --accent:#0f6b5f; --accent-soft:#e6f1ee;
  --border:#e5e2d8; --card:#fff;
  --shadow:0 1px 2px rgba(0,0,0,.04),0 4px 12px rgba(0,0,0,.04);
  --radius:10px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:#14161a; --fg:#ececec; --muted:#9aa0a6;
    --accent:#4cc3b2; --accent-soft:#1c2a28;
    --border:#2a2d33; --card:#1c1f24; --shadow:none;
  }
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--fg);font-family:"Inter",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
main{max-width:820px;margin:0 auto;padding:2.5rem 1.25rem 4rem}
header{text-align:center;margin-bottom:1.75rem}
header h1{font-family:"Amiri",serif;font-weight:700;font-size:clamp(1.8rem,4vw,2.6rem);margin:0 0 .35rem}
.subtitle{margin:0;color:var(--muted);font-size:.92rem}
#searchForm{display:flex;gap:.5rem;margin:1.5rem 0 1.25rem}
#searchForm input[type=search]{flex:1;padding:.85rem 1rem;font-size:1.15rem;font-family:"Amiri","Segoe UI",serif;background:var(--card);color:var(--fg);border:1px solid var(--border);border-radius:var(--radius);outline:none;transition:border-color .15s,box-shadow .15s}
#searchForm input[type=search]:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
#searchForm button{padding:0 1.4rem;font-size:1rem;font-weight:600;color:#fff;background:var(--accent);border:none;border-radius:var(--radius);cursor:pointer}
#searchForm button:hover{filter:brightness(1.05)}
#results{display:flex;flex-direction:column;gap:.75rem}
.mode-toggle{display:flex;align-items:center;gap:.55rem;font-size:.95rem;color:var(--muted);margin:-.5rem 0 1rem;cursor:pointer;user-select:none}
.mode-toggle input{accent-color:var(--accent);width:1.05rem;height:1.05rem}
.summary{background:var(--accent-soft);border:1px solid var(--border);border-radius:var(--radius);padding:1rem 1.25rem;margin-bottom:.5rem;font-size:1.02rem}
.summary ul{margin:0 0 .25rem;padding:0 1.25rem;list-style:disc}
.summary li{line-height:1.85}
.summary strong{font-size:1.08rem}
.surah-dropdown{margin-top:.75rem;border-top:1px dashed var(--border);padding-top:.65rem}
.surah-dropdown>summary{cursor:pointer;list-style:none;font-weight:600;color:var(--accent);padding:.25rem 0;user-select:none}
.surah-dropdown>summary::-webkit-details-marker{display:none}
.surah-dropdown>summary::before{content:"▾";display:inline-block;margin-inline-end:.4rem;transition:transform .15s;font-size:.85em}
.surah-dropdown[open]>summary::before{transform:rotate(180deg)}
.surah-list{list-style:none;margin:.65rem 0 0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:.35rem .75rem;max-height:260px;overflow-y:auto}
.surah-list li{display:flex;align-items:baseline;gap:.5rem;padding:.2rem .35rem;border-radius:6px;background:var(--card);border:1px solid var(--border)}
.surah-list .surah-name{font-family:"Amiri",serif;font-size:1.05rem;flex:1}
.surah-list .surah-en{color:var(--muted);font-size:.78rem}
.surah-list .surah-count{font-weight:700;color:var(--accent);font-variant-numeric:tabular-nums;min-width:1.5em;text-align:end}
.verse{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:1rem 1.25rem;box-shadow:var(--shadow)}
.verse .ref{font-size:.85rem;font-weight:600;color:var(--accent);margin-bottom:.55rem;letter-spacing:.02em;direction:ltr;text-align:left}
.verse .ayah{font-family:"Amiri Quran","Amiri","Scheherazade New",serif;font-size:1.65rem;line-height:2.4;text-align:right;word-spacing:.05em}
.empty,.error{text-align:center;color:var(--muted);padding:2rem 1rem}
.error{color:#c43b3b}
footer{margin-top:3rem;text-align:center;color:var(--muted);font-size:.8rem}
@media (max-width:480px){#searchForm{flex-direction:column}#searchForm button{padding:.85rem}.verse .ayah{font-size:1.4rem;line-height:2.2}}
</style>
</head>
<body>
<main>
  <header>
    <h1>بحث القرآن الكريم</h1>
    <p class="subtitle">بحث دقيق عن الكلمات في القرآن الكريم (الرسم العثماني)</p>
  </header>
  <form id="searchForm" autocomplete="off">
    <input id="query" type="search" placeholder="اكتب كلمة عربية، مثل: الحمار، الجنة، موسى" aria-label="كلمة البحث" autofocus required />
    <button type="submit">بحث</button>
  </form>
  <label class="mode-toggle">
    <input type="checkbox" id="broadMode" />
    <span>بحث موسّع — يشمل البادئات المتصلة (بـ، وـ، فـ، تـ، لـ)</span>
  </label>
  <section id="results" aria-live="polite"></section>
  <footer><p>النص العثماني: حفص عن عاصم · فهرس البحث: الرسم الإملائي · بحث متجاهل للتشكيل</p></footer>
</main>
<script>
const form = document.getElementById("searchForm");
const input = document.getElementById("query");
const broadEl = document.getElementById("broadMode");
const results = document.getElementById("results");

form.addEventListener("submit", (e) => { e.preventDefault(); run(input.value.trim()); });
broadEl.addEventListener("change", () => { const q = input.value.trim(); if (q) run(q); });

async function run(q) {
  if (!q) return;
  results.innerHTML = '<p class="empty">…</p>';
  const mode = broadEl.checked ? "contains" : "exact";
  let data;
  try {
    const r = await fetch("/api/search?q=" + encodeURIComponent(q) + "&mode=" + mode);
    data = await r.json();
  } catch { results.innerHTML = '<p class="error">تعذّر الاتصال. حاول مرة أخرى.</p>'; return; }
  render(data);
}

function escapeHtml(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function render(data) {
  results.innerHTML = "";
  if (data.total === 0) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = `لا توجد نتائج للكلمة: ${data.query}`;
    results.appendChild(p); return;
  }
  const sum = document.createElement("div");
  sum.className = "summary";
  const word = `«${data.query}»`;
  const modeLabel = data.mode === "contains" ? " (بحث موسّع)" : "";
  const surahsCount = data.by_surah.length;
  sum.innerHTML = `
    <ul>
      <li><strong>عدد مرات ورود كلمة ${escapeHtml(word)}: ${data.total} مرة${modeLabel}</strong></li>
      <li>وردت في ${data.total_verses} آية، موزّعة على ${surahsCount} سورة.</li>
    </ul>
    <details class="surah-dropdown">
      <summary>عرض السور التي وردت فيها الكلمة (${surahsCount})</summary>
      <ol class="surah-list"></ol>
    </details>`;
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
  for (const v of data.verses) {
    const a = document.createElement("article");
    a.className = "verse";
    const ref = document.createElement("div"); ref.className = "ref";
    ref.textContent = `[${v.surah_en}: ${v.ayah}]`;
    const ay = document.createElement("div"); ay.className = "ayah";
    ay.lang = "ar"; ay.dir = "rtl"; ay.textContent = v.text;
    a.append(ref, ay); results.appendChild(a);
  }
}

const params = new URLSearchParams(location.search);
const initial = params.get("q");
if (params.get("mode") === "contains") broadEl.checked = true;
if (initial) { input.value = initial; run(initial); }
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------


def make_handler(index: Index):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:  # quieter logs
            sys.stderr.write("  %s\n" % (fmt % args))

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/" or parsed.path == "/index.html":
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/search":
                params = urllib.parse.parse_qs(parsed.query)
                q = params.get("q", [""])[0]
                mode = params.get("mode", ["exact"])[0]
                if mode not in ("exact", "contains"):
                    mode = "exact"
                body = json.dumps(
                    index.search(q, mode=mode), ensure_ascii=False
                ).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if parsed.path == "/api/health":
                body = json.dumps(
                    {"status": "ok", "verses": len(index.verses)}
                ).encode("utf-8")
                self._send(200, body, "application/json")
                return
            self._send(404, b"Not Found", "text/plain")

    return Handler


def find_port(host: str, preferred: int) -> int:
    for p in (preferred, *range(preferred + 1, preferred + 50)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    raise RuntimeError("No free port found near %d" % preferred)


def main() -> int:
    surahs = ensure_dataset()
    print("Indexing %d verses..." % sum(len(s["verses"]) for s in surahs),
          file=sys.stderr)
    index = Index(surahs)

    host = os.environ.get("HOST", "127.0.0.1")
    requested_port = int(os.environ.get("PORT", DEFAULT_PORT))
    # When running locally (loopback) try the next free port if the
    # preferred one is busy. On a hosted platform (Render, Railway, Fly...)
    # PORT is fixed and probing would just fail — bind to what we're told.
    is_local = host in ("127.0.0.1", "localhost")
    port = find_port(host, requested_port) if is_local else requested_port

    server = ThreadingHTTPServer((host, port), make_handler(index))
    url = f"http://{host}:{port}/"
    print(f"\n  ✓ Quran search running at {url}", file=sys.stderr)
    print("  Press Ctrl-C to stop.\n", file=sys.stderr)

    if is_local:
        def _open():
            time.sleep(0.4)
            try:
                webbrowser.open(f"http://127.0.0.1:{port}/")
            except Exception:
                pass

        threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.", file=sys.stderr)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
