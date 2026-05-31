# QA Test Plan — Sama Vendor Connect

**Purpose:** human walk-through to validate every user-facing flow before a real customer demo. Each row is one test. Copy this into Google Sheets if you prefer (open in Sheets → File → Import → Upload this `.md` and paste as table).

## Setup
- Browser: latest Chrome or Safari on a real phone is the realistic env (it's a PWA).
- Live URL (Render): _fill in once deployed_
- Admin URL: `<live-url>/admin`
- Admin password: _set when deploying via `SAMA_ADMIN_PASSWORD`_
- All demo accounts have names starting with `[DEMO]` and are wiped via **Admin → Clear demo**.

## Demo accounts to test with

| Business | Tier | Owner phone | Buyer phone | Viewer phone |
| --- | --- | --- | --- | --- |
| [DEMO] Quick Stop Café | Bronze (0%) | +962790000010 | +962790000011 | — |
| [DEMO] Demo Market | Silver (4%) | +962790000000 | +962790000001 | +962790000002 |
| [DEMO] Royal Restaurant | Gold (7%) | +962790000020 | +962790000021 | — |
| [DEMO] Grand Hotel HoReCa | Platinum (10%) | +962790000030 | +962790000031 | +962790000032 |

OTP is shown in the response (dev mode, no SMS gateway wired yet).

---

## Test cases

| # | Area | Test | Steps | Expected | Pass/Fail | Notes |
|---|---|---|---|---|---|---|
| 1 | Public | Home loads in Arabic by default | Open live URL | Page renders RTL, Arabic text, tabs on the right | | |
| 2 | Public | Language switcher | Click EN | Page flips to LTR English | | |
| 3 | Public | Prices hidden when logged out | View Catalog | Each product shows "🔒 Log in to see price", qty + Add are disabled | | |
| 4 | Public | Help tab | Open Help | FAQ entries expand; phone/email/website match Sama's real info | | |
| 5 | Public | Become a distributor | Fill form, attach a PDF/PNG, submit | "Application received" message | | |
| 6 | Auth | OTP request — registered phone | Log in with +962790000000 | Modal shows OTP (dev mode) | | |
| 7 | Auth | OTP request — unknown phone | Try +962700000000 | Error: "Not registered — apply as a distributor" | | |
| 8 | Auth | Wrong OTP | Enter wrong 6-digit code | Error: wrong code | | |
| 9 | Auth | OTP expires | Wait 6+ min then verify | Error: code expired | | |
| 10 | Auth | Log out | Click Log out | Badge disappears, prices hidden again | | |
| 11 | Dashboard | Auto-open after login | Log in as Silver Owner | Dashboard tab is active, shows "Silver 4%" + bar toward "Gold 7%" + "5,000 JOD left" | | |
| 12 | Dashboard | Bronze customer view | Log in as +962790000010 | Tier "Bronze", progress bar toward Silver, "5,000 JOD left" | | |
| 13 | Dashboard | Platinum customer view | Log in as +962790000030 | "You're at the top tier 🎉", no remaining amount | | |
| 14 | Dashboard | Stat cards populated | Any logged-in user | Annual purchases + orders count + orders total all show real numbers | | |
| 15 | Catalog | Member price after login | Silver Owner views Catalog | Each product shows discounted price + struck-through list price | | |
| 16 | Catalog | Different discount per tier | Compare Bronze vs Platinum on same product | Platinum price lower (10% off) than Bronze (no discount) | | |
| 17 | Order | Buyer places order | Log in as +962790000001, add items, submit | Order confirmation with totals; shows in My orders | | |
| 18 | Order | Below min order rejected | Try qty < min_order | Error: below minimum | | |
| 19 | Order | Owner sees buyer's order | Log in as +962790000000, open My orders | Sees buyer's order with "by Buyer" attribution | | |
| 20 | Order | Viewer cannot order | Log in as +962790000002 | Catalog shows prices but the Add button is hidden/disabled; submit returns "view-only" error | | |
| 21 | Team | Owner sees Team tab | +962790000000 logged in | Team tab visible | | |
| 22 | Team | Buyer cannot see Team tab | +962790000001 logged in | Team tab hidden | | |
| 23 | Team | Invite new user | Owner → Add user (name + phone + role buyer) | User appears in list; new phone can OTP-log in | | |
| 24 | Team | Duplicate phone rejected | Invite with an existing phone | Error: phone already in use | | |
| 25 | Team | Disable user | Click Disable on a buyer | Status flips to disabled; that user's next OTP request returns "user_disabled" | | |
| 26 | Push | Subscribe | Click "Enable notifications", accept permission | Browser registers; admin "subscribers" count increases | | |
| 27 | Push | Admin manual send | Admin → Send push (title+body) | Notification appears on the device | | |
| 28 | Push | Tier nudge (manual trigger) | Admin → run-notifications (or wait for cron) | Notification arrives explaining "X JOD left to next tier" | | |
| 29 | Admin | Login | /admin with set password | Admin dashboard loads | | |
| 30 | Admin | Recent orders show business + buyer | View Recent orders card | Each row: `#id — Business · total JOD (status · placed by Name)` | | |
| 31 | Admin | Vendor applications | View Vendor applications card | Pending demo apps + any new submissions show | | |
| 32 | Admin | Sync catalog (no creds) | Click "Sync catalog from SAP/Olive" | Error explaining SAP_SL_*/OLIVE_API_* env vars are required | | |
| 33 | Admin | Clear demo | Admin → Demo data → Clear demo | All [DEMO] businesses, their users, orders, vendor apps removed; products + tiers untouched | | |
| 34 | Admin | Reseed demo | Click Reseed | Same demo set re-created (deterministic) | | |
| 35 | i18n | All UI strings translated | Walk every screen in Arabic, then English | No untranslated keys visible; numbers/currency render correctly | | |
| 36 | Mobile | Phone viewport | Open on an actual phone | Layout fits without horizontal scroll; tap targets ≥ 44px | | |
| 37 | PWA | Add to home screen | iOS Share → Add to Home / Android install prompt | App opens standalone with the Sama logo | | |
| 38 | Performance | First load | Clear cache, load home | Renders in < 3s on 4G | | |
| 39 | Security | Admin endpoints require login | Hit `/api/admin/overview` logged-out | Returns `admin_required` 401 | | |
| 40 | Security | Sub-user scoping | Owner of Business A tries to disable a user from Business B | Returns 404 / not found | | |

## Bugs / observations log

| # | Date | Tester | Screen | Steps to reproduce | Severity | Status |
|---|---|---|---|---|---|---|
| | | | | | | |
