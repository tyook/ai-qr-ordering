# Unified Auth: Single Identity with httpOnly Cookies

## Problem

The app has two separate auth systems: `User` (restaurant owners, Django AbstractUser) and `Customer` (diners, custom model). They have separate login pages, separate token stores, and separate API clients. The `/admin/register` page doesn't support social auth. A logged-in customer sees a fresh login screen when navigating to `/admin/*`. This is confusing and redundant.

## Solution

Merge into a single `User` model in a new `accounts` Django app. Everyone authenticates through one flow. Restaurant involvement is derived from `RestaurantStaff`/`Restaurant.owner` relationships, not a role field. Auth tokens are delivered via httpOnly cookies instead of localStorage.

---

## Backend

### New `accounts` App

Replaces auth concerns from both `restaurants` and `customers` apps.

#### User Model (`accounts/models.py`)

The unified `User` extends `AbstractUser`:

```python
class User(AbstractUser):
    id = UUIDField(primary_key=True, default=uuid4)
    email = EmailField(unique=True)
    # Django's first_name, last_name inherited from AbstractUser
    phone = CharField(max_length=20, blank=True, default="")
    stripe_customer_id = CharField(max_length=255, blank=True, null=True, unique=True)

    # Migrated from Customer
    auth_provider = CharField(choices=AuthProvider.choices, default="email")
    auth_provider_id = CharField(max_length=255, blank=True, default="")
    dietary_preferences = JSONField(default=list, blank=True)
    allergies = JSONField(default=list, blank=True)
    preferred_language = CharField(max_length=10, blank=True, default="en-US")

    username = None
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class AuthProvider(TextChoices):
        EMAIL = "email"
        GOOGLE = "google"
        APPLE = "apple"

    @property
    def is_restaurant_owner(self):
        """True if user owns or staffs any restaurant."""
        return (
            self.owned_restaurants.exists()
            or self.staff_roles.exists()
        )

    @property
    def name(self):
        """Backwards-compatible name property for templates/serializers."""
        return f"{self.first_name} {self.last_name}".strip()
```

**Dropped from User:** `role` field. Restaurant roles are derived from `RestaurantStaff` and `Restaurant.owner` FKs.

**Dropped entirely:** `Customer` model and `customers` app.

#### Auth Views (`accounts/views.py`)

All auth endpoints consolidate under `/api/auth/`:

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/register/` | POST | Email/password registration |
| `/api/auth/login/` | POST | Email/password login |
| `/api/auth/google/` | POST | Google OAuth login/register |
| `/api/auth/apple/` | POST | Apple OAuth login/register |
| `/api/auth/refresh/` | POST | Refresh access token |
| `/api/auth/logout/` | POST | Clear auth cookies |
| `/api/auth/me/` | GET, PATCH | View/update profile (dietary prefs, allergies, language, phone) |
| `/api/auth/csrf/` | GET | Provide initial CSRF token via `@ensure_csrf_cookie` |

**Cookie-based auth flow:**

1. Login/register/OAuth endpoints generate JWT access + refresh tokens using standard simplejwt `AccessToken`/`RefreshToken` (single User model, no custom token classes needed — delete `CustomerAccessToken`/`CustomerRefreshToken`)
2. Tokens are set as **httpOnly, SameSite=Lax** cookies. The `Secure` flag is conditional on environment (`AUTH_COOKIE_SECURE = not DEBUG`) so cookies work over `http://localhost` in development:
   - `access_token` — short-lived (15 min), `Path=/`
   - `refresh_token` — long-lived (7 days), `Path=/api/auth/refresh/` (scoped to reduce attack surface)
