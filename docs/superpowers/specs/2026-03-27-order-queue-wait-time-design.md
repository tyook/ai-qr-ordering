# Order Queue & Estimated Wait Time

## Overview

Enable customers to see restaurant busyness before placing an order and track their queue position with estimated wait time after ordering. This addresses the core UX challenge of a QR ordering system that accepts orders from customers outside the restaurant, where high volume and long waits are expected.

## Requirements

- **Pre-order**: Display a traffic light busyness indicator (green/yellow/red) with estimated wait on the ConfirmationStep
- **Post-order**: Display a progress bar (Confirmed → Preparing → Ready → Completed), queue position, and estimated wait on the SubmittedStep
- **Real-time updates**: WebSocket push with polling fallback for post-order tracking
- **Wait time calculation**: Owner-configured estimate initially, switch to historical averages after 50 completed orders

## Architecture: Computed Queue (No New Model)

Queue position and wait time are computed on-the-fly from existing Order data. No new queue model — the Order model's `confirmed_at` timestamp and status fields naturally define queue ordering. Historical averages and busyness levels are cached in Redis, refreshed by a Celery periodic task.

### Order status handling

The existing Order model has statuses: `pending_payment`, `pending`, `confirmed`, `preparing`, `ready`, `completed`. In practice, `create_order()` defaults to `confirmed` status, and the payment flow goes `pending_payment → confirmed`. The `pending` status is not actively used in the current codebase.

**Queue scope**: Only orders with status `confirmed` or `preparing` are counted in the queue. Orders in `pending_payment`, `pending`, `ready`, or `completed` are excluded. Order cancellation is out of scope for v1.

## Data Model Changes

### Order model additions (`backend/orders/models.py`)

| Field | Type | Description |
|-------|------|-------------|
| `confirmed_at` | DateTimeField, nullable | Set when status moves to `confirmed` |
| `preparing_at` | DateTimeField, nullable | Set when status moves to `preparing` |
| `ready_at` | DateTimeField, nullable | Set when status moves to `ready` |
| `completed_at` | DateTimeField, nullable | Set when status moves to `completed` |

These timestamps power historical wait time calculations. They must be set in **all code paths** that change order status — not just `update_order_status()`. Specifically:
- `create_order()` — defaults to `confirmed` status, so must set `confirmed_at` when `order_status="confirmed"`
- `update_order_status()` — for kitchen-driven status changes (confirmed → preparing → ready → completed)
- `confirm_payment()` and `_handle_payment_succeeded()` in `services.py` — these set status to `confirmed` directly, so they must also set `confirmed_at`

A helper function `set_status_timestamp(order, status)` centralizes this logic.

### Restaurant model additions (`backend/restaurants/models.py`)

| Field | Type | Description |
|-------|------|-------------|
| `estimated_minutes_per_order` | PositiveIntegerField, default=10 | Owner-configurable fallback estimate |

No persistent `use_historical_estimates` flag — `QueueService` checks the count of completed orders (from cache) at query time to decide which estimate source to use. This avoids a DB write and potential sync issues.

### Redis cached values (per restaurant)

| Key | Description |
|-----|-------------|
| `queue:{slug}:avg_prep_time` | Rolling average minutes from confirmed → ready |
| `queue:{slug}:active_count` | Count of orders in confirmed/preparing status |
| `queue:{slug}:busyness` | Computed traffic light level (green/yellow/red) |
| `queue:{slug}:completed_count` | Total completed orders (for threshold check) |

All Redis keys use a TTL of 10 minutes (slightly longer than the 5-minute refresh interval) so stale values auto-expire if the Celery task fails.

## QueueService (`backend/orders/queue_service.py`)

### Methods

- **`get_queue_position(order)`** — Counts orders for that restaurant with status in (`confirmed`, `preparing`) and `confirmed_at` before this order's `confirmed_at`. Uses `confirmed_at` (not `created_at`) to reflect actual queue entry time — orders that pay faster enter the queue first. Orders with NULL `confirmed_at` are excluded from the count. Returns 1-based integer position.

