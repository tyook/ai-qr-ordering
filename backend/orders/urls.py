from django.urls import path
from orders.views import (
    PublicMenuView, ParseOrderView, ConfirmOrderView, OrderStatusView,
)

urlpatterns = [
    path("order/<slug:slug>/menu/", PublicMenuView.as_view(), name="public-menu"),
    path("order/<slug:slug>/parse/", ParseOrderView.as_view(), name="parse-order"),
    path("order/<slug:slug>/confirm/", ConfirmOrderView.as_view(), name="confirm-order"),
    path(
        "order/<slug:slug>/status/<uuid:order_id>/",
        OrderStatusView.as_view(),
        name="order-status",
    ),
]
