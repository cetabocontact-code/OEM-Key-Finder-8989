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
    abort,
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
from .i18n import DEFAULT_LANG, STRINGS, normalize_lang, t

OTP_TTL_MINUTES = 5
OTP_MAX_ATTEMPTS = 5
PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")
ALLOWED_DOC_EXT = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
UPLOAD_DIR = Path(os.environ.get("SAMA_UPLOAD_DIR", db.DB_PATH.parent / "uploads"))


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

    def current_client() -> dict[str, Any] | None:
        client_id = session.get("client_id")
        if not client_id:
            return None
        conn = db.get_db()
        try:
            row = conn.execute(
                """SELECT c.*, tr.discount_pct, tr.name_en AS tier_en, tr.name_ar AS tier_ar
                   FROM clients c LEFT JOIN tiers tr ON tr.id = c.tier_id
                   WHERE c.id = ?""",
                (client_id,),
            ).fetchone()
        finally:
            conn.close()
        return dict(row) if row else None

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_client():
                return jsonify({"error": "auth_required"}), 401
            return view(*args, **kwargs)

        return wrapped

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

    # ---- pages ---------------------------------------------------------
    @app.get("/")
    def home():
        client = current_client()
        return render_template(
            "index.html",
            lang=g.lang,
            strings={k: t(k, g.lang) for k in STRINGS},
            client=client,
            vapid_public_key=push.public_key(),
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
            n = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
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
            client = conn.execute(
                "SELECT id, status FROM clients WHERE phone = ?", (phone,)
            ).fetchone()
            if not client:
                return jsonify({"error": "not_registered", "can_apply": True}), 404
            if client["status"] != "approved":
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
            # Dev mode: no SMS provider configured, surface code so the flow is testable.
            payload["dev_code"] = code
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
            client = conn.execute("SELECT id FROM clients WHERE phone = ?", (phone,)).fetchone()
            conn.execute("DELETE FROM otp_codes WHERE phone = ?", (phone,))
            conn.commit()
        finally:
            conn.close()
        session["client_id"] = client["id"]
        return jsonify({"ok": True})

    @app.post("/api/auth/logout")
    def logout():
        session.pop("client_id", None)
        return jsonify({"ok": True})

    @app.get("/api/me")
    def me():
        client = current_client()
        if not client:
            return jsonify({"client": None})
        return jsonify(
            {
                "client": {
                    "name": client["name_ar"] if g.lang == "ar" else client["name_en"],
                    "tier": client["tier_ar"] if g.lang == "ar" else client["tier_en"],
                    "discount_pct": client["discount_pct"] or 0,
                    "yearly_spend": client["yearly_spend"],
                }
            }
        )

    # ---- catalog & offers ---------------------------------------------
    @app.get("/api/catalog")
    def catalog():
        client = current_client()
        discount = (client or {}).get("discount_pct") or 0
        conn = db.get_db()
        try:
            rows = conn.execute("SELECT * FROM products ORDER BY category, name_en").fetchall()
        finally:
            conn.close()
        products = []
        for r in rows:
            products.append(
                {
                    "sku": r["sku"],
                    "name": r["name_ar"] if g.lang == "ar" else r["name_en"],
                    "category": r["category"],
                    "size": r["size"],
                    "base_price": r["base_price"],
                    "your_price": price_for(r["base_price"], discount) if client else None,
                    "min_order": r["min_order"],
                    "stock": r["stock"],
                    "image_url": r["image_url"],
                }
            )
        return jsonify({"products": products, "discount_pct": discount, "logged_in": bool(client)})

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
                    {
                        "title": r["title_ar"] if g.lang == "ar" else r["title_en"],
                        "body": r["body_ar"] if g.lang == "ar" else r["body_en"],
                        "kind": r["kind"],
                    }
                    for r in rows
                ]
            }
        )

    # ---- orders --------------------------------------------------------
    @app.post("/api/orders")
    @login_required
    def create_order():
        client = current_client()
        items_in = (request.json or {}).get("items", [])
        note = (request.json or {}).get("note", "")[:500]
        if not isinstance(items_in, list) or not items_in:
            return jsonify({"error": "empty_order"}), 400
        conn = db.get_db()
        try:
            discount = client["discount_pct"] or 0
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
                line_total = prod["base_price"] * qty
                subtotal += line_total
                line_items.append(
                    {"sku": sku, "name_en": prod["name_en"], "name_ar": prod["name_ar"], "qty": qty, "base_price": prod["base_price"]}
                )
            if not line_items:
                return jsonify({"error": "empty_order"}), 400
            total = round(subtotal * (1 - discount / 100), 3)
            order_id = conn.execute(
                """INSERT INTO orders (client_id, items_json, subtotal, discount_pct, total, status, note, created_at)
                   VALUES (?,?,?,?,?,'submitted',?,?)""",
                (client["id"], json.dumps(line_items, ensure_ascii=False), round(subtotal, 3), discount, total, note, db.utc_now()),
            ).lastrowid
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True, "order_id": order_id, "subtotal": round(subtotal, 3), "discount_pct": discount, "total": total})

    @app.get("/api/orders")
    @login_required
    def list_orders():
        client = current_client()
        conn = db.get_db()
        try:
            rows = conn.execute(
                "SELECT id, items_json, subtotal, discount_pct, total, status, created_at FROM orders WHERE client_id = ? ORDER BY id DESC",
                (client["id"],),
            ).fetchall()
        finally:
            conn.close()
        orders = []
        for r in rows:
            orders.append(
                {
                    "id": r["id"],
                    "items": json.loads(r["items_json"]),
                    "subtotal": r["subtotal"],
                    "discount_pct": r["discount_pct"],
                    "total": r["total"],
                    "status": r["status"],
                    "created_at": r["created_at"],
                }
            )
        return jsonify({"orders": orders})

    # ---- vendor application -------------------------------------------
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
        client = current_client()
        conn = db.get_db()
        try:
            conn.execute(
                """INSERT INTO push_subscriptions (client_id, endpoint, subscription_json, created_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(endpoint) DO UPDATE SET subscription_json=excluded.subscription_json""",
                (client["id"] if client else None, endpoint, json.dumps(sub), db.utc_now()),
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

    @app.get("/api/admin/overview")
    @admin_required
    def admin_overview():
        conn = db.get_db()
        try:
            orders = db.rows_to_dicts(
                conn.execute(
                    """SELECT o.id, o.total, o.status, o.created_at, c.name_en AS client
                       FROM orders o JOIN clients c ON c.id = o.client_id ORDER BY o.id DESC LIMIT 50"""
                ).fetchall()
            )
            apps = db.rows_to_dicts(
                conn.execute("SELECT id, business_name, contact_name, phone, status, documents_json, created_at FROM vendor_applications ORDER BY id DESC LIMIT 50").fetchall()
            )
            subs = conn.execute("SELECT COUNT(*) FROM push_subscriptions").fetchone()[0]
        finally:
            conn.close()
        for a in apps:
            a["documents"] = json.loads(a.pop("documents_json"))
        source = "seed/manual"
        from .integrations import active_source

        live = active_source()
        if live:
            source = live.name
        return jsonify({"orders": orders, "applications": apps, "subscribers": subs, "product_source": source})

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
        sent = 0
        for row in subs:
            if push.send(json.loads(row["subscription_json"]), title, body, target_url):
                sent += 1
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
