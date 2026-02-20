from decimal import Decimal
import stripe
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.models import Restaurant, MenuCategory, MenuItem, MenuItemVariant, MenuItemModifier, RestaurantStaff
from restaurants.serializers import PublicMenuCategorySerializer
from orders.serializers import ParseInputSerializer, ConfirmOrderSerializer, OrderResponseSerializer
from orders.services import validate_and_price_order
from orders.llm.menu_context import build_menu_context
from orders.llm.agent import OrderParsingAgent
from orders.models import Order, OrderItem
from orders.broadcast import broadcast_order_to_kitchen


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
                "tax_rate": str(restaurant.tax_rate),
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
        parsed = OrderParsingAgent.run(
            raw_input=raw_input,
            menu_context=menu_context,
        )
        result = validate_and_price_order(restaurant, parsed)

        return Response(result)


class ConfirmOrderView(APIView):
    authentication_classes = []
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

        # Calculate tax
        subtotal = total_price
        tax_rate = restaurant.tax_rate
        tax_amount = (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        grand_total = subtotal + tax_amount

        # Check for customer auth and auto-link
        customer = None
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            try:
                from rest_framework_simplejwt.tokens import UntypedToken
                from customers.models import Customer
                token_str = auth_header.split(" ", 1)[1]
                token = UntypedToken(token_str)
                if token.get("token_type") == "customer_access":
                    customer = Customer.objects.get(id=token["customer_id"])
            except Exception:
                pass  # Not a customer token or invalid — that's fine

        # Create order
        order = Order.objects.create(
            restaurant=restaurant,
            table_identifier=data.get("table_identifier") or None,
            customer=customer,
            customer_name=data.get("customer_name", ""),
            customer_phone=data.get("customer_phone", ""),
            status="confirmed",
            raw_input=data["raw_input"],
            parsed_json=request.data,
            language_detected=data.get("language", "en"),
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total_price=grand_total,
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


class CreatePaymentView(APIView):
    authentication_classes = []
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

        # Validate and calculate price server-side (same logic as ConfirmOrderView)
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
                    {"detail": "Invalid menu item or variant."},
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
                    pass

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

        # Calculate tax
        subtotal = total_price
        tax_rate = restaurant.tax_rate
        tax_amount = (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        grand_total = subtotal + tax_amount

        # Check for customer auth
        customer = None
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            try:
                from rest_framework_simplejwt.tokens import UntypedToken
                from customers.models import Customer
                token_str = auth_header.split(" ", 1)[1]
                token = UntypedToken(token_str)
                if token.get("token_type") == "customer_access":
                    customer = Customer.objects.get(id=token["customer_id"])
            except Exception:
                pass

        # Create order with pending_payment status
        order = Order.objects.create(
            restaurant=restaurant,
            table_identifier=data.get("table_identifier") or None,
            customer=customer,
            customer_name=data.get("customer_name", ""),
            customer_phone=data.get("customer_phone", ""),
            status="pending_payment",
            payment_status="pending",
            raw_input=data["raw_input"],
            parsed_json=request.data,
            language_detected=data.get("language", "en"),
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total_price=grand_total,
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

        # Create Stripe PaymentIntent
        if not settings.STRIPE_SECRET_KEY:
            order.delete()
            return Response(
                {"detail": "Payment system not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        stripe.api_key = settings.STRIPE_SECRET_KEY
        amount_cents = int((grand_total * Decimal("100")).quantize(Decimal("1")))

        payment_method_id = data.get("payment_method_id")
        save_card = data.get("save_card", False)

        intent_params = {
            "amount": amount_cents,
            "currency": restaurant.currency.lower(),
            "automatic_payment_methods": {"enabled": True},
            "metadata": {
                "order_id": str(order.id),
                "restaurant_slug": restaurant.slug,
            },
        }

        # If customer is logged in, attach Stripe Customer
        if customer:
            stripe_customer_id = customer.get_or_create_stripe_customer()
            intent_params["customer"] = stripe_customer_id

            if save_card:
                intent_params["setup_future_usage"] = "on_session"

        # If using a saved payment method, confirm immediately server-side
        if payment_method_id and customer:
            intent_params["payment_method"] = payment_method_id
            intent_params["confirm"] = True
            intent_params["return_url"] = data.get("return_url", "https://localhost")

        try:
            intent = stripe.PaymentIntent.create(**intent_params)
        except stripe.error.StripeError as e:
            order.delete()
            return Response(
                {"detail": f"Payment setup failed: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        order.stripe_payment_intent_id = intent.id
        if payment_method_id:
            order.stripe_payment_method_id = payment_method_id
        order.save(update_fields=["stripe_payment_intent_id", "stripe_payment_method_id"])

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


class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET,
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(
                {"detail": "Invalid webhook signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if event["type"] == "payment_intent.succeeded":
            intent = event["data"]["object"]
            try:
                order = Order.objects.get(
                    stripe_payment_intent_id=intent["id"]
                )
            except Order.DoesNotExist:
                return Response(status=status.HTTP_200_OK)

            if order.payment_status != "paid":
                order.status = "confirmed"
                order.payment_status = "paid"
                order.save(update_fields=["status", "payment_status"])
                broadcast_order_to_kitchen(order)

        elif event["type"] in ("payment_intent.payment_failed", "payment_intent.canceled"):
            intent = event["data"]["object"]
            try:
                order = Order.objects.get(
                    stripe_payment_intent_id=intent["id"]
                )
                order.payment_status = "failed"
                order.save(update_fields=["payment_status"])
            except Order.DoesNotExist:
                pass

        return Response(status=status.HTTP_200_OK)


VALID_TRANSITIONS = {
    "pending_payment": ["confirmed"],
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
