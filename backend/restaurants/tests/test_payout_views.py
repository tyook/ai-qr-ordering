import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from restaurants.models import Restaurant, Payout

User = get_user_model()


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-rest", owner=owner)


@pytest.fixture
def api_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.fixture
def payout(restaurant):
    return Payout.objects.create(
        restaurant=restaurant,
        stripe_transfer_id="tr_test123",
        amount=Decimal("150.00"),
        currency="usd",
        status="completed",
        orders_count=5,
        period_start="2026-03-25",
        period_end="2026-03-25",
    )


@pytest.mark.django_db
class TestPayoutListView:
    def test_list_payouts(self, api_client, restaurant, payout):
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/payouts/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["amount"] == "150.00"

    def test_unauthenticated(self, restaurant):
        client = APIClient()
        response = client.get(f"/api/restaurants/{restaurant.slug}/payouts/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestPayoutDetailView:
    def test_get_payout_detail(self, api_client, restaurant, payout):
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/payouts/{payout.id}/")
        assert response.status_code == 200
        assert response.data["stripe_transfer_id"] == "tr_test123"
