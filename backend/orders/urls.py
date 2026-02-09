from django.urls import path
from orders.views import PublicMenuView

urlpatterns = [
    path("order/<slug:slug>/menu/", PublicMenuView.as_view(), name="public-menu"),
]
