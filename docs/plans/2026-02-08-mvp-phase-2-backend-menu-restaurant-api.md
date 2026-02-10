# Phase 2: Backend Restaurant & Menu API

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement REST API endpoints for restaurant management (CRUD) and menu management (categories, items, variants, modifiers) with proper authentication and permissions.

**Architecture:** DRF ViewSets with nested routing. Restaurant owners/managers can manage their own restaurants and menus. A public endpoint serves the menu for customer ordering (no auth required).

**Tech Stack:** Django 4.2, DRF, pytest

**Depends on:** Phase 1 (models and auth)

---

## Task 1: Restaurant Permission Class

**Files:**
- Create: `backend/restaurants/permissions.py`
- Create: `backend/restaurants/tests/test_permissions.py`

**Step 1: Write the failing test**

Create `backend/restaurants/tests/test_permissions.py`:

```python
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from restaurants.tests.factories import UserFactory, RestaurantFactory, RestaurantStaffFactory


@pytest.mark.django_db
class TestRestaurantPermissions:
    def test_owner_can_access_own_restaurant(self, api_client):
        owner = UserFactory()
        restaurant = RestaurantFactory(owner=owner)
        api_client.force_authenticate(user=owner)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/")
        assert response.status_code == status.HTTP_200_OK

    def test_non_owner_cannot_access_restaurant(self, api_client):
        owner = UserFactory()
        other = UserFactory()
        restaurant = RestaurantFactory(owner=owner)
        api_client.force_authenticate(user=other)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_staff_manager_can_access_restaurant(self, api_client):
        owner = UserFactory()
        manager = UserFactory()
        restaurant = RestaurantFactory(owner=owner)
        RestaurantStaffFactory(user=manager, restaurant=restaurant, role="manager")
        api_client.force_authenticate(user=manager)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/")
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_cannot_list_restaurants(self, api_client):
        response = api_client.get("/api/restaurants/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

> **Note:** You will need to add `RestaurantStaffFactory` to `backend/restaurants/tests/factories.py`:

```python
class RestaurantStaffFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RestaurantStaff

    user = factory.SubFactory(UserFactory)
    restaurant = factory.SubFactory(RestaurantFactory)
    role = "manager"
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
pytest restaurants/tests/test_permissions.py -v
```

Expected: FAIL (views and URLs don't exist)

**Step 3: Create permissions**

Create `backend/restaurants/permissions.py`:

```python
from rest_framework.permissions import BasePermission
from restaurants.models import RestaurantStaff


class IsRestaurantOwnerOrStaff(BasePermission):
    """
    Allow access if user is the restaurant owner or has a staff role.
    """

    def has_object_permission(self, request, view, obj):
        if obj.owner == request.user:
            return True
        return RestaurantStaff.objects.filter(
            user=request.user, restaurant=obj
        ).exists()
```

**Step 4: Implement will happen in Task 2 (views). Move on.**

---

## Task 2: Restaurant API Endpoints

**Files:**
- Modify: `backend/restaurants/serializers.py`
- Modify: `backend/restaurants/views.py`
- Modify: `backend/restaurants/urls.py`

**Step 1: Add restaurant serializers**

Append to `backend/restaurants/serializers.py`:

```python
from restaurants.models import Restaurant, RestaurantStaff


class RestaurantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = ["id", "name", "slug", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        restaurant = Restaurant.objects.create(**validated_data)
        # Auto-create owner staff record
        RestaurantStaff.objects.create(
            user=self.context["request"].user,
            restaurant=restaurant,
            role="owner",
        )
        return restaurant
```

**Step 2: Add restaurant views**

Append to `backend/restaurants/views.py`:

```python
from rest_framework import generics, permissions
from restaurants.models import Restaurant, RestaurantStaff
from restaurants.serializers import RestaurantSerializer
from restaurants.permissions import IsRestaurantOwnerOrStaff


class MyRestaurantsView(generics.ListAPIView):
    """GET /api/restaurants/me/ - List restaurants I own or have staff access to."""
    serializer_class = RestaurantSerializer

    def get_queryset(self):
        user = self.request.user
        owned = Restaurant.objects.filter(owner=user)
        staff_ids = RestaurantStaff.objects.filter(user=user).values_list(
            "restaurant_id", flat=True
        )
        staffed = Restaurant.objects.filter(id__in=staff_ids)
        return (owned | staffed).distinct()


class CreateRestaurantView(generics.CreateAPIView):
    """POST /api/restaurants/ - Create a new restaurant."""
    serializer_class = RestaurantSerializer


class RestaurantDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/restaurants/:slug/ - View or update a restaurant."""
    serializer_class = RestaurantSerializer
    lookup_field = "slug"

    def get_queryset(self):
        user = self.request.user
        owned = Restaurant.objects.filter(owner=user)
        staff_ids = RestaurantStaff.objects.filter(user=user).values_list(
            "restaurant_id", flat=True
        )
        staffed = Restaurant.objects.filter(id__in=staff_ids)
        return (owned | staffed).distinct()
```

**Step 3: Update URLs**

Replace `backend/restaurants/urls.py`:

```python
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from restaurants.views import (
    RegisterView, LoginView,
    MyRestaurantsView, CreateRestaurantView, RestaurantDetailView,
)

urlpatterns = [
    # Auth
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Restaurants
    path("restaurants/me/", MyRestaurantsView.as_view(), name="my-restaurants"),
    path("restaurants/", CreateRestaurantView.as_view(), name="create-restaurant"),
    path("restaurants/<slug:slug>/", RestaurantDetailView.as_view(), name="restaurant-detail"),
]
```

**Step 4: Run permission tests**

```bash
cd backend
pytest restaurants/tests/test_permissions.py -v
```

Expected: All 4 tests PASS.

**Step 5: Write additional restaurant API tests**

Create `backend/restaurants/tests/test_api_restaurants.py`:

```python
import pytest
from rest_framework import status
from restaurants.tests.factories import UserFactory, RestaurantFactory


@pytest.mark.django_db
class TestCreateRestaurant:
    def test_create_restaurant(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/restaurants/",
            {"name": "My Pizza Place", "slug": "my-pizza-place"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "My Pizza Place"
        assert response.data["slug"] == "my-pizza-place"

    def test_create_restaurant_rejects_duplicate_slug(self, api_client):
        RestaurantFactory(slug="taken")
        user = UserFactory()
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/restaurants/",
            {"name": "Another", "slug": "taken"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestMyRestaurants:
    def test_list_own_restaurants(self, api_client):
        user = UserFactory()
        RestaurantFactory(owner=user)
        RestaurantFactory(owner=user)
        RestaurantFactory()  # Someone else's
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/restaurants/me/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2


@pytest.mark.django_db
class TestUpdateRestaurant:
    def test_owner_can_update_name(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        api_client.force_authenticate(user=user)
        response = api_client.patch(
            f"/api/restaurants/{restaurant.slug}/",
            {"name": "New Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "New Name"
```

**Step 6: Run tests**

```bash
cd backend
pytest restaurants/tests/test_api_restaurants.py -v
```

Expected: All tests PASS.

**Step 7: Commit**

```bash
git add backend/restaurants/
git commit -m "feat: add restaurant CRUD API with owner/staff permissions"
```

---

## Task 3: Menu Management API - Categories

**Files:**
- Modify: `backend/restaurants/serializers.py`
- Modify: `backend/restaurants/views.py`
- Modify: `backend/restaurants/urls.py`
- Create: `backend/restaurants/tests/test_api_menu.py`

**Step 1: Write the failing tests**

Create `backend/restaurants/tests/test_api_menu.py`:

```python
import pytest
from rest_framework import status
from restaurants.tests.factories import (
    UserFactory, RestaurantFactory, MenuCategoryFactory,
)


@pytest.mark.django_db
class TestMenuCategoryAPI:
    @pytest.fixture
    def owner_and_restaurant(self):
        owner = UserFactory()
        restaurant = RestaurantFactory(owner=owner)
        return owner, restaurant

    def test_create_category(self, api_client, owner_and_restaurant):
        owner, restaurant = owner_and_restaurant
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/categories/",
            {"name": "Appetizers", "sort_order": 1},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Appetizers"

    def test_update_category(self, api_client, owner_and_restaurant):
        owner, restaurant = owner_and_restaurant
        cat = MenuCategoryFactory(restaurant=restaurant, name="Old Name")
        api_client.force_authenticate(user=owner)
        response = api_client.patch(
            f"/api/restaurants/{restaurant.slug}/categories/{cat.id}/",
            {"name": "New Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "New Name"

    def test_non_owner_cannot_create_category(self, api_client, owner_and_restaurant):
        _, restaurant = owner_and_restaurant
        other = UserFactory()
        api_client.force_authenticate(user=other)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/categories/",
            {"name": "Hack", "sort_order": 1},
            format="json",
        )
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
pytest restaurants/tests/test_api_menu.py -v
```

Expected: FAIL

**Step 3: Add category serializer**

Append to `backend/restaurants/serializers.py`:

```python
from restaurants.models import MenuCategory, MenuItem, MenuItemVariant, MenuItemModifier


class MenuCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuCategory
        fields = ["id", "name", "sort_order", "is_active"]
```

**Step 4: Add category views**

Append to `backend/restaurants/views.py`:

```python
from restaurants.models import MenuCategory
from restaurants.serializers import MenuCategorySerializer


class RestaurantMixin:
    """Mixin to resolve restaurant from URL slug and check access."""

    def get_restaurant(self):
        slug = self.kwargs["slug"]
        user = self.request.user
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Restaurant not found.")

        is_owner = restaurant.owner == user
        is_staff = RestaurantStaff.objects.filter(
            user=user, restaurant=restaurant
        ).exists()
        if not is_owner and not is_staff:
            from rest_framework.exceptions import NotFound
            raise NotFound("Restaurant not found.")

        return restaurant


class MenuCategoryListCreateView(RestaurantMixin, generics.ListCreateAPIView):
    serializer_class = MenuCategorySerializer

    def get_queryset(self):
        restaurant = self.get_restaurant()
        return MenuCategory.objects.filter(restaurant=restaurant)

    def perform_create(self, serializer):
        restaurant = self.get_restaurant()
        serializer.save(restaurant=restaurant)


class MenuCategoryDetailView(RestaurantMixin, generics.RetrieveUpdateAPIView):
    serializer_class = MenuCategorySerializer
    lookup_field = "pk"

    def get_queryset(self):
        restaurant = self.get_restaurant()
        return MenuCategory.objects.filter(restaurant=restaurant)
```

**Step 5: Add URLs**

Add to `backend/restaurants/urls.py`:

```python
from restaurants.views import MenuCategoryListCreateView, MenuCategoryDetailView

# Add to urlpatterns:
    path(
        "restaurants/<slug:slug>/categories/",
        MenuCategoryListCreateView.as_view(),
        name="menu-categories",
    ),
    path(
        "restaurants/<slug:slug>/categories/<int:pk>/",
        MenuCategoryDetailView.as_view(),
        name="menu-category-detail",
    ),
```

**Step 6: Run tests**

```bash
cd backend
pytest restaurants/tests/test_api_menu.py -v
```

Expected: All PASS.

**Step 7: Commit**

```bash
git add backend/restaurants/
git commit -m "feat: add menu category API endpoints"
```

---

## Task 4: Menu Management API - Items, Variants, Modifiers

**Files:**
- Modify: `backend/restaurants/serializers.py`
- Modify: `backend/restaurants/views.py`
- Modify: `backend/restaurants/urls.py`
- Modify: `backend/restaurants/tests/test_api_menu.py`

**Step 1: Write failing tests**

Append to `backend/restaurants/tests/test_api_menu.py`:

```python
from decimal import Decimal
from restaurants.tests.factories import (
    MenuItemFactory, MenuItemVariantFactory, MenuItemModifierFactory,
)


@pytest.mark.django_db
class TestMenuItemAPI:
    @pytest.fixture
    def setup(self):
        owner = UserFactory()
        restaurant = RestaurantFactory(owner=owner)
        category = MenuCategoryFactory(restaurant=restaurant)
        return owner, restaurant, category

    def test_create_item_with_variants_and_modifiers(self, api_client, setup):
        owner, restaurant, category = setup
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/items/",
            {
                "category_id": category.id,
                "name": "Pepperoni Pizza",
                "description": "Classic pepperoni",
                "sort_order": 1,
                "variants": [
                    {"label": "Small", "price": "10.99", "is_default": True},
                    {"label": "Large", "price": "14.99", "is_default": False},
                ],
                "modifiers": [
                    {"name": "Extra Cheese", "price_adjustment": "2.00"},
                    {"name": "No Olives", "price_adjustment": "0.00"},
                ],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Pepperoni Pizza"
        assert len(response.data["variants"]) == 2
        assert len(response.data["modifiers"]) == 2

    def test_update_item(self, api_client, setup):
        owner, restaurant, category = setup
        item = MenuItemFactory(category=category, name="Old Name")
        api_client.force_authenticate(user=owner)
        response = api_client.patch(
            f"/api/restaurants/{restaurant.slug}/items/{item.id}/",
            {"name": "New Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "New Name"

    def test_deactivate_item(self, api_client, setup):
        owner, restaurant, category = setup
        item = MenuItemFactory(category=category)
        api_client.force_authenticate(user=owner)
        response = api_client.delete(
            f"/api/restaurants/{restaurant.slug}/items/{item.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        assert item.is_active is False
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
pytest restaurants/tests/test_api_menu.py::TestMenuItemAPI -v
```

Expected: FAIL

**Step 3: Add item serializers**

Append to `backend/restaurants/serializers.py`:

```python
class MenuItemModifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItemModifier
        fields = ["id", "name", "price_adjustment"]


class MenuItemVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItemVariant
        fields = ["id", "label", "price", "is_default"]


class MenuItemSerializer(serializers.ModelSerializer):
    variants = MenuItemVariantSerializer(many=True, required=False)
    modifiers = MenuItemModifierSerializer(many=True, required=False)
    category_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = MenuItem
        fields = [
            "id", "category_id", "name", "description", "image_url",
            "is_active", "sort_order", "variants", "modifiers",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        variants_data = validated_data.pop("variants", [])
        modifiers_data = validated_data.pop("modifiers", [])
        category_id = validated_data.pop("category_id")

        # Verify category belongs to the restaurant
        restaurant = self.context["restaurant"]
        try:
            category = MenuCategory.objects.get(id=category_id, restaurant=restaurant)
        except MenuCategory.DoesNotExist:
            raise serializers.ValidationError({"category_id": "Invalid category."})

        item = MenuItem.objects.create(category=category, **validated_data)

        for variant_data in variants_data:
            MenuItemVariant.objects.create(menu_item=item, **variant_data)
        for modifier_data in modifiers_data:
            MenuItemModifier.objects.create(menu_item=item, **modifier_data)

        return item

    def update(self, instance, validated_data):
        # For simplicity, variants/modifiers are not updated inline on PATCH.
        # They can be managed separately in a future iteration.
        validated_data.pop("variants", None)
        validated_data.pop("modifiers", None)
        validated_data.pop("category_id", None)
        return super().update(instance, validated_data)
```

**Step 4: Add item views**

Append to `backend/restaurants/views.py`:

```python
from restaurants.models import MenuItem
from restaurants.serializers import MenuItemSerializer


class MenuItemListCreateView(RestaurantMixin, generics.ListCreateAPIView):
    serializer_class = MenuItemSerializer

    def get_queryset(self):
        restaurant = self.get_restaurant()
        return MenuItem.objects.filter(
            category__restaurant=restaurant
        ).prefetch_related("variants", "modifiers")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["restaurant"] = self.get_restaurant()
        return ctx

    def perform_create(self, serializer):
        serializer.save()


class MenuItemDetailView(RestaurantMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MenuItemSerializer
    lookup_field = "pk"

    def get_queryset(self):
        restaurant = self.get_restaurant()
        return MenuItem.objects.filter(
            category__restaurant=restaurant
        ).prefetch_related("variants", "modifiers")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["restaurant"] = self.get_restaurant()
        return ctx

    def perform_destroy(self, instance):
        """Soft-delete: deactivate instead of deleting."""
        instance.is_active = False
        instance.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"status": "deactivated", "id": instance.id},
            status=status.HTTP_200_OK,
        )
```

**Step 5: Add URLs**

Add to `backend/restaurants/urls.py`:

```python
from restaurants.views import MenuItemListCreateView, MenuItemDetailView

# Add to urlpatterns:
    path(
        "restaurants/<slug:slug>/items/",
        MenuItemListCreateView.as_view(),
        name="menu-items",
    ),
    path(
        "restaurants/<slug:slug>/items/<int:pk>/",
        MenuItemDetailView.as_view(),
        name="menu-item-detail",
    ),
```

**Step 6: Run tests**

```bash
cd backend
pytest restaurants/tests/test_api_menu.py -v
```

Expected: All tests PASS.

**Step 7: Commit**

```bash
git add backend/restaurants/
git commit -m "feat: add menu item CRUD API with variants and modifiers"
```

---

## Task 5: Public Menu Endpoint (for customers)

**Files:**
- Modify: `backend/restaurants/serializers.py`
- Modify: `backend/orders/views.py` (or create)
- Modify: `backend/orders/urls.py`
- Create: `backend/orders/tests/test_api_menu_public.py`

**Step 1: Write the failing test**

Create `backend/orders/tests/test_api_menu_public.py`:

```python
import pytest
from rest_framework import status
from restaurants.tests.factories import (
    RestaurantFactory, MenuCategoryFactory, MenuItemFactory,
    MenuItemVariantFactory, MenuItemModifierFactory,
)


@pytest.mark.django_db
class TestPublicMenu:
    def test_get_menu_no_auth_required(self, api_client):
        restaurant = RestaurantFactory(slug="public-test")
        cat = MenuCategoryFactory(restaurant=restaurant, name="Mains")
        item = MenuItemFactory(category=cat, name="Burger")
        MenuItemVariantFactory(menu_item=item, label="Regular", price="10.99")
        MenuItemModifierFactory(menu_item=item, name="Extra Cheese")

        response = api_client.get("/api/order/public-test/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["categories"]) == 1
        assert response.data["categories"][0]["name"] == "Mains"
        assert len(response.data["categories"][0]["items"]) == 1

    def test_inactive_items_excluded(self, api_client):
        restaurant = RestaurantFactory(slug="inactive-test")
        cat = MenuCategoryFactory(restaurant=restaurant)
        MenuItemFactory(category=cat, is_active=True)
        MenuItemFactory(category=cat, is_active=False)

        response = api_client.get("/api/order/inactive-test/menu/")
        assert len(response.data["categories"][0]["items"]) == 1

    def test_nonexistent_restaurant_returns_404(self, api_client):
        response = api_client.get("/api/order/nonexistent/menu/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
pytest orders/tests/test_api_menu_public.py -v
```

Expected: FAIL

**Step 3: Add public menu serializer**

Append to `backend/restaurants/serializers.py`:

```python
class PublicMenuItemSerializer(serializers.ModelSerializer):
    variants = MenuItemVariantSerializer(many=True, read_only=True)
    modifiers = MenuItemModifierSerializer(many=True, read_only=True)

    class Meta:
        model = MenuItem
        fields = ["id", "name", "description", "image_url", "variants", "modifiers"]


class PublicMenuCategorySerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    class Meta:
        model = MenuCategory
        fields = ["id", "name", "items"]

    def get_items(self, obj):
        active_items = obj.items.filter(is_active=True).prefetch_related(
            "variants", "modifiers"
        )
        return PublicMenuItemSerializer(active_items, many=True).data


class PublicMenuSerializer(serializers.Serializer):
    restaurant_name = serializers.CharField()
    categories = PublicMenuCategorySerializer(many=True)
```

**Step 4: Add public menu view**

Replace `backend/orders/views.py`:

```python
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.models import Restaurant, MenuCategory
from restaurants.serializers import PublicMenuCategorySerializer


class PublicMenuView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            return Response(
                {"detail": "Restaurant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        categories = (
            MenuCategory.objects.filter(restaurant=restaurant, is_active=True)
            .prefetch_related("items__variants", "items__modifiers")
            .order_by("sort_order")
        )

        return Response(
            {
                "restaurant_name": restaurant.name,
                "categories": PublicMenuCategorySerializer(categories, many=True).data,
            }
        )
```

**Step 5: Add URL**

Replace `backend/orders/urls.py`:

```python
from django.urls import path
from orders.views import PublicMenuView

urlpatterns = [
    path("order/<slug:slug>/menu/", PublicMenuView.as_view(), name="public-menu"),
]
```

**Step 6: Run tests**

```bash
cd backend
pytest orders/tests/test_api_menu_public.py -v
```

Expected: All PASS.

**Step 7: Run full test suite**

```bash
cd backend
pytest -v
```

Expected: All tests PASS.

**Step 8: Commit**

```bash
git add backend/
git commit -m "feat: add public menu endpoint for customer ordering"
```

---

## Task 6: Full Menu Endpoint (for admin)

**Files:**
- Modify: `backend/restaurants/views.py`
- Modify: `backend/restaurants/urls.py`
- Modify: `backend/restaurants/tests/test_api_menu.py`

**Step 1: Write the failing test**

Append to `backend/restaurants/tests/test_api_menu.py`:

```python
@pytest.mark.django_db
class TestFullMenuAPI:
    def test_get_full_menu_includes_inactive(self, api_client):
        owner = UserFactory()
        restaurant = RestaurantFactory(owner=owner)
        cat = MenuCategoryFactory(restaurant=restaurant)
        MenuItemFactory(category=cat, is_active=True)
        MenuItemFactory(category=cat, is_active=False)

        api_client.force_authenticate(user=owner)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/menu/")
        assert response.status_code == status.HTTP_200_OK
        # Admin view includes all items (active and inactive)
        total_items = sum(
            len(cat["items"]) for cat in response.data["categories"]
        )
        assert total_items == 2
```

**Step 2: Run test to verify it fails**

```bash
cd backend
pytest restaurants/tests/test_api_menu.py::TestFullMenuAPI -v
```

Expected: FAIL

**Step 3: Add admin full menu view**

Append to `backend/restaurants/views.py`:

```python
from restaurants.serializers import PublicMenuCategorySerializer


class FullMenuView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/menu/ - Full menu including inactive items."""

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        categories = (
            MenuCategory.objects.filter(restaurant=restaurant)
            .prefetch_related("items__variants", "items__modifiers")
            .order_by("sort_order")
        )
        # Use a version that includes inactive items
        data = []
        for cat in categories:
            cat_data = {
                "id": cat.id,
                "name": cat.name,
                "sort_order": cat.sort_order,
                "is_active": cat.is_active,
                "items": MenuItemSerializer(
                    cat.items.prefetch_related("variants", "modifiers"),
                    many=True,
                ).data,
            }
            data.append(cat_data)

        return Response({"restaurant_name": restaurant.name, "categories": data})
```

**Step 4: Add URL**

Add to `backend/restaurants/urls.py`:

```python
from restaurants.views import FullMenuView

# Add to urlpatterns:
    path(
        "restaurants/<slug:slug>/menu/",
        FullMenuView.as_view(),
        name="full-menu",
    ),
```

**Step 5: Run tests**

```bash
cd backend
pytest restaurants/tests/test_api_menu.py -v
```

Expected: All PASS.

**Step 6: Commit**

```bash
git add backend/restaurants/
git commit -m "feat: add full menu admin endpoint (includes inactive items)"
```
