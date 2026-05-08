"""Verified-locksmith license gate.

Each authorized locksmith is recorded in ``data/licensed_locksmiths.json``
with a name, license number, state, and a salted SHA-256 of their access
token. The CLI / web tool refuses to run without a valid token.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


class LicenseError(RuntimeError):
    """Raised when a token cannot be authenticated."""


@dataclass(frozen=True)
class Locksmith:
    name: str
    license_number: str
    state: str
    salt: str
    token_hash: str

    def matches(self, token: str) -> bool:
        h = hashlib.sha256((self.salt + token).encode("utf-8")).hexdigest()
        return hmac.compare_digest(h, self.token_hash)


class LicenseStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"locksmiths": []}, indent=2))
        self._records: List[Locksmith] = self._load()

    def _load(self) -> List[Locksmith]:
        raw = json.loads(self.path.read_text())
        return [Locksmith(**r) for r in raw.get("locksmiths", [])]

    def _save(self) -> None:
        payload = {"locksmiths": [r.__dict__ for r in self._records]}
        self.path.write_text(json.dumps(payload, indent=2))

    def list(self) -> List[Dict[str, str]]:
        return [
            {"name": r.name, "license_number": r.license_number, "state": r.state}
            for r in self._records
        ]

    def enroll(self, name: str, license_number: str, state: str,
               token: Optional[str] = None) -> str:
        """Add a locksmith. Returns the plaintext token (only time it's shown)."""
        token = token or secrets.token_urlsafe(24)
        salt = secrets.token_hex(16)
        token_hash = hashlib.sha256((salt + token).encode("utf-8")).hexdigest()
        self._records.append(Locksmith(
            name=name, license_number=license_number, state=state,
            salt=salt, token_hash=token_hash,
        ))
        self._save()
        return token

    def authenticate(self, token: Optional[str]) -> Locksmith:
        if not token:
            raise LicenseError("no access token provided")
        for r in self._records:
            if r.matches(token):
                return r
        raise LicenseError("token does not match any verified locksmith")


def authenticate_from_env(store: LicenseStore,
                          env_var: str = "LOCKSMITH_TOKEN") -> Locksmith:
    """Convenience: authenticate using a token from the environment."""
    token = os.environ.get(env_var)
    return store.authenticate(token)
