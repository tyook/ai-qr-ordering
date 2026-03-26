import pytest
from decimal import Decimal
from unittest.mock import patch
from rest_framework import status

from integrations.tests.factories import POSConnectionFactory
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemVariantFactory,
    RestaurantFactory,
)


@pytest.mark.django_db
class TestPaymentModeAwareness:
    @pytest.fixture
    def pos_collected_restaurant(self):
        restaurant = RestaurantFactory(slug="pos-pay-test", tax_rate=Decimal("8.875"))
        POSConnectionFactory(
            restaurant=restaurant,
            pos_type="square",
            payment_mode="pos_collected",
        )
        cat = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=cat, name="Coffee")
        variant = MenuItemVariantFactory(
            menu_item=item, label="Regular", price=Decimal("4.50"), is_default=True
        )
        return {"restaurant": restaurant, "item": item, "variant": variant}

    def test_menu_endpoint_includes_payment_mode(self, api_client, pos_collected_restaurant):
        response = api_client.get("/api/order/pos-pay-test/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["payment_mode"] == "pos_collected"

    def test_menu_endpoint_defaults_to_stripe(self, api_client):
        RestaurantFactory(slug="no-pos-test")
        response = api_client.get("/api/order/no-pos-test/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["payment_mode"] == "stripe"

    @pytest.fixture
    def confirm_data(self, pos_collected_restaurant):
        return {
            "items": [
                {
                    "menu_item_id": pos_collected_restaurant["item"].id,
                    "variant_id": pos_collected_restaurant["variant"].id,
                    "quantity": 1,
                    "modifier_ids": [],
                }
            ],
            "raw_input": "one coffee",
            "table_identifier": "3",
        }

    @patch("orders.views.dispatch_order_to_pos")
    @patch("orders.broadcast.broadcast_order_to_kitchen")
    def test_confirm_order_with_pos_collected(self, mock_broadcast, mock_dispatch, api_client, pos_collected_restaurant, confirm_data):
        response = api_client.post(
            "/api/order/pos-pay-test/confirm/", confirm_data, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["payment_status"] == "pos_collected"
        assert response.data["status"] == "confirmed"

    @patch("orders.views.dispatch_order_to_pos")
    @patch("orders.broadcast.broadcast_order_to_kitchen")
    def test_confirm_pos_collected_dispatches_to_pos(
        self, mock_broadcast, mock_dispatch, api_client, pos_collected_restaurant, confirm_data
    ):
        response = api_client.post(
            "/api/order/pos-pay-test/confirm/", confirm_data, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        mock_dispatch.delay.assert_called_once_with(str(response.data["id"]))
