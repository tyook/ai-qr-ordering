# Phase 1: Backend Models & Authentication

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement all Django data models from the MVP design and JWT authentication (register, login, refresh).

**Architecture:** Custom User model extending AbstractUser with UUID pk and role field. Restaurant/Menu/Order models per the design doc ERD. JWT auth via djangorestframework-simplejwt.

**Tech Stack:** Django 4.2, DRF, simplejwt, pytest, factory-boy

**Depends on:** Phase 0 (scaffolding complete)

---

## Task 1: Custom User Model

**Files:**
- Modify: `backend/restaurants/models.py`
- Create: `backend/restaurants/tests/test_models.py`
- Create: `backend/restaurants/tests/__init__.py`

**Step 1: Create test directory**

```bash
mkdir -p backend/restaurants/tests
touch backend/restaurants/tests/__init__.py
```

**Step 2: Write the failing test**

Create `backend/restaurants/tests/test_models.py`:

```python
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_with_email(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        assert user.email == "test@example.com"
        assert user.check_password("testpass123")
        assert user.role == "owner"

    def test_user_has_uuid_pk(self):
        import uuid
        user = User.objects.create_user(
            email="uuid@example.com",
            password="testpass123",
        )
        assert isinstance(user.id, uuid.UUID)

    def test_user_str(self):
        user = User.objects.create_user(
            email="str@example.com",
            password="testpass123",
        )
        assert str(user) == "str@example.com"
```

**Step 3: Run test to verify it fails**

```bash
cd backend
pytest restaurants/tests/test_models.py -v
```

Expected: FAIL (model not implemented yet)

**Step 4: Implement User model**

Replace `backend/restaurants/models.py`:

```python
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff"
        ADMIN = "admin", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.OWNER)
    phone = models.CharField(max_length=20, blank=True, default="")

    username = None  # Remove username field
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    def __str__(self):
        return self.email
```

Also create `backend/restaurants/managers.py`:

```python
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
        extra_fields.setdefault("role", "admin")
        return self.create_user(email, password, **extra_fields)
```

Add to User model in `restaurants/models.py`:

```python
from restaurants.managers import UserManager

# Add inside User class:
    objects = UserManager()
```

**Step 5: Run migrations**

```bash
cd backend
python manage.py makemigrations restaurants
python manage.py migrate
```

**Step 6: Run test to verify it passes**

```bash
cd backend
pytest restaurants/tests/test_models.py -v
```

Expected: All 3 tests PASS.

**Step 7: Commit**

```bash
git add backend/restaurants/
git commit -m "feat: add custom User model with UUID pk and role field"
```

---

## Task 2: Restaurant & Staff Models

**Files:**
- Modify: `backend/restaurants/models.py`
- Modify: `backend/restaurants/tests/test_models.py`

**Step 1: Write the failing tests**

Append to `backend/restaurants/tests/test_models.py`:

```python
from restaurants.models import Restaurant, RestaurantStaff


@pytest.mark.django_db
class TestRestaurantModel:
    def test_create_restaurant(self):
        owner = User.objects.create_user(
            email="owner@example.com", password="testpass123"
        )
        restaurant = Restaurant.objects.create(
            name="Test Restaurant",
            slug="test-restaurant",
            owner=owner,
        )
        assert restaurant.name == "Test Restaurant"
        assert restaurant.slug == "test-restaurant"
        assert restaurant.owner == owner

    def test_restaurant_str(self):
        owner = User.objects.create_user(
            email="owner2@example.com", password="testpass123"
        )
        restaurant = Restaurant.objects.create(
            name="My Place", slug="my-place", owner=owner
        )
        assert str(restaurant) == "My Place"

    def test_slug_is_unique(self):
        owner = User.objects.create_user(
            email="owner3@example.com", password="testpass123"
        )
        Restaurant.objects.create(name="R1", slug="same-slug", owner=owner)
        with pytest.raises(Exception):
            Restaurant.objects.create(name="R2", slug="same-slug", owner=owner)


@pytest.mark.django_db
class TestRestaurantStaffModel:
    def test_create_staff(self):
        owner = User.objects.create_user(
            email="staffowner@example.com", password="testpass123"
        )
        restaurant = Restaurant.objects.create(
            name="Staff Test", slug="staff-test", owner=owner
        )
        staff_user = User.objects.create_user(
            email="kitchen@example.com", password="testpass123", role="staff"
        )
        staff = RestaurantStaff.objects.create(
            user=staff_user, restaurant=restaurant, role="kitchen"
        )
        assert staff.role == "kitchen"
        assert staff.restaurant == restaurant
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
pytest restaurants/tests/test_models.py -v
```

