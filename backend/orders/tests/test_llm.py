import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from orders.llm.base import ParsedOrder, ParsedOrderItem
from orders.llm.agent import OrderParsingAgent
from orders.llm.menu_context import build_menu_context
from restaurants.tests.factories import (
    RestaurantFactory, MenuCategoryFactory, MenuItemFactory,
    MenuItemVariantFactory, MenuItemModifierFactory,
)


class TestParsedOrder:
    def test_parsed_order_model(self):
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

    def test_parsed_order_defaults(self):
        item = ParsedOrderItem(menu_item_id=1, variant_id=10, quantity=1)
        assert item.modifier_ids == []
        assert item.special_requests == ""

        order = ParsedOrder(items=[item])
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


class TestOrderParsingAgent:
    def test_agent_properties(self):
        agent = OrderParsingAgent()
        assert agent.get_name() == "OrderParsingAgent"
        assert agent.default_model == "gpt-4o-mini"
        assert agent.get_output_schema() is ParsedOrder
        assert "order-taking assistant" in agent.get_instructions()

    def test_agent_context_building(self):
        agent = OrderParsingAgent()
        context = agent.get_context(
            raw_input="Two pizzas please",
            menu_context="## Pizzas\n  - Margherita",
        )
        assert "customer_order" in context
        assert context["customer_order"] == "Two pizzas please"
        assert "restaurant_menu" in context
        assert "Margherita" in context["restaurant_menu"]

    def test_agent_context_xml_formatting(self):
        agent = OrderParsingAgent()
        context = agent.get_context(
            raw_input="One burger",
            menu_context="## Burgers",
        )
        xml = agent._format_context(context)
        assert "<customer_order>" in xml
        assert "</customer_order>" in xml
        assert "<restaurant_menu>" in xml
        assert "</restaurant_menu>" in xml

    @patch("ai.base_agent.Agent")
    def test_agent_run_calls_agno(self, mock_agent_class):
        """Verify that run() creates an agno Agent and calls run() on it."""
        mock_parsed = ParsedOrder(
            items=[
                ParsedOrderItem(
                    menu_item_id=1, variant_id=10, quantity=2,
                )
            ],
            language="en",
        )
        mock_run_output = MagicMock()
        mock_run_output.content = mock_parsed

        mock_agent_instance = MagicMock()
        mock_agent_instance.run.return_value = mock_run_output
        mock_agent_class.return_value = mock_agent_instance

        result = OrderParsingAgent.run(
            raw_input="Two large margheritas",
            menu_context="menu context here",
        )

        assert result == mock_parsed
        assert result.items[0].menu_item_id == 1
        assert result.items[0].quantity == 2
        assert result.language == "en"
        mock_agent_instance.run.assert_called_once()