### Data migration

A one-time migration backfills `confirmed_at = created_at` for all existing orders in `confirmed` or `preparing` status. This ensures the queue is populated correctly at deployment time for restaurants with in-flight orders.

- **`get_estimated_wait(restaurant, queue_position)`** — If cached completed order count >= 50, uses cached `avg_prep_time * queue_position`. Otherwise, uses `estimated_minutes_per_order * queue_position`. Returns minutes as integer. Note: this is a known simplification that treats orders as sequential. Kitchens process orders in parallel, so actual wait times will be shorter. This is acceptable for v1 — estimates are conservative, and historical averages will naturally account for parallelism once enough data exists.

- **`get_busyness(restaurant)`** — Reads cached `active_count` and estimated wait, using **estimated wait as the primary signal**:
  - **Green**: < 15 min estimated wait
  - **Yellow**: 15-30 min estimated wait
  - **Red**: > 30 min estimated wait
  - Estimated wait = `active_count * avg_prep_time` (or `active_count * estimated_minutes_per_order` pre-threshold)
  - Thresholds hardcoded for v1.

- **`get_restaurant_queue_info(restaurant)`** — Returns busyness level + estimated wait for ConfirmationStep. Reads from Redis cache.

- **`get_order_queue_info(order)`** — Returns queue position + estimated wait + order status for SubmittedStep. Computes position live, wait from cache.

### Celery periodic task (every 5 minutes)

**`update_queue_stats`** — For each restaurant with active orders:
1. Count active orders → cache `active_count`
2. Compute rolling average prep time from last 50 completed orders (within last 30 days) → cache `avg_prep_time`
3. Compute busyness level → cache `busyness`
4. Cache completed order count for threshold check by `QueueService`

This task lives in `backend/orders/tasks.py` alongside existing Celery tasks. It only refreshes cached averages. Real-time queue position updates are pushed instantly via WebSocket when kitchen staff changes order status.

**`broadcast_queue_updates(restaurant_id, changed_order_id)`** — Celery task in `backend/orders/tasks.py`. Triggered on each order status change. Recalculates and pushes queue positions to all affected customer WebSocket groups. Runs asynchronously to avoid blocking kitchen staff responses. Uses a Redis-based deduplication key (`queue_broadcast:{restaurant_id}`) with a 2-second TTL. If a broadcast is already pending for this restaurant, the new trigger is skipped. This coalesces rapid-fire fan-outs when kitchen staff updates multiple orders in quick succession.

Note: `backend/orders/tasks.py` is a **new file** — no existing Celery tasks live in the orders app. The payout task lives in a separate app.

## API Endpoints

### New REST endpoints

**`GET /api/order/<slug>/queue-info/`** — Restaurant busyness (pre-order, public).

Response:
```json
{
  "busyness": "yellow",
  "estimated_wait_minutes": 20,
  "active_orders": 12
}
```

**`GET /api/order/<slug>/queue/<order_id>/`** — Order queue position (post-order, public; UUID serves as access token). Registered as a separate URL pattern in `orders/urls.py` to avoid nesting under the existing `status/` path.

Response:
```json
{
  "queue_position": 5,
  "estimated_wait_minutes": 15,
  "status": "confirmed",
  "busyness": "yellow"
}
```

### WebSocket

**`CustomerOrderConsumer`** at `ws/order/<slug>/<order_id>/`

- On connect: validates the order UUID exists in the database. If not found, rejects the connection. If valid, joins channel group `customer_{order_id}`. Immediately sends current queue state (position, wait, status) so the client has data without waiting for the next update.
- No auth required (UUID order ID serves as access token)
- Orders in `pending_payment` — connection accepted, but no queue data sent until status reaches `confirmed`. Orders already `completed` — connection accepted, final state sent, no further updates.
- Receives pushed updates on status change or queue position shift
- Message format:
```json
{
  "type": "queue_update",
  "queue_position": 3,
  "estimated_wait_minutes": 10,
  "status": "preparing"
}
```

