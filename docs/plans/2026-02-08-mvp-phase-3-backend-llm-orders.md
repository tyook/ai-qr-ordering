# Phase 3: Backend LLM Integration & Order API

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the LLM abstraction layer for parsing natural language orders, the two-step order flow (parse then confirm), and order status endpoints.

**Architecture:** LLM provider abstraction with OpenAI as default. Two-step ordering: `parse` sends customer text + menu context to the LLM and returns structured items for confirmation. `confirm` validates everything against the DB, calculates total price server-side, and creates the Order.

**Tech Stack:** Django 4.2, DRF, OpenAI Python SDK, pytest

**Depends on:** Phase 1 (models), Phase 2 (menu API)

---

## Task 1: LLM Provider Abstraction

**Files:**
- Create: `backend/orders/llm/__init__.py`
- Create: `backend/orders/llm/base.py`
- Create: `backend/orders/llm/openai_provider.py`
- Create: `backend/orders/llm/menu_context.py`
- Create: `backend/orders/tests/test_llm.py`

**Step 1: Create the LLM package**

```bash
mkdir -p backend/orders/llm
touch backend/orders/llm/__init__.py
```

**Step 2: Write the failing tests**

Create `backend/orders/tests/test_llm.py`:

```python
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
```

**Step 3: Run tests to verify they fail**

```bash
cd backend
pytest orders/tests/test_llm.py -v
```

