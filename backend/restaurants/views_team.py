from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.models import Invitation, RestaurantStaff
from restaurants.permissions import IsRestaurantAdmin
from restaurants.serializers import (
    AcceptInvitationSerializer,
    InvitationDetailSerializer,
    InvitationSerializer,
    InviteMemberSerializer,
    StaffMemberSerializer,
    TransferOwnershipSerializer,
    UpdateMemberSerializer,
)
from restaurants.services import TeamService
from restaurants.views import RestaurantMixin


class TeamListView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        members = RestaurantStaff.objects.filter(restaurant=restaurant).select_related("user")
        invitations = Invitation.objects.filter(restaurant=restaurant, status="pending")
        return Response({
            "members": StaffMemberSerializer(members, many=True).data,
            "invitations": InvitationSerializer(invitations, many=True).data,
        })


class InviteMemberView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        serializer = InviteMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email=serializer.validated_data["email"],
            role=serializer.validated_data["role"],
            permissions=serializer.validated_data.get("permissions", {}),
            invited_by=request.user,
        )
        from restaurants.tasks import send_invitation_email_task
        send_invitation_email_task.delay(str(invitation.id))
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


class MemberDetailView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def patch(self, request, slug, staff_id):
        restaurant = self.get_restaurant()
        serializer = UpdateMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff = TeamService.update_member(
            restaurant=restaurant,
            staff_id=staff_id,
            role=serializer.validated_data.get("role"),
            permissions=serializer.validated_data.get("permissions"),
            acting_user=request.user,
        )
        return Response(StaffMemberSerializer(staff).data)

    def delete(self, request, slug, staff_id):
        restaurant = self.get_restaurant()
        TeamService.remove_member(
            restaurant=restaurant,
            staff_id=staff_id,
            acting_user=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TransferOwnershipView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated()]

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        serializer = TransferOwnershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        TeamService.transfer_ownership(
            restaurant=restaurant,
            new_owner_id=str(serializer.validated_data["new_owner_id"]),
            acting_user=request.user,
        )
        return Response({"detail": "Ownership transferred."})


class ResendInvitationView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def post(self, request, slug, invitation_id):
        restaurant = self.get_restaurant()
        from datetime import timedelta
        from django.utils import timezone
        try:
            invitation = Invitation.objects.get(
                id=invitation_id, restaurant=restaurant, status="pending"
            )
        except Invitation.DoesNotExist:
            return Response({"detail": "Invitation not found."}, status=status.HTTP_404_NOT_FOUND)
        invitation.expires_at = timezone.now() + timedelta(days=7)
        invitation.save(update_fields=["expires_at"])
        from restaurants.tasks import send_invitation_email_task
        send_invitation_email_task.delay(str(invitation.id))
        return Response(InvitationSerializer(invitation).data)


class RevokeInvitationView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def delete(self, request, slug, invitation_id):
        restaurant = self.get_restaurant()
        try:
            invitation = Invitation.objects.get(
                id=invitation_id, restaurant=restaurant, status="pending"
            )
        except Invitation.DoesNotExist:
            return Response({"detail": "Invitation not found."}, status=status.HTTP_404_NOT_FOUND)
        invitation.status = "revoked"
        invitation.save(update_fields=["status"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitationValidateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            invitation = Invitation.objects.select_related(
                "restaurant", "invited_by"
            ).get(token=token)
        except Invitation.DoesNotExist:
            return Response({"detail": "Invalid invitation."}, status=status.HTTP_404_NOT_FOUND)
        return Response(InvitationDetailSerializer(invitation).data)


class InvitationAcceptView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, token):
        serializer = AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user if request.user.is_authenticated else None
        registration_data = None
        if not user and data.get("password"):
            registration_data = {
                "first_name": data.get("first_name", ""),
                "last_name": data.get("last_name", ""),
                "password": data["password"],
            }

        staff = TeamService.accept_invitation(
            token=token,
            user=user,
            registration_data=registration_data,
        )
        return Response({
            "detail": "Invitation accepted.",
            "restaurant_slug": staff.restaurant.slug,
            "role": staff.role,
        })


class MyRoleView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated()]

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        perms = TeamService.get_effective_permissions(request.user, restaurant)
        if perms is None:
            return Response({"detail": "Not a team member."}, status=status.HTTP_403_FORBIDDEN)
        return Response(perms)
