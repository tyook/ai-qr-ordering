import pytest
from django.contrib.auth import get_user_model
from restaurants.models import Restaurant, RestaurantStaff

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


from restaurants.models import MenuCategory, MenuItem, MenuItemVariant, MenuItemModifier
from decimal import Decimal
from restaurants.tests.factories import (
    UserFactory, RestaurantFactory, MenuCategoryFactory,
    MenuItemFactory, MenuItemVariantFactory, MenuItemModifierFactory,
)


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


@pytest.mark.django_db
class TestFactories:
    def test_user_factory(self):
        user = UserFactory()
        assert user.email
        assert user.check_password("testpass123")

    def test_full_menu_factory_chain(self):
        variant = MenuItemVariantFactory()
        assert variant.menu_item.category.restaurant.owner.email
