# Unified Auth Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `Customer` and `User` into a single `accounts.User` model with httpOnly cookie-based JWT auth, consolidate all routes under `/account/*`.

**Architecture:** New `accounts` Django app owns the unified `User` model, all auth endpoints, social auth, and profile/payment views. `customers` app is deleted entirely. Frontend collapses two auth stores and two API clients into one cookie-based system. `/admin/*` routes become `/account/restaurants/*`.

**Tech Stack:** Django 4.2, DRF, simplejwt, Next.js 14, Zustand, Tailwind/shadcn

**Spec:** `docs/superpowers/specs/2026-03-26-unified-auth-design.md`

---

## File Structure

### Backend — New files

| File | Responsibility |
|------|----------------|
| `backend/accounts/__init__.py` | App init |
| `backend/accounts/apps.py` | Django app config |
| `backend/accounts/models.py` | Unified `User` model (merged from `restaurants.User` + `customers.Customer`) |
| `backend/accounts/managers.py` | `UserManager` (moved from `restaurants/managers.py`) |
| `backend/accounts/authentication.py` | `CookieJWTAuthentication` DRF class |
| `backend/accounts/social_auth.py` | Google/Apple token verification (moved from `customers/social_auth.py`) |
| `backend/accounts/services.py` | Auth service (token generation, social auth, order linking, payment methods) |
| `backend/accounts/serializers.py` | Register, login, profile serializers |
| `backend/accounts/views.py` | All auth + profile + account endpoints |
| `backend/accounts/urls.py` | URL routing for `/api/auth/*` and `/api/account/*` |
| `backend/accounts/admin.py` | Django admin registration |
| `backend/accounts/tests/__init__.py` | Test package |
| `backend/accounts/tests/factories.py` | `UserFactory` |
| `backend/accounts/tests/test_models.py` | User model tests |
| `backend/accounts/tests/test_authentication.py` | CookieJWTAuthentication tests |
| `backend/accounts/tests/test_views.py` | Auth endpoint tests |

### Backend — Modified files

| File | Change |
|------|--------|
| `backend/config/settings.py` | `AUTH_USER_MODEL`, `INSTALLED_APPS`, cookie/CSRF settings, JWT lifetimes |
| `backend/config/urls.py` | Add `accounts.urls`, remove `customers.urls`, remove auth from `restaurants.urls` |
| `backend/restaurants/models.py` | Remove `User` model, keep everything else |
| `backend/restaurants/managers.py` | Delete (moved to accounts) |
| `backend/restaurants/views.py` | Remove `RegisterView`, `LoginView`; update `RestaurantMixin` |
| `backend/restaurants/urls.py` | Remove auth routes |
| `backend/restaurants/serializers.py` | Remove `RegisterSerializer`, `LoginSerializer`; update `get_user_model()` |
| `backend/restaurants/services.py` | Update imports, fix hardcoded `/admin/` Stripe redirect URLs → `/account/restaurants/` |
| `backend/restaurants/tests/factories.py` | No change needed — already uses `get_user_model()` |
| `backend/orders/models.py` | `Order.customer` FK → `accounts.User`, rename field to `user` |
| `backend/orders/services.py` | Update `resolve_customer_from_token` → `resolve_user_from_request`, rename `customer` param to `user` in `create_order` and `create_payment_intent` |
| `backend/orders/views.py` | Update customer resolution, remove `authentication_classes = []` from `ConfirmOrderView` and `CreatePaymentView` (let `CookieJWTAuthentication` run — it returns `None` for guests, `AllowAny` still permits the request) |
| `backend/orders/tests/factories.py` | Update `OrderFactory` FK |

### Backend — Deleted files

| File |
|------|
| `backend/customers/` (entire app) |

### Frontend — New files

| File | Responsibility |
|------|----------------|
| `frontend/src/hooks/use-auth.ts` | `useRequireAuth()` and `useRequireRestaurantAccess()` hooks |
| `frontend/src/app/account/restaurants/page.tsx` | Restaurant dashboard (moved from `/admin/page.tsx`) |
| `frontend/src/app/account/restaurants/[slug]/menu/page.tsx` | Menu management (moved from `/admin/[slug]/menu/`) |
| `frontend/src/app/account/restaurants/[slug]/orders/page.tsx` | Restaurant orders (moved from `/admin/[slug]/orders/`) |
| `frontend/src/app/account/restaurants/[slug]/billing/page.tsx` | Billing (moved from `/admin/[slug]/billing/`) |
| `frontend/src/app/account/restaurants/[slug]/settings/page.tsx` | Settings (moved from `/admin/[slug]/settings/`) |

### Frontend — Modified files

| File | Change |
|------|--------|
| `frontend/src/lib/api.ts` | Single cookie-based `apiFetch()`, remove `customerApiFetch()` and all customer-specific functions, update endpoints |
| `frontend/src/stores/auth-store.ts` | Unified store with tri-state `isAuthenticated`, social auth, cookie-based |
| `frontend/src/types/index.ts` | Unified `User` type, update `AuthResponse`, remove `CustomerAuthResponse`, rename `CustomerOrderHistoryItem` → `OrderHistoryItem`, `CustomerOrderDetail` → `OrderDetail` |
| `frontend/src/components/Header.tsx` | Unified header with conditional restaurant nav |
| `frontend/src/components/ConditionalHeader.tsx` | Simplify — single `Header` for all non-order routes |
| `frontend/src/components/SocialLoginButtons.tsx` | Update to use unified auth store |
| `frontend/src/components/ThemeProvider.tsx` | Update `/admin` path check → `/account/restaurants` |
| `frontend/src/app/page.tsx` | Update `/admin/register` links → `/account/register` |
| `frontend/src/app/account/login/page.tsx` | Use unified auth store |
| `frontend/src/app/account/register/page.tsx` | Use unified auth store, add first_name/last_name fields |
| `frontend/src/app/account/profile/page.tsx` | Use unified auth store + `apiFetch`, split name field into first_name/last_name |
| `frontend/src/app/account/orders/page.tsx` | Use `apiFetch` instead of `customerApiFetch` |
| `frontend/src/app/account/orders/[orderId]/page.tsx` | Use `apiFetch` instead of `customerApiFetch` |
| `frontend/src/app/account/payment-methods/page.tsx` | Use `apiFetch` instead of `customerApiFetch` |
| `frontend/src/app/order/[slug]/page.tsx` | Replace `useCustomerAuthStore` → `useAuthStore` |
| `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx` | Replace `useCustomerAuthStore` → `useAuthStore`, update `useCustomerProfile` → `useProfile` |
| `frontend/src/app/order/[slug]/components/PaymentStep.tsx` | Replace `useCustomerAuthStore` → `useAuthStore` |
| `frontend/src/app/order/[slug]/components/SubmittedStep.tsx` | Replace `useCustomerAuthStore` → `useAuthStore` |
| `frontend/src/hooks/use-customer-profile.ts` | Rename to `use-profile.ts`, use `fetchMe`/`updateProfile` |
| `frontend/src/hooks/use-customer-orders.ts` | Rename to `use-orders.ts`, use `fetchOrderHistory`/`fetchOrderDetail` |
| `frontend/src/app/layout.tsx` | Remove conditional Google/Apple script loading if needed |

