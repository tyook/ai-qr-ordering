import pytest
from rest_framework import status
from restaurants.tests.factories import UserFactory, RestaurantFactory


@pytest.mark.django_db
class TestCreateRestaurant:
    def test_create_restaurant(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/restaurants/",
            {"name": "My Pizza Place", "slug": "my-pizza-place"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "My Pizza Place"
        assert response.data["slug"] == "my-pizza-place"

    def test_create_restaurant_rejects_duplicate_slug(self, api_client):
        RestaurantFactory(slug="taken")
        user = UserFactory()
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/restaurants/",
            {"name": "Another", "slug": "taken"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestMyRestaurants:
    def test_list_own_restaurants(self, api_client):
        user = UserFactory()
        RestaurantFactory(owner=user)
        RestaurantFactory(owner=user)
        RestaurantFactory()  # Someone else's
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/restaurants/me/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2


@pytest.mark.django_db
class TestUpdateRestaurant:
    def test_owner_can_update_name(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        api_client.force_authenticate(user=user)
        response = api_client.patch(
            f"/api/restaurants/{restaurant.slug}/",
            {"name": "New Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "New Name"
