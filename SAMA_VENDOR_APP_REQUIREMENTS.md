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

### Open questions for v1 (being scoped with the user)
- Login method, ordering vs. browse-only, language, pricing/inventory data source.
