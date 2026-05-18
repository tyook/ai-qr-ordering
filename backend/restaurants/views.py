from django.conf import settings
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.models import (
    HolidayOverride,
    MenuCategory,
    MenuItem,
    MenuVersion,
    OperatingHours,
    Restaurant,
    RestaurantStaff,
    Subscription,
)
from restaurants.permissions import HasActiveSubscription, IsRestaurantAdmin, HasPermission
from restaurants.serializers import (
    HolidayOverrideSerializer,
    MenuCategorySerializer,
    MenuItemSerializer,
    OperatingHoursSerializer,
    RestaurantSerializer,
    SubscriptionSerializer,
)
from restaurants.services import RestaurantService


class MyRestaurantsView(generics.ListAPIView):
    """GET /api/restaurants/me/ - List restaurants I own or have staff access to."""

    serializer_class = RestaurantSerializer

    def get_queryset(self):
        return RestaurantService.get_user_restaurants(self.request.user)


class CreateRestaurantView(generics.CreateAPIView):
    """POST /api/restaurants/ - Create a new restaurant."""

    serializer_class = RestaurantSerializer


class RestaurantDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/restaurants/:slug/ - View or update a restaurant."""

    serializer_class = RestaurantSerializer
    lookup_field = "slug"

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsRestaurantAdmin()]
        return [IsAuthenticated(), HasActiveSubscription()]

    def get_queryset(self):
        return RestaurantService.get_user_restaurants(self.request.user)


class RestaurantMixin:
    """Mixin to resolve restaurant from URL slug and check access."""

    def get_permissions(self):
        return [IsAuthenticated(), HasActiveSubscription()]

    def get_restaurant(self):
        slug = self.kwargs["slug"]
        user = self.request.user
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist as err:
            from rest_framework.exceptions import NotFound

            raise NotFound("Restaurant not found.") from err

        is_owner = restaurant.owner == user
        is_staff = RestaurantStaff.objects.filter(user=user, restaurant=restaurant).exists()
        if not is_owner and not is_staff:
            from rest_framework.exceptions import NotFound

            raise NotFound("Restaurant not found.")

        return restaurant


class MenuCategoryListCreateView(RestaurantMixin, generics.ListCreateAPIView):
    serializer_class = MenuCategorySerializer

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), HasPermission("menu_edit")]
        return [IsAuthenticated(), HasActiveSubscription()]

    def _get_active_version(self, restaurant):
        return restaurant.menu_versions.filter(is_active=True).first()

    def get_queryset(self):
        restaurant = self.get_restaurant()
        active_version = self._get_active_version(restaurant)
        if not active_version:
            return MenuCategory.objects.none()
        return MenuCategory.objects.filter(version=active_version)

    def perform_create(self, serializer):
        restaurant = self.get_restaurant()
        active_version = self._get_active_version(restaurant)
        if not active_version:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("No active menu version found. Please create and activate a menu version first.")
        serializer.save(version=active_version)


class MenuCategoryDetailView(RestaurantMixin, generics.RetrieveUpdateAPIView):
    serializer_class = MenuCategorySerializer
    lookup_field = "pk"

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), HasPermission("menu_edit")]
        return [IsAuthenticated(), HasActiveSubscription()]

    def get_queryset(self):
        restaurant = self.get_restaurant()
        active_version = restaurant.menu_versions.filter(is_active=True).first()
        if not active_version:
            return MenuCategory.objects.none()
        return MenuCategory.objects.filter(version=active_version)


class MenuItemListCreateView(RestaurantMixin, generics.ListCreateAPIView):
    serializer_class = MenuItemSerializer

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), HasPermission("menu_edit")]
        return [IsAuthenticated(), HasActiveSubscription()]

    def _get_active_version(self, restaurant):
        return restaurant.menu_versions.filter(is_active=True).first()

    def get_queryset(self):
        restaurant = self.get_restaurant()
        active_version = self._get_active_version(restaurant)
        if not active_version:
            return MenuItem.objects.none()
        return MenuItem.objects.filter(category__version=active_version).prefetch_related("variants", "modifiers")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        restaurant = self.get_restaurant()
        ctx["restaurant"] = restaurant
        ctx["active_version"] = self._get_active_version(restaurant)
        return ctx

    def perform_create(self, serializer):
        serializer.save()


class MenuItemDetailView(RestaurantMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MenuItemSerializer
    lookup_field = "pk"

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), HasPermission("menu_edit")]
        return [IsAuthenticated(), HasActiveSubscription()]

    def _get_active_version(self, restaurant):
        return restaurant.menu_versions.filter(is_active=True).first()

    def get_queryset(self):
        restaurant = self.get_restaurant()
        active_version = self._get_active_version(restaurant)
        if not active_version:
            return MenuItem.objects.none()
        return MenuItem.objects.filter(category__version=active_version).prefetch_related("variants", "modifiers")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        restaurant = self.get_restaurant()
        ctx["restaurant"] = restaurant
        ctx["active_version"] = self._get_active_version(restaurant)
        return ctx

    def perform_destroy(self, instance):
        instance.delete()


class FullMenuView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/menu/ - Full menu including inactive items."""

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        return Response(RestaurantService.get_full_menu(restaurant))


