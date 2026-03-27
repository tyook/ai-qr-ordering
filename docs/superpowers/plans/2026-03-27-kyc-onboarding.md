# KYC Onboarding Flow Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a post-signup onboarding wizard that collects customer preferences and optionally sets up restaurant ownership with menu upload.

**Architecture:** Multi-step wizard at `/account/onboarding` triggered by a persistent dismissible banner. Backend adds `onboarding_completed`/`onboarding_dismissed` fields to User and replaces the Restaurant `address` field with structured address columns. Frontend reuses existing profile PATCH and restaurant creation endpoints, plus the existing `MenuUploadModal` for menu photo upload.

**Tech Stack:** Django REST Framework, PostgreSQL, Next.js 14 (App Router), React 18, TypeScript, React Query, Zustand, Google Places API, shadcn/ui

**Spec:** `docs/superpowers/specs/2026-03-27-kyc-onboarding-design.md`

---

## File Map

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `backend/accounts/views_onboarding.py` | `OnboardingCompleteView` and `OnboardingDismissView` |
| `backend/accounts/tests/test_onboarding.py` | Tests for onboarding endpoints and user model fields |
| `backend/restaurants/tests/test_structured_address.py` | Tests for structured address migration and serializer |

### Backend — Modified Files
| File | Change |
|------|--------|
| `backend/accounts/models.py` | Add `onboarding_completed`, `onboarding_dismissed` fields |
| `backend/accounts/services.py` | Add new fields to `user_to_dict()` |
| `backend/accounts/serializers.py` | Add new fields to `UserProfileSerializer` |
| `backend/accounts/urls.py` | Add onboarding endpoint routes |
| `backend/restaurants/models.py` | Replace `address` with structured fields |
| `backend/restaurants/serializers/restaurant_serializers.py` | Update `RestaurantSerializer` for structured address |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/app/account/onboarding/page.tsx` | Onboarding wizard page with step management |
| `frontend/src/components/onboarding/onboarding-banner.tsx` | Persistent site-wide banner |
| `frontend/src/components/onboarding/preferences-step.tsx` | Step 1: dietary/allergy/language |
| `frontend/src/components/onboarding/owner-question-step.tsx` | Step 2: restaurant owner yes/no |
| `frontend/src/components/onboarding/restaurant-details-step.tsx` | Step 3: restaurant creation form |
| `frontend/src/components/onboarding/menu-upload-step.tsx` | Step 4: menu upload prompt |
| `frontend/src/components/google-places-autocomplete.tsx` | Reusable address autocomplete input |
| `frontend/src/hooks/use-onboarding.ts` | API hooks for onboarding complete/dismiss |

### Frontend — Modified Files
| File | Change |
|------|--------|
| `frontend/src/types/index.ts` | Add onboarding fields to `User`, update `Restaurant` address fields |
| `frontend/src/lib/api.ts` | Add `completeOnboarding()`, `dismissOnboarding()` functions |
| `frontend/src/app/layout.tsx` | Add `OnboardingBanner` component |
| `frontend/src/hooks/use-create-restaurant.ts` | Update `CreateRestaurantParams` for structured address |
| `frontend/src/app/account/restaurants/page.tsx` | Update create form for structured address |

---

## Chunk 1: Backend — User Model & Onboarding Endpoints

### Task 1: Add onboarding fields to User model

**Files:**
- Modify: `backend/accounts/models.py:7-62`
- Test: `backend/accounts/tests/test_onboarding.py` (create)

- [ ] **Step 1: Write test for new User model fields**

Create `backend/accounts/tests/test_onboarding.py`:

```python
import pytest
from accounts.models import User


