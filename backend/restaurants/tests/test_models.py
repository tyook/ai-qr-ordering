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
