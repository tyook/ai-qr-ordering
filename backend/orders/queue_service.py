import logging

from django.core.cache import cache
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
        if order.status in (Order.Status.READY, Order.Status.COMPLETED):
            return {
                "queue_position": 0,
                "estimated_wait_minutes": 0,
                "status": order.status,
                "busyness": QueueService.get_busyness(order.restaurant)["busyness"],
            }

        position = QueueService.get_queue_position(order)
        estimated_wait = QueueService.get_estimated_wait(order.restaurant, position)

        return {
            "queue_position": position,
            "estimated_wait_minutes": estimated_wait,
            "status": order.status,
            "busyness": QueueService.get_busyness(order.restaurant)["busyness"],
        }