Expected: FAIL (modules don't exist)

**Step 4: Create `backend/orders/llm/base.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ParsedOrderItem:
    menu_item_id: int
    variant_id: int
    quantity: int
    modifier_ids: list[int] = field(default_factory=list)
    special_requests: str = ""


@dataclass
class ParsedOrder:
    items: list[ParsedOrderItem]
    language: str = "en"


class LLMProvider(ABC):
    @abstractmethod
    def parse_order(self, raw_input: str, menu_context: str) -> ParsedOrder:
        ...
```

**Step 5: Create `backend/orders/llm/menu_context.py`**

```python
from restaurants.models import Restaurant, MenuCategory


def build_menu_context(restaurant: Restaurant) -> str:
    """
    Build a text representation of the restaurant's menu for the LLM prompt.
    Includes item IDs so the LLM can reference them in its response.
    """
    lines = [f"Restaurant: {restaurant.name}", ""]

    categories = (
        MenuCategory.objects.filter(restaurant=restaurant, is_active=True)
        .prefetch_related("items__variants", "items__modifiers")
        .order_by("sort_order")
    )

    for category in categories:
        lines.append(f"## {category.name}")
        active_items = category.items.filter(is_active=True).order_by("sort_order")

        for item in active_items:
            lines.append(f"  - {item.name} (item_id: {item.id})")
            if item.description:
                lines.append(f"    Description: {item.description}")

            variants = item.variants.all()
            if variants:
                lines.append("    Sizes/Variants (pick one):")
                for v in variants:
                    default_marker = " [DEFAULT]" if v.is_default else ""
                    lines.append(
                        f"      * {v.label}: ${v.price}{default_marker} (variant_id: {v.id})"
                    )

            modifiers = item.modifiers.all()
            if modifiers:
                lines.append("    Modifiers (optional, pick any):")
                for m in modifiers:
                    price_str = (
                        f"+${m.price_adjustment}" if m.price_adjustment else "free"
                    )
                    lines.append(
                        f"      * {m.name}: {price_str} (modifier_id: {m.id})"
                    )

        lines.append("")

    return "\n".join(lines)
```

**Step 6: Create `backend/orders/llm/openai_provider.py`**

```python
import json
import logging

from openai import OpenAI
from django.conf import settings

from orders.llm.base import LLMProvider, ParsedOrder, ParsedOrderItem

logger = logging.getLogger(__name__)

openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """You are an order-taking assistant for a restaurant. Given a customer's natural language order and the restaurant's menu, extract the structured order.

Return ONLY valid JSON in this exact format:
{
  "items": [
    {
      "menu_item_id": <int>,
      "variant_id": <int>,
      "quantity": <int>,
      "modifier_ids": [<int>, ...],
      "special_requests": "<string>"
    }
  ],
  "language": "<ISO 639-1 code of the language the customer used>"
}

Rules:
- Only use item_id, variant_id, and modifier_id values from the menu provided
- If the customer doesn't specify a variant, use the DEFAULT variant
- If quantity is not specified, assume 1
- Keep special_requests brief and in English
- Detect the language the customer wrote/spoke in and set the "language" field
- If something the customer asked for is not on the menu, skip it (do NOT invent IDs)
"""


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model

    def parse_order(self, raw_input: str, menu_context: str) -> ParsedOrder:
        user_message = f"""Customer's order:
\"{raw_input}\"

Restaurant menu:
{menu_context}"""

        response = openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        raw_json = response.choices[0].message.content
        logger.info("LLM raw response: %s", raw_json)

        data = json.loads(raw_json)
        items = [
            ParsedOrderItem(
                menu_item_id=item["menu_item_id"],
                variant_id=item["variant_id"],
                quantity=item.get("quantity", 1),
                modifier_ids=item.get("modifier_ids", []),
                special_requests=item.get("special_requests", ""),
            )
            for item in data.get("items", [])
        ]

        return ParsedOrder(items=items, language=data.get("language", "en"))
```

**Step 7: Update `backend/orders/llm/__init__.py`**

```python
from orders.llm.base import LLMProvider, ParsedOrder, ParsedOrderItem
from orders.llm.openai_provider import OpenAIProvider
from orders.llm.menu_context import build_menu_context

__all__ = [
    "LLMProvider",
    "ParsedOrder",
    "ParsedOrderItem",
    "OpenAIProvider",
    "build_menu_context",
]
```

**Step 8: Run tests**

```bash
cd backend
pytest orders/tests/test_llm.py -v
```

Expected: All PASS.

**Step 9: Commit**

```bash
git add backend/orders/
git commit -m "feat: add LLM abstraction layer with OpenAI provider and menu context builder"
```

---

## Task 2: Order Parse Endpoint

**Files:**
- Create: `backend/orders/services.py`
- Modify: `backend/orders/views.py`
- Modify: `backend/orders/urls.py`
- Create: `backend/orders/serializers.py`
- Create: `backend/orders/tests/test_api_orders.py`

**Step 1: Write the failing test**

Create `backend/orders/tests/test_api_orders.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
pytest orders/tests/test_api_orders.py::TestParseOrder -v
```

Expected: FAIL

**Step 3: Create order validation service**

Create `backend/orders/services.py`:

```python
from decimal import Decimal

from restaurants.models import Restaurant, MenuItem, MenuItemVariant, MenuItemModifier
from orders.llm.base import ParsedOrder


def validate_and_price_order(restaurant: Restaurant, parsed: ParsedOrder) -> dict:
    """
    Validate LLM-parsed order items against the database.
    Calculate prices server-side. Drop any invalid items.
    Returns a dict ready for the frontend confirmation step.
    """
    validated_items = []
    total_price = Decimal("0.00")

    for parsed_item in parsed.items:
        try:
            menu_item = MenuItem.objects.get(
                id=parsed_item.menu_item_id,
                category__restaurant=restaurant,
                is_active=True,
            )
            variant = MenuItemVariant.objects.get(
                id=parsed_item.variant_id,
                menu_item=menu_item,
            )
        except (MenuItem.DoesNotExist, MenuItemVariant.DoesNotExist):
            continue  # Skip invalid items

        # Validate modifiers
        valid_modifiers = []
        for mod_id in parsed_item.modifier_ids:
            try:
                modifier = MenuItemModifier.objects.get(
                    id=mod_id, menu_item=menu_item
                )
                valid_modifiers.append(
                    {
                        "id": modifier.id,
                        "name": modifier.name,
                        "price_adjustment": str(modifier.price_adjustment),
                    }
                )
            except MenuItemModifier.DoesNotExist:
                continue  # Skip invalid modifiers

        item_price = variant.price * parsed_item.quantity
        modifier_total = sum(
            Decimal(m["price_adjustment"]) for m in valid_modifiers
        ) * parsed_item.quantity
        line_total = item_price + modifier_total
        total_price += line_total

        validated_items.append(
            {
                "menu_item_id": menu_item.id,
                "name": menu_item.name,
                "variant": {
                    "id": variant.id,
                    "label": variant.label,
                    "price": str(variant.price),
                },
                "quantity": parsed_item.quantity,
                "modifiers": valid_modifiers,
                "special_requests": parsed_item.special_requests,
                "line_total": str(line_total),
            }
        )

    return {
        "items": validated_items,
        "total_price": str(total_price),
        "language": parsed.language,
    }
```

**Step 4: Create order serializers**

Create `backend/orders/serializers.py`:

```python
from rest_framework import serializers
from orders.models import Order, OrderItem


class ParseInputSerializer(serializers.Serializer):
    raw_input = serializers.CharField(max_length=2000)
    table_identifier = serializers.CharField(max_length=50, required=False, default="")


class ConfirmOrderItemSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    variant_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    modifier_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    special_requests = serializers.CharField(required=False, default="")


class ConfirmOrderSerializer(serializers.Serializer):
    items = ConfirmOrderItemSerializer(many=True)
    raw_input = serializers.CharField()
    table_identifier = serializers.CharField(required=False, default="")
    language = serializers.CharField(required=False, default="en")


class OrderItemResponseSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="menu_item.name")
    variant_label = serializers.CharField(source="variant.label")
    variant_price = serializers.DecimalField(
        source="variant.price", max_digits=8, decimal_places=2
    )

    class Meta:
        model = OrderItem
        fields = [
            "id", "name", "variant_label", "variant_price",
            "quantity", "special_requests",
        ]


class OrderResponseSerializer(serializers.ModelSerializer):
    items = OrderItemResponseSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "status", "table_identifier", "total_price",
            "created_at", "items",
        ]
```

**Step 5: Add parse view**

Append to `backend/orders/views.py`:

```python
from orders.serializers import ParseInputSerializer, ConfirmOrderSerializer
from orders.services import validate_and_price_order
from orders.llm.menu_context import build_menu_context
from orders.llm.openai_provider import OpenAIProvider


def get_llm_provider():
    return OpenAIProvider()


class ParseOrderView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            return Response(
                {"detail": "Restaurant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ParseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_input = serializer.validated_data["raw_input"]
        menu_context = build_menu_context(restaurant)
        provider = get_llm_provider()
        parsed = provider.parse_order(raw_input, menu_context)
        result = validate_and_price_order(restaurant, parsed)

        return Response(result)
```

**Step 6: Add URL**

Add to `backend/orders/urls.py`:

```python
from orders.views import PublicMenuView, ParseOrderView

urlpatterns = [
    path("order/<slug:slug>/menu/", PublicMenuView.as_view(), name="public-menu"),
    path("order/<slug:slug>/parse/", ParseOrderView.as_view(), name="parse-order"),
]
```

**Step 7: Run tests**

```bash
cd backend
pytest orders/tests/test_api_orders.py::TestParseOrder -v
```

Expected: All PASS.

**Step 8: Commit**

```bash
git add backend/orders/
git commit -m "feat: add order parse endpoint with LLM integration and server-side validation"
```

---

## Task 3: Order Confirm Endpoint

**Files:**
- Modify: `backend/orders/views.py`
- Modify: `backend/orders/urls.py`
- Modify: `backend/orders/tests/test_api_orders.py`

**Step 1: Write the failing test**

Append to `backend/orders/tests/test_api_orders.py`:

```python
from orders.models import Order


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
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
pytest orders/tests/test_api_orders.py::TestConfirmOrder -v
```

Expected: FAIL

**Step 3: Add confirm view**

Append to `backend/orders/views.py`:

```python
from decimal import Decimal
from orders.models import Order, OrderItem
from orders.serializers import ConfirmOrderSerializer, OrderResponseSerializer
from restaurants.models import MenuItem, MenuItemVariant, MenuItemModifier


class ConfirmOrderView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            return Response(
                {"detail": "Restaurant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ConfirmOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not data["items"]:
            return Response(
                {"detail": "Order must contain at least one item."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate and calculate price server-side
        total_price = Decimal("0.00")
        validated_items = []

        for item_data in data["items"]:
            try:
                menu_item = MenuItem.objects.get(
                    id=item_data["menu_item_id"],
                    category__restaurant=restaurant,
                    is_active=True,
                )
                variant = MenuItemVariant.objects.get(
                    id=item_data["variant_id"],
                    menu_item=menu_item,
                )
            except (MenuItem.DoesNotExist, MenuItemVariant.DoesNotExist):
                return Response(
                    {"detail": f"Invalid menu item or variant."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            valid_modifiers = []
            modifier_total = Decimal("0.00")
            for mod_id in item_data.get("modifier_ids", []):
                try:
                    modifier = MenuItemModifier.objects.get(
                        id=mod_id, menu_item=menu_item
                    )
                    valid_modifiers.append(modifier)
                    modifier_total += modifier.price_adjustment
                except MenuItemModifier.DoesNotExist:
                    pass  # Skip invalid modifiers silently

            quantity = item_data["quantity"]
            line_total = (variant.price + modifier_total) * quantity
            total_price += line_total

            validated_items.append(
                {
                    "menu_item": menu_item,
                    "variant": variant,
                    "quantity": quantity,
                    "special_requests": item_data.get("special_requests", ""),
                    "modifiers": valid_modifiers,
                }
            )

        # Create order
        order = Order.objects.create(
            restaurant=restaurant,
            table_identifier=data.get("table_identifier") or None,
            status="confirmed",
            raw_input=data["raw_input"],
            parsed_json=request.data,
            language_detected=data.get("language", "en"),
            total_price=total_price,
        )

        for item_data in validated_items:
            order_item = OrderItem.objects.create(
                order=order,
                menu_item=item_data["menu_item"],
                variant=item_data["variant"],
                quantity=item_data["quantity"],
                special_requests=item_data["special_requests"],
            )
            order_item.modifiers.set(item_data["modifiers"])

        return Response(
            OrderResponseSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )
```

**Step 4: Add URL**

Add to `backend/orders/urls.py`:

```python
from orders.views import PublicMenuView, ParseOrderView, ConfirmOrderView

urlpatterns = [
    path("order/<slug:slug>/menu/", PublicMenuView.as_view(), name="public-menu"),
    path("order/<slug:slug>/parse/", ParseOrderView.as_view(), name="parse-order"),
    path("order/<slug:slug>/confirm/", ConfirmOrderView.as_view(), name="confirm-order"),
]
```

**Step 5: Run tests**

```bash
cd backend
pytest orders/tests/test_api_orders.py -v
```

Expected: All PASS.

**Step 6: Commit**

```bash
git add backend/orders/
git commit -m "feat: add order confirm endpoint with server-side validation and pricing"
```

---

## Task 4: Order Status Endpoint

**Files:**
- Modify: `backend/orders/views.py`
- Modify: `backend/orders/urls.py`
- Modify: `backend/orders/tests/test_api_orders.py`

**Step 1: Write the failing test**

Append to `backend/orders/tests/test_api_orders.py`:

```python
from orders.tests.factories import OrderFactory


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
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
pytest orders/tests/test_api_orders.py::TestOrderStatus -v
```

Expected: FAIL

**Step 3: Add status view**

Append to `backend/orders/views.py`:

```python
class OrderStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug, order_id):
        try:
            order = Order.objects.get(
                id=order_id, restaurant__slug=slug
            )
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(OrderResponseSerializer(order).data)
```

**Step 4: Add URL**

Update `backend/orders/urls.py`:

```python
from orders.views import (
    PublicMenuView, ParseOrderView, ConfirmOrderView, OrderStatusView,
)

urlpatterns = [
    path("order/<slug:slug>/menu/", PublicMenuView.as_view(), name="public-menu"),
    path("order/<slug:slug>/parse/", ParseOrderView.as_view(), name="parse-order"),
    path("order/<slug:slug>/confirm/", ConfirmOrderView.as_view(), name="confirm-order"),
    path(
        "order/<slug:slug>/status/<uuid:order_id>/",
        OrderStatusView.as_view(),
        name="order-status",
    ),
]
```

**Step 5: Run tests**

```bash
cd backend
pytest orders/tests/test_api_orders.py -v
```

Expected: All PASS.

**Step 6: Run full test suite**

```bash
cd backend
pytest -v
```

Expected: All tests PASS.

**Step 7: Commit**

```bash
git add backend/orders/
git commit -m "feat: add order status endpoint"
```
