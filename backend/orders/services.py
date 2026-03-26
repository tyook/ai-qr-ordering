import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import stripe
from django.conf import settings
from django.db import models as db_models
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from orders.broadcast import broadcast_order_to_kitchen
from orders.llm.agent import OrderParsingAgent
from orders.llm.base import ParsedOrder
from orders.llm.menu_context import build_menu_context
from orders.models import Order, OrderItem
from restaurants.models import (
    MenuItem,
    MenuItemModifier,
    MenuItemVariant,
    Restaurant,
    RestaurantStaff,
    Subscription,
)

logger = logging.getLogger(__name__)

VALID_TRANSITIONS = {
    "pending_payment": ["confirmed"],
    "confirmed": ["preparing"],
    "preparing": ["ready"],
    "ready": ["completed"],
}


@dataclass
class OrderPricing:
    """Computed pricing for an order."""

    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total: Decimal


class OrderService:
    """Service layer for order domain operations."""

    # ── Item Validation & Pricing (shared by confirm + payment flows) ──

    @staticmethod
    def validate_and_price_items(
        restaurant: Restaurant, items_data: list[dict]
    ) -> tuple[list[dict], OrderPricing]:
        """Validate order items against the database and calculate pricing.

        This is the shared logic used by both ConfirmOrderView and
        CreatePaymentView, eliminating the previous code duplication.

        Returns (validated_items, pricing) where validated_items is a list of
        dicts containing resolved model instances.
        Raises ValidationError on invalid menu items or variants.
        """
        if not items_data:
            raise ValidationError("Order must contain at least one item.")

        total_price = Decimal("0.00")
        validated_items = []

        for item_data in items_data:
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
                raise ValidationError("Invalid menu item or variant.")

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
        tax_rate = restaurant.tax_rate
        tax_amount = (total_price * tax_rate / Decimal("100")).quantize(
            Decimal("0.01")
        )
        grand_total = total_price + tax_amount

        pricing = OrderPricing(
            subtotal=total_price,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total=grand_total,
        )

        return validated_items, pricing

    # ── LLM-parsed order validation (existing logic, kept as-is) ───

    @staticmethod
    def validate_and_price_order(
        restaurant: Restaurant, parsed: ParsedOrder
    ) -> dict:
        """Validate LLM-parsed order items against the database.

        Calculate prices server-side. Drop any invalid items.
        Returns a dict ready for the frontend confirmation step.
        """
        validated_items = []
        total_price = Decimal("0.00")

        for parsed_item in parsed.items:
            try:
                menu_item = MenuItem.objects.get(
                    id=parsed_item.menu_item_id,
                    category__restaurant=restaurant,
                    is_active=True,
                )
                variant = MenuItemVariant.objects.get(
                    id=parsed_item.variant_id,
                    menu_item=menu_item,
                )
            except (MenuItem.DoesNotExist, MenuItemVariant.DoesNotExist):
                continue  # Skip invalid items

            # Validate modifiers
            valid_modifiers = []
            for mod_id in parsed_item.modifier_ids:
                try:
                    modifier = MenuItemModifier.objects.get(
                        id=mod_id, menu_item=menu_item
                    )
                    valid_modifiers.append(
                        {
                            "id": modifier.id,
                            "name": modifier.name,
                            "price_adjustment": str(modifier.price_adjustment),
                        }
                    )
                except MenuItemModifier.DoesNotExist:
                    continue  # Skip invalid modifiers

            item_price = variant.price * parsed_item.quantity
            modifier_total = (
                sum(Decimal(m["price_adjustment"]) for m in valid_modifiers)
                * parsed_item.quantity
            )
            line_total = item_price + modifier_total
            total_price += line_total

            validated_items.append(
                {
                    "menu_item_id": menu_item.id,
                    "name": menu_item.name,
                    "variant": {
                        "id": variant.id,
                        "label": variant.label,
                        "price": str(variant.price),
                    },
                    "quantity": parsed_item.quantity,
                    "modifiers": valid_modifiers,
                    "special_requests": parsed_item.special_requests,
                    "line_total": str(line_total),
                }
            )

        return {
            "items": validated_items,
            "allergies": parsed.allergies,
            "total_price": str(total_price),
            "language": parsed.language,
        }

    # ── User Resolution ───────────────────────────────────────────

    @staticmethod
    def resolve_user_from_request(request):
        """Extract user from request (set by CookieJWTAuthentication or header).
        Returns None if no authenticated user.
        """
        if hasattr(request, "user") and request.user and request.user.is_authenticated:
            return request.user
        return None

    # ── Order Creation ─────────────────────────────────────────────

    @staticmethod
    def create_order(
        restaurant: Restaurant,
        validated_items: list[dict],
        pricing: OrderPricing,
        *,
        user=None,
        order_status: str = "confirmed",
        payment_status: str = "pending",
        raw_input: str = "",
        parsed_json: dict | None = None,
        language: str = "en",
        table_identifier: str | None = None,
        customer_name: str = "",
        customer_phone: str = "",
        customer_allergies: list | None = None,
    ) -> Order:
        """Create an order with its items. Returns the created Order."""
        order = Order.objects.create(
            restaurant=restaurant,
            table_identifier=table_identifier or None,
            user=user,
            customer_name=customer_name,
            customer_phone=customer_phone,
            status=order_status,
            payment_status=payment_status,
            raw_input=raw_input,
            parsed_json=parsed_json or {},
            language_detected=language,
            subtotal=pricing.subtotal,
            tax_rate=pricing.tax_rate,
            tax_amount=pricing.tax_amount,
            total_price=pricing.total,
            customer_allergies=customer_allergies or [],
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

        return order

    # ── Subscription Check ─────────────────────────────────────────

    @staticmethod
    def check_subscription(restaurant: Restaurant) -> Subscription | None:
        """Check that the restaurant's subscription is active.

        Raises PermissionDenied if subscription is inactive or trial expired.
        Returns the subscription (or None for legacy restaurants).
        """
        try:
            subscription = restaurant.subscription
            if not subscription.is_active:
                raise PermissionDenied(
                    "Subscription is not active. Please subscribe to continue."
                )
            if (
                subscription.status == "trialing"
                and subscription.trial_end
                and subscription.trial_end < timezone.now()
            ):
                raise PermissionDenied(
                    "Free trial has expired. Please subscribe to continue."
                )
            return subscription
        except Subscription.DoesNotExist:
            return None  # Legacy restaurant, allow access

    @staticmethod
    def increment_order_count(subscription: Subscription | None) -> None:
        """Increment the order count on a subscription (soft cap)."""
        if subscription:
            Subscription.objects.filter(id=subscription.id).update(
                order_count=db_models.F("order_count") + 1
            )

    # ── LLM Order Parsing ──────────────────────────────────────────

    @staticmethod
    def parse_order(restaurant: Restaurant, raw_input: str) -> dict:
        """Parse a natural language order via LLM and validate/price it.

        Checks subscription, runs LLM, validates against DB, increments count.
        Returns validated order dict for frontend confirmation.
        """
        subscription = OrderService.check_subscription(restaurant)

        menu_context = build_menu_context(restaurant)
        parsed = OrderParsingAgent.run(
            raw_input=raw_input,
            menu_context=menu_context,
        )
        result = OrderService.validate_and_price_order(restaurant, parsed)

        OrderService.increment_order_count(subscription)

        return result

    # ── Payment ────────────────────────────────────────────────────

    @staticmethod
    def create_payment_intent(
        order: Order,
        restaurant: Restaurant,
        user=None,
        payment_method_id: str | None = None,
        return_url: str | None = None,
    ) -> "stripe.PaymentIntent":
        """Create a Stripe PaymentIntent for an order.

        Raises ValidationError if Stripe is not configured.
        Raises ValidationError on Stripe errors (deletes the order).
        Returns the PaymentIntent object.
        """
        if not settings.STRIPE_SECRET_KEY:
            order.delete()
            raise ValidationError("Payment system not configured.")

        stripe.api_key = settings.STRIPE_SECRET_KEY
        amount_cents = int(
            (order.total_price * Decimal("100")).quantize(Decimal("1"))
        )

        intent_params = {
            "amount": amount_cents,
            "currency": restaurant.currency.lower(),
            "automatic_payment_methods": {"enabled": True},
            "metadata": {
                "order_id": str(order.id),
                "restaurant_slug": restaurant.slug,
            },
        }

        if user:
            stripe_customer_id = user.get_or_create_stripe_customer()
            intent_params["customer"] = stripe_customer_id

        if payment_method_id and user:
            intent_params["payment_method"] = payment_method_id
            intent_params["confirm"] = True
            intent_params["return_url"] = return_url or "https://localhost"

        try:
            intent = stripe.PaymentIntent.create(**intent_params)
        except stripe.error.StripeError as e:
            order.delete()
            raise ValidationError(f"Payment setup failed: {e}")

        order.stripe_payment_intent_id = intent.id
        if payment_method_id:
            order.stripe_payment_method_id = payment_method_id
        order.save(
            update_fields=["stripe_payment_intent_id", "stripe_payment_method_id"]
        )

        return intent

    @staticmethod
    def save_card_consent(order: Order) -> None:
        """Update PaymentIntent to save the card after payment.

        Raises NotFound if order has no payment intent.
        Raises ValidationError on Stripe errors.
        """
        if not order.stripe_payment_intent_id:
            raise ValidationError("No payment intent found.")

        stripe.api_key = settings.STRIPE_SECRET_KEY

        try:
            stripe.PaymentIntent.modify(
                order.stripe_payment_intent_id,
                setup_future_usage="on_session",
            )
        except stripe.error.StripeError as e:
            raise ValidationError(f"Failed to update payment: {e}")

    @staticmethod
    def confirm_payment(order: Order) -> Order:
        """Verify payment with Stripe and transition order status.

        Returns the updated order.
        Raises ValidationError if no payment intent exists.
        """
        if not order.stripe_payment_intent_id:
            raise ValidationError(
                "No payment intent associated with this order."
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            intent = stripe.PaymentIntent.retrieve(
                order.stripe_payment_intent_id
            )
        except stripe.error.StripeError as e:
            raise ValidationError(f"Failed to verify payment: {e}")

        if intent.status == "succeeded":
            updated = Order.objects.filter(
                id=order.id, payment_status="pending"
            ).update(status="confirmed", payment_status="paid")
            order.refresh_from_db()
            if updated:
                broadcast_order_to_kitchen(order)
        elif intent.status in ("requires_payment_method", "canceled"):
            Order.objects.filter(
                id=order.id, payment_status="pending"
            ).update(payment_status="failed")
            order.refresh_from_db()

        return order

    # ── Kitchen Order Updates ──────────────────────────────────────

    @staticmethod
    def update_order_status(order: Order, new_status: str, user) -> Order:
        """Validate and apply an order status transition.

        Checks that the user is staff/owner at the restaurant.
        Raises PermissionDenied if not authorized.
        Raises ValidationError if the transition is invalid.
        Returns the updated order.
        """
        is_owner = order.restaurant.owner == user
        is_staff = RestaurantStaff.objects.filter(
            user=user, restaurant=order.restaurant
        ).exists()
        if not is_owner and not is_staff:
            raise PermissionDenied("Not authorized.")

        allowed = VALID_TRANSITIONS.get(order.status, [])
        if new_status not in allowed:
            raise ValidationError(
                f"Cannot transition from '{order.status}' to '{new_status}'. "
                f"Allowed: {allowed}"
            )

        order.status = new_status
        order.save()
        broadcast_order_to_kitchen(order)
        return order

    # ── Stripe Webhook Handling ────────────────────────────────────

    @staticmethod
    def handle_stripe_webhook(payload: bytes, sig_header: str) -> None:
        """Process a Stripe webhook event.

        Raises ValidationError on invalid signature.
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            raise ValidationError("Invalid webhook signature.")

        event_type = event["type"]
        data_object = event["data"]["object"]

        handler = {
            "payment_intent.succeeded": OrderService._handle_payment_succeeded,
            "payment_intent.payment_failed": OrderService._handle_payment_failed,
            "payment_intent.canceled": OrderService._handle_payment_failed,
            "checkout.session.completed": OrderService._handle_checkout_completed,
            "customer.subscription.updated": OrderService._handle_subscription_updated,
            "customer.subscription.deleted": OrderService._handle_subscription_deleted,
            "invoice.paid": OrderService._handle_invoice_paid,
        }.get(event_type)

        if handler:
            handler(data_object)

    @staticmethod
    def _handle_payment_succeeded(intent: dict) -> None:
        try:
            order = Order.objects.get(stripe_payment_intent_id=intent["id"])
        except Order.DoesNotExist:
            return

        updated = Order.objects.filter(
            id=order.id, payment_status="pending"
        ).update(status="confirmed", payment_status="paid")
        if updated:
            order.refresh_from_db()
            broadcast_order_to_kitchen(order)

    @staticmethod
    def _handle_payment_failed(intent: dict) -> None:
        try:
            order = Order.objects.get(stripe_payment_intent_id=intent["id"])
            order.payment_status = "failed"
            order.save(update_fields=["payment_status"])
        except Order.DoesNotExist:
            pass

    @staticmethod
    def _handle_checkout_completed(session: dict) -> None:
        if session.get("mode") != "subscription":
            return

        restaurant_id = session.get("metadata", {}).get("restaurant_id")
        plan = session.get("metadata", {}).get("plan", "starter")
        if not restaurant_id:
            return

        try:
            sub = Subscription.objects.get(restaurant_id=restaurant_id)
            sub.stripe_subscription_id = session["subscription"]
            sub.stripe_customer_id = session.get(
                "customer", sub.stripe_customer_id
            )
            sub.plan = plan
            sub.status = "active"
            sub.order_count = 0
            sub.save(
                update_fields=[
                    "stripe_subscription_id",
                    "stripe_customer_id",
                    "plan",
                    "status",
                    "order_count",
                ]
            )
        except Subscription.DoesNotExist:
            pass

    @staticmethod
    def _handle_subscription_updated(sub_data: dict) -> None:
        try:
            sub = Subscription.objects.get(
                stripe_subscription_id=sub_data["id"]
            )
            sub.status = sub_data["status"]
            sub.cancel_at_period_end = sub_data.get(
                "cancel_at_period_end", False
            )

            if sub_data.get("current_period_start"):
                sub.current_period_start = datetime.fromtimestamp(
                    sub_data["current_period_start"], tz=UTC
                )
            if sub_data.get("current_period_end"):
                sub.current_period_end = datetime.fromtimestamp(
                    sub_data["current_period_end"], tz=UTC
                )

            plan = sub_data.get("metadata", {}).get("plan")
            if plan and plan in ("starter", "growth", "pro"):
                sub.plan = plan

            sub.save()
        except Subscription.DoesNotExist:
            pass

    @staticmethod
    def _handle_subscription_deleted(sub_data: dict) -> None:
        try:
            sub = Subscription.objects.get(
                stripe_subscription_id=sub_data["id"]
            )
            sub.status = "canceled"
            sub.save(update_fields=["status"])
        except Subscription.DoesNotExist:
            pass

    @staticmethod
    def _handle_invoice_paid(invoice: dict) -> None:
        subscription_id = invoice.get("subscription")
        if not subscription_id:
            return
        try:
            sub = Subscription.objects.get(
                stripe_subscription_id=subscription_id
            )
            sub.order_count = 0
            sub.save(update_fields=["order_count"])
        except Subscription.DoesNotExist:
            pass

    # ── Public Menu ────────────────────────────────────────────────

    @staticmethod
    def get_public_menu(slug: str) -> dict:
        """Return active menu categories for a restaurant by slug.

        Raises NotFound if restaurant doesn't exist.
        """
        from restaurants.models import MenuCategory
        from restaurants.serializers import PublicMenuCategorySerializer

        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            raise NotFound("Restaurant not found.")

        categories = (
            MenuCategory.objects.filter(restaurant=restaurant, is_active=True)
            .prefetch_related("items__variants", "items__modifiers")
            .order_by("sort_order")
        )

        return {
            "restaurant_name": restaurant.name,
            "tax_rate": str(restaurant.tax_rate),
            "categories": PublicMenuCategorySerializer(
                categories, many=True
            ).data,
        }

    @staticmethod
    def get_restaurant_by_slug(slug: str) -> Restaurant:
        """Look up a restaurant by slug. Raises NotFound if missing."""
        try:
            return Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            raise NotFound("Restaurant not found.")
