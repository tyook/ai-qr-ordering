from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from restaurants.models import Invitation, Restaurant, RestaurantStaff

User = get_user_model()


class TeamService:

    @staticmethod
    def invite_member(restaurant, email, role, permissions, invited_by):
        if restaurant.owner.email == email:
            raise ValidationError("This person is the owner.")
        if RestaurantStaff.objects.filter(
            restaurant=restaurant, user__email=email
        ).exists():
            raise ValidationError("This person is already on your team.")
        if Invitation.objects.filter(
            restaurant=restaurant, email=email, status="pending"
        ).exists():
            raise ValidationError("Invitation already pending — resend or revoke it first.")

        invitation = Invitation.objects.create(
            restaurant=restaurant,
            email=email,
            role=role,
            permissions=permissions or {},
            invited_by=invited_by,
        )
        return invitation

    @staticmethod
    @transaction.atomic
    def accept_invitation(token, user=None, registration_data=None):
        try:
            invitation = Invitation.objects.select_related("restaurant").get(
                token=token, status="pending"
            )
        except Invitation.DoesNotExist:
            raise ValidationError("Invalid or already used invitation.")

        if invitation.is_expired:
            invitation.status = "expired"
            invitation.save(update_fields=["status"])
            raise ValidationError("This invitation has expired.")

        if user is None and registration_data:
            user = User.objects.create_user(
                email=invitation.email,
                first_name=registration_data.get("first_name", ""),
                last_name=registration_data.get("last_name", ""),
                password=registration_data["password"],
            )
        elif user is None:
            existing = User.objects.filter(email=invitation.email).first()
            if existing:
                user = existing
            else:
                raise ValidationError("Please provide registration details or log in.")

        staff = RestaurantStaff.objects.create(
            user=user,
            restaurant=invitation.restaurant,
            role=invitation.role,
            permissions=invitation.permissions,
        )
        invitation.status = "accepted"
        invitation.save(update_fields=["status"])
        return staff

    @staticmethod
    def update_member(restaurant, staff_id, role=None, permissions=None, acting_user=None):
        try:
            staff = RestaurantStaff.objects.get(id=staff_id, restaurant=restaurant)
        except RestaurantStaff.DoesNotExist:
            raise ValidationError("Team member not found.")

        if staff.role == "owner":
            raise ValidationError("You cannot change the owner's role.")

        if role is not None:
            staff.role = role
        if permissions is not None:
            staff.permissions = permissions
        staff.save()
        return staff

    @staticmethod
    def remove_member(restaurant, staff_id, acting_user):
        try:
            staff = RestaurantStaff.objects.get(id=staff_id, restaurant=restaurant)
        except RestaurantStaff.DoesNotExist:
            raise ValidationError("Team member not found.")

        if staff.role == "owner":
            raise ValidationError("You cannot remove the owner.")

        staff.delete()

    @staticmethod
    @transaction.atomic
    def transfer_ownership(restaurant, new_owner_id, acting_user):
        if restaurant.owner != acting_user:
            raise ValidationError("Only the owner can transfer ownership.")

        try:
            new_owner = User.objects.get(id=new_owner_id)
        except User.DoesNotExist:
            raise ValidationError("User not found.")

        if not RestaurantStaff.objects.filter(
            user=new_owner, restaurant=restaurant, role__in=["admin", "owner"]
        ).exists():
            raise ValidationError("Can only transfer ownership to an existing admin.")

        old_owner = restaurant.owner
        restaurant.owner = new_owner
        restaurant.save(update_fields=["owner"])

        RestaurantStaff.objects.filter(
            user=new_owner, restaurant=restaurant
        ).update(role="owner")
        RestaurantStaff.objects.filter(
            user=old_owner, restaurant=restaurant
        ).update(role="admin")

    @staticmethod
    def get_effective_permissions(user, restaurant):
        is_owner = restaurant.owner == user
        if is_owner:
            return {
                "role": "owner",
                "is_admin": True,
                "menu_edit": True,
                "order_manage": True,
            }
        try:
            staff = RestaurantStaff.objects.get(user=user, restaurant=restaurant)
        except RestaurantStaff.DoesNotExist:
            return None

        if staff.role == "admin":
            return {
                "role": "admin",
                "is_admin": True,
                "menu_edit": True,
                "order_manage": True,
            }

        return {
            "role": "member",
            "is_admin": False,
            "menu_edit": staff.permissions.get("menu_edit", False),
            "order_manage": staff.permissions.get("order_manage", False),
        }
