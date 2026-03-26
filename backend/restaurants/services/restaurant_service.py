import stripe
from django.conf import settings as django_settings
from rest_framework.exceptions import NotFound, ValidationError

from orders.models import Order
from orders.serializers import OrderResponseSerializer
from restaurants.models import (
    MenuCategory,
    Restaurant,
    RestaurantStaff,
    Subscription,
)
from restaurants.serializers import MenuItemSerializer, SubscriptionSerializer


class RestaurantService:
    """Service layer for restaurant domain operations."""

    # ── Restaurant Queries ─────────────────────────────────────────

    @staticmethod
    def get_user_restaurants(user):
        """Return queryset of restaurants the user owns or is staff of."""
        owned = Restaurant.objects.filter(owner=user)
        staff_ids = RestaurantStaff.objects.filter(user=user).values_list(
            "restaurant_id", flat=True
        )
        staffed = Restaurant.objects.filter(id__in=staff_ids)
        return (owned | staffed).distinct()

    # ── Menu ───────────────────────────────────────────────────────

    @staticmethod
    def get_full_menu(restaurant: Restaurant) -> dict:
        """Return the full menu including inactive items."""
        categories = (
            MenuCategory.objects.filter(restaurant=restaurant)
            .prefetch_related("items__variants", "items__modifiers")
            .order_by("sort_order")
        )
        cat_list = []
        for cat in categories:
            cat_list.append(
                {
                    "id": cat.id,
                    "name": cat.name,
                    "sort_order": cat.sort_order,
                    "is_active": cat.is_active,
                    "items": MenuItemSerializer(
                        cat.items.prefetch_related("variants", "modifiers"),
                        many=True,
                    ).data,
                }
            )

        return {"restaurant_name": restaurant.name, "categories": cat_list}

    # ── Orders ─────────────────────────────────────────────────────

    @staticmethod
    def get_restaurant_orders(restaurant: Restaurant) -> list:
        """Return serialized list of all orders for a restaurant."""
        orders = (
            Order.objects.filter(restaurant=restaurant)
            .select_related("restaurant")
            .prefetch_related("items__menu_item", "items__variant")
        )
        return OrderResponseSerializer(orders, many=True).data

    # ── Subscription ───────────────────────────────────────────────

    @staticmethod
    def _get_subscription(restaurant: Restaurant) -> Subscription:
        """Get subscription for restaurant, raising NotFound if missing."""
        try:
            return restaurant.subscription
        except Subscription.DoesNotExist:
            raise NotFound("No subscription found.")

    @staticmethod
    def create_checkout_session(
        restaurant: Restaurant, user, plan: str, interval: str
    ) -> str:
        """Create a Stripe Checkout session for a subscription.

        Returns the checkout URL.
        Raises ValidationError for invalid plan/price configuration.
        """
        plan_config = django_settings.SUBSCRIPTION_PLANS.get(plan)
        if not plan_config:
            raise ValidationError("Invalid plan.")

        price_key = "monthly_price_id" if interval == "monthly" else "annual_price_id"
        price_id = plan_config.get(price_key)
        if not price_id:
            raise ValidationError("Price not configured.")

        subscription = RestaurantService._get_subscription(restaurant)

        stripe.api_key = django_settings.STRIPE_SECRET_KEY

        if not subscription.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip(),
                metadata={
                    "restaurant_id": str(restaurant.id),
                    "restaurant_slug": restaurant.slug,
                },
            )
            subscription.stripe_customer_id = customer.id
            subscription.save(update_fields=["stripe_customer_id"])

        checkout_session = stripe.checkout.Session.create(
            customer=subscription.stripe_customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=(
                f"{django_settings.FRONTEND_URL}/account/restaurants/{restaurant.slug}"
                f"/billing?session_id={{CHECKOUT_SESSION_ID}}"
            ),
            cancel_url=f"{django_settings.FRONTEND_URL}/account/restaurants/{restaurant.slug}/billing",
            metadata={
                "restaurant_id": str(restaurant.id),
                "plan": plan,
            },
            subscription_data={
                "metadata": {
                    "restaurant_id": str(restaurant.id),
                    "plan": plan,
                },
            },
        )

        return checkout_session.url

    @staticmethod
    def create_billing_portal(restaurant: Restaurant) -> str:
        """Create a Stripe billing portal session.

        Returns the portal URL.
        Raises ValidationError if no billing account exists.
        """
        subscription = RestaurantService._get_subscription(restaurant)

        if not subscription.stripe_customer_id:
            raise ValidationError(
                "No billing account found. Please subscribe first."
            )

        stripe.api_key = django_settings.STRIPE_SECRET_KEY

        portal_session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=f"{django_settings.FRONTEND_URL}/account/restaurants/{restaurant.slug}/billing",
        )

        return portal_session.url

    @staticmethod
    def cancel_subscription(restaurant: Restaurant) -> Subscription:
        """Cancel subscription at period end.

        Returns updated Subscription instance.
        Raises ValidationError if no active paid subscription.
        """
        subscription = RestaurantService._get_subscription(restaurant)

        if not subscription.stripe_subscription_id:
            raise ValidationError("No active paid subscription to cancel.")

        stripe.api_key = django_settings.STRIPE_SECRET_KEY

        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True,
        )

        subscription.cancel_at_period_end = True
        subscription.save(update_fields=["cancel_at_period_end"])
        return subscription

    @staticmethod
    def reactivate_subscription(restaurant: Restaurant) -> Subscription:
        """Undo pending cancellation.

        Returns updated Subscription instance.
        Raises ValidationError if no active subscription.
        """
        subscription = RestaurantService._get_subscription(restaurant)

        if not subscription.stripe_subscription_id:
            raise ValidationError("No active subscription to reactivate.")

        stripe.api_key = django_settings.STRIPE_SECRET_KEY

        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=False,
        )

        subscription.cancel_at_period_end = False
        subscription.save(update_fields=["cancel_at_period_end"])
        return subscription
