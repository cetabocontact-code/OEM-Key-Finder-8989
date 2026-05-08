"""Manufacturer-specific checksum / parity validators.

Catches "ghost codes" — bittings that pass MACS and depth-range checks
but violate a manufacturer's known structural rules. Each profile may
register zero or more rules. A rule returns either ``None`` (pass) or a
short string explaining the warning. Failures are surfaced as
``CHECKSUM`` issues on the decode result; they do not block output, so
the locksmith can override on a known exception.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .manufacturers.base import Profile, REGISTRY


Rule = Callable[[Sequence[int]], Optional[str]]
RULES: Dict[str, List[Rule]] = {}


def register(keyway: str, rule: Rule) -> None:
    RULES.setdefault(keyway.upper(), []).append(rule)


def run_rules(profile: Profile, bitting: Sequence[int]) -> List[str]:
    warnings: List[str] = []
    for keyway in (profile.keyway, *profile.aliases):
        for rule in RULES.get(keyway.upper(), []):
            msg = rule(bitting)
            if msg:
                warnings.append(msg)
    return warnings


# --- generic rule factories ----------------------------------------------
def no_more_than_n_consecutive(n: int) -> Rule:
    def _r(b: Sequence[int]) -> Optional[str]:
        run = 1
        for i in range(1, len(b)):
            run = run + 1 if b[i] == b[i - 1] else 1
            if run > n:
                return (f"more than {n} consecutive identical depths "
                        f"(positions {i - run + 1}..{i})")
        return None
    return _r


def sum_parity(expected: str) -> Rule:
    """expected: 'even' or 'odd'."""
    want = 0 if expected == "even" else 1

    def _r(b: Sequence[int]) -> Optional[str]:
        if sum(b) % 2 != want:
            return f"bitting sum {sum(b)} parity is not {expected} (mfr rule)"
        return None
    return _r


def sum_in_range(lo: int, hi: int) -> Rule:
    def _r(b: Sequence[int]) -> Optional[str]:
        s = sum(b)
        if not lo <= s <= hi:
            return f"bitting sum {s} outside expected mfr range {lo}-{hi}"
        return None
    return _r


def deepest_not_at_position(pos: int) -> Rule:
    """Some commercial keyings forbid the deepest cut at a given position."""
    def _r(b: Sequence[int]) -> Optional[str]:
        if not b:
            return None
        if b[pos] == max(b):
            return f"deepest cut at position {pos + 1} (mfr restricted)"
        return None
    return _r


def no_zero_at_position_one() -> Rule:
    def _r(b: Sequence[int]) -> Optional[str]:
        if b and b[0] == 0:
            return "depth 0 at position 1 (Schlage commercial restriction)"
        return None
    return _r


# --- attach rules ---------------------------------------------------------
# Schlage commercial rule: avoid more than 4 consecutive identical depths.
register("SC1",  no_more_than_n_consecutive(4))
register("SC4",  no_more_than_n_consecutive(4))
register("C123", no_more_than_n_consecutive(4))
register("SC4",  no_zero_at_position_one())

# Kwikset: vendor advises avoid all-same depth (master pin failure mode).
register("KW1",  no_more_than_n_consecutive(4))
register("KW10", no_more_than_n_consecutive(4))

# Sargent / Corbin / Yale commercial rules: similar consecutive limit.
for k in ("LA", "LC", "60", "59", "Y1", "Y8"):
    register(k, no_more_than_n_consecutive(4))

# Master Lock 4-pin: warn if all four cuts are identical (bumpable).
register("M1", no_more_than_n_consecutive(3))
register("M5", no_more_than_n_consecutive(4))
register("M7", no_more_than_n_consecutive(3))

# Automotive parity demos: Ford H75 8-cut uses sum-even parity check; some
# Toyota TR47 6-cuts use a sum-in-range sanity envelope. These are plausible
# example rules — locksmiths should still cross-check with their own data.
register("H75", sum_parity("even"))
register("TR47", sum_in_range(8, 22))
register("TR47", no_more_than_n_consecutive(4))
