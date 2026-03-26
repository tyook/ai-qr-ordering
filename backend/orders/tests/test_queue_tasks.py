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
                completed_at=now,
            )

        update_queue_stats()

        avg = cache.get(f"queue:{restaurant.slug}:avg_prep_time")
        assert avg == pytest.approx(20.0, abs=0.1)

    def test_caches_completed_count(self):
        restaurant = RestaurantFactory()
        for _ in range(5):
            OrderFactory(
                restaurant=restaurant,
                status=Order.Status.COMPLETED,
                confirmed_at=timezone.now() - timedelta(minutes=30),
                completed_at=timezone.now(),
            )

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
