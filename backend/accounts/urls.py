from django.urls import path

from accounts.views_onboarding import OnboardingCompleteView, OnboardingDismissView
from accounts.views import (
    AppleAuthView,
    CSRFTokenView,
    GoogleAuthView,
    LoginView,
    LogoutView,
    MeView,
    OrderDetailView,
    OrderHistoryView,
    PaymentMethodDetailView,
    PaymentMethodsView,
    RefreshView,
    RegisterView,
)

urlpatterns = [
    # Auth
    path("auth/csrf/", CSRFTokenView.as_view(), name="csrf-token"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/google/", GoogleAuthView.as_view(), name="google-auth"),
    path("auth/apple/", AppleAuthView.as_view(), name="apple-auth"),
    path("auth/refresh/", RefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    # Account
    path("account/orders/", OrderHistoryView.as_view(), name="account-orders"),
    path("account/orders/<uuid:order_id>/", OrderDetailView.as_view(), name="account-order-detail"),
    path("account/payment-methods/", PaymentMethodsView.as_view(), name="account-payment-methods"),
    path("account/payment-methods/<str:pm_id>/", PaymentMethodDetailView.as_view(), name="account-payment-method-detail"),
    # Onboarding
    path("account/onboarding/complete/", OnboardingCompleteView.as_view(), name="onboarding-complete"),
    path("account/onboarding/dismiss/", OnboardingDismissView.as_view(), name="onboarding-dismiss"),
]
