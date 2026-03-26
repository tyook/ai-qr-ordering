# POS System Integration Design

**Date:** 2026-03-27
**Status:** Draft

## Problem

QR orders that don't appear in the restaurant's POS system create split operations, broken financial reporting, inventory drift, and tax compliance gaps. This blocks serious restaurant adoption of the platform.

## Goals

- Inject confirmed QR orders into the restaurant's existing POS system so they appear alongside server-entered orders
- Support the most common small-restaurant POS systems (Square, Toast) with direct integrations
- Cover long-tail POS systems via a middleware platform
- Provide a functional fallback for restaurants without a modern POS
- Never block the diner's ordering experience due to POS integration failures

## Non-Goals

- Menu sync (pulling menus from POS into the platform)
- Inventory sync
- POS-side reporting dashboards
- Replacing the restaurant's POS system

## Target Segment

Small/independent restaurants (1-5 locations) initially, expanding to mid-market and enterprise over time.

---

## Architecture Overview

A new Django app called `integrations` sits between the existing order flow and external POS systems. It operates as an async post-order hook: after an order is confirmed (and optionally paid via Stripe), it is dispatched to the POS in the background via Celery. Failure never blocks the order.

### Order Flow With POS Integration

```
Diner submits order
  -> Order created in DB (status=confirmed or pending_payment)
  -> Payment collected (Stripe or deferred to POS)
  -> Kitchen WebSocket broadcast (existing, unchanged)
  -> POS dispatch triggered (new, async via Celery)
      -> Route to correct handler:
          1. Direct adapter (Square/Toast) if available
          2. Middleware (Deliverect/Otter) as fallback
          3. No POS configured -> skip (kitchen display only)
      -> On success: record external_order_id on Order
      -> On failure: retry with backoff, flag for manual attention
```

### Key Architectural Decisions

- **Dual display:** Orders go to both the platform's kitchen WebSocket display and the POS simultaneously. Restaurants choose which screen to use.
- **Celery for async dispatch:** POS sync is fire-and-forget from the order flow's perspective. This aligns with the payout system design which already plans for Celery + django-celery-beat.
- **Adapter pattern:** A `BasePOSAdapter` abstract class with standard methods. Each POS vendor implements this interface.
- **Restaurant-level configuration:** Each restaurant chooses their POS type, authenticates via OAuth, and configures payment handling preference.

### New Django App Structure

```
backend/integrations/
  ├── models.py          # POSConnection, POSSyncLog
  ├── adapters/
  │   ├── base.py        # BasePOSAdapter
  │   ├── square.py      # SquareAdapter
  │   ├── toast.py       # ToastAdapter
  │   └── middleware.py   # Generic middleware adapter
  ├── services.py        # dispatch_to_pos(), retry logic
  ├── tasks.py           # Celery tasks
  ├── views.py           # OAuth callback endpoints, sync management
  ├── urls.py
  └── admin.py
```

---

## Data Models

### POSConnection

Stores a restaurant's POS integration configuration. One restaurant has at most one active POS connection.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID, PK | Primary key |
| restaurant | FK -> Restaurant, unique | One connection per restaurant |
| pos_type | Enum: square, toast, middleware, none | Which POS system |
| is_active | Bool, default=True | Whether integration is live |
| payment_mode | Enum: stripe, pos_collected | Who handles payment |
| oauth_access_token | Encrypted text | Access token (encrypted at rest) |
| oauth_refresh_token | Encrypted text | Refresh token (encrypted at rest) |
| oauth_token_expires_at | Datetime, nullable | Token expiry |
| external_location_id | String, nullable | Square location ID, Toast restaurant GUID, etc. |
| middleware_config | JSON, nullable | Vendor-specific config for middleware integrations |
| created_at | Datetime | Record creation |
| updated_at | Datetime | Last update |

**Notes:**
- OAuth tokens are encrypted at rest using manual Fernet wrapping via Python's `cryptography.fernet` module (the `django-fernet-fields` package is unmaintained). The Fernet encryption key is stored in an environment variable (`POS_ENCRYPTION_KEY`), not in the database. Key rotation: generate a new key, re-encrypt all tokens, swap the env var.
- `external_location_id` is required because most POS systems are multi-location.
- `payment_mode` drives payment flow branching: `stripe` means pay via Stripe and mark as paid externally in POS; `pos_collected` means skip Stripe and let the POS handle payment.

### POSSyncLog