Expected: FAIL (Restaurant, RestaurantStaff not defined)

**Step 3: Implement models**

Append to `backend/restaurants/models.py`:

```python
class Restaurant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=100)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_restaurants")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class RestaurantStaff(models.Model):
    class StaffRole(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        KITCHEN = "kitchen", "Kitchen"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="staff_roles")
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="staff")
    role = models.CharField(max_length=10, choices=StaffRole.choices)
    invited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "restaurant")

    def __str__(self):
        return f"{self.user.email} @ {self.restaurant.name} ({self.role})"
```

**Step 4: Migrate and test**

```bash
cd backend
python manage.py makemigrations restaurants
python manage.py migrate
pytest restaurants/tests/test_models.py -v
```

Expected: All tests PASS.

**Step 5: Commit**

```bash
git add backend/restaurants/
git commit -m "feat: add Restaurant and RestaurantStaff models"
```

---

## Task 3: Menu Models (Category, Item, Variant, Modifier)

**Files:**
- Modify: `backend/restaurants/models.py`
- Modify: `backend/restaurants/tests/test_models.py`

**Step 1: Write the failing tests**

Append to `backend/restaurants/tests/test_models.py`:

```python
from restaurants.models import MenuCategory, MenuItem, MenuItemVariant, MenuItemModifier
from decimal import Decimal


@pytest.mark.django_db
class TestMenuModels:
    @pytest.fixture
    def restaurant(self):
        owner = User.objects.create_user(
            email="menuowner@example.com", password="testpass123"
        )
        return Restaurant.objects.create(
            name="Menu Test", slug="menu-test", owner=owner
        )

    def test_create_category(self, restaurant):
        cat = MenuCategory.objects.create(
            restaurant=restaurant, name="Pizzas", sort_order=1
        )
        assert cat.name == "Pizzas"
        assert cat.is_active is True

    def test_create_item_with_variant_and_modifier(self, restaurant):
        cat = MenuCategory.objects.create(
            restaurant=restaurant, name="Pizzas", sort_order=1
        )
        item = MenuItem.objects.create(
            category=cat, name="Margherita", description="Classic pizza", sort_order=1
        )
        variant = MenuItemVariant.objects.create(
            menu_item=item, label="Large", price=Decimal("14.99"), is_default=True
        )
        modifier = MenuItemModifier.objects.create(
            menu_item=item, name="Extra Cheese", price_adjustment=Decimal("2.00")
        )
        assert item.variants.count() == 1
        assert item.modifiers.count() == 1
        assert variant.price == Decimal("14.99")
        assert modifier.price_adjustment == Decimal("2.00")

    def test_item_belongs_to_restaurant_via_category(self, restaurant):
        cat = MenuCategory.objects.create(
            restaurant=restaurant, name="Drinks", sort_order=2
        )
        item = MenuItem.objects.create(
            category=cat, name="Coke", description="", sort_order=1
        )
        assert item.category.restaurant == restaurant
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
pytest restaurants/tests/test_models.py::TestMenuModels -v
```

Expected: FAIL (models not defined)

**Step 3: Implement menu models**

Append to `backend/restaurants/models.py`:

