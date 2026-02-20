# Monetization Design: QR Order SaaS Pricing

**Date:** 2026-02-20
**Status:** Draft

## Context

QR Order is a SaaS platform for restaurants that enables AI-powered, QR-code-based ordering. Customers scan a QR code, speak or type their order in any language, and the AI parses it into structured menu items. The system handles payments via Stripe and provides real-time kitchen order management.

### Target Customer

Small independent restaurants (1-3 locations, limited tech budget, owner-operated).

### Primary Value Proposition

1. **Labor savings** - run with fewer front-of-house staff or redeploy staff to other tasks.
2. **Faster table turnover** - customers order and pay faster, more covers per shift.

### Key Constraints

- Restaurant owners are the paying customer, not diners.
- Small operators need predictable monthly costs.
- LLM API costs (GPT-4o-mini) run approximately $0.01-0.03 per order parse.
- Go-to-market is direct outreach + free trial.

## Pricing Model: Tiered Subscription + Overage

Flat monthly subscription with a base order allocation per tier. All features are available on every tier - tiers differ only by order volume and overage rate.

### Why This Model

- **Flat base = predictable cost.** Small owners can budget for a fixed monthly number.
- **Overage rate protects margins.** LLM costs scale with usage; overage charges ensure high-volume restaurants don't erode margins.
- **No feature gating.** Every restaurant gets the full product (AI parsing, voice input, kitchen dashboard, multilingual support, saved payment methods). This keeps the product simple and avoids frustrating "upgrade to unlock" friction.
- **Per-transaction-only pricing was rejected** because it creates unpredictable bills and discourages restaurants from going all-in on the platform.

### Tier Structure

| Tier | Monthly Price | Included Orders/mo | Overage Rate | Typical Use Case |
|---|---|---|---|---|
| **Starter** | $49/mo | 200 | $0.20/order | Small cafe, ~7 orders/day |
| **Growth** | $99/mo | 600 | $0.15/order | Typical independent, ~20 orders/day |
| **Pro** | $199/mo | 1,500 | $0.10/order | Busy restaurant, ~50 orders/day |

**Overage handling: soft cap with alerts.**
- Email/SMS notification at 80% and 100% of order allocation.
- Orders continue processing beyond the cap (no disruption to service).
- Overages are billed at end of month.

### Annual Discount

17% discount (~2 months free) for annual prepayment.

| Tier | Monthly | Annual (per month) | Annual Total |
|---|---|---|---|
| **Starter** | $49/mo | $40/mo | $480/yr |
| **Growth** | $99/mo | $82/mo | $984/yr |
| **Pro** | $199/mo | $166/mo | $1,992/yr |

## Free Trial

- **Duration:** 14 days.
- **Allocation:** 200 orders (Starter-equivalent).
- **No credit card required** upfront - removes friction for direct outreach.
- **All features available** during trial.

### Post-Trial Behavior

- AI order parsing stops (QR codes and static menu remain accessible).
- Owner sees a "trial ended" screen with one-click upgrade.
- Personal follow-up from sales (direct outreach model).

## Unit Economics (Per Tier)

Assumes GPT-4o-mini at ~$0.02 average per order parse.

| Tier | Revenue | Max LLM Cost (at cap) | Gross Margin (at cap) |
|---|---|---|---|
| **Starter** | $49 | $4 | ~92% |
| **Growth** | $99 | $12 | ~88% |
| **Pro** | $199 | $30 | ~85% |

Overage orders are also profitable: $0.10-0.20 charge vs. $0.02 cost = 80-90% margin on overages.

## Future Expansion Levers (Not Now)

These are deliberate non-goals for launch but worth revisiting as the business grows:

1. **Multi-location discount.** 10-20% off per additional location for small chains.
2. **Enterprise/custom tier.** For 50+ orders/day restaurants. Custom pricing, dedicated support, SLA.
3. **Add-on modules.** Analytics dashboards, marketing tools, POS integrations priced separately.
4. **Payment processing markup.** Small markup (0.5-1%) on top of Stripe fees. Common in restaurant SaaS but risks eroding trust with small operators.

## Explicitly Avoided

- **Setup fees.** Kills conversion with price-sensitive small operators.
- **Per-table pricing.** Feels nickel-and-dime.
- **Commission on order value.** Misaligns incentives (platform benefits from higher prices, restaurant doesn't).
- **Feature gating between tiers.** Adds complexity and frustration without meaningful revenue benefit at this stage.

## Competitive Reference

| Competitor | Model | Price Range |
|---|---|---|
| Owner.com | Flat monthly | $499/mo + 5% customer fee |
| Orderlina (QR ordering) | Flat monthly | ~$49/mo per location |
| Toast (full POS) | Tiered | $0-$69/mo base + per-order fees |
| Square for Restaurants | Tiered | $0-$60/mo + processing fees |
| ChowNow, Olo | Flat monthly | $99-$199/mo |

QR Order is positioned in the $49-$199/mo range, comparable to mid-range ordering platforms, with AI multilingual parsing as the key differentiator.
