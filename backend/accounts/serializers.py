from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import User
from accounts.services import split_name


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True, validators=[validate_password])
    first_name = serializers.CharField(max_length=150, required=False, default="")
    last_name = serializers.CharField(max_length=150, required=False, default="")
    name = serializers.CharField(max_length=255, required=False, default="")
    phone = serializers.CharField(max_length=20, required=False, default="")
    link_order_id = serializers.UUIDField(required=False, allow_null=True, default=None)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate(self, data):
        if data.get("name") and not data.get("first_name"):
            data["first_name"], data["last_name"] = split_name(data["name"])
        if not data.get("first_name"):
            raise serializers.ValidationError({"first_name": "First name is required."})
        return data

    def create(self, validated_data):
        validated_data.pop("name", None)
        link_order_id = validated_data.pop("link_order_id", None)
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)

        if link_order_id:
            from accounts.services import link_order_to_user
            link_order_to_user(str(link_order_id), user)

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = User.objects.filter(email__iexact=data["email"]).first()
        if not user or not user.check_password(data["password"]):
            raise serializers.ValidationError("Invalid email or password.")
        data["user"] = user
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    is_restaurant_owner = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "name",
            "phone", "dietary_preferences", "allergies",
            "preferred_language", "auth_provider", "is_restaurant_owner",
            "date_joined", "onboarding_completed", "onboarding_dismissed",
        ]
        read_only_fields = [
            "id", "email", "auth_provider", "date_joined",
            "onboarding_completed", "onboarding_dismissed",
        ]
