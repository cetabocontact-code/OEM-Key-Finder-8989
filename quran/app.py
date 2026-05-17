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

import difflib
import html
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

MORPH_FILE = BASE / "data" / "morphology.json"
if MORPH_FILE.exists():
    with MORPH_FILE.open(encoding="utf-8") as f:
        MORPH: dict = json.load(f)
else:
    MORPH = {"roots": {}, "lemmas": {}, "form_morph": {}, "form_roots": {}, "form_lemmas": {}}

ROOTS_IDX: dict[str, list[str]] = MORPH.get("roots", {})        # root  → ["s:v", ...]
LEMMAS_IDX: dict[str, list[str]] = MORPH.get("lemmas", {})      # lemma → ["s:v", ...]
FORM_MORPH: dict[str, dict] = MORPH.get("form_morph", {})       # form  → {root,lemma,pos}
FORM_ROOTS: dict[str, list[str]] = MORPH.get("form_roots", {})  # form  → [root,...]
FORM_LEMMAS: dict[str, list[str]] = MORPH.get("form_lemmas", {})# form  → [lemma,...]


def _build_index() -> tuple[list[dict], dict[str, list[int]], dict[str, int]]:
    """Return (flat verse list, token-inverted-index, "s:v" → verse_idx)."""
    flat: list[dict] = []
    inv: dict[str, list[int]] = {}
    by_ref: dict[str, int] = {}
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
                    "spelled": v["s"],
                    "tokens": tokens,
                }
            )
            by_ref[f"{surah['id']}:{v['n']}"] = idx
            for tok in set(tokens):
                inv.setdefault(tok, []).append(idx)
    return flat, inv, by_ref


VERSES, INDEX, VERSE_BY_REF = _build_index()
ALL_TOKENS: list[str] = sorted(INDEX.keys())  # vocabulary, for "did you mean"


def _hl_predicate(mode: str, q_tokens: list[str], forms_per_qt: list[list[str]],
                  root_q: str = "", lemma_q: str = ""):
    """Return a function: normalized_token → bool (highlight this token?)."""
    if mode == "root" and root_q:
        return lambda n: root_q in FORM_ROOTS.get(n, ())
    if mode == "lemma" and lemma_q:
        return lambda n: lemma_q in FORM_LEMMAS.get(n, ())
    if mode == "contains":
        forms_all = [f for fs in forms_per_qt for f in fs]
        return lambda n: any(f in n for f in forms_all)
    # exact — string equality OR same lemma (covers Uthmani/Imla'ei
    # orthographic variants like الكتب ↔ الكتاب that share lemma كِتَٰب).
    qset = set(q_tokens)
    q_lemmas: set[str] = set()
    for qt in q_tokens:
        for lem in FORM_LEMMAS.get(qt, ()):
            q_lemmas.add(lem)

    def pred(n: str) -> bool:
        if n in qset:
            return True
        if q_lemmas and any(lem in q_lemmas for lem in FORM_LEMMAS.get(n, ())):
            return True
        return False

    return pred


_TOKEN_SPLIT = re.compile(r"(\s+)")


def _render_highlighted(text: str, hit) -> str:
    """Wrap every whitespace-token in <span class="w" data-w="...">;
    matched ones additionally get the .mark class. Spans let the client
    open a morphology card on click."""
    out: list[str] = []
    for part in _TOKEN_SPLIT.split(text):
        if not part:
            continue
        if part.isspace():
            out.append(part)
            continue
        cls = "w mark" if hit(normalize(part)) else "w"
        esc = html.escape(part)
        out.append(f'<span class="{cls}" data-w="{esc}">{esc}</span>')
    return "".join(out)


def search(query: str, mode: str = "exact") -> dict:
    q = normalize(query)
    q_tokens = tokenize(q)
    empty = {
        "query": query, "mode": mode, "normalized": q,
        "total": 0, "total_verses": 0, "by_surah": [], "verses": [],
        "suggestions": [],
    }
    if not query.strip():
        return empty

    # --- Root mode: query is treated as a root, all derived forms match.
    if mode == "root":
        root = q.replace(" ", "")  # accept "ح م ر" or "حمر"
        refs = ROOTS_IDX.get(root, [])
        if not refs:
            empty["suggestions"] = _suggest_roots(root)
            return empty
        hit_ids = [VERSE_BY_REF[r] for r in refs if r in VERSE_BY_REF]
        hl = _hl_predicate("root", [], [], root_q=root)

        def occ_count(verse):
            return sum(
                1 for t in verse["tokens"]
                if root in FORM_ROOTS.get(t, ())
            )

    else:
        # --- Build prefix-elision forms for contains mode.
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
            hit_ids = (
                sorted(set.intersection(*token_matches)) if token_matches else []
            )
        else:
            candidates: Iterable[int] = INDEX.get(q_tokens[0], [])
            if len(q_tokens) > 1:
                rest_sets = [set(INDEX.get(t, [])) for t in q_tokens[1:]]
                candidates = [
                    i for i in candidates if all(i in s for s in rest_sets)
                ]
            hit_ids = [
                i for i in candidates
                if _contains_phrase(VERSES[i]["tokens"], q_tokens)
            ]

        hl = _hl_predicate(mode, q_tokens, forms_per_qt)

        def occ_count(verse, _q=q_tokens, _m=mode, _f=forms_per_qt):
            return _count_in_verse(verse["tokens"], _q, _m, _f)

    if not hit_ids:
        empty["suggestions"] = _suggest_words(q_tokens[0] if q_tokens else q)
        return empty

    hits: list[dict] = []
    by_surah: dict[int, dict] = {}
    total_occurrences = 0
    for idx in hit_ids:
        verse = VERSES[idx]
        occ = occ_count(verse)
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
                "text_html": _render_highlighted(verse["text"], hl),
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
        "suggestions": [],
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


def _suggest_words(q: str, k: int = 6) -> list[str]:
    """Did-you-mean: close matches + substring matches in the token vocab."""
    if not q:
        return []
    out: list[str] = []
    # exact substring matches first
    for tok in ALL_TOKENS:
        if q in tok and tok != q:
            out.append(tok)
            if len(out) >= k:
                return out
    # then edit-distance neighbours
    close = difflib.get_close_matches(q, ALL_TOKENS, n=k - len(out), cutoff=0.7)
    for c in close:
        if c not in out:
            out.append(c)
    return out[:k]


def _suggest_roots(root: str, k: int = 6) -> list[str]:
    if not root:
        return []
    out: list[str] = [r for r in ROOTS_IDX if root in r and r != root]
    out.sort(key=lambda r: (len(r), r))
    return out[:k]


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
    if mode not in ("exact", "contains", "root"):
        mode = "exact"
    return jsonify(search(q, mode=mode))


@app.route("/api/morph")
def api_morph():
    """Morphology card for a single word: root, lemma, POS."""
    word = request.args.get("w", "", type=str).strip()
    if not word:
        return jsonify({})
    n = normalize(word)
    info = FORM_MORPH.get(n) or {}
    return jsonify(
        {
            "word": word,
            "normalized": n,
            "root": info.get("root", ""),
            "lemma": info.get("lemma", ""),
            "pos": info.get("pos", ""),
            "all_roots": FORM_ROOTS.get(n, []),
        }
    )


@app.route("/api/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "verses": len(VERSES),
            "surahs": len(SURAHS),
            "roots": len(ROOTS_IDX),
            "lemmas": len(LEMMAS_IDX),
            "forms": len(FORM_MORPH),
        }
    )


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=bool(int(os.environ.get("DEBUG", "0"))),
    )
