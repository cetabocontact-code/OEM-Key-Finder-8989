"""Hardware-bound seal + 30-day TTL ("JWT time-bomb").

We don't ship AES from stdlib alone, so the seal provides:
  - **integrity binding**  (HMAC-SHA256 over hardware fingerprint + payload)
  - **device binding**     (moving the file to a different host invalidates HMAC)
  - **TTL enforcement**    (issued_at + ttl_days; expired seals refuse to verify)

The seal is a JSON file. Tampering or moving it to another machine
breaks the HMAC. To re-issue, the locksmith must re-authenticate online
(a one-second token exchange in real deployment; here we accept the
master license token).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import platform
import secrets
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


def hardware_fingerprint() -> str:
    """Stable per-host fingerprint. Combines MAC, hostname, platform tag.

    Uses ``uuid.getnode`` (MAC, falls back to a random 48-bit if unavailable
    — we tag that case so the seal cannot accidentally pass on hosts that
    cannot identify themselves).
    """
    node = uuid.getnode()
    is_random_mac = (node >> 40) & 0x01  # multicast bit means generated
    raw = f"{node:012x}|{platform.node()}|{platform.system()}|{platform.machine()}"
    fp = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if is_random_mac:
        fp = "ephemeral:" + fp
    return fp


@dataclass
class Seal:
    locksmith_id: str
    hardware_fp: str
    issued_at: int        # epoch seconds
    ttl_days: int
    nonce: str
    signature: str        # hex HMAC-SHA256

    @property
    def expires_at(self) -> int:
        return self.issued_at + self.ttl_days * 86400

    def remaining_seconds(self, now: Optional[int] = None) -> int:
        return self.expires_at - (now if now is not None else int(time.time()))


class SealError(RuntimeError):
    pass


def _payload_bytes(s: Seal) -> bytes:
    return json.dumps({
        "locksmith_id": s.locksmith_id,
        "hardware_fp": s.hardware_fp,
        "issued_at": s.issued_at,
        "ttl_days": s.ttl_days,
        "nonce": s.nonce,
    }, sort_keys=True).encode("utf-8")


def _sign(payload: bytes, token: str) -> str:
    return hmac.new(token.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def issue_seal(locksmith_id: str, token: str, ttl_days: int = 30) -> Seal:
    if ttl_days <= 0 or ttl_days > 365:
        raise ValueError("ttl_days must be 1..365")
    s = Seal(
        locksmith_id=locksmith_id,
        hardware_fp=hardware_fingerprint(),
        issued_at=int(time.time()),
        ttl_days=ttl_days,
        nonce=secrets.token_hex(8),
        signature="",
    )
    s.signature = _sign(_payload_bytes(s), token)
    return s


def write_seal(path: Path, seal: Seal) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(asdict(seal), indent=2))


def load_seal(path: Path) -> Seal:
    return Seal(**json.loads(Path(path).read_text()))


def verify_seal(seal: Seal, token: str,
                expected_fp: Optional[str] = None,
                now: Optional[int] = None) -> None:
    """Raises SealError if the seal is bad. Returns None on success."""
    fp = expected_fp or hardware_fingerprint()
    if fp.startswith("ephemeral:"):
        raise SealError("hardware fingerprint is ephemeral — refuse to bind")
    if seal.hardware_fp != fp:
        raise SealError("seal hardware fingerprint mismatch (file moved?)")
    expected = _sign(_payload_bytes(seal), token)
    if not hmac.compare_digest(expected, seal.signature):
        raise SealError("seal HMAC signature mismatch")
    now_t = now if now is not None else int(time.time())
    if now_t > seal.expires_at:
        raise SealError(
            f"seal expired {(now_t - seal.expires_at)//86400} day(s) ago — "
            f"refresh required"
        )
