import pytest
from decimal import Decimal
from unittest.mock import patch

from rest_framework import status

from integrations.tests.factories import POSConnectionFactory
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemVariantFactory,
    RestaurantFactory,
)


@pytest.mark.django_db
class TestOrderFlowPOSDispatch:
    @pytest.fixture
    def restaurant_with_pos(self):
        restaurant = RestaurantFactory(slug="pos-test", tax_rate=Decimal("8.875"))
        POSConnectionFactory(restaurant=restaurant, pos_type="square", payment_mode="pos_collected")
        cat = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=cat, name="Burger")
        variant = MenuItemVariantFactory(
            menu_item=item, label="Regular", price=Decimal("12.99"), is_default=True
        )
        return {"restaurant": restaurant, "item": item, "variant": variant}

    @patch("orders.views.dispatch_order_to_pos")
    @patch("orders.broadcast.broadcast_order_to_kitchen")
    def test_confirm_order_dispatches_to_pos(self, mock_broadcast, mock_task, api_client, restaurant_with_pos):
        data = {
            "items": [
                {
                    "menu_item_id": restaurant_with_pos["item"].id,
                    "variant_id": restaurant_with_pos["variant"].id,
                    "quantity": 1,
                    "modifier_ids": [],
                }
            ],
            "raw_input": "one burger please",
            "table_identifier": "5",
        }
        response = api_client.post(
            "/api/order/pos-test/confirm/", data, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        mock_task.delay.assert_called_once()
        # Verify the order ID was passed
        call_args = mock_task.delay.call_args[0]
        assert call_args[0] == str(response.data["id"])
