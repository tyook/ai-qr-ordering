# AI QR Code Ordering System - MVP Design

## Overview

An AI-powered QR code ordering system for restaurants. Customers scan a QR code at their table (or at the counter), type or speak their order in any language, and an LLM parses it into structured menu items. The customer confirms, the order goes to a real-time kitchen dashboard, and food gets made.

**MVP scope:**
- Customer ordering via text and voice input
- LLM-powered natural language order parsing (any language)
- Order confirmation flow with editing
- Real-time kitchen dashboard via WebSocket
- Restaurant admin panel with menu management and QR code generation
- No payments (pay at counter for MVP)
- No POS integration (Phase 2)

---

## Architecture

### Monorepo Structure

```
ai-qr-ordering/
├── frontend/          # Next.js 14 (App Router) PWA
├── backend/           # Django 4.2 + Django Channels
├── docker-compose.yml # Local dev: Postgres, Redis, both apps
└── README.md
```

### System Diagram

```
[Customer Phone / Browser]
        |
        v
[Next.js Frontend PWA]
   ├── /order/:slug/:tableId?    ── REST ──> [Django API] ──> [LLM Provider]
   ├── /kitchen/:slug             ── WS ───> [Django Channels]
   └── /admin/:slug/*             ── REST ──> [Django API]
                                                  |
                                              [PostgreSQL]
                                              [Redis] (channel layer + cache)
```

### Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend | Next.js 14, TypeScript, Tailwind, shadcn/ui | Customer PWA, kitchen dashboard, admin panel |
| Backend API | Django 4.2, DRF | REST API, LLM orchestration, auth |
| WebSocket | Django Channels + Redis | Real-time kitchen order feed |
| LLM Layer | Abstraction with OpenAI default | Parse natural language orders into structured JSON |
| Database | PostgreSQL 16 | Menus, orders, users, restaurants |
| Cache/Broker | Redis 7 | Channel layer, caching, future Celery broker |

---

## Data Model

### User (extends Django AbstractUser)

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| email | string (unique) | Used as login |
| first_name | string | |
| last_name | string | |
| role | enum | owner, staff, admin |
| phone | string (optional) | |

### Restaurant

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| name | string | |
| slug | string (unique) | Used in URLs |
| owner | FK -> User | |
| created_at | datetime | |

### RestaurantStaff

| Field | Type | Notes |
|-------|------|-------|
| id | auto | |
| user | FK -> User | |
| restaurant | FK -> Restaurant | |
| role | enum | owner, manager, kitchen |
| invited_at | datetime | |

### MenuCategory

| Field | Type | Notes |
|-------|------|-------|
| id | auto | |
| restaurant | FK -> Restaurant | |
| name | string | e.g. "Pizzas", "Drinks" |
| sort_order | integer | |
| is_active | boolean | |

### MenuItem

| Field | Type | Notes |
|-------|------|-------|
| id | auto | |
| category | FK -> MenuCategory | |
| name | string | e.g. "Pepperoni Pizza" |
| description | text | |
| image_url | string (optional) | |
| is_active | boolean | |
| sort_order | integer | |

### MenuItemVariant

| Field | Type | Notes |
|-------|------|-------|
| id | auto | |
| menu_item | FK -> MenuItem | |
| label | string | e.g. "Large", "Small", "Bottle" |
| price | decimal | |
| is_default | boolean | |

Variants represent required pick-one choices (sizes, formats).

### MenuItemModifier

| Field | Type | Notes |
|-------|------|-------|
| id | auto | |
| menu_item | FK -> MenuItem | |
| name | string | e.g. "Extra Cheese", "No Olives" |
| price_adjustment | decimal | Can be 0 for free modifiers |

Modifiers represent optional pick-many choices (add/remove toppings).

### Order

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| restaurant | FK -> Restaurant | |
| table_identifier | string (nullable) | Nullable for counter/pickup orders |
| status | enum | pending -> confirmed -> preparing -> ready -> completed |
| raw_input | text | Customer's original text (for prompt tuning) |
| parsed_json | JSON | LLM's structured output |
| language_detected | string | What language the customer used |
| total_price | decimal | Calculated server-side |
| created_at | datetime | |

### OrderItem

| Field | Type | Notes |
|-------|------|-------|
| id | auto | |
| order | FK -> Order | |
| menu_item | FK -> MenuItem | |
| variant | FK -> MenuItemVariant | |
| quantity | integer | |
| special_requests | text | |
| modifiers | M2M -> MenuItemModifier | |

---

## API Endpoints

### Auth
```
POST   /api/auth/register/          # Restaurant owner signup
POST   /api/auth/login/             # Login (returns JWT)
POST   /api/auth/refresh/           # Refresh JWT token
```

### Restaurant Management (authenticated - owner/manager)
```
GET    /api/restaurants/me/          # List my restaurants
POST   /api/restaurants/             # Create restaurant
PATCH  /api/restaurants/:slug/       # Update restaurant
```

