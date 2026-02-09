from rest_framework.permissions import BasePermission
from restaurants.models import RestaurantStaff


class IsRestaurantOwnerOrStaff(BasePermission):
    """
    Allow access if user is the restaurant owner or has a staff role.
    """

    def has_object_permission(self, request, view, obj):
        if obj.owner == request.user:
            return True
        return RestaurantStaff.objects.filter(
            user=request.user, restaurant=obj
        ).exists()
