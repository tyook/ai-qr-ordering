from django.urls import path
from customers.views import (
    CustomerRegisterView,
    CustomerLoginView,
    CustomerTokenRefreshView,
    CustomerProfileView,
    CustomerOrderHistoryView,
)

urlpatterns = [
    path("auth/register/", CustomerRegisterView.as_view(), name="customer-register"),
    path("auth/login/", CustomerLoginView.as_view(), name="customer-login"),
    path("auth/refresh/", CustomerTokenRefreshView.as_view(), name="customer-token-refresh"),
    path("profile/", CustomerProfileView.as_view(), name="customer-profile"),
    path("orders/", CustomerOrderHistoryView.as_view(), name="customer-orders"),
]
