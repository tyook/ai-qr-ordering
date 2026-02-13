from rest_framework import serializers
from orders.models import Order, OrderItem


class ParseInputSerializer(serializers.Serializer):
    raw_input = serializers.CharField(max_length=2000)
    table_identifier = serializers.CharField(max_length=50, required=False, default="", allow_blank=True)


class ConfirmOrderItemSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    variant_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    modifier_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    special_requests = serializers.CharField(required=False, default="", allow_blank=True)


class ConfirmOrderSerializer(serializers.Serializer):
    items = ConfirmOrderItemSerializer(many=True)
    raw_input = serializers.CharField()
    table_identifier = serializers.CharField(required=False, default="", allow_blank=True)
    language = serializers.CharField(required=False, default="en")


class OrderItemResponseSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="menu_item.name")
    variant_label = serializers.CharField(source="variant.label")
    variant_price = serializers.DecimalField(
        source="variant.price", max_digits=8, decimal_places=2
    )

    class Meta:
        model = OrderItem
        fields = [
            "id", "name", "variant_label", "variant_price",
            "quantity", "special_requests",
        ]


class OrderResponseSerializer(serializers.ModelSerializer):
    items = OrderItemResponseSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "status", "table_identifier", "total_price",
            "created_at", "items",
        ]
