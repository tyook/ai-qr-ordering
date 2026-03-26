# Order Queue & Estimated Wait Time Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable customers to see restaurant busyness before ordering and track queue position with estimated wait time after ordering, with real-time WebSocket updates.

**Architecture:** Computed queue — no new models. Queue position derived from existing Order data using `confirmed_at` timestamps. Historical averages cached in Redis, refreshed by Celery periodic task. Real-time updates via Django Channels WebSocket with polling fallback.

**Tech Stack:** Django REST Framework, Django Channels, Celery, Redis, Next.js 14, React, TypeScript, Zustand, React Query

**Spec:** `docs/superpowers/specs/2026-03-27-order-queue-wait-time-design.md`

---

## File Structure

### Backend — New Files
- `backend/orders/queue_service.py` — QueueService class with all queue/busyness logic
- `backend/orders/tasks.py` — Celery tasks: `update_queue_stats`, `broadcast_queue_updates`
- `backend/orders/tests/test_queue_service.py` — Unit tests for QueueService
- `backend/orders/tests/test_queue_api.py` — Integration tests for queue endpoints
- `backend/orders/tests/test_queue_websocket.py` — WebSocket consumer tests
- `backend/orders/tests/test_queue_tasks.py` — Celery task tests
- `backend/orders/migrations/XXXX_add_status_timestamps.py` — Auto-generated migration
- `backend/orders/migrations/XXXX_backfill_confirmed_at.py` — Data migration

### Backend — Modified Files
- `backend/orders/models.py` — Add timestamp fields to Order
- `backend/orders/services.py` — Add `set_status_timestamp()`, integrate into all status-change paths
- `backend/orders/views.py` — Add `QueueInfoView`, `OrderQueueView`
- `backend/orders/urls.py` — Register new endpoints
- `backend/orders/consumers.py` — Add `CustomerOrderConsumer`
- `backend/orders/routing.py` — Add customer WebSocket route
- `backend/orders/broadcast.py` — Extend to broadcast to customers
- `backend/restaurants/models.py` — Add `estimated_minutes_per_order` to Restaurant
- `backend/config/settings.py` — Add `CELERY_BEAT_SCHEDULE`

### Frontend — New Files
- `frontend/src/hooks/use-order-queue.ts` — WebSocket + polling fallback hook
- `frontend/src/hooks/use-restaurant-busyness.ts` — React Query hook for busyness
- `frontend/src/app/order/[slug]/components/BusynessBanner.tsx` — Traffic light banner component
- `frontend/src/app/order/[slug]/components/OrderTracker.tsx` — Progress bar + queue position component

### Frontend — Modified Files
- `frontend/src/lib/api.ts` — Add `fetchQueueInfo`, `fetchOrderQueue` functions
- `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx` — Add busyness banner
- `frontend/src/app/order/[slug]/components/SubmittedStep.tsx` — Add order tracker
- `frontend/src/app/order/[slug]/page.tsx` — Pass slug prop to SubmittedStep

---

## Chunk 1: Backend Data Model & Timestamp Infrastructure

### Task 1: Add status timestamp fields to Order model

**Files:**
- Modify: `backend/orders/models.py`
- Auto-generated: `backend/orders/migrations/XXXX_add_status_timestamps.py`

- [ ] **Step 1: Add timestamp fields to Order model**

In `backend/orders/models.py`, add after the `created_at` field:

```python
    confirmed_at = models.DateTimeField(null=True, blank=True)
    preparing_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
```

- [ ] **Step 2: Generate migration**

Run: `docker compose exec backend python manage.py makemigrations orders`
Expected: New migration file created

- [ ] **Step 3: Apply migration**

Run: `docker compose exec backend python manage.py migrate`
Expected: Migration applied successfully

- [ ] **Step 4: Commit**

```bash
git add backend/orders/models.py backend/orders/migrations/
git commit -m "feat: add status timestamp fields to Order model"
```

### Task 2: Add estimated_minutes_per_order to Restaurant model

**Files:**
- Modify: `backend/restaurants/models.py`
- Auto-generated: `backend/restaurants/migrations/XXXX_add_estimated_minutes.py`

- [ ] **Step 1: Add field to Restaurant model**

In `backend/restaurants/models.py`, add after the `tax_rate` field:

```python
    estimated_minutes_per_order = models.PositiveIntegerField(default=10)
```

- [ ] **Step 2: Generate and apply migration**

Run: `docker compose exec backend python manage.py makemigrations restaurants && docker compose exec backend python manage.py migrate`

- [ ] **Step 3: Commit**

```bash
git add backend/restaurants/models.py backend/restaurants/migrations/
git commit -m "feat: add estimated_minutes_per_order to Restaurant model"
```

### Task 3: Add set_status_timestamp helper and integrate into services

**Files:**
- Modify: `backend/orders/services.py`
- Test: `backend/orders/tests/test_queue_service.py`

- [ ] **Step 1: Write failing tests for timestamp setting**

Create `backend/orders/tests/test_queue_service.py`:

```python
import pytest
from datetime import timedelta
from django.utils import timezone
from orders.models import Order
from orders.services import OrderService
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.django_db
class TestSetStatusTimestamp:
    def test_set_confirmed_timestamp(self):
        order = OrderFactory(status=Order.Status.PENDING_PAYMENT)
        before = timezone.now()
        OrderService.set_status_timestamp(order, "confirmed")
        order.refresh_from_db()
        assert order.confirmed_at is not None
        assert order.confirmed_at >= before

    def test_set_preparing_timestamp(self):
        order = OrderFactory(status=Order.Status.CONFIRMED)
        OrderService.set_status_timestamp(order, "preparing")
        order.refresh_from_db()
        assert order.preparing_at is not None

    def test_set_ready_timestamp(self):
        order = OrderFactory(status=Order.Status.PREPARING)
        OrderService.set_status_timestamp(order, "ready")
        order.refresh_from_db()
        assert order.ready_at is not None

    def test_set_completed_timestamp(self):
        order = OrderFactory(status=Order.Status.READY)
        OrderService.set_status_timestamp(order, "completed")
        order.refresh_from_db()
        assert order.completed_at is not None

    def test_unknown_status_does_nothing(self):
        order = OrderFactory()
        OrderService.set_status_timestamp(order, "unknown_status")
        order.refresh_from_db()
        assert order.confirmed_at is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest orders/tests/test_queue_service.py::TestSetStatusTimestamp -v`
