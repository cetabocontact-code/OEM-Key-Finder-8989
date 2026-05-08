"""Kwikset KW1 / KW10 profiles."""
from .base import Profile, direct_decode, register

KW1 = register(Profile(
    keyway="KW1",
    name="Kwikset KW1 (5-pin)",
    manufacturer="Kwikset",
    pin_count=5,
    depths={
        1: 0.329, 2: 0.306, 3: 0.283, 4: 0.260,
        5: 0.237, 6: 0.214, 7: 0.191,
    },
    spacing=[0.247, 0.403, 0.559, 0.715, 0.871],
    macs=4,
    code_format="5 digits, each 1-7 (direct code)",
    decode=direct_decode(5, range(1, 8)),
    aliases=["KWIKSET", "KWIKSET-KW1"],
    notes="Direct code; depth 1 is shallowest, 7 is deepest.",
))

KW10 = register(Profile(
    keyway="KW10",
    name="Kwikset KW10 (6-pin)",
    manufacturer="Kwikset",
    pin_count=6,
    depths={
        1: 0.329, 2: 0.306, 3: 0.283, 4: 0.260,
        5: 0.237, 6: 0.214, 7: 0.191,
    },
    spacing=[0.247, 0.403, 0.559, 0.715, 0.871, 1.027],
    macs=4,
    code_format="6 digits, each 1-7 (direct code)",
    decode=direct_decode(6, range(1, 8)),
    aliases=["KWIKSET-KW10"],
))
