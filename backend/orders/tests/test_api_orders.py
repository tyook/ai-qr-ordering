import pytest
from decimal import Decimal
from unittest.mock import patch
from rest_framework import status

from orders.llm.base import ParsedOrder, ParsedOrderItem
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
