from rest_framework import status, generics, permissions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from restaurants.serializers import RegisterSerializer, LoginSerializer, RestaurantSerializer
from restaurants.models import Restaurant, RestaurantStaff
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
