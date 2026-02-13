import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser


class KitchenConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        self.group_name = f"kitchen_{self.slug}"

        user = self.scope.get("user", AnonymousUser())
        if isinstance(user, AnonymousUser) or not await self._is_restaurant_member(user):
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def order_update(self, event):
        """Handle order_update messages from the channel layer."""
        await self.send(text_data=json.dumps(event["data"]))

    @database_sync_to_async
    def _is_restaurant_member(self, user):
        from restaurants.models import Restaurant, RestaurantStaff

        try:
            restaurant = Restaurant.objects.get(slug=self.slug)
        except Restaurant.DoesNotExist:
            return False

        if restaurant.owner == user:
            return True
        return RestaurantStaff.objects.filter(user=user, restaurant=restaurant).exists()
