import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal

from integrations.adapters.base import PushResult
from integrations.adapters.square import SquareAdapter
from integrations.tests.factories import POSConnectionFactory
from orders.tests.factories import OrderFactory, OrderItemFactory
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemVariantFactory,
    MenuItemModifierFactory,
    RestaurantFactory,
)


@pytest.mark.django_db
class TestSquareAdapter:
    @pytest.fixture
    def setup(self):
        restaurant = RestaurantFactory()
        connection = POSConnectionFactory(
            restaurant=restaurant,
            pos_type="square",
            external_location_id="L123",
            oauth_access_token="sq_test_token",
        )
        cat = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=cat, name="Burger")
        variant = MenuItemVariantFactory(
            menu_item=item, label="Regular", price=Decimal("12.99")
        )
        modifier = MenuItemModifierFactory(
            menu_item=item, name="Extra Cheese", price_adjustment=Decimal("1.50")
        )
        order = OrderFactory(
            restaurant=restaurant,
            subtotal=Decimal("14.49"),
            tax_amount=Decimal("1.29"),
            total_price=Decimal("15.78"),
        )
        order_item = OrderItemFactory(
            order=order,
            menu_item=item,
            variant=variant,
            quantity=1,
        )
        order_item.modifiers.add(modifier)
        return {
            "connection": connection,
            "order": order,
            "item": item,
            "variant": variant,
            "modifier": modifier,
        }

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_push_order_success(self, mock_get_client, setup):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_result.body = {"order": {"id": "sq_order_abc"}}
        mock_client.orders.create_order.return_value = mock_result
        mock_get_client.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        result = adapter.push_order(setup["order"])

        assert result.success is True
        assert result.external_order_id == "sq_order_abc"
        mock_client.orders.create_order.assert_called_once()

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_push_order_failure(self, mock_get_client, setup):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = False
        mock_result.errors = [{"detail": "Invalid location"}]
        mock_client.orders.create_order.return_value = mock_result
        mock_get_client.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        result = adapter.push_order(setup["order"])

        assert result.success is False
        assert "Invalid location" in result.error_message

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_push_order_with_stripe_payment_marks_paid(self, mock_get_client, setup):
        setup["connection"].payment_mode = "stripe"
        setup["connection"].save()
        setup["order"].payment_status = "paid"
        setup["order"].save()

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_result.body = {"order": {"id": "sq_order_paid"}}
        mock_client.orders.create_order.return_value = mock_result
        mock_get_client.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        result = adapter.push_order(setup["order"])

        assert result.success is True
        call_body = mock_client.orders.create_order.call_args.kwargs["body"]
        # Verify a tender was included for "paid externally"
        assert "tenders" in call_body["order"]

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_cancel_order_success(self, mock_get_client, setup):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_client.orders.update_order.return_value = mock_result
        mock_get_client.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        assert adapter.cancel_order("sq_order_123") is True

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_validate_connection_success(self, mock_get_client, setup):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_client.locations.list_locations.return_value = mock_result
        mock_get_client.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        assert adapter.validate_connection() is True

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_validate_connection_failure(self, mock_get_client, setup):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = False
        mock_client.locations.list_locations.return_value = mock_result
        mock_get_client.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        assert adapter.validate_connection() is False

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_get_order_status_success(self, mock_get_client, setup):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_result.body = {"order": {"state": "OPEN"}}
        mock_client.orders.retrieve_order.return_value = mock_result
        mock_get_client.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        assert adapter.get_order_status("sq_order_123") == "OPEN"

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_get_order_status_failure(self, mock_get_client, setup):
        mock_get_client.return_value.orders.retrieve_order.side_effect = Exception("API error")

        adapter = SquareAdapter(setup["connection"])
        assert adapter.get_order_status("sq_order_123") == "unknown"

    @patch("integrations.adapters.square.SquareClient")
    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_refresh_tokens_success(self, mock_get_client, mock_square_class, setup):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_result.body = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_at": "2026-05-01T00:00:00Z",
        }
        mock_client.o_auth.obtain_token.return_value = mock_result
        mock_square_class.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        assert adapter.refresh_tokens() is True

        setup["connection"].refresh_from_db()
        assert setup["connection"].oauth_token_expires_at is not None

    @patch("integrations.adapters.square.SquareClient")
    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_refresh_tokens_failure(self, mock_get_client, mock_square_class, setup):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = False
        mock_result.body = {"errors": [{"detail": "Invalid refresh token"}]}
        mock_client.o_auth.obtain_token.return_value = mock_result
        mock_square_class.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        assert adapter.refresh_tokens() is False
