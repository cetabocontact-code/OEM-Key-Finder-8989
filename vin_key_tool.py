#!/usr/bin/env python3
"""VIN decoder + OEM key-part resolver proof of work.

The resolver is intentionally conservative. It returns confirmed VIN-level
matches first, then optional catalog rules whose fitment conditions match the
NHTSA decode. Unknown VINs return the decoded vehicle info plus no part match.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_CATALOG = ROOT / "data" / "confirmed_key_parts.json"
DEFAULT_CACHE = ROOT / "data" / "nhtsa_known_decodes.json"
DEFAULT_PROFILES = ROOT / "data" / "make_profiles.json"
NHTSA_ENDPOINT = "https://vpic.nhtsa.dot.gov/api/vehicles/decodevinvaluesextended/{vin}?format=json"
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
MODEL_YEAR_CODES = {
    "A": "2010",
    "B": "2011",
    "C": "2012",
    "D": "2013",
    "E": "2014",
    "F": "2015",
    "G": "2016",
    "H": "2017",
    "J": "2018",
    "K": "2019",
    "L": "2020",
    "M": "2021",
    "N": "2022",
    "P": "2023",
    "R": "2024",
    "S": "2025",
    "T": "2026",
}


class VinKeyError(RuntimeError):
    """Raised for resolver input or lookup failures."""


@dataclass(frozen=True)
class DecodeResult:
    vin: str
    fields: dict[str, str]
    source: str


def normalize_vin(vin: str) -> str:
    normalized = vin.strip().upper()
    if not VIN_RE.match(normalized):
        raise VinKeyError(f"Invalid VIN '{vin}'. VINs must be 17 chars and exclude I, O, Q.")
    return normalized


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def load_cache(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    raw = load_json(path)
    return {normalize_vin(vin): dict(fields) for vin, fields in raw.items()}


def load_catalog(path: Path = DEFAULT_CATALOG) -> dict[str, Any]:
    return load_json(path)


def load_make_profiles(path: Path = DEFAULT_PROFILES) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_json(path)


def slug_make(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def detect_make_profile(vin: str, fields: dict[str, str], profiles: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    make_slug = slug_make(fields.get("Make", ""))
    if make_slug in profiles:
        return make_slug, profiles[make_slug]

    wmi = vin[:3]
    if wmi in {"JTH", "JTJ", "2T2", "58A"}:
        return "lexus", profiles.get("lexus", {})
    if wmi in {"3MW", "WBA", "WBS", "WBX", "WBY", "5UX", "5YX", "4US"}:
        return "bmw", profiles.get("bmw", {})
    if wmi in {"JM1", "JM3", "3MV", "4F2", "4F4", "1YV"}:
        return "mazda", profiles.get("mazda", {})
    if wmi in {"SAL", "SAJ"}:
        return "land-rover", profiles.get("land-rover", {})
    if wmi in {"WAU", "WUA", "TRU"}:
        return "audi", profiles.get("audi", {})
    if wmi in {"5YJ", "7SA", "7G2", "LRW", "SFZ", "XP7"}:
        return "tesla", profiles.get("tesla", {})
    if wmi in {"YV1", "YV4", "LYV"}:
        return "volvo", profiles.get("volvo", {})
    if wmi in {"3VV", "WVW", "WV1", "WV2", "1VW", "3VW"}:
        return "volkswagen", profiles.get("volkswagen", {})
    if wmi in {"1C4", "3C4", "JC4"}:
        return "jeep", profiles.get("jeep", {})
    if wmi == "JN1" and len(vin) > 3:
        return ("infiniti" if vin[3] in {"C", "V", "K", "N"} else "nissan", profiles.get("infiniti" if vin[3] in {"C", "V", "K", "N"} else "nissan", {}))
    if wmi == "1C4" and len(vin) > 3:
        if vin[3] == "B":
            return "jeep", profiles.get("jeep", {})
        if vin[3] in {"C", "D"}:
            return "chrysler", profiles.get("chrysler", {})
        if vin[3] in {"X", "Z"}:
            return "dodge", profiles.get("dodge", {})
    if wmi == "2C3":
        key = "dodge" if vin[3:5] == "CD" else "chrysler"
        return key, profiles.get(key, {})

    for key, profile in profiles.items():
        if wmi in profile.get("wmi", []):
            return key, profile
    return None


def build_profile_source_url(profile: dict[str, Any], make_key: str, vin: str) -> str:
    sites = profile.get("sites") or []
    if not sites:
        return ""
    domain = sites[0]
    if "partsdeal" in domain or "partsnow" in domain or "partsgiant" in domain:
        return f"https://{domain}/page_product/pd?vin={urllib.parse.quote(vin)}&filter=()&pd=Car+Key&pdUrl=car_key"
    if domain == "bmwfans.info":
        return "https://bmwfans.info/"
    return f"https://{domain}/"


def fallback_profile_match(vin: str, fields: dict[str, str], profiles: dict[str, Any]) -> dict[str, Any] | None:
    detected = detect_make_profile(vin, fields, profiles)
    if not detected:
        return None
    make_key, profile = detected
    seed_part = profile.get("seed_part")
    if not seed_part:
        return None

    label = profile.get("label", fields.get("Make", make_key.title()))
    return {
        "confidence": "candidate_from_make_profile_verify_before_ordering",
        "fitment_basis": f"No exact VIN/YMM key match is stored yet. Returning the {label} make-profile OEM seed part from the imported Claude tool data as a candidate starting point.",
        "match_type": "make_profile_candidate",
        "notes": "Use this to start the OEM catalog lookup, not as final order approval. Confirm the part on the linked OEM site with VIN fitment before cutting/programming.",
        "parts": [
            {
                "description": f"{label} key / remote candidate from make profile",
                "part_number": seed_part,
                "replaces": [],
                "verification_required": True,
            }
        ],
        "source_url": build_profile_source_url(profile, make_key, vin),
    }


def minimal_profile_decode(vin: str, profiles: dict[str, Any], reason: str) -> DecodeResult | None:
    normalized = normalize_vin(vin)
    detected = detect_make_profile(normalized, {"Make": ""}, profiles)
    if not detected:
        return None
    _, profile = detected
    fields = compact_decode_fields(
        {
            "VIN": normalized,
            "Make": profile.get("label", ""),
            "ModelYear": MODEL_YEAR_CODES.get(normalized[9], ""),
            "ErrorCode": "PROFILE",
            "ErrorText": reason,
        }
    )
    return DecodeResult(vin=normalized, fields=fields, source="profile")


def compact_decode_fields(raw: dict[str, Any]) -> dict[str, str]:
    keys = [
        "VIN",
        "Make",
        "Model",
        "ModelYear",
        "Trim",
        "Series",
        "Series2",
        "BodyClass",
        "DisplacementL",
        "EngineModel",
        "DriveType",
        "Note",
        "ErrorCode",
        "ErrorText",
    ]
    return {key: str(raw.get(key, "") or "") for key in keys}


def fetch_nhtsa_decode(vin: str, timeout: float = 20.0) -> dict[str, str]:
    url = NHTSA_ENDPOINT.format(vin=urllib.parse.quote(vin))
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    results = payload.get("Results") or []
    if not results:
        raise VinKeyError(f"NHTSA returned no decode results for {vin}.")

    fields = compact_decode_fields(results[0])
    if fields.get("ErrorCode") and fields["ErrorCode"] != "0":
        raise VinKeyError(f"NHTSA decode warning for {vin}: {fields.get('ErrorText', '')}")
    return fields


def decode_vin(
    vin: str,
    *,
    offline: bool = False,
    cache_path: Path = DEFAULT_CACHE,
    update_cache: bool = False,
) -> DecodeResult:
    normalized = normalize_vin(vin)
    cache = load_cache(cache_path)
    if normalized in cache:
        return DecodeResult(vin=normalized, fields=cache[normalized], source="cache")

    if offline:
        raise VinKeyError(f"{normalized} is not in {cache_path}; run without --offline to use NHTSA.")

    fields = fetch_nhtsa_decode(normalized)
    if update_cache:
        cache[normalized] = fields
        save_json(cache_path, cache)
    return DecodeResult(vin=normalized, fields=fields, source="nhtsa")


def string_contains(haystack: str, needles: list[str]) -> bool:
    folded = haystack.casefold()
    return all(needle.casefold() in folded for needle in needles)


def value_matches(actual: str, expected: Any) -> bool:
    if expected is None:
        return True
    if isinstance(expected, list):
        return any(value_matches(actual, option) for option in expected)
    return str(actual).casefold() == str(expected).casefold()


def rule_matches(fields: dict[str, str], rule: dict[str, Any]) -> bool:
    match = rule.get("match", {})
    for field, expected in match.items():
        if field.endswith("_contains"):
            raw_field = field[: -len("_contains")]
            needles = expected if isinstance(expected, list) else [expected]
            if not string_contains(fields.get(raw_field, ""), [str(item) for item in needles]):
                return False
            continue
        if not value_matches(fields.get(field, ""), expected):
            return False
    return True


def resolve_key_parts(
    vin: str,
    *,
    offline: bool = False,
    catalog_path: Path = DEFAULT_CATALOG,
    cache_path: Path = DEFAULT_CACHE,
    profiles_path: Path = DEFAULT_PROFILES,
    update_cache: bool = False,
    include_profile_fallback: bool = True,
) -> dict[str, Any]:
    catalog = load_catalog(catalog_path)
    profiles = load_make_profiles(profiles_path)
    try:
        decode = decode_vin(vin, offline=offline, cache_path=cache_path, update_cache=update_cache)
    except (VinKeyError, OSError) as exc:
        if not include_profile_fallback:
            raise
        decode = minimal_profile_decode(vin, profiles, str(exc))
        if decode is None:
            raise
    exact = catalog.get("vin_confirmations", {})
    matches: list[dict[str, Any]] = []

    if decode.vin in exact:
        record = dict(exact[decode.vin])
        record["match_type"] = "exact_vin"
        matches.append(record)

    for rule in catalog.get("rules", []):
        if rule_matches(decode.fields, rule):
            record = dict(rule)
            record.pop("match", None)
            record["match_type"] = "nhtsa_rule"
            matches.append(record)

    if include_profile_fallback and not matches:
        fallback = fallback_profile_match(decode.vin, decode.fields, profiles)
        if fallback:
            matches.append(fallback)

    return {
        "vin": decode.vin,
        "decode_source": decode.source,
        "decode": decode.fields,
        "matches": matches,
        "detected_make_profile": (detect_make_profile(decode.vin, decode.fields, profiles) or ["", {}])[0],
    }


def resolve_many(vins: list[str], **kwargs: Any) -> list[dict[str, Any]]:
    return [resolve_key_parts(vin, **kwargs) for vin in vins]


def best_part_summary(result: dict[str, Any]) -> str:
    parts: list[str] = []
    for match in result["matches"]:
        for part in match.get("parts", []):
            part_number = part.get("part_number", "")
            if part_number and part_number not in parts:
                parts.append(part_number)
    return "; ".join(parts) if parts else "NO_CONFIRMED_MATCH"


def flatten_for_csv(result: dict[str, Any]) -> dict[str, str]:
    fields = result["decode"]
    replacements: list[str] = []
    superseded_by: list[str] = []
    sources: list[str] = []
    descriptions: list[str] = []
    for match in result["matches"]:
        if match.get("source_url"):
            sources.append(match["source_url"])
        for part in match.get("parts", []):
            descriptions.append(part.get("description", ""))
            replacements.extend(part.get("replaces", []))
            superseded_by.extend(part.get("superseded_by", []))

    return {
        "vin": result["vin"],
        "year": fields.get("ModelYear", ""),
        "make": fields.get("Make", ""),
        "model": fields.get("Model", ""),
        "trim": fields.get("Trim", ""),
        "series": fields.get("Series", ""),
        "engine": fields.get("EngineModel", "") or fields.get("DisplacementL", ""),
        "key_part_numbers": best_part_summary(result),
        "descriptions": "; ".join(sorted(set(filter(None, descriptions)))),
        "replaces": "; ".join(sorted(set(replacements))),
        "superseded_by": "; ".join(sorted(set(superseded_by))),
        "confidence": "; ".join(sorted(set(match.get("confidence", "") for match in result["matches"]))),
        "sources": "; ".join(sorted(set(sources))),
    }


def print_table(results: list[dict[str, Any]]) -> None:
    rows = [flatten_for_csv(result) for result in results]
    headers = ["vin", "year", "make", "model", "trim", "key_part_numbers", "confidence"]
    widths = {
        header: max(len(header), *(len(str(row.get(header, ""))) for row in rows))
        for header in headers
    }
    print("  ".join(header.upper().ljust(widths[header]) for header in headers))
    for row in rows:
        print("  ".join(row.get(header, "").ljust(widths[header]) for header in headers))


def write_csv(results: list[dict[str, Any]], path: Path) -> None:
    rows = [flatten_for_csv(result) for result in results]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decode VINs and resolve confirmed OEM key part numbers.")
    parser.add_argument("vins", nargs="+", help="VIN(s) to decode and resolve.")
    parser.add_argument("--offline", action="store_true", help="Use only cached NHTSA decode fixtures.")
    parser.add_argument("--update-cache", action="store_true", help="Cache live NHTSA results for future offline runs.")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG, help="Path to key part catalog JSON.")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="Path to NHTSA decode cache JSON.")
    parser.add_argument("--json", action="store_true", help="Print full JSON results.")
    parser.add_argument("--csv", type=Path, help="Write flattened results to CSV.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        results = resolve_many(
            args.vins,
            offline=args.offline,
            catalog_path=args.catalog,
            cache_path=args.cache,
            update_cache=args.update_cache,
        )
    except VinKeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.csv:
        write_csv(results, args.csv)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_table(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