### Frontend — Deleted files

| File |
|------|
| `frontend/src/stores/customer-auth-store.ts` |
| `frontend/src/components/CustomerHeader.tsx` |
| `frontend/src/app/admin/` (entire directory — including `admin/login` and `admin/register` which are NOT migrated, just deleted) |

---

## Chunk 1: Backend — `accounts` App (Model, Auth, Services)

### Task 1: Create `accounts` app skeleton and User model

**Files:**
- Create: `backend/accounts/__init__.py`
- Create: `backend/accounts/apps.py`
- Create: `backend/accounts/managers.py`
- Create: `backend/accounts/models.py`
- Create: `backend/accounts/admin.py`

- [ ] **Step 1: Create the app directory and init files**

```bash
mkdir -p backend/accounts/tests
touch backend/accounts/__init__.py
touch backend/accounts/tests/__init__.py
```

- [ ] **Step 2: Create `apps.py`**

```python
# backend/accounts/apps.py
from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
```

- [ ] **Step 3: Create `managers.py`** (moved from `restaurants/managers.py`)

```python
# backend/accounts/managers.py
from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        # Note: deliberately drops the old `role="admin"` default — unified User has no role field
        return self.create_user(email, password, **extra_fields)
```

- [ ] **Step 4: Create `models.py`** with unified User

```python
# backend/accounts/models.py
import uuid

import stripe
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from accounts.managers import UserManager


class User(AbstractUser):
    class AuthProvider(models.TextChoices):
        EMAIL = "email", "Email"
        GOOGLE = "google", "Google"
        APPLE = "apple", "Apple"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, default="")
    stripe_customer_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )

    # Merged from Customer model
    auth_provider = models.CharField(
        max_length=10, choices=AuthProvider.choices, default=AuthProvider.EMAIL
    )
    auth_provider_id = models.CharField(max_length=255, blank=True, default="")
    dietary_preferences = models.JSONField(default=list, blank=True)
    allergies = models.JSONField(default=list, blank=True)
    preferred_language = models.CharField(max_length=10, blank=True, default="en-US")

    username = None
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    @property
    def is_restaurant_owner(self):
        return self.owned_restaurants.exists() or self.staff_roles.exists()

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_or_create_stripe_customer(self):
        if self.stripe_customer_id:
            return self.stripe_customer_id
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe_customer = stripe.Customer.create(
            email=self.email,
            name=self.name,
            metadata={"user_id": str(self.id)},
        )
        self.stripe_customer_id = stripe_customer.id
        self.save(update_fields=["stripe_customer_id"])
        return self.stripe_customer_id

    def __str__(self):
        return self.email
```

- [ ] **Step 5: Create `admin.py`**

```python
# backend/accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "first_name", "last_name", "auth_provider", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal", {"fields": ("first_name", "last_name", "phone")}),
        ("Auth Provider", {"fields": ("auth_provider", "auth_provider_id")}),
        ("Preferences", {"fields": ("dietary_preferences", "allergies", "preferred_language")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "first_name", "last_name")}),
    )
```

- [ ] **Step 6: Commit**

```bash
git add backend/accounts/
git commit -m "feat(accounts): create accounts app with unified User model"
```

### Task 2: CookieJWTAuthentication

**Files:**
- Create: `backend/accounts/authentication.py`
- Create: `backend/accounts/tests/test_authentication.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/accounts/tests/test_authentication.py
import pytest
from django.test import RequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.authentication import CookieJWTAuthentication
from accounts.tests.factories import UserFactory


@pytest.fixture
def auth():
    return CookieJWTAuthentication()


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.mark.django_db
class TestCookieJWTAuthentication:
    def test_authenticates_from_cookie(self, auth, rf):
        user = UserFactory()
        token = RefreshToken.for_user(user)
        request = rf.get("/")
        request.COOKIES["access_token"] = str(token.access_token)
        result_user, _ = auth.authenticate(request)
        assert result_user.id == user.id

    def test_falls_back_to_authorization_header(self, auth, rf):
        user = UserFactory()
        token = RefreshToken.for_user(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        result_user, _ = auth.authenticate(request)
        assert result_user.id == user.id

    def test_returns_none_when_no_token(self, auth, rf):
        request = rf.get("/")
        result = auth.authenticate(request)
        assert result is None

    def test_returns_none_for_invalid_cookie(self, auth, rf):
        request = rf.get("/")
        request.COOKIES["access_token"] = "invalid-token"
        result = auth.authenticate(request)
        assert result is None
```

- [ ] **Step 2: Create UserFactory**

```python
# backend/accounts/tests/factories.py
import factory

from accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest accounts/tests/test_authentication.py -v`
Expected: FAIL — `CookieJWTAuthentication` does not exist yet

- [ ] **Step 4: Write `CookieJWTAuthentication`**

```python
# backend/accounts/authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


class CookieJWTAuthentication(JWTAuthentication):
    """Read JWT from httpOnly cookie, fall back to Authorization header."""

    def authenticate(self, request):
        # Try cookie first
        raw_token = request.COOKIES.get("access_token")
        if raw_token:
            try:
                validated_token = AccessToken(raw_token)
                user = self.get_user(validated_token)
                return (user, validated_token)
            except (InvalidToken, TokenError):
                return None

        # Fall back to Authorization header
        header = self.get_header(request)
        if header is None:
            return None
        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None
        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
            return (user, validated_token)
        except (InvalidToken, TokenError):
            return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest accounts/tests/test_authentication.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/accounts/authentication.py backend/accounts/tests/
git commit -m "feat(accounts): add CookieJWTAuthentication with header fallback"
```

### Task 3: Auth services (token cookies, social auth, name splitting)

**Files:**
- Create: `backend/accounts/services.py`
- Move: `backend/customers/social_auth.py` → `backend/accounts/social_auth.py`

- [ ] **Step 1: Copy `social_auth.py` to accounts** (unchanged)

```bash
cp backend/customers/social_auth.py backend/accounts/social_auth.py
```

- [ ] **Step 2: Write the service module**

```python
# backend/accounts/services.py
import stripe as stripe_lib
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, NotFound, ValidationError
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
```

- [ ] **Step 3: Commit**

```bash
git add backend/accounts/services.py backend/accounts/social_auth.py
git commit -m "feat(accounts): add auth services, social auth, cookie helpers"
```

### Task 4: Serializers and Views

**Files:**
- Create: `backend/accounts/serializers.py`
- Create: `backend/accounts/views.py`
- Create: `backend/accounts/urls.py`

