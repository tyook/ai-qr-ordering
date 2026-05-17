import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import stripe
from django.conf import settings
from django.db import models as db_models
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from orders.broadcast import broadcast_order_to_customer, broadcast_order_to_kitchen
from orders.llm.agent import OrderAgent
from orders.llm.base import ParsedOrder
from orders.recommendation_service import RecommendationService
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

    STATUS_TIMESTAMP_FIELDS = {
        "confirmed": "confirmed_at",
        "preparing": "preparing_at",
        "ready": "ready_at",
        "completed": "completed_at",
    }

    @staticmethod
    def set_status_timestamp(order: Order, status: str) -> None:
        """Set the timestamp field corresponding to the given status."""
        field = OrderService.STATUS_TIMESTAMP_FIELDS.get(status)
        if field:
            setattr(order, field, timezone.now())
            order.save(update_fields=[field])

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
                    category__version__restaurant=restaurant,
                    status=MenuItem.Status.ACTIVE,
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
        unavailable_items = []
        total_price = Decimal("0.00")

        for parsed_item in parsed.items:
            try:
                menu_item = MenuItem.objects.get(
                    id=parsed_item.menu_item_id,
                    category__version__restaurant=restaurant,
                    status=MenuItem.Status.ACTIVE,
                )
                variant = MenuItemVariant.objects.get(
                    id=parsed_item.variant_id,
                    menu_item=menu_item,
                )
            except MenuItem.DoesNotExist:
                # Check if the item exists but is sold out or inactive
                try:
                    item = MenuItem.objects.get(
                        id=parsed_item.menu_item_id,
                        category__version__restaurant=restaurant,
                    )
                    unavailable_items.append({
                        "name": item.name,
                        "reason": "sold_out" if item.status == MenuItem.Status.SOLD_OUT else "inactive",
                    })
                except MenuItem.DoesNotExist:
                    pass
                continue
            except MenuItemVariant.DoesNotExist:
                continue

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
                    "description": menu_item.description or None,
                    "image_url": menu_item.image_url or None,
                    "is_featured": menu_item.is_featured,
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
            "unavailable_items": unavailable_items,
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
        customer_email: str = "",
        customer_phone: str = "",
        customer_allergies: list | None = None,
        tab=None,
    ) -> Order:
        """Create an order with its items. Returns the created Order."""
        order = Order.objects.create(
            restaurant=restaurant,
            table_identifier=table_identifier or None,
            user=user,
            customer_name=customer_name,
            customer_email=customer_email,
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
            tab=tab,
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

        if order_status == "confirmed":
            OrderService.set_status_timestamp(order, "confirmed")
            OrderService._send_confirmation_emails(order)

        return order

    @staticmethod
    def _send_confirmation_emails(order: Order) -> None:
        """Dispatch async email tasks for a newly confirmed order."""
        from orders.tasks import send_new_order_alert_email, send_order_confirmation_email
        send_order_confirmation_email.delay(str(order.id))
        send_new_order_alert_email.delay(str(order.id))

    # ── Subscription Check ─────────────────────────────────────────

    @staticmethod
    def is_subscription_active(restaurant: Restaurant) -> bool:
        """Return True if the restaurant may accept orders."""
        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return True  # Legacy restaurant, allow access

        if not subscription.is_active:
            return False

        # is_active returns True for "trialing" status, but trial may have expired
        if (
            subscription.status == "trialing"
            and subscription.trial_end
            and subscription.trial_end < timezone.now()
        ):
            return False

        return True

    @staticmethod
    def check_subscription(restaurant: Restaurant) -> Subscription | None:
        """Check that the restaurant's subscription is active.

        Raises PermissionDenied if subscription is inactive or trial expired.
        Returns the subscription (or None for legacy restaurants).
        """
        if not OrderService.is_subscription_active(restaurant):
            try:
                subscription = restaurant.subscription
                if subscription.status == "trialing":
                    raise PermissionDenied(
                        "Free trial has expired. Please subscribe to continue."
                    )
            except Subscription.DoesNotExist:
                pass
            raise PermissionDenied(
                "Subscription is not active. Please subscribe to continue."
            )
        try:
            return restaurant.subscription
        except Subscription.DoesNotExist:
            return None

    @staticmethod
    def increment_order_count(subscription: Subscription | None) -> None:
        """Increment the order count on a subscription (soft cap)."""
        if subscription:
            Subscription.objects.filter(id=subscription.id).update(
                order_count=db_models.F("order_count") + 1
            )

    # ── LLM Order Parsing ──────────────────────────────────────────

    @staticmethod
    def parse_order(restaurant: Restaurant, raw_input: str, user=None) -> dict:
        """Parse a natural language order via LLM and validate/price it.

        Checks subscription, runs LLM, validates against DB, increments count.
        Returns validated order dict or recommendation dict for frontend.
        """
        subscription = OrderService.check_subscription(restaurant)

        menu_context = build_menu_context(restaurant)
        agent_response = OrderAgent.run(
            raw_input=raw_input,
            menu_context=menu_context,
        )

        if agent_response.intent == "recommendation":
            # Do NOT increment order count for recommendations —
            # only actual orders consume the subscription quota.
            rec_result = RecommendationService.get_recommendations(
                restaurant=restaurant,
                user=user if user and user.is_authenticated else None,
                recommendation_context=agent_response.recommendation_context,
                max_items=3,
            )
            # Drop `greeting` from rec_result — the cards speak for themselves
            # in the voice chat UI (see spec: Non-Goals).
            return {
                "type": "recommendation",
                "items": rec_result["items"],
            }

        # intent == "order"
        parsed = agent_response.order
        result = OrderService.validate_and_price_order(restaurant, parsed)
        OrderService.increment_order_count(subscription)
        result["type"] = "order"
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
            ).update(status="confirmed", payment_status="paid", paid_at=timezone.now())
            if updated:
                order.refresh_from_db()
                OrderService.set_status_timestamp(order, "confirmed")
                broadcast_order_to_kitchen(order)
                broadcast_order_to_customer(order)
                from orders.tasks import broadcast_queue_updates
                broadcast_queue_updates.apply_async(
                    args=[str(order.restaurant_id), str(order.id)],
                )
                OrderService._send_confirmation_emails(order)
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
        OrderService.set_status_timestamp(order, new_status)
        broadcast_order_to_kitchen(order)
        broadcast_order_to_customer(order)

        # Trigger fan-out to other waiting customers
        from orders.tasks import broadcast_queue_updates
        broadcast_queue_updates.apply_async(
            args=[str(order.restaurant_id), str(order.id)],
        )
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
            "transfer.created": OrderService._handle_transfer_created,
            "transfer.failed": OrderService._handle_transfer_failed,
        }.get(event_type)

        if handler:
            handler(data_object)

    @staticmethod
    def _handle_payment_succeeded(intent: dict) -> None:
        from orders.models import TabPayment

        # Try Order first (existing behavior)
        try:
            order = Order.objects.get(stripe_payment_intent_id=intent["id"])
            updated = Order.objects.filter(
                id=order.id, payment_status="pending"
            ).update(status="confirmed", payment_status="paid", paid_at=timezone.now())
            if updated:
                order.refresh_from_db()
                OrderService.set_status_timestamp(order, "confirmed")
                broadcast_order_to_kitchen(order)
                broadcast_order_to_customer(order)
                from orders.tasks import broadcast_queue_updates
                broadcast_queue_updates.apply_async(
                    args=[str(order.restaurant_id), str(order.id)],
                )
                OrderService._send_confirmation_emails(order)
                from integrations.tasks import dispatch_order_to_pos
                dispatch_order_to_pos.delay(str(order.id))
            return
        except Order.DoesNotExist:
            pass

        # Try TabPayment
        try:
            tab_payment = TabPayment.objects.select_related("tab").get(
                stripe_payment_intent_id=intent["id"]
            )
        except TabPayment.DoesNotExist:
            return

        from orders.tab_service import TabService
        from orders.tab_broadcasts import broadcast_tab_update
        tab_payment.payment_status = "paid"
        tab_payment.paid_at = timezone.now()
        tab_payment.save(update_fields=["payment_status", "paid_at"])
        broadcast_tab_update(tab_payment.tab, "tab.payment_received")

        tab = tab_payment.tab
        if tab.amount_remaining <= 0:
            TabService.finalize_tab(tab)

    @staticmethod
    def _handle_payment_failed(intent: dict) -> None:
        from orders.models import TabPayment

        try:
            order = Order.objects.get(stripe_payment_intent_id=intent["id"])
            order.payment_status = "failed"
            order.save(update_fields=["payment_status"])
        except Order.DoesNotExist:
            try:
                tab_payment = TabPayment.objects.get(stripe_payment_intent_id=intent["id"])
                tab_payment.payment_status = "failed"
                tab_payment.save(update_fields=["payment_status"])
            except TabPayment.DoesNotExist:
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
            from restaurants.tasks import send_subscription_activated_email_task
            send_subscription_activated_email_task.delay(restaurant_id, plan)
        except Subscription.DoesNotExist:
            pass

    @staticmethod
    def _handle_subscription_updated(sub_data: dict) -> None:
        try:
            sub = Subscription.objects.get(
                stripe_subscription_id=sub_data["id"]
            )
            old_status = sub.status
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

            # Send payment failed email on transition to past_due
            if sub.status == "past_due" and old_status != "past_due":
                from restaurants.tasks import send_payment_failed_email_task
                send_payment_failed_email_task.delay(str(sub.restaurant_id))

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
    def _handle_account_updated(data):
        from restaurants.models import ConnectedAccount

        account_obj = data["object"]
        account_id = account_obj["id"]

        try:
            account = ConnectedAccount.objects.get(stripe_account_id=account_id)
            account.payouts_enabled = account_obj.get("payouts_enabled", False)
            account.charges_enabled = account_obj.get("charges_enabled", False)
            account.onboarding_complete = account_obj.get("details_submitted", False)
            account.save(update_fields=[
                "payouts_enabled", "charges_enabled", "onboarding_complete", "updated_at"
            ])
        except ConnectedAccount.DoesNotExist:
            logger.warning(f"ConnectedAccount not found for {account_id}")

    @staticmethod
    def _handle_transfer_created(data):
        from restaurants.models import Payout

        transfer_id = data["object"]["id"]
        Payout.objects.filter(stripe_transfer_id=transfer_id).update(
            status="in_transit"
        )

    @staticmethod
    def _handle_transfer_failed(data):
        from restaurants.models import Payout

        transfer_id = data["object"]["id"]
        payout = Payout.objects.filter(stripe_transfer_id=transfer_id).first()
        if payout:
            payout.status = "failed"
            payout.save(update_fields=["status"])
            payout.orders.update(payout_status="pending", payout=None)
            from restaurants.notifications import send_payout_failed_email
            send_payout_failed_email(payout.restaurant, payout.amount)

    @staticmethod
    def _handle_payout_paid(data):
        from restaurants.models import ConnectedAccount, Payout

        payout_obj = data["object"]
        stripe_payout_id = payout_obj["id"]
        amount_cents = payout_obj["amount"]
        account_id = data.get("account") or payout_obj.get("account")

        try:
            account = ConnectedAccount.objects.get(stripe_account_id=account_id)
        except ConnectedAccount.DoesNotExist:
            logger.warning(f"ConnectedAccount not found for payout event: {account_id}")
            return

        payout = Payout.objects.filter(
            restaurant=account.restaurant,
            status="in_transit",
            amount=Decimal(amount_cents) / 100,
        ).order_by("created_at").first()

        if payout:
            payout.status = "completed"
            payout.stripe_payout_id = stripe_payout_id
            payout.save(update_fields=["status", "stripe_payout_id"])
            payout.orders.update(payout_status="paid_out")
            from restaurants.notifications import send_payout_completed_email
            send_payout_completed_email(account.restaurant, payout.amount)

    @staticmethod
    def _handle_payout_failed(data):
        from restaurants.models import ConnectedAccount, Payout

        payout_obj = data["object"]
        account_id = data.get("account") or payout_obj.get("account")
        amount_cents = payout_obj["amount"]

        try:
            account = ConnectedAccount.objects.get(stripe_account_id=account_id)
        except ConnectedAccount.DoesNotExist:
            return

        payout = Payout.objects.filter(
            restaurant=account.restaurant,
            status="in_transit",
            amount=Decimal(amount_cents) / 100,
        ).order_by("created_at").first()

        if payout:
            payout.status = "failed"
            payout.save(update_fields=["status"])
            from restaurants.notifications import send_payout_failed_email
            send_payout_failed_email(account.restaurant, payout.amount)

    @staticmethod
    def handle_stripe_connect_webhook(payload, sig_header):
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_CONNECT_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            raise ValidationError("Invalid webhook signature")

        handler_name = {
            "account.updated": "_handle_account_updated",
            "payout.paid": "_handle_payout_paid",
            "payout.failed": "_handle_payout_failed",
        }.get(event["type"])

        if handler_name:
            handler = getattr(OrderService, handler_name)
            data = event["data"]
            data["account"] = event.get("account")
            handler(data)

        return {"status": "ok"}

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

            # Send payment success email
            amount_cents = invoice.get("amount_paid", 0)
            lines = invoice.get("lines", {}).get("data", [])
            period_end = lines[0].get("period", {}).get("end", 0) if lines else 0

            from restaurants.tasks import send_payment_success_email_task
            send_payment_success_email_task.delay(
                str(sub.restaurant_id), amount_cents, sub.plan, period_end
            )
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

        active_version = restaurant.menu_versions.filter(is_active=True).first()
        categories = (
            MenuCategory.objects.filter(version=active_version, is_active=True)
            .prefetch_related("items__variants", "items__modifiers")
            .order_by("sort_order")
        ) if active_version else MenuCategory.objects.none()

        # Determine payment mode from POS connection
        from integrations.models import POSConnection
        try:
            pos_conn = POSConnection.objects.get(restaurant=restaurant, is_active=True)
            payment_mode = pos_conn.payment_mode
        except POSConnection.DoesNotExist:
            payment_mode = "stripe"

        # Check if Stripe Connect payment is set up
        from restaurants.models import ConnectedAccount
        payment_ready = ConnectedAccount.objects.filter(
            restaurant=restaurant, onboarding_complete=True
        ).exists()

        from restaurants.serializers import OperatingHoursSerializer, HolidayOverrideSerializer
        operating_hours = restaurant.operating_hours.all()
        holiday_overrides = restaurant.holiday_overrides.all()

        return {
            "restaurant_name": restaurant.name,
            "tax_rate": str(restaurant.tax_rate),
            "categories": PublicMenuCategorySerializer(
                categories, many=True
            ).data,
            "payment_mode": payment_mode,
            "payment_model": restaurant.payment_model,
            "payment_ready": payment_ready,
            "accepting_orders": restaurant.accepting_orders,
            "operating_hours": OperatingHoursSerializer(operating_hours, many=True).data,
            "holiday_overrides": HolidayOverrideSerializer(holiday_overrides, many=True).data,
        }

    @staticmethod
    def get_restaurant_by_slug(slug: str) -> Restaurant:
        """Look up a restaurant by slug. Raises NotFound if missing."""
        try:
            return Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            raise NotFound("Restaurant not found.")

    @staticmethod
    def get_upsell_suggestions(order: Order) -> list[dict]:
        """Return 1-2 AI-driven upsell suggestions for an order."""
        restaurant = order.restaurant

        # Build cart summary from order items
        cart_lines = []
        cart_item_ids = set()
        for oi in order.items.select_related("menu_item", "variant").all():
            cart_lines.append(
                f"- {oi.quantity}x {oi.menu_item.name} ({oi.variant.label})"
            )
            cart_item_ids.add(oi.menu_item.id)

        return OrderService._run_upsell(restaurant, cart_lines, cart_item_ids)

    @staticmethod
    def get_cart_upsell_suggestions(
        restaurant: Restaurant, cart_items: list[dict]
    ) -> list[dict]:
        """Return 1-2 AI-driven upsell suggestions for cart items (pre-order).

        cart_items: list of dicts with menu_item_id, variant_id, quantity.
        """
        cart_lines = []
        cart_item_ids = set()
        for ci in cart_items:
            try:
                item = MenuItem.objects.get(
                    id=ci["menu_item_id"],
                    category__version__restaurant=restaurant,
                    status=MenuItem.Status.ACTIVE,
                )
                variant = MenuItemVariant.objects.get(
                    id=ci["variant_id"], menu_item=item
                )
            except (MenuItem.DoesNotExist, MenuItemVariant.DoesNotExist):
                continue
            cart_lines.append(
                f"- {ci['quantity']}x {item.name} ({variant.label})"
            )
            cart_item_ids.add(item.id)

        return OrderService._run_upsell(restaurant, cart_lines, cart_item_ids)

    @staticmethod
    def _run_upsell(
        restaurant: Restaurant,
        cart_lines: list[str],
        cart_item_ids: set[int],
    ) -> list[dict]:
        """Shared upsell logic: call the LLM agent and enrich results."""
        from orders.llm.upsell_agent import UpsellRecommendationAgent

        if not cart_lines:
            return []

        menu_context = build_menu_context(restaurant)
        cart_summary = "\n".join(cart_lines)

        result = UpsellRecommendationAgent.run(
            cart_summary=cart_summary,
            menu_context=menu_context,
        )

        suggestions = []
        for s in result.suggestions:
            if s.menu_item_id in cart_item_ids:
                continue
            try:
                item = MenuItem.objects.prefetch_related("variants").get(
                    id=s.menu_item_id,
                    category__version__restaurant=restaurant,
                    status=MenuItem.Status.ACTIVE,
                )
            except MenuItem.DoesNotExist:
                continue
            default_variant = item.variants.filter(is_default=True).first()
            if not default_variant:
                default_variant = item.variants.first()
            suggestions.append(
                {
                    "menu_item_id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "image_url": item.image_url,
                    "price": str(default_variant.price) if default_variant else None,
                    "variant_id": default_variant.id if default_variant else None,
                    "variant_label": default_variant.label if default_variant else None,
                    "reason": s.reason,
                }
            )
            if len(suggestions) >= 2:
                break

        return suggestions
