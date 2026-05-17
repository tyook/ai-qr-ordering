from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from rest_framework import status
from orders.models import Order, Tab
from orders.tests.factories import OrderFactory, TabFactory
from restaurants.tests.factories import (
    MenuCategoryFactory, MenuItemFactory, MenuItemVariantFactory,
    MenuVersionFactory, RestaurantFactory, RestaurantStaffFactory, UserFactory,
)

@pytest.mark.django_db
class TestGetTab:
    def test_get_open_tab(self):
        restaurant = RestaurantFactory(slug="tab-get-test", payment_model="tab")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3")
        OrderFactory(
            restaurant=restaurant, tab=tab,
            subtotal=Decimal("10.00"), tax_amount=Decimal("0.89"),
            total_price=Decimal("10.89"), status="confirmed",
        )
        from rest_framework.test import APIClient
        client = APIClient()
        response = client.get("/api/order/tab-get-test/tab/", {"table": "A3"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["table_identifier"] == "A3"
        assert response.data["status"] == "open"
        assert len(response.data["orders"]) == 1
        assert response.data["total"] == "10.89"

    def test_get_tab_no_tab_returns_404(self):
        RestaurantFactory(slug="tab-get-empty", payment_model="tab")
        from rest_framework.test import APIClient
        client = APIClient()
        response = client.get("/api/order/tab-get-empty/tab/", {"table": "A3"})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_tab_requires_table_param(self):
        RestaurantFactory(slug="tab-get-no-table", payment_model="tab")
        from rest_framework.test import APIClient
        client = APIClient()
        response = client.get("/api/order/tab-get-no-table/tab/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
class TestTabOrder:
    @pytest.fixture
    def menu_setup(self):
        restaurant = RestaurantFactory(slug="tab-order-test", payment_model="tab")
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        item = MenuItemFactory(category=cat, name="Burger")
        variant = MenuItemVariantFactory(menu_item=item, label="Regular", price=Decimal("10.00"), is_default=True)
        return {"restaurant": restaurant, "item": item, "variant": variant}

    def test_place_order_on_tab(self, api_client, menu_setup):
        response = api_client.post(
            "/api/order/tab-order-test/tab/order/",
            {"items": [{"menu_item_id": menu_setup["item"].id, "variant_id": menu_setup["variant"].id, "quantity": 1}],
             "raw_input": "One burger", "table_identifier": "A3", "language": "en"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "confirmed"
        assert response.data["payment_status"] == "deferred"
        assert "tab" in response.data
        tab = Tab.objects.get(id=response.data["tab"]["id"])
        assert tab.table_identifier == "A3"
        assert tab.orders.count() == 1

    def test_second_order_uses_same_tab(self, api_client, menu_setup):
        payload = {
            "items": [{"menu_item_id": menu_setup["item"].id, "variant_id": menu_setup["variant"].id, "quantity": 1}],
            "raw_input": "One burger", "table_identifier": "A3", "language": "en",
        }
        r1 = api_client.post("/api/order/tab-order-test/tab/order/", payload, format="json")
        r2 = api_client.post("/api/order/tab-order-test/tab/order/", payload, format="json")
        assert r1.data["tab"]["id"] == r2.data["tab"]["id"]
        tab = Tab.objects.get(id=r1.data["tab"]["id"])
        assert tab.orders.count() == 2

    def test_tab_order_rejected_for_upfront_restaurant(self, api_client):
        restaurant = RestaurantFactory(slug="upfront-test", payment_model="upfront")
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        item = MenuItemFactory(category=cat)
        variant = MenuItemVariantFactory(menu_item=item, price=Decimal("10.00"))
        response = api_client.post(
            "/api/order/upfront-test/tab/order/",
            {"items": [{"menu_item_id": item.id, "variant_id": variant.id, "quantity": 1}],
             "raw_input": "test", "table_identifier": "A1", "language": "en"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
class TestTabClose:
    def test_customer_can_close_tab(self, api_client):
        restaurant = RestaurantFactory(slug="tab-close-test", payment_model="tab")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3")
        response = api_client.post(
            "/api/order/tab-close-test/tab/close/",
            {"table_identifier": "A3"}, format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        tab.refresh_from_db()
        assert tab.status == "closing"

    def test_staff_can_close_tab(self, api_client):
        restaurant = RestaurantFactory(slug="tab-staff-close")
        staff_user = UserFactory()
        RestaurantStaffFactory(user=staff_user, restaurant=restaurant, role="admin")
        tab = TabFactory(restaurant=restaurant, table_identifier="B1")
        api_client.force_authenticate(user=staff_user)
        response = api_client.post(f"/api/kitchen/tab/{tab.id}/close/")
        assert response.status_code == status.HTTP_200_OK
        tab.refresh_from_db()
        assert tab.status == "closing"

    def test_non_staff_cannot_use_kitchen_close(self, api_client):
        restaurant = RestaurantFactory(slug="tab-nostaff-close")
        tab = TabFactory(restaurant=restaurant)
        outsider = UserFactory()
        api_client.force_authenticate(user=outsider)
        response = api_client.post(f"/api/kitchen/tab/{tab.id}/close/")
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