- [ ] **Step 1: Create serializers**

```python
# backend/accounts/serializers.py
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import User
from accounts.services import split_name


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True, validators=[validate_password])
    first_name = serializers.CharField(max_length=150, required=False, default="")
    last_name = serializers.CharField(max_length=150, required=False, default="")
    name = serializers.CharField(max_length=255, required=False, default="")
    phone = serializers.CharField(max_length=20, required=False, default="")
    link_order_id = serializers.UUIDField(required=False, allow_null=True, default=None)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate(self, data):
        # If name provided but not first/last, split it
        if data.get("name") and not data.get("first_name"):
            data["first_name"], data["last_name"] = split_name(data["name"])
        if not data.get("first_name"):
            raise serializers.ValidationError({"first_name": "First name is required."})
        return data

    def create(self, validated_data):
        validated_data.pop("name", None)
        link_order_id = validated_data.pop("link_order_id", None)
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)

        if link_order_id:
            from accounts.services import link_order_to_user
            link_order_to_user(str(link_order_id), user)

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = User.objects.filter(email__iexact=data["email"]).first()
        if not user or not user.check_password(data["password"]):
            raise serializers.ValidationError("Invalid email or password.")
        data["user"] = user
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="name", read_only=True)
    is_restaurant_owner = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "name",
            "phone", "dietary_preferences", "allergies",
            "preferred_language", "auth_provider", "is_restaurant_owner",
            "date_joined",
        ]
        read_only_fields = ["id", "email", "auth_provider", "date_joined"]
```

- [ ] **Step 2: Create views**

```python
# backend/accounts/views.py
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import services
from accounts.serializers import LoginSerializer, RegisterSerializer, UserProfileSerializer


class CSRFTokenView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        return ensure_csrf_cookie(view)

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        return csrf_exempt(view)

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        response = Response(
            {"user": services.user_to_dict(user)},
            status=status.HTTP_201_CREATED,
        )
        return services.set_auth_cookies(response, user)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        return csrf_exempt(view)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        response = Response({"user": services.user_to_dict(user)})
        return services.set_auth_cookies(response, user)


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        return csrf_exempt(view)

    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response(
                {"detail": "Google token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = services.authenticate_google(token)
        services.link_order_to_user(request.data.get("link_order_id"), user)
        response = Response({"user": services.user_to_dict(user)})
        return services.set_auth_cookies(response, user)


class AppleAuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        return csrf_exempt(view)

    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response(
                {"detail": "Apple token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = services.authenticate_apple(
            token, name=request.data.get("name", "")
        )
        services.link_order_to_user(request.data.get("link_order_id"), user)
        response = Response({"user": services.user_to_dict(user)})
        return services.set_auth_cookies(response, user)


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        return csrf_exempt(view)

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token not found."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        # Validate and generate new access token
        from rest_framework_simplejwt.tokens import RefreshToken

        try:
            refresh = RefreshToken(refresh_token)
            user_id = refresh.get("user_id")
            from accounts.models import User

            user = User.objects.get(id=user_id)
        except Exception:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        response = Response({"user": services.user_to_dict(user)})
        return services.set_auth_cookies(response, user)


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        response = Response({"detail": "Logged out."})
        return services.clear_auth_cookies(response)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.user_to_dict(request.user))

    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(services.user_to_dict(request.user))


class OrderHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.get_order_history(request.user))


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        return Response(services.get_order_detail(request.user, order_id))


class PaymentMethodsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.list_payment_methods(request.user))


class PaymentMethodDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pm_id):
        services.detach_payment_method(request.user, pm_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 3: Create URL routing**

```python
# backend/accounts/urls.py
from django.urls import path

from accounts.views import (
    AppleAuthView,
    CSRFTokenView,
    GoogleAuthView,
    LoginView,
    LogoutView,
    MeView,
    OrderDetailView,
    OrderHistoryView,
    PaymentMethodDetailView,
    PaymentMethodsView,
    RefreshView,
    RegisterView,
)

urlpatterns = [
    # Auth
    path("auth/csrf/", CSRFTokenView.as_view(), name="csrf-token"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/google/", GoogleAuthView.as_view(), name="google-auth"),
    path("auth/apple/", AppleAuthView.as_view(), name="apple-auth"),
    path("auth/refresh/", RefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    # Account
    path("account/orders/", OrderHistoryView.as_view(), name="account-orders"),
    path("account/orders/<uuid:order_id>/", OrderDetailView.as_view(), name="account-order-detail"),
    path("account/payment-methods/", PaymentMethodsView.as_view(), name="account-payment-methods"),
    path("account/payment-methods/<str:pm_id>/", PaymentMethodDetailView.as_view(), name="account-payment-method-detail"),
]
```

- [ ] **Step 4: Commit**

```bash
git add backend/accounts/serializers.py backend/accounts/views.py backend/accounts/urls.py
git commit -m "feat(accounts): add auth views, serializers, and URL routing"
```

### Task 5: Update Django settings and root URLs

**Files:**
- Modify: `backend/config/settings.py`
- Modify: `backend/config/urls.py`

- [ ] **Step 1: Update `settings.py`**

Changes:
1. `AUTH_USER_MODEL = "accounts.User"`
2. Replace `"customers"` with `"accounts"` in `INSTALLED_APPS`
3. Add `CookieJWTAuthentication` as default DRF auth class
4. Add cookie settings
5. Update JWT lifetimes

In `INSTALLED_APPS`, replace `"customers"` with `"accounts"`:
```python
INSTALLED_APPS = [
    ...
    # Local
    "accounts",
    "restaurants",
    "orders",
]
```

Update `AUTH_USER_MODEL`:
```python
AUTH_USER_MODEL = "accounts.User"
```

Update `REST_FRAMEWORK`:
```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.CookieJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}
```

Update `SIMPLE_JWT`:
```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}
```

Add cookie settings (after CORS section):
```python
# Cookie auth
AUTH_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False  # Frontend reads csrftoken cookie
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
]
```

- [ ] **Step 2: Update `config/urls.py`**

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("restaurants.urls")),
    path("api/", include("orders.urls")),
]
```

Note: renamed Django admin to `django-admin/` to avoid confusion with the removed frontend `/admin` route.

- [ ] **Step 3: Commit**

```bash
git add backend/config/settings.py backend/config/urls.py
git commit -m "feat(config): wire accounts app, cookie auth, update settings"
```

### Task 6: Update `restaurants` app — remove User model and auth views

**Files:**
- Modify: `backend/restaurants/models.py`
- Delete: `backend/restaurants/managers.py`
- Modify: `backend/restaurants/views.py`
- Modify: `backend/restaurants/urls.py`
- Modify: `backend/restaurants/serializers.py`
- Modify: `backend/restaurants/services.py`
- Modify: `backend/restaurants/tests/factories.py`

- [ ] **Step 1: Remove User model from `restaurants/models.py`**

