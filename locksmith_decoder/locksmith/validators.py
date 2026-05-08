"""Bitting validators: MACS check, depth-range check."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

from .manufacturers.base import Profile


@dataclass(frozen=True)
class ValidationIssue:
    code: str          # short machine tag, e.g. "MACS"
    position: int      # 0-based pin position the issue applies to (-1 = whole)
    detail: str


def check_depths(profile: Profile, bitting: Iterable[int]) -> List[ValidationIssue]:
    """Every cut must be a valid depth for the profile."""
    issues: List[ValidationIssue] = []
    for i, d in enumerate(bitting):
        if not profile.valid_depth(d):
            issues.append(ValidationIssue(
                code="DEPTH",
                position=i,
                detail=f"depth {d} not in profile {profile.keyway} "
                       f"(valid: {sorted(profile.depths)})",
            ))
    return issues


def check_macs(profile: Profile, bitting: Iterable[int]) -> List[ValidationIssue]:
    """Adjacent depths must not differ by more than the profile MACS."""
    bits = list(bitting)
    issues: List[ValidationIssue] = []
    for i in range(len(bits) - 1):
        diff = abs(bits[i] - bits[i + 1])
        if diff > profile.macs:
            issues.append(ValidationIssue(
                code="MACS",
                position=i,
                detail=f"adjacent cuts {bits[i]}->{bits[i+1]} differ by {diff}; "
                       f"MACS for {profile.keyway} is {profile.macs}",
            ))
    return issues


def check_pin_count(profile: Profile, bitting: Iterable[int]) -> List[ValidationIssue]:
    bits = list(bitting)
    if len(bits) != profile.pin_count:
        return [ValidationIssue(
            code="LEN",
            position=-1,
            detail=f"expected {profile.pin_count} cuts, got {len(bits)}",
        )]
    return []


def validate(profile: Profile, bitting: Iterable[int]) -> List[ValidationIssue]:
    """Run every validator. Empty list = bitting is cuttable."""
    bits = list(bitting)
    issues = check_pin_count(profile, bits)
    if issues:
        return issues
    issues.extend(check_depths(profile, bits))
    issues.extend(check_macs(profile, bits))
    return issues


def bitting_to_inches(profile: Profile, bitting: Iterable[int]) -> List[Tuple[float, float]]:
    """Return [(spacing_in, depth_in), ...] for a given bitting."""
    out: List[Tuple[float, float]] = []
    for i, d in enumerate(bitting):
        if i >= len(profile.spacing):
            break
        depth = profile.depths.get(d)
        if depth is None:
            raise ValueError(f"depth {d} not valid for {profile.keyway}")
        out.append((profile.spacing[i], depth))
    return out