Expected: FAIL — `set_status_timestamp` not defined

- [ ] **Step 3: Implement set_status_timestamp**

In `backend/orders/services.py`, add this static method to `OrderService`:

```python
    STATUS_TIMESTAMP_FIELDS = {
        "confirmed": "confirmed_at",
        "preparing": "preparing_at",
        "ready": "ready_at",
        "completed": "completed_at",
    }

    @staticmethod
    def set_status_timestamp(order: Order, status: str) -> None:
        """Set the timestamp field corresponding to the given status."""
        field = OrderService.STATUS_TIMESTAMP_FIELDS.get(status)
        if field:
            setattr(order, field, timezone.now())
            order.save(update_fields=[field])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend pytest orders/tests/test_queue_service.py::TestSetStatusTimestamp -v`
Expected: All 5 PASS

- [ ] **Step 5: Integrate into create_order**

In `backend/orders/services.py`, in `create_order()`, after the `order = Order.objects.create(...)` call, add:

```python
        if order_status == "confirmed":
            OrderService.set_status_timestamp(order, "confirmed")
```

- [ ] **Step 6: Integrate into update_order_status**

In `backend/orders/services.py`, in `update_order_status()`, after `order.status = new_status` and `order.save()`, add:

```python
        OrderService.set_status_timestamp(order, new_status)
```

- [ ] **Step 7: Integrate into confirm_payment**

In `backend/orders/services.py`, in `confirm_payment()`, inside the `if updated:` block, after `broadcast_order_to_kitchen(order)`, add:

```python
            OrderService.set_status_timestamp(order, "confirmed")
```

Note: `order.refresh_from_db()` is already called before the `if updated:` block, so no need to call it again.

- [ ] **Step 8: Integrate into _handle_payment_succeeded**

In `backend/orders/services.py`, in `_handle_payment_succeeded()`, inside the `if updated:` block, after `broadcast_order_to_kitchen(order)`, add:

```python
            order.refresh_from_db()
            OrderService.set_status_timestamp(order, "confirmed")
```

- [ ] **Step 9: Run full test suite to check for regressions**

Run: `docker compose exec backend pytest orders/ -v`
Expected: All existing tests pass

- [ ] **Step 10: Commit**

```bash
git add backend/orders/services.py backend/orders/tests/test_queue_service.py
git commit -m "feat: add set_status_timestamp helper and integrate into all status-change paths"
```

### Task 4: Create data migration to backfill confirmed_at

**Files:**
- Create: `backend/orders/migrations/XXXX_backfill_confirmed_at.py`

- [ ] **Step 1: Create data migration**

Run: `docker compose exec backend python manage.py makemigrations orders --empty -n backfill_confirmed_at`

- [ ] **Step 2: Edit the migration**

Replace the generated migration content with:

```python
from django.db import migrations
from django.db.models import F


def backfill_confirmed_at(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Order.objects.filter(
        status__in=["confirmed", "preparing", "ready", "completed"],
        confirmed_at__isnull=True,
    ).update(confirmed_at=F("created_at"))


def reverse_backfill(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Order.objects.filter(confirmed_at__isnull=False).update(confirmed_at=None)


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "XXXX_add_status_timestamps"),  # Replace XXXX with actual migration number from Task 1
    ]

    operations = [
        migrations.RunPython(backfill_confirmed_at, reverse_backfill),
    ]
```

**Important:** Replace `XXXX_add_status_timestamps` with the actual migration filename generated in Task 1, Step 2.

- [ ] **Step 3: Apply migration**

Run: `docker compose exec backend python manage.py migrate`
Expected: Data migration applied

- [ ] **Step 4: Commit**

```bash
git add backend/orders/migrations/
git commit -m "feat: add data migration to backfill confirmed_at for existing orders"
```

---

## Chunk 2: QueueService & Celery Tasks

### Task 5: Implement QueueService

**Files:**
- Create: `backend/orders/queue_service.py`
- Test: `backend/orders/tests/test_queue_service.py`

- [ ] **Step 1: Write failing tests for get_queue_position**

Append to `backend/orders/tests/test_queue_service.py`:

```python
from orders.queue_service import QueueService

# Note: `timedelta` and other imports are already at the top of the file from Task 3.


@pytest.mark.django_db
class TestGetQueuePosition:
    def test_first_order_is_position_one(self):
        restaurant = RestaurantFactory()
        order = OrderFactory(
            restaurant=restaurant,
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        assert QueueService.get_queue_position(order) == 1

    def test_position_reflects_confirmed_at_ordering(self):
        restaurant = RestaurantFactory()
        order1 = OrderFactory(
            restaurant=restaurant,
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now() - timedelta(minutes=10),
        )
        order2 = OrderFactory(
            restaurant=restaurant,
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now() - timedelta(minutes=5),
        )
        order3 = OrderFactory(
            restaurant=restaurant,
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        assert QueueService.get_queue_position(order1) == 1
        assert QueueService.get_queue_position(order2) == 2
        assert QueueService.get_queue_position(order3) == 3

    def test_excludes_ready_and_completed_orders(self):
        restaurant = RestaurantFactory()
        OrderFactory(
            restaurant=restaurant,
            status=Order.Status.READY,
            confirmed_at=timezone.now() - timedelta(minutes=10),
        )
        OrderFactory(
            restaurant=restaurant,
            status=Order.Status.COMPLETED,
            confirmed_at=timezone.now() - timedelta(minutes=15),
        )
        order = OrderFactory(
            restaurant=restaurant,
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        assert QueueService.get_queue_position(order) == 1

    def test_includes_preparing_orders(self):
        restaurant = RestaurantFactory()
        OrderFactory(
            restaurant=restaurant,
            status=Order.Status.PREPARING,
            confirmed_at=timezone.now() - timedelta(minutes=5),
        )
        order = OrderFactory(
            restaurant=restaurant,
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        assert QueueService.get_queue_position(order) == 2

    def test_excludes_null_confirmed_at(self):
        restaurant = RestaurantFactory()
        OrderFactory(
            restaurant=restaurant,
            status=Order.Status.CONFIRMED,
            confirmed_at=None,
        )
        order = OrderFactory(
            restaurant=restaurant,
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        assert QueueService.get_queue_position(order) == 1

    def test_excludes_other_restaurants(self):
        restaurant1 = RestaurantFactory()
        restaurant2 = RestaurantFactory()
        OrderFactory(
            restaurant=restaurant1,
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now() - timedelta(minutes=5),
        )
        order = OrderFactory(
            restaurant=restaurant2,
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        assert QueueService.get_queue_position(order) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest orders/tests/test_queue_service.py::TestGetQueuePosition -v`
Expected: FAIL — `QueueService` not found

