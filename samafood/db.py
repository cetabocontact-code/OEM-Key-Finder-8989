"""Storage layer for the Sama Food vendor app.

Dual-mode: uses PostgreSQL when DATABASE_URL is set (production / Render),
otherwise a local SQLite file (dev). A thin connection wrapper unifies the
two APIs so the rest of the app uses one query style (`?` placeholders).
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATABASE_URL = os.environ.get("DATABASE_URL", "")
IS_PG = bool(DATABASE_URL)
DB_PATH = Path(os.environ.get("SAMA_DB_PATH", Path(__file__).resolve().parent.parent / "data" / "samafood.db"))

_PK = "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tiers (
    id {pk},
    name_en TEXT NOT NULL,
    name_ar TEXT NOT NULL,
    min_spend REAL NOT NULL,
    max_spend REAL,
    discount_pct REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS businesses (
    id {pk},
    name_en TEXT NOT NULL,
    name_ar TEXT NOT NULL,
    phone TEXT NOT NULL,
    client_type TEXT NOT NULL DEFAULT 'retail',
    yearly_spend REAL NOT NULL DEFAULT 0,
    tier_id INTEGER REFERENCES tiers(id),
    status TEXT NOT NULL DEFAULT 'approved',
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id {pk},
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL DEFAULT 'buyer',
    status TEXT NOT NULL DEFAULT 'active',
    last_login_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id {pk},
    sku TEXT NOT NULL UNIQUE,
    name_en TEXT NOT NULL,
    name_ar TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'water',
    size TEXT NOT NULL DEFAULT '',
    base_price REAL NOT NULL DEFAULT 0,
    min_order INTEGER NOT NULL DEFAULT 1,
    stock INTEGER NOT NULL DEFAULT 0,
    image_url TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual'
);

CREATE TABLE IF NOT EXISTS offers (
    id {pk},
    title_en TEXT NOT NULL,
    title_ar TEXT NOT NULL,
    body_en TEXT NOT NULL DEFAULT '',
    body_ar TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'monthly',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id {pk},
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    user_id INTEGER REFERENCES users(id),
    items_json TEXT NOT NULL,
    subtotal REAL NOT NULL,
    discount_pct REAL NOT NULL,
    total REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'submitted',
    note TEXT NOT NULL DEFAULT '',
    delivery_method TEXT NOT NULL DEFAULT 'pickup',
    delivery_address TEXT NOT NULL DEFAULT '',
    payment_method TEXT NOT NULL DEFAULT 'on_account',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendor_applications (
    id {pk},
    business_name TEXT NOT NULL,
    contact_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    client_type TEXT NOT NULL DEFAULT 'retail',
    documents_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending',
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS otp_codes (
    phone TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id {pk},
    user_id INTEGER REFERENCES users(id),
    endpoint TEXT NOT NULL UNIQUE,
    subscription_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications_log (
    id {pk},
    business_id INTEGER REFERENCES businesses(id),
    user_id INTEGER REFERENCES users(id),
    kind TEXT NOT NULL,
    ref TEXT NOT NULL DEFAULT '',
    sent_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contact_messages (
    id {pk},
    user_id INTEGER REFERENCES users(id),
    business_id INTEGER REFERENCES businesses(id),
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Conn:
    """Unifies sqlite3 and psycopg behind one `?`-placeholder API."""

    def __init__(self, raw: Any, is_pg: bool) -> None:
        self.raw = raw
        self.is_pg = is_pg

    def execute(self, sql: str, params: tuple = ()):  # noqa: ANN201
        if self.is_pg:
            cur = self.raw.cursor()
            cur.execute(sql.replace("?", "%s"), params)
            return cur
        return self.raw.execute(sql, params)

    def insert(self, sql: str, params: tuple = ()) -> int:
        """Run an INSERT and return the new row id."""
        if self.is_pg:
            sql = sql.replace("?", "%s")
            if "returning" not in sql.lower():
                sql += " RETURNING id"
            cur = self.raw.cursor()
            cur.execute(sql, params)
            return cur.fetchone()["id"]
        return self.raw.execute(sql, params).lastrowid

    def executescript(self, script: str) -> None:
        if self.is_pg:
            cur = self.raw.cursor()
            for stmt in (s.strip() for s in script.split(";") if s.strip()):
                cur.execute(stmt)
            return
        self.raw.executescript(script)

    def commit(self) -> None:
        self.raw.commit()

    def close(self) -> None:
        self.raw.close()


def get_db() -> Conn:
    if IS_PG:
        import psycopg
        from psycopg.rows import dict_row

        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        return Conn(psycopg.connect(url, row_factory=dict_row), True)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(DB_PATH)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    return Conn(raw, False)


def init_db() -> None:
    conn = get_db()
    try:
        conn.executescript(SCHEMA.format(pk=_PK))
        _migrate(conn)
        conn.commit()
        if conn.execute("SELECT COUNT(*) AS n FROM tiers").fetchone()["n"] == 0:
            _seed(conn)
    finally:
        conn.close()


def _migrate(conn: "Conn") -> None:
    """Best-effort column additions for already-existing DBs.

    Each ALTER is a no-op when the column is already there; we swallow the
    'duplicate column'/'already exists' error so init stays idempotent on
    both SQLite (local dev) and Postgres (Render).
    """
    additive = [
        "ALTER TABLE orders ADD COLUMN delivery_method TEXT NOT NULL DEFAULT 'pickup'",
        "ALTER TABLE orders ADD COLUMN delivery_address TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE orders ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'on_account'",
    ]
    for sql in additive:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:  # noqa: BLE001 - column already exists, ignore
            if conn.is_pg:
                conn.raw.rollback()


def _seed(conn: Conn) -> None:
    """Seed tiers, products, offers and a demo client.

    Replaced by SAP B1 / Olive sync once live credentials are configured.
    """
    seed_path = Path(__file__).resolve().parent / "seed_data.json"
    data = json.loads(seed_path.read_text(encoding="utf-8"))

    for tier in data["tiers"]:
        conn.execute(
            "INSERT INTO tiers (name_en, name_ar, min_spend, max_spend, discount_pct) VALUES (?,?,?,?,?)",
            (tier["name_en"], tier["name_ar"], tier["min_spend"], tier.get("max_spend"), tier["discount_pct"]),
        )

    for product in data["products"]:
        conn.execute(
            """INSERT INTO products (sku, name_en, name_ar, category, size, base_price, min_order, stock, image_url, source)
               VALUES (?,?,?,?,?,?,?,?,?,'seed')""",
            (
                product["sku"], product["name_en"], product["name_ar"], product["category"],
                product["size"], product["base_price"], product.get("min_order", 1),
                product.get("stock", 0), product.get("image_url", ""),
            ),
        )

    for offer in data["offers"]:
        conn.execute(
            "INSERT INTO offers (title_en, title_ar, body_en, body_ar, kind, active, created_at) VALUES (?,?,?,?,?,1,?)",
            (offer["title_en"], offer["title_ar"], offer["body_en"], offer["body_ar"], offer["kind"], utc_now()),
        )

    conn.commit()
    from . import demo as demo_module

    demo_module.seed_demo(conn)


def tier_for_spend(conn: Conn, spend: float) -> int | None:
    """Pick the tier whose spend band contains `spend` (max_spend NULL = open-ended)."""
    row = conn.execute(
        """SELECT id FROM tiers
           WHERE min_spend <= ? AND (max_spend IS NULL OR ? < max_spend)
           ORDER BY min_spend DESC LIMIT 1""",
        (spend, spend),
    ).fetchone()
    return row["id"] if row else None


def tier_progress(conn: Conn, spend: float) -> dict[str, Any]:
    """Locate the current tier band for `spend` and the gap to the next tier."""
    tiers = rows_to_dicts(conn.execute("SELECT * FROM tiers ORDER BY min_spend").fetchall())
    current = next(
        (t for t in tiers if t["min_spend"] <= spend and (t["max_spend"] is None or spend < t["max_spend"])),
        None,
    )
    upcoming = next((t for t in tiers if t["min_spend"] > spend), None)
    band_start = current["min_spend"] if current else 0
    if upcoming:
        band_end = upcoming["min_spend"]
        progress = round((spend - band_start) / (band_end - band_start) * 100) if band_end > band_start else 100
        progress = max(0, min(100, progress))
        amount_to_next = round(band_end - spend, 2)
    else:
        progress, amount_to_next = 100, 0.0
    return {"current": current, "upcoming": upcoming, "amount_to_next": amount_to_next, "progress_pct": progress}


def rows_to_dicts(rows: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]
