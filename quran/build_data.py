"""Build the bundled Quran dataset used by the search app.

Pulls two parallel editions of the Quran text:

  * Uthmani Hafs script  – for display (authentic mushaf orthography)
  * Imla'ei "spelled"    – for the search index (modern orthography,
                            so user input like "الرحمن" or "الكتاب" matches)

Surah metadata (Arabic name, English transliteration, revelation type) is
taken from the risan/quran-json project.

Run once:

    python build_data.py

Output: data/quran.json
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

UTHMANI_URL = (
    "https://raw.githubusercontent.com/fawazahmed0/quran-api/1/"
    "editions/ara-quranuthmanihaf.min.json"
)
SPELLED_URL = (
    "https://raw.githubusercontent.com/fawazahmed0/quran-api/1/"
    "editions/ara-quranspelled.min.json"
)
META_URL = "https://raw.githubusercontent.com/risan/quran-json/main/dist/quran.json"

OUT = pathlib.Path(__file__).parent / "data" / "quran.json"


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def main() -> int:
    print("Downloading Uthmani edition...", file=sys.stderr)
    uthmani = json.loads(fetch(UTHMANI_URL))["quran"]
    print("Downloading spelled (Imla'ei) edition...", file=sys.stderr)
    spelled = json.loads(fetch(SPELLED_URL))["quran"]
    print("Downloading surah metadata...", file=sys.stderr)
    meta = json.loads(fetch(META_URL))

    by_id = {m["id"]: m for m in meta}
    spelled_idx = {(v["chapter"], v["verse"]): v["text"] for v in spelled}

    surahs = []
    for m in meta:
        sid = m["id"]
        verses = []
        for v in uthmani:
            if v["chapter"] != sid:
                continue
            verses.append(
                {
                    "n": v["verse"],
                    "t": v["text"],
                    "s": spelled_idx[(sid, v["verse"])],
                }
            )
        verses.sort(key=lambda x: x["n"])
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

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(surahs, f, ensure_ascii=False, separators=(",", ":"))

    print(
        f"Wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB, "
        f"{sum(len(s['verses']) for s in surahs)} verses)",
        file=sys.stderr,
    )

    # Also build the morphology index so a single `python build_data.py`
    # produces every file the app needs.
    print("\nNow building morphology index...", file=sys.stderr)
    import build_morphology
    build_morphology.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
