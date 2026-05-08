"""Master Lock #3 / #5 / #7 padlock profiles."""
from .base import Profile, direct_decode, register

# Master #3 padlock — 4-pin, depths 1-8.
MASTER_3 = register(Profile(
    keyway="M1",
    name="Master Lock #3 (4-pin)",
    manufacturer="Master Lock",
    pin_count=4,
    depths={
        1: 0.245, 2: 0.230, 3: 0.215, 4: 0.200,
        5: 0.185, 6: 0.170, 7: 0.155, 8: 0.140,
    },
    spacing=[0.156, 0.250, 0.344, 0.438],
    macs=7,
    code_format="4 digits, each 1-8 (direct code)",
    decode=direct_decode(4, range(1, 9)),
    aliases=["MASTER-3", "MASTER3"],
))

# Master #5 padlock — 5-pin, larger body, depths 1-8.
MASTER_5 = register(Profile(
    keyway="M5",
    name="Master Lock #5 (5-pin)",
    manufacturer="Master Lock",
    pin_count=5,
    depths={
        1: 0.260, 2: 0.245, 3: 0.230, 4: 0.215,
        5: 0.200, 6: 0.185, 7: 0.170, 8: 0.155,
    },
    spacing=[0.156, 0.281, 0.406, 0.531, 0.656],
    macs=7,
    code_format="5 digits, each 1-8 (direct code)",
    decode=direct_decode(5, range(1, 9)),
    aliases=["MASTER-5", "MASTER5"],
))

# Master #7 / 1500 series.
MASTER_7 = register(Profile(
    keyway="M7",
    name="Master Lock #7 / 1500 series (4-pin)",
    manufacturer="Master Lock",
    pin_count=4,
    depths={
        1: 0.245, 2: 0.230, 3: 0.215, 4: 0.200,
        5: 0.185, 6: 0.170, 7: 0.155, 8: 0.140,
    },
    spacing=[0.156, 0.250, 0.344, 0.438],
    macs=7,
    code_format="4 digits, each 1-8",
    decode=direct_decode(4, range(1, 9)),
    aliases=["MASTER-7", "MASTER1500"],
))
