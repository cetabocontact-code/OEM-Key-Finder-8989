"""Quranic word-search web app.

A precise, exact-word search over the Quran. The Uthmani text is shown
to the user; matching is done against a parallel Imla'ei (modern
orthography) index after stripping diacritics and unifying common
character variants, so a query like "الرحمن" or "الكتاب" matches
regardless of whether the user typed tashkeel.

Run:

    python app.py            # dev server on http://127.0.0.1:5000

Production:

    gunicorn -w 2 -b 0.0.0.0:8000 app:app
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import unicodedata
from typing import Iterable

from flask import Flask, jsonify, render_template, request

BASE = pathlib.Path(__file__).parent
DATA_FILE = BASE / "data" / "quran.json"

# --- Arabic text normalization -------------------------------------------
#
# All Arabic ranges are written as \uXXXX escapes so editor bidi
# reordering can\'t silently reshuffle the character class on edit.
#   U+0610-061A  honorific marks
#   U+064B-065F  tashkeel
#   U+0670       superscript (dagger) alef
#   U+06D6-06ED  Quranic annotation marks
#   U+08F0-08FF  extended Arabic marks
#   U+0640       tatweel
_DIACRITICS = re.compile(
    "[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u08F0-\u08FF\u0640]"
)
# U+0622 آ, U+0623 أ, U+0625 إ, U+0671 ٱ, U+0672, U+0673, U+0675 → U+0627 ا
_ALEFS = re.compile("[\u0622\u0623\u0625\u0671\u0672\u0673\u0675]")


def normalize(text: str) -> str:
    """Fold a piece of Arabic text into the canonical search form."""
    text = unicodedata.normalize("NFC", text)
    text = _DIACRITICS.sub("", text)
    text = _ALEFS.sub("\u0627", text)            # → alef
    text = (
        text.replace("\u0649", "\u064A")    # ى → ي
        .replace("\u0629", "\u0647")        # ة → ه
        .replace("\u0624", "\u0648")        # ؤ → و
        .replace("\u0626", "\u064A")        # ئ → ي
    )
    return re.sub(r"\s+", " ", text).strip()


_TOKEN_STRIP = re.compile("[^\u0621-\u064A]+")  # keep only Arabic letters


def tokenize(normalized: str) -> list[str]:
    return [
        t for t in (_TOKEN_STRIP.sub("", w) for w in normalized.split(" ")) if t
    ]


# --- Load + index --------------------------------------------------------

with DATA_FILE.open(encoding="utf-8") as f:
    SURAHS: list[dict] = json.load(f)


def _build_index() -> tuple[list[dict], dict[str, list[int]]]:
    """Return (flat verse list, token → [verse_idx] inverted index)."""
    flat: list[dict] = []
    inv: dict[str, list[int]] = {}
    for surah in SURAHS:
        for v in surah["verses"]:
            idx = len(flat)
            tokens = tokenize(normalize(v["s"]))
            flat.append(
                {
                    "surah_id": surah["id"],
                    "surah_ar": surah["name_ar"],
                    "surah_en": surah["name_en"],
                    "ayah": v["n"],
                    "text": v["t"],
                    "tokens": tokens,
                }
            )
            for tok in set(tokens):
                inv.setdefault(tok, []).append(idx)
    return flat, inv


VERSES, INDEX = _build_index()


def search(query: str, mode: str = "exact") -> dict:
    q = normalize(query)
    q_tokens = tokenize(q)
    empty = {
        "query": query, "mode": mode, "normalized": q,
        "total": 0, "total_verses": 0, "by_surah": [], "verses": [],
    }
    if not q_tokens:
        return empty

    # Build per-query-token "match forms":
    #   exact   → [token]
    #   contains→ [token, "ل"+token[2:] if starts with ال] — catches
    #             attached prefixes (ب/و/ف/ت/ل + word) plus the
    #             lām-elision case (لـ + الـ → drops the alif:
    #             الله→لله, الناس→للناس, الحمد→للحمد).
    forms_per_qt: list[list[str]] = []
    for qt in q_tokens:
        forms = [qt]
        if mode == "contains" and qt.startswith("ال") and len(qt) > 2:
            forms.append("ل" + qt[2:])
        forms_per_qt.append(forms)

    if mode == "contains":
        token_matches: list[set[int]] = []
        for forms in forms_per_qt:
            verses: set[int] = set()
            for token, vids in INDEX.items():
                if any(f in token for f in forms):
                    verses.update(vids)
            token_matches.append(verses)
        hit_ids = sorted(set.intersection(*token_matches)) if token_matches else []
    else:
        candidates: Iterable[int] = INDEX.get(q_tokens[0], [])
        if len(q_tokens) > 1:
            rest_sets = [set(INDEX.get(t, [])) for t in q_tokens[1:]]
            candidates = [i for i in candidates if all(i in s for s in rest_sets)]
        hit_ids = [
            i for i in candidates
            if _contains_phrase(VERSES[i]["tokens"], q_tokens)
        ]

    hits: list[dict] = []
    by_surah: dict[int, dict] = {}
    total_occurrences = 0
    for idx in hit_ids:
        verse = VERSES[idx]
        occ = _count_in_verse(verse["tokens"], q_tokens, mode, forms_per_qt)
        if occ == 0:
            continue
        total_occurrences += occ
        hits.append(
            {
                "surah_id": verse["surah_id"],
                "surah_ar": verse["surah_ar"],
                "surah_en": verse["surah_en"],
                "ayah": verse["ayah"],
                "text": verse["text"],
                "occurrences": occ,
            }
        )
        s = by_surah.setdefault(
            verse["surah_id"],
            {
                "id": verse["surah_id"],
                "name_ar": verse["surah_ar"],
                "name_en": verse["surah_en"],
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
        "normalized": q,
        "total": total_occurrences,
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
    """Total occurrences of the query inside a single verse."""
    if len(q_tokens) == 1:
        forms = forms_per_qt[0]
        if mode == "contains":
            return sum(1 for t in verse_tokens if any(f in t for f in forms))
        return sum(1 for t in verse_tokens if t == q_tokens[0])
    # Multi-word: count contiguous phrase matches (exact); for contains
    # mode just report 1 per verse since substring positions overlap badly.
    if mode == "exact":
        n, m = len(verse_tokens), len(q_tokens)
        return sum(
            1 for i in range(n - m + 1) if verse_tokens[i : i + m] == q_tokens
        )
    return 1


def _contains_phrase(tokens: list[str], phrase: list[str]) -> bool:
    if not phrase:
        return False
    n, m = len(tokens), len(phrase)
    if m > n:
        return False
    first = phrase[0]
    for i in range(n - m + 1):
        if tokens[i] == first and tokens[i : i + m] == phrase:
            return True
    return False


# --- Flask app -----------------------------------------------------------

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "", type=str).strip()
    mode = request.args.get("mode", "exact", type=str)
    if mode not in ("exact", "contains"):
        mode = "exact"
    return jsonify(search(q, mode=mode))


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "verses": len(VERSES), "surahs": len(SURAHS)})


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=bool(int(os.environ.get("DEBUG", "0"))),
    )
