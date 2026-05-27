# Sama Vendor Connect (v1)

Client-facing B2B web app (PWA) for Sama Food Industries: vendors log in by
phone + OTP, browse the catalog at their **tier price**, place bulk orders,
apply to become a vendor (with document upload), and receive **push
notifications** for offers and current rates. Bilingual **Arabic (default,
RTL) / English**. Includes an admin dashboard.

It is **complementary** to Sama's existing systems (SAP Business One for
accounting, Olive for sales/inventory/GPS/invoicing) — not a replacement.

## Deploy to Render (gets you a public test link)

One-click (repo already contains `render.yaml`):

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/cetabocontact-code/OEM-Key-Finder-8989/tree/claude/vendor-notification-app-xaE8l)

Or manually: render.com → **New → Blueprint** → connect this repo and the
`claude/vendor-notification-app-xaE8l` branch → set **`SAMA_ADMIN_PASSWORD`**
when prompted → Apply. Render builds with `render.yaml`, gives an HTTPS URL
(e.g. `https://samafood-vendor-app.onrender.com`), which is the link you can
open on a phone. HTTPS also makes push notifications work.

Demo login on the live link: phone **+962790000000** (OTP shows on screen in
dev mode). Admin at `/admin`.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SAMA_ADMIN_PASSWORD=choose-a-password
gunicorn "samafood:create_app()" --bind 0.0.0.0:8080
# open http://localhost:8080  (admin at /admin)
```

Demo client phone: `+962790000000` (Silver tier, 4% discount). With no SMS
gateway configured, the OTP is returned in the login response (dev mode) and
shown on screen.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string. **If set, the app uses Postgres** (production / Render). If unset, it falls back to local SQLite. |
| `SAMA_SECRET_KEY` | Flask session signing key (Render auto-generates). |
| `SAMA_ADMIN_PASSWORD` | Password for `/admin`. **Required** to use admin. |
| `SAMA_DB_PATH` | SQLite path for local dev (defaults to `data/samafood.db`). Ignored when `DATABASE_URL` is set. |
| `SAMA_UPLOAD_DIR` | Where vendor documents are stored. |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CONTACT` | Web Push keys. Auto-generated if unset, **but must be set in prod** so the web service and the notify cron sign with the same keys (otherwise scheduled pushes won't deliver). |
| `SAP_SL_URL` / `SAP_SL_COMPANYDB` / `SAP_SL_USER` / `SAP_SL_PASSWORD` | SAP Business One Service Layer — enables catalog sync. |
| `OLIVE_API_URL` / `OLIVE_API_KEY` | Olive API — enables catalog sync (takes priority over SAP). |
| SMS gateway creds | Not yet wired — see `_send_sms()` in `app.py`. |

## Scheduled notifications
A daily Render cron worker (`python -m samafood.notify run`, defined in
`render.yaml`) sends:
- **Tier nudges** — as a business's purchasing year (its `created_at`
  anniversary) approaches, it gets one push at the 90-, 60-, and 30-day marks
  telling it how much more to spend to reach the next discount tier.
- **Login refresh** — a user ~11 months idle is reminded to log in.

Sends are idempotent (tracked in `notifications_log`), so re-runs don't repeat.
Run `python -m samafood.notify run --dry-run` to preview, or trigger from the
admin via `POST /api/admin/run-notifications`.

## Status of integrations
- **Catalog/prices/stock**: seeded data until SAP B1 or Olive credentials are
  set, then `Admin → Sync` pulls live data via `integrations.py`.
- **OTP SMS**: dev mode (code shown on screen) until an SMS gateway is wired
  into `_send_sms()`.
- **Push**: works with auto-generated VAPID keys; requires HTTPS (Render
  provides it).