Tracks every attempt to push an order to a POS. Used for debugging, retry logic, and the dashboard sync status view.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID, PK | Primary key |
| order | FK -> Order | The order being synced |
| pos_connection | FK -> POSConnection | Which POS connection was used |
| status | Enum: pending, success, failed, retrying, manually_resolved | Current sync state |
| external_order_id | String, nullable | Order ID in the POS system (set on success) |
| attempt_count | Int, default=0 | Number of push attempts |
| last_error | Text, nullable | Most recent error message |
| next_retry_at | Datetime, nullable | When the next retry is scheduled |
| created_at | Datetime | Record creation |
| updated_at | Datetime | Last update |

### Changes to Existing Order Model

Add `pos_collected` to the existing `payment_status` choices (currently: `pending`, `paid`, `failed`, `refunded`). This new value means "payment is handled by the restaurant's POS, not Stripe."

**Payout system interaction:** Orders with `payment_status = 'pos_collected'` must be excluded from the daily Stripe payout job, since Stripe never collected the funds. The payout system already filters on `payment_status = 'paid'`, so this works correctly by default — but this exclusion should be explicitly tested.

Two new fields on `Order`:
- `external_order_id` (String, nullable, blank=True) — Denormalized from POSSyncLog for quick access.
- `pos_sync_status` (Enum: not_applicable, pending, synced, retrying, failed, manually_resolved, default=not_applicable) — Quick status indicator without joining to POSSyncLog.

**Migration:** Existing orders receive `pos_sync_status = 'not_applicable'` and `external_order_id = NULL` as defaults. This is safe since no POS integration exists prior to this feature.

---

## Adapter Interface

### BasePOSAdapter

```python
class BasePOSAdapter(ABC):
    def __init__(self, connection: POSConnection): ...

    @abstractmethod
    def push_order(self, order: Order) -> PushResult:
        """Push order to POS. Returns external_order_id on success."""

    @abstractmethod
    def cancel_order(self, external_order_id: str) -> bool:
        """Cancel a previously pushed order (e.g., for refunds)."""

    @abstractmethod
    def get_order_status(self, external_order_id: str) -> str:
        """Check order status in POS (for reconciliation)."""

    @abstractmethod
    def validate_connection(self) -> bool:
        """Test that OAuth credentials are still valid."""

    @abstractmethod
    def refresh_tokens(self) -> bool:
        """Refresh expired OAuth tokens."""
```

```python
@dataclass
class PushResult:
    success: bool
    external_order_id: str | None
    error_message: str | None
```

### Square Adapter (Priority 1)

**Why first:** Largest US POS market share for small restaurants. Excellent developer docs, fast app approval, well-designed OAuth and Orders API.

**Key mappings:**
- `Order` -> Square `CreateOrder` API
- `OrderItem` -> Square `OrderLineItem`
- `MenuItemVariant` price -> `base_price_money`
- `MenuItemModifier` -> `OrderLineItemModifier`
- Stripe payment -> Square `tender` of type `OTHER` with note "Paid via [platform]"
- POS-collected mode -> Push order without tender, Square handles payment

**OAuth:** Restaurant clicks "Connect Square" -> redirects to Square OAuth -> callback stores tokens + prompts location selection.

### Toast Adapter (Priority 2)

**Why second:** Dominant in full-service restaurants. API is more complex and requires a Toast partner application (4-8 week approval process).

**Key differences from Square:**
- Uses a restaurant GUID rather than location ID
- Order creation via `orders` API with `externalReferenceId`
- External payments marked via `paidExternally: true` on the check
- Longer partner approval timeline

### Middleware Adapter (Fallback)

A single adapter that speaks to a middleware platform. Covers the long tail of POS systems: Clover, Lightspeed, TouchBistro, Revel, etc.

**Vendor selection:** The specific middleware vendor (Deliverect, Otter, or ItsaCheckmate) must be evaluated and chosen as a prerequisite task before implementing this adapter. Evaluation criteria: POS coverage breadth, per-order pricing, API quality, and support for "paid externally" order status. The adapter interface is vendor-agnostic, so the `BasePOSAdapter` contract applies regardless of which vendor is selected.

**Key differences:**
- OAuth is with the middleware, not each POS vendor
- Order format follows the middleware's standardized schema
- Restaurant connects their POS to the middleware via the middleware's own dashboard
- Less control over error messages and edge cases

---

## Async Dispatch & Retry Logic

### Celery Task Flow

When an order reaches a terminal "ready to dispatch" state, a Celery task is enqueued. The dispatch is triggered from three code paths:

