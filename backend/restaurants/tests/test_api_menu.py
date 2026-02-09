import pytest
from rest_framework import status
from decimal import Decimal
from restaurants.tests.factories import (
    UserFactory, RestaurantFactory, MenuCategoryFactory,
    MenuItemFactory, MenuItemVariantFactory, MenuItemModifierFactory,
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


@pytest.mark.django_db
class TestMenuItemAPI:
    @pytest.fixture
    def setup(self):
        owner = UserFactory()
        restaurant = RestaurantFactory(owner=owner)
        category = MenuCategoryFactory(restaurant=restaurant)
        return owner, restaurant, category

    def test_create_item_with_variants_and_modifiers(self, api_client, setup):
        owner, restaurant, category = setup
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/items/",
            {
                "category_id": category.id,
                "name": "Pepperoni Pizza",
                "description": "Classic pepperoni",
                "sort_order": 1,
                "variants": [
                    {"label": "Small", "price": "10.99", "is_default": True},
                    {"label": "Large", "price": "14.99", "is_default": False},
                ],
                "modifiers": [
                    {"name": "Extra Cheese", "price_adjustment": "2.00"},
                    {"name": "No Olives", "price_adjustment": "0.00"},
                ],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Pepperoni Pizza"
        assert len(response.data["variants"]) == 2
        assert len(response.data["modifiers"]) == 2

    def test_update_item(self, api_client, setup):
        owner, restaurant, category = setup
        item = MenuItemFactory(category=category, name="Old Name")
        api_client.force_authenticate(user=owner)
        response = api_client.patch(
            f"/api/restaurants/{restaurant.slug}/items/{item.id}/",
            {"name": "New Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "New Name"

    def test_deactivate_item(self, api_client, setup):
        owner, restaurant, category = setup
        item = MenuItemFactory(category=category)
        api_client.force_authenticate(user=owner)
        response = api_client.delete(
            f"/api/restaurants/{restaurant.slug}/items/{item.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        assert item.is_active is False


@pytest.mark.django_db
class TestFullMenuAPI:
    def test_get_full_menu_includes_inactive(self, api_client):
        owner = UserFactory()
        restaurant = RestaurantFactory(owner=owner)
        cat = MenuCategoryFactory(restaurant=restaurant)
        MenuItemFactory(category=cat, is_active=True)
        MenuItemFactory(category=cat, is_active=False)

        api_client.force_authenticate(user=owner)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/menu/")
        assert response.status_code == status.HTTP_200_OK
        # Admin view includes all items (active and inactive)
        total_items = sum(
            len(cat["items"]) for cat in response.data["categories"]
        )
        assert total_items == 2
