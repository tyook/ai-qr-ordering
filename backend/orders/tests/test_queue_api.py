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