@pytest.mark.django_db
class TestUserOnboardingFields:
    def test_onboarding_completed_defaults_to_false(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        assert user.onboarding_completed is False

    def test_onboarding_dismissed_defaults_to_false(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        assert user.onboarding_dismissed is False

    def test_can_set_onboarding_completed(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        user.onboarding_completed = True
        user.save()
        user.refresh_from_db()
        assert user.onboarding_completed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest accounts/tests/test_onboarding.py -v`
Expected: FAIL — fields don't exist yet

- [ ] **Step 3: Add fields to User model**

In `backend/accounts/models.py`, add after the `preferred_language` field (around line 25):

```python
    onboarding_completed = models.BooleanField(default=False)
    onboarding_dismissed = models.BooleanField(default=False)
```

- [ ] **Step 4: Create and run migration**

Run: `cd backend && python manage.py makemigrations accounts && python manage.py migrate`

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest accounts/tests/test_onboarding.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/accounts/models.py backend/accounts/migrations/ backend/accounts/tests/test_onboarding.py
git commit -m "feat: add onboarding_completed and onboarding_dismissed fields to User model"
```

---

### Task 2: Update user_to_dict and UserProfileSerializer

**Files:**
- Modify: `backend/accounts/services.py:52-66`
- Modify: `backend/accounts/serializers.py:54-67`
- Test: `backend/accounts/tests/test_onboarding.py` (append)

- [ ] **Step 1: Write tests for serializer and service**

Append to `backend/accounts/tests/test_onboarding.py`:

```python
from accounts.services import user_to_dict
from accounts.serializers import UserProfileSerializer


@pytest.mark.django_db
class TestOnboardingInUserDict:
    def test_user_to_dict_includes_onboarding_completed(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        result = user_to_dict(user)
        assert "onboarding_completed" in result
        assert result["onboarding_completed"] is False

    def test_user_to_dict_includes_onboarding_dismissed(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        result = user_to_dict(user)
        assert "onboarding_dismissed" in result
        assert result["onboarding_dismissed"] is False


@pytest.mark.django_db
class TestOnboardingInProfileSerializer:
    def test_serializer_includes_onboarding_fields(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        serializer = UserProfileSerializer(user)
        assert "onboarding_completed" in serializer.data
        assert "onboarding_dismissed" in serializer.data

    def test_onboarding_fields_are_read_only(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        serializer = UserProfileSerializer(
            user, data={"onboarding_completed": True}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        user.refresh_from_db()
        assert user.onboarding_completed is False  # Should not change via serializer
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest accounts/tests/test_onboarding.py::TestOnboardingInUserDict accounts/tests/test_onboarding.py::TestOnboardingInProfileSerializer -v`
Expected: FAIL

- [ ] **Step 3: Update user_to_dict in services.py**

In `backend/accounts/services.py`, inside `user_to_dict()` (around line 52-66), add to the returned dict:

```python
        "onboarding_completed": user.onboarding_completed,
        "onboarding_dismissed": user.onboarding_dismissed,
        "owns_restaurant": user.owned_restaurants.exists(),
```

- [ ] **Step 4: Update UserProfileSerializer**

In `backend/accounts/serializers.py`, in `UserProfileSerializer.Meta`:
- Add `onboarding_completed` and `onboarding_dismissed` to the `fields` list
- Add both to the `read_only_fields` list

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest accounts/tests/test_onboarding.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/accounts/services.py backend/accounts/serializers.py backend/accounts/tests/test_onboarding.py
git commit -m "feat: include onboarding fields in user_to_dict and UserProfileSerializer"
```

---

### Task 3: Create onboarding complete and dismiss endpoints

**Files:**
- Create: `backend/accounts/views_onboarding.py`
- Modify: `backend/accounts/urls.py:1-34`
- Test: `backend/accounts/tests/test_onboarding.py` (append)

- [ ] **Step 1: Write tests for onboarding endpoints**

Append to `backend/accounts/tests/test_onboarding.py`:

```python
from rest_framework.test import APIClient


@pytest.fixture
def auth_client(db):
    user = User.objects.create_user(
        email="test@example.com",
        password="testpass123",
        first_name="Test",
        last_name="User",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
class TestOnboardingCompleteEndpoint:
    def test_marks_onboarding_as_completed(self, auth_client):
        client, user = auth_client
        response = client.post("/api/account/onboarding/complete/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        user.refresh_from_db()
        assert user.onboarding_completed is True

    def test_requires_authentication(self):
        client = APIClient()
        response = client.post("/api/account/onboarding/complete/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestOnboardingDismissEndpoint:
    def test_marks_onboarding_as_dismissed(self, auth_client):
        client, user = auth_client
        response = client.post("/api/account/onboarding/dismiss/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        user.refresh_from_db()
        assert user.onboarding_dismissed is True

    def test_requires_authentication(self):
        client = APIClient()
        response = client.post("/api/account/onboarding/dismiss/")
        assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest accounts/tests/test_onboarding.py::TestOnboardingCompleteEndpoint accounts/tests/test_onboarding.py::TestOnboardingDismissEndpoint -v`
Expected: FAIL — endpoints don't exist

- [ ] **Step 3: Create views_onboarding.py**

Create `backend/accounts/views_onboarding.py`:

```python
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class OnboardingCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.onboarding_completed = True
        request.user.save(update_fields=["onboarding_completed"])
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class OnboardingDismissView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.onboarding_dismissed = True
        request.user.save(update_fields=["onboarding_dismissed"])
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
```

- [ ] **Step 4: Add URL routes**

In `backend/accounts/urls.py`, add imports and routes:

```python
from accounts.views_onboarding import OnboardingCompleteView, OnboardingDismissView
```

Add to `urlpatterns`:

```python
    path("account/onboarding/complete/", OnboardingCompleteView.as_view()),
    path("account/onboarding/dismiss/", OnboardingDismissView.as_view()),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest accounts/tests/test_onboarding.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/accounts/views_onboarding.py backend/accounts/urls.py backend/accounts/tests/test_onboarding.py
git commit -m "feat: add onboarding complete and dismiss API endpoints"
```

---

## Chunk 2: Backend — Structured Address Migration

### Task 4: Replace Restaurant address field with structured fields

**Files:**
- Modify: `backend/restaurants/models.py:7-27`
- Test: `backend/restaurants/tests/test_structured_address.py` (create)

- [ ] **Step 1: Write tests for structured address fields**

Create `backend/restaurants/tests/test_structured_address.py`:

```python
import pytest
from accounts.models import User
from restaurants.models import Restaurant


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        email="owner@example.com",
        password="testpass123",
        first_name="Owner",
        last_name="User",
    )


@pytest.mark.django_db
class TestRestaurantStructuredAddress:
    def test_structured_address_fields_exist(self, owner):
        restaurant = Restaurant.objects.create(
            name="Test Restaurant",
            slug="test-restaurant",
            owner=owner,
            street_address="123 Main St",
            city="San Francisco",
            state="CA",
            zip_code="94105",
            country="US",
        )
        restaurant.refresh_from_db()
        assert restaurant.street_address == "123 Main St"
        assert restaurant.city == "San Francisco"
        assert restaurant.state == "CA"
        assert restaurant.zip_code == "94105"
        assert restaurant.country == "US"

    def test_country_defaults_to_us(self, owner):
        restaurant = Restaurant.objects.create(
            name="Test Restaurant",
            slug="test-restaurant-2",
            owner=owner,
        )
        assert restaurant.country == "US"

    def test_address_fields_are_optional(self, owner):
        restaurant = Restaurant.objects.create(
            name="Test Restaurant",
            slug="test-restaurant-3",
            owner=owner,
        )
        assert restaurant.street_address == ""
        assert restaurant.city == ""
        assert restaurant.state == ""
        assert restaurant.zip_code == ""

    def test_lat_lng_nullable(self, owner):
        restaurant = Restaurant.objects.create(
            name="Test Restaurant",
            slug="test-restaurant-4",
            owner=owner,
        )
        assert restaurant.latitude is None
        assert restaurant.longitude is None

    def test_google_place_id_optional(self, owner):
        restaurant = Restaurant.objects.create(
            name="Test Restaurant",
            slug="test-restaurant-5",
            owner=owner,
            google_place_id="ChIJIQBpA...",
        )
        assert restaurant.google_place_id == "ChIJIQBpA..."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest restaurants/tests/test_structured_address.py -v`
Expected: FAIL — fields don't exist

- [ ] **Step 3: Update Restaurant model**

In `backend/restaurants/models.py`, replace the `address` field (around line 14) with:

```python
    street_address = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    zip_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="US")
    google_place_id = models.CharField(max_length=255, blank=True, default="")
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
```

- [ ] **Step 4: Create migration — add new fields only (keep old address temporarily)**

Do NOT remove the `address` field from the model yet. Instead, keep both the old `address` field and the new structured fields in the model temporarily. This lets the auto-generated migration just add the new fields.

Run: `cd backend && python manage.py makemigrations restaurants && python manage.py migrate`

- [ ] **Step 5: Create data migration to copy address → street_address**

Run: `cd backend && python manage.py makemigrations restaurants --empty -n copy_address_to_street_address`

Edit the generated migration file with this content:

```python
from django.db import migrations


def copy_address_to_street_address(apps, schema_editor):
    Restaurant = apps.get_model("restaurants", "Restaurant")
    for restaurant in Restaurant.objects.exclude(address=""):
        restaurant.street_address = restaurant.address
        restaurant.save(update_fields=["street_address"])


def reverse(apps, schema_editor):
    Restaurant = apps.get_model("restaurants", "Restaurant")
    for restaurant in Restaurant.objects.exclude(street_address=""):
        restaurant.address = restaurant.street_address
        restaurant.save(update_fields=["address"])


class Migration(migrations.Migration):
    dependencies = [
        ("restaurants", "<previous_migration>"),  # Use the migration name from Step 4
    ]

    operations = [
        migrations.RunPython(copy_address_to_street_address, reverse),
    ]
```

Run: `cd backend && python manage.py migrate`

- [ ] **Step 6: Remove old address field**

Now remove the `address` field from the Restaurant model in `backend/restaurants/models.py`.

Run: `cd backend && python manage.py makemigrations restaurants && python manage.py migrate`

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && python -m pytest restaurants/tests/test_structured_address.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add backend/restaurants/models.py backend/restaurants/migrations/ backend/restaurants/tests/test_structured_address.py
git commit -m "feat: replace Restaurant address with structured address fields"
```

---

### Task 5: Update RestaurantSerializer for structured address

**Files:**
- Modify: `backend/restaurants/serializers/restaurant_serializers.py:14-68`
- Test: `backend/restaurants/tests/test_structured_address.py` (append)

- [ ] **Step 1: Write tests for serializer**

Append to `backend/restaurants/tests/test_structured_address.py`:

```python
from rest_framework.test import APIClient


@pytest.fixture
def auth_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.mark.django_db
class TestRestaurantSerializerStructuredAddress:
    def test_create_restaurant_with_structured_address(self, auth_client):
        response = auth_client.post(
            "/api/restaurants/",
            {
                "name": "Sakura Sushi",
                "slug": "sakura-sushi",
                "phone": "555-123-4567",
                "street_address": "123 Main St",
                "city": "San Francisco",
                "state": "CA",
                "zip_code": "94105",
                "country": "US",
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["street_address"] == "123 Main St"
        assert data["city"] == "San Francisco"
        assert data["state"] == "CA"
        assert data["zip_code"] == "94105"
        assert data["country"] == "US"

    def test_create_restaurant_without_address(self, auth_client):
        response = auth_client.post(
            "/api/restaurants/",
            {"name": "No Address Place", "slug": "no-address"},
            format="json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["street_address"] == ""
        assert data["country"] == "US"

    def test_get_restaurant_includes_structured_address(self, auth_client, owner):
        Restaurant.objects.create(
            name="Test",
            slug="test-get",
            owner=owner,
            street_address="456 Oak Ave",
            city="LA",
            state="CA",
            zip_code="90001",
        )
        response = auth_client.get("/api/restaurants/test-get/")
        assert response.status_code == 200
        data = response.json()
        assert data["street_address"] == "456 Oak Ave"
        assert data["city"] == "LA"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest restaurants/tests/test_structured_address.py::TestRestaurantSerializerStructuredAddress -v`
Expected: FAIL

- [ ] **Step 3: Update RestaurantSerializer**

In `backend/restaurants/serializers/restaurant_serializers.py`, update `RestaurantSerializer.Meta.fields`:

Replace `address` with: `street_address`, `city`, `state`, `zip_code`, `country`, `google_place_id`, `latitude`, `longitude`

All new address fields should be optional (the model already has `blank=True`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest restaurants/tests/test_structured_address.py -v`
Expected: All PASS

- [ ] **Step 5: Run all backend tests to check for regressions**

Run: `cd backend && python -m pytest --tb=short`
Expected: All PASS (fix any tests that reference the old `address` field)

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/serializers/restaurant_serializers.py backend/restaurants/tests/test_structured_address.py
git commit -m "feat: update RestaurantSerializer for structured address fields"
```

---

## Chunk 3: Frontend — Types, API Client, and Hooks

### Task 6: Update TypeScript types

**Files:**
- Modify: `frontend/src/types/index.ts:17-28` (Restaurant), `frontend/src/types/index.ts:31-43` (User)

- [ ] **Step 1: Update User interface**

In `frontend/src/types/index.ts`, add to the `User` interface (after `is_restaurant_owner`):

```typescript
  owns_restaurant: boolean;
  onboarding_completed: boolean;
  onboarding_dismissed: boolean;
```

- [ ] **Step 2: Update Restaurant interface**

In `frontend/src/types/index.ts`, replace `address: string;` in the `Restaurant` interface with:

```typescript
  street_address: string;
  city: string;
  state: string;
  zip_code: string;
  country: string;
  google_place_id: string;
  latitude: number | null;
  longitude: number | null;
```

- [ ] **Step 3: Run TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: Type errors in files still using old `address` field — that's expected, we'll fix those next.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add onboarding fields to User type and structured address to Restaurant type"
```

---

### Task 7: Update API client with onboarding functions

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add onboarding API functions**

In `frontend/src/lib/api.ts`, add:

```typescript
export async function completeOnboarding(): Promise<{ status: string }> {
  return apiFetch("/api/account/onboarding/complete/", { method: "POST" });
}

export async function dismissOnboarding(): Promise<{ status: string }> {
  return apiFetch("/api/account/onboarding/dismiss/", { method: "POST" });
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add onboarding complete and dismiss API functions"
```

---

### Task 8: Create onboarding hooks

**Files:**
- Create: `frontend/src/hooks/use-onboarding.ts`

- [ ] **Step 1: Create the hooks file**

Create `frontend/src/hooks/use-onboarding.ts`:

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { completeOnboarding, dismissOnboarding } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";

export function useCompleteOnboarding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: completeOnboarding,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      // Also refresh the Zustand auth store so the banner updates immediately
      useAuthStore.getState().checkAuth();
    },
  });
}

export function useDismissOnboarding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: dismissOnboarding,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      // Also refresh the Zustand auth store so the banner updates immediately
      useAuthStore.getState().checkAuth();
    },
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/use-onboarding.ts
git commit -m "feat: add useCompleteOnboarding and useDismissOnboarding hooks"
```

---

### Task 9: Update restaurant creation hook and page for structured address

**Files:**
- Modify: `frontend/src/hooks/use-create-restaurant.ts`
- Modify: `frontend/src/app/account/restaurants/page.tsx`

- [ ] **Step 1: Update CreateRestaurantParams interface**

In `frontend/src/hooks/use-create-restaurant.ts`, update the interface:

```typescript
interface CreateRestaurantParams {
  name: string;
  slug: string;
  phone?: string;
  street_address?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  country?: string;
  google_place_id?: string;
  latitude?: number | null;
  longitude?: number | null;
  homepage?: string;
  logo_url?: string;
}
```

- [ ] **Step 2: Update restaurant creation page**

In `frontend/src/app/account/restaurants/page.tsx`, update the create form:
- Replace the single `address` text input with a `street_address` input (for now — Google Places will be added in a later task)
- Add `city`, `state`, `zip_code` inputs
- Update the form state and submission to use new field names
- Update any display of restaurant address in the list to compose from structured fields

- [ ] **Step 3: Run TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no more type errors from old `address` field)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/use-create-restaurant.ts frontend/src/app/account/restaurants/page.tsx
git commit -m "feat: update restaurant creation for structured address fields"
```

---

## Chunk 4: Frontend — Onboarding Banner

### Task 10: Create OnboardingBanner component

**Files:**
- Create: `frontend/src/components/onboarding/onboarding-banner.tsx`
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Create the banner component**

Create `frontend/src/components/onboarding/onboarding-banner.tsx`:

```typescript
"use client";

import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useDismissOnboarding } from "@/hooks/use-onboarding";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

export function OnboardingBanner() {
  const router = useRouter();
  const { isAuthenticated, user } = useAuthStore();
  const dismissMutation = useDismissOnboarding();

  if (
    !isAuthenticated ||
    !user ||
    user.onboarding_completed ||
    user.onboarding_dismissed
  ) {
    return null;
  }

  const handleDismiss = () => {
    dismissMutation.mutate();
  };

  return (
    <div className="bg-gradient-to-r from-blue-900/50 to-green-900/50 border-b border-blue-800/50 px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-blue-400 text-sm">✨</span>
        <span className="text-sm text-gray-200">
          Complete your profile for a personalized experience
        </span>
        <Button
          variant="default"
          size="sm"
          onClick={() => router.push("/account/onboarding")}
        >
          Set up now
        </Button>
      </div>
      <button
        onClick={handleDismiss}
        className="text-gray-500 hover:text-gray-300 transition-colors"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Add banner to root layout**

In `frontend/src/app/layout.tsx`, import and add `<OnboardingBanner />` just inside the `<body>`, after the providers but before or alongside `<ConditionalHeader />`. The banner should appear above the header on all pages.

```typescript
import { OnboardingBanner } from "@/components/onboarding/onboarding-banner";
```

Add `<OnboardingBanner />` inside the `<QueryProvider>` and `<ThemeProvider>` wrappers, before `<ConditionalHeader />`. The banner needs React Query context (for mutations) and theme context (for styling).

- [ ] **Step 3: Test manually**

Run: `cd frontend && npm run dev`
- Log in as a user with `onboarding_completed = false`
- Verify banner appears on all pages
- Verify clicking X dismisses the banner
- Verify clicking "Set up now" navigates to `/account/onboarding` (will 404 for now)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/onboarding/onboarding-banner.tsx frontend/src/app/layout.tsx
git commit -m "feat: add persistent onboarding banner to root layout"
```

---

## Chunk 5: Frontend — Onboarding Wizard Page and Steps

### Task 11: Create the onboarding wizard page

**Files:**
- Create: `frontend/src/app/account/onboarding/page.tsx`

- [ ] **Step 1: Create the wizard page**

Create `frontend/src/app/account/onboarding/page.tsx`:

```typescript
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useRequireAuth } from "@/hooks/use-auth";
import { useAuthStore } from "@/stores/auth-store";
import { useCompleteOnboarding } from "@/hooks/use-onboarding";
import { PreferencesStep } from "@/components/onboarding/preferences-step";
import { OwnerQuestionStep } from "@/components/onboarding/owner-question-step";
import { RestaurantDetailsStep } from "@/components/onboarding/restaurant-details-step";
import { MenuUploadStep } from "@/components/onboarding/menu-upload-step";

type Step = "preferences" | "owner-question" | "restaurant-details" | "menu-upload";

export default function OnboardingPage() {
  const isAuthenticated = useRequireAuth();
  const router = useRouter();
  const { user } = useAuthStore();
  const completeMutation = useCompleteOnboarding();
  const [step, setStep] = useState<Step>("preferences");
  const [restaurantSlug, setRestaurantSlug] = useState<string | null>(null);

  if (!isAuthenticated || !user) return null;

  const totalSteps = step === "restaurant-details" || step === "menu-upload" ? 4 : 2;
  const currentStep =
    step === "preferences" ? 1 :
    step === "owner-question" ? 2 :
    step === "restaurant-details" ? 3 : 4;

  const handleComplete = () => {
    completeMutation.mutate(undefined, {
      onSuccess: () => router.push(
        restaurantSlug ? `/account/restaurants/${restaurantSlug}/menu` : "/"
      ),
    });
  };

  const progressPercent = (currentStep / totalSteps) * 100;

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      {/* Progress bar */}
      <div className="mb-6">
        <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-1">
          Step {currentStep} of {totalSteps}
        </p>
      </div>

      {step === "preferences" && (
        <PreferencesStep
          onNext={() => setStep("owner-question")}
          onSkip={() => setStep("owner-question")}
        />
      )}

      {step === "owner-question" && (
        <OwnerQuestionStep
          onYes={() => {
            if (user.owns_restaurant) {
              // Already owns a restaurant — skip to complete
              handleComplete();
            } else {
              setStep("restaurant-details");
            }
          }}
          onNo={handleComplete}
          onBack={() => setStep("preferences")}
        />
      )}

      {step === "restaurant-details" && (
        <RestaurantDetailsStep
          onCreated={(slug) => {
            setRestaurantSlug(slug);
            setStep("menu-upload");
          }}
          onBack={() => setStep("owner-question")}
        />
      )}

      {step === "menu-upload" && restaurantSlug && (
        <MenuUploadStep
          slug={restaurantSlug}
          onComplete={handleComplete}
          onSkip={handleComplete}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/account/onboarding/page.tsx
git commit -m "feat: create onboarding wizard page with step management"
```

---

### Task 12: Create PreferencesStep component

**Files:**
- Create: `frontend/src/components/onboarding/preferences-step.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/onboarding/preferences-step.tsx`:

This component should closely follow the existing pattern in `frontend/src/app/account/profile/page.tsx` (lines for dietary preferences and allergies sections). Reuse the same predefined badge lists and custom input pattern.

```typescript
"use client";

import { useState } from "react";
import { useProfile, useUpdateProfile } from "@/hooks/use-profile";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SPEECH_LANGUAGES } from "@/lib/constants"; // Check if this exists, else define inline

interface PreferencesStepProps {
  onNext: () => void;
  onSkip: () => void;
}

const DIETARY_OPTIONS = [
  "Vegetarian", "Vegan", "Halal", "Kosher",
  "Gluten-Free", "Pescatarian", "Dairy-Free",
];

const ALLERGY_OPTIONS = [
  "Peanuts", "Tree Nuts", "Dairy", "Eggs",
  "Shellfish", "Soy", "Wheat", "Fish",
];

export function PreferencesStep({ onNext, onSkip }: PreferencesStepProps) {
  const { data: profile } = useProfile();
  const updateProfile = useUpdateProfile();

  const [dietaryPreferences, setDietaryPreferences] = useState<string[]>(
    profile?.dietary_preferences ?? []
  );
  const [allergies, setAllergies] = useState<string[]>(
    profile?.allergies ?? []
  );
  const [preferredLanguage, setPreferredLanguage] = useState(
    profile?.preferred_language ?? "en-US"
  );
  const [customDietary, setCustomDietary] = useState("");
  const [customAllergy, setCustomAllergy] = useState("");

  const toggleItem = (list: string[], item: string, setList: (l: string[]) => void) => {
    setList(list.includes(item) ? list.filter((i) => i !== item) : [...list, item]);
  };

  const addCustom = (value: string, list: string[], setList: (l: string[]) => void, setClear: (v: string) => void) => {
    const trimmed = value.trim();
    if (trimmed && !list.includes(trimmed)) {
      setList([...list, trimmed]);
    }
    setClear("");
  };

  const handleSave = () => {
    updateProfile.mutate(
      {
        dietary_preferences: dietaryPreferences,
        allergies,
        preferred_language: preferredLanguage,
      },
      { onSuccess: onNext }
    );
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-1">Tell us about your preferences</h2>
      <p className="text-sm text-gray-400 mb-6">
        This helps us personalize your ordering experience. Everything is optional.
      </p>

      {/* Dietary Restrictions */}
      <div className="mb-5">
        <label className="text-sm font-medium text-gray-300 mb-2 block">
          Dietary Restrictions
        </label>
        <div className="flex flex-wrap gap-2">
          {DIETARY_OPTIONS.map((option) => (
            <button
              key={option}
              onClick={() => toggleItem(dietaryPreferences, option, setDietaryPreferences)}
              className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                dietaryPreferences.includes(option)
                  ? "bg-green-900/50 border-green-700 text-green-400"
                  : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500"
              }`}
            >
              {option}
            </button>
          ))}
        </div>
        <div className="flex gap-2 mt-2">
          <Input
            placeholder="Add custom restriction..."
            value={customDietary}
            onChange={(e) => setCustomDietary(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addCustom(customDietary, dietaryPreferences, setDietaryPreferences, setCustomDietary);
              }
            }}
            className="flex-1"
          />
        </div>
      </div>

      {/* Allergies */}
      <div className="mb-5">
        <label className="text-sm font-medium text-gray-300 mb-2 block">
          Allergies
        </label>
        <div className="flex flex-wrap gap-2">
          {ALLERGY_OPTIONS.map((option) => (
            <button
              key={option}
              onClick={() => toggleItem(allergies, option, setAllergies)}
              className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                allergies.includes(option)
                  ? "bg-red-900/50 border-red-700 text-red-400"
                  : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500"
              }`}
            >
              {option}
            </button>
          ))}
        </div>
        <div className="flex gap-2 mt-2">
          <Input
            placeholder="Add custom allergy..."
            value={customAllergy}
            onChange={(e) => setCustomAllergy(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addCustom(customAllergy, allergies, setAllergies, setCustomAllergy);
              }
            }}
            className="flex-1"
          />
        </div>
      </div>

      {/* Preferred Language */}
      <div className="mb-7">
        <label className="text-sm font-medium text-gray-300 mb-2 block">
          Preferred Language (for voice ordering)
        </label>
        <select
          value={preferredLanguage}
          onChange={(e) => setPreferredLanguage(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
        >
          <option value="en-US">English</option>
          <option value="es-ES">Spanish</option>
          <option value="fr-FR">French</option>
          <option value="zh-CN">Chinese (Mandarin)</option>
          <option value="ja-JP">Japanese</option>
          <option value="ko-KR">Korean</option>
        </select>
      </div>

      {/* Navigation */}
      <div className="flex justify-between items-center">
        <button onClick={onSkip} className="text-sm text-gray-500 hover:text-gray-300">
          Skip
        </button>
        <Button onClick={handleSave} disabled={updateProfile.isPending}>
          {updateProfile.isPending ? "Saving..." : "Continue"}
        </Button>
      </div>
    </div>
  );
}
```

**Note:** `SPEECH_LANGUAGES` exists in `frontend/src/lib/constants.ts` (used by the profile page). Import and use it for the language dropdown instead of the hardcoded list above. Replace the `<select>` options with a map over `SPEECH_LANGUAGES`. Add the import: `import { SPEECH_LANGUAGES } from "@/lib/constants";`

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/onboarding/preferences-step.tsx
git commit -m "feat: create PreferencesStep component for onboarding wizard"
```

---

### Task 13: Create OwnerQuestionStep component

**Files:**
- Create: `frontend/src/components/onboarding/owner-question-step.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/onboarding/owner-question-step.tsx`:

```typescript
"use client";

interface OwnerQuestionStepProps {
  onYes: () => void;
  onNo: () => void;
  onBack: () => void;
}

export function OwnerQuestionStep({ onYes, onNo, onBack }: OwnerQuestionStepProps) {
  return (
    <div>
      <h2 className="text-xl font-semibold mb-1 text-center">
        Are you a restaurant owner?
      </h2>
      <p className="text-sm text-gray-400 mb-8 text-center">
        Set up your restaurant to start receiving QR orders
      </p>

      <div className="flex gap-4 justify-center mb-8">
        <button
          onClick={onYes}
          className="flex-1 max-w-[180px] bg-blue-900/30 border-2 border-blue-700 rounded-xl p-6 text-center hover:border-blue-500 transition-colors"
        >
          <div className="text-3xl mb-2">🏪</div>
          <div className="font-semibold text-gray-200">Yes</div>
          <div className="text-xs text-gray-500 mt-1">Set up my restaurant</div>
        </button>

        <button
          onClick={onNo}
          className="flex-1 max-w-[180px] bg-gray-800 border-2 border-gray-700 rounded-xl p-6 text-center hover:border-gray-500 transition-colors"
        >
          <div className="text-3xl mb-2">🍽️</div>
          <div className="font-semibold text-gray-200">No</div>
          <div className="text-xs text-gray-500 mt-1">I'm just a customer</div>
        </button>
      </div>

      <div className="flex justify-between items-center">
        <button onClick={onBack} className="text-sm text-gray-500 hover:text-gray-300">
          ← Back
        </button>
        <button onClick={onNo} className="text-sm text-gray-500 hover:text-gray-300">
          Skip
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/onboarding/owner-question-step.tsx
git commit -m "feat: create OwnerQuestionStep component for onboarding wizard"
```

---

### Task 14: Create GooglePlacesAutocomplete component

**Files:**
- Create: `frontend/src/components/google-places-autocomplete.tsx`

- [ ] **Step 1: Install Google Maps package (if not already installed)**

Run: `cd frontend && npm install @react-google-maps/api`

Note: Check if `@react-google-maps/api` or similar is already installed. If Google Maps API is already loaded via script tag (check `layout.tsx`), use the native `google.maps.places.Autocomplete` API instead.

- [ ] **Step 2: Create the component**

Create `frontend/src/components/google-places-autocomplete.tsx`:

```typescript
"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { Input } from "@/components/ui/input";

interface AddressComponents {
  street_address: string;
  city: string;
  state: string;
  zip_code: string;
  country: string;
  google_place_id: string;
  latitude: number | null;
  longitude: number | null;
}

interface GooglePlacesAutocompleteProps {
  onSelect: (address: AddressComponents) => void;
  defaultValue?: string;
}

function parsePlace(place: google.maps.places.PlaceResult): AddressComponents {
  const components: AddressComponents = {
    street_address: "",
    city: "",
    state: "",
    zip_code: "",
    country: "",
    google_place_id: place.place_id ?? "",
    latitude: place.geometry?.location?.lat() ?? null,
    longitude: place.geometry?.location?.lng() ?? null,
  };

  let streetNumber = "";
  let route = "";

  for (const component of place.address_components ?? []) {
    const type = component.types[0];
    if (type === "street_number") streetNumber = component.long_name;
    else if (type === "route") route = component.long_name;
    else if (type === "locality") components.city = component.long_name;
    else if (type === "administrative_area_level_1") components.state = component.short_name;
    else if (type === "postal_code") components.zip_code = component.long_name;
    else if (type === "country") components.country = component.short_name;
  }

  components.street_address = [streetNumber, route].filter(Boolean).join(" ");
  return components;
}

export function GooglePlacesAutocomplete({
  onSelect,
  defaultValue = "",
}: GooglePlacesAutocompleteProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const autocompleteRef = useRef<google.maps.places.Autocomplete | null>(null);
  const [inputValue, setInputValue] = useState(defaultValue);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    if (typeof google !== "undefined" && google.maps?.places) {
      setIsLoaded(true);
    }
    // If Google Maps isn't loaded, fall back to plain input
  }, []);

  useEffect(() => {
    if (!isLoaded || !inputRef.current || autocompleteRef.current) return;

    autocompleteRef.current = new google.maps.places.Autocomplete(inputRef.current, {
      types: ["address"],
      fields: ["address_components", "geometry", "place_id"],
    });

    autocompleteRef.current.addListener("place_changed", () => {
      const place = autocompleteRef.current?.getPlace();
      if (place?.address_components) {
        const parsed = parsePlace(place);
        setInputValue(place.formatted_address ?? "");
        onSelect(parsed);
      }
    });
  }, [isLoaded, onSelect]);

  return (
    <Input
      ref={inputRef}
      value={inputValue}
      onChange={(e) => setInputValue(e.target.value)}
      placeholder="Start typing an address..."
    />
  );
}
```

**Note:** The Google Maps JavaScript API must be loaded with the `places` library. Check if it's already loaded in `layout.tsx`. If not, add a script tag: `https://maps.googleapis.com/maps/api/js?key=GOOGLE_API_KEY&libraries=places`. The API key should come from an environment variable (`NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/google-places-autocomplete.tsx
git commit -m "feat: create GooglePlacesAutocomplete component"
```

---

### Task 15: Create RestaurantDetailsStep component

**Files:**
- Create: `frontend/src/components/onboarding/restaurant-details-step.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/onboarding/restaurant-details-step.tsx`:

```typescript
"use client";

import { useState } from "react";
import { useCreateRestaurant } from "@/hooks/use-create-restaurant";
import { GooglePlacesAutocomplete } from "@/components/google-places-autocomplete";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface RestaurantDetailsStepProps {
  onCreated: (slug: string) => void;
  onBack: () => void;
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function RestaurantDetailsStep({ onCreated, onBack }: RestaurantDetailsStepProps) {
  const createRestaurant = useCreateRestaurant();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState({
    street_address: "",
    city: "",
    state: "",
    zip_code: "",
    country: "US",
    google_place_id: "",
    latitude: null as number | null,
    longitude: null as number | null,
  });
  const [error, setError] = useState<string | null>(null);

  const handleNameChange = (value: string) => {
    setName(value);
    setSlug(slugify(value));
  };

  const handleSubmit = () => {
    if (!name.trim() || !slug.trim()) {
      setError("Restaurant name and slug are required.");
      return;
    }
    setError(null);
    createRestaurant.mutate(
      {
        name: name.trim(),
        slug: slug.trim(),
        phone: phone.trim() || undefined,
        ...address,
      },
      {
        onSuccess: (data) => onCreated(data.slug),
        onError: (err: any) => {
          const message =
            err?.response?.data?.slug?.[0] ??
            err?.response?.data?.detail ??
            "Failed to create restaurant. Please try again.";
          setError(message);
        },
      }
    );
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-1">Restaurant Details</h2>
      <p className="text-sm text-gray-400 mb-6">
        Basic info to get your restaurant set up
      </p>

      {error && (
        <div className="bg-red-900/30 border border-red-700 text-red-400 text-sm rounded-lg px-3 py-2 mb-4">
          {error}
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="text-sm font-medium text-gray-300 mb-1 block">
            Restaurant Name *
          </label>
          <Input
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="e.g. Sakura Sushi"
          />
        </div>

        <div>
          <label className="text-sm font-medium text-gray-300 mb-1 block">
            URL Slug *
          </label>
          <Input
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="e.g. sakura-sushi"
          />
        </div>

        <div>
          <label className="text-sm font-medium text-gray-300 mb-1 block">
            Phone
          </label>
          <Input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="(555) 123-4567"
          />
        </div>

        <div>
          <label className="text-sm font-medium text-gray-300 mb-1 block">
            Address
          </label>
          <GooglePlacesAutocomplete
            onSelect={(components) => setAddress(components)}
          />
        </div>

        {/* Show auto-filled fields if address was selected */}
        {address.city && (
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-2">
            <p className="text-xs text-gray-500 uppercase">Auto-filled from selection</p>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-gray-500 text-xs">Street</span>
                <p className="text-gray-300">{address.street_address}</p>
              </div>
              <div>
                <span className="text-gray-500 text-xs">City</span>
                <p className="text-gray-300">{address.city}</p>
              </div>
              <div>
                <span className="text-gray-500 text-xs">State</span>
                <p className="text-gray-300">{address.state}</p>
              </div>
              <div>
                <span className="text-gray-500 text-xs">ZIP Code</span>
                <p className="text-gray-300">{address.zip_code}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="flex justify-between items-center mt-7">
        <button onClick={onBack} className="text-sm text-gray-500 hover:text-gray-300">
          ← Back
        </button>
        <Button onClick={handleSubmit} disabled={createRestaurant.isPending}>
          {createRestaurant.isPending ? "Creating..." : "Create Restaurant"}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/onboarding/restaurant-details-step.tsx
git commit -m "feat: create RestaurantDetailsStep with Google Places autocomplete"
```

---

### Task 16: Create MenuUploadStep component

**Files:**
- Create: `frontend/src/components/onboarding/menu-upload-step.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/onboarding/menu-upload-step.tsx`:

```typescript
"use client";

import { useState } from "react";
import { MenuUploadModal } from "@/components/menu-upload-modal";
import { Button } from "@/components/ui/button";

interface MenuUploadStepProps {
  slug: string;
  onComplete: () => void;
  onSkip: () => void;
}

export function MenuUploadStep({ slug, onComplete, onSkip }: MenuUploadStepProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [hasUploaded, setHasUploaded] = useState(false);

  return (
    <div className="text-center">
      <h2 className="text-xl font-semibold mb-1">Upload Your Menu</h2>
      <p className="text-sm text-gray-400 mb-8">
        Take photos of your menu and our AI will parse it automatically.
        You can also do this later from your restaurant dashboard.
      </p>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 mb-8">
        <div className="text-4xl mb-4">📸</div>
        <p className="text-gray-300 mb-2">Upload menu photos</p>
        <p className="text-xs text-gray-500 mb-6">
          Supports JPEG, PNG, HEIC — up to 10 photos
        </p>
        <Button onClick={() => setModalOpen(true)}>
          {hasUploaded ? "Upload More Photos" : "Upload Menu Photos"}
        </Button>
      </div>

      <div className="flex justify-between items-center">
        <div />
        {hasUploaded ? (
          <Button onClick={onComplete}>Continue</Button>
        ) : (
          <button onClick={onSkip} className="text-sm text-gray-500 hover:text-gray-300">
            Skip for now →
          </button>
        )}
      </div>

      <MenuUploadModal
        slug={slug}
        open={modalOpen}
        onOpenChange={(open) => {
          setModalOpen(open);
          if (!open) {
            // Modal closed after upload — mark as uploaded so Continue button appears
            setHasUploaded(true);
          }
        }}
        hasExistingMenu={hasUploaded}
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/onboarding/menu-upload-step.tsx
git commit -m "feat: create MenuUploadStep with existing MenuUploadModal integration"
```

---

## Chunk 6: Frontend — Account Menu Link & Google Maps Setup

### Task 17: Add "Complete your profile" link to account menu

**Files:**
- Modify: the header/account dropdown component (find the exact file — likely in `frontend/src/components/` containing the account dropdown or user menu)

- [ ] **Step 1: Find the account menu component**

Search for the component that renders the account dropdown in the header. Look for the `Header` component imported by `ConditionalHeader`. It likely contains a user menu with links to Profile, Orders, Restaurants, etc.

- [ ] **Step 2: Add onboarding link**

Add a link to `/account/onboarding` that renders when `user.onboarding_completed === false`:

```typescript
{user && !user.onboarding_completed && (
  <Link href="/account/onboarding" className="...">
    Complete your profile
  </Link>
)}
```

Place it prominently near the top of the menu items.

- [ ] **Step 3: Test manually**

- Log in as a user with `onboarding_completed = false`
- Verify "Complete your profile" link appears in account menu
- Verify it navigates to `/account/onboarding`
- Set `onboarding_completed = true` in DB, refresh — verify link disappears

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Header.tsx
git commit -m "feat: add 'Complete your profile' link to account menu"
```

---

### Task 18: Add Google Maps Places API script

**Files:**
- Modify: `frontend/src/app/layout.tsx` or create an environment variable

- [ ] **Step 1: Add environment variable**

Add to `.env.local` (do NOT commit this file):

```
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=your-api-key-here
```

- [ ] **Step 2: Load Google Maps script**

In `frontend/src/app/layout.tsx`, add a Script tag for Google Maps Places API (similar to the existing Google GSI and Apple Auth scripts):

```typescript
<Script
  src={`https://maps.googleapis.com/maps/api/js?key=${process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}&libraries=places`}
  strategy="lazyOnload"
/>
```

- [ ] **Step 3: Add TypeScript types for Google Maps**

Run: `cd frontend && npm install -D @types/google.maps`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/layout.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat: add Google Maps Places API script and types"
```

---

## Chunk 7: Backend — Existing User Data Migration

### Task 19: Create data migration for existing users

**Files:**
- Create: new migration in `backend/accounts/migrations/`

- [ ] **Step 1: Create the data migration**

Run: `cd backend && python manage.py makemigrations accounts --empty -n backfill_onboarding_completed`

Edit the generated migration:

```python
from django.db import migrations


def backfill_onboarding_completed(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    # Mark users who have dietary preferences or allergies filled in
    User.objects.exclude(dietary_preferences=[]).update(onboarding_completed=True)
    User.objects.exclude(allergies=[]).update(onboarding_completed=True)
    # Mark users who own restaurants
    from django.db.models import Exists, OuterRef
    Restaurant = apps.get_model("restaurants", "Restaurant")
    User.objects.filter(
        Exists(Restaurant.objects.filter(owner=OuterRef("pk")))
    ).update(onboarding_completed=True)


def reverse(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.update(onboarding_completed=False)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "<previous_migration>"),  # Set to latest accounts migration
        ("restaurants", "<latest_restaurants_migration>"),  # Need Restaurant model
    ]

    operations = [
        migrations.RunPython(backfill_onboarding_completed, reverse),
    ]
```

- [ ] **Step 2: Run the migration**

Run: `cd backend && python manage.py migrate`

- [ ] **Step 3: Verify**

Run: `cd backend && python manage.py shell -c "from accounts.models import User; print(f'Total: {User.objects.count()}, Onboarded: {User.objects.filter(onboarding_completed=True).count()}')""`

- [ ] **Step 4: Commit**

```bash
git add backend/accounts/migrations/
git commit -m "feat: backfill onboarding_completed for existing users with profiles or restaurants"
```

---

## Chunk 8: Integration Testing & Polish

### Task 20: End-to-end manual testing

- [ ] **Step 1: Test customer-only flow**

1. Create a new user account
2. Verify banner appears on all pages
3. Click "Set up now" → navigates to `/account/onboarding`
4. Step 1: Select some dietary preferences, add a custom allergy, pick language → Continue
5. Step 2: Click "No"
6. Verify: onboarding_completed = true in DB, banner gone, account menu link gone
7. Verify: profile page shows the preferences you set

- [ ] **Step 2: Test restaurant owner flow**

1. Create another new user account
2. Navigate to onboarding wizard
3. Step 1: Skip
4. Step 2: Click "Yes"
5. Step 3: Fill in restaurant name (verify slug auto-generates), use Google Places for address
6. Step 4: Click "Upload Menu Photos", upload a test menu image, review parsed menu, save
7. Verify: restaurant created in DB with structured address, menu version created
8. Verify: redirected to restaurant dashboard, banner gone

- [ ] **Step 3: Test dismiss flow**

1. Create another new user account
2. Click X on banner → verify banner disappears
3. Refresh page → verify banner stays dismissed
4. Verify "Complete your profile" still shows in account menu
5. Click it → completes onboarding → verify menu link also disappears

- [ ] **Step 4: Test edge cases**

1. User who already owns a restaurant → Step 2 "Yes" should skip Step 3
2. Close browser mid-wizard → reopen → preferences from Step 1 should be saved
3. Invalid slug (duplicate) → should show inline error on Step 3
4. Google Places unavailable → address input should still work as plain text

- [ ] **Step 5: Fix any issues found**

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "fix: polish onboarding flow based on integration testing"
```
