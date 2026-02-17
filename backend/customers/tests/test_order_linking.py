import pytest
from rest_framework.test import APIClient
from customers.tests.factories import CustomerFactory
from customers.authentication import CustomerRefreshToken
from restaurants.tests.factories import (
    RestaurantFactory, MenuCategoryFactory, MenuItemFactory, MenuItemVariantFactory,
)

pytestmark = pytest.mark.django_db


class TestOrderCustomerLinking:
    @pytest.fixture
    def restaurant_with_menu(self):
        restaurant = RestaurantFactory(slug="test-rest")
        category = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=category)
        variant = MenuItemVariantFactory(menu_item=item, price="10.00")
        return restaurant, item, variant

    def test_confirm_order_with_customer_name(self, api_client, restaurant_with_menu):
        restaurant, item, variant = restaurant_with_menu
        resp = api_client.post(f"/api/order/{restaurant.slug}/confirm/", {
            "items": [{"menu_item_id": item.id, "variant_id": variant.id, "quantity": 1}],
            "raw_input": "one item",
            "customer_name": "Alice",
            "customer_phone": "555-1234",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["customer_name"] == "Alice"
        assert resp.data["customer_phone"] == "555-1234"

    def test_confirm_order_auto_links_customer(self, api_client, restaurant_with_menu):
        restaurant, item, variant = restaurant_with_menu
        customer = CustomerFactory(email="alice@example.com")
        refresh = CustomerRefreshToken.for_customer(customer)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        resp = api_client.post(f"/api/order/{restaurant.slug}/confirm/", {
            "items": [{"menu_item_id": item.id, "variant_id": variant.id, "quantity": 1}],
            "raw_input": "one item",
            "customer_name": "Alice",
        }, format="json")
        assert resp.status_code == 201
        from orders.models import Order
        order = Order.objects.get(id=resp.data["id"])
        assert order.customer == customer

    def test_register_links_existing_order(self, api_client, restaurant_with_menu):
        restaurant, item, variant = restaurant_with_menu
        # Place order as guest
        resp = api_client.post(f"/api/order/{restaurant.slug}/confirm/", {
            "items": [{"menu_item_id": item.id, "variant_id": variant.id, "quantity": 1}],
            "raw_input": "one item",
            "customer_name": "Alice",
        }, format="json")
        order_id = resp.data["id"]

        # Register with link_order_id
        resp = api_client.post("/api/customer/auth/register/", {
            "email": "alice@example.com",
            "password": "securepass123",
            "name": "Alice",
            "link_order_id": order_id,
        }, format="json")
        assert resp.status_code == 201

        from orders.models import Order
        order = Order.objects.get(id=order_id)
        from customers.models import Customer
        customer = Customer.objects.get(email="alice@example.com")
        assert order.customer == customer
