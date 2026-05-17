import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from restaurants.models import Invitation, RestaurantStaff
from restaurants.services.team_service import TeamService
from restaurants.tests.factories import RestaurantFactory, RestaurantStaffFactory, UserFactory

User = get_user_model()


@pytest.mark.django_db
class TestInviteMember:
    def test_creates_invitation(self):
        restaurant = RestaurantFactory()
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="new@example.com",
            role="member",
            permissions={},
            invited_by=restaurant.owner,
        )
        assert invitation.status == "pending"
        assert invitation.email == "new@example.com"
        assert invitation.role == "member"
        assert len(invitation.token) > 20

    def test_rejects_existing_staff(self):
        restaurant = RestaurantFactory()
        staff_user = UserFactory(email="exists@example.com")
        RestaurantStaffFactory(user=staff_user, restaurant=restaurant, role="member")
        with pytest.raises(ValidationError, match="already on your team"):
            TeamService.invite_member(
                restaurant=restaurant,
                email="exists@example.com",
                role="admin",
                permissions={},
                invited_by=restaurant.owner,
            )

    def test_rejects_owner_email(self):
        restaurant = RestaurantFactory()
        with pytest.raises(ValidationError, match="owner"):
            TeamService.invite_member(
                restaurant=restaurant,
                email=restaurant.owner.email,
                role="admin",
                permissions={},
                invited_by=restaurant.owner,
            )

    def test_rejects_duplicate_pending(self):
        restaurant = RestaurantFactory()
        TeamService.invite_member(
            restaurant=restaurant,
            email="dup@example.com",
            role="member",
            permissions={},
            invited_by=restaurant.owner,
        )
        with pytest.raises(ValidationError, match="already pending"):
            TeamService.invite_member(
                restaurant=restaurant,
                email="dup@example.com",
                role="admin",
                permissions={},
                invited_by=restaurant.owner,
            )


@pytest.mark.django_db
class TestAcceptInvitation:
    def test_existing_user_accepts(self):
        restaurant = RestaurantFactory()
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="joiner@example.com",
            role="member",
            permissions={"menu_edit": True},
            invited_by=restaurant.owner,
        )
        user = UserFactory(email="joiner@example.com")
        staff = TeamService.accept_invitation(invitation.token, user=user)
        assert staff.user == user
        assert staff.role == "member"
        assert staff.permissions == {"menu_edit": True}
        invitation.refresh_from_db()
        assert invitation.status == "accepted"

    def test_new_user_registers_and_accepts(self):
        restaurant = RestaurantFactory()
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="brand-new@example.com",
            role="admin",
            permissions={},
            invited_by=restaurant.owner,
        )
        staff = TeamService.accept_invitation(
            invitation.token,
            registration_data={
                "first_name": "New",
                "last_name": "Person",
                "password": "securepass123",
            },
        )
        assert staff.user.email == "brand-new@example.com"
        assert staff.role == "admin"
        assert User.objects.filter(email="brand-new@example.com").exists()

    def test_expired_token_rejected(self):
        restaurant = RestaurantFactory()
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="late@example.com",
            role="member",
            permissions={},
            invited_by=restaurant.owner,
        )
        from datetime import timedelta
        from django.utils import timezone
        invitation.expires_at = timezone.now() - timedelta(days=1)
        invitation.save()
        with pytest.raises(ValidationError, match="expired"):
            TeamService.accept_invitation(invitation.token)

    def test_no_user_no_registration_data_rejected(self):
        restaurant = RestaurantFactory()
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="nobody@example.com",
            role="member",
            permissions={},
            invited_by=restaurant.owner,
        )
        with pytest.raises(ValidationError, match="registration details"):
            TeamService.accept_invitation(invitation.token)

    def test_already_accepted_token_rejected(self):
        restaurant = RestaurantFactory()
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="used@example.com",
            role="member",
            permissions={},
            invited_by=restaurant.owner,
        )
        user = UserFactory(email="used@example.com")
        TeamService.accept_invitation(invitation.token, user=user)
        with pytest.raises(ValidationError, match="Invalid or already used"):
            TeamService.accept_invitation(invitation.token)


