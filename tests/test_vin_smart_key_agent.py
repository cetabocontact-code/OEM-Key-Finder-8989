#!/usr/bin/env python3
"""Offline parsing/scoring tests for vin_smart_key_agent.

Network calls (NHTSA, OEM parts sites) are not exercised here. These tests only
prove the HTML extraction, part-number normalization, brand detection, search
URL building, and verification scoring are correct against fixed strings.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vin_smart_key_agent import (  # noqa: E402
    AgentError,
    DecodeData,
    build_search_url,
    detect_brand,
    extract_candidates,
    normalize_part_number,
    normalize_vin,
    select_best_part,
    verify_vin_context,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_vin_normalization() -> None:
    _assert(normalize_vin(" kmhm34aa4ra070319 ") == "KMHM34AA4RA070319", "VIN trim/upper")
    try:
        normalize_vin("not-a-vin")
    except AgentError:
        return
    raise AssertionError("Expected AgentError for invalid VIN")


def test_brand_detection() -> None:
    _assert(detect_brand("KMHM34AA4RA070319") == "hyundai", "KMH -> hyundai")
    _assert(detect_brand("KNDJN2A21E7058280") == "kia", "KND -> kia")
    _assert(detect_brand("3KPC24A64NE177716", "HYUNDAI") == "hyundai", "Mexico Hyundai")
    _assert(detect_brand("3KPFT4DE2SE036913", "KIA") == "kia", "Mexico Kia")
    try:
        detect_brand("3KPC24A64NE177716", "")
    except AgentError:
        pass
    else:
        raise AssertionError("Shared WMI without decoded make should fail")
    try:
        detect_brand("WBA73AK08N7K27666")
    except AgentError:
        return
    raise AssertionError("Non-Hyundai/Kia WMI should raise")


def test_part_number_normalization() -> None:
    _assert(normalize_part_number("95440KL000") == "95440-KL000", "compact -> dashed")
    _assert(normalize_part_number("95440-KL000") == "95440-KL000", "already dashed")
    _assert(normalize_part_number(" 81996-aa000 ") == "81996-AA000", "trim + case")
    _assert(normalize_part_number("954A0 KL000") == "954A0-KL000", "new prefix family")


def test_search_url_construction() -> None:
    _, url = build_search_url("hyundai", "KMHM34AA4RA070319")
    _assert("hyundaipartsdeal.com" in url, "Hyundai domain")
    _assert("vin=KMHM34AA4RA070319" in url, "VIN in query")
    _assert("pd=Car+Key" in url, "Filtered to car key")

    _, url = build_search_url("kia", "3KPFT4DE2SE036913")
    _assert("kiapartsnow.com" in url, "Kia domain")
    _assert("vin=3KPFT4DE2SE036913" in url, "Kia VIN in query")


def test_extract_candidates_from_html() -> None:
    html = """
    <html><body>
      <a href="/p/Hyundai_2024_IONIQ-6/smart">Smart Key Transmitter 95440-KL000 (without Auto Park)</a>
      <a href="/p/Hyundai_2024_IONIQ-6/sk2">Smart Key Transmitter 95440KL200 with Auto Park</a>
      <a href="/p/Hyundai_2024_IONIQ-6/blank">Key Blank 81996-AA000</a>
      <p>VIN KMHM34AA4RA070319 - 2024 Hyundai Ioniq 6 SEL</p>
    </body></html>
    """
    candidates = extract_candidates(html, "https://www.hyundaipartsdeal.com/page_product/pd")
    part_numbers = {candidate.part_number for candidate in candidates}
    _assert(
        {"95440-KL000", "95440-KL200", "81996-AA000"} <= part_numbers,
        f"Expected 3 known parts, got {part_numbers}",
    )
    smart_candidate = next(candidate for candidate in candidates if candidate.part_number == "95440-KL000")
    _assert(
        smart_candidate.product_url.endswith("/p/Hyundai_2024_IONIQ-6/smart"),
        "Relative href should absolutize to the parts site",
    )


def test_select_best_part_prefers_smart_key() -> None:
    decode = DecodeData(vin="KMHM34AA4RA070319", year="2024", make="HYUNDAI", model="Ioniq 6", trim="SEL")
    html = """
    <a href="/p/a">Smart Key Transmitter 95440-KL000 without Auto Park</a>
    <a href="/p/b">Key Blank 81996-AA000</a>
    <a href="/p/c">Random Bracket 95440-AB123</a>
    """
    candidates = extract_candidates(html, "https://www.hyundaipartsdeal.com/")
    best = select_best_part(candidates, decode)
    _assert(best is not None, "Expected a verified pick")
    _assert(best.part_number == "95440-KL000", f"Wrong winner: {best.part_number}")


def test_verify_vin_context_matches_year_and_model() -> None:
    decode = DecodeData(vin="KMHM34AA4RA070319", year="2024", make="HYUNDAI", model="Ioniq 6")
    html = "<p>2024 Hyundai Ioniq 6 SEL fits this part</p>"
    ok, reason = verify_vin_context(html, decode)
    _assert(ok, f"Expected match, got: {reason}")

    html_no_match = "<p>Generic page with no vehicle details</p>"
    ok, _ = verify_vin_context(html_no_match, decode)
    _assert(not ok, "Should not falsely verify a generic page")


def main() -> int:
    tests = [
        test_vin_normalization,
        test_brand_detection,
        test_part_number_normalization,
        test_search_url_construction,
        test_extract_candidates_from_html,
        test_select_best_part_prefers_smart_key,
        test_verify_vin_context_matches_year_and_model,
    ]
    failures: list[str] = []
    for test in tests:
        try:
            test()
            print(f"  ok  {test.__name__}")
        except AssertionError as exc:
            failures.append(f"{test.__name__}: {exc}")
            print(f"  FAIL {test.__name__}: {exc}")
    if failures:
        print(f"\n{len(failures)} test(s) failed")
        return 1
    print(f"\nAll {len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
