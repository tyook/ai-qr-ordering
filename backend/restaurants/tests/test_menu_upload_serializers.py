import pytest
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from restaurants.models import MenuVersion, Restaurant
from restaurants.serializers.menu_upload_serializers import (
    MenuUploadParseSerializer,
    MenuSaveSerializer,
    MenuVersionSerializer,
)

User = get_user_model()


@pytest.fixture
def menu_version(db):
    owner = User.objects.create_user(email="mvs_owner@example.com", password="testpass123")
    restaurant = Restaurant.objects.create(name="MVS Test", slug="mvs-test", owner=owner)
    return MenuVersion.objects.create(
        restaurant=restaurant,
        name="Test Version",
        is_active=True,
        source="manual",
    )


class TestMenuUploadParseSerializer:
    def test_valid_single_image(self):
        image = SimpleUploadedFile("menu.jpg", b"fake-image", content_type="image/jpeg")
        serializer = MenuUploadParseSerializer(data={"images": [image]})
        assert serializer.is_valid(), serializer.errors

    def test_rejects_non_image(self):
        file = SimpleUploadedFile("doc.pdf", b"fake", content_type="application/pdf")
        serializer = MenuUploadParseSerializer(data={"images": [file]})
        assert not serializer.is_valid()

    def test_rejects_too_many_images(self):
        images = [
            SimpleUploadedFile(f"menu{i}.jpg", b"fake", content_type="image/jpeg")
            for i in range(11)
        ]
        serializer = MenuUploadParseSerializer(data={"images": images})
        assert not serializer.is_valid()


class TestMenuSaveSerializer:
    def test_valid_overwrite(self):
        data = {
            "menu": {
                "categories": [
                    {
                        "name": "Mains",
                        "items": [
                            {
                                "name": "Burger",
                                "description": "Beef burger",
                                "variants": [{"label": "Regular", "price": "12.00"}],
                            }
                        ],
                    }
                ]
            },
            "mode": "overwrite",
        }
        serializer = MenuSaveSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_rejects_invalid_mode(self):
        data = {
            "menu": {"categories": []},
            "mode": "invalid",
        }
        serializer = MenuSaveSerializer(data=data)
        assert not serializer.is_valid()

    def test_version_name_optional(self):
        data = {
            "menu": {"categories": []},
            "mode": "overwrite",
        }
        serializer = MenuSaveSerializer(data=data)
        assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
class TestMenuVersionSerializer:
    def test_serializes_version(self, menu_version):
        serializer = MenuVersionSerializer(menu_version)
        data = serializer.data
        assert "id" in data
        assert data["name"] == menu_version.name
        assert "is_active" in data
        assert "source" in data
        assert "created_at" in data
