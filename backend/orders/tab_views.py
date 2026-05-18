from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from orders.broadcast import broadcast_order_to_kitchen
from orders.models import Tab
from orders.serializers import ConfirmOrderSerializer, OrderResponseSerializer, TabPaymentRequestSerializer, TabResponseSerializer
from orders.services import OrderService
from orders.tab_broadcasts import broadcast_tab_update
from orders.tab_payment_service import TabPaymentService
from orders.tab_service import TabService
from restaurants.models import Restaurant, RestaurantStaff


class TabDetailView(APIView):
    """GET /api/order/{slug}/tab/?table={id}"""
    permission_classes = [AllowAny]

    def get(self, request, slug):
        table = request.query_params.get("table")
        if not table:
            return Response({"error": "table query parameter is required"}, status=status.HTTP_400_BAD_REQUEST)
        restaurant = Restaurant.objects.filter(slug=slug).first()
        if not restaurant:
            return Response(status=status.HTTP_404_NOT_FOUND)
        tab = TabService.get_open_tab(restaurant, table)
        if not tab:
            return Response({"error": "No open tab for this table"}, status=status.HTTP_404_NOT_FOUND)
        return Response(TabResponseSerializer(tab).data)


class TabOrderView(APIView):
    """POST /api/order/{slug}/tab/order/ — place an order on a tab"""
    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = Restaurant.objects.filter(slug=slug).first()
        if not restaurant:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if restaurant.payment_model != "tab":
            return Response({"error": "This restaurant does not use tab mode"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ConfirmOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        table_identifier = data.get("table_identifier", "")
        if not table_identifier:
            return Response({"error": "table_identifier is required for tab orders"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tab = TabService.get_or_create_tab(restaurant, table_identifier)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        validated_items, pricing = OrderService.validate_and_price_items(restaurant, data["items"])
        if not validated_items:
            return Response({"error": "No valid items in order"}, status=status.HTTP_400_BAD_REQUEST)

        user = OrderService.resolve_user_from_request(request)

        order = OrderService.create_order(
            restaurant, validated_items, pricing,
            user=user, order_status="confirmed", payment_status="deferred",
            raw_input=data.get("raw_input", ""),
            language=data.get("language", ""),
            table_identifier=table_identifier,
            customer_name=data.get("customer_name", ""),
            customer_phone=data.get("customer_phone", ""),
            customer_allergies=data.get("allergies", []),
            tab=tab,
        )

        response_data = OrderResponseSerializer(order).data
        response_data["tab"] = TabResponseSerializer(tab).data
        broadcast_tab_update(tab, "tab.order_added")
        broadcast_order_to_kitchen(order)
        return Response(response_data, status=status.HTTP_201_CREATED)


class TabCloseView(APIView):
    """POST /api/order/{slug}/tab/close/"""
    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = Restaurant.objects.filter(slug=slug).first()
        if not restaurant:
            return Response(status=status.HTTP_404_NOT_FOUND)
        table_identifier = request.data.get("table_identifier")
        if not table_identifier:
            return Response({"error": "table_identifier is required"}, status=status.HTTP_400_BAD_REQUEST)
        tab = TabService.get_open_tab(restaurant, table_identifier)
        if not tab:
            return Response({"error": "No open tab for this table"}, status=status.HTTP_404_NOT_FOUND)
        TabService.close_tab(tab)
        return Response(TabResponseSerializer(tab).data)


class TabPayView(APIView):
    """POST /api/order/{slug}/tab/pay/"""
    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = Restaurant.objects.filter(slug=slug).first()
        if not restaurant:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = TabPaymentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            tab = Tab.objects.get(id=data["tab_id"], restaurant=restaurant)
        except Tab.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            payment, client_secret = TabPaymentService.create_payment(
                tab=tab,
                payment_type=data["type"],
                split_count=data.get("split_count"),
                item_ids=data.get("item_ids"),
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"payment_id": str(payment.id), "client_secret": client_secret},
            status=status.HTTP_201_CREATED,
        )


class TabConfirmPaymentView(APIView):
    """POST /api/order/{slug}/tab/confirm-payment/{payment_id}/"""
    permission_classes = [AllowAny]

    def post(self, request, slug, payment_id):
        from orders.models import TabPayment
        try:
            payment = TabPayment.objects.select_related("tab", "tab__restaurant").get(
                id=payment_id, tab__restaurant__slug=slug
            )
        except TabPayment.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        succeeded = TabPaymentService.confirm_payment(payment)
        if succeeded:
            return Response(TabResponseSerializer(payment.tab).data)
        return Response(
            {"error": "Payment not yet confirmed", "payment_status": payment.payment_status},
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )


class KitchenTabCloseView(APIView):
    """POST /api/kitchen/tab/{tab_id}/close/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, tab_id):
        try:
            tab = Tab.objects.select_related("restaurant").get(id=tab_id)
        except Tab.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        from restaurants.services import TeamService
        perms = TeamService.get_effective_permissions(request.user, tab.restaurant)
        if perms is None or (not perms["is_admin"] and not perms.get("order_manage")):
            return Response(status=status.HTTP_403_FORBIDDEN)
        TabService.close_tab(tab)
        return Response(TabResponseSerializer(tab).data)
