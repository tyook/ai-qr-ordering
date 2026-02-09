import pytest
from rest_framework import status
from restaurants.tests.factories import (
    UserFactory, RestaurantFactory, MenuCategoryFactory,
)


@pytest.mark.django_db
class TestMenuCategoryAPI:
    @pytest.fixture
    def owner_and_restaurant(self):
        owner = UserFactory()
        restaurant = RestaurantFactory(owner=owner)
        return owner, restaurant

    def test_create_category(self, api_client, owner_and_restaurant):
        owner, restaurant = owner_and_restaurant
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/categories/",
            {"name": "Appetizers", "sort_order": 1},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Appetizers"

    def test_update_category(self, api_client, owner_and_restaurant):
        owner, restaurant = owner_and_restaurant
        cat = MenuCategoryFactory(restaurant=restaurant, name="Old Name")
        api_client.force_authenticate(user=owner)
        response = api_client.patch(
            f"/api/restaurants/{restaurant.slug}/categories/{cat.id}/",
            {"name": "New Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "New Name"

    def test_non_owner_cannot_create_category(self, api_client, owner_and_restaurant):
        _, restaurant = owner_and_restaurant
        other = UserFactory()
        api_client.force_authenticate(user=other)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/categories/",
            {"name": "Hack", "sort_order": 1},
            format="json",
        )
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]
