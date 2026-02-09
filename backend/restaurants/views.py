from rest_framework import status, generics, permissions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from restaurants.serializers import RegisterSerializer, LoginSerializer, RestaurantSerializer, MenuCategorySerializer, MenuItemSerializer, PublicMenuCategorySerializer
from restaurants.models import Restaurant, RestaurantStaff, MenuCategory, MenuItem
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
