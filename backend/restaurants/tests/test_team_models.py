import pytest
from datetime import timedelta
from django.utils import timezone

from restaurants.models import RestaurantStaff
from restaurants.tests.factories import RestaurantStaffFactory, RestaurantFactory, UserFactory


@pytest.mark.django_db
class TestRestaurantStaffRoles:
    def test_role_choices(self):
        assert RestaurantStaff.StaffRole.OWNER == "owner"
        assert RestaurantStaff.StaffRole.ADMIN == "admin"
        assert RestaurantStaff.StaffRole.MEMBER == "member"

    def test_default_permissions_is_empty_dict(self):
        staff = RestaurantStaffFactory(role="member")
        assert staff.permissions == {}

    def test_permissions_stores_overrides(self):
        staff = RestaurantStaffFactory(role="member", permissions={"menu_edit": True})
        staff.refresh_from_db()
        assert staff.permissions == {"menu_edit": True}


@pytest.mark.django_db
class TestInvitationModel:
    def test_create_invitation(self):
        restaurant = RestaurantFactory()
        user = restaurant.owner
        from restaurants.models import Invitation
        invitation = Invitation.objects.create(
            restaurant=restaurant,
            email="new@example.com",
            role="member",
            invited_by=user,
        )
        assert invitation.token  # auto-generated
        assert len(invitation.token) > 20
        assert invitation.status == "pending"
        assert invitation.expires_at > timezone.now()

    def test_duplicate_pending_invite_blocked(self):
        restaurant = RestaurantFactory()
        from restaurants.models import Invitation
        Invitation.objects.create(
            restaurant=restaurant,
            email="dup@example.com",
            role="member",
            invited_by=restaurant.owner,
        )
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            Invitation.objects.create(
                restaurant=restaurant,
                email="dup@example.com",
                role="admin",
                invited_by=restaurant.owner,
            )

    def test_accepted_invite_allows_new_pending(self):
        restaurant = RestaurantFactory()
        from restaurants.models import Invitation
        inv = Invitation.objects.create(
            restaurant=restaurant,
            email="reuse@example.com",
            role="member",
            invited_by=restaurant.owner,
        )
        inv.status = "accepted"
        inv.save()
        new_inv = Invitation.objects.create(
            restaurant=restaurant,
            email="reuse@example.com",
            role="admin",
            invited_by=restaurant.owner,
        )
        assert new_inv.status == "pending"
