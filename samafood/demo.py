"""Demo data — populates the app with realistic, clearly-labelled fake
businesses, users, orders, and vendor applications so it looks alive for
walk-throughs without polluting real data.

Every row created here carries `is_demo = 1`; `clear_demo()` purges only
those (and their dependents), so when Sama starts onboarding real
customers, a single call wipes the demo without touching anything live.

Usage:
    python -m samafood.demo seed     # add demo rows if absent
    python -m samafood.demo clear    # purge demo rows
    python -m samafood.demo reseed   # clear, then seed fresh
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone

from . import db


# Each business: prefixed with [DEMO] so they're unmistakable in any UI list.
DEMO_BUSINESSES = [
    {
        "name_en": "[DEMO] Quick Stop Café",
        "name_ar": "[تجريبي] مقهى كويك ستوب",
        "phone": "+962790000010",
        "client_type": "cafe",
        "yearly_spend": 5000,  # Bronze (0%)
        "users": [
            {"name": "Ahmad (Owner)", "phone": "+962790000010", "role": "owner"},
            {"name": "Layla (Buyer)", "phone": "+962790000011", "role": "buyer"},
        ],
    },
    {
        "name_en": "[DEMO] Demo Market",
        "name_ar": "[تجريبي] سوبرماركت تجريبي",
        "phone": "+962790000000",
        "client_type": "supermarket",
        "yearly_spend": 15000,  # Silver (4%)
        "users": [
            {"name": "Owner", "phone": "+962790000000", "role": "owner"},
            {"name": "Buyer", "phone": "+962790000001", "role": "buyer"},
            {"name": "Viewer", "phone": "+962790000002", "role": "viewer"},
        ],
    },
    {
        "name_en": "[DEMO] Royal Restaurant",
        "name_ar": "[تجريبي] مطعم الملكي",
        "phone": "+962790000020",
        "client_type": "restaurant",
        "yearly_spend": 28000,  # Gold (7%)
        "users": [
            {"name": "Khaled (Owner)", "phone": "+962790000020", "role": "owner"},
            {"name": "Noor (Buyer)", "phone": "+962790000021", "role": "buyer"},
        ],
    },
    {
        "name_en": "[DEMO] Grand Hotel HoReCa",
        "name_ar": "[تجريبي] فندق غراند",
        "phone": "+962790000030",
        "client_type": "horeca",
        "yearly_spend": 75000,  # Platinum (10%)
        "users": [
            {"name": "Maya (Owner)", "phone": "+962790000030", "role": "owner"},
            {"name": "Yousef (Buyer)", "phone": "+962790000031", "role": "buyer"},
            {"name": "Sara (Viewer)", "phone": "+962790000032", "role": "viewer"},
        ],
    },
]

DEMO_VENDOR_APPLICATIONS = [
    {"business_name": "[DEMO] Al Noor Mini Market", "contact_name": "Khaled Al Noor", "phone": "+962791112222", "client_type": "supermarket"},
    {"business_name": "[DEMO] Cedar Catering", "contact_name": "Reema Hadid", "phone": "+962791113333", "client_type": "horeca"},
]


def _has_demo_business(conn: db.Conn) -> bool:
    row = conn.execute("SELECT 1 FROM businesses WHERE is_demo = 1 LIMIT 1").fetchone()
    return row is not None


def _pick_products(conn: db.Conn, n: int) -> list[dict]:
    rows = conn.execute("SELECT sku, base_price, min_order FROM products ORDER BY id").fetchall()
    products = db.rows_to_dicts(rows)
    return random.sample(products, min(n, len(products)))


def _seed_orders(conn: db.Conn, business_id: int, user_id: int, discount_pct: float, rng: random.Random) -> None:
    """Create 3-5 plausible historical orders for a business."""
    for days_ago in rng.sample(range(2, 60), rng.randint(3, 5)):
        chosen = rng.sample(_pick_products(conn, 8), rng.randint(2, 4))
        items = []
        subtotal = 0.0
        for p in chosen:
            qty = max(p["min_order"], rng.randint(1, 4) * p["min_order"])
            subtotal += p["base_price"] * qty
            items.append({"sku": p["sku"], "qty": qty, "base_price": p["base_price"]})
        total = round(subtotal * (1 - discount_pct / 100), 3)
        created = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")
        conn.execute(
            """INSERT INTO orders (business_id, user_id, items_json, subtotal, discount_pct, total, status, note, created_at)
               VALUES (?,?,?,?,?,?,'submitted','',?)""",
            (business_id, user_id, json.dumps(items, ensure_ascii=False), round(subtotal, 3), discount_pct, total, created),
        )


def seed_demo(conn: db.Conn | None = None, *, force: bool = False) -> dict:
    """Create demo businesses/users/orders/applications if not already present."""
    own_conn = conn is None
    if own_conn:
        conn = db.get_db()
    try:
        if not force and _has_demo_business(conn):
            return {"skipped": "demo already seeded; use clear or reseed"}
        rng = random.Random(42)  # deterministic for stable demos
        created = {"businesses": 0, "users": 0, "orders": 0, "applications": 0}
        for biz in DEMO_BUSINESSES:
            tier_id = db.tier_for_spend(conn, biz["yearly_spend"])
            business_id = conn.insert(
                """INSERT INTO businesses (name_en, name_ar, phone, client_type, yearly_spend, tier_id, status, is_demo, created_at)
                   VALUES (?,?,?,?,?,?,'approved',1,?)""",
                (biz["name_en"], biz["name_ar"], biz["phone"], biz["client_type"], biz["yearly_spend"], tier_id, db.utc_now()),
            )
            created["businesses"] += 1
            first_buyer_id = None
            for user in biz["users"]:
                uid = conn.insert(
                    "INSERT INTO users (business_id, name, phone, role, status, created_at) VALUES (?,?,?,?,'active',?)",
                    (business_id, user["name"], user["phone"], user["role"], db.utc_now()),
                )
                created["users"] += 1
                if first_buyer_id is None and user["role"] in ("owner", "buyer"):
                    first_buyer_id = uid
            tier_row = conn.execute("SELECT discount_pct FROM tiers WHERE id = ?", (tier_id,)).fetchone() if tier_id else None
            discount_pct = (tier_row["discount_pct"] if tier_row else 0) or 0
            before = conn.execute("SELECT COUNT(*) AS n FROM orders WHERE business_id = ?", (business_id,)).fetchone()["n"]
            _seed_orders(conn, business_id, first_buyer_id, discount_pct, rng)
            after = conn.execute("SELECT COUNT(*) AS n FROM orders WHERE business_id = ?", (business_id,)).fetchone()["n"]
            created["orders"] += after - before
        for app in DEMO_VENDOR_APPLICATIONS:
            conn.execute(
                """INSERT INTO vendor_applications (business_name, contact_name, phone, client_type, documents_json, status, is_demo, created_at)
                   VALUES (?,?,?,?,'[]','pending',1,?)""",
                (app["business_name"], app["contact_name"], app["phone"], app["client_type"], db.utc_now()),
            )
            created["applications"] += 1
        conn.commit()
        return {"seeded": created}
    finally:
        if own_conn:
            conn.close()


def clear_demo(conn: db.Conn | None = None) -> dict:
    """Purge all rows flagged is_demo and their dependents."""
    own_conn = conn is None
    if own_conn:
        conn = db.get_db()
    try:
        biz_ids = [r["id"] for r in conn.execute("SELECT id FROM businesses WHERE is_demo = 1").fetchall()]
        user_ids = (
            [r["id"] for r in conn.execute(
                f"SELECT id FROM users WHERE business_id IN ({','.join('?' * len(biz_ids))})", tuple(biz_ids)
            ).fetchall()]
            if biz_ids else []
        )
        deleted = {"orders": 0, "users": 0, "businesses": 0, "applications": 0, "push_subs": 0, "notifications": 0}
        if biz_ids:
            placeholders = ",".join("?" * len(biz_ids))
            deleted["orders"] = conn.execute(f"DELETE FROM orders WHERE business_id IN ({placeholders})", tuple(biz_ids)).rowcount or 0
            deleted["notifications"] = conn.execute(f"DELETE FROM notifications_log WHERE business_id IN ({placeholders})", tuple(biz_ids)).rowcount or 0
        if user_ids:
            user_ph = ",".join("?" * len(user_ids))
            deleted["push_subs"] = conn.execute(f"DELETE FROM push_subscriptions WHERE user_id IN ({user_ph})", tuple(user_ids)).rowcount or 0
            deleted["users"] = conn.execute(f"DELETE FROM users WHERE id IN ({user_ph})", tuple(user_ids)).rowcount or 0
        if biz_ids:
            placeholders = ",".join("?" * len(biz_ids))
            deleted["businesses"] = conn.execute(f"DELETE FROM businesses WHERE id IN ({placeholders})", tuple(biz_ids)).rowcount or 0
        deleted["applications"] = conn.execute("DELETE FROM vendor_applications WHERE is_demo = 1").rowcount or 0
        conn.commit()
        return {"cleared": deleted}
    finally:
        if own_conn:
            conn.close()


def reseed_demo() -> dict:
    out = {"clear": clear_demo(), "seed": seed_demo(force=True)}
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="samafood.demo")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    sub.add_parser("clear")
    sub.add_parser("reseed")
    args = parser.parse_args(argv)
    db.init_db()
    if args.cmd == "seed":
        out = seed_demo(force=True)
    elif args.cmd == "clear":
        out = clear_demo()
    else:
        out = reseed_demo()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
