"""SQLite storage for the Sama Food vendor app."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(os.environ.get("SAMA_DB_PATH", Path(__file__).resolve().parent.parent / "data" / "samafood.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS tiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL,
    name_ar TEXT NOT NULL,
    min_spend REAL NOT NULL,
    max_spend REAL,
    discount_pct REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS businesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL,
    name_ar TEXT NOT NULL,
    phone TEXT NOT NULL,
    client_type TEXT NOT NULL DEFAULT 'retail',
    yearly_spend REAL NOT NULL DEFAULT 0,
    tier_id INTEGER REFERENCES tiers(id),
    status TEXT NOT NULL DEFAULT 'approved',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL DEFAULT 'buyer',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title_en TEXT NOT NULL,
    title_ar TEXT NOT NULL,
    body_en TEXT NOT NULL DEFAULT '',
    body_ar TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'monthly',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    user_id INTEGER REFERENCES users(id),
    items_json TEXT NOT NULL,
    subtotal REAL NOT NULL,
    discount_pct REAL NOT NULL,
    total REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'submitted',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendor_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_name TEXT NOT NULL,
    contact_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    client_type TEXT NOT NULL DEFAULT 'retail',
    documents_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS otp_codes (
    phone TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    endpoint TEXT NOT NULL UNIQUE,
    subscription_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        if conn.execute("SELECT COUNT(*) FROM tiers").fetchone()[0] == 0:
            _seed(conn)
    finally:
        conn.close()


def _seed(conn: sqlite3.Connection) -> None:
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

    demo = data["demo_business"]
    tier_id = tier_for_spend(conn, demo["yearly_spend"])
    business_id = conn.execute(
        """INSERT INTO businesses (name_en, name_ar, phone, client_type, yearly_spend, tier_id, status, created_at)
           VALUES (?,?,?,?,?,?,'approved',?)""",
        (demo["name_en"], demo["name_ar"], demo["phone"], demo["client_type"], demo["yearly_spend"], tier_id, utc_now()),
    ).lastrowid
    for user in demo["users"]:
        conn.execute(
            "INSERT INTO users (business_id, name, phone, role, status, created_at) VALUES (?,?,?,?,'active',?)",
            (business_id, user["name"], user["phone"], user["role"], utc_now()),
        )
    conn.commit()


def tier_for_spend(conn: sqlite3.Connection, spend: float) -> int | None:
    """Pick the tier whose spend band contains `spend` (max_spend NULL = open-ended)."""
    row = conn.execute(
        """SELECT id FROM tiers
           WHERE min_spend <= ? AND (max_spend IS NULL OR ? < max_spend)
           ORDER BY min_spend DESC LIMIT 1""",
        (spend, spend),
    ).fetchone()
    return row["id"] if row else None


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]
