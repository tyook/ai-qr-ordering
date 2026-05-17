# Multi-User Team Management

## Overview

Add multi-user support to restaurants with role-based permissions, email-based invitation flow, and a team management UI. Enables restaurant owners to invite employees (admins, kitchen staff) to collaborate on their restaurant.

## Roles

Three fixed roles with a clear hierarchy:

- **Owner**: All permissions. One per restaurant (the `Restaurant.owner` FK). Cannot be removed — only transferred.
- **Admin**: All permissions except removing/demoting the Owner and transferring ownership. Multiple Admins allowed.
- **Member**: Baseline access (kitchen dashboard, view orders). Can be granted additional permissions via per-member overrides.

## Permission System

### Overridable Permissions

Members can be granted these additional permissions beyond their baseline:

| Permission key | Description |
|---------------|-------------|
| `menu_edit` | Create, edit, delete menu items, categories, upload menus |
| `order_manage` | Manage orders beyond viewing (change status, view details) |

Owner and Admin roles implicitly have all permissions — overrides are ignored for them.

### Permission Matrix

| Action | Owner | Admin | Member |
|--------|-------|-------|--------|
| View kitchen dashboard | Yes | Yes | Yes |
| View orders | Yes | Yes | Yes |
| Manage orders (status changes) | Yes | Yes | Override |
| Edit menu | Yes | Yes | Override |
| View analytics | Yes | Yes | No |
| Settings / Billing / POS | Yes | Yes | No |
| Invite / manage team | Yes | Yes | No |
| Remove Owner | — | No | No |
| Transfer ownership | Yes | No | No |

### Resolution Logic

1. If user is `Restaurant.owner` → all permissions
2. If role is `admin` → all permissions
3. If role is `member` → baseline (`kitchen_view`, `order_view`) plus any `true` values in the `permissions` JSON

## Data Model

### Changes to `RestaurantStaff`

- Rename `StaffRole` choices: `owner` / `admin` / `member` (from `owner` / `manager` / `kitchen`)
- Add `permissions` field: `JSONField(default=dict, blank=True)` — stores override flags like `{"menu_edit": true, "order_manage": false}`
- **Data migration required**: A migration must convert existing rows: `manager` → `admin`, `kitchen` → `member`. The `owner` value is unchanged.

### New `Invitation` Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUIDField (PK) | Primary key |
| `restaurant` | FK → Restaurant | Target restaurant |
| `email` | EmailField | Invitee's email address |
| `role` | CharField (choices: admin, member) | Cannot invite as owner |
| `permissions` | JSONField (default=dict) | Pre-set overrides for member invites |
| `token` | CharField (max_length=64, unique) | URL-safe random token, generated via `secrets.token_urlsafe(32)` (32 bytes of randomness) |
| `invited_by` | FK → User | Who sent the invitation |
| `status` | CharField | `pending` / `accepted` / `expired` / `revoked` |
| `created_at` | DateTimeField | Auto-set on creation |
| `expires_at` | DateTimeField | `created_at + 7 days` |

**Constraints:**
- Conditional unique constraint using Django's `UniqueConstraint` with `condition=Q(status="pending")` on `(restaurant, email)` — no duplicate pending invites. This requires PostgreSQL's partial unique index; `unique_together` cannot express this.

### Ownership Transfer

No new model. Atomic operation: swap the `Restaurant.owner` FK and update/create `RestaurantStaff` records accordingly.

## Invitation Flow

### Sending (Owner/Admin)

1. Owner/Admin opens Team Management page, clicks "Invite Member"
2. Enters email, selects role (Admin or Member)
3. If Member, can toggle `menu_edit` and `order_manage` permissions
4. Backend creates `Invitation` record with secure token, `expires_at = now + 7 days`
5. Backend sends email asynchronously (Celery task) with link: `{FRONTEND_URL}/invite/{token}`

**Validations:**
- Email already a staff member → error: "This person is already on your team"
- Email is the restaurant owner → error: "This person is the owner"
- Pending invitation already exists for email+restaurant → error: "Invitation already pending — resend or revoke it first"

