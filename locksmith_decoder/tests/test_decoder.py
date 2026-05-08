"""Test suite for the locksmith decoder.

Runs against >= 12 unique entries spanning every supported manufacturer.
Verifies bitting, depth-in-thousandths, MACS validation, error paths,
reverse encoding, batch CSV ingestion, and the auth gate.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from locksmith import Decoder, LicenseStore, LicenseError  # noqa: E402


# 12+ unique cases covering every registered keyway plus error paths.
CASES = [
    # (keyway, code, expected_bitting, expected_valid)
    ("SC1",  "12345",  (1, 2, 3, 4, 5),       True),
    ("SC1",  "67890",  (6, 7, 8, 9, 0),       False),  # Schlage MACS=7, jump 9->0=9 fails
    ("SC4",  "102938", (1, 0, 2, 9, 3, 8),    True),   # max jump 7
    ("KW1",  "13571",  (1, 3, 5, 7, 1),       False),  # KW1 MACS=4, jump 7->1=6 fails
    ("KW1",  "24642",  (2, 4, 6, 4, 2),       True),
    ("KW10", "234567", (2, 3, 4, 5, 6, 7),    True),
    ("M1",   "5482",   (5, 4, 8, 2),          True),
    ("M5",   "32145",  (3, 2, 1, 4, 5),       True),
    ("LA",   "654321", (6, 5, 4, 3, 2, 1),    True),
    ("LC",   "12345",  (1, 2, 3, 4, 5),       True),
    ("Y1",   "98765",  (9, 8, 7, 6, 5),       True),
    ("Y8",   "012345", (0, 1, 2, 3, 4, 5),    True),
    ("AR1",  "52173",  (5, 2, 1, 7, 3),       True),
    ("AR4",  "123456", (1, 2, 3, 4, 5, 6),    True),
    ("60",   "987654", (9, 8, 7, 6, 5, 4),    True),
    ("59",   "76543",  (7, 6, 5, 4, 3),       True),
    ("MED-ORIG", "123456", (1, 2, 3, 4, 5, 6), True),  # Medeco MACS=2, all diffs=1
    ("WR3",  "52316",  (5, 2, 3, 1, 6),       False),  # WR3 MACS=4, 1->6=5 fails
]


class TestDecoder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dec = Decoder()

    def test_at_least_12_unique_cases(self):
        self.assertGreaterEqual(len(CASES), 12)
        self.assertEqual(len({(k, c) for k, c, *_ in CASES}), len(CASES))

    def test_decoded_bitting_matches(self):
        for keyway, code, expected_bits, _ in CASES:
            with self.subTest(keyway=keyway, code=code):
                res = self.dec.decode(keyway, code)
                self.assertTrue(res.ok, f"{keyway}/{code} failed: {res.error}")
                self.assertEqual(res.bitting.bitting, expected_bits)

    def test_macs_validation(self):
        for keyway, code, _, expected_valid in CASES:
            with self.subTest(keyway=keyway, code=code):
                res = self.dec.decode(keyway, code)
                self.assertEqual(
                    res.bitting.valid, expected_valid,
                    msg=f"{keyway}/{code}: issues={res.bitting.issues}",
                )

    def test_depths_have_thousandths_inch_values(self):
        # Every cut should map to a positive depth in inches.
        for keyway, code, _, _ in CASES:
            res = self.dec.decode(keyway, code)
            self.assertEqual(len(res.bitting.inches), res.bitting.pin_count)
            for spacing, depth in res.bitting.inches:
                self.assertGreater(spacing, 0)
                self.assertGreater(depth, 0)
                self.assertLess(depth, 1.0)

    def test_unknown_keyway_returns_error(self):
        res = self.dec.decode("BOGUS-99", "12345")
        self.assertFalse(res.ok)
        self.assertIn("unknown keyway", res.error)

    def test_bad_code_format_returns_error(self):
        res = self.dec.decode("SC1", "abcde")
        self.assertFalse(res.ok)

        res2 = self.dec.decode("SC1", "1234")  # too few digits
        self.assertFalse(res2.ok)

        res3 = self.dec.decode("KW1", "13579")  # 8/9 not allowed in KW1
        self.assertFalse(res3.ok)

    def test_reverse_encode(self):
        self.assertEqual(self.dec.encode("SC1", [1, 2, 3, 4, 5]), "12345")
        self.assertEqual(self.dec.encode("KW1", [3, 4, 5, 4, 3]), "34543")
        with self.assertRaises(ValueError):
            self.dec.encode("KW1", [3, 4, 9, 4, 3])  # 9 invalid
        with self.assertRaises(ValueError):
            self.dec.encode("SC1", [1, 2, 3])        # wrong length

    def test_keyway_listing_covers_all_manufacturers(self):
        manufacturers = {p.manufacturer for p in self.dec.keyways()}
        for expected in {"Schlage", "Kwikset", "Master Lock", "Sargent",
                         "Yale", "Arrow", "Corbin Russwin", "Medeco", "Weiser"}:
            self.assertIn(expected, manufacturers)

    def test_decode_speed_under_50us(self):
        # Warm up + measure 1000 lookups; per-call must average <50us.
        for _ in range(50):
            self.dec.decode("SC1", "12345")
        t0 = time.perf_counter_ns()
        for _ in range(1000):
            self.dec.decode("SC1", "12345")
        avg_us = (time.perf_counter_ns() - t0) / 1000 / 1000
        self.assertLess(avg_us, 50, f"avg {avg_us:.2f} us per decode")

    def test_batch_csv(self):
        path = ROOT / "examples" / "sample_batch.csv"
        with path.open() as f:
            reader = csv.DictReader(f)
            jobs = [(r["keyway"], r["code"]) for r in reader]
        results = self.dec.decode_many(jobs)
        self.assertEqual(len(results), len(jobs))
        # All decoder calls return a result (ok or error captured).
        for r in results:
            self.assertIsNotNone(r.elapsed_us)


class TestAuth(unittest.TestCase):
    def test_enroll_and_authenticate(self):
        with tempfile.TemporaryDirectory() as td:
            store = LicenseStore(Path(td) / "lic.json")
            tok = store.enroll("Jane Smith", "LIC-9001", "CA")
            smith = store.authenticate(tok)
            self.assertEqual(smith.name, "Jane Smith")
            self.assertEqual(smith.license_number, "LIC-9001")
            with self.assertRaises(LicenseError):
                store.authenticate("wrong-token")
            with self.assertRaises(LicenseError):
                store.authenticate(None)

    def test_persisted_across_instances(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lic.json"
            store1 = LicenseStore(path)
            tok = store1.enroll("Joe Locks", "LIC-7000", "TX",
                                token="abc-test-token")
            store2 = LicenseStore(path)
            self.assertEqual(store2.authenticate(tok).name, "Joe Locks")


if __name__ == "__main__":
    unittest.main(verbosity=2)
