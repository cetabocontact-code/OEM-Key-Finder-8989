#!/usr/bin/env python3
"""Locksmith Decoder CLI.

Usage:
  python cli.py decode SC1 12345
  python cli.py decode KW1 13571 --json
  python cli.py batch examples/sample_batch.csv
  python cli.py keyways
  python cli.py encode SC1 1 2 3 4 5
  python cli.py enroll "Jane Smith" LIC-12345 CA
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import List

from locksmith import Decoder, LicenseError, LicenseStore


ROOT = Path(__file__).resolve().parent
DEFAULT_LICENSES = ROOT / "data" / "licensed_locksmiths.json"


def _store() -> LicenseStore:
    return LicenseStore(Path(os.environ.get("LOCKSMITH_LICENSES", DEFAULT_LICENSES)))


def _authenticate(args) -> None:
    """Verify a locksmith token unless --skip-auth is given (CI / tests)."""
    if args.skip_auth or os.environ.get("LOCKSMITH_SKIP_AUTH") == "1":
        return
    token = args.token or os.environ.get("LOCKSMITH_TOKEN")
    try:
        smith = _store().authenticate(token)
    except LicenseError as exc:
        sys.exit(
            f"access denied: {exc}\n"
            f"set LOCKSMITH_TOKEN or pass --token. "
            f"Enroll with: python cli.py enroll \"Name\" LIC-### STATE"
        )
    print(f"# authenticated as {smith.name} (lic {smith.license_number}/{smith.state})",
          file=sys.stderr)


def cmd_decode(args) -> int:
    _authenticate(args)
    dec = Decoder()
    res = dec.decode(args.keyway, args.code)
    if args.json:
        print(json.dumps(res.to_dict(), indent=2))
    else:
        if not res.ok:
            print(f"ERROR: {res.error}")
            return 2
        print(res.bitting.pretty())
        print(f"\n(decoded in {res.elapsed_us} us)")
    return 0 if res.ok else 2


def cmd_batch(args) -> int:
    _authenticate(args)
    dec = Decoder()
    rows = []
    with open(args.csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((row["keyway"], row["code"]))
    t0 = time.perf_counter()
    results = dec.decode_many(rows)
    dt = time.perf_counter() - t0

    out_rows = []
    for r in results:
        out_rows.append({
            "code": r.code,
            "keyway": r.keyway,
            "ok": r.ok,
            "error": r.error or "",
            "bitting": "-".join(str(b) for b in r.bitting.bitting) if r.bitting else "",
            "valid": r.bitting.valid if r.bitting else "",
            "elapsed_us": r.elapsed_us,
        })

    if args.out:
        with open(args.out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            writer.writeheader()
            writer.writerows(out_rows)
        print(f"wrote {len(out_rows)} rows to {args.out}")
    else:
        for row in out_rows:
            print(json.dumps(row))

    print(f"# {len(rows)} codes in {dt*1000:.2f} ms "
          f"({(dt/len(rows))*1e6:.1f} us each)", file=sys.stderr)
    return 0


def cmd_keyways(args) -> int:
    _authenticate(args)
    dec = Decoder()
    print(f"{'KEYWAY':<10} {'PINS':<5} {'MACS':<5} MANUFACTURER         NAME")
    print("-" * 78)
    for prof in dec.keyways():
        print(f"{prof.keyway:<10} {prof.pin_count:<5} {prof.macs:<5} "
              f"{prof.manufacturer:<20} {prof.name}")
    return 0


def cmd_encode(args) -> int:
    _authenticate(args)
    dec = Decoder()
    try:
        code = dec.encode(args.keyway, args.bitting)
    except (KeyError, ValueError) as exc:
        sys.exit(f"error: {exc}")
    print(code)
    return 0


def cmd_enroll(args) -> int:
    store = _store()
    token = store.enroll(args.name, args.license_number, args.state, args.token)
    print(f"enrolled {args.name} (lic {args.license_number}/{args.state})")
    print(f"access token (save this — only shown once):")
    print(f"  {token}")
    print(f"use with: export LOCKSMITH_TOKEN={token}")
    return 0


def cmd_list_locksmiths(args) -> int:
    store = _store()
    smiths = store.list()
    if not smiths:
        print("no locksmiths enrolled. use 'enroll' to add one.")
        return 0
    for s in smiths:
        print(f"  {s['name']:<24} lic {s['license_number']:<14} state {s['state']}")
    return 0


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="locksmith-decoder",
                                description="Fast offline key-code decoder for verified locksmiths")
    p.add_argument("--token", help="locksmith access token (overrides env)")
    p.add_argument("--skip-auth", action="store_true",
                   help="bypass auth check (for CI/tests)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_dec = sub.add_parser("decode", help="decode a single code")
    p_dec.add_argument("keyway")
    p_dec.add_argument("code")
    p_dec.add_argument("--json", action="store_true")
    p_dec.set_defaults(func=cmd_decode)

    p_batch = sub.add_parser("batch", help="decode codes from a CSV (keyway,code)")
    p_batch.add_argument("csv_path")
    p_batch.add_argument("--out", help="write CSV results")
    p_batch.set_defaults(func=cmd_batch)

    p_keys = sub.add_parser("keyways", help="list supported keyways")
    p_keys.set_defaults(func=cmd_keyways)

    p_enc = sub.add_parser("encode", help="bitting -> direct code")
    p_enc.add_argument("keyway")
    p_enc.add_argument("bitting", nargs="+", type=int)
    p_enc.set_defaults(func=cmd_encode)

    p_enr = sub.add_parser("enroll", help="register a verified locksmith")
    p_enr.add_argument("name")
    p_enr.add_argument("license_number")
    p_enr.add_argument("state")
    p_enr.add_argument("--token", help="use a chosen token instead of generating one")
    p_enr.set_defaults(func=cmd_enroll)

    p_lst = sub.add_parser("list-locksmiths", help="list enrolled locksmiths")
    p_lst.set_defaults(func=cmd_list_locksmiths)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