### Menu Management (authenticated - owner/manager)
```
GET    /api/restaurants/:slug/menu/              # Full menu
POST   /api/restaurants/:slug/categories/        # Create category
PATCH  /api/restaurants/:slug/categories/:id/    # Update category
POST   /api/restaurants/:slug/items/             # Create menu item
PATCH  /api/restaurants/:slug/items/:id/         # Update item
DELETE /api/restaurants/:slug/items/:id/         # Deactivate item
```

### Customer Ordering (public - no auth required)
```
GET    /api/order/:slug/menu/        # Get menu for display
POST   /api/order/:slug/parse/       # Send raw text -> get parsed order
POST   /api/order/:slug/confirm/     # Confirm and place order
GET    /api/order/:slug/status/:id/  # Check order status
```

### Kitchen (authenticated - kitchen staff)
```
WS     /ws/kitchen/:slug/            # WebSocket for live orders
PATCH  /api/kitchen/orders/:id/      # Update order status
```

Key decisions:
- Customer endpoints are unauthenticated (no friction to order)
- JWT auth for restaurant owners/staff (djangorestframework-simplejwt)
- Two-step ordering: `parse` returns the LLM interpretation for confirmation, `confirm` places the order
- WebSocket only for kitchen dashboard; REST for everything else

---

## LLM Integration

### Order Parsing Flow

1. Customer submits text (typed or via Web Speech API speech-to-text)
2. Backend builds a prompt containing the restaurant's full menu (items, variants, modifiers, prices)
3. LLM returns structured JSON matching menu item IDs
4. Backend validates the response - every item/variant/modifier must exist in the DB and be active
5. Backend calculates total price server-side (never trust LLM for pricing)
6. Returns parsed order to frontend for customer confirmation

### Abstraction Layer

```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def parse_order(self, raw_input: str, menu_context: str) -> ParsedOrder:
        ...

class OpenAIProvider(LLMProvider):
    # GPT-4o / GPT-4o-mini
    ...

class AnthropicProvider(LLMProvider):
    # Claude
    ...
```

### Critical Rule

The LLM suggests, the backend validates. LLM output is treated as untrusted input. Every item is verified against the database before showing to the customer.

---

## Frontend Pages

```
frontend/src/app/
├── order/[slug]/
│   ├── page.tsx                  # Ordering page (no table)
│   └── [tableId]/
│       └── page.tsx              # Ordering page (with table)
├── kitchen/[slug]/
│   └── page.tsx                  # Real-time kitchen dashboard
├── admin/
│   ├── page.tsx                  # Dashboard / restaurant list
│   ├── login/page.tsx            # Login
│   ├── register/page.tsx         # Signup
│   └── [slug]/
│       ├── menu/page.tsx         # Menu management
│       ├── orders/page.tsx       # Order history
│       └── settings/page.tsx     # Restaurant settings + QR code generator
└── layout.tsx
```

### Customer Ordering Flow (single page, multi-step)

1. **Welcome step** - Restaurant name/logo, "Type or speak your order"
2. **Input step** - Text box + mic button, customer submits
3. **Loading step** - "Understanding your order..." while LLM parses
4. **Confirmation step** - Parsed items with quantities, variants, modifiers, prices. Edit/remove items. "Add more items" loops back to step 2
5. **Submitted step** - "Order placed! Order #42. Table 5."

### Kitchen Dashboard

- Card-based layout, one card per order
- Columns/swimlanes: Pending -> Preparing -> Ready
- Each card: order number, table (if set), items, time since placed
- New orders animate in with sound notification
- Tap card to advance status

### Admin Panel

- Menu management with drag-and-drop ordering
- Inline editing for prices and descriptions
- Image upload for menu items
- QR code generator: enter table IDs, download printable QR codes

---

## Tech Stack

### Backend
```
Python 3.12
Django 4.2
djangorestframework
djangorestframework-simplejwt
django-channels
channels-redis
openai
django-cors-headers
Pillow
psycopg2-binary
pytest + factory-boy
```

### Frontend
```
Next.js 14 (App Router)
TypeScript
Tailwind CSS
shadcn/ui
react-hot-toast
qrcode.react
zustand
```

### Infrastructure (local dev)
```yaml
# docker-compose.yml
services:
  db:        # PostgreSQL 16
  redis:     # Redis 7
  backend:   # Django dev server
  frontend:  # Next.js dev server
```

### Production (when ready)
- Vercel for frontend
- Railway or Fly.io for Django backend
- Managed Postgres + Redis from hosting provider

---

## Phase 2 (Post-MVP)

- Stripe payment integration (Apple Pay / Google Pay)
- POS integration (Toast / Clover / Lightspeed)
- AI upsell suggestions and combo recommendations
- Customer accounts for repeat orders
- Email/SMS order receipts
- Voice-only hands-free ordering mode
- Loyalty programs and discount codes
- Multi-language UI translations