```python
class MenuCategory(models.Model):
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=100)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order"]
        verbose_name_plural = "menu categories"

    def __str__(self):
        return f"{self.restaurant.name} - {self.name}"


class MenuItem(models.Model):
    category = models.ForeignKey(
        MenuCategory, on_delete=models.CASCADE, related_name="items"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    image_url = models.URLField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.name


class MenuItemVariant(models.Model):
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, related_name="variants"
    )
    label = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.menu_item.name} - {self.label} (${self.price})"


class MenuItemModifier(models.Model):
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, related_name="modifiers"
    )
    name = models.CharField(max_length=100)
    price_adjustment = models.DecimalField(
        max_digits=8, decimal_places=2, default=0
    )

    def __str__(self):
        return f"{self.menu_item.name} + {self.name} (${self.price_adjustment})"
```

**Step 4: Migrate and test**

```bash
cd backend
python manage.py makemigrations restaurants
python manage.py migrate
pytest restaurants/tests/test_models.py -v
```

Expected: All tests PASS.

**Step 5: Commit**

```bash
git add backend/restaurants/
git commit -m "feat: add MenuCategory, MenuItem, MenuItemVariant, and MenuItemModifier models"
```

---

## Task 4: Order Models

**Files:**
- Modify: `backend/orders/models.py`
- Create: `backend/orders/tests/__init__.py`
- Create: `backend/orders/tests/test_models.py`

**Step 1: Create test directory**

```bash
mkdir -p backend/orders/tests
touch backend/orders/tests/__init__.py
```

**Step 2: Write the failing tests**

Create `backend/orders/tests/test_models.py`:

```python
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model

from orders.models import Order, OrderItem
from restaurants.models import (
    Restaurant, MenuCategory, MenuItem, MenuItemVariant, MenuItemModifier,
)

User = get_user_model()


@pytest.mark.django_db
class TestOrderModel:
    @pytest.fixture
    def menu_setup(self):
        owner = User.objects.create_user(
            email="orderowner@example.com", password="testpass123"
        )
        restaurant = Restaurant.objects.create(
            name="Order Test", slug="order-test", owner=owner
        )
        category = MenuCategory.objects.create(
            restaurant=restaurant, name="Mains", sort_order=1
        )
        item = MenuItem.objects.create(
            category=category, name="Burger", description="Beef burger", sort_order=1
        )
        variant = MenuItemVariant.objects.create(
            menu_item=item, label="Regular", price=Decimal("12.99"), is_default=True
        )
        modifier = MenuItemModifier.objects.create(
            menu_item=item, name="Extra Bacon", price_adjustment=Decimal("2.00")
        )
        return {
            "restaurant": restaurant,
            "item": item,
            "variant": variant,
            "modifier": modifier,
        }

    def test_create_order(self, menu_setup):
        order = Order.objects.create(
            restaurant=menu_setup["restaurant"],
            table_identifier="5",
            status="pending",
            raw_input="I want a burger with extra bacon",
            parsed_json={"items": []},
            language_detected="en",
            total_price=Decimal("14.99"),
        )
        assert order.status == "pending"
        assert str(order.id)  # UUID is set

    def test_create_order_item_with_modifiers(self, menu_setup):
        order = Order.objects.create(
            restaurant=menu_setup["restaurant"],
            raw_input="burger with bacon",
            parsed_json={},
            total_price=Decimal("14.99"),
        )
        order_item = OrderItem.objects.create(
            order=order,
            menu_item=menu_setup["item"],
            variant=menu_setup["variant"],
            quantity=1,
        )
        order_item.modifiers.add(menu_setup["modifier"])
        assert order_item.modifiers.count() == 1
        assert order_item.variant.price == Decimal("12.99")

    def test_order_status_choices(self, menu_setup):
        order = Order.objects.create(
            restaurant=menu_setup["restaurant"],
            raw_input="test",
            parsed_json={},
            total_price=Decimal("0"),
        )
        for status in ["pending", "confirmed", "preparing", "ready", "completed"]:
            order.status = status
            order.full_clean()  # Should not raise
```

**Step 3: Run tests to verify they fail**

