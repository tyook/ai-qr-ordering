import pytest
from unittest.mock import patch
from rest_framework.test import APIClient
from customers.models import Customer
from customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


class TestGoogleAuth:
    MOCK_GOOGLE_USER = {
        "sub": "google-user-123",
        "email": "alice@gmail.com",
        "name": "Alice Smith",
        "picture": "https://example.com/photo.jpg",
    }

    @patch("customers.views.verify_google_token")
    def test_google_login_new_user(self, mock_verify, api_client):
        mock_verify.return_value = self.MOCK_GOOGLE_USER
        resp = api_client.post("/api/customer/auth/google/", {
            "token": "fake-google-token",
        }, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data
        assert resp.data["customer"]["email"] == "alice@gmail.com"
        assert resp.data["customer"]["name"] == "Alice Smith"
        # Customer created
        customer = Customer.objects.get(email="alice@gmail.com")
        assert customer.auth_provider == "google"
        assert customer.auth_provider_id == "google-user-123"

    @patch("customers.views.verify_google_token")
    def test_google_login_existing_user(self, mock_verify, api_client):
        mock_verify.return_value = self.MOCK_GOOGLE_USER
        CustomerFactory(email="alice@gmail.com", name="Alice")
        resp = api_client.post("/api/customer/auth/google/", {
            "token": "fake-google-token",
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["customer"]["email"] == "alice@gmail.com"
        # No duplicate created
        assert Customer.objects.filter(email="alice@gmail.com").count() == 1

    @patch("customers.views.verify_google_token")
    def test_google_login_invalid_token(self, mock_verify, api_client):
        mock_verify.side_effect = ValueError("Invalid token")
        resp = api_client.post("/api/customer/auth/google/", {
            "token": "bad-token",
        }, format="json")
        assert resp.status_code == 400

    def test_google_login_missing_token(self, api_client):
        resp = api_client.post("/api/customer/auth/google/", {}, format="json")
        assert resp.status_code == 400
