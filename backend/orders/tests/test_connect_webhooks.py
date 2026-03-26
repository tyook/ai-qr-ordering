import pytest
from django.contrib.auth import get_user_model
from restaurants.models import ConnectedAccount, Restaurant

User = get_user_model()


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-restaurant", owner=owner)


@pytest.fixture
def connected_account(restaurant):
    return ConnectedAccount.objects.create(
        restaurant=restaurant,
        stripe_account_id="acct_test123",
        onboarding_complete=False,
        payouts_enabled=False,
        charges_enabled=False,
    )


@pytest.mark.django_db
class TestAccountUpdatedWebhook:
    def test_updates_connected_account(self, connected_account):
        from orders.services import OrderService

        event_data = {
            "type": "account.updated",
            "account": "acct_test123",
            "data": {
                "object": {
                    "id": "acct_test123",
                    "payouts_enabled": True,
                    "charges_enabled": True,
                    "details_submitted": True,
                }
            },
        }

        OrderService._handle_account_updated(event_data["data"])

        connected_account.refresh_from_db()
        assert connected_account.payouts_enabled is True
        assert connected_account.charges_enabled is True
        assert connected_account.onboarding_complete is True
