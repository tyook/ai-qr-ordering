from django.urls import path

from restaurants.views import (
    CancelSubscriptionView,
    ConnectDashboardView,
    ConnectOnboardView,
    ConnectStatusView,
    CreateBillingPortalView,
    CreateCheckoutSessionView,
    CreateRestaurantView,
    FullMenuView,
    MenuCategoryDetailView,
    MenuCategoryListCreateView,
    MenuItemDetailView,
    MenuItemListCreateView,
    MyRestaurantsView,
    PayoutDetailView,
    PayoutListView,
    ReactivateSubscriptionView,
    RestaurantDetailView,
    RestaurantOrderListView,
    SubscriptionDetailView,
)

urlpatterns = [
    # Restaurants
    path("restaurants/me/", MyRestaurantsView.as_view(), name="my-restaurants"),
    path("restaurants/", CreateRestaurantView.as_view(), name="create-restaurant"),
    path("restaurants/<slug:slug>/", RestaurantDetailView.as_view(), name="restaurant-detail"),
    # Menu Categories
    path(
        "restaurants/<slug:slug>/categories/",
        MenuCategoryListCreateView.as_view(),
        name="menu-categories",
    ),
    path(
        "restaurants/<slug:slug>/categories/<int:pk>/",
        MenuCategoryDetailView.as_view(),
        name="menu-category-detail",
    ),
    # Menu Items
    path(
        "restaurants/<slug:slug>/items/",
        MenuItemListCreateView.as_view(),
        name="menu-items",
    ),
    path(
        "restaurants/<slug:slug>/items/<int:pk>/",
        MenuItemDetailView.as_view(),
        name="menu-item-detail",
    ),
    # Full Menu (Admin)
    path(
        "restaurants/<slug:slug>/menu/",
        FullMenuView.as_view(),
        name="full-menu",
    ),
    # Orders (Admin)
    path(
        "restaurants/<slug:slug>/orders/",
        RestaurantOrderListView.as_view(),
        name="restaurant-orders",
    ),
    # Subscription
    path(
        "restaurants/<slug:slug>/subscription/",
        SubscriptionDetailView.as_view(),
        name="subscription-detail",
    ),
    path(
        "restaurants/<slug:slug>/subscription/checkout/",
        CreateCheckoutSessionView.as_view(),
        name="subscription-checkout",
    ),
    path(
        "restaurants/<slug:slug>/subscription/portal/",
        CreateBillingPortalView.as_view(),
        name="subscription-portal",
    ),
    path(
        "restaurants/<slug:slug>/subscription/cancel/",
        CancelSubscriptionView.as_view(),
        name="subscription-cancel",
    ),
    path(
        "restaurants/<slug:slug>/subscription/reactivate/",
        ReactivateSubscriptionView.as_view(),
        name="subscription-reactivate",
    ),
    # Payouts
    path(
        "restaurants/<slug:slug>/payouts/",
        PayoutListView.as_view(),
        name="payout-list",
    ),
    path(
        "restaurants/<slug:slug>/payouts/<uuid:payout_id>/",
        PayoutDetailView.as_view(),
        name="payout-detail",
    ),
    # Connect (payout onboarding)
    path(
        "restaurants/<slug:slug>/connect/onboard/",
        ConnectOnboardView.as_view(),
        name="connect-onboard",
    ),
    path(
        "restaurants/<slug:slug>/connect/status/",
        ConnectStatusView.as_view(),
        name="connect-status",
    ),
    path(
        "restaurants/<slug:slug>/connect/dashboard/",
        ConnectDashboardView.as_view(),
        name="connect-dashboard",
    ),
]
