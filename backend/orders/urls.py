from django.urls import path
from orders.views import PublicMenuView, ParseOrderView

urlpatterns = [
    path("order/<slug:slug>/menu/", PublicMenuView.as_view(), name="public-menu"),
    path("order/<slug:slug>/parse/", ParseOrderView.as_view(), name="parse-order"),
]
