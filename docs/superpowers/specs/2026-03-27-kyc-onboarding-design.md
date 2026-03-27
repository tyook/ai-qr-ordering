# KYC Onboarding Flow — Design Spec

## Overview

A post-signup onboarding wizard that collects customer preferences and optionally sets up restaurant ownership. Triggered via a dismissible persistent banner, accessible at `/account/onboarding`.

## User Flow

1. User signs up or logs in (existing flow)
2. Persistent banner appears site-wide: "Complete your profile for a personalized experience" with "Set up now" CTA and dismiss X
3. Clicking banner (or "Complete your profile" in account menu) navigates to `/account/onboarding`
4. **Step 1 — Customer Preferences** (all optional, skippable):
   - Dietary restrictions (badge toggles + custom input)
   - Allergies (badge toggles + custom input)
   - Preferred language (dropdown)
5. **Step 2 — Are you a restaurant owner?** (Yes/No card selection)
   - **No** → onboarding complete, banner removed
   - **Yes** → Step 3
6. **Step 3 — Restaurant Details**:
   - Restaurant name (required)
   - URL slug (required, auto-generated from name)
   - Phone (optional)
   - Address via Google Places Autocomplete → structured fields (optional)
   - `homepage` and `logo_url` are excluded — can be set later in restaurant settings
   - Creates restaurant → proceeds to Step 4
7. **Step 4 — Menu Upload** (skippable, only shown for restaurant owners):
   - Prompt: "Upload your menu" with description of AI-powered photo parsing
   - "Upload Menu Photos" button opens existing `MenuUploadModal` as a modal overlay
   - The modal handles the full upload → AI parse → review → save flow
   - Requires the restaurant slug from Step 3 (passed to `MenuUploadModal`)
   - "Skip" option to proceed without uploading
   - After modal completion or skip → onboarding complete, redirect to restaurant dashboard

## Banner Behavior

- **Visible when:** authenticated AND `onboarding_completed === false` AND `onboarding_dismissed === false`
- **Dismissing:** sets `onboarding_dismissed = true` server-side, banner disappears
- **Account menu link:** "Complete your profile" visible when `onboarding_completed === false` (regardless of dismiss state)
- **Completing wizard:** sets `onboarding_completed = true`, banner and menu link both disappear
- **Existing users:** When this feature ships, all existing users will have `onboarding_completed = false`. A data migration will set `onboarding_completed = true` for users who already have dietary preferences or allergies filled in, or who already own a restaurant. This avoids showing the banner to users who have effectively already onboarded.

## Backend Changes

### User Model

Add two fields:

- `onboarding_completed` — BooleanField, default=False
- `onboarding_dismissed` — BooleanField, default=False

Update `user_to_dict()` in `accounts/services.py` to include both new fields in its return dict.

### Restaurant Model — Structured Address

Replace single `address` TextField with:

| Field | Type | Notes |
|-------|------|-------|
| `street_address` | CharField(255) | blank=True |
| `city` | CharField(100) | blank=True |
| `state` | CharField(100) | blank=True |
| `zip_code` | CharField(20) | blank=True |
| `country` | CharField(100) | default="US" |
| `google_place_id` | CharField(255) | optional, blank=True |
| `latitude` | DecimalField(9,6) | optional, null=True, blank=True |
| `longitude` | DecimalField(9,6) | optional, null=True, blank=True |

**Migration strategy:** Copy existing `address` values into `street_address` only. The `city`, `state`, `zip_code`, and `country` fields will remain empty for migrated records since the existing freeform text cannot be reliably parsed. Then remove the `address` column.

### API Endpoints

