from decimal import Decimal

from restaurants.models import Restaurant, MenuItem, MenuItemVariant, MenuItemModifier
from orders.llm.base import ParsedOrder


def validate_and_price_order(restaurant: Restaurant, parsed: ParsedOrder) -> dict:
    """
    Validate LLM-parsed order items against the database.
    Calculate prices server-side. Drop any invalid items.
    Returns a dict ready for the frontend confirmation step.
    """
    validated_items = []
    total_price = Decimal("0.00")

    for parsed_item in parsed.items:
        try:
            menu_item = MenuItem.objects.get(
                id=parsed_item.menu_item_id,
                category__restaurant=restaurant,
                is_active=True,
            )
            variant = MenuItemVariant.objects.get(
                id=parsed_item.variant_id,
                menu_item=menu_item,
            )
        except (MenuItem.DoesNotExist, MenuItemVariant.DoesNotExist):
            continue  # Skip invalid items

        # Validate modifiers
        valid_modifiers = []
        for mod_id in parsed_item.modifier_ids:
            try:
                modifier = MenuItemModifier.objects.get(
                    id=mod_id, menu_item=menu_item
                )
                valid_modifiers.append(
                    {
                        "id": modifier.id,
                        "name": modifier.name,
                        "price_adjustment": str(modifier.price_adjustment),
                    }
                )
            except MenuItemModifier.DoesNotExist:
                continue  # Skip invalid modifiers

        item_price = variant.price * parsed_item.quantity
        modifier_total = sum(
            Decimal(m["price_adjustment"]) for m in valid_modifiers
        ) * parsed_item.quantity
        line_total = item_price + modifier_total
        total_price += line_total

        validated_items.append(
            {
                "menu_item_id": menu_item.id,
                "name": menu_item.name,
                "variant": {
                    "id": variant.id,
                    "label": variant.label,
                    "price": str(variant.price),
                },
                "quantity": parsed_item.quantity,
                "modifiers": valid_modifiers,
                "special_requests": parsed_item.special_requests,
                "line_total": str(line_total),
            }
        )

    return {
        "items": validated_items,
        "total_price": str(total_price),
        "language": parsed.language,
    }
