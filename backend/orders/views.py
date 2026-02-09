from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.models import Restaurant, MenuCategory
from restaurants.serializers import PublicMenuCategorySerializer


class PublicMenuView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            return Response(
                {"detail": "Restaurant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        categories = (
            MenuCategory.objects.filter(restaurant=restaurant, is_active=True)
            .prefetch_related("items__variants", "items__modifiers")
            .order_by("sort_order")
        )

        return Response(
            {
                "restaurant_name": restaurant.name,
                "categories": PublicMenuCategorySerializer(categories, many=True).data,
            }
        )
