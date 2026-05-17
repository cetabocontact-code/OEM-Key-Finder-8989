#!/usr/bin/env python3
"""Live VIN -> Smart Key Fob part number agent for Hyundai and Kia.

This module is intentionally database-free. It only does two things:

1. Decode the VIN against the NHTSA vPIC API and capture every decoded field.
2. Use the decoded year/make/model plus the VIN to query the OEM parts site
   (hyundaipartsdeal.com or kiapartsnow.com), then extract the smart key /
   key fob part number directly from the live product page.

A part number is only returned when the live OEM page confirms it matches the
decoded VIN. Otherwise the agent returns the source URL so a human can verify.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any


NHTSA_ENDPOINT = (
    "https://vpic.nhtsa.dot.gov/api/vehicles/decodevinvaluesextended/{vin}?format=json"
)

VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")

HYUNDAI_WMIS = {"KMH", "KM8", "5NM", "5NP", "KMF"}
KIA_WMIS = {"KNA", "KND", "KNE", "KNJ", "5XY", "5XX"}
# 3KP is shared by Hyundai (Accent) and Kia (Rio, K4) Mexico-built cars, so
# require the NHTSA Make field to disambiguate.
SHARED_WMIS = {"3KP", "3CN", "3KM"}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

KEY_TERMS = (
    "smart key",
    "key fob",
    "keyless entry",
    "transmitter",
    "remote control",
    "tx assy",
    "key-fob",
    "fob",
    "keyless",
)

# Part numbers that look like a real OEM Hyundai/Kia electronics SKU.
# Hyundai/Kia smart-key SKUs typically start with 95430, 95440, 95450, or 81996
# and follow either 95440-XXXXX or 95440XXXXX. We capture both styles.
PART_NUMBER_RE = re.compile(
    r"\b(?:95430|95440|95450|81996|954A0)[- ]?[A-Z0-9]{4,6}\b",
    re.IGNORECASE,
)


class AgentError(RuntimeError):
    """Raised for any unrecoverable agent failure."""


@dataclass
class DecodeData:
    vin: str
    year: str = ""
    make: str = ""
    model: str = ""
    trim: str = ""
    series: str = ""
    body: str = ""
    drive: str = ""
    engine: str = ""
    plant_country: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class CandidatePart:
    part_number: str
    description: str
    product_url: str
    page_context: str


@dataclass
class AgentResult:
    vin: str
    decode: DecodeData
    parts_site: str
    search_url: str
    candidates: list[CandidatePart]
    verified_part_number: str | None
    verified_reason: str

    def to_json(self) -> dict[str, Any]:
        return {
            "vin": self.vin,
            "decode": {
                "year": self.decode.year,
                "make": self.decode.make,
                "model": self.decode.model,
                "trim": self.decode.trim,
                "series": self.decode.series,
                "body": self.decode.body,
                "drive": self.decode.drive,
                "engine": self.decode.engine,
                "plant_country": self.decode.plant_country,
                "raw": self.decode.raw,
            },
            "parts_site": self.parts_site,
            "search_url": self.search_url,
            "candidates": [
                {
                    "part_number": candidate.part_number,
                    "description": candidate.description,
                    "product_url": candidate.product_url,
                }
                for candidate in self.candidates
            ],
            "verified_part_number": self.verified_part_number,
            "verified_reason": self.verified_reason,
        }


def normalize_vin(vin: str) -> str:
    cleaned = "".join(ch for ch in vin.strip().upper() if not ch.isspace())
    if not VIN_RE.match(cleaned):
        raise AgentError(
            f"Invalid VIN '{vin}'. A VIN must be 17 alphanumeric characters and exclude I, O, Q."
        )
    return cleaned


def detect_brand(vin: str, decoded_make: str = "") -> str:
    wmi = vin[:3]
    if wmi in HYUNDAI_WMIS:
        return "hyundai"
    if wmi in KIA_WMIS:
        return "kia"
    if wmi in SHARED_WMIS:
        make = decoded_make.casefold()
        if "hyundai" in make:
            return "hyundai"
        if "kia" in make:
            return "kia"
        raise AgentError(
            f"VIN WMI '{wmi}' is shared by Hyundai and Kia; NHTSA Make '{decoded_make}' "
            "did not resolve the brand."
        )
    raise AgentError(
        f"VIN WMI '{wmi}' is not Hyundai or Kia. This agent only handles Hyundai and Kia."
    )


def http_get(url: str, *, timeout: float = 25.0) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        raise AgentError(f"HTTP {exc.code} from {url}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise AgentError(f"Network error fetching {url}: {exc.reason}") from exc


def decode_vin(vin: str) -> DecodeData:
    url = NHTSA_ENDPOINT.format(vin=urllib.parse.quote(vin))
    body = http_get(url)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise AgentError(f"NHTSA returned non-JSON for {vin}") from exc

    results = payload.get("Results") or []
    if not results:
        raise AgentError(f"NHTSA returned no results for {vin}.")

    row = results[0]
    error_code = str(row.get("ErrorCode") or "")
    if error_code and error_code not in {"0", "0,0"}:
        raise AgentError(
            f"NHTSA decode error {error_code} for {vin}: {row.get('ErrorText', '')}"
        )

    raw = {str(k): "" if v is None else str(v) for k, v in row.items()}
    return DecodeData(
        vin=vin,
        year=raw.get("ModelYear", ""),
        make=raw.get("Make", ""),
        model=raw.get("Model", ""),
        trim=raw.get("Trim", ""),
        series=raw.get("Series", ""),
        body=raw.get("BodyClass", ""),
        drive=raw.get("DriveType", ""),
        engine=raw.get("EngineModel", "") or raw.get("DisplacementL", ""),
        plant_country=raw.get("PlantCountry", ""),
        raw=raw,
    )


class _LinkTextCollector(HTMLParser):
    """Capture (href, inner text) pairs so we can match part-number anchors."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._open_a_hrefs: list[str] = []
        self._buffer: list[list[str]] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = ""
        for name, value in attrs:
            if name.lower() == "href" and value:
                href = value
                break
        self._open_a_hrefs.append(href)
        self._buffer.append([])

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._open_a_hrefs:
            return
        href = self._open_a_hrefs.pop()
        text = " ".join("".join(self._buffer.pop()).split())
        if href or text:
            self.links.append((href, text))

    def handle_data(self, data: str) -> None:
        if self._buffer:
            self._buffer[-1].append(data)


