import pytest
from django.db import IntegrityError
from restaurants.models import MenuVersion, Restaurant, MenuCategory
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def restaurant(db):
    owner = User.objects.create_user(email="mvowner@example.com", password="testpass123")
    return Restaurant.objects.create(name="MV Test", slug="mv-test", owner=owner)


@pytest.mark.django_db
class TestMenuVersionModel:
    def test_create_menu_version(self, restaurant):
        version = MenuVersion.objects.create(
            restaurant=restaurant,
            name="Lunch Menu",
            source="manual",
        )
        assert version.name == "Lunch Menu"
        assert version.source == "manual"
        assert version.is_active is False
        assert version.restaurant == restaurant

    def test_str_representation(self, restaurant):
        version = MenuVersion.objects.create(
            restaurant=restaurant, name="Dinner", source="manual"
        )
        assert str(version) == "Dinner"

    def test_source_choices(self, restaurant):
        version = MenuVersion.objects.create(
            restaurant=restaurant, name="AI Menu", source="ai_upload"
        )
        assert version.source == "ai_upload"

    def test_ordering_by_created_at(self, restaurant):
        v1 = MenuVersion.objects.create(
            restaurant=restaurant, name="V1", source="manual"
        )
        v2 = MenuVersion.objects.create(
            restaurant=restaurant, name="V2", source="manual"
        )
        versions = list(MenuVersion.objects.filter(restaurant=restaurant))
        assert versions == [v2, v1]  # newest first
