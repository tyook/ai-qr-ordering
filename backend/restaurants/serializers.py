from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from restaurants.models import Restaurant, RestaurantStaff, MenuCategory, MenuItem, MenuItemVariant, MenuItemModifier

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["email", "password", "first_name", "last_name"]

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

    def to_representation(self, instance):
        refresh = RefreshToken.for_user(instance)
        return {
            "user": {
                "id": str(instance.id),
                "email": instance.email,
                "first_name": instance.first_name,
                "last_name": instance.last_name,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = User.objects.filter(email=data["email"]).first()
        if not user or not user.check_password(data["password"]):
            raise serializers.ValidationError("Invalid email or password.")
        data["user"] = user
        return data


class RestaurantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = ["id", "name", "slug", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        restaurant = Restaurant.objects.create(**validated_data)
        # Auto-create owner staff record
        RestaurantStaff.objects.create(
            user=self.context["request"].user,
            restaurant=restaurant,
            role="owner",
        )
        return restaurant


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
            "id", "category_id", "name", "description", "image_url",
            "is_active", "sort_order", "variants", "modifiers",
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
            raise serializers.ValidationError({"category_id": "Invalid category."})

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
        active_items = obj.items.filter(is_active=True).prefetch_related(
            "variants", "modifiers"
        )
        return PublicMenuItemSerializer(active_items, many=True).data


class PublicMenuSerializer(serializers.Serializer):
    restaurant_name = serializers.CharField()
    categories = PublicMenuCategorySerializer(many=True)