class RestaurantOrderListView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/orders/ - List all orders for a restaurant."""

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        return Response(RestaurantService.get_restaurant_orders(restaurant))


class SubscriptionDetailView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/subscription/ - View subscription details."""

    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(SubscriptionSerializer(subscription).data)


class CreateCheckoutSessionView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/checkout/ - Create Stripe Checkout session."""

    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        plan = request.data.get("plan", "starter")
        interval = request.data.get("interval", "monthly")
        checkout_url = RestaurantService.create_checkout_session(
            restaurant, request.user, plan, interval
        )
        return Response({"checkout_url": checkout_url})


class CreateBillingPortalView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/portal/ - Open Stripe Billing Portal."""

    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        portal_url = RestaurantService.create_billing_portal(restaurant)
        return Response({"portal_url": portal_url})


class CancelSubscriptionView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/cancel/ - Cancel subscription at period end."""

    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        subscription = RestaurantService.cancel_subscription(restaurant)
        return Response(SubscriptionSerializer(subscription).data)


class ReactivateSubscriptionView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/reactivate/ - Undo pending cancellation."""

    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        subscription = RestaurantService.reactivate_subscription(restaurant)
        return Response(SubscriptionSerializer(subscription).data)


class BillingHistoryView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/subscription/invoices/ - List Stripe invoices."""

    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return Response([])

        if not subscription.stripe_customer_id:
            return Response([])

        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        invoices = stripe.Invoice.list(
            customer=subscription.stripe_customer_id,
            limit=12,
        )

        result = []
        for inv in invoices["data"]:
            # Extract plan name from line items
            plan_name = ""
            lines = inv.get("lines", {}).get("data", [])
            if lines:
                price_meta = lines[0].get("price", {}).get("metadata", {})
                plan_name = price_meta.get("plan", "").title()
                if not plan_name:
                    plan_name = lines[0].get("description", "")

            result.append({
                "id": inv["id"],
                "date": inv["created"],
                "amount": inv["amount_paid"],
                "currency": inv["currency"],
                "status": inv["status"],
                "plan": plan_name,
                "receipt_url": inv.get("hosted_invoice_url", ""),
            })

        return Response(result)


from rest_framework.pagination import PageNumberPagination
from restaurants.serializers import PayoutListSerializer, PayoutDetailSerializer
from restaurants.models import Payout


class PayoutPagination(PageNumberPagination):
    page_size = 20


class PayoutListView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        payouts = Payout.objects.filter(restaurant=restaurant)
        paginator = PayoutPagination()
        page = paginator.paginate_queryset(payouts, request)
        serializer = PayoutListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class PayoutDetailView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def get(self, request, slug, payout_id):
        restaurant = self.get_restaurant()
        try:
            payout = Payout.objects.get(id=payout_id, restaurant=restaurant)
        except Payout.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Payout not found")
        serializer = PayoutDetailSerializer(payout)
        return Response(serializer.data)


from restaurants.services import ConnectService


class ConnectOnboardView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        result = ConnectService.create_onboarding_link(restaurant)
        return Response(result)


class ConnectStatusView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        result = ConnectService.get_connect_status(restaurant)
        return Response(result)


class ConnectDashboardView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        result = ConnectService.create_dashboard_link(restaurant)
        return Response(result)


class OnboardingConnectInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug, owner=request.user)
        except Restaurant.DoesNotExist:
            raise NotFound("Restaurant not found.")

        return_url = request.data.get("return_url", "")
        refresh_url = request.data.get("refresh_url", "")
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")

        if not return_url.startswith(frontend_url) or not refresh_url.startswith(frontend_url):
            return Response(
                {"error": "Invalid return URL"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = ConnectService.create_onboarding_link(
            restaurant, return_url=return_url, refresh_url=refresh_url
        )
        return Response(result)


class OnboardingConnectStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug, owner=request.user)
        except Restaurant.DoesNotExist:
            raise NotFound("Restaurant not found.")

        result = ConnectService.get_connect_status(restaurant)
        return Response(result)


from restaurants.models import Table
from restaurants.serializers import TableSerializer


class TableListCreateView(RestaurantMixin, generics.ListCreateAPIView):
    """GET/POST /api/restaurants/:slug/tables/"""

    serializer_class = TableSerializer
    pagination_class = None

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsRestaurantAdmin()]
        return [IsAuthenticated(), HasActiveSubscription()]

    def get_queryset(self):
        restaurant = self.get_restaurant()
        return Table.objects.filter(restaurant=restaurant)

    def perform_create(self, serializer):
        restaurant = self.get_restaurant()
        serializer.save(restaurant=restaurant)


class TableDetailView(RestaurantMixin, generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/restaurants/:slug/tables/:id/"""

    serializer_class = TableSerializer
    lookup_field = "pk"

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsRestaurantAdmin()]
        return [IsAuthenticated(), HasActiveSubscription()]

    def get_queryset(self):
        restaurant = self.get_restaurant()
        return Table.objects.filter(restaurant=restaurant)


