# Sama Food Industries — Vendor App Requirements

> Working notes for the vendor connection + push-notification web app.
> Company: Sama Food Industries (manufacturer of water, juice, soda drinks, and more).
> Website: https://samafood.jo/

## Core concept
- Connect more directly with vendors.
- Ease order processing and agreed pricing between Sama Food and its vendors.

## Push notifications (key feature)
- Send pop-up push notifications to vendors' phones.
- Announce weekly and monthly offers (e.g. "buy 10 get 5 free").

## Delivery dispatch to online marketplaces
- Ability to dispatch the job/delivery to online marketplaces to get a lower delivery price.
- Requirements to dispatch a delivery job:
  - Job requirements (details of the delivery to be performed).
  - Insurance.
  - A 2-minute application/onboarding flow on the Sama app.

## Pricing & sales agents
- Introduce sales agents who negotiate deals at different levels.
- Goal: maintain **cost + an agreed percentage** (percentage set with the board).
- Objective: capture as much market demand as possible.

## Executive input (Sama Food manager)

### Existing systems (already in use — do NOT replace)
- **SAP Business One** — used for accounting.
- **Olive** — used by the sales team for ~6 years; they love it. Handles:
  - Access to all offers and inventory.
  - GPS / route tracking for distribution vans.
  - Invoicing — prints invoices/cash receipts for cash vans and distribution vans.
- The new app is **complementary** to these, not a replacement. The sales team keeps Olive; the new app is **client-facing**.

### v1 direction (what the executive wants first)
- A **client-facing web app** where clients log into their own accounts.
- Clients see **tiered pricing/discounts** based on their **yearly spend agreement**, e.g.:
  - 0 – 10K spend → 0% discount
  - 10K – 20K → ~4% discount
  - (continues up by client size)
- Discount tier is driven by the size/yearly agreement of the client.
- **Vendor application**: prospective clients can apply to become a vendor by **uploading certain documents** (specific document list TBD from executive).
- **Push notifications** to notify clients of **current rates** and offers (offers already flow through the distributor vans today).

### v1 decisions (confirmed with user)
- Clients can: browse catalog + see tier price, place orders in-app, receive push notifications, apply to become a vendor.
- Login: **phone + OTP**.
- Languages: **Arabic primary (RTL) + English** toggle.
- Product/price/stock data source: **integrate SAP B1 / Olive** (adapter built; live sync pending credentials).

### Confirmed product packaging (from Sama)
- Water 200 ml — case of 24
- Water 330 ml — case of 12
- Water 600 ml — case of 12
- Water 1.5 L — case of 6
- Water 5-gallon dispenser jug
- Juice, soda (12/24 packs), and **Raz Energy** line (specs vary — confirm)

### Company contacts (verify these are Sama Food Industries, Amman, JO)
- Phone: +962 6 405 9090 / +962 6 405 9080
- Email: Info@Samafood.jo
- Website: https://samafood.jo/

---

## What to ask Sama's developer (for the integrations)

The app is built and runnable; these credentials/specs switch on the live
pieces. Give the developer this list:

**1. SAP Business One (accounting) — Service Layer access**
- Is the Service Layer enabled and reachable? What is its base URL? (e.g. `https://<host>:50000/b1s/v1`)
- The **CompanyDB** name.
- A **service/integration user** + password (read access to Items, prices, stock; and—if we later push orders—write access to draft Sales Orders).
- Which **price list** maps to our base price, and where item barcodes/Arabic names live.

**2. Olive (sales/inventory) — API access**
- Does Olive expose an **API or data export**? If yes: base URL, an **API key/token**, and the **endpoint + field names** for products, prices, stock, and offers.
- If there is no API: can we get a **scheduled export** (CSV/Excel) of the catalog and stock instead?
- How are **client price tiers / yearly-agreement discounts** stored today — can we read them?

**3. OTP / SMS gateway (for phone login)**
- Which **SMS provider** does Sama use in Jordan (e.g. Unifonic, local aggregator, Twilio)?
- API credentials (account SID / API key + sender ID/short code) and whether the sender ID is **registered/approved** for Jordan.

**4. Hosting / domain**
- A subdomain to host it under (e.g. `vendors.samafood.jo` or `orders.samafood.jo`) and DNS access, since push notifications require HTTPS.

---

## Build vs. buy (factory, bulk B2B) — recommendation
- Sama already owns the hard parts: **Olive** (sales, inventory, GPS, invoicing) and **SAP B1** (accounting). The gap is a **client-facing ordering + offers + push** layer on top.
- **Build (this app):** lightweight, branded, bilingual, no per-seat SaaS fees, integrates straight into SAP/Olive. Best if we want full control and the scope stays focused. (Chosen for v1.)
- **Buy (B2B commerce SaaS):** options that fit bulk/wholesale distributors —
  - **Pepperi**, **REPZO** (MENA-focused van-sales/B2B), **B2B Wave**, **Orderwerks**, **Now Commerce** — purpose-built B2B ordering portals with tier pricing.
  - **Shopify B2B / Plus** — strong storefront, weaker on van-sales/credit-terms nuance.
  - **Push** via these usually needs an add-on (OneSignal/Firebase) anyway.
  - Trade-off: faster to launch but recurring fees, less control, and SAP/Olive integration still has to be built or paid for.
- **Reusable libraries we already lean on** (so we're not reinventing): Flask, SQLite, **pywebpush** (Web Push), **Firebase Cloud Messaging / OneSignal** (drop-in push if we outgrow self-hosted Web Push), and the **SAP B1 Service Layer** + Olive APIs for data — no need to build catalog/inventory from scratch once connected.
