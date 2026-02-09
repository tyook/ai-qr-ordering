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
