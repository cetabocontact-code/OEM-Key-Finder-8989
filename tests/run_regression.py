#!/usr/bin/env python3
"""Regression tests for supplied confirmed VIN -> key part examples."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vin_key_tool import best_part_summary, resolve_key_parts  # noqa: E402


EXPECTED = {
    "19UDE4H66TA000653": "08E92-3S5-200",
    "1HGCY1F39RA023637": "72147-T20-A11",
    "WBA73AK08N7K27666": "51212469144",
    "2C4RC1L71PR618182": "68217832AD",
    "1FTFW3LD6SFB00855": "GB5Z-15K601-A",
    "1GKKNULS6MZ165460": "13522895",
    "3KPC24A64NE177716": "95430-J0800",
    "5N1DL1HUXPC376439": "T99K1-6SA00",
    "3KPFT4DE2SE036913": "95430GG000",
    "3MVDMBBM7RM694230": "BCYN675DYB",
    "JF2SKARC9PH490439": "88835FL031",
}


def main() -> int:
    failures: list[str] = []
    for vin, expected_part in EXPECTED.items():
        result = resolve_key_parts(vin, offline=True)
        actual_part = best_part_summary(result)
        decode = result["decode"]
        if decode.get("ErrorCode") != "0":
            failures.append(f"{vin}: NHTSA fixture is not a clean decode: {decode.get('ErrorText')}")
        if actual_part != expected_part:
            failures.append(f"{vin}: expected {expected_part}, got {actual_part}")

    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"PASS: {len(EXPECTED)} confirmed VIN key-part mappings matched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
