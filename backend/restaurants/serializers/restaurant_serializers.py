from rest_framework import serializers

from restaurants.models import (
    MenuCategory,
    MenuItem,
    MenuItemModifier,
    MenuItemVariant,
    Restaurant,
    RestaurantStaff,
    Subscription,
)


class RestaurantSerializer(serializers.ModelSerializer):
    subscription = serializers.SerializerMethodField()

    class Meta:
        model = Restaurant
        fields = [
            "id",
            "name",
            "slug",
            "phone",
            "address",
            "homepage",
            "logo_url",
            "tax_rate",
            "created_at",
            "subscription",
        ]
        read_only_fields = ["id", "created_at", "subscription"]

    def get_subscription(self, obj):
        try:
            sub = obj.subscription
        except Subscription.DoesNotExist:
            return None
        # Import here to avoid circular — SubscriptionSerializer is defined below
        return SubscriptionSerializer(sub).data

    def create(self, validated_data):
        from datetime import timedelta

        from django.conf import settings
        from django.utils import timezone

        validated_data["owner"] = self.context["request"].user
        restaurant = Restaurant.objects.create(**validated_data)
        # Auto-create owner staff record
        RestaurantStaff.objects.create(
            user=self.context["request"].user,
            restaurant=restaurant,
            role="owner",
        )
        # Auto-create trial subscription
        from restaurants.models import Subscription

        trial_end = timezone.now() + timedelta(days=settings.FREE_TRIAL_DAYS)
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            trial_end=trial_end,
            current_period_start=timezone.now(),
            current_period_end=trial_end,
            order_count=0,
        )
        return restaurant


class SubscriptionSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)
    order_limit = serializers.IntegerField(read_only=True)
    overage_count = serializers.IntegerField(read_only=True)
    plan_name = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "plan",
            "plan_name",
            "status",
            "trial_end",
            "current_period_start",
            "current_period_end",
            "cancel_at_period_end",
            "order_count",
            "order_limit",
            "overage_count",
            "is_active",
        ]

    def get_plan_name(self, obj):
        from django.conf import settings

        plan_config = settings.SUBSCRIPTION_PLANS.get(obj.plan, {})
        return plan_config.get("name", obj.plan.title())


class MenuCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuCategory
        fields = ["id", "name", "sort_order", "is_active"]


class MenuItemModifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItemModifier
        fields = ["id", "name", "price_adjustment"]


class MenuItemVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItemVariant
        fields = ["id", "label", "price", "is_default"]


class MenuItemSerializer(serializers.ModelSerializer):
    variants = MenuItemVariantSerializer(many=True, required=False)
    modifiers = MenuItemModifierSerializer(many=True, required=False)
    category_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = MenuItem
        fields = [
            "id",
            "category_id",
            "name",
            "description",
            "image_url",
            "is_active",
            "sort_order",
            "variants",
            "modifiers",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        variants_data = validated_data.pop("variants", [])
        modifiers_data = validated_data.pop("modifiers", [])
        category_id = validated_data.pop("category_id")

        # Verify category belongs to the restaurant
        restaurant = self.context["restaurant"]
        try:
            category = MenuCategory.objects.get(id=category_id, restaurant=restaurant)
        except MenuCategory.DoesNotExist:
            raise serializers.ValidationError({"category_id": "Invalid category."}) from None

        item = MenuItem.objects.create(category=category, **validated_data)

        for variant_data in variants_data:
            MenuItemVariant.objects.create(menu_item=item, **variant_data)
        for modifier_data in modifiers_data:
            MenuItemModifier.objects.create(menu_item=item, **modifier_data)

        return item

    def update(self, instance, validated_data):
        # For simplicity, variants/modifiers are not updated inline on PATCH.
        # They can be managed separately in a future iteration.
        validated_data.pop("variants", None)
        validated_data.pop("modifiers", None)
        validated_data.pop("category_id", None)
        return super().update(instance, validated_data)


class PublicMenuItemSerializer(serializers.ModelSerializer):
    variants = MenuItemVariantSerializer(many=True, read_only=True)
    modifiers = MenuItemModifierSerializer(many=True, read_only=True)

    class Meta:
        model = MenuItem
        fields = ["id", "name", "description", "image_url", "variants", "modifiers"]


class PublicMenuCategorySerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    class Meta:
        model = MenuCategory
        fields = ["id", "name", "items"]

    def get_items(self, obj):
        active_items = obj.items.filter(is_active=True).prefetch_related("variants", "modifiers")
        return PublicMenuItemSerializer(active_items, many=True).data


class PublicMenuSerializer(serializers.Serializer):
    restaurant_name = serializers.CharField()
    categories = PublicMenuCategorySerializer(many=True)
