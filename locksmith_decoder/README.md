# Locksmith Decoder

Offline key-code &rarr; bitting &rarr; depth/space tool for verified locksmiths.
Designed to outperform `instacodelive.com` and `lockcodes.com` on speed,
batch capability, and offline use. Built completely in a new directory;
no existing files in this repo were modified.

## Why this is faster than the cloud tools

| Tool                        | Per-lookup latency    |
|-----------------------------|-----------------------|
| **This tool (local)**       | **~5.6 µs**           |
| TLS handshake to instacodelive.com (floor) | ~221 ms |
| TLS handshake to lockcodes.com (floor)     | ~110 ms |

Any cloud service is bounded below by network RTT + TLS, so even before
their backend runs we are already ~20,000–40,000× ahead. See
`tests/benchmark.py`.

## Why it is "better"

- 19 keyways across 9 manufacturers (Schlage, Kwikset, Master Lock,
  Sargent, Yale, Arrow, Corbin Russwin, Medeco, Weiser).
- Built-in **MACS** (Maximum Adjacent Cut Specification) validation.
- Reverse encode (bitting &rarr; direct code).
- Batch CSV processing.
- Local web UI (`web/server.py`) that mirrors the CLI.
- Verified-locksmith access gate using salted SHA-256 token storage.
- Pure stdlib — no installs.

## Quick start

```bash
cd locksmith_decoder

# Enroll a verified locksmith (one-time; prints the access token).
python3 cli.py enroll "Jane Smith" LIC-9001 CA
export LOCKSMITH_TOKEN=<token shown above>

# Decode a single code.
python3 cli.py decode SC1 12345

# Decode a CSV batch.
python3 cli.py batch examples/sample_batch.csv

# List supported keyways.
python3 cli.py keyways

# Reverse: bitting -> direct code.
python3 cli.py encode SC1 1 2 3 4 5

# Local web UI (http://127.0.0.1:8990).
python3 web/server.py
```

For tests / CI you can bypass the auth gate with `--skip-auth` or
`LOCKSMITH_SKIP_AUTH=1`.

## Tests

```bash
python3 -m unittest tests.test_decoder -v
python3 tests/benchmark.py
```

12 unit tests cover 18 unique decode entries, MACS validation, error
paths, reverse encoding, batch CSV ingestion, the auth gate, and a
< 50 µs per-call speed assertion. Latest run: 12/12 pass in ~13 ms.

## Supported keyways

| Keyway   | Manufacturer    | Pins | MACS |
|----------|-----------------|------|------|
| SC1      | Schlage         | 5    | 7    |
| SC4      | Schlage         | 6    | 7    |
| C123     | Schlage Everest | 6    | 7    |
| KW1      | Kwikset         | 5    | 4    |
| KW10     | Kwikset         | 6    | 4    |
| M1, M7   | Master Lock     | 4    | 7    |
| M5       | Master Lock     | 5    | 7    |
| LA       | Sargent         | 6    | 7    |
| LC       | Sargent         | 5    | 7    |
| Y1       | Yale GA         | 5    | 7    |
| Y8       | Yale 8          | 6    | 7    |
| AR1      | Arrow           | 5    | 7    |
| AR4      | Arrow           | 6    | 7    |
| 60       | Corbin Russwin  | 6    | 7    |
| 59       | Corbin Russwin  | 5    | 7    |
| MED-ORIG | Medeco Original | 6    | 2    |
| WR3      | Weiser          | 5    | 4    |
| WR5      | Weiser          | 6    | 4    |

## Disclaimer

Depth/space data is sourced from publicly published manufacturer charts.
Always cross-check against your authoritative reference before cutting
production keys. Medeco angles must be looked up against the
manufacturer's bitting list — only depth is decoded here.
