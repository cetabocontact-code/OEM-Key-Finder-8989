# Future ideas — parked for after launch

Notes captured during build; not part of the current scope. Each one needs
Sama's approval before we wire it.

## Referral program for Sama employees
Once the app is live and a baseline of distributor orders is flowing,
introduce a referral system where **current Sama employees can refer new
distributors and earn a small commission on each subsequent order**, on a
clear, capped formula.

**Open decisions to confirm with Saif before building:**
- Commission rate (flat JOD per order? % of order value? % of margin?).
- Caps: per-order ceiling, per-month ceiling, vesting period.
- Eligibility: which employee roles can refer; can a sales rep refer their
  own customer.
- Attribution: referral code vs. manual link by admin; how long the
  attribution window lasts.
- Payout cadence (monthly with payroll?) and approval workflow.
- Tax/HR treatment in Jordan.

**Rough implementation sketch (when greenlit):**
- `referrals` table: `id, employee_id, business_id, code, status, created_at`.
- `referral_payouts` table: order_id → commission_amount, status, paid_at.
- Vendor application form gets an optional "Referral code" field.
- Cron job (extends `samafood.notify`) computes earned commissions from
  newly settled orders, writes to `referral_payouts`.
- Employee-facing view (or weekly email) listing referred businesses + earned-to-date.
- Admin override to disqualify/reverse on chargebacks.

Keep the policy doc in this repo (`docs/REFERRAL_POLICY.md`) once approved,
so the rules and the code stay in lockstep.
