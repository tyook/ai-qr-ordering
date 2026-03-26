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
| `/api/auth/me/` | GET | Current user profile |

**Cookie-based auth flow:**

1. Login/register/OAuth endpoints generate JWT access + refresh tokens
2. Tokens are set as **httpOnly, Secure, SameSite=Lax** cookies:
   - `access_token` — short-lived (15 min)
   - `refresh_token` — long-lived (7 days)
3. Response body returns user data only (no tokens)
4. Django CSRF middleware is enabled; frontend sends `X-CSRFToken` header from `csrftoken` cookie
5. A `/api/auth/csrf/` endpoint provides the initial CSRF token via `ensure_csrf_cookie`

**Social auth** (`accounts/social_auth.py`): Moved from `customers/social_auth.py` unchanged. `verify_google_token()` and `verify_apple_token()` now create/find `accounts.User` instead of `Customer`.

**Order linking on signup**: The `link_order_id` parameter (currently on customer OAuth endpoints) is preserved. When a guest places an order then signs up, the order gets linked to their new `User`.

#### Authentication Backend

Custom DRF authentication class `CookieJWTAuthentication`:
- Reads `access_token` from httpOnly cookie (not Authorization header)
- Validates JWT, returns User
- Falls back to checking Authorization header for API clients/testing

#### Profile & Orders Views

Customer-specific views move to `accounts`:

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/me/` | GET, PATCH | View/update profile (dietary prefs, allergies, language, phone) |
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
  isAuthenticated: boolean;
  user: User | null;
  login(email: string, password: string): Promise<void>;
  register(data: RegisterData): Promise<void>;
  googleLogin(token: string, linkOrderId?: string): Promise<void>;
  appleLogin(token: string, name?: string, linkOrderId?: string): Promise<void>;
  logout(): Promise<void>;
  checkAuth(): Promise<boolean>;
}
```

No tokens in localStorage. Cookies are sent automatically by the browser.

### API Client (`src/lib/api.ts`)

Single `apiFetch()` function replaces both `apiFetch()` and `customerApiFetch()`:

```typescript
async function apiFetch(path: string, options?: RequestInit) {
  const csrfToken = getCookie("csrftoken");
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",  // sends cookies
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
      ...options?.headers,
    },
  });

  if (res.status === 401) {
    // Try refreshing
    const refreshRes = await fetch(`${API_URL}/api/auth/refresh/`, {
      method: "POST",
      credentials: "include",
    });
    if (refreshRes.ok) {
      return apiFetch(path, options);  // retry
    }
    // Refresh failed — clear state, redirect to login
    useAuthStore.getState().clearAuth();
  }

  return res;
}
```

`customer-auth-store.ts` is deleted. All customer-specific API functions (`customerRegister`, `customerLogin`, `customerGoogleAuth`, etc.) are merged into the unified API module.

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
    if (!checkAuth()) router.push("/account/login");
  }, []);
  return isAuthenticated;
}
```

Restaurant management pages add an additional check:

```typescript
function useRequireRestaurantAccess() {
  const auth = useRequireAuth();
  const { user } = useAuthStore();
  const router = useRouter();
  useEffect(() => {
    if (auth && !user?.is_restaurant_owner) router.push("/account/restaurants");
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