```bash
cd backend
pytest orders/tests/test_models.py -v
```

Expected: FAIL (Order, OrderItem not defined)

**Step 4: Implement Order models**

Replace `backend/orders/models.py`:

```python
import uuid
from django.db import models
from restaurants.models import Restaurant, MenuItem, MenuItemVariant, MenuItemModifier


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="orders"
    )
    table_identifier = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    raw_input = models.TextField()
    parsed_json = models.JSONField(default=dict)
    language_detected = models.CharField(max_length=10, blank=True, default="")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        table = f" (Table {self.table_identifier})" if self.table_identifier else ""
        return f"Order {self.id}{table} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT)
    variant = models.ForeignKey(MenuItemVariant, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    special_requests = models.TextField(blank=True, default="")
    modifiers = models.ManyToManyField(MenuItemModifier, blank=True)

    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name} ({self.variant.label})"
```

**Step 5: Migrate and test**

```bash
cd backend
python manage.py makemigrations orders
python manage.py migrate
pytest orders/tests/test_models.py -v
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
git add backend/orders/
git commit -m "feat: add Order and OrderItem models with status workflow"
```

---

## Task 5: Test Factories

**Files:**
- Create: `backend/restaurants/tests/factories.py`
- Create: `backend/orders/tests/factories.py`

**Step 1: Create restaurant factories**

Create `backend/restaurants/tests/factories.py`:

```python
import factory
from django.contrib.auth import get_user_model
from restaurants.models import (
    Restaurant, RestaurantStaff, MenuCategory, MenuItem,
    MenuItemVariant, MenuItemModifier,
)

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


class RestaurantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Restaurant

    name = factory.Sequence(lambda n: f"Restaurant {n}")
    slug = factory.Sequence(lambda n: f"restaurant-{n}")
    owner = factory.SubFactory(UserFactory)


class MenuCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MenuCategory

    restaurant = factory.SubFactory(RestaurantFactory)
    name = factory.Sequence(lambda n: f"Category {n}")
    sort_order = factory.Sequence(lambda n: n)


class MenuItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MenuItem

    category = factory.SubFactory(MenuCategoryFactory)
    name = factory.Sequence(lambda n: f"Item {n}")
    description = "A test menu item"
    sort_order = factory.Sequence(lambda n: n)


class MenuItemVariantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MenuItemVariant

    menu_item = factory.SubFactory(MenuItemFactory)
    label = "Regular"
    price = factory.Faker("pydecimal", left_digits=2, right_digits=2, positive=True)
    is_default = True


class MenuItemModifierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MenuItemModifier

    menu_item = factory.SubFactory(MenuItemFactory)
    name = factory.Sequence(lambda n: f"Modifier {n}")
    price_adjustment = factory.Faker(
        "pydecimal", left_digits=1, right_digits=2, positive=True
    )
```

**Step 2: Create order factories**

Create `backend/orders/tests/factories.py`:

```python
import factory
from orders.models import Order, OrderItem
from restaurants.tests.factories import (
    RestaurantFactory, MenuItemFactory, MenuItemVariantFactory,
)


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    restaurant = factory.SubFactory(RestaurantFactory)
    raw_input = "Test order input"
    parsed_json = factory.LazyFunction(dict)
    total_price = factory.Faker(
        "pydecimal", left_digits=2, right_digits=2, positive=True
    )


class OrderItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrderItem

    order = factory.SubFactory(OrderFactory)
    menu_item = factory.SubFactory(MenuItemFactory)
    variant = factory.SubFactory(MenuItemVariantFactory)
    quantity = 1
```

**Step 3: Verify factories work**

Add a quick test to `backend/restaurants/tests/test_models.py`:

```python
from restaurants.tests.factories import (
    UserFactory, RestaurantFactory, MenuCategoryFactory,
    MenuItemFactory, MenuItemVariantFactory, MenuItemModifierFactory,
)


@pytest.mark.django_db
class TestFactories:
    def test_user_factory(self):
        user = UserFactory()
        assert user.email
        assert user.check_password("testpass123")

    def test_full_menu_factory_chain(self):
        variant = MenuItemVariantFactory()
        assert variant.menu_item.category.restaurant.owner.email
```