| Method | Path | Purpose | Notes |
|--------|------|---------|-------|
| PATCH | `/api/accounts/me/` | Save preferences (step 1) | Existing `MeView` endpoint, already handles dietary_preferences, allergies, preferred_language |
| POST | `/api/accounts/onboarding/complete/` | Mark onboarding done | New view: `OnboardingCompleteView`. Sets `onboarding_completed = true`. Returns `{"status": "ok"}`. Auth required. |
| POST | `/api/accounts/onboarding/dismiss/` | Dismiss banner | New view: `OnboardingDismissView`. Sets `onboarding_dismissed = true`. Returns `{"status": "ok"}`. Auth required. |
| POST | `/api/restaurants/` | Create restaurant (step 3) | Existing endpoint, updated serializer for structured address |

### Serializer & Service Updates

- `UserProfileSerializer` — add `onboarding_completed` and `onboarding_dismissed` as read-only fields
- `user_to_dict()` in `accounts/services.py` — add `onboarding_completed` and `onboarding_dismissed` to the returned dict
- `RestaurantSerializer` — replace `address` with structured address fields (`street_address`, `city`, `state`, `zip_code`, `country`, `google_place_id`, `latitude`, `longitude`)

### Affected Existing Code

The structured address change affects:
- **Existing restaurant creation page** (`frontend/src/app/account/restaurants/page.tsx`) — must update form to use structured address fields instead of single `address` string
- **`use-create-restaurant` hook** — update payload to send structured fields
- **Any restaurant display code** that reads `address` — update to compose display from structured fields

## Frontend Changes

### New Route

`/account/onboarding` — the wizard page

### State Management

Use local component state (`useState`) for wizard step tracking and form data, since this is a short-lived UI-only flow. This follows the existing codebase pattern where form inputs use local state. React Query mutations handle API calls.

```
Local state:
  step: "preferences" | "owner-question" | "restaurant-details" | "menu-upload"
  (form field values managed per-step component)
```

### New Components

| Component | Purpose |
|-----------|---------|
| `OnboardingBanner` | Persistent top banner, rendered in root layout |
| `OnboardingWizard` | Step container with progress bar, manages step state |
| `PreferencesStep` | Dietary/allergy badges + language dropdown |
| `OwnerQuestionStep` | Yes/No card selection |
| `RestaurantDetailsStep` | Name, slug, phone, address with Google Places |
| `MenuUploadStep` | "Upload your menu" prompt with button to open existing `MenuUploadModal`, plus skip option |
| `GooglePlacesAutocomplete` | Address input with autocomplete dropdown. Used in onboarding wizard and will replace the plain address input on the existing restaurant creation/settings page. |

### Account Menu

Add "Complete your profile" link when `onboarding_completed === false`.

### Google Places Integration

- Use `@react-google-maps/api` package or load Google Places JS API via script tag
- Single address input with autocomplete dropdown
- On selection: parse place components into structured fields
- Show auto-filled fields below input (editable for corrections)
- Fallback: if Google Places API unavailable, show manual text inputs for each field

## Edge Cases

1. **Browser closed mid-wizard** — Step 1 saves preferences immediately via PATCH. On return, user starts from step 2 (preferences already persisted).
2. **User already owns a restaurant** — Check `owned_restaurants.exists()` specifically (not `is_restaurant_owner`, which also includes staff members). If they already own a restaurant and select "Yes" on step 2, skip step 3 and redirect to existing restaurant dashboard.
3. **Slug collision** — Backend validates uniqueness, frontend shows inline error (same as existing restaurant creation).
4. **Google Places API failure** — Fall back to manual text inputs for each address field.
5. **User dismisses banner, returns later** — Account menu link remains until onboarding is completed.
6. **Staff member wants to create own restaurant** — A user who is staff at another restaurant but doesn't own one will see step 3 normally, since we check `owned_restaurants` not `is_restaurant_owner`.
7. **Menu upload fails or user closes modal** — If the `MenuUploadModal` is closed without completing, user returns to the menu upload step and can retry or skip.

## Out of Scope

- Payment information collection (handled at checkout)
- POS integration, Stripe configuration (handled via existing restaurant dashboard)
- Phone verification / identity verification
- Email verification (could be added later)