@pytest.mark.django_db
class TestUpdateMember:
    def test_change_role(self):
        restaurant = RestaurantFactory()
        member = UserFactory()
        staff = RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        updated = TeamService.update_member(
            restaurant=restaurant,
            staff_id=staff.id,
            role="admin",
            acting_user=restaurant.owner,
        )
        assert updated.role == "admin"

    def test_cannot_demote_owner(self):
        restaurant = RestaurantFactory()
        owner_staff = RestaurantStaffFactory(
            user=restaurant.owner, restaurant=restaurant, role="owner"
        )
        admin = UserFactory()
        RestaurantStaffFactory(user=admin, restaurant=restaurant, role="admin")
        with pytest.raises(ValidationError, match="cannot"):
            TeamService.update_member(
                restaurant=restaurant,
                staff_id=owner_staff.id,
                role="member",
                acting_user=admin,
            )


@pytest.mark.django_db
class TestRemoveMember:
    def test_remove_member(self):
        restaurant = RestaurantFactory()
        member = UserFactory()
        staff = RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        TeamService.remove_member(
            restaurant=restaurant,
            staff_id=staff.id,
            acting_user=restaurant.owner,
        )
        assert not RestaurantStaff.objects.filter(id=staff.id).exists()

    def test_cannot_remove_owner(self):
        restaurant = RestaurantFactory()
        owner_staff = RestaurantStaffFactory(
            user=restaurant.owner, restaurant=restaurant, role="owner"
        )
        admin = UserFactory()
        RestaurantStaffFactory(user=admin, restaurant=restaurant, role="admin")
        with pytest.raises(ValidationError, match="cannot remove the owner"):
            TeamService.remove_member(
                restaurant=restaurant,
                staff_id=owner_staff.id,
                acting_user=admin,
            )


@pytest.mark.django_db
class TestTransferOwnership:
    def test_transfer_to_admin(self):
        restaurant = RestaurantFactory()
        old_owner = restaurant.owner
        RestaurantStaffFactory(user=old_owner, restaurant=restaurant, role="owner")
        new_owner = UserFactory()
        RestaurantStaffFactory(user=new_owner, restaurant=restaurant, role="admin")
        TeamService.transfer_ownership(
            restaurant=restaurant,
            new_owner_id=str(new_owner.id),
            acting_user=old_owner,
        )
        restaurant.refresh_from_db()
        assert restaurant.owner == new_owner
        new_owner_staff = RestaurantStaff.objects.get(user=new_owner, restaurant=restaurant)
        assert new_owner_staff.role == "owner"
        old_owner_staff = RestaurantStaff.objects.get(user=old_owner, restaurant=restaurant)
        assert old_owner_staff.role == "admin"

    def test_non_owner_cannot_transfer(self):
        restaurant = RestaurantFactory()
        admin = UserFactory()
        RestaurantStaffFactory(user=admin, restaurant=restaurant, role="admin")
        target = UserFactory()
        RestaurantStaffFactory(user=target, restaurant=restaurant, role="admin")
        with pytest.raises(ValidationError, match="Only the owner"):
            TeamService.transfer_ownership(
                restaurant=restaurant,
                new_owner_id=str(target.id),
                acting_user=admin,
            )


@pytest.mark.django_db
class TestGetEffectivePermissions:
    def test_owner_gets_all(self):
        restaurant = RestaurantFactory()
        perms = TeamService.get_effective_permissions(restaurant.owner, restaurant)
        assert perms["role"] == "owner"
        assert perms["menu_edit"] is True
        assert perms["order_manage"] is True
        assert perms["is_admin"] is True

    def test_member_with_override(self):
        restaurant = RestaurantFactory()
        member = UserFactory()
        RestaurantStaffFactory(
            user=member, restaurant=restaurant, role="member",
            permissions={"menu_edit": True},
        )
        perms = TeamService.get_effective_permissions(member, restaurant)
        assert perms["role"] == "member"
        assert perms["menu_edit"] is True
        assert perms["order_manage"] is False
        assert perms["is_admin"] is False
