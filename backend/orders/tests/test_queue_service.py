import pytest
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from orders.models import Order
from orders.queue_service import QueueService
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


@pytest.mark.django_db
class TestGetBusyness:
    def test_green_when_low_wait(self):
        restaurant = RestaurantFactory(estimated_minutes_per_order=2)
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