class HallStatusView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/hall-status/ - Table grid with active tab info."""

    def get(self, request, slug):
        from orders.models import Tab

        restaurant = self.get_restaurant()
        tables = Table.objects.filter(restaurant=restaurant, is_active=True).order_by("number")

        # Fetch all open tabs for this restaurant, keyed by table_identifier
        open_tabs = (
            Tab.objects.filter(restaurant=restaurant, status="open")
            .prefetch_related("orders__items__menu_item", "orders__items__variant")
        )
        tab_by_table = {tab.table_identifier: tab for tab in open_tabs}

        result = []
        for table in tables:
            tab = tab_by_table.get(table.number)
            table_data = {
                "id": str(table.id),
                "name": table.name,
                "number": table.number,
                "has_tab": tab is not None,
                "tab": None,
            }
            if tab:
                first_order = tab.orders.order_by("created_at").first()
                table_data["tab"] = {
                    "id": str(tab.id),
                    "status": tab.status,
                    "total": f"{tab.total:.2f}",
                    "order_count": tab.orders.count(),
                    "opened_at": tab.opened_at.isoformat(),
                    "first_order_at": first_order.created_at.isoformat() if first_order else None,
                    "orders": [
                        {
                            "id": str(order.id),
                            "status": order.status,
                            "total_price": f"{order.total_price:.2f}",
                            "created_at": order.created_at.isoformat(),
                            "items": [
                                {
                                    "id": item.id,
                                    "name": item.menu_item.name,
                                    "variant_label": item.variant.label,
                                    "quantity": item.quantity,
                                }
                                for item in order.items.all()
                            ],
                        }
                        for order in tab.orders.order_by("created_at")
                    ],
                }
            result.append(table_data)

        return Response(result)


class RestaurantAnalyticsView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/analytics/?period=7d|30d|90d|custom&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD"""

    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def get(self, request, slug):
        from datetime import datetime, timedelta

        from django.db.models import Avg, Count, Sum
        from django.db.models.functions import ExtractHour, TruncDate
        from django.utils import timezone

        from orders.models import Order, OrderItem

        restaurant = self.get_restaurant()

        period_str = request.query_params.get("period", "30d")
        start_date_param = request.query_params.get("start_date")
        end_date_param = request.query_params.get("end_date")

        now = timezone.now()

        if period_str == "custom" and start_date_param and end_date_param:
            start_date = timezone.make_aware(
                datetime.strptime(start_date_param, "%Y-%m-%d")
            )
            end_date = timezone.make_aware(
                datetime.strptime(end_date_param, "%Y-%m-%d")
            ) + timedelta(days=1)  # include the end date fully
            days = (end_date - start_date).days
            prev_start = start_date - timedelta(days=days)
        else:
            days_map = {"7d": 7, "30d": 30, "90d": 90}
            days = days_map.get(period_str, 30)
            end_date = now
            start_date = now - timedelta(days=days)
            prev_start = start_date - timedelta(days=days)

        completed_statuses = [Order.Status.COMPLETED, Order.Status.CONFIRMED]
        base_qs = Order.objects.filter(
            restaurant=restaurant,
            status__in=completed_statuses,
        )

        current_qs = base_qs.filter(created_at__gte=start_date, created_at__lt=end_date)
        prev_qs = base_qs.filter(created_at__gte=prev_start, created_at__lt=start_date)

        # Summary metrics
        current_agg = current_qs.aggregate(
            order_count=Count("id"),
            total_revenue=Sum("total_price"),
            total_tax=Sum("tax_amount"),
            avg_order_value=Avg("total_price"),
        )
        prev_agg = prev_qs.aggregate(
            order_count=Count("id"),
            total_revenue=Sum("total_price"),
        )

        # Daily order volume
        daily_orders = list(
            current_qs.annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"), revenue=Sum("total_price"))
            .order_by("date")
        )
        for entry in daily_orders:
            entry["date"] = entry["date"].isoformat()
            entry["revenue"] = float(entry["revenue"] or 0)

        # Top 5 items
        top_items = list(
            OrderItem.objects.filter(order__in=current_qs)
            .values("menu_item__name")
            .annotate(total_quantity=Sum("quantity"))
            .order_by("-total_quantity")[:5]
        )

        # Peak hours
        hourly = list(
            current_qs.annotate(hour=ExtractHour("created_at"))
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )
        peak_hours = {entry["hour"]: entry["count"] for entry in hourly}
        peak_hours_full = [{"hour": h, "orders": peak_hours.get(h, 0)} for h in range(24)]

        # Orders by payment type
        payment_breakdown = list(
            current_qs.values("payment_status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return Response(
            {
                "period": period_str,
                "summary": {
                    "order_count": current_agg["order_count"],
                    "total_revenue": float(current_agg["total_revenue"] or 0),
                    "total_tax": float(current_agg["total_tax"] or 0),
                    "net_revenue": float(
                        (current_agg["total_revenue"] or 0)
                        - (current_agg["total_tax"] or 0)
                    ),
                    "avg_order_value": float(current_agg["avg_order_value"] or 0),
                    "prev_order_count": prev_agg["order_count"],
                    "prev_total_revenue": float(prev_agg["total_revenue"] or 0),
                },
                "daily_orders": daily_orders,
                "top_items": [
                    {"name": item["menu_item__name"], "quantity": item["total_quantity"]}
                    for item in top_items
                ],
                "peak_hours": peak_hours_full,
                "payment_breakdown": [
                    {"type": entry["payment_status"], "count": entry["count"]}
                    for entry in payment_breakdown
                ],
            }
        )


class AcceptingOrdersToggleView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/accepting-orders/ - Toggle accepting_orders."""

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsRestaurantAdmin()]
        return [IsAuthenticated(), HasActiveSubscription()]

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        return Response({
            "accepting_orders": restaurant.accepting_orders,
            "auto_resume_orders": restaurant.auto_resume_orders,
        })

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        accepting = request.data.get("accepting_orders")
        if accepting is None:
            return Response(
                {"detail": "accepting_orders is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        restaurant.accepting_orders = accepting
        auto_resume = request.data.get("auto_resume_orders")
        if auto_resume is not None:
            restaurant.auto_resume_orders = auto_resume
        restaurant.save(update_fields=["accepting_orders", "auto_resume_orders"])
        return Response({
            "accepting_orders": restaurant.accepting_orders,
            "auto_resume_orders": restaurant.auto_resume_orders,
        })


class OperatingHoursBulkView(RestaurantMixin, APIView):
    """GET/PUT /api/restaurants/:slug/operating-hours/
    GET returns all time slots across all days.
    PUT accepts a list of slot objects (multiple per day allowed, zero = closed) and replaces all.
    """

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsRestaurantAdmin()]
        return [IsAuthenticated(), HasActiveSubscription()]

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        hours = restaurant.operating_hours.all()
        return Response(OperatingHoursSerializer(hours, many=True).data)

    def put(self, request, slug):
        restaurant = self.get_restaurant()
        serializer = OperatingHoursSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        restaurant.operating_hours.all().delete()
        for item in serializer.validated_data:
            OperatingHours.objects.create(restaurant=restaurant, **item)

        hours = restaurant.operating_hours.all()
        return Response(OperatingHoursSerializer(hours, many=True).data)


class HolidayOverrideListCreateView(RestaurantMixin, generics.ListCreateAPIView):
    """GET/POST /api/restaurants/:slug/holiday-overrides/"""

    serializer_class = HolidayOverrideSerializer

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsRestaurantAdmin()]
        return [IsAuthenticated(), HasActiveSubscription()]

    def get_queryset(self):
        restaurant = self.get_restaurant()
        return restaurant.holiday_overrides.all()

    def perform_create(self, serializer):
        restaurant = self.get_restaurant()
        serializer.save(restaurant=restaurant)


class HolidayOverrideDetailView(RestaurantMixin, generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/restaurants/:slug/holiday-overrides/:pk/"""

    serializer_class = HolidayOverrideSerializer

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsRestaurantAdmin()]
        return [IsAuthenticated(), HasActiveSubscription()]

    def get_queryset(self):
        restaurant = self.get_restaurant()
        return restaurant.holiday_overrides.all()
