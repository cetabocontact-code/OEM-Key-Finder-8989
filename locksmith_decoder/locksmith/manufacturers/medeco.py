"""Medeco Original / Biaxial profile.

Medeco uses angled cuts; this profile only resolves the depth component
of the bitting. Angle (L/C/R) decoding requires the locksmith's bitting
list and is therefore not supported here.
"""
from .base import Profile, direct_decode, register

MEDECO_ORIG = register(Profile(
    keyway="MED-ORIG",
    name="Medeco Original (6-pin, depth only)",
    manufacturer="Medeco",
    pin_count=6,
    depths={
        1: 0.317, 2: 0.302, 3: 0.287, 4: 0.272,
        5: 0.257, 6: 0.242,
    },
    spacing=[0.216, 0.372, 0.528, 0.684, 0.840, 0.996],
    macs=2,
    code_format="6 digits, each 1-6 (depth only — angles not decoded)",
    decode=direct_decode(6, range(1, 7)),
    aliases=["MEDECO", "MEDECO-ORIG"],
    notes="Angles must be looked up from manufacturer bitting list.",
))
