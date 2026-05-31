"""Flask application factory and routes for the Sama Food vendor app."""

from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from . import db, push
from .i18n import CONTACT, DEFAULT_LANG, FAQ, STRINGS, normalize_lang, t

OTP_TTL_MINUTES = 5
OTP_MAX_ATTEMPTS = 5
PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")
ALLOWED_DOC_EXT = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
UPLOAD_DIR = Path(os.environ.get("SAMA_UPLOAD_DIR", db.DB_PATH.parent / "uploads"))
ROLES = ("owner", "buyer", "viewer")
ORDERING_ROLES = ("owner", "buyer")

USER_QUERY = """
SELECT u.id AS user_id, u.name AS user_name, u.role AS role, u.status AS user_status,
       b.id AS business_id, b.name_en AS b_name_en, b.name_ar AS b_name_ar,
       b.status AS b_status, b.yearly_spend AS yearly_spend,
       tr.discount_pct AS discount_pct, tr.name_en AS tier_en, tr.name_ar AS tier_ar
FROM users u
JOIN businesses b ON b.id = u.business_id
LEFT JOIN tiers tr ON tr.id = b.tier_id
WHERE u.id = ?
"""


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("SAMA_SECRET_KEY", secrets.token_hex(32))
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    db.init_db()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # ---- helpers -------------------------------------------------------
    def current_lang() -> str:
        return normalize_lang(request.args.get("lang") or session.get("lang") or DEFAULT_LANG)

    @app.before_request
    def _set_lang() -> None:
        if request.args.get("lang"):
            session["lang"] = normalize_lang(request.args.get("lang"))
        g.lang = current_lang()

    def current_user() -> dict[str, Any] | None:
        user_id = session.get("user_id")
        if not user_id:
            return None
        conn = db.get_db()
        try:
            row = conn.execute(USER_QUERY, (user_id,)).fetchone()
        finally:
            conn.close()
        if not row or row["user_status"] != "active" or row["b_status"] != "approved":
            return None
        return dict(row)

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user():
                return jsonify({"error": "auth_required"}), 401
            return view(*args, **kwargs)

        return wrapped

    def role_required(*roles):
        def deco(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                user = current_user()
                if not user:
                    return jsonify({"error": "auth_required"}), 401
                if user["role"] not in roles:
                    return jsonify({"error": "forbidden", "need_role": list(roles)}), 403
                g.user = user
                return view(*args, **kwargs)

            return wrapped

        return deco

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("is_admin"):
                if request.path.startswith("/api/"):
                    return jsonify({"error": "admin_required"}), 401
                return redirect(url_for("admin_login_page"))
            return view(*args, **kwargs)

        return wrapped

    def price_for(base_price: float, discount_pct: float) -> float:
        return round(base_price * (1 - (discount_pct or 0) / 100), 3)

    def localized(row: dict[str, Any], field: str) -> str:
        return row[f"{field}_ar"] if g.lang == "ar" else row[f"{field}_en"]

    # ---- pages ---------------------------------------------------------
    @app.get("/")
    def home():
        user = current_user()
        if not user:
            return render_template(
                "login.html",
                lang=g.lang,
                strings={k: t(k, g.lang) for k in STRINGS},
                contact=CONTACT,
            )
        return render_template(
            "index.html",
            lang=g.lang,
            strings={k: t(k, g.lang) for k in STRINGS},
            user=user,
            faq=FAQ,
            contact=CONTACT,
            vapid_public_key=push.public_key(),
        )

    @app.get("/apply")
    def apply_page():
        return render_template(
            "apply.html",
            lang=g.lang,
            strings={k: t(k, g.lang) for k in STRINGS},
            contact=CONTACT,
        )

    @app.get("/admin")
    @admin_required
    def admin_page():
        return render_template("admin.html", lang=g.lang)

    @app.get("/admin/login")
    def admin_login_page():
        return render_template("admin_login.html", lang=g.lang)

    # ---- health --------------------------------------------------------
    @app.get("/api/health")
    def health():
        conn = db.get_db()
        try:
            n = conn.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
        finally:
            conn.close()
        return jsonify({"ok": True, "products": n})

    # ---- auth (phone + OTP) -------------------------------------------
    @app.post("/api/auth/request-otp")
    def request_otp():
        phone = (request.json or {}).get("phone", "").strip()
        if not PHONE_RE.match(phone):
            return jsonify({"error": "invalid_phone"}), 400
        conn = db.get_db()
        try:
            user = conn.execute(
                """SELECT u.id, u.status AS user_status, b.status AS b_status
                   FROM users u JOIN businesses b ON b.id = u.business_id
                   WHERE u.phone = ?""",
                (phone,),
            ).fetchone()
            if not user:
                return jsonify({"error": "not_registered", "can_apply": True}), 404
            if user["user_status"] != "active":
                return jsonify({"error": "user_disabled"}), 403
            if user["b_status"] != "approved":
                return jsonify({"error": "not_approved"}), 403
            code = f"{secrets.randbelow(1_000_000):06d}"
            expires = (datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()
            conn.execute(
                """INSERT INTO otp_codes (phone, code, expires_at, attempts) VALUES (?,?,?,0)
                   ON CONFLICT(phone) DO UPDATE SET code=excluded.code, expires_at=excluded.expires_at, attempts=0""",
                (phone, code, expires),
            )
            conn.commit()
        finally:
            conn.close()
        delivered = _send_sms(phone, code)
        payload: dict[str, Any] = {"ok": True, "sms_delivered": delivered}
        if not delivered:
            payload["dev_code"] = code  # Dev mode: no SMS gateway wired yet.
        return jsonify(payload)

    @app.post("/api/auth/verify-otp")
    def verify_otp():
        data = request.json or {}
        phone = data.get("phone", "").strip()
        code = data.get("code", "").strip()
        conn = db.get_db()
        try:
            row = conn.execute("SELECT * FROM otp_codes WHERE phone = ?", (phone,)).fetchone()
            if not row:
                return jsonify({"error": "no_code"}), 400
            if row["attempts"] >= OTP_MAX_ATTEMPTS:
                return jsonify({"error": "too_many_attempts"}), 429
            if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
                return jsonify({"error": "code_expired"}), 400
            if not secrets.compare_digest(row["code"], code):
                conn.execute("UPDATE otp_codes SET attempts = attempts + 1 WHERE phone = ?", (phone,))
                conn.commit()
                return jsonify({"error": "wrong_code"}), 400
            user = conn.execute("SELECT id FROM users WHERE phone = ?", (phone,)).fetchone()
            conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (db.utc_now(), user["id"]))
            conn.execute("DELETE FROM otp_codes WHERE phone = ?", (phone,))
            conn.commit()
        finally:
            conn.close()
        session["user_id"] = user["id"]
        return jsonify({"ok": True})

    @app.post("/api/auth/logout")
    def logout():
        session.pop("user_id", None)
        return jsonify({"ok": True})

    @app.get("/api/me")
    def me():
        user = current_user()
        if not user:
            return jsonify({"user": None})
        return jsonify(
            {
                "user": {
                    "name": user["user_name"],
                    "role": user["role"],
                    "business": user["b_name_ar"] if g.lang == "ar" else user["b_name_en"],
                    "tier": user["tier_ar"] if g.lang == "ar" else user["tier_en"],
                    "discount_pct": user["discount_pct"] or 0,
                    "yearly_spend": user["yearly_spend"],
                    "can_order": user["role"] in ORDERING_ROLES,
                    "can_manage_team": user["role"] == "owner",
                }
            }
        )

    # ---- catalog & offers ---------------------------------------------
    @app.get("/api/catalog")
    def catalog():
        user = current_user()
        discount = (user or {}).get("discount_pct") or 0
        conn = db.get_db()
        try:
            rows = conn.execute("SELECT * FROM products ORDER BY category, name_en").fetchall()
        finally:
            conn.close()
        products = [
            {
                "sku": r["sku"],
                "name": localized(r, "name"),
                "category": r["category"],
                "size": r["size"],
                "base_price": r["base_price"],
                "your_price": price_for(r["base_price"], discount) if user else None,
                "min_order": r["min_order"],
                "stock": r["stock"],
                "image_url": r["image_url"],
            }
            for r in rows
        ]
        return jsonify({"products": products, "discount_pct": discount, "logged_in": bool(user)})

    @app.get("/api/offers")
    def offers():
        conn = db.get_db()
        try:
            rows = conn.execute("SELECT * FROM offers WHERE active = 1 ORDER BY created_at DESC").fetchall()
        finally:
            conn.close()
        return jsonify(
            {
                "offers": [
                    {"title": localized(r, "title"), "body": localized(r, "body"), "kind": r["kind"]}
                    for r in rows
                ]
            }
        )

    # ---- orders --------------------------------------------------------
    DELIVERY_METHODS = ("pickup", "delivery")
    PAYMENT_METHODS = ("on_account", "cash", "card")

    @app.post("/api/orders")
    @role_required(*ORDERING_ROLES)
    def create_order():
        user = g.user
        body = request.json or {}
        items_in = body.get("items", [])
        note = (body.get("note") or "")[:500]
        delivery_method = body.get("delivery_method", "pickup")
        delivery_address = (body.get("delivery_address") or "")[:300]
        payment_method = body.get("payment_method", "on_account")
        if delivery_method not in DELIVERY_METHODS:
            return jsonify({"error": "invalid_delivery_method"}), 400
        if payment_method not in PAYMENT_METHODS:
            return jsonify({"error": "invalid_payment_method"}), 400
        if delivery_method == "delivery" and not delivery_address.strip():
            return jsonify({"error": "delivery_address_required"}), 400
        if not isinstance(items_in, list) or not items_in:
            return jsonify({"error": "empty_order"}), 400
        conn = db.get_db()
        try:
            discount = user["discount_pct"] or 0
            line_items = []
            subtotal = 0.0
            for item in items_in:
                sku = str(item.get("sku", ""))
                qty = int(item.get("qty", 0))
                if qty <= 0:
                    continue
                prod = conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
                if not prod:
                    return jsonify({"error": "unknown_sku", "sku": sku}), 400
                if qty < prod["min_order"]:
                    return jsonify({"error": "below_min_order", "sku": sku, "min_order": prod["min_order"]}), 400
                subtotal += prod["base_price"] * qty
                line_items.append(
                    {"sku": sku, "name_en": prod["name_en"], "name_ar": prod["name_ar"], "qty": qty, "base_price": prod["base_price"]}
                )
            if not line_items:
                return jsonify({"error": "empty_order"}), 400
            total = round(subtotal * (1 - discount / 100), 3)
            order_id = conn.insert(
                """INSERT INTO orders (business_id, user_id, items_json, subtotal, discount_pct, total, status, note,
                                       delivery_method, delivery_address, payment_method, created_at)
                   VALUES (?,?,?,?,?,?,'submitted',?,?,?,?,?)""",
                (user["business_id"], user["user_id"], json.dumps(line_items, ensure_ascii=False),
                 round(subtotal, 3), discount, total, note,
                 delivery_method, delivery_address, payment_method, db.utc_now()),
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify({
            "ok": True, "order_id": order_id,
            "subtotal": round(subtotal, 3), "discount_pct": discount, "total": total,
            "delivery_method": delivery_method, "payment_method": payment_method,
        })

    @app.get("/api/orders")
    @login_required
    def list_orders():
        user = current_user()
        conn = db.get_db()
        try:
            rows = conn.execute(
                """SELECT o.id, o.items_json, o.subtotal, o.discount_pct, o.total, o.status, o.created_at,
                          o.delivery_method, o.delivery_address, o.payment_method, o.note,
                          u.name AS placed_by
                   FROM orders o LEFT JOIN users u ON u.id = o.user_id
                   WHERE o.business_id = ? ORDER BY o.id DESC""",
                (user["business_id"],),
            ).fetchall()
        finally:
            conn.close()
        orders = [
            {
                "id": r["id"],
                "items": json.loads(r["items_json"]),
                "subtotal": r["subtotal"],
                "discount_pct": r["discount_pct"],
                "total": r["total"],
                "status": r["status"],
                "placed_by": r["placed_by"],
                "created_at": r["created_at"],
                "delivery_method": r["delivery_method"],
                "delivery_address": r["delivery_address"],
                "payment_method": r["payment_method"],
                "note": r["note"],
            }
            for r in rows
        ]
        return jsonify({"orders": orders})

    @app.get("/api/orders/<int:order_id>")
    @login_required
    def order_detail(order_id: int):
        user = current_user()
        conn = db.get_db()
        try:
            row = conn.execute(
                """SELECT o.*, u.name AS placed_by, b.name_en AS business_en, b.name_ar AS business_ar
                   FROM orders o LEFT JOIN users u ON u.id = o.user_id
                   JOIN businesses b ON b.id = o.business_id
                   WHERE o.id = ? AND o.business_id = ?""",
                (order_id, user["business_id"]),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return jsonify({"error": "not_found"}), 404
        return jsonify({
            "id": row["id"],
            "items": json.loads(row["items_json"]),
            "subtotal": row["subtotal"],
            "discount_pct": row["discount_pct"],
            "total": row["total"],
            "status": row["status"],
            "placed_by": row["placed_by"],
            "created_at": row["created_at"],
            "delivery_method": row["delivery_method"],
            "delivery_address": row["delivery_address"],
            "payment_method": row["payment_method"],
            "note": row["note"],
            "business": row["business_ar"] if g.lang == "ar" else row["business_en"],
        })

    # ---- dashboard -----------------------------------------------------
    @app.get("/api/dashboard")
    @login_required
    def dashboard():
        user = current_user()
        spend = user["yearly_spend"] or 0
        conn = db.get_db()
        try:
            prog = db.tier_progress(conn, spend)
            agg = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(total),0) AS spent FROM orders WHERE business_id = ?",
                (user["business_id"],),
            ).fetchone()
        finally:
            conn.close()

        upcoming = prog["upcoming"]
        next_tier = (
            {"name": (upcoming["name_ar"] if g.lang == "ar" else upcoming["name_en"]), "discount_pct": upcoming["discount_pct"]}
            if upcoming
            else None
        )
        return jsonify(
            {
                "business": user["b_name_ar"] if g.lang == "ar" else user["b_name_en"],
                "tier": user["tier_ar"] if g.lang == "ar" else user["tier_en"],
                "discount_pct": user["discount_pct"] or 0,
                "yearly_spend": spend,
                "next_tier": next_tier,
                "amount_to_next": prog["amount_to_next"],
                "progress_pct": prog["progress_pct"],
                "orders_count": agg["n"],
                "orders_total": round(agg["spent"], 2),
            }
        )


    @app.get("/api/team")
    @role_required("owner")
    def list_team():
        conn = db.get_db()
        try:
            rows = conn.execute(
                "SELECT id, name, phone, role, status, created_at FROM users WHERE business_id = ? ORDER BY id",
                (g.user["business_id"],),
            ).fetchall()
        finally:
            conn.close()
        return jsonify({"team": db.rows_to_dicts(rows), "me": g.user["user_id"]})

    @app.post("/api/team/invite")
    @role_required("owner")
    def invite_user():
        data = request.json or {}
        name = data.get("name", "").strip()
        phone = data.get("phone", "").strip()
        role = data.get("role", "buyer")
        if not name or not PHONE_RE.match(phone):
            return jsonify({"error": "invalid_input"}), 400
        if role not in ("buyer", "viewer"):
            return jsonify({"error": "invalid_role"}), 400
        conn = db.get_db()
        try:
            if conn.execute("SELECT 1 FROM users WHERE phone = ?", (phone,)).fetchone():
                return jsonify({"error": "phone_taken"}), 409
            conn.execute(
                "INSERT INTO users (business_id, name, phone, role, status, created_at) VALUES (?,?,?,?,'active',?)",
                (g.user["business_id"], name, phone, role, db.utc_now()),
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True})

    @app.post("/api/team/<int:user_id>/update")
    @role_required("owner")
    def update_user(user_id: int):
        data = request.json or {}
        if user_id == g.user["user_id"]:
            return jsonify({"error": "cannot_modify_self"}), 400
        conn = db.get_db()
        try:
            target = conn.execute(
                "SELECT id FROM users WHERE id = ? AND business_id = ?", (user_id, g.user["business_id"])
            ).fetchone()
            if not target:
                return jsonify({"error": "not_found"}), 404
            if "role" in data:
                if data["role"] not in ("buyer", "viewer"):
                    return jsonify({"error": "invalid_role"}), 400
                conn.execute("UPDATE users SET role = ? WHERE id = ?", (data["role"], user_id))
            if "status" in data:
                if data["status"] not in ("active", "disabled"):
                    return jsonify({"error": "invalid_status"}), 400
                conn.execute("UPDATE users SET status = ? WHERE id = ?", (data["status"], user_id))
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True})

    # ---- contact messages ----------------------------------------------
    @app.post("/api/contact-message")
    def contact_message():
        data = request.json or {}
        name = (data.get("name") or "").strip()[:120]
        phone = (data.get("phone") or "").strip()[:20]
        subject = (data.get("subject") or "").strip()[:200]
        message = (data.get("message") or "").strip()[:2000]
        if not name or not phone or not message:
            return jsonify({"error": "missing_fields"}), 400
        if not PHONE_RE.match(phone):
            return jsonify({"error": "invalid_phone"}), 400
        user = current_user()
        conn = db.get_db()
        try:
            conn.execute(
                """INSERT INTO contact_messages (user_id, business_id, name, phone, subject, message, status, created_at)
                   VALUES (?,?,?,?,?,?,'new',?)""",
                (
                    user["user_id"] if user else None,
                    user["business_id"] if user else None,
                    name, phone, subject, message, db.utc_now(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True})

    # ---- vendor / distributor application ------------------------------
    @app.post("/api/vendor-application")
    def vendor_application():
        form = request.form
        business = form.get("business_name", "").strip()
        contact_name = form.get("contact_name", "").strip()
        phone = form.get("phone", "").strip()
        client_type = form.get("client_type", "retail").strip()
        if not business or not contact_name or not PHONE_RE.match(phone):
            return jsonify({"error": "invalid_input"}), 400
        saved_docs = []
        for file in request.files.getlist("documents"):
            if not file or not file.filename:
                continue
            ext = Path(file.filename).suffix.lower()
            if ext not in ALLOWED_DOC_EXT:
                return jsonify({"error": "bad_file_type", "filename": file.filename}), 400
            safe = f"{secrets.token_hex(8)}_{secure_filename(file.filename)}"
            file.save(UPLOAD_DIR / safe)
            saved_docs.append({"original": file.filename, "stored": safe})
        conn = db.get_db()
        try:
            conn.execute(
                """INSERT INTO vendor_applications (business_name, contact_name, phone, client_type, documents_json, status, created_at)
                   VALUES (?,?,?,?,?,'pending',?)""",
                (business, contact_name, phone, client_type, json.dumps(saved_docs, ensure_ascii=False), db.utc_now()),
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True})

    # ---- push ----------------------------------------------------------
    @app.get("/api/push/public-key")
    def push_public_key():
        return jsonify({"public_key": push.public_key()})

    @app.post("/api/push/subscribe")
    def push_subscribe():
        sub = request.json or {}
        endpoint = sub.get("endpoint")
        if not endpoint:
            return jsonify({"error": "invalid_subscription"}), 400
        user = current_user()
        conn = db.get_db()
        try:
            conn.execute(
                """INSERT INTO push_subscriptions (user_id, endpoint, subscription_json, created_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(endpoint) DO UPDATE SET subscription_json=excluded.subscription_json""",
                (user["user_id"] if user else None, endpoint, json.dumps(sub), db.utc_now()),
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True})

    # ---- admin ---------------------------------------------------------
    @app.post("/api/admin/login")
    def admin_login():
        password = (request.json or {}).get("password", "")
        expected = os.environ.get("SAMA_ADMIN_PASSWORD", "")
        if not expected:
            return jsonify({"error": "admin_password_not_set"}), 500
        if not secrets.compare_digest(password, expected):
            return jsonify({"error": "wrong_password"}), 401
        session["is_admin"] = True
        return jsonify({"ok": True})

    @app.post("/api/admin/logout")
    def admin_logout():
        session.pop("is_admin", None)
        return jsonify({"ok": True})

    @app.post("/api/admin/run-notifications")
    @admin_required
    def admin_run_notifications():
        from . import notify

        dry_run = bool((request.json or {}).get("dry_run"))
        return jsonify(notify.run(dry_run=dry_run))

    @app.post("/api/admin/demo")
    @admin_required
    def admin_demo():
        from . import demo as demo_module

        action = (request.json or {}).get("action", "")
        if action == "seed":
            return jsonify(demo_module.seed_demo(force=True))
        if action == "clear":
            return jsonify(demo_module.clear_demo())
        if action == "reseed":
            return jsonify(demo_module.reseed_demo())
        return jsonify({"error": "unknown_action", "valid": ["seed", "clear", "reseed"]}), 400

    @app.get("/api/admin/overview")
    @admin_required
    def admin_overview():
        conn = db.get_db()
        try:
            orders = db.rows_to_dicts(
                conn.execute(
                    """SELECT o.id, o.total, o.status, o.created_at, b.name_en AS business, u.name AS placed_by
                       FROM orders o JOIN businesses b ON b.id = o.business_id
                       LEFT JOIN users u ON u.id = o.user_id ORDER BY o.id DESC LIMIT 50"""
                ).fetchall()
            )
            apps = db.rows_to_dicts(
                conn.execute(
                    "SELECT id, business_name, contact_name, phone, status, documents_json, created_at FROM vendor_applications ORDER BY id DESC LIMIT 50"
                ).fetchall()
            )
            messages = db.rows_to_dicts(
                conn.execute(
                    "SELECT id, name, phone, subject, message, status, created_at FROM contact_messages ORDER BY id DESC LIMIT 50"
                ).fetchall()
            )
            subs = conn.execute("SELECT COUNT(*) AS n FROM push_subscriptions").fetchone()["n"]
            businesses = conn.execute("SELECT COUNT(*) AS n FROM businesses").fetchone()["n"]
            users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        finally:
            conn.close()
        for a in apps:
            a["documents"] = json.loads(a.pop("documents_json"))
        from .integrations import active_source

        live = active_source()
        return jsonify(
            {
                "orders": orders,
                "applications": apps,
                "messages": messages,
                "subscribers": subs,
                "businesses": businesses,
                "users": users,
                "product_source": live.name if live else "seed/manual",
            }
        )

    @app.post("/api/admin/notify")
    @admin_required
    def admin_notify():
        data = request.json or {}
        title = data.get("title", "").strip()
        body = data.get("body", "").strip()
        target_url = data.get("url", "/")
        if not title:
            return jsonify({"error": "title_required"}), 400
        conn = db.get_db()
        try:
            subs = conn.execute("SELECT subscription_json FROM push_subscriptions").fetchall()
        finally:
            conn.close()
        sent = sum(1 for row in subs if push.send(json.loads(row["subscription_json"]), title, body, target_url))
        return jsonify({"ok": True, "sent": sent, "total": len(subs)})

    @app.post("/api/admin/sync")
    @admin_required
    def admin_sync():
        from .integrations import active_source

        source = active_source()
        if not source:
            return jsonify({"error": "no_live_source", "hint": "Set SAP_SL_* or OLIVE_API_* env vars to enable sync."}), 400
        try:
            products = source.fetch_products()
        except Exception as exc:  # noqa: BLE001 - surface integration errors to admin
            return jsonify({"error": "sync_failed", "detail": str(exc)}), 502
        conn = db.get_db()
        try:
            for p in products:
                conn.execute(
                    """INSERT INTO products (sku, name_en, name_ar, category, size, base_price, stock, source)
                       VALUES (?,?,?,?,?,?,?,?)
                       ON CONFLICT(sku) DO UPDATE SET
                         name_en=excluded.name_en, name_ar=excluded.name_ar,
                         base_price=excluded.base_price, stock=excluded.stock, source=excluded.source""",
                    (p["sku"], p["name_en"], p["name_ar"], p.get("category", "other"), p.get("size", ""), p.get("base_price", 0), p.get("stock", 0), source.name),
                )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True, "synced": len(products), "source": source.name})

    return app


def _send_sms(phone: str, code: str) -> bool:
    """Send the OTP via SMS. Returns True if a provider delivered it.

    No provider is wired in v1 (awaiting Sama's SMS gateway credentials), so
    this returns False and the caller falls back to dev mode. Drop the chosen
    provider's API call here once credentials are available.
    """
    return False
