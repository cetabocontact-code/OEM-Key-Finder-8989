"""Core Decoder facade: code -> bitting -> depth/space output."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from . import manufacturers as _ensure_loaded  # noqa: F401  registers profiles
from .manufacturers.base import REGISTRY, Profile
from .validators import (
    ValidationIssue,
    bitting_to_inches,
    validate as run_validators,
)


@dataclass
class BittingResult:
    keyway: str
    manufacturer: str
    profile_name: str
    pin_count: int
    bitting: Tuple[int, ...]
    inches: List[Tuple[float, float]]      # (spacing, depth) per pin
    macs: int
    valid: bool
    issues: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def pretty(self) -> str:
        lines = [
            f"Keyway:       {self.keyway}  ({self.profile_name})",
            f"Manufacturer: {self.manufacturer}",
            f"Bitting:      {'-'.join(str(b) for b in self.bitting)}",
            f"MACS:         {self.macs}   (valid={self.valid})",
            "Cuts (in):",
        ]
        for i, (s, d) in enumerate(self.inches, start=1):
            lines.append(f"  pin {i}:  spacing={s:.3f}\"  depth={d:.3f}\"")
        if self.issues:
            lines.append("Issues:")
            for it in self.issues:
                lines.append(f"  - {it['code']}@{it['position']}: {it['detail']}")
        return "\n".join(lines)


@dataclass
class DecodeResult:
    code: str
    keyway: str
    elapsed_us: int
    bitting: Optional[BittingResult] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "keyway": self.keyway,
            "elapsed_us": self.elapsed_us,
            "ok": self.ok,
            "error": self.error,
            "bitting": self.bitting.to_dict() if self.bitting else None,
        }


class Decoder:
    """Indexed in-memory key-code decoder.

    Build once, call ``decode()`` many times. All lookups are O(1) on the
    keyway hash map plus the cost of the manufacturer's bitting routine.
    """

    def __init__(self) -> None:
        self._profiles: Dict[str, Profile] = dict(REGISTRY)

    # -- introspection --------------------------------------------------
    def keyways(self) -> List[Profile]:
        seen: Dict[str, Profile] = {}
        for prof in self._profiles.values():
            seen.setdefault(prof.keyway, prof)
        return sorted(seen.values(), key=lambda p: (p.manufacturer, p.keyway))

    def profile(self, keyway: str) -> Profile:
        prof = self._profiles.get(keyway.upper())
        if prof is None:
            raise KeyError(f"unknown keyway: {keyway!r}. "
                           f"Try one of: {sorted({p.keyway for p in self._profiles.values()})}")
        return prof

    # -- core operations ------------------------------------------------
    def decode(self, keyway: str, code: str) -> DecodeResult:
        start = time.perf_counter_ns()
        try:
            prof = self.profile(keyway)
        except KeyError as exc:
            return DecodeResult(
                code=code, keyway=keyway,
                elapsed_us=(time.perf_counter_ns() - start) // 1000,
                error=str(exc),
            )

        try:
            bits = prof.decode(code)
        except ValueError as exc:
            return DecodeResult(
                code=code, keyway=prof.keyway,
                elapsed_us=(time.perf_counter_ns() - start) // 1000,
                error=str(exc),
            )

        issues = run_validators(prof, bits)
        valid = not issues
        try:
            inches = bitting_to_inches(prof, bits)
        except ValueError as exc:
            inches = []
            issues.append(ValidationIssue("INCH", -1, str(exc)))

        bitting = BittingResult(
            keyway=prof.keyway,
            manufacturer=prof.manufacturer,
            profile_name=prof.name,
            pin_count=prof.pin_count,
            bitting=bits,
            inches=inches,
            macs=prof.macs,
            valid=valid,
            issues=[{"code": i.code, "position": str(i.position),
                     "detail": i.detail} for i in issues],
        )
        elapsed = (time.perf_counter_ns() - start) // 1000
        return DecodeResult(code=code, keyway=prof.keyway,
                            elapsed_us=elapsed, bitting=bitting)

    def decode_many(self, jobs: Iterable[Tuple[str, str]]) -> List[DecodeResult]:
        return [self.decode(k, c) for k, c in jobs]

    # Reverse: bitting -> direct code (works for direct-code profiles).
    def encode(self, keyway: str, bitting: Iterable[int]) -> str:
        prof = self.profile(keyway)
        bits = list(bitting)
        if len(bits) != prof.pin_count:
            raise ValueError(f"need {prof.pin_count} cuts, got {len(bits)}")
        for b in bits:
            if not prof.valid_depth(b):
                raise ValueError(f"depth {b} invalid for {prof.keyway}")
        return "".join(str(b) for b in bits)
