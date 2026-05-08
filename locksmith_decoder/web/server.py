#!/usr/bin/env python3
"""Local web UI for the locksmith decoder.

Stdlib-only HTTP server. Serves index.html and exposes:

  POST /api/decode   {token, keyway, code}    -> JSON result
  POST /api/batch    {token, jobs:[{kw,code}]}-> JSON results
  GET  /api/keyways                           -> list of profiles

Bind locally only by default; set LOCKSMITH_BIND=0.0.0.0 to expose.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from locksmith import Decoder, LicenseError, LicenseStore  # noqa: E402

WEB_ROOT = ROOT / "web"
LICENSE_PATH = ROOT / "data" / "licensed_locksmiths.json"

DECODER = Decoder()
LICENSES = LicenseStore(LICENSE_PATH)
SKIP_AUTH = os.environ.get("LOCKSMITH_SKIP_AUTH") == "1"


def _auth(token: str | None) -> str:
    if SKIP_AUTH:
        return "auth-bypassed"
    smith = LICENSES.authenticate(token)
    return f"{smith.name} ({smith.license_number}/{smith.state})"


class Handler(BaseHTTPRequestHandler):
    server_version = "LocksmithDecoder/1.0"

    def log_message(self, fmt, *args) -> None:  # noqa: A003
        sys.stderr.write(f"[web] {self.address_string()} - {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, ctype: str) -> None:
        if not path.exists():
            self.send_error(404, "not found")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._send_file(WEB_ROOT / "index.html", "text/html; charset=utf-8")
        elif self.path == "/style.css":
            self._send_file(WEB_ROOT / "style.css", "text/css")
        elif self.path == "/app.js":
            self._send_file(WEB_ROOT / "app.js", "application/javascript")
        elif self.path == "/api/keyways":
            payload = {"keyways": [
                {
                    "keyway": p.keyway,
                    "manufacturer": p.manufacturer,
                    "name": p.name,
                    "pin_count": p.pin_count,
                    "macs": p.macs,
                    "code_format": p.code_format,
                }
                for p in DECODER.keyways()
            ]}
            self._send_json(200, payload)
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return

        try:
            who = _auth(data.get("token"))
        except LicenseError as exc:
            self._send_json(401, {"error": f"unauthorized: {exc}"})
            return

        if self.path == "/api/decode":
            res = DECODER.decode(data.get("keyway", ""), data.get("code", ""))
            self._send_json(200, {"who": who, "result": res.to_dict()})
        elif self.path == "/api/batch":
            jobs = [(j.get("keyway", ""), j.get("code", ""))
                    for j in data.get("jobs", [])]
            results = DECODER.decode_many(jobs)
            self._send_json(200, {
                "who": who,
                "results": [r.to_dict() for r in results],
            })
        else:
            self.send_error(404)


def main() -> int:
    host = os.environ.get("LOCKSMITH_BIND", "127.0.0.1")
    port = int(os.environ.get("LOCKSMITH_PORT", "8990"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"locksmith decoder web UI: http://{host}:{port}")
    print(f"  auth bypass: {SKIP_AUTH}")
    print(f"  keyways:     {len(DECODER.keyways())}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
