"""
Tests for MenuVersionService.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from restaurants.models import (
    MenuCategory,
    MenuItem,
    MenuItemModifier,
    MenuItemVariant,
    MenuVersion,
    Restaurant,
)
from restaurants.services.menu_version_service import MenuVersionService

User = get_user_model()


@pytest.fixture
def restaurant(db):
    owner = User.objects.create_user(email="mvs_owner@example.com", password="testpass123")
    return Restaurant.objects.create(name="Version Test Restaurant", slug="vtr", owner=owner)


@pytest.fixture
def version(restaurant):
    return MenuVersion.objects.create(restaurant=restaurant, name="V1", source="manual")


@pytest.fixture
def active_version(restaurant):
    return MenuVersion.objects.create(
        restaurant=restaurant, name="Active V", source="manual", is_active=True
    )


@pytest.fixture
def version_with_items(restaurant):
    """A version containing 1 category with 2 items, each with a variant and modifier."""
    v = MenuVersion.objects.create(restaurant=restaurant, name="With Items", source="manual")
    cat = MenuCategory.objects.create(version=v, name="Burgers", sort_order=0)
    for i in range(2):
        item = MenuItem.objects.create(
            category=cat,
            name=f"Item {i}",
            description=f"Desc {i}",
            sort_order=i,
        )
        MenuItemVariant.objects.create(
            menu_item=item, label="Standard", price=Decimal("9.99"), is_default=True
        )
        MenuItemModifier.objects.create(
            menu_item=item, name="Extra Sauce", price_adjustment=Decimal("0.50")
        )
    return v


# ── generate_default_name ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateDefaultName:
    def test_returns_base_name_when_no_versions_exist(self, restaurant):
        from datetime import date

        today = date.today()
        expected_base = f"Menu - {today.strftime('%b %-d, %Y')}"
        name = MenuVersionService.generate_default_name(restaurant)
        assert name == expected_base

    def test_returns_counter_when_name_exists(self, restaurant):
        from datetime import date

        today = date.today()
        base_name = f"Menu - {today.strftime('%b %-d, %Y')}"
        MenuVersion.objects.create(restaurant=restaurant, name=base_name, source="manual")

        name = MenuVersionService.generate_default_name(restaurant)
        assert name == f"{base_name} (2)"

    def test_increments_counter_for_multiple_duplicates(self, restaurant):
        from datetime import date

        today = date.today()
        base_name = f"Menu - {today.strftime('%b %-d, %Y')}"
        MenuVersion.objects.create(restaurant=restaurant, name=base_name, source="manual")
        MenuVersion.objects.create(restaurant=restaurant, name=f"{base_name} (2)", source="manual")

        name = MenuVersionService.generate_default_name(restaurant)
        assert name == f"{base_name} (3)"

    def test_names_are_restaurant_scoped(self, db):
        """Versions from another restaurant should not affect the counter."""
        from datetime import date

        today = date.today()
        base_name = f"Menu - {today.strftime('%b %-d, %Y')}"

        owner2 = User.objects.create_user(email="other@example.com", password="pass")
        other_restaurant = Restaurant.objects.create(name="Other", slug="other", owner=owner2)
        MenuVersion.objects.create(restaurant=other_restaurant, name=base_name, source="manual")

        owner1 = User.objects.create_user(email="first@example.com", password="pass")
        restaurant = Restaurant.objects.create(name="First", slug="first", owner=owner1)

        name = MenuVersionService.generate_default_name(restaurant)
        assert name == base_name


# ── activate_version ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestActivateVersion:
    def test_activates_given_version(self, restaurant, version):
        result = MenuVersionService.activate_version(restaurant, version)
        version.refresh_from_db()
        assert version.is_active is True
        assert result.is_active is True

    def test_deactivates_other_versions(self, restaurant, active_version, version):
        # active_version is initially active; now activate version
        MenuVersionService.activate_version(restaurant, version)
        active_version.refresh_from_db()
        assert active_version.is_active is False

    def test_only_one_version_active_at_a_time(self, restaurant):
        v1 = MenuVersion.objects.create(restaurant=restaurant, name="V1", source="manual", is_active=True)
        v2 = MenuVersion.objects.create(restaurant=restaurant, name="V2", source="manual", is_active=True)

        MenuVersionService.activate_version(restaurant, v1)

        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v1.is_active is True
        assert v2.is_active is False
        active_count = MenuVersion.objects.filter(restaurant=restaurant, is_active=True).count()
        assert active_count == 1


# ── delete_version ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDeleteVersion:
    def test_cannot_delete_active_version(self, active_version):
        with pytest.raises(ValueError, match="Cannot delete the active menu version"):
            MenuVersionService.delete_version(active_version)

    def test_can_delete_inactive_version(self, restaurant, version):
        version_id = version.id
        MenuVersionService.delete_version(version)
        assert not MenuVersion.objects.filter(id=version_id).exists()


# ── rename_version ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRenameVersion:
    def test_renames_version(self, version):
        result = MenuVersionService.rename_version(version, "New Name")
        version.refresh_from_db()
        assert version.name == "New Name"
        assert result.name == "New Name"


# ── list_versions ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestListVersions:
    def test_returns_list_of_dicts(self, restaurant, version):
        result = MenuVersionService.list_versions(restaurant)
        assert isinstance(result, list)
        assert len(result) == 1
        entry = result[0]
        assert entry["id"] == version.id
        assert entry["name"] == version.name
        assert "is_active" in entry
        assert "source" in entry
        assert "created_at" in entry
        assert "item_count" in entry

    def test_item_count_is_correct(self, restaurant, version_with_items):
        result = MenuVersionService.list_versions(restaurant)
        entry = next(e for e in result if e["id"] == version_with_items.id)
        assert entry["item_count"] == 2

    def test_item_count_zero_for_empty_version(self, restaurant, version):
        result = MenuVersionService.list_versions(restaurant)
        entry = next(e for e in result if e["id"] == version.id)
        assert entry["item_count"] == 0

    def test_returns_all_versions_for_restaurant(self, restaurant):
        MenuVersion.objects.create(restaurant=restaurant, name="A", source="manual")
        MenuVersion.objects.create(restaurant=restaurant, name="B", source="manual")
        result = MenuVersionService.list_versions(restaurant)
        assert len(result) == 2


# ── duplicate_version_into ─────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDuplicateVersionInto:
    def test_copies_categories(self, restaurant, version_with_items):
        target = MenuVersion.objects.create(restaurant=restaurant, name="Target", source="manual")
        MenuVersionService.duplicate_version_into(version_with_items, target)

        source_cats = list(version_with_items.categories.values_list("name", flat=True))
        target_cats = list(target.categories.values_list("name", flat=True))
        assert source_cats == target_cats

    def test_copies_items(self, restaurant, version_with_items):
        target = MenuVersion.objects.create(restaurant=restaurant, name="Target", source="manual")
        MenuVersionService.duplicate_version_into(version_with_items, target)

        source_item_names = set(
            MenuItem.objects.filter(category__version=version_with_items).values_list("name", flat=True)
        )
        target_item_names = set(
            MenuItem.objects.filter(category__version=target).values_list("name", flat=True)
        )
        assert source_item_names == target_item_names

    def test_copies_variants(self, restaurant, version_with_items):
        target = MenuVersion.objects.create(restaurant=restaurant, name="Target", source="manual")
        MenuVersionService.duplicate_version_into(version_with_items, target)

        source_variant_count = MenuItemVariant.objects.filter(
            menu_item__category__version=version_with_items
        ).count()
        target_variant_count = MenuItemVariant.objects.filter(
            menu_item__category__version=target
        ).count()
        assert target_variant_count == source_variant_count

    def test_copies_modifiers(self, restaurant, version_with_items):
        target = MenuVersion.objects.create(restaurant=restaurant, name="Target", source="manual")
        MenuVersionService.duplicate_version_into(version_with_items, target)

        source_modifier_count = MenuItemModifier.objects.filter(
            menu_item__category__version=version_with_items
        ).count()
        target_modifier_count = MenuItemModifier.objects.filter(
            menu_item__category__version=target
        ).count()
        assert target_modifier_count == source_modifier_count

    def test_new_objects_have_different_pks(self, restaurant, version_with_items):
        target = MenuVersion.objects.create(restaurant=restaurant, name="Target", source="manual")
        MenuVersionService.duplicate_version_into(version_with_items, target)

        source_item_ids = set(
            MenuItem.objects.filter(category__version=version_with_items).values_list("id", flat=True)
        )
        target_item_ids = set(
            MenuItem.objects.filter(category__version=target).values_list("id", flat=True)
        )
        assert source_item_ids.isdisjoint(target_item_ids)


# ── duplicate_version ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDuplicateVersion:
    def test_creates_new_version_with_given_name(self, restaurant, version_with_items):
        new_version = MenuVersionService.duplicate_version(version_with_items, "Copy")
        assert new_version.name == "Copy"
        assert new_version.restaurant == restaurant

    def test_new_version_is_not_active(self, restaurant, version_with_items):
        new_version = MenuVersionService.duplicate_version(version_with_items, "Copy")
        assert new_version.is_active is False

    def test_new_version_has_full_deep_copy(self, restaurant, version_with_items):
        new_version = MenuVersionService.duplicate_version(version_with_items, "Copy")

        assert new_version.categories.count() == version_with_items.categories.count()

        target_item_count = MenuItem.objects.filter(
            category__version=new_version
        ).count()
        source_item_count = MenuItem.objects.filter(
            category__version=version_with_items
        ).count()
        assert target_item_count == source_item_count

        target_variant_count = MenuItemVariant.objects.filter(
            menu_item__category__version=new_version
        ).count()
        source_variant_count = MenuItemVariant.objects.filter(
            menu_item__category__version=version_with_items
        ).count()
        assert target_variant_count == source_variant_count

    def test_source_version_is_unchanged(self, restaurant, version_with_items):
        original_item_count = MenuItem.objects.filter(
            category__version=version_with_items
        ).count()

        MenuVersionService.duplicate_version(version_with_items, "Copy")

        assert (
            MenuItem.objects.filter(category__version=version_with_items).count()
            == original_item_count
        )
