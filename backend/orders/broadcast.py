from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from orders.serializers import OrderResponseSerializer


def broadcast_order_to_kitchen(order):
    """Send order data to the kitchen WebSocket group."""
    channel_layer = get_channel_layer()
    data = OrderResponseSerializer(order).data
    # Convert UUIDs and Decimals to strings for JSON
    data["id"] = str(data["id"])
    data["total_price"] = str(data["total_price"])

    async_to_sync(channel_layer.group_send)(
        f"kitchen_{order.restaurant.slug}",
        {
            "type": "order_update",
            "data": data,
        },
    )
