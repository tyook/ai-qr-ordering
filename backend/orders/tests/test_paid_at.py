import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone
from orders.services import OrderService
from orders.models import Order
from django.contrib.auth import get_user_model
from restaurants.models import Restaurant

User = get_user_model()


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-restaurant", owner=owner)


@pytest.fixture
def pending_order(restaurant):
    return Order.objects.create(
        restaurant=restaurant,
        raw_input="test order",
        status="pending_payment",
        payment_status="pending",
        subtotal=10.00,
        tax_rate=0,
        tax_amount=0,
        total_price=10.00,
        stripe_payment_intent_id="pi_test123",
    )


@pytest.mark.django_db
class TestPaidAtTimestamp:
    @patch("orders.services.stripe.PaymentIntent.retrieve")
    def test_confirm_payment_sets_paid_at(self, mock_retrieve, pending_order):
        mock_intent = MagicMock()
        mock_intent.status = "succeeded"
        mock_retrieve.return_value = mock_intent

        OrderService.confirm_payment(pending_order)
        pending_order.refresh_from_db()

        assert pending_order.paid_at is not None
        assert pending_order.payment_status == "paid"

    def test_webhook_payment_succeeded_sets_paid_at(self, pending_order):
        OrderService._handle_payment_succeeded(
            {"id": "pi_test123"}
        )
        pending_order.refresh_from_db()

        assert pending_order.paid_at is not None
        assert pending_order.payment_status == "paid"
