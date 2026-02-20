import pytest
from unittest.mock import patch, MagicMock
from rest_framework import status
from restaurants.tests.factories import UserFactory, RestaurantFactory
from restaurants.models import Subscription
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestSubscriptionDetail:
    def test_owner_can_view_subscription(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            trial_end=timezone.now() + timedelta(days=14),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
        )
        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/subscription/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["plan"] == "starter"
        assert response.data["status"] == "trialing"
        assert "order_count" in response.data
        assert "order_limit" in response.data
        assert "is_active" in response.data

    def test_unauthenticated_cannot_view(self, api_client):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant, plan="starter", status="trialing",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
        )
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/subscription/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_owner_cannot_view(self, api_client):
        other_user = UserFactory()
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant, plan="starter", status="trialing",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
        )
        api_client.force_authenticate(user=other_user)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/subscription/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCreateCheckoutSession:
    @patch("stripe.checkout.Session.create")
    @patch("stripe.Customer.create")
    def test_create_checkout_session(self, mock_stripe_customer, mock_checkout, api_client, settings):
        settings.SUBSCRIPTION_PLANS = {
            **settings.SUBSCRIPTION_PLANS,
            "growth": {
                **settings.SUBSCRIPTION_PLANS["growth"],
                "monthly_price_id": "price_test_growth_monthly",
                "annual_price_id": "price_test_growth_annual",
            },
        }
        mock_stripe_customer.return_value = MagicMock(id="cus_test123")
        mock_checkout.return_value = MagicMock(url="https://checkout.stripe.com/test")
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        Subscription.objects.create(
            restaurant=restaurant, plan="starter", status="trialing",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
        )
        api_client.force_authenticate(user=user)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/subscription/checkout/",
            {"plan": "growth", "interval": "monthly"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "checkout_url" in response.data


@pytest.mark.django_db
class TestCreateBillingPortal:
    @patch("stripe.billing_portal.Session.create")
    def test_create_portal_session(self, mock_portal, api_client):
        mock_portal.return_value = MagicMock(url="https://billing.stripe.com/test")
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        Subscription.objects.create(
            restaurant=restaurant, plan="starter", status="active",
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        api_client.force_authenticate(user=user)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/subscription/portal/",
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "portal_url" in response.data


@pytest.mark.django_db
class TestCancelSubscription:
    @patch("stripe.Subscription.modify")
    def test_cancel_subscription_at_period_end(self, mock_modify, api_client):
        mock_modify.return_value = MagicMock(
            cancel_at_period_end=True,
            status="active",
        )
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        Subscription.objects.create(
            restaurant=restaurant, plan="growth", status="active",
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        api_client.force_authenticate(user=user)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/subscription/cancel/",
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["cancel_at_period_end"] is True
        mock_modify.assert_called_once_with("sub_test123", cancel_at_period_end=True)

    def test_cancel_requires_active_subscription(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        Subscription.objects.create(
            restaurant=restaurant, plan="starter", status="trialing",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
            # No stripe_subscription_id — trial without Stripe sub
        )
        api_client.force_authenticate(user=user)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/subscription/cancel/",
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("stripe.Subscription.modify")
    def test_reactivate_subscription(self, mock_modify, api_client):
        mock_modify.return_value = MagicMock(
            cancel_at_period_end=False,
            status="active",
        )
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        Subscription.objects.create(
            restaurant=restaurant, plan="growth", status="active",
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            cancel_at_period_end=True,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        api_client.force_authenticate(user=user)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/subscription/reactivate/",
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["cancel_at_period_end"] is False
        mock_modify.assert_called_once_with("sub_test123", cancel_at_period_end=False)
