from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.models import POSConnection, POSSyncLog
from integrations.serializers import (
    POSConnectionSerializer,
    POSConnectionUpdateSerializer,
    POSSyncLogSerializer,
)
from restaurants.models import Restaurant


class RestaurantPOSMixin:
    def get_restaurant(self, slug):
        try:
            return Restaurant.objects.get(slug=slug, owner=self.request.user)
        except Restaurant.DoesNotExist:
            raise NotFound("Restaurant not found.")


class POSConnectionDetailView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        restaurant = self.get_restaurant(slug)
        try:
            connection = POSConnection.objects.get(restaurant=restaurant)
        except POSConnection.DoesNotExist:
            return Response(
                {"pos_type": "none", "is_connected": False, "payment_mode": "stripe"}
            )
        return Response(POSConnectionSerializer(connection).data)

    def patch(self, request, slug):
        restaurant = self.get_restaurant(slug)
        try:
            connection = POSConnection.objects.get(restaurant=restaurant)
        except POSConnection.DoesNotExist:
            raise NotFound("No POS connection found for this restaurant.")
        serializer = POSConnectionUpdateSerializer(
            connection, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(POSConnectionSerializer(connection).data)

    def delete(self, request, slug):
        restaurant = self.get_restaurant(slug)
        POSConnection.objects.filter(restaurant=restaurant).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
