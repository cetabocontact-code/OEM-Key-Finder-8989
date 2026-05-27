"""Scheduled customer notifications — run daily via a Render cron job.

Two kinds of nudges, both idempotent (each milestone is sent at most once per
cycle, tracked in `notifications_log`):

  * tier nudges — as a business's purchasing year (its created_at anniversary)
    approaches, remind it how much more to spend to reach the next discount.
    Fires when days-to-anniversary first crosses 90, then 60, then 30.
  * login refresh — once a user is ~11 months past their last login, remind
    them to log in so their account/access stays current.

Usage:
    python -m samafood.notify run            # send
    python -m samafood.notify run --dry-run  # preview only, sends nothing
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime

from . import db, push

TIER_MILESTONES = (90, 60, 30)  # days before the anniversary
LOGIN_REFRESH_DAYS = 330


def _as_date(value: str) -> date:
    return datetime.fromisoformat(value).date()


def _days_until_anniversary(created_at: str, today: date) -> tuple[int, str]:
    """Days until the next created_at anniversary, plus that cycle's year label."""
    created = _as_date(created_at)
    try:
        anniversary = created.replace(year=today.year)
    except ValueError:  # created on Feb 29 in a non-leap target year
        anniversary = created.replace(year=today.year, day=28)
    if anniversary < today:
        try:
            anniversary = created.replace(year=today.year + 1)
        except ValueError:
            anniversary = created.replace(year=today.year + 1, day=28)
    return (anniversary - today).days, str(anniversary.year)


def _already_sent(conn: db.Conn, business_id, user_id, kind: str, ref: str) -> bool:
    if user_id is None:
        row = conn.execute(
            "SELECT 1 FROM notifications_log WHERE business_id = ? AND user_id IS NULL AND kind = ? AND ref = ?",
            (business_id, kind, ref),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM notifications_log WHERE business_id = ? AND user_id = ? AND kind = ? AND ref = ?",
            (business_id, user_id, kind, ref),
        ).fetchone()
    return row is not None


def _log(conn: db.Conn, business_id, user_id, kind: str, ref: str) -> None:
    conn.execute(
        "INSERT INTO notifications_log (business_id, user_id, kind, ref, sent_at) VALUES (?,?,?,?,?)",
        (business_id, user_id, kind, ref, db.utc_now()),
    )


def _subscriptions(conn: db.Conn, *, business_id=None, user_id=None) -> list[dict]:
    if user_id is not None:
        rows = conn.execute(
            "SELECT subscription_json FROM push_subscriptions WHERE user_id = ?", (user_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT ps.subscription_json FROM push_subscriptions ps
               JOIN users u ON u.id = ps.user_id
               WHERE u.business_id = ? AND u.status = 'active'""",
            (business_id,),
        ).fetchall()
    return [json.loads(r["subscription_json"]) for r in rows]


def _deliver(subs: list[dict], title: str, body: str, dry_run: bool) -> int:
    if dry_run:
        return 0
    return sum(1 for s in subs if push.send(s, title, body, "/"))


TITLE = "سما فود | Sama Food"


def run(dry_run: bool = False, today: date | None = None) -> dict:
    today = today or date.today()
    conn = db.get_db()
    planned: list[str] = []
    sent_count = 0
    try:
        # --- tier nudges (business-level) ---
        businesses = conn.execute(
            "SELECT id, name_en, yearly_spend, created_at FROM businesses WHERE status = 'approved'"
        ).fetchall()
        for b in businesses:
            prog = db.tier_progress(conn, b["yearly_spend"] or 0)
            upcoming = prog["upcoming"]
            if not upcoming or prog["amount_to_next"] <= 0:
                continue
            days, ref = _days_until_anniversary(b["created_at"], today)
            bucket = min((m for m in TIER_MILESTONES if days <= m), default=None)
            if bucket is None:
                continue
            kind = f"tier_{bucket}"
            if _already_sent(conn, b["id"], None, kind, ref):
                continue
            body = (
                f"تبقّى {prog['amount_to_next']} د.أ للوصول لفئة {upcoming['name_ar']} وخصم {upcoming['discount_pct']}% "
                f"(باقي {days} يوم). / {prog['amount_to_next']} JOD more to reach {upcoming['name_en']} "
                f"({upcoming['discount_pct']}% off) — {days} days left."
            )
            subs = _subscriptions(conn, business_id=b["id"])
            sent_count += _deliver(subs, TITLE, body, dry_run)
            _log(conn, b["id"], None, kind, ref)
            planned.append(f"{kind} -> {b['name_en']} (days={days}, gap={prog['amount_to_next']}, subs={len(subs)})")

        # --- yearly login-refresh (per user) ---
        users = conn.execute(
            "SELECT id, business_id, last_login_at FROM users WHERE status = 'active' AND last_login_at IS NOT NULL"
        ).fetchall()
        for u in users:
            since = (today - _as_date(u["last_login_at"])).days
            if since < LOGIN_REFRESH_DAYS:
                continue
            ref = u["last_login_at"][:10]
            if _already_sent(conn, u["business_id"], u["id"], "login_refresh", ref):
                continue
            body = "سجّل الدخول للحفاظ على حسابك ومتابعة أسعارك وعروضك. / Log in to keep your account active and see your prices."
            subs = _subscriptions(conn, user_id=u["id"])
            sent_count += _deliver(subs, TITLE, body, dry_run)
            _log(conn, u["business_id"], u["id"], "login_refresh", ref)
            planned.append(f"login_refresh -> user {u['id']} (idle={since}d, subs={len(subs)})")

        if not dry_run:
            conn.commit()
    finally:
        conn.close()

    return {"dry_run": dry_run, "notifications": planned, "pushes_sent": sent_count}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="samafood.notify")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="evaluate and send scheduled notifications")
    run_p.add_argument("--dry-run", action="store_true", help="preview without sending or logging")
    args = parser.parse_args(argv)

    db.init_db()
    result = run(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
