from rest_framework import serializers

from restaurants.models import (
    HolidayOverride,
    MenuCategory,
    MenuItem,
    MenuItemModifier,
    MenuItemVariant,
    OperatingHours,
    Restaurant,
    RestaurantStaff,
    Subscription,
    Table,
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
            "street_address",
            "city",
            "state",
            "zip_code",
            "country",
            "google_place_id",
            "latitude",
            "longitude",
            "homepage",
            "logo_url",
            "tax_rate",
            "payment_model",
            "accepting_orders",
            "auto_resume_orders",
            "created_at",
            "subscription",
        ]
        read_only_fields = ["id", "slug", "created_at", "subscription"]

    def get_subscription(self, obj):
        try:
            sub = obj.subscription
        except Subscription.DoesNotExist:
            return None
        # Import here to avoid circular — SubscriptionSerializer is defined below
        return SubscriptionSerializer(sub).data

    @staticmethod
    def _generate_unique_slug(name, exclude_pk=None):
        from django.db import IntegrityError
        from django.utils.text import slugify

        base_slug = slugify(name)
        if not base_slug:
            base_slug = "restaurant"
        slug = base_slug
        suffix = 2
        while True:
            qs = Restaurant.objects.filter(slug=slug)
            if exclude_pk:
                qs = qs.exclude(pk=exclude_pk)
            if not qs.exists():
                return slug
            slug = f"{base_slug}-{suffix}"
            suffix += 1

    def create(self, validated_data):
        from datetime import timedelta

        from django.conf import settings
        from django.utils import timezone

        validated_data["owner"] = self.context["request"].user
        validated_data["slug"] = self._generate_unique_slug(validated_data["name"])
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
        from restaurants.tasks import send_merchant_welcome_email_task
        send_merchant_welcome_email_task.delay(str(restaurant.id))
        return restaurant

    def update(self, instance, validated_data):
        if "name" in validated_data and validated_data["name"] != instance.name:
            validated_data["slug"] = self._generate_unique_slug(
                validated_data["name"], exclude_pk=instance.pk
            )
        return super().update(instance, validated_data)


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
    id = serializers.IntegerField(required=False)

    class Meta:
        model = MenuItemModifier
        fields = ["id", "name", "price_adjustment"]


class MenuItemVariantSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

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
            "status",
            "is_upsellable",
            "is_featured",
            "sort_order",
            "variants",
            "modifiers",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        variants_data = validated_data.pop("variants", [])
        modifiers_data = validated_data.pop("modifiers", [])
        category_id = validated_data.pop("category_id")

        # Verify category belongs to the active menu version
        active_version = self.context.get("active_version")
        if active_version is None:
            raise serializers.ValidationError({"category_id": "No active menu version found."})
        try:
            category = MenuCategory.objects.get(id=category_id, version=active_version)
        except MenuCategory.DoesNotExist:
            raise serializers.ValidationError({"category_id": "Invalid category."}) from None

        item = MenuItem.objects.create(category=category, **validated_data)

        for variant_data in variants_data:
            MenuItemVariant.objects.create(menu_item=item, **variant_data)
        for modifier_data in modifiers_data:
            MenuItemModifier.objects.create(menu_item=item, **modifier_data)

        return item

    def update(self, instance, validated_data):
        variants_data = validated_data.pop("variants", None)
        modifiers_data = validated_data.pop("modifiers", None)
        validated_data.pop("category_id", None)
        instance = super().update(instance, validated_data)

        if variants_data is not None:
            incoming_ids = {v["id"] for v in variants_data if v.get("id")}
            # Delete variants not in the incoming list
            instance.variants.exclude(id__in=incoming_ids).delete()
            # Update existing / create new
            for variant_data in variants_data:
                variant_id = variant_data.get("id")
                if variant_id:
                    try:
                        variant = instance.variants.get(id=variant_id)
                        for attr, value in variant_data.items():
                            if attr != "id":
                                setattr(variant, attr, value)
                        variant.save()
                    except MenuItemVariant.DoesNotExist:
                        pass
                else:
                    data = {k: v for k, v in variant_data.items() if k != "id"}
                    MenuItemVariant.objects.create(menu_item=instance, **data)

        if modifiers_data is not None:
            incoming_ids = {m["id"] for m in modifiers_data if m.get("id")}
            instance.modifiers.exclude(id__in=incoming_ids).delete()
            for modifier_data in modifiers_data:
                modifier_id = modifier_data.get("id")
                if modifier_id:
                    try:
                        modifier = instance.modifiers.get(id=modifier_id)
                        for attr, value in modifier_data.items():
                            if attr != "id":
                                setattr(modifier, attr, value)
                        modifier.save()
                    except MenuItemModifier.DoesNotExist:
                        pass
                else:
                    data = {k: v for k, v in modifier_data.items() if k != "id"}
                    MenuItemModifier.objects.create(menu_item=instance, **data)

        return instance


class PublicMenuItemSerializer(serializers.ModelSerializer):
    variants = MenuItemVariantSerializer(many=True, read_only=True)
    modifiers = MenuItemModifierSerializer(many=True, read_only=True)
    is_sold_out = serializers.SerializerMethodField()

    class Meta:
        model = MenuItem
        fields = ["id", "name", "description", "image_url", "is_sold_out", "is_featured", "variants", "modifiers"]

    def get_is_sold_out(self, obj):
        return obj.status == MenuItem.Status.SOLD_OUT


class PublicMenuCategorySerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    class Meta:
        model = MenuCategory
        fields = ["id", "name", "items"]

    def get_items(self, obj):
        visible_items = obj.items.filter(
            status__in=[MenuItem.Status.ACTIVE, MenuItem.Status.SOLD_OUT]
        ).prefetch_related("variants", "modifiers")
        return PublicMenuItemSerializer(visible_items, many=True).data


class PublicMenuSerializer(serializers.Serializer):
    restaurant_name = serializers.CharField()
    categories = PublicMenuCategorySerializer(many=True)


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ["id", "name", "number", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_number(self, value):
        import re

        if not re.match(r"^[A-Za-z0-9_-]+$", value):
            raise serializers.ValidationError(
                "Table number must contain only letters, numbers, hyphens, or underscores."
            )
        return value


class OperatingHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperatingHours
        fields = ["id", "day_of_week", "open_time", "close_time"]
        read_only_fields = ["id"]


class HolidayOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = HolidayOverride
        fields = ["id", "date", "label", "is_closed", "open_time", "close_time"]
        read_only_fields = ["id"]

    def validate(self, data):
        is_closed = data.get("is_closed", True)
        if not is_closed:
            if not data.get("open_time") or not data.get("close_time"):
                raise serializers.ValidationError(
                    "open_time and close_time are required when not closed."
                )
        return data
