import pytest
from unittest.mock import patch
from rest_framework import status
from restaurants.tests.factories import RestaurantFactory, MenuCategoryFactory, MenuItemFactory, MenuItemVariantFactory
from restaurants.models import Subscription
from django.utils import timezone
from datetime import timedelta


def _setup_restaurant_with_menu():
    """Create a restaurant with a menu item for parsing."""
    restaurant = RestaurantFactory()
    category = MenuCategoryFactory(restaurant=restaurant)
    item = MenuItemFactory(category=category, name="Pizza")
    MenuItemVariantFactory(menu_item=item, label="Large", price=15.00)
    return restaurant


@pytest.mark.django_db
class TestSubscriptionGate:
    @patch("orders.views.validate_and_price_order")
    @patch("orders.views.OrderParsingAgent.run")
    def test_parse_order_increments_order_count(self, mock_agent, mock_validate, api_client):
        mock_agent.return_value = {"items": [], "language": "en"}
        mock_validate.return_value = {"items": [], "language": "en"}
        restaurant = _setup_restaurant_with_menu()
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="active",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            order_count=5,
        )
        response = api_client.post(
            f"/api/order/{restaurant.slug}/parse/",
            {"raw_input": "one large pizza"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        sub.refresh_from_db()
        assert sub.order_count == 6

    def test_parse_order_blocked_when_subscription_canceled(self, api_client):
        restaurant = _setup_restaurant_with_menu()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="canceled",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() - timedelta(days=1),
            order_count=0,
        )
        response = api_client.post(
            f"/api/order/{restaurant.slug}/parse/",
            {"raw_input": "one large pizza"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "subscription" in response.data["detail"].lower()

    def test_parse_order_blocked_when_trial_expired(self, api_client):
        restaurant = _setup_restaurant_with_menu()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            trial_end=timezone.now() - timedelta(days=1),
            current_period_start=timezone.now() - timedelta(days=15),
            current_period_end=timezone.now() - timedelta(days=1),
            order_count=0,
        )
        response = api_client.post(
            f"/api/order/{restaurant.slug}/parse/",
            {"raw_input": "one large pizza"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("orders.views.validate_and_price_order")
    @patch("orders.views.OrderParsingAgent.run")
    def test_parse_order_allowed_when_over_limit_soft_cap(self, mock_agent, mock_validate, api_client):
        """Soft cap: orders continue even when over limit."""
        mock_agent.return_value = {"items": [], "language": "en"}
        mock_validate.return_value = {"items": [], "language": "en"}
        restaurant = _setup_restaurant_with_menu()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="active",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            order_count=250,  # Over the 200 limit
        )
        response = api_client.post(
            f"/api/order/{restaurant.slug}/parse/",
            {"raw_input": "one large pizza"},
            format="json",
        )
        # Soft cap: should still work
        assert response.status_code == status.HTTP_200_OK

    def test_parse_order_allowed_when_no_subscription_exists(self, api_client):
        """Restaurants without a subscription (legacy) should not be blocked."""
        restaurant = _setup_restaurant_with_menu()
        # No Subscription object created
        with patch("orders.views.OrderParsingAgent.run") as mock_agent, \
             patch("orders.views.validate_and_price_order") as mock_validate:
            mock_agent.return_value = {"items": [], "language": "en"}
            mock_validate.return_value = {"items": [], "language": "en"}
            response = api_client.post(
                f"/api/order/{restaurant.slug}/parse/",
                {"raw_input": "one large pizza"},
                format="json",
            )
            assert response.status_code == status.HTTP_200_OK
