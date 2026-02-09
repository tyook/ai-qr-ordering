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
        assert response.status_code == status.HTTP_400_BAD_REQUEST


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
