"""
Tests for restaurants.llm schemas and agents.

All LLM calls are mocked so no API key is required.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from restaurants.llm.merge_agent import MenuMergeAgent
from restaurants.llm.parse_agent import MenuParsingAgent
from restaurants.llm.schemas import (
    ParsedMenu,
    ParsedMenuCategory,
    ParsedMenuItem,
    ParsedMenuPage,
    ParsedMenuVariant,
)


# ── Schema tests ─────────────────────────────────────────────────────────────


class TestParsedMenuVariant:
    def test_valid_creation(self):
        variant = ParsedMenuVariant(label="Regular", price=Decimal("9.50"))
        assert variant.label == "Regular"
        assert variant.price == Decimal("9.50")

    def test_price_from_string(self):
        variant = ParsedMenuVariant(label="Large", price="12.00")
        assert variant.price == Decimal("12.00")

    def test_missing_label_raises(self):
        with pytest.raises(ValidationError):
            ParsedMenuVariant(price=Decimal("5.00"))

    def test_missing_price_raises(self):
        with pytest.raises(ValidationError):
            ParsedMenuVariant(label="Small")


class TestParsedMenuItem:
    def _variant(self, label="Standard", price="8.00"):
        return ParsedMenuVariant(label=label, price=Decimal(price))

    def test_valid_with_description(self):
        item = ParsedMenuItem(
            name="Burger",
            description="A tasty burger",
            variants=[self._variant()],
        )
        assert item.name == "Burger"
        assert item.description == "A tasty burger"
        assert len(item.variants) == 1

    def test_description_is_optional(self):
        item = ParsedMenuItem(name="Fries", variants=[self._variant()])
        assert item.description is None

    def test_empty_variants_raises(self):
        with pytest.raises(ValidationError):
            ParsedMenuItem(name="Salad", variants=[])

    def test_missing_variants_raises(self):
        with pytest.raises(ValidationError):
            ParsedMenuItem(name="Salad")

    def test_multiple_variants(self):
        item = ParsedMenuItem(
            name="Pizza",
            variants=[
                self._variant("Small", "8.00"),
                self._variant("Large", "14.00"),
            ],
        )
        assert len(item.variants) == 2


class TestParsedMenuCategory:
    def _item(self, name="Item"):
        return ParsedMenuItem(
            name=name,
            variants=[ParsedMenuVariant(label="Standard", price=Decimal("5.00"))],
        )

    def test_valid_creation(self):
        cat = ParsedMenuCategory(name="Starters", items=[self._item()])
        assert cat.name == "Starters"
        assert len(cat.items) == 1

    def test_empty_items_allowed(self):
        cat = ParsedMenuCategory(name="Desserts", items=[])
        assert cat.items == []


class TestParsedMenuPage:
    def _category(self, name="Mains"):
        return ParsedMenuCategory(
            name=name,
            items=[
                ParsedMenuItem(
                    name="Steak",
                    variants=[ParsedMenuVariant(label="Standard", price=Decimal("20.00"))],
                )
            ],
        )

    def test_valid_creation(self):
        page = ParsedMenuPage(categories=[self._category()])
        assert len(page.categories) == 1

    def test_empty_categories_allowed(self):
        page = ParsedMenuPage(categories=[])
        assert page.categories == []


class TestParsedMenu:
    def _category(self, name="Drinks"):
        return ParsedMenuCategory(
            name=name,
            items=[
                ParsedMenuItem(
                    name="Cola",
                    variants=[ParsedMenuVariant(label="Standard", price=Decimal("2.50"))],
                )
            ],
        )

    def test_valid_creation(self):
        menu = ParsedMenu(categories=[self._category()])
        assert len(menu.categories) == 1

    def test_empty_categories_allowed(self):
        menu = ParsedMenu(categories=[])
        assert menu.categories == []

    def test_multiple_categories(self):
        menu = ParsedMenu(categories=[self._category("Drinks"), self._category("Snacks")])
        assert len(menu.categories) == 2


# ── MenuParsingAgent tests ────────────────────────────────────────────────────


class TestMenuParsingAgent:
    def _make_page(self):
        return ParsedMenuPage(
            categories=[
                ParsedMenuCategory(
                    name="Burgers",
                    items=[
                        ParsedMenuItem(
                            name="Classic",
                            variants=[ParsedMenuVariant(label="Standard", price=Decimal("10.00"))],
                        )
                    ],
                )
            ]
        )

    def test_get_name(self):
        agent = MenuParsingAgent()
        assert agent.get_name() == "MenuParsingAgent"

    def test_get_output_schema(self):
        agent = MenuParsingAgent()
        assert agent.get_output_schema() is ParsedMenuPage

    def test_default_model_is_gpt4o(self):
        assert MenuParsingAgent.default_model == "gpt-4o"

    def test_resolve_model_always_uses_gpt4o(self):
        """_resolve_model should ignore LLM_MODEL and always use gpt-4o."""
        agent = MenuParsingAgent()
        with patch("restaurants.llm.parse_agent.resolve_model") as mock_resolve:
            mock_resolve.return_value = MagicMock()
            agent._resolve_model()
            mock_resolve.assert_called_once_with("gpt-4o")

    def test_run_calls_agent_with_image(self):
        expected_page = self._make_page()
        mock_result = MagicMock()
        mock_result.content = expected_page

        mock_agent = MagicMock()
        mock_agent.run.return_value = mock_result

        with patch.object(MenuParsingAgent, "_build_agent", return_value=mock_agent):
            result = MenuParsingAgent.run(image_data=b"fake-image-bytes")

        mock_agent.run.assert_called_once()
        call_args = mock_agent.run.call_args
        # images kwarg should be a list with one Image
        images = call_args.kwargs.get("images") or call_args[1].get("images")
        assert images is not None
        assert len(images) == 1
        assert images[0].content == b"fake-image-bytes"

        assert result is expected_page

    def test_run_returns_parsed_menu_page(self):
        expected_page = self._make_page()
        mock_result = MagicMock()
        mock_result.content = expected_page

        mock_agent = MagicMock()
        mock_agent.run.return_value = mock_result

        with patch.object(MenuParsingAgent, "_build_agent", return_value=mock_agent):
            result = MenuParsingAgent.run(image_data=b"data")

        assert isinstance(result, ParsedMenuPage)


# ── MenuMergeAgent tests ──────────────────────────────────────────────────────


class TestMenuMergeAgent:
    def _make_page(self, category_name="Mains"):
        return ParsedMenuPage(
            categories=[
                ParsedMenuCategory(
                    name=category_name,
                    items=[
                        ParsedMenuItem(
                            name="Dish",
                            variants=[
                                ParsedMenuVariant(label="Standard", price=Decimal("15.00"))
                            ],
                        )
                    ],
                )
            ]
        )

    def test_get_name(self):
        agent = MenuMergeAgent()
        assert agent.get_name() == "MenuMergeAgent"

    def test_get_output_schema(self):
        agent = MenuMergeAgent()
        assert agent.get_output_schema() is ParsedMenu

    def test_default_model_is_gpt4o_mini(self):
        assert MenuMergeAgent.default_model == "gpt-4o-mini"

    def test_run_empty_pages_returns_empty_menu(self):
        result = MenuMergeAgent.run(pages=[])
        assert isinstance(result, ParsedMenu)
        assert result.categories == []

    def test_run_single_page_short_circuits(self):
        """Single page should return immediately without an LLM call."""
        page = self._make_page()
        with patch.object(MenuMergeAgent, "_build_agent") as mock_build:
            result = MenuMergeAgent.run(pages=[page])
            mock_build.assert_not_called()

        assert isinstance(result, ParsedMenu)
        assert result.categories == page.categories

    def test_run_multiple_pages_calls_agent(self):
        pages = [self._make_page("Starters"), self._make_page("Mains")]
        expected_menu = ParsedMenu(
            categories=[
                ParsedMenuCategory(
                    name="Starters",
                    items=[
                        ParsedMenuItem(
                            name="Dish",
                            variants=[
                                ParsedMenuVariant(label="Standard", price=Decimal("15.00"))
                            ],
                        )
                    ],
                ),
                ParsedMenuCategory(
                    name="Mains",
                    items=[
                        ParsedMenuItem(
                            name="Dish",
                            variants=[
                                ParsedMenuVariant(label="Standard", price=Decimal("15.00"))
                            ],
                        )
                    ],
                ),
            ]
        )

        mock_result = MagicMock()
        mock_result.content = expected_menu
        mock_agent = MagicMock()
        mock_agent.run.return_value = mock_result

        with patch.object(MenuMergeAgent, "_build_agent", return_value=mock_agent):
            result = MenuMergeAgent.run(pages=pages)

        mock_agent.run.assert_called_once()
        assert result is expected_menu

    def test_get_context_serializes_pages_as_json(self):
        import json

        page = self._make_page("Drinks")
        agent = MenuMergeAgent()
        context = agent.get_context(pages=[page])

        assert "menu_pages" in context
        data = json.loads(context["menu_pages"])
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["categories"][0]["name"] == "Drinks"

    def test_get_context_empty_pages(self):
        import json

        agent = MenuMergeAgent()
        context = agent.get_context(pages=[])
        data = json.loads(context["menu_pages"])
        assert data == []
