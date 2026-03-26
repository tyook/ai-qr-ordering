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