### Broadcasting changes (`broadcast.py`)

Extend `broadcast_order_to_kitchen()` to also:
1. Push update to `customer_{order_id}` group for the changed order
2. Offload fan-out to a **Celery task** (`broadcast_queue_updates`): recalculate and push updated queue positions to all customers with active orders at that restaurant (status `confirmed` or `preparing`, `confirmed_at` after the changed order's `confirmed_at`). This keeps the kitchen staff's status update response fast.
3. Skip orders already in `ready` or `completed` status

### Polling fallback

If WebSocket connection fails, frontend polls `GET /api/order/<slug>/queue/<order_id>/` every 15 seconds.

## Frontend Components

### ConfirmationStep changes (`frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`)

Add a busyness banner at the top of the page, above order items:
- Calls `GET /api/order/<slug>/queue-info/` on mount
- Displays traffic light: green circle + "Short wait (~X min)", yellow + "Moderate wait (~X min)", red + "Busy — ~X min wait"
- Subtle, non-blocking — informational only

### SubmittedStep changes (`frontend/src/app/order/[slug]/components/SubmittedStep.tsx`)

Extend the current SubmittedStep with a live order tracker (the existing account registration prompt remains below the tracker):
- **Progress bar** — 4 steps: Confirmed → Preparing → Ready → Completed. Active step highlighted, completed steps checked.
- **Queue position** — "You are #5 in line"
- **Estimated wait** — "~15 minutes estimated wait"
- **Live indicator** — green dot + "Live updates active" (WebSocket) or gray "Updating..." (polling)
- When order reaches "ready": queue info replaced with "Your order is ready for pickup!"
- When "completed": "Order complete. Thank you!"

### New hooks

**`use-order-queue.ts`**
- Manages WebSocket connection to `ws/order/<slug>/<order_id>/`
- On WebSocket failure, starts polling every 15 seconds
- Reconnection attempted every 3 seconds (matches existing pattern)
- Returns `{ queuePosition, estimatedWait, status, busyness, isConnected }`

**`use-restaurant-busyness.ts`**
- React Query hook calling the queue-info endpoint
- Returns `{ busyness, estimatedWait, isLoading }`

## Error Handling & Edge Cases

| Scenario | Behavior |
|----------|----------|
| WebSocket disconnects | Auto-switch to polling every 15s; indicator changes to "Updating..." |
| WebSocket reconnects | Resume push updates; indicator returns to "Live updates active" |
| No active orders | Busyness banner shows green: "No wait right now" |
| No completed orders, no configured estimate | Default to 10 minutes per order |
| Redis cache empty (cold start) | Compute on-the-fly and cache the result |
| Order reaches "ready" | Queue position/wait disappear; show "Your order is ready for pickup!" |
| Order reaches "completed" | Show "Order complete. Thank you!" |
| Historical data staleness | Only use orders from last 30 days for averages |
| Queue-info API failure | Hide busyness banner on ConfirmationStep; don't block ordering |

## Testing Strategy

### Backend unit tests
- `QueueService.get_queue_position()` — correct position with multiple orders in various statuses
- `QueueService.get_estimated_wait()` — owner-configured vs historical calculation, switchover at 50 orders
- `QueueService.get_busyness()` — green/yellow/red thresholds
- `update_order_status()` — status timestamps set correctly on transitions
- Celery task — cache values computed and stored correctly

### Backend integration tests
- Queue info endpoint returns correct busyness for various order loads
- Order queue endpoint returns correct position and wait time
- WebSocket consumer sends queue updates on status change
- Broadcasting recalculates positions for affected customers only

### Frontend tests
- `use-order-queue` hook — WebSocket connection, fallback to polling, state updates
- `use-restaurant-busyness` hook — API call and data mapping
- Busyness banner renders correct color/text per level
- Progress bar renders correct state per order status
- Queue position and wait time update on new data