**Step 4: Run all tests**

```bash
cd backend
pytest -v
```

Expected: All tests PASS.

**Step 5: Commit**

```bash
git add backend/
git commit -m "feat: add factory-boy factories for all models"
```

---

## Task 6: JWT Authentication Endpoints

**Files:**
- Create: `backend/restaurants/serializers.py`
- Create: `backend/restaurants/views.py` (replace default)
- Modify: `backend/restaurants/urls.py`
- Create: `backend/restaurants/tests/test_auth.py`

**Step 1: Write the failing tests**

Create `backend/restaurants/tests/test_auth.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

User = get_user_model()


@pytest.mark.django_db
class TestRegister:
    def test_register_creates_user(self, api_client):
        response = api_client.post(
            "/api/auth/register/",
            {
                "email": "new@example.com",
                "password": "strongpass123",
                "first_name": "New",
                "last_name": "User",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert "access" in response.data
        assert "refresh" in response.data
        assert User.objects.filter(email="new@example.com").exists()

    def test_register_rejects_duplicate_email(self, api_client):
        User.objects.create_user(email="dup@example.com", password="testpass123")
        response = api_client.post(
            "/api/auth/register/",
            {
                "email": "dup@example.com",
                "password": "strongpass123",
                "first_name": "Dup",
                "last_name": "User",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_rejects_weak_password(self, api_client):
        response = api_client.post(
            "/api/auth/register/",
            {
                "email": "weak@example.com",
                "password": "123",
                "first_name": "Weak",
                "last_name": "Pass",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLogin:
    def test_login_returns_tokens(self, api_client):
        User.objects.create_user(email="login@example.com", password="testpass123")
        response = api_client.post(
            "/api/auth/login/",
            {"email": "login@example.com", "password": "testpass123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_login_rejects_wrong_password(self, api_client):
        User.objects.create_user(email="wrong@example.com", password="testpass123")
        response = api_client.post(
            "/api/auth/login/",
            {"email": "wrong@example.com", "password": "wrongpass"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTokenRefresh:
    def test_refresh_returns_new_access_token(self, api_client):
        User.objects.create_user(email="refresh@example.com", password="testpass123")
        login = api_client.post(
            "/api/auth/login/",
            {"email": "refresh@example.com", "password": "testpass123"},
            format="json",
        )
        refresh_token = login.data["refresh"]
        response = api_client.post(
            "/api/auth/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
pytest restaurants/tests/test_auth.py -v
```

Expected: FAIL (URLs not configured, serializers not defined)

**Step 3: Create serializers**

Create `backend/restaurants/serializers.py`:

```python
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["email", "password", "first_name", "last_name"]

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

    def to_representation(self, instance):
        refresh = RefreshToken.for_user(instance)
        return {
            "user": {
                "id": str(instance.id),
                "email": instance.email,
                "first_name": instance.first_name,
                "last_name": instance.last_name,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = User.objects.filter(email=data["email"]).first()
        if not user or not user.check_password(data["password"]):
            raise serializers.ValidationError("Invalid email or password.")
        data["user"] = user
        return data
```

**Step 4: Create views**

Replace `backend/restaurants/views.py`:

```python
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from restaurants.serializers import RegisterSerializer, LoginSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )
```

**Step 5: Configure URLs**

Replace `backend/restaurants/urls.py`:

```python
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from restaurants.views import RegisterView, LoginView

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
```

**Step 6: Run tests to verify they pass**

```bash
cd backend
pytest restaurants/tests/test_auth.py -v
```

Expected: All 5 tests PASS.

**Step 7: Run full test suite**

```bash
cd backend
pytest -v
```

Expected: All tests PASS.

**Step 8: Commit**

```bash
git add backend/restaurants/
git commit -m "feat: add JWT auth endpoints (register, login, refresh)"
```
