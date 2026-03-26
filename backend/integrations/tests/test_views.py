import pytest
from rest_framework import status

from integrations.models import POSConnection
from integrations.tests.factories import POSConnectionFactory
from restaurants.tests.factories import RestaurantFactory, UserFactory


@pytest.mark.django_db
class TestPOSConnectionAPI:
    @pytest.fixture
    def owner_setup(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user, slug="test-resto")
        api_client.force_authenticate(user=user)
        return {"user": user, "restaurant": restaurant, "client": api_client}

    def test_get_connection_when_none_exists(self, owner_setup):
        response = owner_setup["client"].get(
            "/api/restaurants/test-resto/pos/connection/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pos_type"] == "none"
        assert response.data["is_connected"] is False

    def test_get_existing_connection(self, owner_setup):
        POSConnectionFactory(
            restaurant=owner_setup["restaurant"],
            pos_type="square",
        )
        response = owner_setup["client"].get(
            "/api/restaurants/test-resto/pos/connection/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pos_type"] == "square"
        assert response.data["is_connected"] is True

    def test_update_payment_mode(self, owner_setup):
        POSConnectionFactory(
            restaurant=owner_setup["restaurant"],
            pos_type="square",
        )
        response = owner_setup["client"].patch(
            "/api/restaurants/test-resto/pos/connection/",
            {"payment_mode": "pos_collected"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["payment_mode"] == "pos_collected"

    def test_delete_connection(self, owner_setup):
        POSConnectionFactory(
            restaurant=owner_setup["restaurant"],
            pos_type="square",
        )
        response = owner_setup["client"].delete(
            "/api/restaurants/test-resto/pos/connection/"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not POSConnection.objects.filter(
            restaurant=owner_setup["restaurant"]
        ).exists()

    def test_unauthenticated_access_denied(self, api_client):
        RestaurantFactory(slug="test-resto")
        response = api_client.get(
            "/api/restaurants/test-resto/pos/connection/"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
