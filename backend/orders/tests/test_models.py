import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model

from orders.models import Order, OrderItem
from restaurants.models import (
    Restaurant, MenuCategory, MenuItem, MenuItemVariant, MenuItemModifier,
)

User = get_user_model()


@pytest.mark.django_db
class TestOrderModel:
    @pytest.fixture
    def menu_setup(self):
        owner = User.objects.create_user(
            email="orderowner@example.com", password="testpass123"
        )
        restaurant = Restaurant.objects.create(
            name="Order Test", slug="order-test", owner=owner
        )
        category = MenuCategory.objects.create(
            restaurant=restaurant, name="Mains", sort_order=1
        )
        item = MenuItem.objects.create(
            category=category, name="Burger", description="Beef burger", sort_order=1
        )
        variant = MenuItemVariant.objects.create(
            menu_item=item, label="Regular", price=Decimal("12.99"), is_default=True
        )
        modifier = MenuItemModifier.objects.create(
            menu_item=item, name="Extra Bacon", price_adjustment=Decimal("2.00")
        )
        return {
            "restaurant": restaurant,
            "item": item,
            "variant": variant,
            "modifier": modifier,
        }

    def test_create_order(self, menu_setup):
        order = Order.objects.create(
            restaurant=menu_setup["restaurant"],
            table_identifier="5",
            status="pending",
            raw_input="I want a burger with extra bacon",
            parsed_json={"items": []},
            language_detected="en",
            total_price=Decimal("14.99"),
        )
        assert order.status == "pending"
        assert str(order.id)  # UUID is set

    def test_create_order_item_with_modifiers(self, menu_setup):
        order = Order.objects.create(
            restaurant=menu_setup["restaurant"],
            raw_input="burger with bacon",
            parsed_json={},
            total_price=Decimal("14.99"),
        )
        order_item = OrderItem.objects.create(
            order=order,
            menu_item=menu_setup["item"],
            variant=menu_setup["variant"],
            quantity=1,
        )
        order_item.modifiers.add(menu_setup["modifier"])
        assert order_item.modifiers.count() == 1
        assert order_item.variant.price == Decimal("12.99")

    def test_order_status_choices(self, menu_setup):
        order = Order.objects.create(
            restaurant=menu_setup["restaurant"],
            raw_input="test",
            parsed_json={},
            total_price=Decimal("0"),
        )
        for status in ["pending", "confirmed", "preparing", "ready", "completed"]:
            order.status = status
            order.full_clean()  # Should not raise