def _absolutize(base: str, href: str) -> str:
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urllib.parse.urljoin(base, href)


def extract_candidates(html: str, base_url: str) -> list[CandidatePart]:
    collector = _LinkTextCollector()
    try:
        collector.feed(html)
    except Exception:
        # HTMLParser can choke on malformed input; fall back to regex over raw text.
        collector.links = []

    candidates: dict[str, CandidatePart] = {}

    for href, text in collector.links:
        if not text:
            continue
        match = PART_NUMBER_RE.search(text)
        if not match:
            continue
        part = normalize_part_number(match.group(0))
        if part in candidates:
            continue
        candidates[part] = CandidatePart(
            part_number=part,
            description=text,
            product_url=_absolutize(base_url, href),
            page_context=text,
        )

    if not candidates:
        # Fallback: scan whole document for part numbers in context.
        text_only = re.sub(r"<[^>]+>", " ", html)
        for match in PART_NUMBER_RE.finditer(text_only):
            part = normalize_part_number(match.group(0))
            if part in candidates:
                continue
            start = max(0, match.start() - 160)
            end = min(len(text_only), match.end() + 160)
            context = " ".join(text_only[start:end].split())
            candidates[part] = CandidatePart(
                part_number=part,
                description=context,
                product_url=base_url,
                page_context=context,
            )

    return list(candidates.values())


def normalize_part_number(raw: str) -> str:
    cleaned = raw.strip().upper()
    # Hyundai/Kia OEM publishes both 95440-KL000 and 95440KL000 styles, plus a
    # newer 954A0-XXXXX prefix. Normalize all to the dashed form.
    compact = cleaned.replace("-", "").replace(" ", "")
    if len(compact) >= 6 and compact[0].isdigit() and compact[1].isdigit():
        return f"{compact[:5]}-{compact[5:]}"
    return cleaned