3. Response body returns user data only (no tokens)
4. Django CSRF middleware is enabled; frontend sends `X-CSRFToken` header from `csrftoken` cookie
5. `/api/auth/csrf/` endpoint provides the initial CSRF token via `ensure_csrf_cookie`
6. **CSRF exemptions:** `/api/auth/login/`, `/api/auth/register/`, `/api/auth/google/`, `/api/auth/apple/`, and `/api/auth/refresh/` are CSRF-exempt (they either require credentials the attacker doesn't have or are idempotent token operations). Only authenticated mutation endpoints require CSRF.

**Name handling:** The current `Customer` model has a single `name` field; the unified `User` has `first_name` + `last_name`. Strategy:
- Registration API accepts an optional `name` field. If provided (instead of `first_name`/`last_name`), split on first space: first token = `first_name`, remainder = `last_name` (defaults to `""` if single word).
- Social auth providers (Google, Apple) return a single `name` string — same splitting logic applies.
- The `User.name` property concatenates them back for display.

**Social auth** (`accounts/social_auth.py`): Moved from `customers/social_auth.py`. `verify_google_token()` and `verify_apple_token()` now create/find `accounts.User` instead of `Customer`. Password handling uses Django's built-in `User.set_password()` / `check_password()` (no more manual hashing on the Customer model).

**Stripe:** The `get_or_create_stripe_customer()` method moves from `Customer` to `User`. The unified `User.stripe_customer_id` serves both diner payments and restaurant subscription billing. Note: `Subscription.stripe_customer_id` remains as a separate field — it tracks the Stripe customer for the restaurant entity (which may differ from the owner's personal Stripe customer).

**Order linking on signup**: The `link_order_id` parameter (currently on customer OAuth endpoints) is preserved. When a guest places an order then signs up, the order gets linked to their new `User`.

#### Authentication Backend

Custom DRF authentication class `CookieJWTAuthentication`:
- Reads `access_token` from httpOnly cookie (not Authorization header)
- Validates JWT using standard simplejwt validation (`AccessToken` class)
- Falls back to checking Authorization header for API clients/testing

#### Account Views

Customer-facing views move to `accounts`:

| Endpoint | Method | Description |
|---|---|---|
| `/api/account/orders/` | GET | Order history for current user |
| `/api/account/orders/<id>/` | GET | Order detail |
| `/api/account/payment-methods/` | GET | List saved payment methods |
| `/api/account/payment-methods/<id>/` | DELETE | Delete payment method |

### Changes to `restaurants` App

- `User` model moves out to `accounts`. Update `AUTH_USER_MODEL = "accounts.User"`.
- `UserManager` moves to `accounts/managers.py`.
- Remove `RegisterView`, `LoginView`, token refresh from `restaurants/views.py` and `restaurants/urls.py`.
- `Restaurant.owner` FK now points to `accounts.User` (same table, different app label).
- `RestaurantStaff.user` FK points to `accounts.User`.
- Restaurant management views (`RestaurantMixin`, menu CRUD, orders, subscriptions) stay in `restaurants` app.
- `RestaurantMixin` auth check: instead of checking `request.user` via DRF's `IsAuthenticated`, it uses the new `CookieJWTAuthentication`.

### Changes to `orders` App

- `Order.customer` FK changes from `customers.Customer` to `accounts.User` (field renamed to `user`).
- `customer_name` and `customer_phone` fields on `Order` stay as-is — they describe the customer role in that order context, not the model name.
- Order creation (guest or authenticated) updates accordingly.

### Migration Strategy

Since the app is not deployed, we can do a clean migration:

1. Create `accounts` app with unified `User` model
2. Update `AUTH_USER_MODEL` to `accounts.User`
3. Delete `customers` app
4. Update all FKs (`Restaurant.owner`, `RestaurantStaff.user`, `Order.customer`) to point to `accounts.User`
5. Reset migrations (no production data to preserve): `flush` + fresh `makemigrations` + `migrate`

### Django Settings Changes

```python
AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = [
    ...
    "accounts",
    "restaurants",
    "orders",
    # "customers" removed
]

# Cookie settings
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Frontend needs to read CSRF token
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
AUTH_COOKIE_SECURE = not DEBUG  # False in dev (http://localhost), True in prod

# For local dev with separate frontend/backend ports
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = ["http://localhost:3001"]

# JWT (shorter access token for cookie-based flow)
ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)
REFRESH_TOKEN_LIFETIME = timedelta(days=7)
```

---

## Frontend

### Route Structure

```
/account/login                              — email + Google/Apple sign-in
/account/register                           — email + Google/Apple sign-up
/account/profile                            — personal settings, dietary prefs
/account/orders                             — order history as customer
/account/orders/[orderId]                   — order detail
/account/payment-methods                    — saved cards
/account/restaurants                        — list owned/staffed restaurants
/account/restaurants/[slug]/menu            — menu management
/account/restaurants/[slug]/orders          — restaurant order history
/account/restaurants/[slug]/billing         — subscription/billing
/account/restaurants/[slug]/settings        — restaurant settings

/order/[slug]/[tableId]                     — public ordering flow (unchanged)
/kitchen/[slug]                             — kitchen display (unchanged)
/                                           — landing page (unchanged)
```

`/admin/*` routes are deleted entirely.

### Auth Store (`src/stores/auth-store.ts`)

Single Zustand store replaces both `auth-store.ts` and `customer-auth-store.ts`:

```typescript
interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  name: string;
  phone: string;
  dietary_preferences: string[];
  allergies: string[];
  preferred_language: string;
  is_restaurant_owner: boolean;
}

interface AuthState {
  isAuthenticated: boolean | null;  // null = unknown (checking), true/false = resolved
  user: User | null;
  login(email: string, password: string): Promise<void>;
  register(data: RegisterData): Promise<void>;
  googleLogin(token: string, linkOrderId?: string): Promise<void>;
  appleLogin(token: string, name?: string, linkOrderId?: string): Promise<void>;
  logout(): Promise<void>;
  checkAuth(): Promise<boolean>;  // calls /api/auth/me/, sets isAuthenticated
  clearAuth(): void;
}
```

No tokens in localStorage. Cookies are sent automatically by the browser.

**Auth initialization:** Since httpOnly cookies are not readable by JS, auth state on page load starts as `isAuthenticated: null` (unknown). The app calls `checkAuth()` (hits `/api/auth/me/`) on mount to resolve to `true` or `false`. Protected pages show a loading state while `isAuthenticated === null`.

### API Client (`src/lib/api.ts`)

Single `apiFetch()` function replaces both `apiFetch()` and `customerApiFetch()`. The implementation should follow the existing error-handling patterns (concurrent refresh deduplication via `isRefreshing`/`refreshPromise`, typed return values). Key changes from the current implementation:

- `credentials: "include"` on all requests (sends cookies cross-origin)
- `X-CSRFToken` header read from the `csrftoken` cookie on mutation requests
- No `Authorization` header (tokens are in cookies)
- Refresh calls `POST /api/auth/refresh/` with `credentials: "include"` (no CSRF needed — endpoint is CSRF-exempt)

`customer-auth-store.ts` is deleted. `customerApiFetch()` is deleted. All customer-specific API functions (`customerRegister`, `customerLogin`, `customerGoogleAuth`, etc.) are merged into the unified API module.

### Header / Navigation

Single `Header` component that adapts based on context:
- Always shows: profile, orders, logout
- Conditionally shows: "My Restaurants" link if `user.is_restaurant_owner`
- On restaurant management pages: shows restaurant nav (menu, orders, billing, settings)

`ConditionalHeader` simplifies: returns null for `/order/*` and `/kitchen/*`, returns `Header` for everything else.

### Route Protection

Single pattern:

```typescript
function useRequireAuth() {
  const { isAuthenticated, checkAuth } = useAuthStore();
  const router = useRouter();
  useEffect(() => {
    checkAuth().then(ok => { if (!ok) router.push("/account/login"); });
  }, []);
  return isAuthenticated;  // null = loading, true = authed, false = redirecting
}
```

Protected pages render a loading spinner while `isAuthenticated === null`, then their content when `true`.

Restaurant management pages add an additional check:

```typescript
function useRequireRestaurantAccess() {
  const auth = useRequireAuth();
  const { user } = useAuthStore();
  const router = useRouter();
  useEffect(() => {
    if (auth === true && !user?.is_restaurant_owner) router.push("/account/profile");
  }, [auth, user]);
}
```

---

## What Stays Unchanged

- `Restaurant`, `Subscription`, `RestaurantStaff`, `MenuCategory`, `MenuItem`, `MenuItemVariant`, `MenuItemModifier` models (stay in `restaurants` app, FKs updated)
- Order creation flow at `/order/[slug]/[tableId]` (guest ordering still works without auth)
- Kitchen display at `/kitchen/[slug]`
- Stripe payment/subscription logic
- WebSocket channels for real-time order updates
- LLM order parsing

## Testing

- Unit tests for `CookieJWTAuthentication` (reads cookie, falls back to header)
- Unit tests for unified registration (email, Google, Apple)
- Unit tests for cookie setting (httpOnly, Secure flags, SameSite)
- Integration tests for CSRF flow (get token, include in mutation requests)
- Integration tests for order linking on OAuth signup
- Frontend: test that `credentials: "include"` is set on all fetch calls
- Frontend: test CSRF token extraction and header inclusion
