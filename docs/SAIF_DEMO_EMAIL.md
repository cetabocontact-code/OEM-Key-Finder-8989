# Demo email to Mr. Saif (Sama Food Industries)

Fill in `<LIVE_URL>` after Render deploy, attach 2-3 screenshots, hit send.

---

**Subject:** Sama Vendor Connect — quick demo and a few questions before we go live

Dear Mr. Saif,

Thanks for being open to a look. I've put together a working demo of a
client-facing ordering app for Sama Food — built around your real
distributors, your real tier structure, and your real product line from the
export price list you shared. It complements (not replaces) SAP B1 and
Olive — it just lets distributors self-serve their orders at their tier
price and see what they need to buy to move up.

**Live link:** <LIVE_URL>

**Try it in 2 minutes — open the link on your phone:**
- Browse the catalog in Arabic (default) or English. All 8 categories from
  the price list are there: carbonated, sugar-free, fruit juices,
  specialty (Concord grape, lychee, pomelo, salty lime…), RAZ energy, and
  all water sizes including the 5-gallon dispenser.
- Tap **Log in** and enter **+962790000020** (a demo "Royal Restaurant" at
  Gold tier — 7% discount). The OTP shows on screen (no SMS gateway wired
  yet — that's one of the items I'd like to discuss).
- Open **Dashboard** → you'll see the tier badge, a progress bar to
  Platinum, and recent orders.
- Try **Team** to invite another buyer (any phone). Owners manage the team;
  buyers can order; viewers are read-only.
- **Help → Contact us** shows the real Sama address, phones, email, hours.

To see other tiers, log out and try:
- **+962790000010** — Bronze café (no discount yet)
- **+962790000000** — Silver market (4%)
- **+962790000030** — Platinum HoReCa (10%, already top tier)

All demo accounts are clearly tagged `[DEMO]` and can be cleared with one
click before any real customer onboards.

**What I'd love your input on so we can flip this to live data:**
1. **Product prices** — should the per-case prices come from SAP B1 (which
   price list?) or from Olive?
2. **Arabic item names** — where do they live in your system (item master
   foreign name, a user-defined field, …)?
3. **API access** — can your IT team provision read-only credentials for
   either SAP Business One Service Layer or Olive, and confirm whether
   the system is reachable from the public internet (or what VPN we'd need)?
4. **SMS gateway** — do you have a provider in mind (we wire it once and
   OTPs go out by SMS instead of on-screen)?
5. **Annual cycle** — the tier-progress reminders fire 90/60/30 days before
   a customer's anniversary. Should we anchor that to their signup date
   (default), the calendar year, or Sama's fiscal year?

Whenever you're ready I can be on a call to walk it through. Happy to send
a short Loom too if that's easier.

Best,
<YOUR_NAME>

---

## What to attach
Pick 2-3 of these from `/tmp/shots2/` (or re-shoot after the live deploy):
- `catalog_en.png` — Catalog with all 29 Sama products and branded cans.
- `catalog_ar.png` — Same in Arabic, RTL.
- `help_en.png` — Contact card showing all the real info.
- Dashboard screenshot from an earlier run (`/tmp/shots/03_dashboard_owner_en.png`).
