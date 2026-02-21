from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from restaurants.models import MenuCategory, MenuItem, Restaurant, RestaurantStaff, Subscription
from restaurants.serializers import (
    LoginSerializer,
    MenuCategorySerializer,
    MenuItemSerializer,
    RegisterSerializer,
    RestaurantSerializer,
    SubscriptionSerializer,
)
from restaurants.services import RestaurantService


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
        return RestaurantService.get_user_restaurants(self.request.user)


class CreateRestaurantView(generics.CreateAPIView):
    """POST /api/restaurants/ - Create a new restaurant."""

    serializer_class = RestaurantSerializer


class RestaurantDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/restaurants/:slug/ - View or update a restaurant."""

    serializer_class = RestaurantSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return RestaurantService.get_user_restaurants(self.request.user)


class RestaurantMixin:
    """Mixin to resolve restaurant from URL slug and check access."""

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
        return MenuItem.objects.filter(category__restaurant=restaurant).prefetch_related("variants", "modifiers")

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
        return MenuItem.objects.filter(category__restaurant=restaurant).prefetch_related("variants", "modifiers")

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
        return Response(RestaurantService.get_full_menu(restaurant))


class RestaurantOrderListView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/orders/ - List all orders for a restaurant."""

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        return Response(RestaurantService.get_restaurant_orders(restaurant))


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
        checkout_url = RestaurantService.create_checkout_session(
            restaurant, request.user, plan, interval
        )
        return Response({"checkout_url": checkout_url})


class CreateBillingPortalView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/portal/ - Open Stripe Billing Portal."""

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        portal_url = RestaurantService.create_billing_portal(restaurant)
        return Response({"portal_url": portal_url})


class CancelSubscriptionView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/cancel/ - Cancel subscription at period end."""

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        subscription = RestaurantService.cancel_subscription(restaurant)
        return Response(SubscriptionSerializer(subscription).data)


class ReactivateSubscriptionView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/reactivate/ - Undo pending cancellation."""

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        subscription = RestaurantService.reactivate_subscription(restaurant)
        return Response(SubscriptionSerializer(subscription).data)
