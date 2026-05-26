# Sama Vendor Connect (v1)

Client-facing B2B web app (PWA) for Sama Food Industries: vendors log in by
phone + OTP, browse the catalog at their **tier price**, place bulk orders,
apply to become a vendor (with document upload), and receive **push
notifications** for offers and current rates. Bilingual **Arabic (default,
RTL) / English**. Includes an admin dashboard.

It is **complementary** to Sama's existing systems (SAP Business One for
accounting, Olive for sales/inventory/GPS/invoicing) — not a replacement.

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
| `SAMA_SECRET_KEY` | Flask session signing key (Render auto-generates). |
| `SAMA_ADMIN_PASSWORD` | Password for `/admin`. **Required** to use admin. |
| `SAMA_DB_PATH` | SQLite path (defaults to `data/samafood.db`). |
| `SAMA_UPLOAD_DIR` | Where vendor documents are stored. |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CONTACT` | Web Push keys. Auto-generated if unset (set them in prod so subscriptions survive restarts). |
| `SAP_SL_URL` / `SAP_SL_COMPANYDB` / `SAP_SL_USER` / `SAP_SL_PASSWORD` | SAP Business One Service Layer — enables catalog sync. |
| `OLIVE_API_URL` / `OLIVE_API_KEY` | Olive API — enables catalog sync (takes priority over SAP). |
| SMS gateway creds | Not yet wired — see `_send_sms()` in `app.py`. |

## Status of integrations
- **Catalog/prices/stock**: seeded data until SAP B1 or Olive credentials are
  set, then `Admin → Sync` pulls live data via `integrations.py`.
- **OTP SMS**: dev mode (code shown on screen) until an SMS gateway is wired
  into `_send_sms()`.
- **Push**: works with auto-generated VAPID keys; requires HTTPS (Render
  provides it).
