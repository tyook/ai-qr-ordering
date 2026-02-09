from decimal import Decimal
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.models import Restaurant, MenuCategory, MenuItem, MenuItemVariant, MenuItemModifier, RestaurantStaff
from restaurants.serializers import PublicMenuCategorySerializer
from orders.serializers import ParseInputSerializer, ConfirmOrderSerializer, OrderResponseSerializer
from orders.services import validate_and_price_order
from orders.llm.menu_context import build_menu_context
from orders.llm.openai_provider import OpenAIProvider
from orders.models import Order, OrderItem
from orders.broadcast import broadcast_order_to_kitchen


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


class ConfirmOrderView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            return Response(
                {"detail": "Restaurant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ConfirmOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not data["items"]:
            return Response(
                {"detail": "Order must contain at least one item."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate and calculate price server-side
        total_price = Decimal("0.00")
        validated_items = []

        for item_data in data["items"]:
            try:
                menu_item = MenuItem.objects.get(
                    id=item_data["menu_item_id"],
                    category__restaurant=restaurant,
                    is_active=True,
                )
                variant = MenuItemVariant.objects.get(
                    id=item_data["variant_id"],
                    menu_item=menu_item,
                )
            except (MenuItem.DoesNotExist, MenuItemVariant.DoesNotExist):
                return Response(
                    {"detail": f"Invalid menu item or variant."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            valid_modifiers = []
            modifier_total = Decimal("0.00")
            for mod_id in item_data.get("modifier_ids", []):
                try:
                    modifier = MenuItemModifier.objects.get(
                        id=mod_id, menu_item=menu_item
                    )
                    valid_modifiers.append(modifier)
                    modifier_total += modifier.price_adjustment
                except MenuItemModifier.DoesNotExist:
                    pass  # Skip invalid modifiers silently

            quantity = item_data["quantity"]
            line_total = (variant.price + modifier_total) * quantity
            total_price += line_total

            validated_items.append(
                {
                    "menu_item": menu_item,
                    "variant": variant,
                    "quantity": quantity,
                    "special_requests": item_data.get("special_requests", ""),
                    "modifiers": valid_modifiers,
                }
            )

        # Create order
        order = Order.objects.create(
            restaurant=restaurant,
            table_identifier=data.get("table_identifier") or None,
            status="confirmed",
            raw_input=data["raw_input"],
            parsed_json=request.data,
            language_detected=data.get("language", "en"),
            total_price=total_price,
        )

        for item_data in validated_items:
            order_item = OrderItem.objects.create(
                order=order,
                menu_item=item_data["menu_item"],
                variant=item_data["variant"],
                quantity=item_data["quantity"],
                special_requests=item_data["special_requests"],
            )
            order_item.modifiers.set(item_data["modifiers"])

        broadcast_order_to_kitchen(order)

        return Response(
            OrderResponseSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


class OrderStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug, order_id):
        try:
            order = Order.objects.get(
                id=order_id, restaurant__slug=slug
            )
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(OrderResponseSerializer(order).data)


VALID_TRANSITIONS = {
    "confirmed": ["preparing"],
    "preparing": ["ready"],
    "ready": ["completed"],
}


class KitchenOrderUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check user is staff at this restaurant
        is_owner = order.restaurant.owner == request.user
        is_staff = RestaurantStaff.objects.filter(
            user=request.user, restaurant=order.restaurant
        ).exists()
        if not is_owner and not is_staff:
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get("status")
        allowed = VALID_TRANSITIONS.get(order.status, [])
        if new_status not in allowed:
            return Response(
                {
                    "detail": f"Cannot transition from '{order.status}' to '{new_status}'. "
                    f"Allowed: {allowed}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = new_status
        order.save()

        # Broadcast status change to kitchen
        broadcast_order_to_kitchen(order)

        return Response(OrderResponseSerializer(order).data)
