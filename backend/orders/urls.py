from django.urls import path

from orders.views import (
    ConfirmOrderView,
    ConfirmPaymentView,
    CreatePaymentView,
    KitchenOrderUpdateView,
    OrderQueueView,
    OrderStatusView,
    ParseOrderView,
    PublicMenuView,
    QueueInfoView,
    SaveCardConsentView,
    StripeConnectWebhookView,
    StripeWebhookView,
)

urlpatterns = [
    path("order/<slug:slug>/menu/", PublicMenuView.as_view(), name="public-menu"),
    path("order/<slug:slug>/parse/", ParseOrderView.as_view(), name="parse-order"),
    path("order/<slug:slug>/confirm/", ConfirmOrderView.as_view(), name="confirm-order"),
    path("order/<slug:slug>/create-payment/", CreatePaymentView.as_view(), name="create-payment"),
    path("order/<slug:slug>/save-card/<uuid:order_id>/", SaveCardConsentView.as_view(), name="save-card-consent"),
    path(
        "order/<slug:slug>/confirm-payment/<uuid:order_id>/",
        ConfirmPaymentView.as_view(),
        name="confirm-payment",
    ),
    path(
        "order/<slug:slug>/status/<uuid:order_id>/",
        OrderStatusView.as_view(),
        name="order-status",
    ),
    path(
        "kitchen/orders/<uuid:order_id>/",
        KitchenOrderUpdateView.as_view(),
        name="kitchen-order-update",
    ),
    path("order/<slug:slug>/queue-info/", QueueInfoView.as_view(), name="queue-info"),
    path("order/<slug:slug>/queue/<uuid:order_id>/", OrderQueueView.as_view(), name="order-queue"),
    path("webhooks/stripe/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("webhooks/stripe-connect/", StripeConnectWebhookView.as_view(), name="stripe-connect-webhook"),
]
