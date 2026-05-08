"""Differential ("delta") sync for the offline data set.

A manifest enumerates every data file with its sha256 and version. The
locksmith's tool downloads only files whose hash differs from the local
copy, then verifies (a) per-file sha256, (b) the manifest's HMAC over
all entries. If either check fails, the partial update is rolled back.

To keep this self-contained and testable offline we model the "remote"
as just another directory on disk. In production, swap ``LocalSource``
for an HTTP source that streams the manifest first.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Protocol


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class FileEntry:
    path: str          # relative
    sha256: str
    version: int = 1


@dataclass
class Manifest:
    version: int
    generated_at: int
    files: List[FileEntry] = field(default_factory=list)
    signature: str = ""    # HMAC-SHA256 over canonical entries

    def to_json(self) -> str:
        return json.dumps({
            "version": self.version,
            "generated_at": self.generated_at,
            "files": [asdict(f) for f in self.files],
            "signature": self.signature,
        }, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, raw: str) -> "Manifest":
        d = json.loads(raw)
        return cls(
            version=d["version"],
            generated_at=d["generated_at"],
            files=[FileEntry(**f) for f in d["files"]],
            signature=d.get("signature", ""),
        )

    def signing_payload(self) -> bytes:
        body = {"version": self.version,
                "generated_at": self.generated_at,
                "files": [asdict(f) for f in self.files]}
        return json.dumps(body, sort_keys=True).encode("utf-8")


def sign_manifest(m: Manifest, key: str) -> Manifest:
    m.signature = hmac.new(key.encode("utf-8"),
                           m.signing_payload(),
                           hashlib.sha256).hexdigest()
    return m


def verify_manifest(m: Manifest, key: str) -> None:
    expected = hmac.new(key.encode("utf-8"),
                        m.signing_payload(),
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, m.signature):
        raise ValueError("manifest signature does not match shared key")


class Source(Protocol):
    def manifest(self) -> Manifest: ...
    def fetch(self, rel: str) -> bytes: ...


class LocalSource:
    """Source that reads from a directory on disk."""
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def manifest(self) -> Manifest:
        return Manifest.from_json((self.root / "manifest.json").read_text())

    def fetch(self, rel: str) -> bytes:
        return (self.root / rel).read_bytes()


@dataclass
class SyncReport:
    added: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    unchanged: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    bytes_transferred: int = 0


def build_manifest(root: Path, key: str, version: int = 1) -> Manifest:
    """Recursively walk root and produce a signed manifest."""
    root = Path(root)
    files: List[FileEntry] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rel = p.relative_to(root).as_posix()
            files.append(FileEntry(path=rel, sha256=sha256_file(p),
                                   version=version))
    m = Manifest(version=version, generated_at=int(time.time()), files=files)
    return sign_manifest(m, key)


def local_inventory(root: Path) -> Dict[str, str]:
    """sha256 of every existing local file (relative path -> hex)."""
    out: Dict[str, str] = {}
    if not root.exists():
        return out
    for p in root.rglob("*"):
        if p.is_file() and p.name != "manifest.json":
            out[p.relative_to(root).as_posix()] = sha256_file(p)
    return out


def sync(source: Source, target_root: Path, key: str) -> SyncReport:
    """Pull manifest, verify, transfer only deltas, verify each file."""
    target_root = Path(target_root)
    target_root.mkdir(parents=True, exist_ok=True)
    remote = source.manifest()
    verify_manifest(remote, key)

    inventory = local_inventory(target_root)
    report = SyncReport()
    staged: Dict[str, bytes] = {}

    for entry in remote.files:
        local_hash = inventory.get(entry.path)
        if local_hash == entry.sha256:
            report.unchanged.append(entry.path)
            continue
        try:
            blob = source.fetch(entry.path)
        except Exception as exc:        # noqa: BLE001
            report.failed.append(f"{entry.path}: fetch error: {exc}")
            return report
        actual = hashlib.sha256(blob).hexdigest()
        if actual != entry.sha256:
            report.failed.append(f"{entry.path}: sha256 mismatch — rejected")
            return report
        staged[entry.path] = blob
        if local_hash is None:
            report.added.append(entry.path)
        else:
            report.updated.append(entry.path)
        report.bytes_transferred += len(blob)

    # Atomic-ish apply: only after every fetch+verify succeeded.
    for rel, blob in staged.items():
        dest = target_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_bytes(blob)
        shutil.move(str(tmp), str(dest))

    (target_root / "manifest.json").write_text(remote.to_json())
    return report
