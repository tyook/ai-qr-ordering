import stripe as stripe_lib
from django.conf import settings
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from accounts.social_auth import verify_apple_token, verify_google_token


def split_name(name: str) -> tuple[str, str]:
    """Split a single name string into (first_name, last_name)."""
    parts = name.strip().split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""
    return first_name, last_name


def set_auth_cookies(response: Response, user: User) -> Response:
    """Generate JWT tokens and set them as httpOnly cookies on the response."""
    refresh = RefreshToken.for_user(user)
    secure = getattr(settings, "AUTH_COOKIE_SECURE", not settings.DEBUG)

    response.set_cookie(
        key="access_token",
        value=str(refresh.access_token),
        httponly=True,
        secure=secure,
        samesite="Lax",
        path="/",
        max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
    )
    response.set_cookie(
        key="refresh_token",
        value=str(refresh),
        httponly=True,
        secure=secure,
        samesite="Lax",
        path="/api/auth/refresh/",
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
    )
    return response


def clear_auth_cookies(response: Response) -> Response:
    """Delete auth cookies."""
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth/refresh/")
    return response


def user_to_dict(user: User) -> dict:
    """Serialize user to response dict."""
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "name": user.name,
        "phone": user.phone,
        "dietary_preferences": user.dietary_preferences,
        "allergies": user.allergies,
        "preferred_language": user.preferred_language,
        "is_restaurant_owner": user.is_restaurant_owner,
        "auth_provider": user.auth_provider,
        "onboarding_completed": user.onboarding_completed,
        "onboarding_dismissed": user.onboarding_dismissed,
        "owns_restaurant": user.owned_restaurants.exists(),
    }


def authenticate_google(token: str) -> User:
    """Verify Google token and find/create user."""
    try:
        google_user = verify_google_token(token)
    except ValueError as e:
        raise ValidationError(f"Invalid Google token: {e}")

    email = google_user.get("email")
    if not email:
        raise ValidationError("Google account has no email.")

    first_name, last_name = split_name(google_user["name"])

    user, created = User.objects.get_or_create(
        email=email.lower(),
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "auth_provider": "google",
            "auth_provider_id": google_user["sub"],
        },
    )

    if not created and user.auth_provider == "email":
        user.auth_provider = "google"
        user.auth_provider_id = google_user["sub"]
        user.save(update_fields=["auth_provider", "auth_provider_id"])

    return user


def authenticate_apple(token: str, name: str = "") -> User:
    """Verify Apple token and find/create user."""
    try:
        apple_user = verify_apple_token(token)
    except (ValueError, Exception) as e:
        raise ValidationError(f"Invalid Apple token: {e}")

    email = apple_user.get("email")
    if not email:
        raise ValidationError("Apple account has no email.")

    display_name = name or apple_user.get("name", "") or email.split("@")[0]
    first_name, last_name = split_name(display_name)

    user, created = User.objects.get_or_create(
        email=email.lower(),
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "auth_provider": "apple",
            "auth_provider_id": apple_user["sub"],
        },
    )

    if not created and user.auth_provider == "email":
        user.auth_provider = "apple"
        user.auth_provider_id = apple_user["sub"]
        user.save(update_fields=["auth_provider", "auth_provider_id"])

    return user


def link_order_to_user(order_id: str | None, user: User) -> None:
    """Link an unlinked order to a user (e.g. after social auth)."""
    if order_id:
        from orders.models import Order

        Order.objects.filter(id=order_id, user__isnull=True).update(user=user)


# ── Payment Methods ────────────────────────────────────────────

def list_payment_methods(user: User) -> list[dict]:
    if not user.stripe_customer_id:
        return []
    stripe_lib.api_key = settings.STRIPE_SECRET_KEY
    try:
        methods = stripe_lib.PaymentMethod.list(
            customer=user.stripe_customer_id, type="card"
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


def detach_payment_method(user: User, pm_id: str) -> None:
    if not user.stripe_customer_id:
        raise NotFound("No payment methods found.")
    stripe_lib.api_key = settings.STRIPE_SECRET_KEY
    try:
        pm = stripe_lib.PaymentMethod.retrieve(pm_id)
        if pm.customer != user.stripe_customer_id:
            raise NotFound("Payment method not found.")
        stripe_lib.PaymentMethod.detach(pm_id)
    except stripe_lib.error.StripeError as e:
        raise ValidationError(f"Failed to remove payment method: {e}")


# ── Order History ──────────────────────────────────────────────

def get_order_history(user: User) -> list[dict]:
    from orders.models import Order
    from orders.serializers import OrderResponseSerializer

    orders = (
        Order.objects.filter(user=user)
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


def get_order_detail(user: User, order_id: str) -> dict:
    from orders.models import Order
    from orders.serializers import OrderResponseSerializer

    try:
        order = (
            Order.objects.select_related("restaurant")
            .prefetch_related("items__menu_item", "items__variant", "items__modifiers")
            .get(id=order_id, user=user)
        )
    except Order.DoesNotExist:
        raise NotFound("Order not found.")

    order_data = OrderResponseSerializer(order).data
    order_data["restaurant_name"] = order.restaurant.name
    order_data["restaurant_slug"] = order.restaurant.slug
    order_data["payment_method"] = _resolve_payment_method(
        order.stripe_payment_method_id
    )
    return order_data


def _resolve_payment_method(stripe_payment_method_id: str | None) -> dict | None:
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
