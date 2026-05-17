# Quranic Word Search

A lightweight Flask web app for precise, exact-word search across the
Quran. Displays results in the Uthmani script, with a summary of total
occurrences and per-surah counts followed by the matching verses — no
commentary, no Tafsir.

## Stack

- **Python 3.10+ / Flask** — single-process backend, ~250 lines.
- **Bundled JSON** (2.7 MB) with two parallel editions of every verse:
  - **Uthmani Hafs** for display.
  - **Imla'ei (spelled)** as the search index, so queries like
    `الرحمن` and `الكتاب` match correctly regardless of Uthmani
    orthographic quirks (dagger alef, etc.).
- **Diacritic-insensitive** matching: tashkeel, tatweel, and Quranic
  annotation marks are stripped on both sides of the search. Common
  letter variants are unified (`ى → ي`, `ة → ه`, `ٱ/أ/إ/آ → ا`,
  `ؤ → و`, `ئ → ي`).
- Whole-word, exact match (or exact phrase for multi-word queries).
- Plain HTML + vanilla JS UI with Amiri Quran font.

## Run

```bash
cd quran
pip install -r requirements.txt
python build_data.py        # one-time: builds data/quran.json
python app.py               # http://127.0.0.1:5000
```

Production:

```bash
gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

## API

`GET /api/search?q=<word>` returns:

```json
{
  "query": "الحمار",
  "normalized": "الحمار",
  "total": 1,
  "by_surah": [{"id": 62, "name_ar": "الجمعة", "name_en": "Al-Jumu'ah", "count": 1}],
  "verses": [
    {"surah_id": 62, "surah_ar": "الجمعة", "surah_en": "Al-Jumu'ah",
     "ayah": 5, "text": "مَثَلُ ٱلَّذِينَ حُمِّلُوا۟ ..."}
  ]
}
```

## Data sources

- Uthmani Hafs text: King Fahd Quran Complex, via
  [fawazahmed0/quran-api](https://github.com/fawazahmed0/quran-api)
  (`ara-quranuthmanihaf`).
- Imla'ei spelled text: Arabic Wikisource, via the same project
  (`ara-quranspelled`).
- Surah names / metadata:
  [risan/quran-json](https://github.com/risan/quran-json).

Run `python build_data.py` to refresh `data/quran.json`.
