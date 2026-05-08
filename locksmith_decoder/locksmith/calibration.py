"""Per-machine DSD calibration to combat machine drift.

Each cutting machine (Dolphin, Condor, Triton, etc.) has small offsets
relative to the published manufacturer spec. The locksmith cuts a
reference key, measures with calipers, and inputs the measured values.
We compute the offset and persist it. From then on every decode emits
``calibrated_inches`` alongside the published ``inches``.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


KNOWN_MACHINES = ("Dolphin", "Condor", "Triton", "Futura", "Silca-Idea",
                  "Manual")


@dataclass
class MachineProfile:
    machine_id: str           # short slug, unique per shop
    name: str                 # machine model
    spacing_offset_in: float = 0.0
    depth_offset_in: float = 0.0
    last_test_cut_keyway: Optional[str] = None
    last_test_cut_at: Optional[str] = None
    sample_count: int = 0
    tolerance_in: float = 0.002   # alarm if the offset exceeds this

    def apply(self, inches: Sequence[Tuple[float, float]]
              ) -> List[Tuple[float, float]]:
        return [(s + self.spacing_offset_in, d + self.depth_offset_in)
                for s, d in inches]

    def out_of_tolerance(self) -> bool:
        return (abs(self.spacing_offset_in) > self.tolerance_in
                or abs(self.depth_offset_in) > self.tolerance_in)


@dataclass
class CalibrationStore:
    path: Path
    profiles: Dict[str, MachineProfile] = field(default_factory=dict)
    active: Optional[str] = None

    @classmethod
    def load(cls, path: Path) -> "CalibrationStore":
        path = Path(path)
        if not path.exists():
            return cls(path=path)
        raw = json.loads(path.read_text())
        profs = {k: MachineProfile(**v) for k, v in raw.get("profiles", {}).items()}
        return cls(path=path, profiles=profs, active=raw.get("active"))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "active": self.active,
            "profiles": {k: asdict(v) for k, v in self.profiles.items()},
        }
        self.path.write_text(json.dumps(payload, indent=2))

    def add(self, machine_id: str, name: str) -> MachineProfile:
        prof = MachineProfile(machine_id=machine_id, name=name)
        self.profiles[machine_id] = prof
        if self.active is None:
            self.active = machine_id
        self.save()
        return prof

    def select(self, machine_id: str) -> MachineProfile:
        if machine_id not in self.profiles:
            raise KeyError(machine_id)
        self.active = machine_id
        self.save()
        return self.profiles[machine_id]

    def current(self) -> Optional[MachineProfile]:
        return self.profiles.get(self.active) if self.active else None

    def record_test_cut(self,
                        machine_id: str,
                        keyway: str,
                        published_inches: Sequence[Tuple[float, float]],
                        measured_inches: Sequence[Tuple[float, float]],
                        when: str) -> MachineProfile:
        """Compute mean spacing/depth deltas and persist them."""
        if machine_id not in self.profiles:
            raise KeyError(machine_id)
        if len(published_inches) != len(measured_inches):
            raise ValueError("measurement count must match published cut count")
        spacing_deltas = [m[0] - p[0] for p, m in zip(published_inches, measured_inches)]
        depth_deltas = [m[1] - p[1] for p, m in zip(published_inches, measured_inches)]
        prof = self.profiles[machine_id]
        # Offsets are subtracted on apply, so we store +delta to "push back".
        prof.spacing_offset_in = -statistics.fmean(spacing_deltas)
        prof.depth_offset_in = -statistics.fmean(depth_deltas)
        prof.last_test_cut_keyway = keyway
        prof.last_test_cut_at = when
        prof.sample_count += 1
        self.save()
        return prof
