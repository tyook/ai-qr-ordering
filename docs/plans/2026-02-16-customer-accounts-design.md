# Customer Accounts & Dashboard Design

## Overview

Add customer accounts to the QR ordering system. Customers can place orders anonymously (as today) and optionally create accounts to save preferences, view order history, and persist dietary/allergy information.

Customer accounts are completely separate from restaurant owner/staff accounts. Different models, different auth, different UI.

## Customer Model

New `customers` Django app with a `Customer` model, independent of the existing `User` model.

### `Customer` fields

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `email` | EmailField | Unique, required |
| `password` | CharField | Hashed, nullable (social login users) |
| `name` | CharField | Required |
| `phone` | CharField | Optional |
| `auth_provider` | CharField | `email`, `google`, or `apple` |
| `auth_provider_id` | CharField | External ID from Google/Apple, nullable |
| `dietary_preferences` | JSONField | e.g. `["vegetarian", "gluten-free"]` |
| `allergies` | JSONField | e.g. `["peanuts", "shellfish"]` |
| `preferred_language` | CharField | Default speech input language |
| `created_at` | DateTimeField | Auto |
| `updated_at` | DateTimeField | Auto |

### Order model changes

| Field | Change |
|---|---|
| `Order.customer` | New nullable ForeignKey to `Customer` |
| `Order.customer_name` | New CharField, required at submission |
| `Order.customer_phone` | New CharField, optional |

Existing orders remain unlinked (`customer=null`).

## Authentication

### Customer auth endpoints (`/api/customer/auth/`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/register/` | POST | Email + password sign-up |
| `/login/` | POST | Email + password login |
| `/google/` | POST | Google OAuth token exchange |
| `/apple/` | POST | Apple Sign-In token exchange |
| `/refresh/` | POST | Refresh JWT |

### Token separation

Both customer and owner auth use `djangorestframework-simplejwt`, but tokens include a `token_type` claim:

- Customer tokens: `{"token_type": "customer", ...}` — only valid for `/api/customer/*`
- Owner tokens: `{"token_type": "owner", ...}` — only valid for `/api/restaurants/*`, `/api/kitchen/*`

A custom permission class checks the token type on each request.

### Login methods

- **Email + password** — standard registration and login
- **Google OAuth** — exchange Google ID token for customer JWT
- **Apple Sign-In** — exchange Apple identity token for customer JWT

Social login creates a `Customer` record on first use (auto-register).

## Order Flow Changes

### Current flow (unchanged for guests)

```
Scan QR -> Voice/text input -> LLM parses -> Review -> Submit -> "Order submitted!"
```

### What changes

**1. Name + phone on confirmation step.**

Before submitting, the customer enters their name (required) and phone (optional). This serves the restaurant regardless of account creation — they need to know who the order is for. If the customer is logged in, these fields auto-fill from their profile.

**2. Post-submit account prompt.**

After the order is submitted, the Submitted step shows:

```
Order #42 submitted!
Your order is being prepared.

+---------------------------------+
|  Save your info for next time?  |
|                                 |
|  [Continue with Google]         |
|  [Continue with Apple]          |
|  [Sign up with email]           |
|                                 |
|  Skip                           |
+---------------------------------+
```

**3. Order linking.**

When the customer creates an account from this prompt, the backend links the just-placed order to the new `Customer` record. The frontend sends the `order_id` along with the registration request.

**4. Returning customers.**

If a customer is already signed in when they scan a QR code:
- The order is automatically linked to their account
- Name and phone auto-fill on the confirmation step
- Dietary preferences and allergies are passed as context to the LLM parser

**Key rule:** signing in is never required to place an order.

## Customer Dashboard

### Routes

| Route | Purpose |
|---|---|
| `/account/login` | Customer login (email/password, Google, Apple) |
| `/account/register` | Customer registration |
| `/account/orders` | Past order history |
| `/account/profile` | Edit name, phone, dietary prefs, allergies |

### Order history (`/account/orders`)

- Lists all past orders, newest first
- Each order shows: restaurant name, date, items, total, status
- Tap an order to see full details (items, modifiers, variants, prices)
- No reorder functionality for now

### Profile (`/account/profile`)

- Edit name, phone number
- Dietary preferences — multi-select from predefined list (vegetarian, vegan, halal, kosher, gluten-free, etc.) with custom entries
- Allergies — same pattern, predefined list + custom
- Preferred language for voice input
- Preferences are passed as context to the LLM when parsing orders, so it can flag conflicts (e.g., "You mentioned peanut sauce but you have a peanut allergy")

### Navigation

Simple top nav with "Orders" and "Profile" links. Not an admin panel — keep it lightweight.

## Preferences Behavior

The existing `PreferencesDialog` component (language + allergy note) is reassigned to customer context only.

| Context | Preferences visible? | Storage |
|---|---|---|
| Customer on `/order/*` (guest) | Yes — gear icon in order header | localStorage only |
| Customer on `/account/*` (logged in) | Yes — same dialog | localStorage + synced to `Customer` profile on backend |
| Restaurant owner on `/admin/*` | No — removed from admin dropdown | N/A |
| Kitchen staff on `/kitchen/*` | No | N/A |

The `PreferencesDialog` component stays as-is. It's used in the customer-facing header instead of the admin header.

## Full Route Map

### Frontend

```
/                                    Landing page

# Customer ordering (no auth required)
/order/[slug]/                       Order flow
/order/[slug]/[tableId]/             Order flow with table ID

# Customer account (auth required)
/account/login                       Customer login
/account/register                    Customer registration
/account/orders                      Order history
/account/profile                     Profile & preferences

# Restaurant owner/staff (auth required)
/admin/login                         Owner login
/admin/register                      Owner registration
/admin/                              Restaurant list
/admin/[slug]/menu                   Menu management
/admin/[slug]/orders                 Order history (restaurant side)
/admin/[slug]/settings               Settings + QR codes
/admin/[slug]/dashboard              Performance metrics (future)

# Kitchen (auth required)
/kitchen/[slug]/                     Real-time kitchen display
```

### Backend API

```
# Customer auth
/api/customer/auth/register/         POST  - Sign up
/api/customer/auth/login/            POST  - Login
/api/customer/auth/google/           POST  - Google OAuth
/api/customer/auth/apple/            POST  - Apple Sign-In
/api/customer/auth/refresh/          POST  - Refresh token

# Customer account
/api/customer/profile/               GET/PATCH  - View/update profile
/api/customer/orders/                GET        - Order history

# Public ordering (unchanged)
/api/order/:slug/menu/               GET   - Public menu
/api/order/:slug/parse/              POST  - Parse order via LLM
/api/order/:slug/confirm/            POST  - Confirm order (now accepts customer_name, customer_phone)

# Restaurant admin (unchanged)
/api/restaurants/...                  (existing endpoints)

# Kitchen (unchanged)
/api/kitchen/...                      (existing endpoints)
```

### Backend apps

| App | Purpose |
|---|---|
| `restaurants` | Restaurant, menu, owner/staff `User` model, owner auth |
| `orders` | Order, LLM parsing, kitchen WebSocket |
| `customers` (new) | `Customer` model, customer auth, profile, order history |

## Login Screens

Two completely separate login experiences, accessed from different entry points:

| | Customer login | Owner login |
|---|---|---|
| URL | `/account/login` | `/admin/login` |
| Entry point | "Sign in" from order page, or "Create account" after placing order | Navigate to `/admin` |
| Options | Email + password, Google, Apple | Email + password |
| After login | Back to ordering / order history | Admin dashboard |

A customer never sees the admin login. An owner never sees the customer login.
