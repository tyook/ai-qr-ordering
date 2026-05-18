import pytest
from rest_framework import status

from restaurants.models import Subscription
from restaurants.tests.factories import RestaurantFactory, RestaurantStaffFactory, UserFactory
from datetime import timedelta
from django.utils import timezone


def _setup_restaurant_with_subscription():
    restaurant = RestaurantFactory()
    Subscription.objects.create(
        restaurant=restaurant,
        plan="starter",
        status="active",
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30),
    )
    return restaurant


@pytest.mark.django_db
class TestAdminOnlyViews:
    def test_member_cannot_access_analytics(self, api_client):
        restaurant = _setup_restaurant_with_subscription()
        member = UserFactory()
        RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        api_client.force_authenticate(user=member)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/analytics/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_access_analytics(self, api_client):
        restaurant = _setup_restaurant_with_subscription()
        admin = UserFactory()
        RestaurantStaffFactory(user=admin, restaurant=restaurant, role="admin")
        api_client.force_authenticate(user=admin)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/analytics/")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestMenuEditPermission:
    def test_member_without_permission_cannot_create_category(self, api_client):
        restaurant = _setup_restaurant_with_subscription()
        member = UserFactory()
        RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        api_client.force_authenticate(user=member)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/categories/",
            {"name": "New Category"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_member_with_permission_can_create_category(self, api_client):
        restaurant = _setup_restaurant_with_subscription()
        from restaurants.models import MenuVersion
        MenuVersion.objects.create(restaurant=restaurant, name="Main", is_active=True)
        member = UserFactory()
        RestaurantStaffFactory(
            user=member, restaurant=restaurant, role="member",
            permissions={"menu_edit": True},
        )
        api_client.force_authenticate(user=member)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/categories/",
            {"name": "New Category"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
