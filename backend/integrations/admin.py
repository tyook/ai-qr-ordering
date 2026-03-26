from django.contrib import admin

from integrations.models import POSConnection, POSSyncLog


@admin.register(POSConnection)
class POSConnectionAdmin(admin.ModelAdmin):
    list_display = ["restaurant", "pos_type", "is_active", "payment_mode", "created_at"]
    list_filter = ["pos_type", "is_active", "payment_mode"]
    search_fields = ["restaurant__name", "restaurant__slug"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(POSSyncLog)
class POSSyncLogAdmin(admin.ModelAdmin):
    list_display = ["order", "status", "attempt_count", "external_order_id", "created_at"]
    list_filter = ["status"]
    search_fields = ["order__id", "external_order_id"]
    readonly_fields = ["id", "created_at", "updated_at"]
