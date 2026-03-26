from rest_framework import serializers

from integrations.models import POSConnection, POSSyncLog


class POSConnectionSerializer(serializers.ModelSerializer):
    is_connected = serializers.SerializerMethodField()

    class Meta:
        model = POSConnection
        fields = [
            "id",
            "pos_type",
            "is_active",
            "payment_mode",
            "external_location_id",
            "is_connected",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_connected", "created_at", "updated_at"]

    def get_is_connected(self, obj):
        return obj.is_active and obj.pos_type != POSConnection.POSType.NONE


class POSConnectionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = POSConnection
        fields = ["payment_mode", "external_location_id"]


class POSSyncLogSerializer(serializers.ModelSerializer):
    order_id = serializers.UUIDField(source="order.id", read_only=True)
    order_created_at = serializers.DateTimeField(source="order.created_at", read_only=True)

    class Meta:
        model = POSSyncLog
        fields = [
            "id",
            "order_id",
            "order_created_at",
            "status",
            "external_order_id",
            "attempt_count",
            "last_error",
            "next_retry_at",
            "created_at",
        ]
