from unittest.mock import patch

import pytest

from customers.models import Customer
from customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


class TestAppleAuth:
    MOCK_APPLE_USER = {
        "sub": "apple-user-456",
        "email": "bob@icloud.com",
        "name": "",
    }

    @patch("customers.services.verify_apple_token")
    def test_apple_login_new_user(self, mock_verify, api_client):
        mock_verify.return_value = self.MOCK_APPLE_USER
        resp = api_client.post(
            "/api/customer/auth/apple/",
            {
                "token": "fake-apple-token",
                "name": "Bob Jones",
            },
            format="json",
        )
        assert resp.status_code == 200
        assert "access" in resp.data
        assert resp.data["customer"]["email"] == "bob@icloud.com"
        customer = Customer.objects.get(email="bob@icloud.com")
        assert customer.auth_provider == "apple"
        assert customer.auth_provider_id == "apple-user-456"
        assert customer.name == "Bob Jones"

    @patch("customers.services.verify_apple_token")
    def test_apple_login_existing_user(self, mock_verify, api_client):
        mock_verify.return_value = self.MOCK_APPLE_USER
        CustomerFactory(email="bob@icloud.com", name="Bob")
        resp = api_client.post(
            "/api/customer/auth/apple/",
            {
                "token": "fake-apple-token",
            },
            format="json",
        )
        assert resp.status_code == 200
        assert Customer.objects.filter(email="bob@icloud.com").count() == 1

    @patch("customers.services.verify_apple_token")
    def test_apple_login_invalid_token(self, mock_verify, api_client):
        mock_verify.side_effect = ValueError("Invalid token")
        resp = api_client.post(
            "/api/customer/auth/apple/",
            {
                "token": "bad-token",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_apple_login_missing_token(self, api_client):
        resp = api_client.post("/api/customer/auth/apple/", {}, format="json")
        assert resp.status_code == 400

    @patch("customers.services.verify_apple_token")
    def test_apple_login_fallback_name(self, mock_verify, api_client):
        """When no name is provided, use email prefix as display name."""
        mock_verify.return_value = self.MOCK_APPLE_USER
        resp = api_client.post(
            "/api/customer/auth/apple/",
            {
                "token": "fake-apple-token",
                # No name provided
            },
            format="json",
        )
        assert resp.status_code == 200
        customer = Customer.objects.get(email="bob@icloud.com")
        assert customer.name == "bob"  # Falls back to email prefix