1. **POS-collected mode:** `ConfirmOrderView` (line 33) — immediately after order creation with `status=confirmed`, since there's no payment step.
2. **Stripe mode (inline payment):** `CreatePaymentView` (line 72) — after successful inline PaymentIntent confirmation (when `status` transitions from `pending_payment`).
3. **Stripe mode (async payment):** `ConfirmPaymentView` (line 166) and the Stripe webhook handler in `StripeWebhookView` (line 201) — after payment confirmation.

All three paths call `dispatch_order_to_pos.delay(order_id)` after the order is confirmed and (if applicable) paid.

```
Order reaches dispatch-ready state
  -> dispatch_order_to_pos.delay(order_id)
  -> Task checks: does this restaurant have an active POSConnection?
      -> No  -> Set pos_sync_status = "not_applicable", done
      -> Yes -> Create POSSyncLog(status=pending)
             -> Route to correct adapter
             -> Call adapter.push_order(order)
             -> Success -> POSSyncLog(status=success), Order(pos_sync_status=synced)
             -> Failure -> POSSyncLog(status=retrying), schedule retry
```

### Retry Strategy

Exponential backoff with a cap:

| Attempt | Delay | Cumulative |
|---------|-------|------------|
| 1 | Immediate | 0 |
| 2 | 30 seconds | 30s |
| 3 | 2 minutes | 2.5 min |
| 4 | 10 minutes | 12.5 min |
| 5 | 30 minutes | 42.5 min |

After 5 failed attempts:
- `POSSyncLog.status` -> `failed`
- `Order.pos_sync_status` -> `failed`
- Notification surfaced in the restaurant dashboard

### Token Refresh Handling

