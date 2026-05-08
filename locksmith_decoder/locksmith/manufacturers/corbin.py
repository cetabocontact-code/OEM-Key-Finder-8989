"""Corbin / Russwin profiles."""
from .base import Profile, direct_decode, register

# Corbin 60 keyway, 6-pin.
CORBIN_60 = register(Profile(
    keyway="60",
    name="Corbin 60 (6-pin)",
    manufacturer="Corbin Russwin",
    pin_count=6,
    depths={
        1: 0.328, 2: 0.308, 3: 0.288, 4: 0.268,
        5: 0.248, 6: 0.228, 7: 0.208, 8: 0.188, 9: 0.168,
    },
    spacing=[0.216, 0.372, 0.528, 0.684, 0.840, 0.996],
    macs=7,
    code_format="6 digits, each 1-9",
    decode=direct_decode(6, range(1, 10)),
    aliases=["CORBIN", "CORBIN-60", "RUSSWIN"],
))

# Corbin 59 keyway, 5-pin.
CORBIN_59 = register(Profile(
    keyway="59",
    name="Corbin 59 (5-pin)",
    manufacturer="Corbin Russwin",
    pin_count=5,
    depths={
        1: 0.328, 2: 0.308, 3: 0.288, 4: 0.268,
        5: 0.248, 6: 0.228, 7: 0.208, 8: 0.188, 9: 0.168,
    },
    spacing=[0.216, 0.372, 0.528, 0.684, 0.840],
    macs=7,
    code_format="5 digits, each 1-9",
    decode=direct_decode(5, range(1, 10)),
    aliases=["CORBIN-59"],
))
