from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from restaurants.models import ConnectedAccount, MenuCategory, MenuItem, MenuItemModifier, MenuItemVariant, Payout, Restaurant, RestaurantStaff
from restaurants.tests.factories import (
    MenuItemVariantFactory,
    UserFactory,
)

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
        owner = User.objects.create_user(email="owner@example.com", password="testpass123")
        restaurant = Restaurant.objects.create(
            name="Test Restaurant",
            slug="test-restaurant",
            owner=owner,
        )
        assert restaurant.name == "Test Restaurant"
        assert restaurant.slug == "test-restaurant"
        assert restaurant.owner == owner

    def test_restaurant_str(self):
        owner = User.objects.create_user(email="owner2@example.com", password="testpass123")
        restaurant = Restaurant.objects.create(name="My Place", slug="my-place", owner=owner)
        assert str(restaurant) == "My Place"

    def test_slug_is_unique(self):
        from django.db import IntegrityError

        owner = User.objects.create_user(email="owner3@example.com", password="testpass123")
        Restaurant.objects.create(name="R1", slug="same-slug", owner=owner)
        with pytest.raises(IntegrityError):
            Restaurant.objects.create(name="R2", slug="same-slug", owner=owner)


@pytest.mark.django_db
class TestRestaurantStaffModel:
    def test_create_staff(self):
        owner = User.objects.create_user(email="staffowner@example.com", password="testpass123")
        restaurant = Restaurant.objects.create(name="Staff Test", slug="staff-test", owner=owner)
        staff_user = User.objects.create_user(email="kitchen@example.com", password="testpass123")
        staff = RestaurantStaff.objects.create(user=staff_user, restaurant=restaurant, role="kitchen")
        assert staff.role == "kitchen"
        assert staff.restaurant == restaurant


@pytest.mark.django_db
class TestMenuModels:
    @pytest.fixture
    def restaurant(self):
        owner = User.objects.create_user(email="menuowner@example.com", password="testpass123")
        return Restaurant.objects.create(name="Menu Test", slug="menu-test", owner=owner)

    def test_create_category(self, restaurant):
        cat = MenuCategory.objects.create(restaurant=restaurant, name="Pizzas", sort_order=1)
        assert cat.name == "Pizzas"
        assert cat.is_active is True

    def test_create_item_with_variant_and_modifier(self, restaurant):
        cat = MenuCategory.objects.create(restaurant=restaurant, name="Pizzas", sort_order=1)
        item = MenuItem.objects.create(category=cat, name="Margherita", description="Classic pizza", sort_order=1)
        variant = MenuItemVariant.objects.create(menu_item=item, label="Large", price=Decimal("14.99"), is_default=True)
        modifier = MenuItemModifier.objects.create(
            menu_item=item, name="Extra Cheese", price_adjustment=Decimal("2.00")
        )
        assert item.variants.count() == 1
        assert item.modifiers.count() == 1
        assert variant.price == Decimal("14.99")
        assert modifier.price_adjustment == Decimal("2.00")

    def test_item_belongs_to_restaurant_via_category(self, restaurant):
        cat = MenuCategory.objects.create(restaurant=restaurant, name="Drinks", sort_order=2)
        item = MenuItem.objects.create(category=cat, name="Coke", description="", sort_order=1)
        assert item.category.restaurant == restaurant


@pytest.mark.django_db
class TestConnectedAccount:
    @pytest.fixture
    def restaurant(self):
        owner = User.objects.create_user(email="caowner@example.com", password="testpass123")
        return Restaurant.objects.create(name="CA Test", slug="ca-test", owner=owner)

    def test_create_connected_account(self, restaurant):
        account = ConnectedAccount.objects.create(
            restaurant=restaurant,
            stripe_account_id="acct_test123",
        )
        assert account.stripe_account_id == "acct_test123"
        assert account.onboarding_complete is False
        assert account.payouts_enabled is False
        assert account.charges_enabled is False
        assert account.pending_refund_balance == 0
        assert account.restaurant == restaurant

    def test_one_to_one_constraint(self, restaurant):
        ConnectedAccount.objects.create(
            restaurant=restaurant,
            stripe_account_id="acct_test123",
        )
        with pytest.raises(IntegrityError):
            ConnectedAccount.objects.create(
                restaurant=restaurant,
                stripe_account_id="acct_test456",
            )


@pytest.mark.django_db
class TestPayout:
    @pytest.fixture
    def restaurant(self):
        owner = User.objects.create_user(email="payoutowner@example.com", password="testpass123")
        return Restaurant.objects.create(name="Payout Test", slug="payout-test", owner=owner)

    def test_create_payout(self, restaurant):
        payout = Payout.objects.create(
            restaurant=restaurant,
            stripe_transfer_id="tr_test123",
            amount=150.00,
            currency="usd",
            orders_count=5,
            period_start="2026-03-25",
            period_end="2026-03-25",
        )
        assert payout.status == "pending"
        assert payout.fee_amount == 0
        assert payout.fee_rate == 0
        assert payout.fee_fixed == 0
        assert payout.stripe_payout_id is None

    def test_payout_status_choices(self, restaurant):
        payout = Payout.objects.create(
            restaurant=restaurant,
            stripe_transfer_id="tr_test456",
            amount=100.00,
            currency="usd",
            status="in_transit",
            orders_count=3,
            period_start="2026-03-25",
            period_end="2026-03-25",
        )
        assert payout.status == "in_transit"


@pytest.mark.django_db
class TestFactories:
    def test_user_factory(self):
        user = UserFactory()
        assert user.email
        assert user.check_password("testpass123")

    def test_full_menu_factory_chain(self):
        variant = MenuItemVariantFactory()
        assert variant.menu_item.category.restaurant.owner.email
