"""Schlage SC1 / SC4 profiles.

Depth and space values are taken from the Schlage Commercial published
depth & space chart (industry-standard locksmith reference). Locksmiths
should still cross-check against their authoritative reference before
cutting production keys.
"""
from .base import Profile, direct_decode, register

# 5-pin SC1 (Classic / residential), pins 0-9, 0.015" increments.
SC1 = register(Profile(
    keyway="SC1",
    name="Schlage SC1 (Classic, 5-pin)",
    manufacturer="Schlage",
    pin_count=5,
    depths={
        0: 0.335, 1: 0.320, 2: 0.305, 3: 0.290, 4: 0.275,
        5: 0.260, 6: 0.245, 7: 0.230, 8: 0.215, 9: 0.200,
    },
    spacing=[0.231, 0.387, 0.543, 0.699, 0.855],
    macs=7,
    code_format="5 digits, each 0-9 (direct code)",
    decode=direct_decode(5, range(0, 10)),
    aliases=["SCHLAGE-SC1", "SC"],
    notes="Direct code: digits map 1:1 to bitting depths.",
))

# 6-pin SC4 (commercial). Same depth chart, extra position.
SC4 = register(Profile(
    keyway="SC4",
    name="Schlage SC4 (Commercial, 6-pin)",
    manufacturer="Schlage",
    pin_count=6,
    depths={
        0: 0.335, 1: 0.320, 2: 0.305, 3: 0.290, 4: 0.275,
        5: 0.260, 6: 0.245, 7: 0.230, 8: 0.215, 9: 0.200,
    },
    spacing=[0.231, 0.387, 0.543, 0.699, 0.855, 1.011],
    macs=7,
    code_format="6 digits, each 0-9 (direct code)",
    decode=direct_decode(6, range(0, 10)),
    aliases=["SCHLAGE-SC4"],
))

# Schlage Everest C123 / 6-pin restricted keyway. Same depth math, narrower
# allowed depth set in real life — kept as 0-9 here for tool flexibility.
EVEREST = register(Profile(
    keyway="C123",
    name="Schlage Everest C123 (6-pin)",
    manufacturer="Schlage",
    pin_count=6,
    depths={
        0: 0.335, 1: 0.320, 2: 0.305, 3: 0.290, 4: 0.275,
        5: 0.260, 6: 0.245, 7: 0.230, 8: 0.215, 9: 0.200,
    },
    spacing=[0.231, 0.387, 0.543, 0.699, 0.855, 1.011],
    macs=7,
    code_format="6 digits 0-9",
    decode=direct_decode(6, range(0, 10)),
    aliases=["EVEREST", "SCHLAGE-EVEREST"],
))
