"""Arrow AR1 profile."""
from .base import Profile, direct_decode, register

AR1 = register(Profile(
    keyway="AR1",
    name="Arrow AR1 (5-pin)",
    manufacturer="Arrow",
    pin_count=5,
    depths={
        1: 0.310, 2: 0.295, 3: 0.280, 4: 0.265,
        5: 0.250, 6: 0.235, 7: 0.220,
    },
    spacing=[0.216, 0.372, 0.528, 0.684, 0.840],
    macs=7,
    code_format="5 digits, each 1-7",
    decode=direct_decode(5, range(1, 8)),
    aliases=["ARROW", "ARROW-AR1"],
))

AR4 = register(Profile(
    keyway="AR4",
    name="Arrow AR4 (6-pin)",
    manufacturer="Arrow",
    pin_count=6,
    depths={
        1: 0.310, 2: 0.295, 3: 0.280, 4: 0.265,
        5: 0.250, 6: 0.235, 7: 0.220,
    },
    spacing=[0.216, 0.372, 0.528, 0.684, 0.840, 0.996],
    macs=7,
    code_format="6 digits, each 1-7",
    decode=direct_decode(6, range(1, 8)),
    aliases=["ARROW-AR4"],
))
