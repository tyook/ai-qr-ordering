from django.urls import path
from customers.views import (
    CustomerRegisterView,
    CustomerLoginView,
    GoogleAuthView,
    AppleAuthView,
    CustomerTokenRefreshView,
    CustomerProfileView,
    CustomerOrderHistoryView,
)

urlpatterns = [
    path("auth/register/", CustomerRegisterView.as_view(), name="customer-register"),
    path("auth/login/", CustomerLoginView.as_view(), name="customer-login"),
    path("auth/google/", GoogleAuthView.as_view(), name="customer-google-auth"),
    path("auth/apple/", AppleAuthView.as_view(), name="customer-apple-auth"),
    path("auth/refresh/", CustomerTokenRefreshView.as_view(), name="customer-token-refresh"),
    path("profile/", CustomerProfileView.as_view(), name="customer-profile"),
    path("orders/", CustomerOrderHistoryView.as_view(), name="customer-orders"),
]
