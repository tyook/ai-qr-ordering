import pytest
from rest_framework import status

from restaurants.tests.factories import RestaurantFactory, RestaurantStaffFactory, UserFactory


@pytest.mark.django_db
class TestRestaurantPermissions:
    def test_owner_can_access_own_restaurant(self, api_client):
        owner = UserFactory()
        restaurant = RestaurantFactory(owner=owner)
        api_client.force_authenticate(user=owner)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/")
        assert response.status_code == status.HTTP_200_OK

    def test_non_owner_cannot_access_restaurant(self, api_client):
        owner = UserFactory()
        other = UserFactory()
        restaurant = RestaurantFactory(owner=owner)
        api_client.force_authenticate(user=other)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_staff_manager_can_access_restaurant(self, api_client):
        owner = UserFactory()
        manager = UserFactory()
        restaurant = RestaurantFactory(owner=owner)
        RestaurantStaffFactory(user=manager, restaurant=restaurant, role="admin")
        api_client.force_authenticate(user=manager)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/")
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_cannot_list_restaurants(self, api_client):
        response = api_client.get("/api/restaurants/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