If an adapter call fails with a 401/auth error:
1. Call `adapter.refresh_tokens()`
2. If refresh succeeds -> retry `push_order` immediately (doesn't count as a retry attempt)
3. If refresh fails -> set `POSConnection.is_active = False`, surface a "reconnect your POS" alert

### Cancel/Refund Sync

When an order is refunded:
- If `external_order_id` exists -> enqueue `cancel_pos_order.delay(order_id)`
- Adapter calls `cancel_order()` on the POS
- Best-effort: if POS cancel fails, log it but don't block the refund

---

## Payment Mode Branching

### Mode: Stripe (payment_mode = "stripe")

The current flow with POS sync added:

```
Diner places order
  -> Order created (status=pending_payment)
  -> Stripe PaymentIntent created -> diner pays
  -> Payment confirmed -> Order status=confirmed
  -> Kitchen WebSocket broadcast
  -> POS dispatch: order pushed with "paid externally" flag
```

The POS receives a completed, paid order. No payment action needed on the POS side.

### Mode: POS-Collected (payment_mode = "pos_collected")

Stripe is skipped entirely:

```
Diner places order
  -> Order created (status=confirmed, payment_status=pos_collected)
  -> Kitchen WebSocket broadcast
  -> POS dispatch: order pushed WITHOUT payment/tender
  -> Restaurant collects payment via their POS terminal
```

**Changes to existing order flow:**
- `ConfirmOrderView` (`POST /api/order/<slug>/confirm/`, views.py line 33) gains awareness of payment mode. When the restaurant's `POSConnection.payment_mode = 'pos_collected'`, this endpoint creates the order with `status=confirmed` and `payment_status=pos_collected`, bypassing the `CreatePaymentView` / `ConfirmPaymentView` flow entirely.
- New `payment_status` value: `pos_collected` (added to Order model choices).
- Frontend: the existing `GET /api/order/<slug>/menu/` (`PublicMenuView`) adds a `payment_mode` field to the response. If `pos_collected`, the frontend skips the Stripe payment UI and shows "Your order has been sent. Please pay at the counter."

No POS connection details are exposed to the public endpoint.

---

## Restaurant Dashboard — POS Sync Management

### POS Settings Page

Located at `/account/restaurants/[id]/settings/integrations`.

**Connection status panel:**
- Current POS type + connection status (connected/disconnected)
- "Connect [Square/Toast]" or "Connect via Middleware" button (initiates OAuth)
- "Disconnect" button
- Payment mode toggle: Stripe vs. POS-collected
- Location selector (populated after OAuth, for multi-location accounts)

### POS Sync Status Page

Located at `/account/restaurants/[id]/orders/sync` (or as a tab on the orders page).

**Summary bar:**
- Count of failed syncs (red badge)
- Count of pending/retrying syncs
- "Retry All Failed" button — enqueues a Celery task that re-dispatches all failed orders for the restaurant

**Sync log table:**

| Column | Description |
|--------|-------------|
| Order # | Link to order detail |
| Order Date | When the order was placed |
| Sync Status | pending / synced / retrying / failed / manually_resolved |
| POS Order ID | External ID (shown on success) |
| Attempts | Count of push attempts |
| Last Error | Truncated error message, expandable |
| Actions | "Retry" button (per-order), "Mark Resolved" button |

**"Mark Resolved"** sets `pos_sync_status = manually_resolved` for orders the restaurant manually entered into their POS.

### API Endpoints

```
# POS Connection management
POST   /api/restaurants/<id>/pos/connect/             # Initiate OAuth
GET    /api/restaurants/<id>/pos/connection/           # Get connection status
DELETE /api/restaurants/<id>/pos/connection/           # Disconnect
PATCH  /api/restaurants/<id>/pos/connection/           # Update payment_mode, location

# OAuth callbacks (public, validated via state param)
GET    /api/integrations/oauth/square/callback/
GET    /api/integrations/oauth/toast/callback/

# Sync management
GET    /api/restaurants/<id>/pos/sync-logs/            # List sync logs (filterable)
POST   /api/restaurants/<id>/pos/retry-all/            # Retry all failed syncs
POST   /api/restaurants/<id>/pos/retry/<order_id>/     # Retry single order
PATCH  /api/restaurants/<id>/pos/sync-logs/<id>/       # Mark as manually_resolved
```

---

## Receipt Printer Fallback

For restaurants without a modern POS or middleware-compatible system.

### Approach: Manual Print Button on Kitchen Display

The kitchen WebSocket display (`/kitchen/[slug]`) already receives orders in real-time. Add a **"Print" button** on each order card:

- Clicking "Print" opens the browser's print dialog with a print-optimized CSS layout (thermal receipt format: narrow, no margins, large text)
- The kitchen tablet/computer connects to a thermal printer via USB or network
- Uses `window.print()` which requires a user gesture (click) — fully supported across all browsers

**Note:** Fully automatic printing (no click required) is not possible via standard browser APIs, as `window.print()` requires a user-initiated event. If auto-print is needed in the future, options include a dedicated Electron kiosk app or direct ESC/POS integration via the Web Serial API. These are out of scope for the initial implementation.

### Print Format

```
================================
[Restaurant Name]
ORDER #1234
Table: 5
Time: 2:35 PM
================================
2x  Iced Coffee (Large)
    + Extra shot
1x  Croissant
--------------------------------
Special: No nuts (allergy)
================================
Payment: Paid via Stripe
         (or: Pay at counter)
================================
```

### Why Not Direct Printer Integration?

ESC/POS protocols require either a local agent on the restaurant's network or a cloud printing service (e.g., Star CloudPRNT). Both add significant complexity. The browser print approach works today with zero additional infrastructure. Direct printer integration can be a future enhancement if demand warrants it.

---

## Infrastructure Dependencies

- **Celery + django-celery-beat:** Shared with the payout system design. Required for async POS dispatch and retry scheduling.
- **cryptography (Python package):** For Fernet encryption of OAuth tokens at rest. Already a transitive dependency of many packages; add as explicit dependency.
- **Square SDK:** `squareup` Python package for Square API.
- **Toast API client:** HTTP client (no official Python SDK; use `httpx`).
- **Middleware SDK:** Depends on chosen vendor (evaluation is a prerequisite task; see Middleware Adapter section).

## Launch Order

1. **Square adapter** — Largest market share, fastest to build and get approved
2. **Toast adapter** — Start partner application early (4-8 week approval), build adapter in parallel
3. **Middleware fallback** — Evaluate Deliverect vs. Otter, integrate
4. **Receipt printer fallback** — Browser-based print button on kitchen display

Work streams 1 and 2 can partially overlap (Toast partner application submitted while building Square adapter). Work stream 4 is independent and can be built at any time.

---

## Future Considerations (Out of Scope)

These are explicitly deferred and not part of this design:

- **POS webhooks (inbound):** Square and Toast support webhooks for order status updates (e.g., order completed on POS side). Bidirectional status sync could be added later.
- **Rate limiting:** Square has rate limits (~1000 req/10s per location). During dinner rushes, adapter implementations should be aware of this. Specific rate-limit handling is an implementation detail.
- **Internal alerting:** POSSyncLog handles per-restaurant visibility. Engineering-level alerting (e.g., if POS failure rate spikes across restaurants, indicating an API outage) is an operational concern to address during deployment.
- **Auto-print via Electron/ESC/POS:** Direct printer integration for fully automatic printing without user interaction.
