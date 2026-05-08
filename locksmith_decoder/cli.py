#!/usr/bin/env python3
"""Locksmith Decoder CLI."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Tuple

from locksmith import (
    CalibrationStore,
    Decoder,
    LicenseError,
    LicenseStore,
    SealError,
    build_manifest,
    hardware_fingerprint,
    issue_seal,
    load_seal,
    sync as run_sync,
    verify_seal,
    write_seal,
)
from locksmith.sync import LocalSource


ROOT = Path(__file__).resolve().parent
DEFAULT_LICENSES = ROOT / "data" / "licensed_locksmiths.json"
DEFAULT_CALIBRATION = ROOT / "data" / "calibration.json"
DEFAULT_SEAL = ROOT / "data" / "seal.json"
DEFAULT_DATA_DIR = ROOT / "data" / "synced"


def _store() -> LicenseStore:
    return LicenseStore(Path(os.environ.get("LOCKSMITH_LICENSES", DEFAULT_LICENSES)))


def _calibration() -> CalibrationStore:
    return CalibrationStore.load(
        Path(os.environ.get("LOCKSMITH_CALIBRATION", DEFAULT_CALIBRATION))
    )


def _seal_path() -> Path:
    return Path(os.environ.get("LOCKSMITH_SEAL", DEFAULT_SEAL))


def _authenticate(args) -> str:
    """Verify locksmith token + (if present) hardware seal."""
    if args.skip_auth or os.environ.get("LOCKSMITH_SKIP_AUTH") == "1":
        return "auth-bypassed"
    token = args.token or os.environ.get("LOCKSMITH_TOKEN")
    try:
        smith = _store().authenticate(token)
    except LicenseError as exc:
        sys.exit(
            f"access denied: {exc}\n"
            f"set LOCKSMITH_TOKEN or pass --token. Enroll with: "
            f"python cli.py enroll \"Name\" LIC-### STATE"
        )
    seal_path = _seal_path()
    if seal_path.exists():
        try:
            seal = load_seal(seal_path)
            verify_seal(seal, token)
        except SealError as exc:
            sys.exit(
                f"hardware seal failed: {exc}\n"
                f"refresh with: python cli.py seal --ttl 30"
            )
    print(f"# authenticated as {smith.name} (lic {smith.license_number}/"
          f"{smith.state})", file=sys.stderr)
    return smith.license_number


def cmd_decode(args) -> int:
    _authenticate(args)
    dec = Decoder(calibration=_calibration() if args.calibrated else None)
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
    dec = Decoder(calibration=_calibration() if args.calibrated else None)
    rows: List[Tuple[str, str]] = []
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
            "warnings": "; ".join(r.bitting.checksum_warnings) if r.bitting else "",
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
    print("access token (save this — only shown once):")
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


def cmd_calibrate(args) -> int:
    _authenticate(args)
    store = _calibration()
    if args.subcmd == "add":
        store.add(args.machine_id, args.name)
        print(f"added machine '{args.machine_id}' ({args.name}); active.")
    elif args.subcmd == "list":
        if not store.profiles:
            print("no machines registered.")
            return 0
        for mid, p in store.profiles.items():
            mark = "*" if mid == store.active else " "
            print(f"{mark} {mid:<14} {p.name:<14} "
                  f"spacing_off={p.spacing_offset_in:+.4f}\" "
                  f"depth_off={p.depth_offset_in:+.4f}\" "
                  f"samples={p.sample_count} "
                  f"{'ALERT_OOT' if p.out_of_tolerance() else 'ok'}")
    elif args.subcmd == "select":
        store.select(args.machine_id)
        print(f"active machine -> {args.machine_id}")
    elif args.subcmd == "test-cut":
        dec = Decoder()
        res = dec.decode(args.keyway, args.code)
        if not res.ok:
            sys.exit(f"reference decode failed: {res.error}")
        if len(args.measured) != res.bitting.pin_count * 2:
            sys.exit(f"pass {res.bitting.pin_count*2} measurements: "
                     f"sp1 dp1 sp2 dp2 ...")
        measured = [(args.measured[i], args.measured[i + 1])
                    for i in range(0, len(args.measured), 2)]
        prof = store.record_test_cut(
            args.machine_id, args.keyway,
            res.bitting.inches, measured,
            time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        print(f"calibrated {args.machine_id}: "
              f"spacing_off={prof.spacing_offset_in:+.4f}\" "
              f"depth_off={prof.depth_offset_in:+.4f}\" "
              f"{'(OUT OF TOLERANCE)' if prof.out_of_tolerance() else ''}")
    return 0


def cmd_seal(args) -> int:
    token = args.token or os.environ.get("LOCKSMITH_TOKEN")
    if not token:
        sys.exit("LOCKSMITH_TOKEN required to (re)issue seal.")
    smith = _store().authenticate(token)
    seal = issue_seal(smith.license_number, token, ttl_days=args.ttl)
    write_seal(_seal_path(), seal)
    print(f"sealed for {smith.name} (lic {smith.license_number})")
    print(f"  hardware fp: {seal.hardware_fp[:16]}...")
    print(f"  expires in : {args.ttl} days  ({time.ctime(seal.expires_at)})")
    return 0


def cmd_verify_seal(args) -> int:
    token = args.token or os.environ.get("LOCKSMITH_TOKEN")
    if not token:
        sys.exit("LOCKSMITH_TOKEN required.")
    seal = load_seal(_seal_path())
    try:
        verify_seal(seal, token)
    except SealError as exc:
        sys.exit(f"INVALID: {exc}")
    print(f"seal OK; expires in {seal.remaining_seconds()//86400} day(s)")
    print(f"hardware fingerprint: {hardware_fingerprint()[:16]}...")
    return 0


def cmd_sync(args) -> int:
    _authenticate(args)
    src = LocalSource(Path(args.from_dir))
    target = Path(args.to_dir or DEFAULT_DATA_DIR)
    report = run_sync(src, target, args.key)
    print(f"sync to {target}:")
    print(f"  added    : {len(report.added)}")
    print(f"  updated  : {len(report.updated)}")
    print(f"  unchanged: {len(report.unchanged)}")
    print(f"  failed   : {len(report.failed)}")
    print(f"  bytes    : {report.bytes_transferred}")
    if report.failed:
        for f in report.failed:
            print(f"  ! {f}")
        return 2
    return 0


def cmd_build_manifest(args) -> int:
    m = build_manifest(Path(args.dir), args.key)
    out = Path(args.dir) / "manifest.json"
    out.write_text(m.to_json())
    print(f"wrote {out}  ({len(m.files)} files)")
    return 0


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="locksmith-decoder",
        description="Offline key-code decoder for verified locksmiths",
    )
    p.add_argument("--token")
    p.add_argument("--skip-auth", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_dec = sub.add_parser("decode")
    p_dec.add_argument("keyway")
    p_dec.add_argument("code")
    p_dec.add_argument("--json", action="store_true")
    p_dec.add_argument("--calibrated", action="store_true",
                       help="apply active machine calibration to inches")
    p_dec.set_defaults(func=cmd_decode)

    p_batch = sub.add_parser("batch")
    p_batch.add_argument("csv_path")
    p_batch.add_argument("--out")
    p_batch.add_argument("--calibrated", action="store_true")
    p_batch.set_defaults(func=cmd_batch)

    sub.add_parser("keyways").set_defaults(func=cmd_keyways)

    p_enc = sub.add_parser("encode")
    p_enc.add_argument("keyway")
    p_enc.add_argument("bitting", nargs="+", type=int)
    p_enc.set_defaults(func=cmd_encode)

    p_enr = sub.add_parser("enroll")
    p_enr.add_argument("name")
    p_enr.add_argument("license_number")
    p_enr.add_argument("state")
    p_enr.add_argument("--token")
    p_enr.set_defaults(func=cmd_enroll)

    sub.add_parser("list-locksmiths").set_defaults(func=cmd_list_locksmiths)

    p_cal = sub.add_parser("calibrate", help="manage cutting-machine calibration")
    cal_sub = p_cal.add_subparsers(dest="subcmd", required=True)
    a = cal_sub.add_parser("add")
    a.add_argument("machine_id"); a.add_argument("name")
    cal_sub.add_parser("list")
    s = cal_sub.add_parser("select"); s.add_argument("machine_id")
    t = cal_sub.add_parser("test-cut")
    t.add_argument("machine_id")
    t.add_argument("keyway")
    t.add_argument("code")
    t.add_argument("measured", nargs="+", type=float,
                   help="alternating spacing/depth in inches per pin")
    p_cal.set_defaults(func=cmd_calibrate)

    p_seal = sub.add_parser("seal", help="issue 30-day hardware-bound seal")
    p_seal.add_argument("--ttl", type=int, default=30)
    p_seal.set_defaults(func=cmd_seal)

    sub.add_parser("verify-seal").set_defaults(func=cmd_verify_seal)

    p_sync = sub.add_parser("sync", help="pull verified delta from data source")
    p_sync.add_argument("from_dir")
    p_sync.add_argument("--to-dir", dest="to_dir")
    p_sync.add_argument("--key", required=True,
                        help="HMAC key shared with the manifest publisher")
    p_sync.set_defaults(func=cmd_sync)

    p_bm = sub.add_parser("build-manifest", help="(publisher) build signed manifest")
    p_bm.add_argument("dir")
    p_bm.add_argument("--key", required=True)
    p_bm.set_defaults(func=cmd_build_manifest)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
