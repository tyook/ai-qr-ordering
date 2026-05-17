import pytest
from unittest.mock import MagicMock

from restaurants.models import RestaurantStaff
from restaurants.permissions import IsRestaurantAdmin, HasPermission
from restaurants.tests.factories import RestaurantFactory, RestaurantStaffFactory, UserFactory


def _make_request(user):
    request = MagicMock()
    request.user = user
    request.method = "POST"
    return request


def _make_view(slug):
    view = MagicMock()
    view.kwargs = {"slug": slug}
    return view


@pytest.mark.django_db
class TestIsRestaurantAdmin:
    def test_owner_allowed(self):
        restaurant = RestaurantFactory()
        request = _make_request(restaurant.owner)
        view = _make_view(restaurant.slug)
        assert IsRestaurantAdmin().has_permission(request, view) is True

    def test_admin_allowed(self):
        restaurant = RestaurantFactory()
        admin_user = UserFactory()
        RestaurantStaffFactory(user=admin_user, restaurant=restaurant, role="admin")
        request = _make_request(admin_user)
        view = _make_view(restaurant.slug)
        assert IsRestaurantAdmin().has_permission(request, view) is True

    def test_member_denied(self):
        restaurant = RestaurantFactory()
        member_user = UserFactory()
        RestaurantStaffFactory(user=member_user, restaurant=restaurant, role="member")
        request = _make_request(member_user)
        view = _make_view(restaurant.slug)
        assert IsRestaurantAdmin().has_permission(request, view) is False

    def test_stranger_denied(self):
        restaurant = RestaurantFactory()
        stranger = UserFactory()
        request = _make_request(stranger)
        view = _make_view(restaurant.slug)
        assert IsRestaurantAdmin().has_permission(request, view) is False


@pytest.mark.django_db
class TestHasPermission:
    def test_owner_auto_passes(self):
        restaurant = RestaurantFactory()
        request = _make_request(restaurant.owner)
        view = _make_view(restaurant.slug)
        assert HasPermission("menu_edit").has_permission(request, view) is True

    def test_admin_auto_passes(self):
        restaurant = RestaurantFactory()
        admin_user = UserFactory()
        RestaurantStaffFactory(user=admin_user, restaurant=restaurant, role="admin")
        request = _make_request(admin_user)
        view = _make_view(restaurant.slug)
        assert HasPermission("menu_edit").has_permission(request, view) is True

    def test_member_with_permission_allowed(self):
        restaurant = RestaurantFactory()
        member = UserFactory()
        RestaurantStaffFactory(
            user=member, restaurant=restaurant, role="member",
            permissions={"menu_edit": True},
        )
        request = _make_request(member)
        view = _make_view(restaurant.slug)
        assert HasPermission("menu_edit").has_permission(request, view) is True

    def test_member_without_permission_denied(self):
        restaurant = RestaurantFactory()
        member = UserFactory()
        RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        request = _make_request(member)
        view = _make_view(restaurant.slug)
        assert HasPermission("menu_edit").has_permission(request, view) is False
