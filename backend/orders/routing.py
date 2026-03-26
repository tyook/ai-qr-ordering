from django.urls import re_path

from orders.consumers import CustomerOrderConsumer, KitchenConsumer

websocket_urlpatterns = [
    re_path(r"ws/kitchen/(?P<slug>[\w-]+)/$", KitchenConsumer.as_asgi()),
    re_path(
        r"ws/order/(?P<slug>[\w-]+)/(?P<order_id>[0-9a-f-]+)/$",
        CustomerOrderConsumer.as_asgi(),
    ),
]
