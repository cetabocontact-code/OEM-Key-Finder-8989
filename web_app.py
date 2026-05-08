#!/usr/bin/env python3
"""Small web interface for the VIN key-part resolver."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from vin_key_tool import (
    ROOT,
    VinKeyError,
    detect_make_profile,
    flatten_for_csv,
    load_make_profiles,
    resolve_key_parts,
)


WEB_ROOT = ROOT / "web"
HISTORY_PATH = ROOT / "data" / "search_history.json"
SUBSCRIBERS_PATH = ROOT / "data" / "private" / "subscribers.jsonl"
MAX_HISTORY = 50
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_history() -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    try:
        with HISTORY_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return payload[:MAX_HISTORY]


def save_history(history: list[dict[str, Any]]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("w", encoding="utf-8") as handle:
        json.dump(history[:MAX_HISTORY], handle, indent=2)
        handle.write("\n")


def load_subscriber_emails() -> set[str]:
    if not SUBSCRIBERS_PATH.exists():
        return set()
    emails: set[str] = set()
    try:
        with SUBSCRIBERS_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                email = str(item.get("email", "")).casefold()
                if email:
                    emails.add(email)
    except OSError:
        return set()
    return emails


def save_subscriber(email: str) -> tuple[bool, str]:
    normalized = email.strip().casefold()
    if not EMAIL_PATTERN.match(normalized):
        return False, "Enter a valid email address."

    existing = load_subscriber_emails()
    if normalized in existing:
        return True, "That email is already subscribed."

    SUBSCRIBERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {"email": normalized, "subscribed_at": utc_now()}
    with SUBSCRIBERS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")))
        handle.write("\n")
    return True, "Subscribed. Thank you."


def public_makes() -> list[dict[str, Any]]:
    profiles = load_make_profiles()
    makes: list[dict[str, Any]] = []
    for key, profile in profiles.items():
        makes.append(
            {
                "id": key,
                "label": profile.get("label", key.title()),
                "color": profile.get("color", "#1f6f78"),
                "sites": profile.get("sites", []),
                "seed": profile.get("seed_part", ""),
                "testVin": profile.get("test_vin", ""),
            }
        )
    return makes


def detect_make_from_partial_vin(vin: str) -> dict[str, Any]:
    normalized = "".join(char for char in vin.upper() if char.isalnum())[:17]
    profiles = load_make_profiles()
    partial = {"vin": normalized, "detectedWmi": normalized[:3] or None}
    if len(normalized) < 3:
        return {**partial, "make": None, "makeLabel": None, "color": None}

    fields = {"Make": ""}
    detected = detect_make_profile(normalized.ljust(17, "0"), fields, profiles)
    if not detected:
        return {**partial, "make": None, "makeLabel": None, "color": None}
    key, profile = detected
    return {
        **partial,
        "make": key,
        "makeLabel": profile.get("label", key.title()),
        "color": profile.get("color", "#1f6f78"),
    }


def summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    flat = flatten_for_csv(result)
    parts: list[dict[str, Any]] = []
    for match in result.get("matches", []):
        for part in match.get("parts", []):
            parts.append(
                {
                    "part_number": part.get("part_number", ""),
                    "description": part.get("description", ""),
                    "replaces": part.get("replaces", []),
                    "superseded_by": part.get("superseded_by", []),
                    "match_type": match.get("match_type", ""),
                    "confidence": match.get("confidence", ""),
                    "source_url": match.get("source_url", ""),
                    "notes": match.get("notes", ""),
                    "verification_required": bool(part.get("verification_required", False)),
                }
            )

    return {
        "vin": result.get("vin", ""),
        "searched_at": utc_now(),
        "year": flat.get("year", ""),
        "make": flat.get("make", ""),
        "model": flat.get("model", ""),
        "trim": flat.get("trim", ""),
        "series": flat.get("series", ""),
        "engine": flat.get("engine", ""),
        "key_part_numbers": flat.get("key_part_numbers", ""),
        "confidence": flat.get("confidence", ""),
        "replaces": flat.get("replaces", ""),
        "superseded_by": flat.get("superseded_by", ""),
        "decode_source": result.get("decode_source", ""),
        "decode": result.get("decode", {}),
        "parts": parts,
    }


def to_lookup_payload(summary: dict[str, Any]) -> dict[str, Any]:
    parts = [
        {
            "part": part.get("part_number", ""),
            "name": part.get("description", "") or "Key / Remote Part",
            "viewUrl": part.get("source_url", ""),
            "confidence": part.get("confidence", ""),
            "replaces": part.get("replaces", []),
            "supersededBy": part.get("superseded_by", []),
            "verificationRequired": part.get("verification_required", False),
            "notes": part.get("notes", ""),
        }
        for part in summary.get("parts", [])
    ]
    vehicle = " ".join(
        item
        for item in [summary.get("year", ""), summary.get("make", ""), summary.get("model", ""), summary.get("trim", "")]
        if item
    )
    return {
        "vehicle": vehicle,
        "vin": summary.get("vin", ""),
        "make": summary.get("make", "").casefold(),
        "makeLabel": summary.get("make", ""),
        "count": len(parts),
        "cached": summary.get("decode_source") == "cache",
        "siteUsed": parts[0].get("viewUrl", "") if parts else "",
        "sourceUrl": parts[0].get("viewUrl", "") if parts else "",
        "parts": parts,
        "confidence": summary.get("confidence", ""),
        "decode": summary.get("decode", {}),
    }


def record_history(summary: dict[str, Any]) -> None:
    history = load_history()
    vin = summary.get("vin")
    history = [item for item in history if item.get("vin") != vin]
    history.insert(0, summary)
    save_history(history)


class VinKeyHandler(BaseHTTPRequestHandler):
    server_version = "VinKeyWeb/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.write_json({"ok": True, "history_count": len(load_history())})
            return
        if parsed.path == "/api/makes":
            self.write_json({"makes": public_makes()})
            return
        if parsed.path == "/api/history":
            history = load_history()
            self.write_json({"items": history, "history": history})
            return
        if parsed.path == "/api/search":
            params = parse_qs(parsed.query)
            vin = (params.get("vin") or [""])[0]
            offline = (params.get("offline") or ["false"])[0].lower() == "true"
            self.handle_search(vin, offline=offline)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/search", "/api/detect", "/api/lookup", "/api/batch_lookup", "/api/subscribe"}:
            self.write_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw or "{}")
        except (ValueError, json.JSONDecodeError):
            self.write_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/detect":
            self.write_json(detect_make_from_partial_vin(str(payload.get("vin", ""))))
            return
        if parsed.path == "/api/subscribe":
            ok, message = save_subscriber(str(payload.get("email", "")))
            if not ok:
                self.write_json({"error": message}, status=HTTPStatus.BAD_REQUEST)
                return
            self.write_json({"ok": True, "message": message})
            return
        if parsed.path == "/api/lookup":
            self.handle_lookup(str(payload.get("vin", "")), offline=bool(payload.get("offline", False)))
            return
        if parsed.path == "/api/batch_lookup":
            vins = payload.get("vins", [])
            if not isinstance(vins, list):
                self.write_json({"error": "vins must be a list"}, status=HTTPStatus.BAD_REQUEST)
                return
            self.handle_batch_lookup(vins, offline=bool(payload.get("offline", False)))
            return
        self.handle_search(str(payload.get("vin", "")), offline=bool(payload.get("offline", False)))

    def handle_search(self, vin: str, *, offline: bool) -> None:
        try:
            result = resolve_key_parts(vin, offline=offline, update_cache=not offline)
        except VinKeyError as exc:
            self.write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except OSError as exc:
            self.write_json(
                {"error": f"Network or file access failed while resolving VIN: {exc}"},
                status=HTTPStatus.BAD_GATEWAY,
            )
            return

        summary = summarize_result(result)
        record_history(summary)
        self.write_json({"result": summary, "history": load_history()})

    def handle_lookup(self, vin: str, *, offline: bool) -> None:
        try:
            result = resolve_key_parts(vin, offline=offline, update_cache=not offline)
        except VinKeyError as exc:
            self.write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except OSError as exc:
            self.write_json(
                {"error": f"Network or file access failed while resolving VIN: {exc}"},
                status=HTTPStatus.BAD_GATEWAY,
            )
            return

        summary = summarize_result(result)
        record_history(summary)
        self.write_json(to_lookup_payload(summary))

    def handle_batch_lookup(self, vins: list[Any], *, offline: bool) -> None:
        items: list[dict[str, Any]] = []
        history_updates: list[dict[str, Any]] = []
        for vin in vins:
            try:
                result = resolve_key_parts(str(vin), offline=offline, update_cache=not offline)
                summary = summarize_result(result)
                history_updates.append(summary)
                items.append({"ok": True, "vin": summary.get("vin", ""), "result": to_lookup_payload(summary)})
            except (VinKeyError, OSError) as exc:
                items.append({"ok": False, "vin": str(vin), "error": str(exc)})

        if history_updates:
            history = load_history()
            for summary in history_updates:
                vin = summary.get("vin")
                history = [item for item in history if item.get("vin") != vin]
                history.insert(0, summary)
            save_history(history)

        self.write_json({"items": items, "count": len(items)})

    def serve_static(self, path: str) -> None:
        target = WEB_ROOT / "index.html" if path in ("", "/") else WEB_ROOT / path.lstrip("/")
        try:
            resolved = target.resolve()
            if not resolved.is_file() or WEB_ROOT.resolve() not in resolved.parents:
                raise FileNotFoundError
            content = resolved.read_bytes()
        except (OSError, FileNotFoundError):
            self.write_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def write_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the VIN key-part web app.")
    parser.add_argument("--host", default="0.0.0.0", help="Host/interface to bind.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)), help="Port to bind.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), VinKeyHandler)
    print(f"VIN key tool running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
