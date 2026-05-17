"""Build the Quranic morphology index from the Quranic Arabic Corpus.

Pulls QAC v0.4 (Kais Dukes, CC BY-SA 3.0), converts Buckwalter
transliteration to Arabic, and writes a compact JSON that lets the app:

  * search by root (e.g. ح م ر → every derived form)
  * highlight any word in the displayed verse that shares the searched
    root or lemma
  * show a small morphology card (root, lemma, POS) for any verse word

Run once:

    python build_morphology.py

Output: data/morphology.json
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import sys
import unicodedata
import urllib.request

QAC_URL = (
    "https://raw.githubusercontent.com/cltk/"
    "arabic_morphology_quranic-corpus/master/quranic-corpus-morphology-0.4.txt"
)

OUT = pathlib.Path(__file__).parent / "data" / "morphology.json"

# Buckwalter → Arabic Unicode mapping.
BW2AR = {
    "'": "ء", "|": "آ", ">": "أ", "&": "ؤ",
    "<": "إ", "}": "ئ", "A": "ا", "b": "ب",
    "p": "ة", "t": "ت", "v": "ث", "j": "ج",
    "H": "ح", "x": "خ", "d": "د", "*": "ذ",
    "r": "ر", "z": "ز", "s": "س", "$": "ش",
    "S": "ص", "D": "ض", "T": "ط", "Z": "ظ",
    "E": "ع", "g": "غ", "_": "ـ", "f": "ف",
    "q": "ق", "k": "ك", "l": "ل", "m": "م",
    "n": "ن", "h": "ه", "w": "و", "Y": "ى",
    "y": "ي", "F": "ً", "N": "ٌ", "K": "ٍ",
    "a": "َ", "u": "ُ", "i": "ِ", "~": "ّ",
    "o": "ْ", "`": "ٰ", "{": "ٱ",
}


def bw_to_ar(s: str) -> str:
    return "".join(BW2AR.get(c, c) for c in s)


# Same normalization the app uses, kept consistent.
_DIACRITICS = re.compile(
    "[ؐ-ًؚ-ٰٟۖ-ࣰۭ-ࣿـ]"
)
_ALEFS = re.compile("[آأإٱٲٳٵ]")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _DIACRITICS.sub("", text)
    text = _ALEFS.sub("ا", text)
    return (
        text.replace("ى", "ي")
        .replace("ة", "ه")
        .replace("ؤ", "و")
        .replace("ئ", "ي")
    )


def fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=120) as resp:
        return resp.read().decode("utf-8")


def main() -> int:
    print("Downloading QAC morphology...", file=sys.stderr)
    text = fetch(QAC_URL)

    # Per-(sura,verse,word): join every segment's surface form, and
    # collect root/lemma/pos from the STEM segment(s).
    word_segments: dict[tuple[int, int, int], list[tuple[int, str]]] = (
        collections.defaultdict(list)
    )
    word_stems: dict[tuple[int, int, int], dict] = {}

    for line in text.splitlines():
        if not line.startswith("("):
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        loc, form_bw, tag, features = parts
        s, v, w, seg = (int(x) for x in loc.strip("()").split(":"))
        word_segments[(s, v, w)].append((seg, form_bw))
        feats = features.split("|")
        if "STEM" in feats and (s, v, w) not in word_stems:
            root_bw = next((f[5:] for f in feats if f.startswith("ROOT:")), None)
            lem_bw = next((f[4:] for f in feats if f.startswith("LEM:")), None)
            pos = next((f[4:] for f in feats if f.startswith("POS:")), None)
            word_stems[(s, v, w)] = {
                "root": bw_to_ar(root_bw) if root_bw else "",
                "lemma": bw_to_ar(lem_bw) if lem_bw else "",
                "pos": pos or "",
            }

    words: dict[tuple[int, int, int], dict] = {}
    for key, segs in word_segments.items():
        segs.sort(key=lambda x: x[0])
        full_bw = "".join(s[1] for s in segs)
        stem = word_stems.get(key, {"root": "", "lemma": "", "pos": ""})
        words[key] = {
            "form": bw_to_ar(full_bw),
            "root": stem["root"],
            "lemma": stem["lemma"],
            "pos": stem["pos"],
        }

    print(f"  parsed {len(words)} words", file=sys.stderr)

    # Aggregate verse-level data. We index forms by the *spelled* (Imla'ei)
    # token of each word, because that's what the search index and the
    # verse-display tokenization use. We align QAC's per-word order to the
    # spelled-text whitespace tokens 1:1 where the counts match (94% of
    # verses); for the rest we still capture verse-level roots/lemmas for
    # search, just not per-token form mappings.
    quran = json.load(
        (pathlib.Path(__file__).parent / "data" / "quran.json").open(
            encoding="utf-8"
        )
    )
    spelled_tokens: dict[tuple[int, int], list[str]] = {}
    for surah in quran:
        for verse in surah["verses"]:
            spelled_tokens[(surah["id"], verse["n"])] = verse["s"].split()

    verse_roots: dict[tuple[int, int], set[str]] = collections.defaultdict(set)
    verse_lemmas: dict[tuple[int, int], set[str]] = collections.defaultdict(set)
    form_morph_count: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )

    # Group QAC words by verse, in word order.
    qac_by_verse: dict[tuple[int, int], list[dict]] = collections.defaultdict(list)
    for (s, v, w), d in sorted(words.items()):
        qac_by_verse[(s, v)].append(d)

    aligned = 0
    for (s, v), qac_words in qac_by_verse.items():
        for d in qac_words:
            if d["root"]:
                verse_roots[(s, v)].add(d["root"])
            if d["lemma"]:
                verse_lemmas[(s, v)].add(d["lemma"])
            # Index the QAC's own surface form too (Uthmani-flavoured —
            # may differ from the spelled token because of the dagger
            # alef: الكتب in Uthmani-strip vs الكتاب in Imla'ei). This
            # lets the highlighter work whether the verse-display
            # tokenization yields one or the other.
            qac_norm = normalize(d["form"])
            if qac_norm:
                form_morph_count[qac_norm][
                    (d["root"], d["lemma"], d["pos"])
                ] += 1

        tokens = spelled_tokens.get((s, v), [])
        if len(tokens) != len(qac_words):
            continue
        aligned += 1
        for tok, d in zip(tokens, qac_words):
            norm = normalize(tok)
            if not norm:
                continue
            form_morph_count[norm][(d["root"], d["lemma"], d["pos"])] += 1

    print(
        f"  aligned {aligned}/{len(qac_by_verse)} verses 1:1 between "
        f"QAC and spelled tokens",
        file=sys.stderr,
    )

    # Per normalized form: most-common analysis (for the hover card) +
    # the full set of roots and lemmas it can take (used to decide
    # whether a verse token should be highlighted under a root/lemma
    # search — a single surface form can map to multiple roots).
    form_morph: dict[str, dict] = {}
    form_roots: dict[str, list[str]] = {}
    form_lemmas: dict[str, list[str]] = {}
    for norm, counter in form_morph_count.items():
        (root, lemma, pos), _ = counter.most_common(1)[0]
        form_morph[norm] = {"root": root, "lemma": lemma, "pos": pos}
        rs = sorted({k[0] for k in counter if k[0]})
        ls = sorted({k[1] for k in counter if k[1]})
        if rs:
            form_roots[norm] = rs
        if ls:
            form_lemmas[norm] = ls

    # roots index: root → sorted list of "s:v"
    roots: dict[str, list[str]] = collections.defaultdict(list)
    for (s, v), root_set in verse_roots.items():
        for r in root_set:
            roots[r].append(f"{s}:{v}")
    for r in roots:
        roots[r] = sorted(roots[r], key=lambda x: tuple(map(int, x.split(":"))))

    lemmas: dict[str, list[str]] = collections.defaultdict(list)
    for (s, v), lemma_set in verse_lemmas.items():
        for l in lemma_set:
            lemmas[l].append(f"{s}:{v}")
    for l in lemmas:
        lemmas[l] = sorted(lemmas[l], key=lambda x: tuple(map(int, x.split(":"))))

    out = {
        "roots": roots,
        "lemmas": lemmas,
        "form_morph": form_morph,
        "form_roots": form_roots,
        "form_lemmas": form_lemmas,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    size = OUT.stat().st_size
    print(
        f"Wrote {OUT} ({size/1024:.0f} KB): "
        f"{len(roots)} roots, {len(lemmas)} lemmas, "
        f"{len(form_morph)} forms",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
