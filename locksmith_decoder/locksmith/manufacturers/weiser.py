"""Weiser WR3 / WR5 profiles."""
from .base import Profile, direct_decode, register

WR3 = register(Profile(
    keyway="WR3",
    name="Weiser WR3 (5-pin)",
    manufacturer="Weiser",
    pin_count=5,
    depths={
        1: 0.328, 2: 0.305, 3: 0.282, 4: 0.259,
        5: 0.236, 6: 0.213, 7: 0.190,
    },
    spacing=[0.216, 0.372, 0.528, 0.684, 0.840],
    macs=4,
    code_format="5 digits, each 1-7",
    decode=direct_decode(5, range(1, 8)),
    aliases=["WEISER", "WEISER-WR3"],
))

WR5 = register(Profile(
    keyway="WR5",
    name="Weiser WR5 (6-pin)",
    manufacturer="Weiser",
    pin_count=6,
    depths={
        1: 0.328, 2: 0.305, 3: 0.282, 4: 0.259,
        5: 0.236, 6: 0.213, 7: 0.190,
    },
    spacing=[0.216, 0.372, 0.528, 0.684, 0.840, 0.996],
    macs=4,
    code_format="6 digits, each 1-7",
    decode=direct_decode(6, range(1, 8)),
    aliases=["WEISER-WR5"],
))
