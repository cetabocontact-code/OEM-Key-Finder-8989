"""Yale GA / 8 profile."""
from .base import Profile, direct_decode, register

YALE_GA = register(Profile(
    keyway="Y1",
    name="Yale GA (5-pin)",
    manufacturer="Yale",
    pin_count=5,
    depths={
        0: 0.293, 1: 0.275, 2: 0.257, 3: 0.239, 4: 0.221,
        5: 0.203, 6: 0.185, 7: 0.167, 8: 0.149, 9: 0.131,
    },
    spacing=[0.196, 0.352, 0.508, 0.664, 0.820],
    macs=7,
    code_format="5 digits, each 0-9 (direct code)",
    decode=direct_decode(5, range(0, 10)),
    aliases=["YALE", "YALE-GA"],
))

YALE_8 = register(Profile(
    keyway="Y8",
    name="Yale 8 (6-pin)",
    manufacturer="Yale",
    pin_count=6,
    depths={
        0: 0.293, 1: 0.275, 2: 0.257, 3: 0.239, 4: 0.221,
        5: 0.203, 6: 0.185, 7: 0.167, 8: 0.149, 9: 0.131,
    },
    spacing=[0.196, 0.352, 0.508, 0.664, 0.820, 0.976],
    macs=7,
    code_format="6 digits, each 0-9",
    decode=direct_decode(6, range(0, 10)),
    aliases=["YALE-8"],
))
