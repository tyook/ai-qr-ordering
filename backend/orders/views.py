import logging

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import CookieJWTAuthentication
from orders.broadcast import broadcast_order_to_customer, broadcast_order_to_kitchen
from integrations.models import POSConnection
from integrations.tasks import dispatch_order_to_pos
from orders.models import Order
from orders.queue_service import QueueService
from orders.serializers import ConfirmOrderSerializer, OrderResponseSerializer, ParseInputSerializer
from orders.services import OrderService
from restaurants.models import Restaurant


class PublicMenuView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        restaurant = OrderService.get_restaurant_by_slug(slug)

        if not OrderService.is_subscription_active(restaurant):
            return Response({
                "available": False,
                "restaurant_name": restaurant.name,
            })

        menu = OrderService.get_public_menu(slug)
        menu["available"] = True
        return Response(menu)


class ParseOrderView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = OrderService.get_restaurant_by_slug(slug)

        serializer = ParseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = OrderService.parse_order(
            restaurant, serializer.validated_data["raw_input"], user=request.user
        )
        return Response(result)


logger = logging.getLogger(__name__)


class TranscribeAudioView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]

    def post(self, request, slug):
        # Validate restaurant exists (same gate as parse)
        OrderService.get_restaurant_by_slug(slug)

        audio_file = request.FILES.get("audio")
        if not audio_file:
            return Response(
                {"detail": "No audio file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import openai
        from django.conf import settings as django_settings

        client = openai.OpenAI(api_key=django_settings.OPENAI_API_KEY)

        try:
            result = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=(audio_file.name or "audio.webm", audio_file.read(), audio_file.content_type or "audio/webm"),
            )
            return Response({"transcript": result.text})
        except openai.OpenAIError as exc:
            logger.exception("OpenAI transcription failed")
            return Response(
                {"detail": f"Transcription failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )


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

        # Determine payment mode from POS connection
        try:
            pos_connection = POSConnection.objects.get(restaurant=restaurant, is_active=True)
            payment_mode = pos_connection.payment_mode
        except POSConnection.DoesNotExist:
            payment_mode = "stripe"

        payment_status = "pos_collected" if payment_mode == "pos_collected" else "pending"

        order = OrderService.create_order(
            restaurant,
            validated_items,
            pricing,
            user=user,
            order_status="confirmed",
            payment_status=payment_status,
            raw_input=data["raw_input"],
            parsed_json=request.data,
            language=data.get("language", "en"),
            table_identifier=data.get("table_identifier"),
            customer_name=data.get("customer_name", ""),
            customer_email=data.get("customer_email", ""),
            customer_phone=data.get("customer_phone", ""),
        )

        from orders.broadcast import broadcast_order_to_kitchen

        broadcast_order_to_kitchen(order)
        broadcast_order_to_customer(order)
        from orders.tasks import broadcast_queue_updates
        broadcast_queue_updates.apply_async(
            args=[str(order.restaurant_id), str(order.id)],
        )

        # POS dispatch — only for pos_collected orders, which skip the payment
        # flow entirely. Stripe-mode orders are dispatched after payment
        # confirmation (from ConfirmPaymentView / StripeWebhookView).
        if payment_mode == "pos_collected":
            dispatch_order_to_pos.delay(str(order.id))

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
            customer_email=data.get("customer_email", ""),
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
            OrderService.set_status_timestamp(order, "confirmed")
            broadcast_order_to_kitchen(order)
            broadcast_order_to_customer(order)
            from orders.tasks import broadcast_queue_updates
            broadcast_queue_updates.apply_async(
                args=[str(order.restaurant_id), str(order.id)],
            )
            dispatch_order_to_pos.delay(str(order.id))
            OrderService._send_confirmation_emails(order)

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

        if order.payment_status == "paid":
            dispatch_order_to_pos.delay(str(order.id))

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


class StripeConnectWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        result = OrderService.handle_stripe_connect_webhook(
            request.body, request.META.get("HTTP_STRIPE_SIGNATURE", "")
        )
        return Response(result)


class UpsellSuggestionsView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, slug, order_id):
        try:
            order = Order.objects.get(id=order_id, restaurant__slug=slug)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        suggestions = OrderService.get_upsell_suggestions(order)
        return Response({"suggestions": suggestions})


class CartUpsellView(APIView):
    """POST /api/order/<slug>/cart-upsell/ — AI upsell suggestions for cart items (pre-order)."""

    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = OrderService.get_restaurant_by_slug(slug)

        cart_items = request.data.get("items", [])
        if not cart_items:
            return Response({"suggestions": []})

        suggestions = OrderService.get_cart_upsell_suggestions(
            restaurant, cart_items
        )
        return Response({"suggestions": suggestions})


class QueueInfoView(APIView):
    """GET /api/order/<slug>/queue-info/ — restaurant busyness (public)."""

    permission_classes = [AllowAny]

    def get(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            raise NotFound("Restaurant not found")

        data = QueueService.get_restaurant_queue_info(restaurant)
        return Response(data)


class OrderQueueView(APIView):
    """GET /api/order/<slug>/queue/<order_id>/ — order queue position (public)."""

    permission_classes = [AllowAny]

    def get(self, request, slug, order_id):
        try:
            order = Order.objects.select_related("restaurant").get(
                id=order_id, restaurant__slug=slug
            )
        except Order.DoesNotExist:
            raise NotFound("Order not found")

        data = QueueService.get_order_queue_info(order)
        response = Response(data)
        response["Cache-Control"] = "no-store"
        return response


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

        from restaurants.services import TeamService
        perms = TeamService.get_effective_permissions(request.user, order.restaurant)
        if perms is None or (not perms["is_admin"] and not perms.get("order_manage")):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get("status")
        order = OrderService.update_order_status(order, new_status, request.user)
        return Response(OrderResponseSerializer(order).data)
