"""Benchmark: in-memory decoder vs network round-trip baseline.

We can't legitimately call instacodelive/lockcodes — they require paid
locksmith credentials. We instead compare against the *minimum* time it
takes to issue an HTTPS request to a live host, because any network-based
service is bounded below by RTT + TLS handshake. If we beat that, we are
already faster than any cloud-hosted decoder, regardless of its backend.
"""
from __future__ import annotations

import socket
import ssl
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from locksmith import Decoder

NETWORK_HOSTS = ["www.instacodelive.com", "lockcodes.com", "www.google.com"]
N_RUNS = 1000


def time_local(dec: Decoder) -> float:
    pairs = [
        ("SC1", "12345"), ("KW1", "24642"), ("LA", "654321"),
        ("Y1", "98765"), ("M5", "32145"), ("AR1", "52173"),
        ("60", "987654"), ("59", "76543"), ("WR3", "52316"),
        ("MED-ORIG", "123456"),
    ]
    # warm
    for k, c in pairs:
        dec.decode(k, c)
    t0 = time.perf_counter_ns()
    for _ in range(N_RUNS):
        for k, c in pairs:
            dec.decode(k, c)
    elapsed_ns = time.perf_counter_ns() - t0
    return elapsed_ns / (N_RUNS * len(pairs))   # ns per decode


def time_network(host: str) -> float:
    """Time one TCP+TLS handshake. This is the *floor* for any HTTPS API."""
    ctx = ssl.create_default_context()
    samples = []
    for _ in range(3):
        t0 = time.perf_counter_ns()
        try:
            with socket.create_connection((host, 443), timeout=4) as raw:
                with ctx.wrap_socket(raw, server_hostname=host) as s:
                    s.do_handshake()
        except (OSError, ssl.SSLError) as exc:
            return float("nan")
        samples.append(time.perf_counter_ns() - t0)
    return sum(samples) / len(samples)


def main() -> int:
    dec = Decoder()
    local_ns = time_local(dec)
    print(f"local decoder:           {local_ns/1000:8.2f} us/decode "
          f"({N_RUNS*10} calls)")

    for host in NETWORK_HOSTS:
        net_ns = time_network(host)
        if net_ns != net_ns:  # NaN
            print(f"  {host:<28}  unreachable")
            continue
        ratio = net_ns / local_ns
        print(f"  TLS handshake to {host:<22} {net_ns/1_000_000:7.2f} ms  "
              f"({ratio:,.0f}x slower than local decode)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
