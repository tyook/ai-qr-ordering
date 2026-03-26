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

        from orders.queue_service import QueueService
        busyness_info = QueueService.get_busyness(restaurant)
        cache.set(f"queue:{slug}:busyness", busyness_info["busyness"], QUEUE_CACHE_TTL)


@shared_task
def broadcast_queue_updates(restaurant_id, changed_order_id):
    """Broadcast updated queue positions to all affected customers."""
    dedup_key = f"queue_broadcast:{restaurant_id}"
    if cache.get(dedup_key):
        return
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
