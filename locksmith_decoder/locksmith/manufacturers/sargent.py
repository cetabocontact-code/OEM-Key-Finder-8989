"""Sargent profiles (LA, LB, LC, etc.)."""
from .base import Profile, direct_decode, register

# Sargent 6-pin, depth 1-9 (standard commercial chart).
SARGENT_LA = register(Profile(
    keyway="LA",
    name="Sargent LA (6-pin)",
    manufacturer="Sargent",
    pin_count=6,
    depths={
        1: 0.328, 2: 0.308, 3: 0.288, 4: 0.268,
        5: 0.248, 6: 0.228, 7: 0.208, 8: 0.188, 9: 0.168,
    },
    spacing=[0.216, 0.372, 0.528, 0.684, 0.840, 0.996],
    macs=7,
    code_format="6 digits, each 1-9 (direct code)",
    decode=direct_decode(6, range(1, 10)),
    aliases=["SARGENT-LA", "SARGENT"],
))

# Sargent 5-pin LC keyway.
SARGENT_LC = register(Profile(
    keyway="LC",
    name="Sargent LC (5-pin)",
    manufacturer="Sargent",
    pin_count=5,
    depths={
        1: 0.328, 2: 0.308, 3: 0.288, 4: 0.268,
        5: 0.248, 6: 0.228, 7: 0.208, 8: 0.188, 9: 0.168,
    },
    spacing=[0.216, 0.372, 0.528, 0.684, 0.840],
    macs=7,
    code_format="5 digits, each 1-9",
    decode=direct_decode(5, range(1, 10)),
    aliases=["SARGENT-LC"],
))
