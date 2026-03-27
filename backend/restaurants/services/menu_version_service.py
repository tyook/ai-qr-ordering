"""
MenuVersionService — manages menu version lifecycle.

Provides methods for creating, activating, deleting, renaming, listing,
and duplicating MenuVersion objects and their associated categories/items.
"""

from datetime import date

from django.db import transaction

from restaurants.models import (
    MenuCategory,
    MenuItem,
    MenuItemModifier,
    MenuItemVariant,
    MenuVersion,
    Restaurant,
)


class MenuVersionService:
    # ── Name Generation ────────────────────────────────────────────────────────

    @staticmethod
    def generate_default_name(restaurant: Restaurant) -> str:
        """
        Return a default version name like "Menu - Mar 27, 2026".

        If a version with that name already exists for the restaurant, append
        a counter: "Menu - Mar 27, 2026 (2)", "Menu - Mar 27, 2026 (3)", etc.
        """
        today = date.today()
        base_name = f"Menu - {today.strftime('%b %-d, %Y')}"

        existing_names = set(
            MenuVersion.objects.filter(restaurant=restaurant).values_list("name", flat=True)
        )

        if base_name not in existing_names:
            return base_name

        counter = 2
        while True:
            candidate = f"{base_name} ({counter})"
            if candidate not in existing_names:
                return candidate
            counter += 1

    # ── Activation ─────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def activate_version(restaurant: Restaurant, version: MenuVersion) -> MenuVersion:
        """
        Atomically deactivate all versions for the restaurant, then activate
        the given one. Returns the activated version.
        """
        MenuVersion.objects.filter(restaurant=restaurant).update(is_active=False)
        version.is_active = True
        version.save(update_fields=["is_active", "updated_at"])
        return version

    # ── Deletion ───────────────────────────────────────────────────────────────

    @staticmethod
    def delete_version(version: MenuVersion) -> None:
        """
        Delete the given version. Raises ValueError if the version is active.
        """
        if version.is_active:
            raise ValueError("Cannot delete the active menu version.")
        version.delete()

    # ── Rename ─────────────────────────────────────────────────────────────────

    @staticmethod
    def rename_version(version: MenuVersion, new_name: str) -> MenuVersion:
        """
        Rename the given version. Returns the updated version.
        """
        version.name = new_name
        version.save(update_fields=["name", "updated_at"])
        return version

    # ── List ───────────────────────────────────────────────────────────────────

    @staticmethod
    def list_versions(restaurant: Restaurant) -> list[dict]:
        """
        Return a list of dicts describing all versions for the restaurant.

        Each dict has: id, name, is_active, source, created_at, item_count.
        """
        versions = MenuVersion.objects.filter(restaurant=restaurant).prefetch_related(
            "categories__items"
        )
        result = []
        for version in versions:
            item_count = sum(
                category.items.count() for category in version.categories.all()
            )
            result.append(
                {
                    "id": version.id,
                    "name": version.name,
                    "is_active": version.is_active,
                    "source": version.source,
                    "created_at": version.created_at,
                    "item_count": item_count,
                }
            )
        return result

    # ── Duplication ────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def duplicate_version_into(source: MenuVersion, target: MenuVersion) -> MenuVersion:
        """
        Copy all categories, items, variants, and modifiers from source into
        target. Returns the target version.
        """
        for category in source.categories.prefetch_related(
            "items__variants", "items__modifiers"
        ).all():
            new_category = MenuCategory.objects.create(
                version=target,
                name=category.name,
                sort_order=category.sort_order,
                is_active=category.is_active,
            )
            for item in category.items.all():
                new_item = MenuItem.objects.create(
                    category=new_category,
                    name=item.name,
                    description=item.description,
                    image_url=item.image_url,
                    is_active=item.is_active,
                    sort_order=item.sort_order,
                )
                for variant in item.variants.all():
                    MenuItemVariant.objects.create(
                        menu_item=new_item,
                        label=variant.label,
                        price=variant.price,
                        is_default=variant.is_default,
                    )
                for modifier in item.modifiers.all():
                    MenuItemModifier.objects.create(
                        menu_item=new_item,
                        name=modifier.name,
                        price_adjustment=modifier.price_adjustment,
                    )
        return target

    @staticmethod
    @transaction.atomic
    def duplicate_version(source: MenuVersion, new_name: str) -> MenuVersion:
        """
        Create a new MenuVersion with new_name for the same restaurant, then
        copy all data from source into it. Returns the new version.
        """
        target = MenuVersion.objects.create(
            restaurant=source.restaurant,
            name=new_name,
            source=source.source,
            is_active=False,
        )
        MenuVersionService.duplicate_version_into(source, target)
        return target
