"""Conflict resolution: suggest alternative keyway profiles.

When a decode fails MACS / depth / checksum validation, the engine
walks all registered profiles and asks: would this same code be valid
on a different (compatible) profile? Returns a ranked list of
candidates so the locksmith can compare instead of being told the cut
is impossible.

Compatibility heuristic (cheap, deterministic):
  - same pin count                         (must match)
  - same manufacturer family               (+strong score)
  - depth set is a superset of the cuts    (must match)
  - the candidate's MACS accepts the cuts  (+score)
  - candidate's checksum rules pass        (+score)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from .checksum import run_rules
from .manufacturers.base import Profile, REGISTRY
from .validators import validate


@dataclass
class Candidate:
    profile: Profile
    score: int
    reason: str

    def to_dict(self) -> dict:
        return {
            "keyway": self.profile.keyway,
            "manufacturer": self.profile.manufacturer,
            "name": self.profile.name,
            "score": self.score,
            "reason": self.reason,
        }


def suggest(original: Profile, bitting: Sequence[int],
            limit: int = 4) -> List[Candidate]:
    seen: set[str] = {original.keyway}
    cands: List[Candidate] = []
    for prof in REGISTRY.values():
        if prof.keyway in seen:
            continue
        seen.add(prof.keyway)
        if prof.pin_count != len(bitting):
            continue
        if not all(prof.valid_depth(d) for d in bitting):
            continue
        score = 1
        reasons: List[str] = ["depth set compatible"]
        if prof.manufacturer == original.manufacturer:
            score += 3
            reasons.append("same manufacturer family")
        if not validate(prof, bitting):
            score += 3
            reasons.append("MACS valid")
        if not run_rules(prof, bitting):
            score += 2
            reasons.append("checksum rules pass")
        cands.append(Candidate(profile=prof, score=score,
                               reason="; ".join(reasons)))
    cands.sort(key=lambda c: (-c.score, c.profile.keyway))
    return cands[:limit]
