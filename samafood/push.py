"""Web Push (VAPID) helpers.

Push delivery needs a VAPID key pair. Provide your own via env vars for
production (so subscriptions survive restarts); otherwise a pair is generated
at startup for local/dev use.

  VAPID_PUBLIC_KEY   base64url-encoded public key
  VAPID_PRIVATE_KEY  base64url-encoded private key
  VAPID_CONTACT      mailto: address for the push service (e.g. mailto:ops@samafood.jo)
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

_CACHE: dict[str, str] = {}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _generate_keys() -> tuple[str, str]:
    key = ec.generate_private_key(ec.SECP256R1())
    private_raw = key.private_numbers().private_value.to_bytes(32, "big")
    public_raw = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return _b64(public_raw), _b64(private_raw)


def get_keys() -> tuple[str, str]:
    if "public" not in _CACHE:
        pub = os.environ.get("VAPID_PUBLIC_KEY")
        priv = os.environ.get("VAPID_PRIVATE_KEY")
        if not (pub and priv):
            pub, priv = _generate_keys()
        _CACHE["public"], _CACHE["private"] = pub, priv
    return _CACHE["public"], _CACHE["private"]


def public_key() -> str:
    return get_keys()[0]


def contact() -> str:
    return os.environ.get("VAPID_CONTACT", "mailto:ops@samafood.jo")


def send(subscription: dict[str, Any], title: str, body: str, url: str = "/") -> bool:
    try:
        from pywebpush import webpush
    except ImportError:
        # pywebpush not installed in this environment; sending is unavailable.
        return False
    _, private = get_keys()
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=private,
            vapid_claims={"sub": contact()},
        )
        return True
    except Exception:  # noqa: BLE001 - best-effort: one bad subscription must not abort a batch
        return False
