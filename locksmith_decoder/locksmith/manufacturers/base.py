"""Base profile types and registry for manufacturer cards."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


# A code lookup function takes the raw user-supplied code string and returns
# the corresponding bitting tuple, or raises ValueError.
CodeLookup = Callable[[str], Tuple[int, ...]]


@dataclass(frozen=True)
class Profile:
    """A keyway / code-series profile.

    Depths are in inches, measured from the bottom of the cut to the
    blade reference plane. Spacing entries are distances from the
    shoulder to each cut's center, also in inches.
    """

    keyway: str           # e.g. "SC1"
    name: str             # display name
    manufacturer: str     # e.g. "Schlage"
    pin_count: int
    depths: Dict[int, float]
    spacing: List[float]
    macs: int             # Maximum Adjacent Cut Specification
    code_format: str
    decode: CodeLookup
    notes: str = ""
    aliases: List[str] = field(default_factory=list)

    def valid_depth(self, d: int) -> bool:
        return d in self.depths


REGISTRY: Dict[str, Profile] = {}


def register(profile: Profile) -> Profile:
    """Add a profile to the global registry. Aliases are resolved too."""
    keys = [profile.keyway.upper(), *(a.upper() for a in profile.aliases)]
    for k in keys:
        if k in REGISTRY:
            raise RuntimeError(f"duplicate keyway registration: {k}")
        REGISTRY[k] = profile
    return profile


def direct_decode(pin_count: int, valid: range) -> CodeLookup:
    """Build a 'direct code' decoder where each digit *is* the bitting depth."""
    valid_set = set(valid)

    def _decode(code: str) -> Tuple[int, ...]:
        s = code.strip()
        if not s.isdigit():
            raise ValueError(f"code must be numeric: {code!r}")
        if len(s) != pin_count:
            raise ValueError(f"expected {pin_count} digits, got {len(s)}")
        bits = tuple(int(c) for c in s)
        for b in bits:
            if b not in valid_set:
                raise ValueError(
                    f"depth {b} out of range "
                    f"({min(valid_set)}-{max(valid_set)})"
                )
        return bits

    return _decode


def offset_decode(pin_count: int, base_low: int, base_high: int,
                  offset: int) -> CodeLookup:
    """Decode where each digit has a fixed offset applied (e.g. +1 or -1)."""
    def _decode(code: str) -> Tuple[int, ...]:
        s = code.strip()
        if not s.isdigit() or len(s) != pin_count:
            raise ValueError(f"expected {pin_count} numeric digits, got {code!r}")
        out = []
        for c in s:
            d = int(c) + offset
            if d < base_low or d > base_high:
                raise ValueError(
                    f"derived depth {d} out of range {base_low}-{base_high}"
                )
            out.append(d)
        return tuple(out)
    return _decode
