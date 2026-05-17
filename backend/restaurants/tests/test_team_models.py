import pytest

from restaurants.models import RestaurantStaff
from restaurants.tests.factories import RestaurantStaffFactory


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
