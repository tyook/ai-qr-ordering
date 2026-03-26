import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.utils import timezone

from config.asgi import application
from orders.models import Order
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import RestaurantFactory


@database_sync_to_async
def _create_restaurant_and_order(slug, status, confirmed_at=None):
    restaurant = RestaurantFactory(slug=slug)
    kwargs = {"restaurant": restaurant, "status": status}
    if confirmed_at is not None:
        kwargs["confirmed_at"] = confirmed_at
    order = OrderFactory(**kwargs)
    return restaurant, order


@database_sync_to_async
def _create_restaurant(slug):
    return RestaurantFactory(slug=slug)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCustomerOrderWebSocket:
    async def test_connect_with_valid_order(self):
        restaurant, order = await _create_restaurant_and_order(
            "ws-customer", Order.Status.CONFIRMED, confirmed_at=timezone.now()
        )
        communicator = WebsocketCommunicator(application, f"/ws/order/ws-customer/{order.id}/")
        connected, _ = await communicator.connect()
        assert connected

        response = await communicator.receive_json_from(timeout=5)
        assert response["status"] == "confirmed"
        assert "queue_position" in response
        await communicator.disconnect()

    async def test_reject_invalid_order(self):
        await _create_restaurant("ws-invalid")
        communicator = WebsocketCommunicator(
            application, "/ws/order/ws-invalid/00000000-0000-0000-0000-000000000000/"
        )
        connected, _ = await communicator.connect()
        assert not connected

    async def test_receive_queue_update(self):
        restaurant, order = await _create_restaurant_and_order(
            "ws-update", Order.Status.CONFIRMED, confirmed_at=timezone.now()
        )
        communicator = WebsocketCommunicator(application, f"/ws/order/ws-update/{order.id}/")
        connected, _ = await communicator.connect()
        assert connected

        await communicator.receive_json_from(timeout=5)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"customer_{order.id}",
            {
                "type": "queue_update",
                "data": {
                    "queue_position": 2,
                    "estimated_wait_minutes": 10,
                    "status": "preparing",
                    "busyness": "yellow",
                },
            },
        )

        response = await communicator.receive_json_from(timeout=5)
        assert response["queue_position"] == 2
        assert response["status"] == "preparing"
        await communicator.disconnect()

    async def test_completed_order_sends_final_state(self):
        restaurant, order = await _create_restaurant_and_order(
            "ws-complete", Order.Status.COMPLETED, confirmed_at=timezone.now()
        )
        communicator = WebsocketCommunicator(application, f"/ws/order/ws-complete/{order.id}/")
        connected, _ = await communicator.connect()
        assert connected

        response = await communicator.receive_json_from(timeout=5)
        assert response["status"] == "completed"
        await communicator.disconnect()

    async def test_pending_payment_no_queue_data(self):
        restaurant, order = await _create_restaurant_and_order(
            "ws-pending", Order.Status.PENDING_PAYMENT
        )
        communicator = WebsocketCommunicator(application, f"/ws/order/ws-pending/{order.id}/")
        connected, _ = await communicator.connect()
        assert connected

        response = await communicator.receive_json_from(timeout=5)
        assert response["status"] == "pending_payment"
        assert response.get("queue_position") is None
        await communicator.disconnect()
