import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from orders.llm.base import ParsedOrder, ParsedOrderItem
from orders.llm.openai_provider import OpenAIProvider
from orders.llm.menu_context import build_menu_context
from restaurants.tests.factories import (
    RestaurantFactory, MenuCategoryFactory, MenuItemFactory,
    MenuItemVariantFactory, MenuItemModifierFactory,
)


class TestParsedOrder:
    def test_parsed_order_dataclass(self):
        item = ParsedOrderItem(
            menu_item_id=1,
            variant_id=10,
            quantity=2,
            modifier_ids=[100, 101],
            special_requests="no onions",
        )
        order = ParsedOrder(items=[item], language="en")
        assert len(order.items) == 1
        assert order.language == "en"


@pytest.mark.django_db
class TestMenuContext:
    def test_build_menu_context_includes_items_and_prices(self):
        restaurant = RestaurantFactory()
        cat = MenuCategoryFactory(restaurant=restaurant, name="Pizzas")
        item = MenuItemFactory(category=cat, name="Margherita")
        MenuItemVariantFactory(
            menu_item=item, label="Large", price=Decimal("14.99")
        )
        MenuItemModifierFactory(
            menu_item=item, name="Extra Cheese", price_adjustment=Decimal("2.00")
        )

        context = build_menu_context(restaurant)
        assert "Margherita" in context
        assert "14.99" in context
        assert "Extra Cheese" in context
        assert "Pizzas" in context

    def test_build_menu_context_excludes_inactive(self):
        restaurant = RestaurantFactory()
        cat = MenuCategoryFactory(restaurant=restaurant)
        MenuItemFactory(category=cat, name="Active Item", is_active=True)
        MenuItemFactory(category=cat, name="Hidden Item", is_active=False)

        context = build_menu_context(restaurant)
        assert "Active Item" in context
        assert "Hidden Item" not in context


class TestOpenAIProvider:
    @patch("orders.llm.openai_provider.openai_client")
    def test_parse_order_calls_openai_and_returns_parsed(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"items": [{"menu_item_id": 1, "variant_id": 10, "quantity": 2, "modifier_ids": [], "special_requests": ""}], "language": "en"}'
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider()
        result = provider.parse_order("Two large margheritas", "menu context here")

        assert len(result.items) == 1
        assert result.items[0].menu_item_id == 1
        assert result.items[0].quantity == 2
        assert result.language == "en"
        mock_client.chat.completions.create.assert_called_once()
