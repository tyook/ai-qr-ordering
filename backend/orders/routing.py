from django.urls import re_path
from orders.consumers import KitchenConsumer

websocket_urlpatterns = [
    re_path(r"ws/kitchen/(?P<slug>[\w-]+)/$", KitchenConsumer.as_asgi()),
]