Delete lines 1-29 (the `User` class and its imports: `AbstractUser`, `UserManager`). Keep `Restaurant` and everything below. Update the `Restaurant.owner` FK import:

```python
# backend/restaurants/models.py — top of file after removing User
import uuid

from django.conf import settings
from django.db import models
```

Change `Restaurant.owner`:
```python
owner = models.ForeignKey(
    settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_restaurants"
)
```

Change `RestaurantStaff.user`:
```python
user = models.ForeignKey(
    settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_roles"
)
```

- [ ] **Step 2: Delete `restaurants/managers.py`**

```bash
rm backend/restaurants/managers.py
```

- [ ] **Step 3: Update `restaurants/views.py`**

Remove `RegisterView` and `LoginView` (lines 19-42). Remove their imports (`RegisterSerializer`, `LoginSerializer`, `RefreshToken`).

- [ ] **Step 4: Update `restaurants/urls.py`**

Remove auth routes (lines 25-27: register, login, refresh). Remove imports for `RegisterView`, `LoginView`, `TokenRefreshView`.

- [ ] **Step 5: Update `restaurants/serializers.py`**

Remove `RegisterSerializer` (lines 19-41) and `LoginSerializer` (lines 44-53). Remove `RefreshToken` import and `validate_password` import.

- [ ] **Step 6: Update `restaurants/services.py`**

Update Stripe checkout redirect URLs from `/admin/{slug}/billing` to `/account/restaurants/{slug}/billing`:

```python
# In create_checkout_session():
success_url=f"{settings.FRONTEND_URL}/account/restaurants/{restaurant.slug}/billing?session_id={{CHECKOUT_SESSION_ID}}",
cancel_url=f"{settings.FRONTEND_URL}/account/restaurants/{restaurant.slug}/billing",

# In create_billing_portal():
return_url=f"{settings.FRONTEND_URL}/account/restaurants/{restaurant.slug}/billing",
```

- [ ] **Step 7: Note: `restaurants/tests/factories.py` needs no change**

The existing `UserFactory` already uses `get_user_model()`, which will automatically resolve to `accounts.User` after the `AUTH_USER_MODEL` setting change.

- [ ] **Step 8: Commit**

```bash
git add backend/restaurants/
git rm backend/restaurants/managers.py
git commit -m "refactor(restaurants): remove User model and auth views, use accounts.User"
```

### Task 7: Update `orders` app — FK and customer resolution

**Files:**
- Modify: `backend/orders/models.py`
- Modify: `backend/orders/services.py`
- Modify: `backend/orders/tests/factories.py`

- [ ] **Step 1: Update `Order.customer` FK in `orders/models.py`**

Change the FK from `customers.Customer` to `settings.AUTH_USER_MODEL`, rename field to `user`:

```python
from django.conf import settings

# In Order class:
user = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="orders",
)
```

Keep `customer_name` and `customer_phone` as-is.

- [ ] **Step 2: Update `orders/services.py`**

Replace `resolve_customer_from_token` with `resolve_user_from_request`:

```python
@staticmethod
def resolve_user_from_request(request) -> "User | None":
    """Extract user from request (set by CookieJWTAuthentication or header).

    Returns None if no authenticated user.
    """
    if hasattr(request, "user") and request.user and request.user.is_authenticated:
        return request.user
    return None
```

Update `create_order` to use `user=` parameter instead of `customer=`.

Update `create_payment_intent` to rename `customer=` parameter to `user=`, and update `customer.get_or_create_stripe_customer()` → `user.get_or_create_stripe_customer()`.

Update all `Order.objects.filter(customer=...)` → `Order.objects.filter(user=...)`.

- [ ] **Step 3: Update `orders/views.py`**

Replace `OrderService.resolve_customer_from_token(request)` calls with `OrderService.resolve_user_from_request(request)`.

**Remove `authentication_classes = []`** from `ConfirmOrderView` and `CreatePaymentView`. This allows `CookieJWTAuthentication` to run and populate `request.user` for logged-in customers (it returns `None` gracefully for guests). `permission_classes = [AllowAny]` still allows unauthenticated requests through.

Update `create_order(... customer=customer ...)` → `create_order(... user=user ...)`.

Update `create_payment_intent(... customer=customer ...)` → `create_payment_intent(... user=user ...)`.

Update allergy resolution: `customer.allergies` → `user.allergies`.

- [ ] **Step 4: Update `orders/tests/factories.py`**

Rename `OrderFactory.customer` field to `user`, keep default as `None` (guest orders):

```python
user = None  # Guest orders have no user
```

- [ ] **Step 5: Commit**

```bash
git add backend/orders/
git commit -m "refactor(orders): rename customer FK to user, update resolution"
```

### Task 8: Delete `customers` app and reset migrations

**Files:**
- Delete: `backend/customers/` (entire directory)
- Regenerate: all migrations

- [ ] **Step 1: Delete customers app**

```bash
rm -rf backend/customers/
```

- [ ] **Step 2: Remove old migrations**

```bash
rm -rf backend/accounts/migrations/
rm -rf backend/restaurants/migrations/
rm -rf backend/orders/migrations/
mkdir -p backend/accounts/migrations backend/restaurants/migrations backend/orders/migrations
touch backend/accounts/migrations/__init__.py
touch backend/restaurants/migrations/__init__.py
touch backend/orders/migrations/__init__.py
```

- [ ] **Step 3: Generate fresh migrations**

```bash
cd backend && python manage.py makemigrations accounts restaurants orders
```

- [ ] **Step 4: Drop and recreate the database, then apply migrations**

`flush` may fail because it references deleted tables. Since no production data exists, drop and recreate:

```bash
dropdb aiqr && createdb aiqr
cd backend && python manage.py migrate
```

If using Docker, instead run:
```bash
docker compose exec db psql -U aiqr -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
cd backend && python manage.py migrate
```

- [ ] **Step 5: Run backend tests**

```bash
cd backend && python -m pytest -v
```

Expected: All tests pass (accounts tests pass, restaurants tests pass, orders tests pass)

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: delete customers app, reset migrations for unified User"
```

### Task 9: Write auth view tests

**Files:**
- Create/Modify: `backend/accounts/tests/test_views.py`

- [ ] **Step 1: Write tests for register, login, logout, refresh, me, social auth**

```python
# backend/accounts/tests/test_views.py
import pytest
from django.test import TestClient
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory


@pytest.fixture
def api():
    return APIClient()


