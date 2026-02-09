import uuid
from django.db import models
from restaurants.models import Restaurant, MenuItem, MenuItemVariant, MenuItemModifier


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="orders"
    )
    table_identifier = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    raw_input = models.TextField()
    parsed_json = models.JSONField(default=dict, blank=True)
    language_detected = models.CharField(max_length=10, blank=True, default="")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        table = f" (Table {self.table_identifier})" if self.table_identifier else ""
        return f"Order {self.id}{table} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT)
    variant = models.ForeignKey(MenuItemVariant, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    special_requests = models.TextField(blank=True, default="")
    modifiers = models.ManyToManyField(MenuItemModifier, blank=True)

    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name} ({self.variant.label})"
