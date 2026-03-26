from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order
from orders.serializers import ConfirmOrderSerializer, OrderResponseSerializer, ParseInputSerializer
from orders.services import OrderService


class PublicMenuView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        return Response(OrderService.get_public_menu(slug))


class ParseOrderView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = OrderService.get_restaurant_by_slug(slug)

        serializer = ParseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = OrderService.parse_order(
            restaurant, serializer.validated_data["raw_input"]
        )
        return Response(result)


class ConfirmOrderView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = OrderService.get_restaurant_by_slug(slug)

        serializer = ConfirmOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        validated_items, pricing = OrderService.validate_and_price_items(
            restaurant, data["items"]
        )
        user = OrderService.resolve_user_from_request(request)

        order = OrderService.create_order(
            restaurant,
            validated_items,
            pricing,
            user=user,
            order_status="confirmed",
            raw_input=data["raw_input"],
            parsed_json=request.data,
            language=data.get("language", "en"),
            table_identifier=data.get("table_identifier"),
            customer_name=data.get("customer_name", ""),
            customer_phone=data.get("customer_phone", ""),
        )

        from orders.broadcast import broadcast_order_to_kitchen

        broadcast_order_to_kitchen(order)

        return Response(
            OrderResponseSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


class CreatePaymentView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = OrderService.get_restaurant_by_slug(slug)

        serializer = ConfirmOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        validated_items, pricing = OrderService.validate_and_price_items(
            restaurant, data["items"]
        )
        user = OrderService.resolve_user_from_request(request)

        # Build customer_allergies list
        customer_allergies = []
        if user and user.allergies:
            customer_allergies = list(user.allergies)
        elif data.get("allergies"):
            customer_allergies = list(data["allergies"])

        order = OrderService.create_order(
            restaurant,
            validated_items,
            pricing,
            user=user,
            order_status="pending_payment",
            payment_status="pending",
            raw_input=data["raw_input"],
            parsed_json=request.data,
            language=data.get("language", "en"),
            table_identifier=data.get("table_identifier"),
            customer_name=data.get("customer_name", ""),
            customer_phone=data.get("customer_phone", ""),
            customer_allergies=customer_allergies,
        )

        intent = OrderService.create_payment_intent(
            order,
            restaurant,
            user=user,
            payment_method_id=data.get("payment_method_id"),
            return_url=data.get("return_url"),
        )

        response_data = OrderResponseSerializer(order).data
        response_data["client_secret"] = intent.client_secret

        # If payment was confirmed server-side and succeeded
        if intent.status == "succeeded":
            order.status = "confirmed"
            order.payment_status = "paid"
            order.save(update_fields=["status", "payment_status"])
            response_data["status"] = "confirmed"
            response_data["payment_status"] = "paid"

        return Response(response_data, status=status.HTTP_201_CREATED)


class SaveCardConsentView(APIView):
    """PATCH: update a PaymentIntent to save the card after payment."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def patch(self, request, slug, order_id):
        try:
            order = Order.objects.get(id=order_id, restaurant__slug=slug)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        OrderService.save_card_consent(order)
        return Response({"detail": "Card will be saved after payment."})


class OrderStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug, order_id):
        try:
            order = Order.objects.get(id=order_id, restaurant__slug=slug)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(OrderResponseSerializer(order).data)


class ConfirmPaymentView(APIView):
    """Called by the frontend after stripe.confirmPayment() succeeds.

    Verifies the PaymentIntent status with Stripe and transitions the
    order from pending_payment -> confirmed.  This is a synchronous
    fallback so the order status is correct even when the Stripe webhook
    hasn't arrived yet.
    """

    permission_classes = [AllowAny]

    def post(self, request, slug, order_id):
        try:
            order = Order.objects.get(id=order_id, restaurant__slug=slug)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        order = OrderService.confirm_payment(order)

        if order.payment_status == "failed":
            return Response(
                {
                    "detail": "Payment failed.",
                    "status": order.status,
                    "payment_status": "failed",
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        return Response(OrderResponseSerializer(order).data)


class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        OrderService.handle_stripe_webhook(request.body, sig_header)
        return Response(status=status.HTTP_200_OK)


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

        new_status = request.data.get("status")
        order = OrderService.update_order_status(order, new_status, request.user)
        return Response(OrderResponseSerializer(order).data)
