from django.urls import path

from restaurants.views_menu_upload import (
    MenuItemImageUploadView,
    MenuUploadParseView,
    MenuUploadSaveView,
    MenuVersionActivateView,
    MenuVersionDetailView,
    MenuVersionListView,
)
from restaurants.views_team import (
    InvitationAcceptView,
    InvitationValidateView,
    InviteMemberView,
    MemberDetailView,
    MyRoleView,
    ResendInvitationView,
    RevokeInvitationView,
    TeamListView,
    TransferOwnershipView,
)
from restaurants.views import (
    AcceptingOrdersToggleView,
    BillingHistoryView,
    CancelSubscriptionView,
    ConnectDashboardView,
    ConnectOnboardView,
    ConnectStatusView,
    HallStatusView,
    HolidayOverrideDetailView,
    HolidayOverrideListCreateView,
    OnboardingConnectInitiateView,
    OnboardingConnectStatusView,
    OperatingHoursBulkView,
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
    RestaurantAnalyticsView,
    RestaurantDetailView,
    RestaurantOrderListView,
    SubscriptionDetailView,
    TableDetailView,
    TableListCreateView,
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
    path(
        "restaurants/<slug:slug>/subscription/invoices/",
        BillingHistoryView.as_view(),
        name="subscription-invoices",
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
    # Menu Upload & Versions
    path("restaurants/<slug:slug>/menu/upload/parse/", MenuUploadParseView.as_view(), name="menu-upload-parse"),
    path("restaurants/<slug:slug>/menu/upload/save/", MenuUploadSaveView.as_view(), name="menu-upload-save"),
    path("restaurants/<slug:slug>/menu/upload/image/", MenuItemImageUploadView.as_view(), name="menu-item-image-upload"),
    path("restaurants/<slug:slug>/menu/versions/", MenuVersionListView.as_view(), name="menu-versions"),
    path("restaurants/<slug:slug>/menu/versions/<int:pk>/", MenuVersionDetailView.as_view(), name="menu-version-detail"),
    path("restaurants/<slug:slug>/menu/versions/<int:pk>/activate/", MenuVersionActivateView.as_view(), name="menu-version-activate"),
    # Accepting Orders Toggle
    path(
        "restaurants/<slug:slug>/accepting-orders/",
        AcceptingOrdersToggleView.as_view(),
        name="accepting-orders-toggle",
    ),
    # Operating Hours
    path(
        "restaurants/<slug:slug>/operating-hours/",
        OperatingHoursBulkView.as_view(),
        name="operating-hours",
    ),
    # Holiday Overrides
    path(
        "restaurants/<slug:slug>/holiday-overrides/",
        HolidayOverrideListCreateView.as_view(),
        name="holiday-override-list-create",
    ),
    path(
        "restaurants/<slug:slug>/holiday-overrides/<int:pk>/",
        HolidayOverrideDetailView.as_view(),
        name="holiday-override-detail",
    ),
    # Tables
    path(
        "restaurants/<slug:slug>/tables/",
        TableListCreateView.as_view(),
        name="table-list-create",
    ),
    path(
        "restaurants/<slug:slug>/tables/<uuid:pk>/",
        TableDetailView.as_view(),
        name="table-detail",
    ),
    # Hall Status
    path(
        "restaurants/<slug:slug>/hall-status/",
        HallStatusView.as_view(),
        name="hall-status",
    ),
    # Analytics
    path(
        "restaurants/<slug:slug>/analytics/",
        RestaurantAnalyticsView.as_view(),
        name="restaurant-analytics",
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
    path(
        "restaurants/<slug:slug>/connect/onboarding-initiate/",
        OnboardingConnectInitiateView.as_view(),
        name="connect-onboarding-initiate",
    ),
    path(
        "restaurants/<slug:slug>/connect/onboarding-status/",
        OnboardingConnectStatusView.as_view(),
        name="connect-onboarding-status",
    ),
    # Team Management
    path("restaurants/<slug:slug>/team/", TeamListView.as_view(), name="team-list"),
    path("restaurants/<slug:slug>/team/invite/", InviteMemberView.as_view(), name="team-invite"),
    path("restaurants/<slug:slug>/team/<int:staff_id>/", MemberDetailView.as_view(), name="team-member-detail"),
    path("restaurants/<slug:slug>/team/transfer-ownership/", TransferOwnershipView.as_view(), name="team-transfer-ownership"),
    path("restaurants/<slug:slug>/team/invitations/<uuid:invitation_id>/resend/", ResendInvitationView.as_view(), name="team-resend-invitation"),
    path("restaurants/<slug:slug>/team/invitations/<uuid:invitation_id>/", RevokeInvitationView.as_view(), name="team-revoke-invitation"),
    path("restaurants/<slug:slug>/my-role/", MyRoleView.as_view(), name="my-role"),
    # Invitations (public)
    path("invitations/<str:token>/", InvitationValidateView.as_view(), name="invitation-validate"),
    path("invitations/<str:token>/accept/", InvitationAcceptView.as_view(), name="invitation-accept"),
]
