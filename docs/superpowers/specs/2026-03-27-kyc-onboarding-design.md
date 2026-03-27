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
   - Creates restaurant → redirects to existing restaurant dashboard

## Banner Behavior

- **Visible when:** authenticated AND `onboarding_completed === false` AND `onboarding_dismissed === false`
- **Dismissing:** sets `onboarding_dismissed = true` server-side, banner disappears
- **Account menu link:** "Complete your profile" visible when `onboarding_completed === false` (regardless of dismiss state)
- **Completing wizard:** sets `onboarding_completed = true`, banner and menu link both disappear

## Backend Changes

### User Model

Add two fields:

- `onboarding_completed` — BooleanField, default=False
- `onboarding_dismissed` — BooleanField, default=False

### Restaurant Model — Structured Address

Replace single `address` TextField with:

| Field | Type | Notes |
|-------|------|-------|
| `street_address` | CharField(255) | |
| `city` | CharField(100) | |
| `state` | CharField(100) | |
| `zip_code` | CharField(20) | |
| `country` | CharField(100) | default="US" |
| `google_place_id` | CharField(255) | optional |
| `latitude` | DecimalField(9,6) | optional, nullable |
| `longitude` | DecimalField(9,6) | optional, nullable |

Migration: copy existing `address` values into `street_address`, then remove `address` column.

### API Endpoints

| Method | Path | Purpose | Notes |
|--------|------|---------|-------|
| PATCH | `/api/accounts/profile/` | Save preferences (step 1) | Existing endpoint, already handles dietary_preferences, allergies, preferred_language |
| POST | `/api/accounts/onboarding/complete/` | Mark onboarding done | Sets `onboarding_completed = true` |
| POST | `/api/accounts/onboarding/dismiss/` | Dismiss banner | Sets `onboarding_dismissed = true` |
| POST | `/api/restaurants/` | Create restaurant (step 3) | Existing endpoint, updated serializer for structured address |

### Serializer Updates

- `UserProfileSerializer` — add `onboarding_completed` and `onboarding_dismissed` as read-only fields
- `RestaurantSerializer` — replace `address` with structured address fields

## Frontend Changes

### New Route

`/account/onboarding` — the wizard page

### New Zustand Store: `useOnboardingStore`

```
State:
  step: "preferences" | "owner-question" | "restaurant-details"
  dietaryPreferences: string[]
  allergies: string[]
  preferredLanguage: string
  isRestaurantOwner: boolean | null
  restaurantData: { name, slug, phone, address fields }
  isLoading: boolean
  error: string | null

Actions:
  setStep()
  setPreferences()
  setOwnerChoice()
  setRestaurantData()
  reset()
```

### New Components

| Component | Purpose |
|-----------|---------|
| `OnboardingBanner` | Persistent top banner, rendered in root layout |
| `OnboardingWizard` | Step container with progress bar |
| `PreferencesStep` | Dietary/allergy badges + language dropdown |
| `OwnerQuestionStep` | Yes/No card selection |
| `RestaurantDetailsStep` | Name, slug, phone, address with Google Places |
| `GooglePlacesAutocomplete` | Reusable address input with autocomplete dropdown |

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
2. **User already has a restaurant** — If user selects "Yes" on step 2 but already owns a restaurant, skip step 3 and redirect to existing restaurant dashboard.
3. **Slug collision** — Backend validates uniqueness, frontend shows inline error (same as existing restaurant creation).
4. **Google Places API failure** — Fall back to manual text inputs for each address field.
5. **User dismisses banner, returns later** — Account menu link remains until onboarding is completed.

## Out of Scope

- Payment information collection (handled at checkout)
- Menu upload, POS integration, Stripe configuration (handled via existing restaurant dashboard)
- Phone verification / identity verification
- Email verification (could be added later)
