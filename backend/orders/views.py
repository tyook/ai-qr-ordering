from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.models import Restaurant, MenuCategory
from restaurants.serializers import PublicMenuCategorySerializer
from orders.serializers import ParseInputSerializer, ConfirmOrderSerializer
from orders.services import validate_and_price_order
from orders.llm.menu_context import build_menu_context
from orders.llm.openai_provider import OpenAIProvider


def get_llm_provider():
    return OpenAIProvider()


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


class ParseOrderView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            return Response(
                {"detail": "Restaurant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ParseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_input = serializer.validated_data["raw_input"]
        menu_context = build_menu_context(restaurant)
        provider = get_llm_provider()
        parsed = provider.parse_order(raw_input, menu_context)
        result = validate_and_price_order(restaurant, parsed)

        return Response(result)
