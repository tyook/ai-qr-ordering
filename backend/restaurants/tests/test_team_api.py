import pytest
from unittest.mock import MagicMock, patch
from rest_framework import status

from restaurants.models import Invitation, RestaurantStaff
from restaurants.tests.factories import RestaurantFactory, RestaurantStaffFactory, UserFactory


@pytest.mark.django_db
class TestTeamListView:
    def test_owner_can_list_team(self, api_client):
        restaurant = RestaurantFactory()
        RestaurantStaffFactory(user=restaurant.owner, restaurant=restaurant, role="owner")
        api_client.force_authenticate(user=restaurant.owner)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/team/")
        assert response.status_code == status.HTTP_200_OK
        assert "members" in response.data
        assert "invitations" in response.data

    def test_member_cannot_list_team(self, api_client):
        restaurant = RestaurantFactory()
        member = UserFactory()
        RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        api_client.force_authenticate(user=member)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/team/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestInviteView:
    def test_owner_can_invite(self, api_client):
        mock_task = MagicMock()
        restaurant = RestaurantFactory()
        RestaurantStaffFactory(user=restaurant.owner, restaurant=restaurant, role="owner")
        api_client.force_authenticate(user=restaurant.owner)
        with patch("restaurants.tasks.send_invitation_email_task", mock_task, create=True):
            response = api_client.post(
                f"/api/restaurants/{restaurant.slug}/team/invite/",
                {"email": "new@example.com", "role": "member"},
                format="json",
            )
        assert response.status_code == status.HTTP_201_CREATED
        assert Invitation.objects.filter(email="new@example.com").exists()


@pytest.mark.django_db
class TestRemoveMemberView:
    def test_owner_can_remove_member(self, api_client):
        restaurant = RestaurantFactory()
        RestaurantStaffFactory(user=restaurant.owner, restaurant=restaurant, role="owner")
        member = UserFactory()
        staff = RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        api_client.force_authenticate(user=restaurant.owner)
        response = api_client.delete(f"/api/restaurants/{restaurant.slug}/team/{staff.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not RestaurantStaff.objects.filter(id=staff.id).exists()


@pytest.mark.django_db
class TestInvitationAcceptView:
    def test_existing_user_can_accept(self, api_client):
        restaurant = RestaurantFactory()
        from restaurants.services.team_service import TeamService
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="joiner@example.com",
            role="member",
            permissions={"menu_edit": True},
            invited_by=restaurant.owner,
        )
        user = UserFactory(email="joiner@example.com")
        api_client.force_authenticate(user=user)
        response = api_client.post(f"/api/invitations/{invitation.token}/accept/")
        assert response.status_code == status.HTTP_200_OK
        assert RestaurantStaff.objects.filter(user=user, restaurant=restaurant).exists()

    def test_new_user_registers_and_accepts(self, api_client):
        restaurant = RestaurantFactory()
        from restaurants.services.team_service import TeamService
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="brand-new@example.com",
            role="admin",
            permissions={},
            invited_by=restaurant.owner,
        )
        response = api_client.post(
            f"/api/invitations/{invitation.token}/accept/",
            {"first_name": "New", "last_name": "User", "password": "securepass123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert RestaurantStaff.objects.filter(
            user__email="brand-new@example.com", restaurant=restaurant
        ).exists()

    def test_validate_invitation(self, api_client):
        restaurant = RestaurantFactory()
        from restaurants.services.team_service import TeamService
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="check@example.com",
            role="member",
            permissions={},
            invited_by=restaurant.owner,
        )
        response = api_client.get(f"/api/invitations/{invitation.token}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["restaurant_name"] == restaurant.name
        assert response.data["role"] == "member"


@pytest.mark.django_db
class TestMyRoleView:
    def test_returns_role_and_permissions(self, api_client):
        restaurant = RestaurantFactory()
        member = UserFactory()
        RestaurantStaffFactory(
            user=member, restaurant=restaurant, role="member",
            permissions={"menu_edit": True},
        )
        api_client.force_authenticate(user=member)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/my-role/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "member"
        assert response.data["menu_edit"] is True
        assert response.data["order_manage"] is False
