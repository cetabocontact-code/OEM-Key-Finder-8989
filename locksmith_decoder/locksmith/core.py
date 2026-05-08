"""Core Decoder facade.

Pipeline (per call):
  1. resolve profile by keyway
  2. decode raw code -> bitting
  3. structural validation (length, depth set, MACS)
  4. manufacturer checksum / parity rules         [strategy 2]
  5. apply active machine calibration to inches    [strategy 3]
  6. on validation failure, propose alternatives   [strategy 5]
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from . import manufacturers as _ensure_loaded  # noqa: F401  registers profiles
from .calibration import CalibrationStore, MachineProfile
from .checksum import run_rules
from .fallback import Candidate, suggest
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
    inches: List[Tuple[float, float]]
    calibrated_inches: Optional[List[Tuple[float, float]]]
    machine: Optional[str]
    macs: int
    valid: bool
    checksum_warnings: List[str] = field(default_factory=list)
    issues: List[Dict[str, str]] = field(default_factory=list)
    alternatives: List[Dict[str, object]] = field(default_factory=list)

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
        if self.calibrated_inches:
            lines.append(f"Cuts (in, calibrated for {self.machine}):")
            for i, (s, d) in enumerate(self.calibrated_inches, start=1):
                lines.append(f"  pin {i}:  spacing={s:.3f}\"  depth={d:.3f}\"")
        if self.checksum_warnings:
            lines.append("Checksum warnings:")
            for w in self.checksum_warnings:
                lines.append(f"  ! {w}")
        if self.issues:
            lines.append("Issues:")
            for it in self.issues:
                lines.append(f"  - {it['code']}@{it['position']}: {it['detail']}")
        if self.alternatives:
            lines.append("Alternative profiles to try:")
            for a in self.alternatives:
                lines.append(
                    f"  ~ {a['keyway']:<10} {a['manufacturer']:<16} "
                    f"score={a['score']}  ({a['reason']})"
                )
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

    Optionally accepts a ``CalibrationStore`` so decoded inches are
    adjusted for the active cutting machine's measured drift.
    """

    def __init__(self, calibration: Optional[CalibrationStore] = None) -> None:
        self._profiles: Dict[str, Profile] = dict(REGISTRY)
        self.calibration = calibration

    # -- introspection --------------------------------------------------
    def keyways(self) -> List[Profile]:
        seen: Dict[str, Profile] = {}
        for prof in self._profiles.values():
            seen.setdefault(prof.keyway, prof)
        return sorted(seen.values(), key=lambda p: (p.manufacturer, p.keyway))

    def profile(self, keyway: str) -> Profile:
        prof = self._profiles.get(keyway.upper())
        if prof is None:
            raise KeyError(
                f"unknown keyway: {keyway!r}. Try one of: "
                f"{sorted({p.keyway for p in self._profiles.values()})}"
            )
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
        warnings = run_rules(prof, bits)
        valid = (not issues) and (not warnings)

        try:
            inches = bitting_to_inches(prof, bits)
        except ValueError as exc:
            inches = []
            issues.append(ValidationIssue("INCH", -1, str(exc)))

        machine_profile: Optional[MachineProfile] = None
        calibrated = None
        if self.calibration:
            machine_profile = self.calibration.current()
            if machine_profile and inches:
                calibrated = machine_profile.apply(inches)

        alternatives: List[Candidate] = []
        if not valid:
            alternatives = suggest(prof, bits)

        bitting = BittingResult(
            keyway=prof.keyway,
            manufacturer=prof.manufacturer,
            profile_name=prof.name,
            pin_count=prof.pin_count,
            bitting=bits,
            inches=inches,
            calibrated_inches=calibrated,
            machine=machine_profile.name if machine_profile else None,
            macs=prof.macs,
            valid=valid,
            checksum_warnings=warnings,
            issues=[{"code": i.code, "position": str(i.position),
                     "detail": i.detail} for i in issues],
            alternatives=[c.to_dict() for c in alternatives],
        )
        elapsed = (time.perf_counter_ns() - start) // 1000
        return DecodeResult(code=code, keyway=prof.keyway,
                            elapsed_us=elapsed, bitting=bitting)

    def decode_many(self, jobs: Iterable[Tuple[str, str]]) -> List[DecodeResult]:
        return [self.decode(k, c) for k, c in jobs]

    def encode(self, keyway: str, bitting: Iterable[int]) -> str:
        prof = self.profile(keyway)
        bits = list(bitting)
        if len(bits) != prof.pin_count:
            raise ValueError(f"need {prof.pin_count} cuts, got {len(bits)}")
        for b in bits:
            if not prof.valid_depth(b):
                raise ValueError(f"depth {b} invalid for {prof.keyway}")
        return "".join(str(b) for b in bits)
