from rest_framework import serializers

from restaurants.models import Invitation, RestaurantStaff


class StaffMemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    user_id = serializers.UUIDField(source="user.id", read_only=True)

    class Meta:
        model = RestaurantStaff
        fields = ["id", "user_id", "email", "first_name", "last_name", "role", "permissions", "invited_at"]


class InvitationSerializer(serializers.ModelSerializer):
    invited_by_name = serializers.CharField(source="invited_by.name", read_only=True)

    class Meta:
        model = Invitation
        fields = ["id", "email", "role", "permissions", "status", "invited_by_name", "created_at", "expires_at"]


class InviteMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=["admin", "member"])
    permissions = serializers.DictField(child=serializers.BooleanField(), required=False, default=dict)


class UpdateMemberSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["admin", "member"], required=False)
    permissions = serializers.DictField(child=serializers.BooleanField(), required=False)


class TransferOwnershipSerializer(serializers.Serializer):
    new_owner_id = serializers.UUIDField()


class AcceptInvitationSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    password = serializers.CharField(required=False, min_length=8)
    auth_provider = serializers.ChoiceField(choices=["google", "apple"], required=False)
    auth_token = serializers.CharField(required=False)


class InvitationDetailSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)
    restaurant_slug = serializers.CharField(source="restaurant.slug", read_only=True)
    invited_by_name = serializers.CharField(source="invited_by.name", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invitation
        fields = [
            "id", "restaurant_name", "restaurant_slug", "email", "role",
            "permissions", "status", "invited_by_name", "is_expired", "expires_at",
        ]
