import stripe
from django.conf import settings as django_settings
from rest_framework import status, generics, permissions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from restaurants.serializers import RegisterSerializer, LoginSerializer, RestaurantSerializer, MenuCategorySerializer, MenuItemSerializer, PublicMenuCategorySerializer, SubscriptionSerializer
from restaurants.models import Restaurant, RestaurantStaff, MenuCategory, MenuItem, Subscription
from restaurants.permissions import IsRestaurantOwnerOrStaff


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )


class MyRestaurantsView(generics.ListAPIView):
    """GET /api/restaurants/me/ - List restaurants I own or have staff access to."""
    serializer_class = RestaurantSerializer

    def get_queryset(self):
        user = self.request.user
        owned = Restaurant.objects.filter(owner=user)
        staff_ids = RestaurantStaff.objects.filter(user=user).values_list(
            "restaurant_id", flat=True
        )
        staffed = Restaurant.objects.filter(id__in=staff_ids)
        return (owned | staffed).distinct()


class CreateRestaurantView(generics.CreateAPIView):
    """POST /api/restaurants/ - Create a new restaurant."""
    serializer_class = RestaurantSerializer


class RestaurantDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/restaurants/:slug/ - View or update a restaurant."""
    serializer_class = RestaurantSerializer
    lookup_field = "slug"

    def get_queryset(self):
        user = self.request.user
        owned = Restaurant.objects.filter(owner=user)
        staff_ids = RestaurantStaff.objects.filter(user=user).values_list(
            "restaurant_id", flat=True
        )
        staffed = Restaurant.objects.filter(id__in=staff_ids)
        return (owned | staffed).distinct()


class RestaurantMixin:
    """Mixin to resolve restaurant from URL slug and check access."""

    def get_restaurant(self):
        slug = self.kwargs["slug"]
        user = self.request.user
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Restaurant not found.")

        is_owner = restaurant.owner == user
        is_staff = RestaurantStaff.objects.filter(
            user=user, restaurant=restaurant
        ).exists()
        if not is_owner and not is_staff:
            from rest_framework.exceptions import NotFound
            raise NotFound("Restaurant not found.")

        return restaurant


class MenuCategoryListCreateView(RestaurantMixin, generics.ListCreateAPIView):
    serializer_class = MenuCategorySerializer

    def get_queryset(self):
        restaurant = self.get_restaurant()
        return MenuCategory.objects.filter(restaurant=restaurant)

    def perform_create(self, serializer):
        restaurant = self.get_restaurant()
        serializer.save(restaurant=restaurant)


class MenuCategoryDetailView(RestaurantMixin, generics.RetrieveUpdateAPIView):
    serializer_class = MenuCategorySerializer
    lookup_field = "pk"

    def get_queryset(self):
        restaurant = self.get_restaurant()
        return MenuCategory.objects.filter(restaurant=restaurant)


class MenuItemListCreateView(RestaurantMixin, generics.ListCreateAPIView):
    serializer_class = MenuItemSerializer

    def get_queryset(self):
        restaurant = self.get_restaurant()
        return MenuItem.objects.filter(
            category__restaurant=restaurant
        ).prefetch_related("variants", "modifiers")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["restaurant"] = self.get_restaurant()
        return ctx

    def perform_create(self, serializer):
        serializer.save()


class MenuItemDetailView(RestaurantMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MenuItemSerializer
    lookup_field = "pk"

    def get_queryset(self):
        restaurant = self.get_restaurant()
        return MenuItem.objects.filter(
            category__restaurant=restaurant
        ).prefetch_related("variants", "modifiers")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["restaurant"] = self.get_restaurant()
        return ctx

    def perform_destroy(self, instance):
        """Soft-delete: deactivate instead of deleting."""
        instance.is_active = False
        instance.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"status": "deactivated", "id": instance.id},
            status=status.HTTP_200_OK,
        )


class FullMenuView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/menu/ - Full menu including inactive items."""

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        categories = (
            MenuCategory.objects.filter(restaurant=restaurant)
            .prefetch_related("items__variants", "items__modifiers")
            .order_by("sort_order")
        )
        # Use a version that includes inactive items
        data = []
        for cat in categories:
            cat_data = {
                "id": cat.id,
                "name": cat.name,
                "sort_order": cat.sort_order,
                "is_active": cat.is_active,
                "items": MenuItemSerializer(
                    cat.items.prefetch_related("variants", "modifiers"),
                    many=True,
                ).data,
            }
            data.append(cat_data)

        return Response({"restaurant_name": restaurant.name, "categories": data})


class SubscriptionDetailView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/subscription/ - View subscription details."""

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

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        plan = request.data.get("plan", "starter")
        interval = request.data.get("interval", "monthly")

        plan_config = django_settings.SUBSCRIPTION_PLANS.get(plan)
        if not plan_config:
            return Response(
                {"detail": "Invalid plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        price_key = "monthly_price_id" if interval == "monthly" else "annual_price_id"
        price_id = plan_config.get(price_key)
        if not price_id:
            return Response(
                {"detail": "Price not configured."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stripe.api_key = django_settings.STRIPE_SECRET_KEY

        # Get or create Stripe Customer for the restaurant owner
        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not subscription.stripe_customer_id:
            customer = stripe.Customer.create(
                email=request.user.email,
                name=f"{request.user.first_name} {request.user.last_name}".strip(),
                metadata={
                    "restaurant_id": str(restaurant.id),
                    "restaurant_slug": restaurant.slug,
                },
            )
            subscription.stripe_customer_id = customer.id
            subscription.save(update_fields=["stripe_customer_id"])

        checkout_session = stripe.checkout.Session.create(
            customer=subscription.stripe_customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{django_settings.FRONTEND_URL}/admin/{restaurant.slug}/billing?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{django_settings.FRONTEND_URL}/admin/{restaurant.slug}/billing",
            metadata={
                "restaurant_id": str(restaurant.id),
                "plan": plan,
            },
            subscription_data={
                "metadata": {
                    "restaurant_id": str(restaurant.id),
                    "plan": plan,
                },
            },
        )

        return Response({"checkout_url": checkout_session.url})


class CreateBillingPortalView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/portal/ - Open Stripe Billing Portal."""

    def post(self, request, slug):
        restaurant = self.get_restaurant()

        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not subscription.stripe_customer_id:
            return Response(
                {"detail": "No billing account found. Please subscribe first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stripe.api_key = django_settings.STRIPE_SECRET_KEY

        portal_session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=f"{django_settings.FRONTEND_URL}/admin/{restaurant.slug}/billing",
        )

        return Response({"portal_url": portal_session.url})


class CancelSubscriptionView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/cancel/ - Cancel subscription at period end."""

    def post(self, request, slug):
        restaurant = self.get_restaurant()

        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not subscription.stripe_subscription_id:
            return Response(
                {"detail": "No active paid subscription to cancel."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stripe.api_key = django_settings.STRIPE_SECRET_KEY

        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True,
        )

        subscription.cancel_at_period_end = True
        subscription.save(update_fields=["cancel_at_period_end"])

        return Response(SubscriptionSerializer(subscription).data)


class ReactivateSubscriptionView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/reactivate/ - Undo pending cancellation."""

    def post(self, request, slug):
        restaurant = self.get_restaurant()

        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not subscription.stripe_subscription_id:
            return Response(
                {"detail": "No active subscription to reactivate."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stripe.api_key = django_settings.STRIPE_SECRET_KEY

        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=False,
        )

        subscription.cancel_at_period_end = False
        subscription.save(update_fields=["cancel_at_period_end"])

        return Response(SubscriptionSerializer(subscription).data)
