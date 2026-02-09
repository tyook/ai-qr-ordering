import pytest
from rest_framework import status
from restaurants.tests.factories import (
    RestaurantFactory, MenuCategoryFactory, MenuItemFactory,
    MenuItemVariantFactory, MenuItemModifierFactory,
)


@pytest.mark.django_db
class TestPublicMenu:
    def test_get_menu_no_auth_required(self, api_client):
        restaurant = RestaurantFactory(slug="public-test")
        cat = MenuCategoryFactory(restaurant=restaurant, name="Mains")
        item = MenuItemFactory(category=cat, name="Burger")
        MenuItemVariantFactory(menu_item=item, label="Regular", price="10.99")
        MenuItemModifierFactory(menu_item=item, name="Extra Cheese")

        response = api_client.get("/api/order/public-test/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["categories"]) == 1
        assert response.data["categories"][0]["name"] == "Mains"
        assert len(response.data["categories"][0]["items"]) == 1

    def test_inactive_items_excluded(self, api_client):
        restaurant = RestaurantFactory(slug="inactive-test")
        cat = MenuCategoryFactory(restaurant=restaurant)
        MenuItemFactory(category=cat, is_active=True)
        MenuItemFactory(category=cat, is_active=False)

        response = api_client.get("/api/order/inactive-test/menu/")
        assert len(response.data["categories"][0]["items"]) == 1

    def test_nonexistent_restaurant_returns_404(self, api_client):
        response = api_client.get("/api/order/nonexistent/menu/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
