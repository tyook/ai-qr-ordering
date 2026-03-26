import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from restaurants.services.connect_service import ConnectService
from restaurants.models import ConnectedAccount, Restaurant

User = get_user_model()


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-restaurant", owner=owner)


@pytest.mark.django_db
class TestConnectServiceOnboard:
    @patch("restaurants.services.connect_service.stripe.Account.create")
    @patch("restaurants.services.connect_service.stripe.AccountLink.create")
    def test_create_connect_account(self, mock_link, mock_create, restaurant):
        mock_create.return_value = MagicMock(id="acct_test123")
        mock_link.return_value = MagicMock(url="https://connect.stripe.com/setup/abc")

        result = ConnectService.create_onboarding_link(restaurant)

        assert result["url"] == "https://connect.stripe.com/setup/abc"
        account = ConnectedAccount.objects.get(restaurant=restaurant)
        assert account.stripe_account_id == "acct_test123"

    @patch("restaurants.services.connect_service.stripe.Account.create")
    @patch("restaurants.services.connect_service.stripe.AccountLink.create")
    def test_returns_new_link_if_account_exists(self, mock_link, mock_create, restaurant):
        ConnectedAccount.objects.create(
            restaurant=restaurant, stripe_account_id="acct_existing"
        )
        mock_link.return_value = MagicMock(url="https://connect.stripe.com/setup/new")

        result = ConnectService.create_onboarding_link(restaurant)

        assert result["url"] == "https://connect.stripe.com/setup/new"
        mock_create.assert_not_called()


@pytest.mark.django_db
class TestConnectServiceStatus:
    def test_status_no_account(self, restaurant):
        result = ConnectService.get_connect_status(restaurant)
        assert result["has_account"] is False
        assert result["payouts_enabled"] is False

    def test_status_with_account(self, restaurant):
        ConnectedAccount.objects.create(
            restaurant=restaurant,
            stripe_account_id="acct_test123",
            onboarding_complete=True,
            payouts_enabled=True,
            charges_enabled=True,
        )
        result = ConnectService.get_connect_status(restaurant)
        assert result["has_account"] is True
        assert result["payouts_enabled"] is True


@pytest.mark.django_db
class TestConnectServiceDashboard:
    @patch("restaurants.services.connect_service.stripe.Account.create_login_link")
    def test_create_dashboard_link(self, mock_login_link, restaurant):
        ConnectedAccount.objects.create(
            restaurant=restaurant,
            stripe_account_id="acct_test123",
            onboarding_complete=True,
        )
        mock_login_link.return_value = MagicMock(url="https://connect.stripe.com/express/abc")

        result = ConnectService.create_dashboard_link(restaurant)
        assert result["url"] == "https://connect.stripe.com/express/abc"
