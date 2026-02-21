import stripe as stripe_lib
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, NotFound, ValidationError
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken

from customers.authentication import CustomerAccessToken, CustomerRefreshToken
from customers.models import Customer
from customers.serializers import CustomerProfileSerializer
from customers.social_auth import verify_apple_token, verify_google_token
from orders.models import Order
from orders.serializers import OrderResponseSerializer


class CustomerService:
    """Service layer for customer domain operations."""

    # ── Social Authentication ──────────────────────────────────────

    @staticmethod
    def authenticate_google(token: str) -> Customer:
        """Verify Google token and find/create customer.

        Returns the customer (created or existing).
        Raises ValidationError on invalid token or missing email.
        """
        try:
            google_user = verify_google_token(token)
        except ValueError as e:
            raise ValidationError(f"Invalid Google token: {e}")

        email = google_user.get("email")
        if not email:
            raise ValidationError("Google account has no email.")

        customer, created = Customer.objects.get_or_create(
            email=email.lower(),
            defaults={
                "name": google_user["name"],
                "auth_provider": "google",
                "auth_provider_id": google_user["sub"],
            },
        )

        if not created and customer.auth_provider == "email":
            customer.auth_provider = "google"
            customer.auth_provider_id = google_user["sub"]
            customer.save(update_fields=["auth_provider", "auth_provider_id"])

        return customer

    @staticmethod
    def authenticate_apple(token: str, name: str = "") -> Customer:
        """Verify Apple token and find/create customer.

        Returns the customer (created or existing).
        Raises ValidationError on invalid token or missing email.
        """
        try:
            apple_user = verify_apple_token(token)
        except (ValueError, Exception) as e:
            raise ValidationError(f"Invalid Apple token: {e}")

        email = apple_user.get("email")
        if not email:
            raise ValidationError("Apple account has no email.")

        display_name = name or apple_user.get("name", "") or email.split("@")[0]

        customer, created = Customer.objects.get_or_create(
            email=email.lower(),
            defaults={
                "name": display_name,
                "auth_provider": "apple",
                "auth_provider_id": apple_user["sub"],
            },
        )

        if not created and customer.auth_provider == "email":
            customer.auth_provider = "apple"
            customer.auth_provider_id = apple_user["sub"]
            customer.save(update_fields=["auth_provider", "auth_provider_id"])

        return customer

    # ── Order Linking ──────────────────────────────────────────────

    @staticmethod
    def link_order_to_customer(order_id: str, customer: Customer) -> None:
        """Link an unlinked order to a customer (e.g. after social auth)."""
        if order_id:
            Order.objects.filter(id=order_id, customer__isnull=True).update(
                customer=customer
            )

    # ── Token Generation ───────────────────────────────────────────

    @staticmethod
    def generate_tokens(customer: Customer) -> dict:
        """Generate JWT access/refresh tokens and customer info dict."""
        refresh = CustomerRefreshToken.for_customer(customer)
        return {
            "customer": {
                "id": str(customer.id),
                "email": customer.email,
                "name": customer.name,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }

    @staticmethod
    def refresh_access_token(token_str: str) -> str:
        """Validate a refresh token and return a new access token string.

        Raises AuthenticationFailed on invalid/expired tokens.
        """
        try:
            refresh_token = UntypedToken(token_str)
            if refresh_token.get("token_type") != "customer_refresh":
                raise InvalidToken("Invalid token type")
            access = CustomerAccessToken()
            access.set_exp(from_time=refresh_token.current_time)
            access["customer_id"] = refresh_token["customer_id"]
            access["token_type"] = "customer_access"
            return str(access)
        except (InvalidToken, TokenError):
            raise AuthenticationFailed("Invalid or expired refresh token.")

    # ── Order History ──────────────────────────────────────────────

    @staticmethod
    def get_order_history(customer: Customer) -> list[dict]:
        """Return list of customer's past orders with restaurant details."""
        orders = (
            Order.objects.filter(customer=customer)
            .select_related("restaurant")
            .prefetch_related("items__menu_item", "items__variant")
        )
        data = []
        for order in orders:
            order_data = OrderResponseSerializer(order).data
            order_data["restaurant_name"] = order.restaurant.name
            order_data["restaurant_slug"] = order.restaurant.slug
            data.append(order_data)
        return data

    @staticmethod
    def get_order_detail(customer: Customer, order_id: str) -> dict:
        """Return single order detail including Stripe payment method info.

        Raises NotFound if order doesn't exist or doesn't belong to customer.
        """
        try:
            order = (
                Order.objects.select_related("restaurant")
                .prefetch_related("items__menu_item", "items__variant", "items__modifiers")
                .get(id=order_id, customer=customer)
            )
        except Order.DoesNotExist:
            raise NotFound("Order not found.")

        order_data = OrderResponseSerializer(order).data
        order_data["restaurant_name"] = order.restaurant.name
        order_data["restaurant_slug"] = order.restaurant.slug
        order_data["payment_method"] = CustomerService._resolve_payment_method(
            order.stripe_payment_method_id
        )
        return order_data

    @staticmethod
    def _resolve_payment_method(stripe_payment_method_id: str | None) -> dict | None:
        """Retrieve card details from Stripe for a payment method ID."""
        if not stripe_payment_method_id:
            return None
        try:
            stripe_lib.api_key = settings.STRIPE_SECRET_KEY
            pm = stripe_lib.PaymentMethod.retrieve(stripe_payment_method_id)
            if pm.card:
                return {
                    "brand": pm.card.brand,
                    "last4": pm.card.last4,
                    "exp_month": pm.card.exp_month,
                    "exp_year": pm.card.exp_year,
                }
        except Exception:
            pass
        return None

    # ── Payment Methods ────────────────────────────────────────────

    @staticmethod
    def list_payment_methods(customer: Customer) -> list[dict]:
        """List saved Stripe payment methods (cards) for a customer."""
        if not customer.stripe_customer_id:
            return []

        stripe_lib.api_key = settings.STRIPE_SECRET_KEY

        try:
            methods = stripe_lib.PaymentMethod.list(
                customer=customer.stripe_customer_id,
                type="card",
            )
        except stripe_lib.error.StripeError:
            return []

        return [
            {
                "id": pm.id,
                "brand": pm.card.brand,
                "last4": pm.card.last4,
                "exp_month": pm.card.exp_month,
                "exp_year": pm.card.exp_year,
            }
            for pm in methods.data
        ]

    @staticmethod
    def detach_payment_method(customer: Customer, pm_id: str) -> None:
        """Detach a payment method from customer's Stripe account.

        Raises NotFound if customer has no Stripe account or PM doesn't belong to them.
        Raises ValidationError on Stripe errors.
        """
        if not customer.stripe_customer_id:
            raise NotFound("No payment methods found.")

        stripe_lib.api_key = settings.STRIPE_SECRET_KEY

        try:
            pm = stripe_lib.PaymentMethod.retrieve(pm_id)
            if pm.customer != customer.stripe_customer_id:
                raise NotFound("Payment method not found.")
            stripe_lib.PaymentMethod.detach(pm_id)
        except stripe_lib.error.StripeError as e:
            raise ValidationError(f"Failed to remove payment method: {e}")