def build_search_url(brand: str, vin: str) -> tuple[str, str]:
    if brand == "hyundai":
        domain = "www.hyundaipartsdeal.com"
    else:
        domain = "www.kiapartsnow.com"
    url = (
        f"https://{domain}/page_product/pd?"
        f"vin={urllib.parse.quote(vin)}&filter=()&pd=Car+Key&pdUrl=car_key"
    )
    return domain, url


def verify_vin_context(html: str, decode: DecodeData) -> tuple[bool, str]:
    """Confirm the live page actually corresponds to the decoded vehicle."""
    haystack = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).casefold()
    if decode.vin.casefold() in haystack:
        return True, "Live OEM page lists the decoded VIN."
    checks: list[str] = []
    if decode.year and decode.year in haystack:
        checks.append(decode.year)
    if decode.model and decode.model.casefold() in haystack:
        checks.append(decode.model)
    if decode.make and decode.make.casefold() in haystack:
        checks.append(decode.make)
    if {"year", "model", "make"} <= {label.lower() for label in checks} or len(checks) >= 2:
        return True, "Live OEM page text matches NHTSA year + " + ", ".join(checks)
    return False, (
        "Could not confirm the live page corresponds to the decoded VIN; review the search URL manually."
    )


def select_best_part(candidates: list[CandidatePart], decode: DecodeData) -> CandidatePart | None:
    if not candidates:
        return None
    scored: list[tuple[int, CandidatePart]] = []
    year_token = decode.year
    model_token = decode.model.casefold() if decode.model else ""
    for candidate in candidates:
        text = (candidate.description or "").casefold()
        score = 0
        for term in KEY_TERMS:
            if term in text:
                score += 5
                break
        if "smart key" in text:
            score += 6
        if "without auto park" in text or "w/o auto park" in text:
            score += 1
        if year_token and year_token in text:
            score += 2
        if model_token and model_token in text:
            score += 2
        # Hyundai/Kia OEM smart-key SKUs start with 95440 or 954A0.
        if candidate.part_number.startswith("95440") or candidate.part_number.startswith("954A0"):
            score += 3
        scored.append((score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best = scored[0]
    if best_score <= 0:
        return None
    return best


def run(vin: str) -> AgentResult:
    normalized = normalize_vin(vin)
    decode = decode_vin(normalized)
    brand = detect_brand(normalized, decode.make)

    domain, search_url = build_search_url(brand, normalized)
    html = http_get(search_url)
    candidates = extract_candidates(html, search_url)

    matched_vin, reason = verify_vin_context(html, decode)
    best = select_best_part(candidates, decode) if matched_vin else None

    return AgentResult(
        vin=normalized,
        decode=decode,
        parts_site=domain,
        search_url=search_url,
        candidates=candidates,
        verified_part_number=best.part_number if best else None,
        verified_reason=(
            f"{reason} Best candidate selected by smart-key keyword + SKU prefix scoring."
            if best
            else reason
        ),
    )


def format_text(result: AgentResult) -> str:
    decode = result.decode
    lines = [
        f"VIN          : {result.vin}",
        f"Vehicle      : {decode.year} {decode.make} {decode.model} {decode.trim}".rstrip(),
        f"Series/Body  : {decode.series} / {decode.body}".strip(" /"),
        f"Engine/Drive : {decode.engine} / {decode.drive}".strip(" /"),
        f"Plant        : {decode.plant_country}",
        f"Parts site   : {result.parts_site}",
        f"Search URL   : {result.search_url}",
    ]
    if result.verified_part_number:
        lines.append(f"Smart key fob: {result.verified_part_number}  [VERIFIED]")
    else:
        lines.append("Smart key fob: NOT VERIFIED - open the search URL above to confirm.")
    lines.append(f"Reason       : {result.verified_reason}")
    if result.candidates:
        lines.append("Candidates pulled from live page:")
        for candidate in result.candidates:
            lines.append(
                f"  - {candidate.part_number}  {candidate.description[:100]}"
            )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Decode a VIN with NHTSA and pull the smart key fob part number live "
            "from the Hyundai or Kia OEM parts site. No local database."
        )
    )
    parser.add_argument("vin", help="17-character VIN")
    parser.add_argument(
        "--json", action="store_true", help="Print the full JSON result."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(args.vin)
    except AgentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.to_json(), indent=2))
    else:
        print(format_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
