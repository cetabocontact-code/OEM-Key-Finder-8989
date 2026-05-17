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

# Combining marks: tashkeel (fatha/kasra/damma/sukun/shadda/tanween),
# Quranic annotation marks, dagger alef, tatweel.
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ࣰۭ-ࣿـ]")
_ALEFS = re.compile(r"[آأإٱٲٳٵ]")  # آ أ إ ٱ ٲ ٳ ٵ


def normalize(text: str) -> str:
    """Fold a piece of Arabic text into the canonical search form.

    - Strips diacritics, tatweel, and Quranic annotation marks.
    - Unifies alef variants → ا, alef maksura → ي, ta marbuta → ه,
      hamza-on-waw → و, hamza-on-ya → ي.
    - Collapses whitespace.
    """
    text = unicodedata.normalize("NFC", text)
    text = _DIACRITICS.sub("", text)
    text = _ALEFS.sub("ا", text)
    text = (
        text.replace("ى", "ي")  # ى → ي
        .replace("ة", "ه")  # ة → ه
        .replace("ؤ", "و")  # ؤ → و
        .replace("ئ", "ي")  # ئ → ي
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text


_TOKEN_STRIP = re.compile(r"[^ء-ي]+")  # keep only Arabic letters


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


def search(query: str) -> dict:
    q = normalize(query)
    q_tokens = tokenize(q)
    if not q_tokens:
        return {"query": query, "total": 0, "by_surah": [], "verses": []}

    # Exact-word match: every query token must appear as a whole word
    # in the verse, in order, as a contiguous run.
    candidates: Iterable[int] = INDEX.get(q_tokens[0], [])
    if len(q_tokens) > 1:
        # Intersect with verses containing all tokens, then check order.
        rest_sets = [set(INDEX.get(t, [])) for t in q_tokens[1:]]
        candidates = [i for i in candidates if all(i in s for s in rest_sets)]

    hits: list[dict] = []
    by_surah: dict[int, dict] = {}
    for idx in candidates:
        verse = VERSES[idx]
        toks = verse["tokens"]
        if not _contains_phrase(toks, q_tokens):
            continue
        hits.append(
            {
                "surah_id": verse["surah_id"],
                "surah_ar": verse["surah_ar"],
                "surah_en": verse["surah_en"],
                "ayah": verse["ayah"],
                "text": verse["text"],
            }
        )
        s = by_surah.setdefault(
            verse["surah_id"],
            {
                "id": verse["surah_id"],
                "name_ar": verse["surah_ar"],
                "name_en": verse["surah_en"],
                "count": 0,
            },
        )
        s["count"] += 1

    hits.sort(key=lambda h: (h["surah_id"], h["ayah"]))
    return {
        "query": query,
        "normalized": q,
        "total": len(hits),
        "by_surah": sorted(by_surah.values(), key=lambda s: s["id"]),
        "verses": hits,
    }


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
    return jsonify(search(q))


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "verses": len(VERSES), "surahs": len(SURAHS)})


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=bool(int(os.environ.get("DEBUG", "0"))),
    )