- [ ] **Step 3: Implement QueueService with get_queue_position**

Create `backend/orders/queue_service.py`:

```python
import logging
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, F, Q
from django.utils import timezone

from orders.models import Order
from restaurants.models import Restaurant

logger = logging.getLogger(__name__)

QUEUE_CACHE_TTL = 600  # 10 minutes
HISTORICAL_THRESHOLD = 50
BUSYNESS_GREEN_MAX = 15  # minutes
BUSYNESS_YELLOW_MAX = 30  # minutes
HISTORICAL_WINDOW_DAYS = 30

ACTIVE_STATUSES = [Order.Status.CONFIRMED, Order.Status.PREPARING]


class QueueService:
    @staticmethod
    def get_queue_position(order: Order) -> int:
        """Get 1-based queue position for an order."""
        if not order.confirmed_at:
            return 0

        ahead = Order.objects.filter(
            restaurant=order.restaurant,
            status__in=ACTIVE_STATUSES,
            confirmed_at__isnull=False,
            confirmed_at__lt=order.confirmed_at,
        ).count()

        return ahead + 1

    @staticmethod
    def get_estimated_wait(restaurant: Restaurant, queue_position: int) -> int:
        """Get estimated wait time in minutes."""
        slug = restaurant.slug
        completed_count = cache.get(f"queue:{slug}:completed_count", 0)

        if completed_count >= HISTORICAL_THRESHOLD:
            avg_prep = cache.get(f"queue:{slug}:avg_prep_time")
            if avg_prep is not None:
                return max(1, int(avg_prep * queue_position))

        return max(1, restaurant.estimated_minutes_per_order * queue_position)

    @staticmethod
    def get_busyness(restaurant: Restaurant) -> dict:
        """Get busyness level and estimated wait for a restaurant."""
        slug = restaurant.slug
        active_count = cache.get(f"queue:{slug}:active_count")

        if active_count is None:
            active_count = Order.objects.filter(
                restaurant=restaurant,
                status__in=ACTIVE_STATUSES,
            ).count()
            cache.set(f"queue:{slug}:active_count", active_count, QUEUE_CACHE_TTL)

        estimated_wait = QueueService.get_estimated_wait(restaurant, active_count)

        if estimated_wait < BUSYNESS_GREEN_MAX:
            level = "green"
        elif estimated_wait <= BUSYNESS_YELLOW_MAX:
            level = "yellow"
        else:
            level = "red"

        return {
            "busyness": level,
            "estimated_wait_minutes": estimated_wait,
            "active_orders": active_count,
        }

    @staticmethod
    def get_restaurant_queue_info(restaurant: Restaurant) -> dict:
        """Get queue info for ConfirmationStep (pre-order)."""
        return QueueService.get_busyness(restaurant)

    @staticmethod
    def get_order_queue_info(order: Order) -> dict:
        """Get queue info for SubmittedStep (post-order)."""
        position = QueueService.get_queue_position(order)
        estimated_wait = QueueService.get_estimated_wait(order.restaurant, position)

        return {
            "queue_position": position,
            "estimated_wait_minutes": estimated_wait,
            "status": order.status,
            "busyness": QueueService.get_busyness(order.restaurant)["busyness"],
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend pytest orders/tests/test_queue_service.py::TestGetQueuePosition -v`
Expected: All 6 PASS

- [ ] **Step 5: Write failing tests for get_estimated_wait**

Append to `backend/orders/tests/test_queue_service.py`:

```python
from unittest.mock import patch


@pytest.mark.django_db
class TestGetEstimatedWait:
    def test_uses_restaurant_default_below_threshold(self):
        restaurant = RestaurantFactory(estimated_minutes_per_order=8)
        result = QueueService.get_estimated_wait(restaurant, 3)
        assert result == 24  # 8 * 3

    def test_uses_historical_above_threshold(self):
        restaurant = RestaurantFactory(estimated_minutes_per_order=8)
        with patch("orders.queue_service.cache") as mock_cache:
            mock_cache.get.side_effect = lambda key, *args: {
                f"queue:{restaurant.slug}:completed_count": 60,
                f"queue:{restaurant.slug}:avg_prep_time": 12.5,
            }.get(key, args[0] if args else None)
            result = QueueService.get_estimated_wait(restaurant, 3)
            assert result == 37  # int(12.5 * 3) = 37

    def test_minimum_wait_is_one_minute(self):
        restaurant = RestaurantFactory(estimated_minutes_per_order=0)
        result = QueueService.get_estimated_wait(restaurant, 0)
        assert result == 1

    def test_falls_back_to_default_when_no_cache(self):
        restaurant = RestaurantFactory(estimated_minutes_per_order=10)
        with patch("orders.queue_service.cache") as mock_cache:
            mock_cache.get.side_effect = lambda key, *args: {
                f"queue:{restaurant.slug}:completed_count": 60,
                f"queue:{restaurant.slug}:avg_prep_time": None,
            }.get(key, args[0] if args else None)
            result = QueueService.get_estimated_wait(restaurant, 3)
            assert result == 30  # fallback: 10 * 3
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose exec backend pytest orders/tests/test_queue_service.py::TestGetEstimatedWait -v`
Expected: All 4 PASS (implementation already covers these)

- [ ] **Step 7: Write failing tests for get_busyness**

Append to `backend/orders/tests/test_queue_service.py`:

