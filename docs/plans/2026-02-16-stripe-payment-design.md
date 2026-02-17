# Stripe Payment Integration — Phase 1 Design

## Overview

Add pay-at-order payment via Stripe Payment Element. Customers must pay before their order reaches the kitchen. All payment methods (cards, Apple Pay, Google Pay, PayPal) are handled by Stripe — no sensitive payment data touches our server.

Phase 2 (customer accounts + saved payment methods) is out of scope.

## Order Flow (Revised)

```
confirmation screen → "Place Order"
  → POST /api/order/{slug}/create-payment/
  → Backend: validate items, calculate totals, create Order (status: pending_payment),
    create Stripe PaymentIntent, return client_secret
  → Frontend: transition to "payment" step, render Stripe Payment Element
  → Customer completes payment
  → Stripe webhook (payment_intent.succeeded)
  → Backend: update order to "confirmed", payment_status to "paid", broadcast to kitchen
  → Frontend: transition to "submitted" step
```

Step flow: `welcome → input → loading → confirmation → payment → submitted`

## Backend Changes

### Order Model — New Fields

- `payment_status`: CharField with choices `pending`, `paid`, `failed`, `refunded` (default: `pending`)
- `stripe_payment_intent_id`: CharField, nullable, stores Stripe PaymentIntent ID (e.g., `pi_xxx`)
- New `status` choice: `pending_payment` (added before `confirmed`)

### New Endpoints

#### POST `/api/order/{slug}/create-payment/`

Request body: same as current `confirm/` endpoint (items, raw_input, table_identifier, language).

Behavior:
1. Validate restaurant exists
2. Validate order items against database (menu items, variants, modifiers)
3. Calculate prices server-side (subtotal, tax, total)
4. Create Order with `status="pending_payment"`, `payment_status="pending"`
5. Create Stripe PaymentIntent for the total amount (in cents)
6. Store `stripe_payment_intent_id` on the Order
7. Return `{ order_id, client_secret, ...order details }`

#### POST `/api/webhooks/stripe/`

Receives Stripe webhook events. Verifies signature using `STRIPE_WEBHOOK_SECRET`.

On `payment_intent.succeeded`:
1. Look up Order by `stripe_payment_intent_id`
2. Set `status = "confirmed"`, `payment_status = "paid"`
3. Broadcast order to kitchen via WebSocket

On `payment_intent.payment_failed`:
1. Look up Order by `stripe_payment_intent_id`
2. Set `payment_status = "failed"`

### Removed/Changed Endpoints

The existing `POST /api/order/{slug}/confirm/` endpoint's validation and calculation logic moves into `create-payment/`. The old endpoint can be removed.

### New Backend Dependencies

- `stripe` Python package

### New Environment Variables

- `STRIPE_SECRET_KEY` — for creating PaymentIntents
- `STRIPE_WEBHOOK_SECRET` — for verifying webhook signatures

## Frontend Changes

### New Step: `payment`

Added to `OrderStep` type and order store. Sits between `confirmation` and `submitted`.

### Order Store Changes

- Add `clientSecret: string | null` to store state
- Add `setClientSecret` action
- Add `"payment"` to `OrderStep` union type

### ConfirmationStep Changes

"Place Order" button calls `create-payment/` instead of `confirm/`. On success:
- Store the `client_secret` in the order store
- Transition to `"payment"` step

### New PaymentStep Component

- Initializes Stripe with `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`
- Wraps payment form in Stripe `<Elements>` provider with the `client_secret`
- Renders `<PaymentElement>` (automatically shows card, Apple Pay, Google Pay, PayPal)
- On success: transitions to `"submitted"` step
- On failure: shows error inline, allows retry

### New Frontend Dependencies

- `@stripe/stripe-js`
- `@stripe/react-stripe-js`

### New Environment Variables

- `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` — Stripe publishable key

## Edge Cases

| Scenario | Handling |
|---|---|
| Payment fails | Stripe shows error inline. Customer retries. Order stays `pending_payment`. |
| Customer abandons | Order stays `pending_payment`. Kitchen never sees it. Cleanup job can expire stale orders later. |
| Webhook before frontend callback | No issue. Kitchen gets the order. Frontend transitions on its own callback. |
| Frontend success but no webhook yet | Frontend shows success optimistically. Kitchen broadcast only on webhook (source of truth). |
| Double payment | Prevented by Stripe. Each PaymentIntent can only be paid once. |

## Payment Methods

All handled by Stripe Payment Element with zero additional frontend code:
- Credit/debit cards
- Apple Pay (on supported devices/browsers)
- Google Pay (on supported devices/browsers)
- PayPal (enabled in Stripe Dashboard)
