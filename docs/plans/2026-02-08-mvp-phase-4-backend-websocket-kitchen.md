# Phase 4: Backend WebSocket & Kitchen API

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement WebSocket consumer for real-time kitchen order feed and the kitchen order status update endpoint.

**Architecture:** Django Channels WebSocket consumer sends new/updated orders to connected kitchen clients. On order confirm, a signal broadcasts to the kitchen group. Kitchen staff update order status via REST, which also triggers a WebSocket broadcast.

**Tech Stack:** Django Channels, channels-redis, pytest, pytest-asyncio

**Depends on:** Phase 1 (models), Phase 3 (order endpoints)

---

## Task 1: Kitchen WebSocket Consumer

**Files:**
- Create: `backend/orders/consumers.py`
- Modify: `backend/orders/routing.py`
- Create: `backend/orders/tests/test_websocket.py`

**Step 1: Install test dependency**

Add to `backend/requirements.txt`:

```txt
pytest-asyncio==0.25.3
```

Install: `pip install pytest-asyncio`

**Step 2: Write the failing test**

Create `backend/orders/tests/test_websocket.py`:

```python
import pytest
import json
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from config.asgi import application
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestKitchenWebSocket:
    async def test_connect_to_kitchen(self):
        restaurant = await self._create_restaurant("ws-test")
        communicator = WebsocketCommunicator(
            application, f"/ws/kitchen/{restaurant.slug}/"
        )
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async def test_receive_order_broadcast(self):
        restaurant = await self._create_restaurant("ws-broadcast")
        communicator = WebsocketCommunicator(
            application, f"/ws/kitchen/{restaurant.slug}/"
        )
        connected, _ = await communicator.connect()
        assert connected

        # Simulate broadcasting an order
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"kitchen_{restaurant.slug}",
            {
                "type": "order_update",
                "data": {
                    "id": "test-uuid",
                    "status": "confirmed",
                    "items": [],
                },
            },
        )

        response = await communicator.receive_json_from(timeout=5)
        assert response["id"] == "test-uuid"
        assert response["status"] == "confirmed"
        await communicator.disconnect()

    @staticmethod
    async def _create_restaurant(slug):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        from restaurants.models import Restaurant
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def create():
            owner = User.objects.create_user(
                email=f"{slug}@example.com", password="testpass123"
            )
            return Restaurant.objects.create(
                name=f"WS Test {slug}", slug=slug, owner=owner
            )

        return await create()
```

**Step 3: Run test to verify it fails**

```bash
cd backend
pytest orders/tests/test_websocket.py -v
```

Expected: FAIL (consumer not implemented)

**Step 4: Implement the WebSocket consumer**

Create `backend/orders/consumers.py`:

```python
import json
from channels.generic.websocket import AsyncWebsocketConsumer


class KitchenConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        self.group_name = f"kitchen_{self.slug}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def order_update(self, event):
        """Handle order_update messages from the channel layer."""
        await self.send(text_data=json.dumps(event["data"]))
```

**Step 5: Update routing**

Replace `backend/orders/routing.py`:

```python
from django.urls import re_path
from orders.consumers import KitchenConsumer

websocket_urlpatterns = [
    re_path(r"ws/kitchen/(?P<slug>[\w-]+)/$", KitchenConsumer.as_asgi()),
]
```

**Step 6: Run tests**

```bash
cd backend
pytest orders/tests/test_websocket.py -v
```

Expected: All PASS.

**Step 7: Commit**

```bash
git add backend/orders/
git commit -m "feat: add kitchen WebSocket consumer for real-time order updates"
```

---

## Task 2: Broadcast on Order Confirmation

**Files:**
- Create: `backend/orders/signals.py`
- Modify: `backend/orders/apps.py`
- Modify: `backend/orders/views.py`

**Step 1: Create the broadcast utility**

Create `backend/orders/broadcast.py`:

```python
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
```

**Step 2: Call broadcast from ConfirmOrderView**

In `backend/orders/views.py`, at the end of the `ConfirmOrderView.post` method, before the return statement, add:

