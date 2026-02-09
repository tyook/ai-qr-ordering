import pytest
from decimal import Decimal
from unittest.mock import patch
from rest_framework import status

from orders.llm.base import ParsedOrder, ParsedOrderItem
from orders.models import Order
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import (
    RestaurantFactory, MenuCategoryFactory, MenuItemFactory,
    MenuItemVariantFactory, MenuItemModifierFactory,
)


@pytest.mark.django_db
class TestParseOrder:
    @pytest.fixture
    def menu_setup(self):
        restaurant = RestaurantFactory(slug="parse-test")
        cat = MenuCategoryFactory(restaurant=restaurant, name="Mains")
        item = MenuItemFactory(category=cat, name="Burger")
        variant = MenuItemVariantFactory(
            menu_item=item, label="Regular", price=Decimal("12.99"), is_default=True
        )
        modifier = MenuItemModifierFactory(
            menu_item=item, name="Extra Bacon", price_adjustment=Decimal("2.00")
        )
        return {
            "restaurant": restaurant,
            "item": item,
            "variant": variant,
            "modifier": modifier,
        }

    @patch("orders.views.get_llm_provider")
    def test_parse_returns_structured_order(self, mock_get_provider, api_client, menu_setup):
        mock_provider = mock_get_provider.return_value
        mock_provider.parse_order.return_value = ParsedOrder(
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

    @patch("orders.views.get_llm_provider")
    def test_parse_rejects_invalid_item_ids(self, mock_get_provider, api_client, menu_setup):
        mock_provider = mock_get_provider.return_value
        mock_provider.parse_order.return_value = ParsedOrder(
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
        variant = MenuItemVariantFactory(
            menu_item=item, label="Large", price=Decimal("14.99"), is_default=True
        )
        modifier = MenuItemModifierFactory(
            menu_item=item, name="Extra Cheese", price_adjustment=Decimal("2.00")
        )
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
        response = api_client.get(
            f"/api/order/status-test/status/{order.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "preparing"
        assert response.data["id"] == str(order.id)

    def test_order_from_wrong_restaurant_returns_404(self, api_client):
        restaurant1 = RestaurantFactory(slug="r1")
        restaurant2 = RestaurantFactory(slug="r2")
        order = OrderFactory(restaurant=restaurant1)
        response = api_client.get(f"/api/order/r2/status/{order.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
