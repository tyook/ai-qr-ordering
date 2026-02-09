from restaurants.models import Restaurant, MenuCategory


def build_menu_context(restaurant: Restaurant) -> str:
    """
    Build a text representation of the restaurant's menu for the LLM prompt.
    Includes item IDs so the LLM can reference them in its response.
    """
    lines = [f"Restaurant: {restaurant.name}", ""]

    categories = (
        MenuCategory.objects.filter(restaurant=restaurant, is_active=True)
        .prefetch_related("items__variants", "items__modifiers")
        .order_by("sort_order")
    )

    for category in categories:
        lines.append(f"## {category.name}")
        active_items = category.items.filter(is_active=True).order_by("sort_order")

        for item in active_items:
            lines.append(f"  - {item.name} (item_id: {item.id})")
            if item.description:
                lines.append(f"    Description: {item.description}")

            variants = item.variants.all()
            if variants:
                lines.append("    Sizes/Variants (pick one):")
                for v in variants:
                    default_marker = " [DEFAULT]" if v.is_default else ""
                    lines.append(
                        f"      * {v.label}: ${v.price}{default_marker} (variant_id: {v.id})"
                    )

            modifiers = item.modifiers.all()
            if modifiers:
                lines.append("    Modifiers (optional, pick any):")
                for m in modifiers:
                    price_str = (
                        f"+${m.price_adjustment}" if m.price_adjustment else "free"
                    )
                    lines.append(
                        f"      * {m.name}: {price_str} (modifier_id: {m.id})"
                    )

        lines.append("")

    return "\n".join(lines)
