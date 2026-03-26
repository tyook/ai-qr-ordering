from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import stripe
from rest_framework import status

from orders.llm.base import ParsedOrder, ParsedOrderItem
from orders.models import Order
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemModifierFactory,
    MenuItemVariantFactory,
    RestaurantFactory,
    RestaurantStaffFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestParseOrder:
    @pytest.fixture
    def menu_setup(self):
        restaurant = RestaurantFactory(slug="parse-test")
        cat = MenuCategoryFactory(restaurant=restaurant, name="Mains")
        item = MenuItemFactory(category=cat, name="Burger")
        variant = MenuItemVariantFactory(menu_item=item, label="Regular", price=Decimal("12.99"), is_default=True)
        modifier = MenuItemModifierFactory(menu_item=item, name="Extra Bacon", price_adjustment=Decimal("2.00"))
        return {
            "restaurant": restaurant,
            "item": item,
            "variant": variant,
            "modifier": modifier,
        }

    @patch("orders.services.OrderParsingAgent.run")
    def test_parse_returns_structured_order(self, mock_run, api_client, menu_setup):
        mock_run.return_value = ParsedOrder(
            items=[
                ParsedOrderItem(
                    menu_item_id=menu_setup["item"].id,
                    variant_id=menu_setup["variant"].id,
                    quantity=1,
                    modifier_ids=[menu_setup["modifier"].id],
                    special_requests="no pickles",
                )
            ],
            language="en",
        )

        response = api_client.post(
            "/api/order/parse-test/parse/",
            {"raw_input": "I want a burger with extra bacon, no pickles"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["items"]) == 1
        assert response.data["items"][0]["name"] == "Burger"
        assert response.data["items"][0]["variant"]["label"] == "Regular"
        assert response.data["total_price"] == "14.99"
        assert response.data["language"] == "en"

    @patch("orders.services.OrderParsingAgent.run")
    def test_parse_rejects_invalid_item_ids(self, mock_run, api_client, menu_setup):
        mock_run.return_value = ParsedOrder(
            items=[
                ParsedOrderItem(
                    menu_item_id=99999,  # Doesn't exist
                    variant_id=99999,
                    quantity=1,
                )
            ],
            language="en",
        )

        response = api_client.post(
            "/api/order/parse-test/parse/",
            {"raw_input": "I want something nonexistent"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        # Invalid items are silently dropped
        assert len(response.data["items"]) == 0


@pytest.mark.django_db
class TestConfirmOrder:
    @pytest.fixture
    def menu_setup(self):
        restaurant = RestaurantFactory(slug="confirm-test")
        cat = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=cat, name="Pizza")
        variant = MenuItemVariantFactory(menu_item=item, label="Large", price=Decimal("14.99"), is_default=True)
        modifier = MenuItemModifierFactory(menu_item=item, name="Extra Cheese", price_adjustment=Decimal("2.00"))
        return {
            "restaurant": restaurant,
            "item": item,
            "variant": variant,
            "modifier": modifier,
        }

    def test_confirm_creates_order(self, api_client, menu_setup):
        response = api_client.post(
            "/api/order/confirm-test/confirm/",
            {
                "items": [
                    {
                        "menu_item_id": menu_setup["item"].id,
                        "variant_id": menu_setup["variant"].id,
                        "quantity": 2,
                        "modifier_ids": [menu_setup["modifier"].id],
                        "special_requests": "well done",
                    }
                ],
                "raw_input": "Two large pizzas with extra cheese",
                "table_identifier": "5",
                "language": "en",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "confirmed"
        assert response.data["table_identifier"] == "5"
        # Price: (14.99 + 2.00) * 2 = 33.98
        assert Decimal(response.data["total_price"]) == Decimal("33.98")

        # Verify order exists in DB
        order = Order.objects.get(id=response.data["id"])
        assert order.items.count() == 1
        assert order.items.first().quantity == 2

    def test_confirm_rejects_invalid_items(self, api_client, menu_setup):
        response = api_client.post(
            "/api/order/confirm-test/confirm/",
            {
                "items": [
                    {
                        "menu_item_id": 99999,
                        "variant_id": 99999,
                        "quantity": 1,
                    }
                ],
                "raw_input": "invalid",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_with_no_items_rejected(self, api_client, menu_setup):
        response = api_client.post(
            "/api/order/confirm-test/confirm/",
            {"items": [], "raw_input": "nothing"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestOrderStatus:
    def test_get_order_status(self, api_client):
        restaurant = RestaurantFactory(slug="status-test")
        order = OrderFactory(restaurant=restaurant, status="preparing")
        response = api_client.get(f"/api/order/status-test/status/{order.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "preparing"
        assert response.data["id"] == str(order.id)

    def test_order_from_wrong_restaurant_returns_404(self, api_client):
        restaurant1 = RestaurantFactory(slug="r1")
        RestaurantFactory(slug="r2")
        order = OrderFactory(restaurant=restaurant1)
        response = api_client.get(f"/api/order/r2/status/{order.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestKitchenOrderUpdate:
    @pytest.fixture
    def kitchen_setup(self):
        restaurant = RestaurantFactory(slug="kitchen-test")
        kitchen_user = UserFactory()
        RestaurantStaffFactory(user=kitchen_user, restaurant=restaurant, role="kitchen")
        order = OrderFactory(restaurant=restaurant, status="confirmed")
        return restaurant, kitchen_user, order

    def test_kitchen_staff_can_update_status(self, api_client, kitchen_setup):
        restaurant, kitchen_user, order = kitchen_setup
        api_client.force_authenticate(user=kitchen_user)
        response = api_client.patch(
            f"/api/kitchen/orders/{order.id}/",
            {"status": "preparing"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "preparing"

    def test_non_staff_cannot_update(self, api_client, kitchen_setup):
        _, _, order = kitchen_setup
        outsider = UserFactory()
        api_client.force_authenticate(user=outsider)
        response = api_client.patch(
            f"/api/kitchen/orders/{order.id}/",
            {"status": "preparing"},
            format="json",
        )
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]

    def test_invalid_status_transition_rejected(self, api_client, kitchen_setup):
        restaurant, kitchen_user, order = kitchen_setup
        api_client.force_authenticate(user=kitchen_user)
        # Can't go from confirmed directly to completed
        response = api_client.patch(
            f"/api/kitchen/orders/{order.id}/",
            {"status": "completed"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_cannot_update(self, api_client, kitchen_setup):
        _, _, order = kitchen_setup
        response = api_client.patch(
            f"/api/kitchen/orders/{order.id}/",
            {"status": "preparing"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestCreatePayment:
    @pytest.fixture
    def menu_setup(self):
        restaurant = RestaurantFactory(slug="payment-test", tax_rate=Decimal("8.875"))
        cat = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=cat, name="Burger")
        variant = MenuItemVariantFactory(menu_item=item, label="Regular", price=Decimal("10.00"), is_default=True)
        return {
            "restaurant": restaurant,
            "item": item,
            "variant": variant,
        }

    @patch("orders.services.settings")
    @patch("orders.services.stripe")
    def test_create_payment_creates_order_and_intent(self, mock_stripe, mock_settings, api_client, menu_setup):
        mock_settings.STRIPE_SECRET_KEY = "sk_test_fake_key"
        mock_intent = MagicMock()
        mock_intent.id = "pi_test_123"
        mock_intent.client_secret = "pi_test_123_secret_456"
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        response = api_client.post(
            "/api/order/payment-test/create-payment/",
            {
                "items": [
                    {
                        "menu_item_id": menu_setup["item"].id,
                        "variant_id": menu_setup["variant"].id,
                        "quantity": 2,
                    }
                ],
                "raw_input": "Two burgers",
                "table_identifier": "3",
                "language": "en",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "pending_payment"
        assert response.data["payment_status"] == "pending"
        assert response.data["client_secret"] == "pi_test_123_secret_456"

        # Verify order in DB
        order = Order.objects.get(id=response.data["id"])
        assert order.stripe_payment_intent_id == "pi_test_123"
        assert order.status == "pending_payment"
        # Subtotal: 10.00 * 2 = 20.00, Tax: 20.00 * 8.875% = 1.78
        assert order.subtotal == Decimal("20.00")
        assert order.tax_amount == Decimal("1.78")
        assert order.total_price == Decimal("21.78")

        # Verify Stripe was called with correct amount in cents
        mock_stripe.PaymentIntent.create.assert_called_once()
        call_kwargs = mock_stripe.PaymentIntent.create.call_args[1]
        assert call_kwargs["amount"] == 2178
        assert call_kwargs["currency"] == "usd"

    @patch("orders.services.stripe")
    def test_create_payment_no_items_rejected(self, mock_stripe, api_client, menu_setup):
        response = api_client.post(
            "/api/order/payment-test/create-payment/",
            {"items": [], "raw_input": "nothing"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_stripe.PaymentIntent.create.assert_not_called()


@pytest.mark.django_db
class TestStripeWebhook:
    @patch("orders.services.stripe.Webhook.construct_event")
    @patch("orders.services.broadcast_order_to_kitchen")
    @patch("integrations.tasks.dispatch_order_to_pos")
    def test_payment_succeeded_confirms_order(self, mock_dispatch, mock_broadcast, mock_construct, api_client):
        order = OrderFactory(
            status="pending_payment",
            payment_status="pending",
            stripe_payment_intent_id="pi_test_webhook",
        )

        mock_construct.return_value = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test_webhook"}},
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=b"raw_payload",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        order.refresh_from_db()
        assert order.status == "confirmed"
        assert order.payment_status == "paid"
        mock_broadcast.assert_called_once_with(order)

    @patch("orders.services.stripe.Webhook.construct_event")
    def test_payment_failed_updates_status(self, mock_construct, api_client):
        order = OrderFactory(
            status="pending_payment",
            payment_status="pending",
            stripe_payment_intent_id="pi_test_fail",
        )

        mock_construct.return_value = {
            "type": "payment_intent.payment_failed",
            "data": {"object": {"id": "pi_test_fail"}},
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=b"raw_payload",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        order.refresh_from_db()
        assert order.payment_status == "failed"
        assert order.status == "pending_payment"

    @patch("orders.services.stripe.Webhook.construct_event")
    def test_invalid_signature_rejected(self, mock_construct, api_client):
        mock_construct.side_effect = stripe.error.SignatureVerificationError("bad sig", "sig_header")

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=b"raw_payload",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="bad_sig",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