```python
from orders.broadcast import broadcast_order_to_kitchen

# Add at end of ConfirmOrderView.post, before return:
        broadcast_order_to_kitchen(order)
```

**Step 3: Commit**

```bash
git add backend/orders/
git commit -m "feat: broadcast confirmed orders to kitchen WebSocket"
```

---

## Task 3: Kitchen Order Status Update Endpoint

**Files:**
- Modify: `backend/orders/views.py`
- Modify: `backend/orders/urls.py`
- Modify: `backend/orders/tests/test_api_orders.py`

**Step 1: Write the failing test**

Append to `backend/orders/tests/test_api_orders.py`:

```python
from restaurants.tests.factories import UserFactory, RestaurantStaffFactory


@pytest.mark.django_db
class TestKitchenOrderUpdate:
    @pytest.fixture
    def kitchen_setup(self):
        restaurant = RestaurantFactory(slug="kitchen-test")
        kitchen_user = UserFactory(role="staff")
        RestaurantStaffFactory(
            user=kitchen_user, restaurant=restaurant, role="kitchen"
        )
        order = OrderFactory(restaurant=restaurant, status="confirmed")
        return restaurant, kitchen_user, order

    def test_kitchen_staff_can_update_status(self, api_client, kitchen_setup):
        restaurant, kitchen_user, order = kitchen_setup
        api_client.force_authenticate(user=kitchen_user)
        response = api_client.patch(
            f"/api/kitchen/orders/{order.id}/",
            {"status": "preparing"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "preparing"

    def test_non_staff_cannot_update(self, api_client, kitchen_setup):
        _, _, order = kitchen_setup
        outsider = UserFactory()
        api_client.force_authenticate(user=outsider)
        response = api_client.patch(
            f"/api/kitchen/orders/{order.id}/",
            {"status": "preparing"},
            format="json",
        )
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]

    def test_invalid_status_transition_rejected(self, api_client, kitchen_setup):
        restaurant, kitchen_user, order = kitchen_setup
        api_client.force_authenticate(user=kitchen_user)
        # Can't go from confirmed directly to completed
        response = api_client.patch(
            f"/api/kitchen/orders/{order.id}/",
            {"status": "completed"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_cannot_update(self, api_client, kitchen_setup):
        _, _, order = kitchen_setup
        response = api_client.patch(
            f"/api/kitchen/orders/{order.id}/",
            {"status": "preparing"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

> **Note:** You need to add `RestaurantStaffFactory` to the imports if not already done in Phase 2.

**Step 2: Run tests to verify they fail**

```bash
cd backend
pytest orders/tests/test_api_orders.py::TestKitchenOrderUpdate -v
```

Expected: FAIL

**Step 3: Implement the kitchen order update view**

Append to `backend/orders/views.py`:

```python
from rest_framework.permissions import IsAuthenticated
from restaurants.models import RestaurantStaff

VALID_TRANSITIONS = {
    "confirmed": ["preparing"],
    "preparing": ["ready"],
    "ready": ["completed"],
}


class KitchenOrderUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check user is staff at this restaurant
        is_owner = order.restaurant.owner == request.user
        is_staff = RestaurantStaff.objects.filter(
            user=request.user, restaurant=order.restaurant
        ).exists()
        if not is_owner and not is_staff:
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get("status")
        allowed = VALID_TRANSITIONS.get(order.status, [])
        if new_status not in allowed:
            return Response(
                {
                    "detail": f"Cannot transition from '{order.status}' to '{new_status}'. "
                    f"Allowed: {allowed}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = new_status
        order.save()

        # Broadcast status change to kitchen
        broadcast_order_to_kitchen(order)

        return Response(OrderResponseSerializer(order).data)
```

**Step 4: Add URL**

Add to `backend/orders/urls.py`:

```python
from orders.views import KitchenOrderUpdateView

# Add to urlpatterns:
    path(
        "kitchen/orders/<uuid:order_id>/",
        KitchenOrderUpdateView.as_view(),
        name="kitchen-order-update",
    ),
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
git commit -m "feat: add kitchen order status update endpoint with valid transitions and WebSocket broadcast"
```
