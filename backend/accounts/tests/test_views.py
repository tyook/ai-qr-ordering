import pytest
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory


@pytest.fixture
def api():
    return APIClient()


@pytest.mark.django_db
class TestRegister:
    def test_register_with_first_last_name(self, api):
        resp = api.post("/api/auth/register/", {
            "email": "new@example.com",
            "password": "StrongPass123!",
            "first_name": "Jane",
            "last_name": "Doe",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["user"]["email"] == "new@example.com"
        assert resp.data["user"]["first_name"] == "Jane"
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies
        assert resp.cookies["access_token"]["httponly"]

    def test_register_with_single_name(self, api):
        resp = api.post("/api/auth/register/", {
            "email": "new@example.com",
            "password": "StrongPass123!",
            "name": "Jane Doe",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["user"]["first_name"] == "Jane"
        assert resp.data["user"]["last_name"] == "Doe"

    def test_register_duplicate_email(self, api):
        UserFactory(email="existing@example.com")
        resp = api.post("/api/auth/register/", {
            "email": "existing@example.com",
            "password": "StrongPass123!",
            "first_name": "Jane",
            "last_name": "Doe",
        }, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, api):
        UserFactory(email="user@example.com")
        resp = api.post("/api/auth/login/", {
            "email": "user@example.com",
            "password": "testpass123",
        }, format="json")
        assert resp.status_code == 200
        assert "access_token" in resp.cookies

    def test_login_wrong_password(self, api):
        UserFactory(email="user@example.com")
        resp = api.post("/api/auth/login/", {
            "email": "user@example.com",
            "password": "wrong",
        }, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestMe:
    def test_me_returns_user(self, api):
        UserFactory(email="me@example.com")
        api.post("/api/auth/login/", {
            "email": "me@example.com", "password": "testpass123",
        }, format="json")
        resp = api.get("/api/auth/me/")
        assert resp.status_code == 200
        assert resp.data["email"] == "me@example.com"
        assert "is_restaurant_owner" in resp.data

    def test_me_unauthenticated(self, api):
        resp = api.get("/api/auth/me/")
        assert resp.status_code in (401, 403)


@pytest.mark.django_db
class TestLogout:
    def test_logout_clears_cookies(self, api):
        UserFactory(email="user@example.com")
        api.post("/api/auth/login/", {
            "email": "user@example.com", "password": "testpass123",
        }, format="json")
        resp = api.post("/api/auth/logout/")
        assert resp.status_code == 200
        assert resp.cookies["access_token"].value == ""


@pytest.mark.django_db
class TestRefresh:
    def test_refresh_returns_new_cookies(self, api):
        UserFactory(email="user@example.com")
        api.post("/api/auth/login/", {
            "email": "user@example.com", "password": "testpass123",
        }, format="json")
        resp = api.post("/api/auth/refresh/")
        assert resp.status_code == 200
        assert "access_token" in resp.cookies


@pytest.mark.django_db
class TestCookieAttributes:
    def test_cookies_are_samesite_lax(self, api):
        resp = api.post("/api/auth/register/", {
            "email": "cookie@example.com",
            "password": "StrongPass123!",
            "first_name": "Test",
            "last_name": "User",
        }, format="json")
        assert resp.cookies["access_token"]["samesite"] == "Lax"
        assert resp.cookies["refresh_token"]["samesite"] == "Lax"

    def test_refresh_cookie_scoped_to_refresh_path(self, api):
        resp = api.post("/api/auth/register/", {
            "email": "path@example.com",
            "password": "StrongPass123!",
            "first_name": "Test",
            "last_name": "User",
        }, format="json")
        assert resp.cookies["refresh_token"]["path"] == "/api/auth/refresh/"


@pytest.mark.django_db
class TestCSRF:
    def test_csrf_endpoint_sets_cookie(self, api):
        resp = api.get("/api/auth/csrf/")
        assert resp.status_code == 200
        assert "csrftoken" in resp.cookies


@pytest.mark.django_db
class TestOrderLinking:
    def test_register_links_order(self, api):
        from orders.tests.factories import OrderFactory
        order = OrderFactory(user=None)
        resp = api.post("/api/auth/register/", {
            "email": "linker@example.com",
            "password": "StrongPass123!",
            "first_name": "Jane",
            "last_name": "Doe",
            "link_order_id": str(order.id),
        }, format="json")
        assert resp.status_code == 201
        order.refresh_from_db()
        assert order.user is not None
