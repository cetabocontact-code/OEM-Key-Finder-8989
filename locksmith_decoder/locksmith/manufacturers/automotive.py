"""Automotive profiles (demo: Ford H75 8-cut, Toyota TR47 6-cut).

These exist to exercise checksum / parity validation. Depth & space
values are example values; treat as illustrative until verified against
your authoritative auto-key reference.
"""
from .base import Profile, direct_decode, register

# Ford H75 / 10-cut (uses positions 1-8 in this simplified profile).
# Depths 1-4 only. Sum-parity rule registered in checksum.py.
H75 = register(Profile(
    keyway="H75",
    name="Ford H75 8-cut (auto)",
    manufacturer="Ford",
    pin_count=8,
    depths={1: 0.260, 2: 0.245, 3: 0.230, 4: 0.215},
    spacing=[0.155, 0.247, 0.339, 0.431, 0.523, 0.615, 0.707, 0.799],
    macs=2,
    code_format="8 digits, each 1-4 (sum must be even)",
    decode=direct_decode(8, range(1, 5)),
    aliases=["FORD-H75", "FORD-8CUT"],
    notes="Sum-parity rule: total of cut depths must be even.",
))

# Toyota TR47 6-cut. Depths 1-4. Range-bounded parity rule.
TR47 = register(Profile(
    keyway="TR47",
    name="Toyota TR47 6-cut (auto)",
    manufacturer="Toyota",
    pin_count=6,
    depths={1: 0.245, 2: 0.230, 3: 0.215, 4: 0.200},
    spacing=[0.142, 0.220, 0.298, 0.376, 0.454, 0.532],
    macs=2,
    code_format="6 digits, each 1-4",
    decode=direct_decode(6, range(1, 5)),
    aliases=["TOYOTA-TR47"],
    notes="Sum-in-range envelope check (8..22).",
))