### Accepting (Invitee)

1. Invitee clicks link → frontend hits `GET /api/invitations/{token}/` to validate
2. If expired → "This invitation has expired. Ask the restaurant to send a new one."
3. If already accepted → "You've already joined this restaurant." with link to dashboard
4. If valid:
   - **Logged in**: Confirmation screen → "Accept Invitation" button
   - **Not logged in, has account**: "Log in" link, then redirect back after login
   - **No account**: Inline registration form (email pre-filled and locked, name, password, social login options)
5. On accept: create `RestaurantStaff` with role and permissions from invitation, mark invitation as `accepted`, log user in if newly created

### Resend / Revoke

- **Resend**: Resets `expires_at` to `now + 7 days`, sends new email with same token
- **Revoke**: Sets status to `revoked`, token no longer valid

### Multi-Restaurant

Users can belong to multiple restaurants with different roles. The existing `RestaurantStaff` unique constraint on `(user, restaurant)` already supports this.

### Invitation Link Expiry

Links expire after 7 days. Owner/Admin can resend to reset the expiry.

## API Endpoints

### Team Management (Owner/Admin only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/restaurants/:slug/team/` | List all staff + pending invitations |
| POST | `/api/restaurants/:slug/team/invite/` | Send invitation |
| PATCH | `/api/restaurants/:slug/team/:staff_id/` | Update role or permissions |
| DELETE | `/api/restaurants/:slug/team/:staff_id/` | Remove team member |
| POST | `/api/restaurants/:slug/team/transfer-ownership/` | Transfer ownership (Owner only) |
| POST | `/api/restaurants/:slug/team/invitations/:id/resend/` | Resend invitation email |
| DELETE | `/api/restaurants/:slug/team/invitations/:id/` | Revoke invitation |

### Invitation (Public)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/invitations/:token/` | Validate invitation |
| POST | `/api/invitations/:token/accept/` | Accept invitation (see request body below) |

**Accept invitation request body (`POST /api/invitations/:token/accept/`):**

- **Logged-in user**: Empty body or `{}`. The authenticated user is added to the restaurant.
- **New registration**: `{"first_name": "...", "last_name": "...", "password": "..."}`. Email is taken from the invitation. Creates a new User account and adds them to the restaurant.
- **Social auth registration**: `{"auth_provider": "google"|"apple", "auth_token": "..."}`. Creates account via social auth flow and adds to restaurant. The social auth email must match the invitation email.

### Role Check (Any Staff)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/restaurants/:slug/my-role/` | Current user's role + effective permissions |

## Backend Architecture

### Service Layer

New `TeamService` class:

- `invite_member(restaurant, email, role, permissions, invited_by)` — validates, creates Invitation, queues email
- `accept_invitation(token, user=None, registration_data=None)` — validates token, creates user if needed, creates RestaurantStaff
- `update_member(restaurant, staff_id, role=None, permissions=None, acting_user)` — validates permission hierarchy
- `remove_member(restaurant, staff_id, acting_user)` — validates you can't remove the owner
- `transfer_ownership(restaurant, new_owner_id, acting_user)` — atomic swap of owner FK + staff records
- `get_effective_permissions(user, restaurant)` — resolves role + overrides into flat permission dict

### DRF Permission Classes

- `IsRestaurantAdmin` — requires Owner or Admin role (for team management, settings, billing, analytics)
- `HasPermission('menu_edit')` — Owner/Admin auto-pass, Member checked against JSON overrides
- `HasPermission('order_manage')` — same pattern

Existing `IsRestaurantOwnerOrStaff` unchanged — used for basic "can you access this restaurant" checks.

### Existing View Permission Updates

Apply new permission classes to existing views in `restaurants/views.py`:

| View | Current Access | New Permission |
|------|---------------|----------------|
| `RestaurantAnalyticsView` | Any staff | `IsRestaurantAdmin` |
| `SubscriptionDetailView` | Any staff | `IsRestaurantAdmin` |
| `CreateCheckoutSessionView` | Any staff | `IsRestaurantAdmin` |
| `CancelSubscriptionView` | Any staff | `IsRestaurantAdmin` |
| `ReactivateSubscriptionView` | Any staff | `IsRestaurantAdmin` |
| `BillingHistoryView` | Any staff | `IsRestaurantAdmin` |
| `CreateBillingPortalView` | Any staff | `IsRestaurantAdmin` |
| `RestaurantDetailView` (PATCH) | Any staff | `IsRestaurantAdmin` (GET remains any staff) |
| `ConnectOnboardView` | Any staff | `IsRestaurantAdmin` |
| `MenuCategoryListCreateView` (POST) | Any staff | `HasPermission('menu_edit')` |
| `MenuCategoryDetailView` (PATCH) | Any staff | `HasPermission('menu_edit')` |
| `MenuItemListCreateView` (POST) | Any staff | `HasPermission('menu_edit')` |
| `MenuItemDetailView` (PATCH/DELETE) | Any staff | `HasPermission('menu_edit')` |
| `AcceptingOrdersToggleView` (POST) | Any staff | `IsRestaurantAdmin` |
| `OperatingHoursBulkView` (PUT) | Any staff | `IsRestaurantAdmin` |
| `HolidayOverrideListCreateView` (POST) | Any staff | `IsRestaurantAdmin` |
| `TableListCreateView` (POST) | Any staff | `IsRestaurantAdmin` |
| `TableDetailView` (PATCH/DELETE) | Any staff | `IsRestaurantAdmin` |
| `HolidayOverrideDetailView` (PATCH/DELETE) | Any staff | `IsRestaurantAdmin` |
| `PayoutListView` | Any staff | `IsRestaurantAdmin` |
| `PayoutDetailView` | Any staff | `IsRestaurantAdmin` |
| `ConnectStatusView` | Any staff | `IsRestaurantAdmin` |
| `ConnectDashboardView` | Any staff | `IsRestaurantAdmin` |

All GET endpoints on these views remain accessible to any staff member unless listed above as `IsRestaurantAdmin` for all methods. Write operations are gated by role.

### Email

New template: `emails/team_invitation.html`
Celery task: `send_invitation_email` — async send following existing pattern

## Frontend Architecture

### New Routes

- `/account/restaurants/[slug]/team/` — Team Management page (Owner/Admin only)
- `/invite/[token]/` — Invite acceptance page (public)

### New Hooks

- `use-team.ts` — query for team list + mutations for invite, update, remove, resend, revoke
- `use-invitation.ts` — query for invitation validation + accept mutation
- `use-my-role.ts` — query for current user's role + effective permissions

### New Components

- `src/app/account/restaurants/[slug]/team/page.tsx` — Team Management page
- `src/app/account/restaurants/[slug]/team/components/invite-modal.tsx` — Invite dialog
- `src/app/account/restaurants/[slug]/team/components/member-row.tsx` — Row with ⋮ dropdown
- `src/app/account/restaurants/[slug]/team/components/pending-invite-row.tsx` — Pending invitation row
- `src/app/invite/[token]/page.tsx` — Invite acceptance page

### Navigation Changes

- Add "Team" link to the restaurant navigation bar in `/account/restaurants/[slug]/` (the horizontal button bar pattern used across restaurant dashboard pages, visible to Owner/Admin only via `useMyRole`)
- Guard existing routes:
  - Settings, Billing, Analytics, Team → Owner/Admin only
  - Menu editing → Owner/Admin, or Member with `menu_edit`
  - Order management → Owner/Admin, or Member with `order_manage`
  - Kitchen dashboard → all staff

### Frontend Permission Helper

A `can(permission: string)` function derived from `useMyRole` data, used to conditionally render UI elements (nav items, buttons, action menus).

## UI Mockups

Mockups are available in `.superpowers/brainstorm/` for reference:
- `team-management-v2.html` — Team management page with member table, pending invitations, ⋮ dropdown menus, and permission matrix
- `invite-acceptance.html` — Invite acceptance page with logged-in, new account, and error states