```python
@pytest.mark.django_db
class TestGetBusyness:
    def test_green_when_low_wait(self):
        restaurant = RestaurantFactory(estimated_minutes_per_order=2)
        # 2 min/order * 3 active = 6 min < 15 = green
        for _ in range(3):
            OrderFactory(
                restaurant=restaurant,
                status=Order.Status.CONFIRMED,
                confirmed_at=timezone.now(),
            )
        result = QueueService.get_busyness(restaurant)
        assert result["busyness"] == "green"
        assert result["active_orders"] == 3

    def test_yellow_when_moderate_wait(self):
        restaurant = RestaurantFactory(estimated_minutes_per_order=5)
        # 5 min/order * 4 active = 20 min -> yellow
        for _ in range(4):
            OrderFactory(
                restaurant=restaurant,
                status=Order.Status.CONFIRMED,
                confirmed_at=timezone.now(),
            )
        result = QueueService.get_busyness(restaurant)
        assert result["busyness"] == "yellow"

    def test_red_when_high_wait(self):
        restaurant = RestaurantFactory(estimated_minutes_per_order=10)
        # 10 min/order * 4 active = 40 min > 30 = red
        for _ in range(4):
            OrderFactory(
                restaurant=restaurant,
                status=Order.Status.CONFIRMED,
                confirmed_at=timezone.now(),
            )
        result = QueueService.get_busyness(restaurant)
        assert result["busyness"] == "red"

    def test_green_when_no_orders(self):
        restaurant = RestaurantFactory()
        result = QueueService.get_busyness(restaurant)
        assert result["busyness"] == "green"
        assert result["active_orders"] == 0
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `docker compose exec backend pytest orders/tests/test_queue_service.py::TestGetBusyness -v`
Expected: All 4 PASS

- [ ] **Step 9: Commit**

```bash
git add backend/orders/queue_service.py backend/orders/tests/test_queue_service.py
git commit -m "feat: implement QueueService with queue position, wait time, and busyness"
```

### Task 6: Implement Celery tasks

**Files:**
- Create: `backend/orders/tasks.py`
- Modify: `backend/config/settings.py`
- Test: `backend/orders/tests/test_queue_tasks.py`

- [ ] **Step 1: Write failing tests for update_queue_stats**

Create `backend/orders/tests/test_queue_tasks.py`:

```python
import pytest
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.utils import timezone

from orders.models import Order
from orders.tasks import update_queue_stats
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.django_db
class TestUpdateQueueStats:
    def setup_method(self):
        cache.clear()

    def test_caches_active_count(self):
        restaurant = RestaurantFactory()
        OrderFactory(restaurant=restaurant, status=Order.Status.CONFIRMED, confirmed_at=timezone.now())
        OrderFactory(restaurant=restaurant, status=Order.Status.PREPARING, confirmed_at=timezone.now())
        OrderFactory(restaurant=restaurant, status=Order.Status.COMPLETED, confirmed_at=timezone.now())

        update_queue_stats()

        assert cache.get(f"queue:{restaurant.slug}:active_count") == 2

    def test_caches_avg_prep_time(self):
        restaurant = RestaurantFactory()
        now = timezone.now()
        for i in range(3):
            OrderFactory(
                restaurant=restaurant,
                status=Order.Status.COMPLETED,
                confirmed_at=now - timedelta(minutes=30 + i * 10),
                ready_at=now - timedelta(minutes=10 + i * 10),
            )
        # Each order took 20 minutes from confirmed -> ready

        update_queue_stats()

        avg = cache.get(f"queue:{restaurant.slug}:avg_prep_time")
        assert avg == pytest.approx(20.0, abs=0.1)

    def test_caches_completed_count(self):
        restaurant = RestaurantFactory()
        for _ in range(5):
            OrderFactory(restaurant=restaurant, status=Order.Status.COMPLETED)

        update_queue_stats()

        assert cache.get(f"queue:{restaurant.slug}:completed_count") == 5

    def test_caches_for_restaurants_with_completed_orders(self):
        restaurant = RestaurantFactory()
        OrderFactory(
            restaurant=restaurant,
            status=Order.Status.COMPLETED,
            confirmed_at=timezone.now() - timedelta(minutes=30),
            completed_at=timezone.now(),
        )

        update_queue_stats()

        assert cache.get(f"queue:{restaurant.slug}:completed_count") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest orders/tests/test_queue_tasks.py -v`
Expected: FAIL — `tasks` module not found

- [ ] **Step 3: Implement Celery tasks**

Create `backend/orders/tasks.py`:

```python
import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db.models import Avg, F, Q
from django.utils import timezone

from orders.models import Order
from orders.queue_service import ACTIVE_STATUSES, HISTORICAL_WINDOW_DAYS, QUEUE_CACHE_TTL
from restaurants.models import Restaurant

logger = logging.getLogger(__name__)

BROADCAST_DEDUP_TTL = 2  # seconds


@shared_task
def update_queue_stats():
    """Refresh cached queue statistics for all restaurants with recent activity."""
    cutoff = timezone.now() - timedelta(days=HISTORICAL_WINDOW_DAYS)

    restaurant_ids = (
        Order.objects.filter(
            Q(status__in=ACTIVE_STATUSES) | Q(status=Order.Status.COMPLETED, completed_at__gte=cutoff)
        )
        .values_list("restaurant_id", flat=True)
        .distinct()
    )

    for restaurant in Restaurant.objects.filter(id__in=restaurant_ids):
        slug = restaurant.slug

        active_count = Order.objects.filter(
            restaurant=restaurant,
            status__in=ACTIVE_STATUSES,
        ).count()
        cache.set(f"queue:{slug}:active_count", active_count, QUEUE_CACHE_TTL)

        completed_qs = Order.objects.filter(
            restaurant=restaurant,
            status=Order.Status.COMPLETED,
        )
        completed_count = completed_qs.count()
        cache.set(f"queue:{slug}:completed_count", completed_count, QUEUE_CACHE_TTL)

        avg_prep = (
            completed_qs.filter(
                confirmed_at__isnull=False,
                ready_at__isnull=False,
                confirmed_at__gte=cutoff,
            )
            .annotate(prep_seconds=F("ready_at") - F("confirmed_at"))
            .aggregate(avg=Avg("prep_seconds"))["avg"]
        )
        if avg_prep is not None:
            avg_minutes = avg_prep.total_seconds() / 60
            cache.set(f"queue:{slug}:avg_prep_time", avg_minutes, QUEUE_CACHE_TTL)

        # Compute busyness from cached values
        from orders.queue_service import QueueService

        busyness_info = QueueService.get_busyness(restaurant)
        cache.set(f"queue:{slug}:busyness", busyness_info["busyness"], QUEUE_CACHE_TTL)