@pytest.mark.django_db
class TestRegister:
    def test_register_with_first_last_name(self, api):
        resp = api.post("/api/auth/register/", {
            "email": "new@example.com",
            "password": "StrongPass123!",
            "first_name": "Jane",
            "last_name": "Doe",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["user"]["email"] == "new@example.com"
        assert resp.data["user"]["first_name"] == "Jane"
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies
        assert resp.cookies["access_token"]["httponly"]

    def test_register_with_single_name(self, api):
        resp = api.post("/api/auth/register/", {
            "email": "new@example.com",
            "password": "StrongPass123!",
            "name": "Jane Doe",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["user"]["first_name"] == "Jane"
        assert resp.data["user"]["last_name"] == "Doe"

    def test_register_duplicate_email(self, api):
        UserFactory(email="existing@example.com")
        resp = api.post("/api/auth/register/", {
            "email": "existing@example.com",
            "password": "StrongPass123!",
            "first_name": "Jane",
            "last_name": "Doe",
        }, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, api):
        UserFactory(email="user@example.com")
        resp = api.post("/api/auth/login/", {
            "email": "user@example.com",
            "password": "testpass123",
        }, format="json")
        assert resp.status_code == 200
        assert "access_token" in resp.cookies

    def test_login_wrong_password(self, api):
        UserFactory(email="user@example.com")
        resp = api.post("/api/auth/login/", {
            "email": "user@example.com",
            "password": "wrong",
        }, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestMe:
    def test_me_returns_user(self, api):
        user = UserFactory(email="me@example.com")
        # Login to get cookies
        api.post("/api/auth/login/", {
            "email": "me@example.com", "password": "testpass123",
        }, format="json")
        resp = api.get("/api/auth/me/")
        assert resp.status_code == 200
        assert resp.data["email"] == "me@example.com"
        assert "is_restaurant_owner" in resp.data

    def test_me_unauthenticated(self, api):
        resp = api.get("/api/auth/me/")
        assert resp.status_code in (401, 403)


@pytest.mark.django_db
class TestLogout:
    def test_logout_clears_cookies(self, api):
        UserFactory(email="user@example.com")
        api.post("/api/auth/login/", {
            "email": "user@example.com", "password": "testpass123",
        }, format="json")
        resp = api.post("/api/auth/logout/")
        assert resp.status_code == 200
        # Cookies should be cleared (max-age=0)
        assert resp.cookies["access_token"].value == ""


@pytest.mark.django_db
class TestRefresh:
    def test_refresh_returns_new_cookies(self, api):
        UserFactory(email="user@example.com")
        login_resp = api.post("/api/auth/login/", {
            "email": "user@example.com", "password": "testpass123",
        }, format="json")
        # The refresh cookie is scoped to /api/auth/refresh/
        # APIClient should send cookies automatically
        resp = api.post("/api/auth/refresh/")
        assert resp.status_code == 200
        assert "access_token" in resp.cookies
```

- [ ] **Step 2: Add tests for cookie attributes, CSRF, and order linking**

```python
@pytest.mark.django_db
class TestCookieAttributes:
    def test_cookies_are_samesite_lax(self, api):
        resp = api.post("/api/auth/register/", {
            "email": "cookie@example.com",
            "password": "StrongPass123!",
            "first_name": "Test",
            "last_name": "User",
        }, format="json")
        assert resp.cookies["access_token"]["samesite"] == "Lax"
        assert resp.cookies["refresh_token"]["samesite"] == "Lax"

    def test_refresh_cookie_scoped_to_refresh_path(self, api):
        resp = api.post("/api/auth/register/", {
            "email": "path@example.com",
            "password": "StrongPass123!",
            "first_name": "Test",
            "last_name": "User",
        }, format="json")
        assert resp.cookies["refresh_token"]["path"] == "/api/auth/refresh/"


@pytest.mark.django_db
class TestCSRF:
    def test_csrf_endpoint_sets_cookie(self, api):
        resp = api.get("/api/auth/csrf/")
        assert resp.status_code == 200
        assert "csrftoken" in resp.cookies

    def test_me_patch_requires_csrf_when_authenticated(self, api):
        UserFactory(email="csrf@example.com")
        api.post("/api/auth/login/", {
            "email": "csrf@example.com", "password": "testpass123",
        }, format="json")
        # PATCH /api/auth/me/ — should work because APIClient handles CSRF
        resp = api.patch("/api/auth/me/", {"phone": "555-0100"}, format="json")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestOrderLinking:
    def test_register_links_order(self, api):
        from orders.tests.factories import OrderFactory
        order = OrderFactory(user=None)
        resp = api.post("/api/auth/register/", {
            "email": "linker@example.com",
            "password": "StrongPass123!",
            "first_name": "Jane",
            "last_name": "Doe",
            "link_order_id": str(order.id),
        }, format="json")
        assert resp.status_code == 201
        order.refresh_from_db()
        assert order.user is not None
```

- [ ] **Step 3: Run tests**

Run: `cd backend && python -m pytest accounts/tests/test_views.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add backend/accounts/tests/test_views.py
git commit -m "test(accounts): add auth view tests for register, login, logout, refresh, me, csrf, cookies, order linking"
```

---

## Chunk 2: Frontend — Unified Auth Store and API Client

### Task 10: Update TypeScript types

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Update types**

Replace `CustomerAuthResponse` and `CustomerProfile` with unified types:

```typescript
// Replace CustomerProfile with User
export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  name: string;
  phone: string;
  dietary_preferences: string[];
  allergies: string[];
  preferred_language: string;
  auth_provider: string;
  is_restaurant_owner: boolean;
}

// Auth responses now return user data only (tokens are in cookies)
export interface AuthResponse {
  user: User;
}
```

Remove `CustomerAuthResponse` and `CustomerProfile`. Rename `CustomerOrderHistoryItem` → `OrderHistoryItem` and `CustomerOrderDetail` → `OrderDetail`:

```typescript
export interface OrderHistoryItem extends OrderResponse {
  restaurant_name: string;
  restaurant_slug: string;
}

export interface OrderDetail extends OrderHistoryItem {
  payment_method: {
    brand: string;
    last4: string;
    exp_month: number;
    exp_year: number;
  } | null;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "refactor(types): unified User type, remove customer-specific types"
```

### Task 11: Rewrite `api.ts` — single cookie-based client

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Rewrite the API client**

Replace the entire file. Key changes:
- Single `apiFetch()` with `credentials: "include"`
- No `Authorization` header
- CSRF token from cookie on mutations
- Remove `customerApiFetch` and all customer-specific functions
- Unified endpoint paths (`/api/auth/*`, `/api/account/*`)

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5005";

function getCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? match[2] : "";
}

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  try {
    const resp = await fetch(`${API_URL}/api/auth/refresh/`, {
      method: "POST",
      credentials: "include",
    });
    return resp.ok;
  } catch {
    return false;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  _isRetry = false
): Promise<T> {
  const url = `${API_URL}${path}`;
  const method = (options.method || "GET").toUpperCase();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  // Add CSRF token for mutation requests
  if (method !== "GET" && method !== "HEAD") {
    const csrfToken = getCookie("csrftoken");
    if (csrfToken) {
      headers["X-CSRFToken"] = csrfToken;
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "include",
  });

  if (response.status === 401 && !_isRetry) {
    if (!isRefreshing) {
      isRefreshing = true;
      refreshPromise = tryRefresh().finally(() => {
        isRefreshing = false;
        refreshPromise = null;
      });
    }

    const refreshed = await refreshPromise;
    if (refreshed) {
      return apiFetch<T>(path, options, true);
    }

    // Refresh failed — clear auth state
    const { useAuthStore } = await import("@/stores/auth-store");
    useAuthStore.getState().clearAuth();
    throw new Error("Session expired. Please log in again.");
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      error.detail || error.email?.[0] || `API error: ${response.status}`
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// ── Imports ──
import type {
  PublicMenu,
  ParsedOrderResponse,
  ConfirmOrderItem,
  OrderResponse,
  CreatePaymentResponse,
  AuthResponse,
  User,
  OrderHistoryItem,
  OrderDetail,
  SavedPaymentMethod,
  Subscription,
} from "@/types";

// ── Auth ──
export async function register(data: {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  name?: string;
  phone?: string;
  link_order_id?: string;
}): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/api/auth/register/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function login(
  email: string,
  password: string
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function googleAuth(
  token: string,
  linkOrderId?: string
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/api/auth/google/", {
    method: "POST",
    body: JSON.stringify({ token, link_order_id: linkOrderId }),
  });
}

export async function appleAuth(
  token: string,
  name?: string,
  linkOrderId?: string
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/api/auth/apple/", {
    method: "POST",
    body: JSON.stringify({ token, name, link_order_id: linkOrderId }),
  });
}

export async function logout(): Promise<void> {
  await apiFetch("/api/auth/logout/", { method: "POST" });
}

export async function fetchMe(): Promise<User> {
  return apiFetch<User>("/api/auth/me/");
}

export async function updateProfile(data: Partial<User>): Promise<User> {
  return apiFetch<User>("/api/auth/me/", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function fetchCsrfToken(): Promise<void> {
  await apiFetch("/api/auth/csrf/");
}

// ── Account (orders, payment methods) ──
export async function fetchOrderHistory(): Promise<OrderHistoryItem[]> {
  return apiFetch<OrderHistoryItem[]>("/api/account/orders/");
}

export async function fetchOrderDetail(orderId: string): Promise<OrderDetail> {
  return apiFetch<OrderDetail>(`/api/account/orders/${orderId}/`);
}

export async function fetchPaymentMethods(): Promise<SavedPaymentMethod[]> {
  return apiFetch<SavedPaymentMethod[]>("/api/account/payment-methods/");
}

export async function deletePaymentMethod(pmId: string): Promise<void> {
  await apiFetch<void>(`/api/account/payment-methods/${pmId}/`, {
    method: "DELETE",
  });
}

// ── Public Order Flow (unchanged paths) ──
export async function fetchMenu(slug: string): Promise<PublicMenu> {
  return apiFetch<PublicMenu>(`/api/order/${slug}/menu/`);
}

export async function parseOrder(
  slug: string,
  rawInput: string
): Promise<ParsedOrderResponse> {
  return apiFetch<ParsedOrderResponse>(`/api/order/${slug}/parse/`, {
    method: "POST",
    body: JSON.stringify({ raw_input: rawInput }),
  });
}

export async function confirmOrder(
  slug: string,
  items: ConfirmOrderItem[],
  rawInput: string,
  tableIdentifier: string,
  language: string,
  customerName?: string,
  customerPhone?: string
): Promise<OrderResponse> {
  return apiFetch<OrderResponse>(`/api/order/${slug}/confirm/`, {
    method: "POST",
    body: JSON.stringify({
      items,
      raw_input: rawInput,
      table_identifier: tableIdentifier,
      language,
      customer_name: customerName || "",
      customer_phone: customerPhone || "",
    }),
  });
}

export async function createPayment(
  slug: string,
  items: ConfirmOrderItem[],
  rawInput: string,
  tableIdentifier: string,
  language: string,
  customerName?: string,
  customerPhone?: string,
  paymentMethodId?: string,
  saveCard?: boolean,
  allergies?: string[]
): Promise<CreatePaymentResponse> {
  return apiFetch<CreatePaymentResponse>(
    `/api/order/${slug}/create-payment/`,
    {
      method: "POST",
      body: JSON.stringify({
        items,
        raw_input: rawInput,
        table_identifier: tableIdentifier,
        language,
        customer_name: customerName || "",
        customer_phone: customerPhone || "",
        payment_method_id: paymentMethodId || "",
        save_card: saveCard || false,
        return_url: typeof window !== "undefined" ? window.location.href : "",
        allergies: allergies || [],
      }),
    }
  );
}

export async function fetchOrderStatus(
  slug: string,
  orderId: string
): Promise<OrderResponse> {
  return apiFetch<OrderResponse>(`/api/order/${slug}/status/${orderId}/`);
}

export async function confirmPayment(
  slug: string,
  orderId: string
): Promise<OrderResponse> {
  return apiFetch<OrderResponse>(
    `/api/order/${slug}/confirm-payment/${orderId}/`,
    { method: "POST" }
  );
}

export async function saveCardConsent(
  slug: string,
  orderId: string
): Promise<void> {
  await apiFetch(`/api/order/${slug}/save-card/${orderId}/`, {
    method: "PATCH",
  });
}

// ── Restaurant Admin ──
export async function fetchRestaurantOrders(
  slug: string
): Promise<OrderResponse[]> {
  return apiFetch<OrderResponse[]>(`/api/restaurants/${slug}/orders/`);
}

export async function fetchSubscription(slug: string): Promise<Subscription> {
  return apiFetch<Subscription>(`/api/restaurants/${slug}/subscription/`);
}

export async function createCheckoutSession(
  slug: string,
  plan: string,
  interval: "monthly" | "annual"
): Promise<{ checkout_url: string }> {
  return apiFetch<{ checkout_url: string }>(
    `/api/restaurants/${slug}/subscription/checkout/`,
    { method: "POST", body: JSON.stringify({ plan, interval }) }
  );
}

export async function createBillingPortal(
  slug: string
): Promise<{ portal_url: string }> {
  return apiFetch<{ portal_url: string }>(
    `/api/restaurants/${slug}/subscription/portal/`,
    { method: "POST" }
  );
}

export async function cancelSubscription(
  slug: string
): Promise<Subscription> {
  return apiFetch<Subscription>(
    `/api/restaurants/${slug}/subscription/cancel/`,
    { method: "POST" }
  );
}

export async function reactivateSubscription(
  slug: string
): Promise<Subscription> {
  return apiFetch<Subscription>(
    `/api/restaurants/${slug}/subscription/reactivate/`,
    { method: "POST" }
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "refactor(api): single cookie-based apiFetch, remove customerApiFetch"
```

### Task 12: Rewrite auth store

**Files:**
- Modify: `frontend/src/stores/auth-store.ts`
- Delete: `frontend/src/stores/customer-auth-store.ts`

- [ ] **Step 1: Rewrite `auth-store.ts`**

```typescript
import { create } from "zustand";
import type { User, AuthResponse } from "@/types";

interface AuthState {
  isAuthenticated: boolean | null; // null = unknown, true/false = resolved
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
    name?: string;
    phone?: string;
    link_order_id?: string;
  }) => Promise<void>;
  googleLogin: (token: string, linkOrderId?: string) => Promise<void>;
  appleLogin: (token: string, name?: string, linkOrderId?: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<boolean>;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: null,
  user: null,

  login: async (email, password) => {
    const { login } = await import("@/lib/api");
    const data = await login(email, password);
    set({ isAuthenticated: true, user: data.user });
  },

  register: async (formData) => {
    const { register } = await import("@/lib/api");
    const data = await register(formData);
    set({ isAuthenticated: true, user: data.user });
  },

  googleLogin: async (token, linkOrderId) => {
    const { googleAuth } = await import("@/lib/api");
    const data = await googleAuth(token, linkOrderId);
    set({ isAuthenticated: true, user: data.user });
  },

  appleLogin: async (token, name, linkOrderId) => {
    const { appleAuth } = await import("@/lib/api");
    const data = await appleAuth(token, name, linkOrderId);
    set({ isAuthenticated: true, user: data.user });
  },

  logout: async () => {
    const { logout } = await import("@/lib/api");
    await logout().catch(() => {});
    set({ isAuthenticated: false, user: null });
  },

  checkAuth: async () => {
    try {
      const { fetchMe } = await import("@/lib/api");
      const user = await fetchMe();
      set({ isAuthenticated: true, user });
      return true;
    } catch {
      set({ isAuthenticated: false, user: null });
      return false;
    }
  },

  clearAuth: () => {
    set({ isAuthenticated: false, user: null });
  },
}));
```

- [ ] **Step 2: Delete `customer-auth-store.ts`**

```bash
rm frontend/src/stores/customer-auth-store.ts
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/stores/auth-store.ts
git rm frontend/src/stores/customer-auth-store.ts
git commit -m "refactor(stores): unified auth store, delete customer-auth-store"
```

### Task 13: Auth hooks

**Files:**
- Create: `frontend/src/hooks/use-auth.ts`

- [ ] **Step 1: Create auth hooks**

```typescript
// frontend/src/hooks/use-auth.ts
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";

export function useRequireAuth() {
  const { isAuthenticated, checkAuth } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated === null) {
      checkAuth().then((ok) => {
        if (!ok) router.push("/account/login");
      });
    } else if (isAuthenticated === false) {
      router.push("/account/login");
    }
  }, [isAuthenticated, checkAuth, router]);

  return isAuthenticated;
}

export function useRequireRestaurantAccess() {
  const auth = useRequireAuth();
  const { user } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (auth === true && user && !user.is_restaurant_owner) {
      router.push("/account/profile");
    }
  }, [auth, user, router]);

  return auth;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/use-auth.ts
git commit -m "feat(hooks): add useRequireAuth and useRequireRestaurantAccess"
```

---

## Chunk 3: Frontend — Routes and Components

### Task 14: Unified Header

**Files:**
- Modify: `frontend/src/components/Header.tsx`
- Modify: `frontend/src/components/ConditionalHeader.tsx`
- Delete: `frontend/src/components/CustomerHeader.tsx`

- [ ] **Step 1: Rewrite `Header.tsx`** as unified header

Combines admin `Header` and `CustomerHeader` into one. Shows:
- Logo, Orders, Profile always
- "My Restaurants" if `user.is_restaurant_owner`
- Restaurant sub-nav when on `/account/restaurants/[slug]/*`

```typescript
// Use useAuthStore instead of separate stores
// Replace /admin links with /account/restaurants
// Add Orders, Profile, Payment Methods links
// Conditionally show "My Restaurants" based on user.is_restaurant_owner
```

Key changes from current `Header.tsx`:
- Import `useAuthStore` (already does)
- Add customer nav items (Orders, Profile, Payment Methods)
- Change `/admin` → `/account/restaurants`
- Change `/admin/login` → `/account/login`

- [ ] **Step 2: Simplify `ConditionalHeader.tsx`**

```typescript
"use client";

import { usePathname } from "next/navigation";
import { Header } from "@/components/Header";

export function ConditionalHeader() {
  const pathname = usePathname();

  // No header on ordering flow or kitchen display
  if (pathname.startsWith("/order/") || pathname.startsWith("/kitchen/")) {
    return null;
  }

  return <Header />;
}
```

- [ ] **Step 3: Delete `CustomerHeader.tsx`**

```bash
rm frontend/src/components/CustomerHeader.tsx
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Header.tsx frontend/src/components/ConditionalHeader.tsx
git rm frontend/src/components/CustomerHeader.tsx
git commit -m "refactor(components): unified Header, remove CustomerHeader"
```

### Task 15: Update login/register pages

**Files:**
- Modify: `frontend/src/app/account/login/page.tsx`
- Modify: `frontend/src/app/account/register/page.tsx`
- Modify: `frontend/src/components/SocialLoginButtons.tsx`

- [ ] **Step 1: Update `SocialLoginButtons.tsx`**

Change from `useCustomerAuthStore` to `useAuthStore`:

```typescript
import { useAuthStore } from "@/stores/auth-store";
// ...
const { googleLogin, appleLogin } = useAuthStore();
```

- [ ] **Step 2: Update `account/login/page.tsx`**

Change from `useCustomerAuthStore` to `useAuthStore`:

```typescript
import { useAuthStore } from "@/stores/auth-store";
// ...
const { login, isAuthenticated } = useAuthStore();
```

Redirect to `/account/profile` (or wherever makes sense) after login.

- [ ] **Step 3: Update `account/register/page.tsx`**

Change from `useCustomerAuthStore` to `useAuthStore`. Add first_name/last_name fields (or keep single name field with backend splitting).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/account/login/ frontend/src/app/account/register/ frontend/src/components/SocialLoginButtons.tsx
git commit -m "refactor(auth pages): use unified auth store with social auth"
```

### Task 15b: Update order flow components (imports `customer-auth-store`)

**Files:**
- Modify: `frontend/src/app/order/[slug]/page.tsx`
- Modify: `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`
- Modify: `frontend/src/app/order/[slug]/components/PaymentStep.tsx`
- Modify: `frontend/src/app/order/[slug]/components/SubmittedStep.tsx`

These files import `useCustomerAuthStore` which is now deleted. **Must be done before Task 12 deletes `customer-auth-store.ts`**, or done as part of the same commit.

- [ ] **Step 1: Update all four files**

In each file:
- Replace `import { useCustomerAuthStore } from "@/stores/customer-auth-store"` → `import { useAuthStore } from "@/stores/auth-store"`
- Replace `useCustomerAuthStore()` → `useAuthStore()`
- Replace `customer` property references → `user` (e.g., `customer?.name` → `user?.name`)
- In `ConfirmationStep.tsx`: replace `useCustomerProfile` → `useProfile` (see Task 15c)

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/order/
git commit -m "refactor(order flow): use unified auth store"
```

### Task 15c: Rename customer hooks to unified hooks

**Files:**
- Rename: `frontend/src/hooks/use-customer-profile.ts` → `frontend/src/hooks/use-profile.ts`
- Rename: `frontend/src/hooks/use-customer-orders.ts` → `frontend/src/hooks/use-orders.ts`

- [ ] **Step 1: Create `use-profile.ts`**

```typescript
// frontend/src/hooks/use-profile.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchMe, updateProfile } from "@/lib/api";

export function useProfile() {
  return useQuery({
    queryKey: ["profile"],
    queryFn: fetchMe,
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}
```

- [ ] **Step 2: Create `use-orders.ts`**

```typescript
// frontend/src/hooks/use-orders.ts
import { useQuery } from "@tanstack/react-query";
import { fetchOrderHistory, fetchOrderDetail } from "@/lib/api";

export function useOrderHistory() {
  return useQuery({
    queryKey: ["orderHistory"],
    queryFn: fetchOrderHistory,
  });
}

export function useOrderDetail(orderId: string) {
  return useQuery({
    queryKey: ["orderDetail", orderId],
    queryFn: () => fetchOrderDetail(orderId),
    enabled: !!orderId,
  });
}
```

- [ ] **Step 3: Delete old hook files**

```bash
rm frontend/src/hooks/use-customer-profile.ts
rm frontend/src/hooks/use-customer-orders.ts
```

- [ ] **Step 4: Update all imports of old hooks across the codebase**

Search for `use-customer-profile` and `use-customer-orders` and update to `use-profile` and `use-orders`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/
git commit -m "refactor(hooks): rename customer hooks to unified profile/orders hooks"
```

### Task 15d: Update landing page and ThemeProvider

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/components/ThemeProvider.tsx`

- [ ] **Step 1: Update landing page**

Replace all `/admin/register` links with `/account/register` in `frontend/src/app/page.tsx`.

- [ ] **Step 2: Update ThemeProvider**

In `frontend/src/components/ThemeProvider.tsx`, replace `pathname.startsWith("/admin")` with `pathname.startsWith("/account/restaurants")`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/page.tsx frontend/src/components/ThemeProvider.tsx
git commit -m "refactor: update /admin references in landing page and ThemeProvider"
```

### Task 16: Move admin pages to `/account/restaurants/*`

**Files:**
- Create: `frontend/src/app/account/restaurants/page.tsx` (from `admin/page.tsx`)
- Create: `frontend/src/app/account/restaurants/[slug]/menu/page.tsx`
- Create: `frontend/src/app/account/restaurants/[slug]/orders/page.tsx`
- Create: `frontend/src/app/account/restaurants/[slug]/billing/page.tsx`
- Create: `frontend/src/app/account/restaurants/[slug]/settings/page.tsx`
- Delete: `frontend/src/app/admin/` (entire directory)

- [ ] **Step 1: Copy admin pages to new location**

```bash
mkdir -p frontend/src/app/account/restaurants/\[slug\]
cp frontend/src/app/admin/page.tsx frontend/src/app/account/restaurants/page.tsx
cp -r frontend/src/app/admin/\[slug\]/menu frontend/src/app/account/restaurants/\[slug\]/menu
cp -r frontend/src/app/admin/\[slug\]/orders frontend/src/app/account/restaurants/\[slug\]/orders
cp -r frontend/src/app/admin/\[slug\]/billing frontend/src/app/account/restaurants/\[slug\]/billing
cp -r frontend/src/app/admin/\[slug\]/settings frontend/src/app/account/restaurants/\[slug\]/settings
```

- [ ] **Step 2: Update imports in each copied page**

In each page:
- Replace `useAuthStore` references (already correct, just ensure unified store)
- Replace `useRequireAuth` patterns with the hook from `@/hooks/use-auth`
- Replace `/admin` links with `/account/restaurants`
- Handle tri-state `isAuthenticated` (show loading while `null`)

- [ ] **Step 3: Delete admin directory**

```bash
rm -rf frontend/src/app/admin/
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/account/restaurants/
git rm -rf frontend/src/app/admin/
git commit -m "refactor(routes): move admin pages to /account/restaurants, delete /admin"
```

### Task 17: Update remaining account pages

**Files:**
- Modify: `frontend/src/app/account/profile/page.tsx`
- Modify: `frontend/src/app/account/orders/page.tsx`
- Modify: `frontend/src/app/account/orders/[orderId]/page.tsx`
- Modify: `frontend/src/app/account/payment-methods/page.tsx`

- [ ] **Step 1: Update profile page**

- Replace `useCustomerAuthStore` → `useAuthStore`
- Replace `useCustomerProfile` hook → `useProfile` from `@/hooks/use-profile`
- Replace `useUpdateProfile` mutation → from `@/hooks/use-profile`
- Use `useRequireAuth()` hook
- **Split the single "Name" form field into "First Name" and "Last Name"** — the backend's `UserProfileSerializer` does not accept a writable `name` field. The form must send `{ first_name, last_name }` instead of `{ name }`.

- [ ] **Step 2: Update orders page**

- Replace `useCustomerAuthStore` → `useAuthStore`
- Replace `fetchCustomerOrders` → `fetchOrderHistory`
- Use `useRequireAuth()` hook

- [ ] **Step 3: Update order detail page**

- Replace `useCustomerAuthStore` → `useAuthStore`
- Replace `fetchCustomerOrder` → `fetchOrderDetail`
- Use `useRequireAuth()` hook

- [ ] **Step 4: Update payment methods page**

- Replace `useCustomerAuthStore` → `useAuthStore`
- Use `useRequireAuth()` hook
- API functions (`fetchPaymentMethods`, `deletePaymentMethod`) already use the right names

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/account/
git commit -m "refactor(account pages): use unified auth store and api client"
```

### Task 18: Smoke test the full stack

- [ ] **Step 1: Start backend**

```bash
cd backend && python manage.py runserver 5005
```

- [ ] **Step 2: Start frontend**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Manual verification checklist**

1. Visit `http://localhost:3001/account/register` — register with email/password
2. Verify cookies are set (DevTools → Application → Cookies)
3. Visit `http://localhost:3001/account/profile` — should show user data
4. Visit `http://localhost:3001/account/restaurants` — should show empty state (no restaurants)
5. Logout → verify cookies are cleared
6. Login again → verify cookies set
7. Google Sign-In works from login page
8. Visiting old `/admin/*` routes returns 404

- [ ] **Step 4: Run all backend tests**

```bash
cd backend && python -m pytest -v
```

- [ ] **Step 5: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: No build errors

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: unified auth complete — single User model, cookie auth, consolidated routes"
```