@shared_task
def broadcast_queue_updates(restaurant_id, changed_order_id):
    """Broadcast updated queue positions to all affected customers."""
    dedup_key = f"queue_broadcast:{restaurant_id}"
    if cache.get(dedup_key):
        return  # Already a pending broadcast
    cache.set(dedup_key, True, BROADCAST_DEDUP_TTL)

    from orders.queue_service import QueueService

    try:
        restaurant = Restaurant.objects.get(id=restaurant_id)
    except Restaurant.DoesNotExist:
        return

    active_orders = Order.objects.filter(
        restaurant=restaurant,
        status__in=ACTIVE_STATUSES,
        confirmed_at__isnull=False,
    ).order_by("confirmed_at")

    channel_layer = get_channel_layer()

    for order in active_orders:
        queue_info = QueueService.get_order_queue_info(order)
        async_to_sync(channel_layer.group_send)(
            f"customer_{order.id}",
            {
                "type": "queue_update",
                "data": queue_info,
            },
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend pytest orders/tests/test_queue_tasks.py -v`
Expected: All 4 PASS

- [ ] **Step 5: Add CELERY_BEAT_SCHEDULE to settings**

In `backend/config/settings.py`, add after the existing Celery config:

```python
CELERY_BEAT_SCHEDULE = {
    "update-queue-stats": {
        "task": "orders.tasks.update_queue_stats",
        "schedule": 300.0,  # Every 5 minutes
    },
}
```

- [ ] **Step 6: Run full backend test suite**

Run: `docker compose exec backend pytest orders/ -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/orders/tasks.py backend/orders/tests/test_queue_tasks.py backend/config/settings.py
git commit -m "feat: add Celery tasks for queue stats refresh and broadcast"
```

---

## Chunk 3: API Endpoints & WebSocket Consumer

### Task 7: Add queue serializers and API views

**Files:**
- Modify: `backend/orders/serializers.py`
- Modify: `backend/orders/views.py`
- Modify: `backend/orders/urls.py`
- Test: `backend/orders/tests/test_queue_api.py`

- [ ] **Step 1: Write failing tests for queue endpoints**

Create `backend/orders/tests/test_queue_api.py`:

```python
import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework import status

from orders.models import Order
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.django_db
class TestQueueInfoView:
    def test_returns_busyness_for_restaurant(self, api_client):
        restaurant = RestaurantFactory(slug="queue-test", estimated_minutes_per_order=5)
        for _ in range(3):
            OrderFactory(
                restaurant=restaurant,
                status=Order.Status.CONFIRMED,
                confirmed_at=timezone.now(),
            )

        response = api_client.get("/api/order/queue-test/queue-info/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["busyness"] in ("green", "yellow", "red")
        assert "estimated_wait_minutes" in response.data
        assert response.data["active_orders"] == 3

    def test_returns_green_when_no_orders(self, api_client):
        RestaurantFactory(slug="empty-queue")

        response = api_client.get("/api/order/empty-queue/queue-info/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["busyness"] == "green"
        assert response.data["active_orders"] == 0

    def test_404_for_unknown_restaurant(self, api_client):
        response = api_client.get("/api/order/nonexistent/queue-info/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestOrderQueueView:
    def test_returns_queue_position(self, api_client):
        restaurant = RestaurantFactory(slug="order-queue")
        order1 = OrderFactory(
            restaurant=restaurant,
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now() - timedelta(minutes=5),
        )
        order2 = OrderFactory(
            restaurant=restaurant,
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now(),
        )

        response = api_client.get(f"/api/order/order-queue/queue/{order2.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["queue_position"] == 2
        assert response.data["status"] == "confirmed"
        assert "estimated_wait_minutes" in response.data
        assert "busyness" in response.data

    def test_404_for_unknown_order(self, api_client):
        RestaurantFactory(slug="order-queue-404")
        response = api_client.get("/api/order/order-queue-404/queue/00000000-0000-0000-0000-000000000000/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest orders/tests/test_queue_api.py -v`
Expected: FAIL — 404 on new endpoints (not registered)

- [ ] **Step 3: Add API views**

In `backend/orders/views.py`, add imports at top:

```python
from orders.queue_service import QueueService
from restaurants.models import Restaurant
```

Also ensure `NotFound` is imported from `rest_framework.exceptions` (add to existing imports if not present).

Add the new views:

```python
class QueueInfoView(APIView):
    """GET /api/order/<slug>/queue-info/ — restaurant busyness (public)."""

    def get(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            raise NotFound("Restaurant not found")

        data = QueueService.get_restaurant_queue_info(restaurant)
        return Response(data)


class OrderQueueView(APIView):
    """GET /api/order/<slug>/queue/<order_id>/ — order queue position (public)."""

    def get(self, request, slug, order_id):
        try:
            order = Order.objects.select_related("restaurant").get(
                id=order_id, restaurant__slug=slug
            )
        except Order.DoesNotExist:
            raise NotFound("Order not found")

        data = QueueService.get_order_queue_info(order)
        return Response(data)
```

- [ ] **Step 4: Register URL patterns**

In `backend/orders/urls.py`, add `QueueInfoView` and `OrderQueueView` to the existing import block from `orders.views`.

Add to `urlpatterns`:

```python
    path("order/<slug:slug>/queue-info/", QueueInfoView.as_view(), name="queue-info"),
    path("order/<slug:slug>/queue/<uuid:order_id>/", OrderQueueView.as_view(), name="order-queue"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec backend pytest orders/tests/test_queue_api.py -v`
Expected: All 5 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/orders/views.py backend/orders/urls.py backend/orders/tests/test_queue_api.py
git commit -m "feat: add queue-info and order-queue REST endpoints"
```

### Task 8: Add CustomerOrderConsumer WebSocket

**Files:**
- Modify: `backend/orders/consumers.py`
- Modify: `backend/orders/routing.py`
- Test: `backend/orders/tests/test_queue_websocket.py`

- [ ] **Step 1: Write failing tests for CustomerOrderConsumer**

Create `backend/orders/tests/test_queue_websocket.py`:

```python
import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.utils import timezone

from config.asgi import application
from orders.models import Order
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCustomerOrderWebSocket:
    async def test_connect_with_valid_order(self):
        restaurant = RestaurantFactory(slug="ws-customer")
        order = OrderFactory(
            restaurant=restaurant,
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        communicator = WebsocketCommunicator(application, f"/ws/order/ws-customer/{order.id}/")
        connected, _ = await communicator.connect()
        assert connected

        # Should receive initial state
        response = await communicator.receive_json_from(timeout=5)
        assert response["status"] == "confirmed"
        assert "queue_position" in response
        await communicator.disconnect()

    async def test_reject_invalid_order(self):
        RestaurantFactory(slug="ws-invalid")
        communicator = WebsocketCommunicator(
            application, "/ws/order/ws-invalid/00000000-0000-0000-0000-000000000000/"
        )
        connected, _ = await communicator.connect()
        assert not connected

    async def test_receive_queue_update(self):
        restaurant = RestaurantFactory(slug="ws-update")
        order = OrderFactory(
            restaurant=restaurant,
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        communicator = WebsocketCommunicator(application, f"/ws/order/ws-update/{order.id}/")
        connected, _ = await communicator.connect()
        assert connected

        # Consume initial state message
        await communicator.receive_json_from(timeout=5)

        # Simulate a queue update broadcast
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"customer_{order.id}",
            {
                "type": "queue_update",
                "data": {
                    "queue_position": 2,
                    "estimated_wait_minutes": 10,
                    "status": "preparing",
                    "busyness": "yellow",
                },
            },
        )

        response = await communicator.receive_json_from(timeout=5)
        assert response["queue_position"] == 2
        assert response["status"] == "preparing"
        await communicator.disconnect()

    async def test_completed_order_sends_final_state(self):
        restaurant = RestaurantFactory(slug="ws-complete")
        order = OrderFactory(
            restaurant=restaurant,
            status=Order.Status.COMPLETED,
            confirmed_at=timezone.now(),
        )
        communicator = WebsocketCommunicator(application, f"/ws/order/ws-complete/{order.id}/")
        connected, _ = await communicator.connect()
        assert connected

        response = await communicator.receive_json_from(timeout=5)
        assert response["status"] == "completed"
        await communicator.disconnect()

    async def test_pending_payment_no_queue_data(self):
        restaurant = RestaurantFactory(slug="ws-pending")
        order = OrderFactory(
            restaurant=restaurant,
            status=Order.Status.PENDING_PAYMENT,
        )
        communicator = WebsocketCommunicator(application, f"/ws/order/ws-pending/{order.id}/")
        connected, _ = await communicator.connect()
        assert connected

        response = await communicator.receive_json_from(timeout=5)
        assert response["status"] == "pending_payment"
        assert response.get("queue_position") is None
        await communicator.disconnect()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest orders/tests/test_queue_websocket.py -v`
Expected: FAIL — route not found / consumer not defined

- [ ] **Step 3: Implement CustomerOrderConsumer**

In `backend/orders/consumers.py`, add the `CustomerOrderConsumer` class below the existing `KitchenConsumer` (imports are already present):

```python
class CustomerOrderConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        self.order_id = str(self.scope["url_route"]["kwargs"]["order_id"])
        self.group_name = f"customer_{self.order_id}"

        # Validate order exists
        order_data = await self._get_order_state()
        if order_data is None:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial state
        await self.send(text_data=json.dumps(order_data))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def queue_update(self, event):
        """Receives queue update messages."""
        await self.send(text_data=json.dumps(event["data"]))

    @database_sync_to_async
    def _get_order_state(self):
        from orders.models import Order
        from orders.queue_service import QueueService

        try:
            order = Order.objects.select_related("restaurant").get(
                id=self.order_id, restaurant__slug=self.slug
            )
        except Order.DoesNotExist:
            return None

        if order.status in (Order.Status.PENDING_PAYMENT, Order.Status.PENDING):
            return {"status": order.status, "queue_position": None, "estimated_wait_minutes": None, "busyness": None}

        return QueueService.get_order_queue_info(order)
```

- [ ] **Step 4: Add WebSocket route**

In `backend/orders/routing.py`:

```python
from django.urls import re_path
from orders.consumers import CustomerOrderConsumer, KitchenConsumer

websocket_urlpatterns = [
    re_path(r"ws/kitchen/(?P<slug>[\w-]+)/$", KitchenConsumer.as_asgi()),
    re_path(
        r"ws/order/(?P<slug>[\w-]+)/(?P<order_id>[0-9a-f-]+)/$",
        CustomerOrderConsumer.as_asgi(),
    ),
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec backend pytest orders/tests/test_queue_websocket.py -v`
Expected: All 5 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/orders/consumers.py backend/orders/routing.py backend/orders/tests/test_queue_websocket.py
git commit -m "feat: add CustomerOrderConsumer WebSocket for live queue updates"
```

### Task 9: Extend broadcasting to customers

**Files:**
- Modify: `backend/orders/broadcast.py`
- Modify: `backend/orders/services.py`

- [ ] **Step 1: Extend broadcast.py**

In `backend/orders/broadcast.py`, add the customer broadcast function:

```python
def broadcast_order_to_customer(order):
    """Send queue update to the customer's WebSocket group."""
    from orders.queue_service import QueueService

    channel_layer = get_channel_layer()
    queue_info = QueueService.get_order_queue_info(order)

    async_to_sync(channel_layer.group_send)(
        f"customer_{order.id}",
        {
            "type": "queue_update",
            "data": queue_info,
        },
    )
```

- [ ] **Step 2: Integrate into services.py**

In `backend/orders/services.py`, add import:

```python
from orders.broadcast import broadcast_order_to_customer
```

In `update_order_status()`, after the existing `broadcast_order_to_kitchen(order)` call, add:

```python
        broadcast_order_to_customer(order)

        # Trigger fan-out to other waiting customers
        from orders.tasks import broadcast_queue_updates
        broadcast_queue_updates.apply_async(
            args=[str(order.restaurant_id), str(order.id)],
            countdown=2,
        )
```

In `confirm_payment()`, inside the `if updated:` block, after `broadcast_order_to_kitchen(order)`, add:

```python
            broadcast_order_to_customer(order)
            from orders.tasks import broadcast_queue_updates
            broadcast_queue_updates.apply_async(
                args=[str(order.restaurant_id), str(order.id)],
                countdown=2,
            )
```

In `_handle_payment_succeeded()`, inside the `if updated:` block, after `broadcast_order_to_kitchen(order)`, add the same lines.

- [ ] **Step 3: Run full backend test suite**

Run: `docker compose exec backend pytest orders/ -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/orders/broadcast.py backend/orders/services.py
git commit -m "feat: extend broadcasting to push queue updates to customers"
```

---

## Chunk 4: Frontend — API Layer & Hooks

### Task 10: Add queue API functions

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add API functions**

In `frontend/src/lib/api.ts`, add the queue-related types and functions:

```typescript
export interface QueueInfo {
  busyness: "green" | "yellow" | "red";
  estimated_wait_minutes: number;
  active_orders: number;
}

export interface OrderQueueInfo {
  queue_position: number | null;
  estimated_wait_minutes: number | null;
  status: string;
  busyness: string | null;
}

export async function fetchQueueInfo(slug: string): Promise<QueueInfo> {
  return apiFetch<QueueInfo>(`/api/order/${slug}/queue-info/`);
}

export async function fetchOrderQueue(slug: string, orderId: string): Promise<OrderQueueInfo> {
  return apiFetch<OrderQueueInfo>(`/api/order/${slug}/queue/${orderId}/`);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add queue-info and order-queue API functions"
```

### Task 11: Create use-restaurant-busyness hook

**Files:**
- Create: `frontend/src/hooks/use-restaurant-busyness.ts`

- [ ] **Step 1: Create the hook**

Create `frontend/src/hooks/use-restaurant-busyness.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchQueueInfo, type QueueInfo } from "@/lib/api";

export function useRestaurantBusyness(slug: string) {
  const { data, isLoading, error } = useQuery<QueueInfo>({
    queryKey: ["queueInfo", slug],
    queryFn: () => fetchQueueInfo(slug),
    refetchInterval: 60_000, // Refresh every 60s
    retry: 1,
  });

  return {
    busyness: data?.busyness ?? null,
    estimatedWait: data?.estimated_wait_minutes ?? null,
    activeOrders: data?.active_orders ?? 0,
    isLoading,
    error,
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/use-restaurant-busyness.ts
git commit -m "feat: add use-restaurant-busyness hook"
```

### Task 12: Create use-order-queue hook with WebSocket + polling fallback

**Files:**
- Create: `frontend/src/hooks/use-order-queue.ts`

- [ ] **Step 1: Create the hook**

Create `frontend/src/hooks/use-order-queue.ts`:

```typescript
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchOrderQueue, type OrderQueueInfo } from "@/lib/api";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:5005";
const RECONNECT_INTERVAL = 3000;
const POLL_INTERVAL = 15000;

interface UseOrderQueueOptions {
  slug: string;
  orderId: string | null;
  enabled?: boolean;
}

export function useOrderQueue({ slug, orderId, enabled = true }: UseOrderQueueOptions) {
  const [queueInfo, setQueueInfo] = useState<OrderQueueInfo | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<NodeJS.Timeout>();
  const pollRef = useRef<NodeJS.Timeout>();
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = undefined;
    }
  }, []);

  const startPolling = useCallback(() => {
    if (!orderId || !enabledRef.current) return;
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const data = await fetchOrderQueue(slug, orderId);
        setQueueInfo(data);
      } catch {
        // Silently fail — will retry on next interval
      }
    }, POLL_INTERVAL);
  }, [slug, orderId, stopPolling]);

  const connect = useCallback(() => {
    if (!orderId || !enabledRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(`${WS_URL}/ws/order/${slug}/${orderId}/`);

    ws.onopen = () => {
      setIsConnected(true);
      stopPolling();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setQueueInfo(data);
      } catch {
        // Ignore non-JSON messages
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      if (enabledRef.current) {
        startPolling();
        reconnectRef.current = setTimeout(connect, RECONNECT_INTERVAL);
      }
    };

    ws.onerror = () => ws.close();
    wsRef.current = ws;
  }, [slug, orderId, stopPolling, startPolling]);

  useEffect(() => {
    if (!enabled || !orderId) return;
    connect();

    return () => {
      enabledRef.current = false;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      stopPolling();
      wsRef.current?.close();
    };
  }, [connect, enabled, orderId, stopPolling]);

  return {
    queuePosition: queueInfo?.queue_position ?? null,
    estimatedWait: queueInfo?.estimated_wait_minutes ?? null,
    status: queueInfo?.status ?? null,
    busyness: queueInfo?.busyness ?? null,
    isConnected,
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/use-order-queue.ts
git commit -m "feat: add use-order-queue hook with WebSocket and polling fallback"
```

---

## Chunk 5: Frontend — UI Components

### Task 13: Create BusynessBanner component

**Files:**
- Create: `frontend/src/app/order/[slug]/components/BusynessBanner.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/app/order/[slug]/components/BusynessBanner.tsx`:

```tsx
"use client";

import { useRestaurantBusyness } from "@/hooks/use-restaurant-busyness";

interface BusynessBannerProps {
  slug: string;
}

const BUSYNESS_CONFIG = {
  green: {
    emoji: "\u{1F7E2}",
    label: "Short wait",
    bg: "bg-green-50",
    border: "border-green-200",
    text: "text-green-800",
  },
  yellow: {
    emoji: "\u{1F7E1}",
    label: "Moderate wait",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    text: "text-yellow-800",
  },
  red: {
    emoji: "\u{1F534}",
    label: "Busy",
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-800",
  },
} as const;

export function BusynessBanner({ slug }: BusynessBannerProps) {
  const { busyness, estimatedWait, isLoading, error } = useRestaurantBusyness(slug);

  if (isLoading || error || !busyness) return null;

  const config = BUSYNESS_CONFIG[busyness];

  return (
    <div className={`${config.bg} ${config.border} border rounded-lg p-3 mb-4 flex items-center gap-3`}>
      <span className="text-xl">{config.emoji}</span>
      <div>
        <div className={`font-semibold text-sm ${config.text}`}>{config.label}</div>
        <div className="text-xs text-gray-600">
          {estimatedWait
            ? `~${estimatedWait} min estimated wait right now`
            : "No wait right now"}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/order/[slug]/components/BusynessBanner.tsx
git commit -m "feat: add BusynessBanner component for ConfirmationStep"
```

### Task 14: Create OrderTracker component

**Files:**
- Create: `frontend/src/app/order/[slug]/components/OrderTracker.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/app/order/[slug]/components/OrderTracker.tsx`:

```tsx
"use client";

import { useOrderQueue } from "@/hooks/use-order-queue";

interface OrderTrackerProps {
  slug: string;
  orderId: string;
}

const STEPS = [
  { key: "confirmed", label: "Confirmed" },
  { key: "preparing", label: "Preparing" },
  { key: "ready", label: "Ready" },
  { key: "completed", label: "Completed" },
] as const;

const STATUS_ORDER = ["confirmed", "preparing", "ready", "completed"];

function getStepIndex(status: string | null): number {
  if (!status) return -1;
  return STATUS_ORDER.indexOf(status);
}

export function OrderTracker({ slug, orderId }: OrderTrackerProps) {
  const { queuePosition, estimatedWait, status, isConnected } = useOrderQueue({
    slug,
    orderId,
    enabled: true,
  });

  const currentIndex = getStepIndex(status);
  const isReady = status === "ready";
  const isCompleted = status === "completed";

  return (
    <div className="w-full max-w-md mx-auto">
      {/* Progress bar */}
      <div className="flex items-center justify-between mb-6 px-2">
        {STEPS.map((step, i) => {
          const isActive = i === currentIndex;
          const isDone = i < currentIndex;
          return (
            <div key={step.key} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold ${
                    isDone
                      ? "bg-green-500 text-white"
                      : isActive
                        ? "bg-blue-500 text-white"
                        : "bg-gray-200 text-gray-500"
                  }`}
                >
                  {isDone ? "\u2713" : i + 1}
                </div>
                <span
                  className={`text-xs mt-1 ${
                    isDone
                      ? "text-green-600 font-semibold"
                      : isActive
                        ? "text-blue-600 font-semibold"
                        : "text-gray-400"
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-1 mb-5 ${
                    i < currentIndex ? "bg-green-500" : "bg-gray-200"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Queue info */}
      {isReady ? (
        <div className="bg-green-50 rounded-xl p-5 text-center mb-4">
          <div className="text-lg font-bold text-green-800">Your order is ready for pickup!</div>
        </div>
      ) : isCompleted ? (
        <div className="bg-gray-50 rounded-xl p-5 text-center mb-4">
          <div className="text-lg font-bold text-gray-800">Order complete. Thank you!</div>
        </div>
      ) : queuePosition !== null ? (
        <div className="bg-gray-50 rounded-xl p-5 text-center mb-4">
          <div className="text-3xl font-extrabold text-gray-900">#{queuePosition}</div>
          <div className="text-sm text-gray-500 mb-3">in line</div>
          {estimatedWait !== null && (
            <>
              <div className="w-12 h-px bg-gray-300 mx-auto mb-3" />
              <div className="text-xl font-bold text-yellow-700">~{estimatedWait} min</div>
              <div className="text-sm text-gray-500">estimated wait</div>
            </>
          )}
        </div>
      ) : null}

      {/* Connection indicator */}
      <div className="flex items-center justify-center gap-1.5 text-xs">
        <span
          className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-500" : "bg-gray-400"}`}
        />
        <span className={isConnected ? "text-green-600" : "text-gray-500"}>
          {isConnected ? "Live updates active" : "Updating..."}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/order/[slug]/components/OrderTracker.tsx
git commit -m "feat: add OrderTracker component with progress bar and queue position"
```

### Task 15: Integrate BusynessBanner into ConfirmationStep

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`

- [ ] **Step 1: Add BusynessBanner import and render**

In `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`, add import:

```typescript
import { BusynessBanner } from "./BusynessBanner";
```

Add the banner at the top of the component's return JSX, before the order items list (as the first child inside the main container):

```tsx
<BusynessBanner slug={slug} />
```

- [ ] **Step 2: Verify it renders**

Run: `cd frontend && npm run dev`
Navigate to an order confirmation page and verify the busyness banner appears.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/order/[slug]/components/ConfirmationStep.tsx
git commit -m "feat: add busyness banner to ConfirmationStep"
```

### Task 16: Integrate OrderTracker into SubmittedStep

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/SubmittedStep.tsx`
- Modify: `frontend/src/app/order/[slug]/page.tsx` (parent component)

- [ ] **Step 1: Add slug prop to SubmittedStep**

In `frontend/src/app/order/[slug]/components/SubmittedStep.tsx`, add a props interface and update the component signature:

```typescript
interface SubmittedStepProps {
  slug: string;
}

export function SubmittedStep({ slug }: SubmittedStepProps) {
```

- [ ] **Step 2: Update parent to pass slug**

In `frontend/src/app/order/[slug]/page.tsx`, find where `<SubmittedStep />` is rendered and change it to:

```tsx
<SubmittedStep slug={slug} />
```

Where `slug` comes from the page's route params.

- [ ] **Step 3: Add OrderTracker import and render**

In `frontend/src/app/order/[slug]/components/SubmittedStep.tsx`, add import:

```typescript
import { OrderTracker } from "./OrderTracker";
```

Add the OrderTracker component near the top of the submitted step content, after the "Order submitted!" heading and before the account registration section:

```tsx
{orderId && <OrderTracker slug={slug} orderId={orderId} />}
```

- [ ] **Step 2: Verify it renders**

Run: `cd frontend && npm run dev`
Place a test order and verify the order tracker appears on the submitted step.

- [ ] **Step 3: Run frontend build to check for type errors**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no type errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/order/[slug]/components/SubmittedStep.tsx
git commit -m "feat: add order tracker with live queue updates to SubmittedStep"
```

---

## Chunk 6: Integration Testing & Cleanup

### Task 17: End-to-end integration verification

- [ ] **Step 1: Run full backend test suite**

Run: `docker compose exec backend pytest -v`
Expected: All tests pass

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Manual integration test**

1. Start services: `docker compose up`
2. Navigate to a restaurant's order page
3. Verify busyness banner shows on ConfirmationStep
4. Place an order
5. Verify OrderTracker shows on SubmittedStep with queue position
6. Open kitchen display in another tab
7. Advance the order status
8. Verify customer view updates in real-time

- [ ] **Step 4: Final commit (if any unstaged changes remain)**

```bash
git status
# Review any unstaged changes, then add only relevant files:
git add backend/ frontend/
git commit -m "feat: order queue and estimated wait time feature complete"
```
