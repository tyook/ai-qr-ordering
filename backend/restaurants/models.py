import uuid

from django.conf import settings
from django.db import models


class Restaurant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=100)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_restaurants")
    currency = models.CharField(max_length=3, default="USD", help_text="ISO 4217 currency code")
    phone = models.CharField(max_length=20, blank=True, default="")
    address = models.TextField(blank=True, default="")
    homepage = models.URLField(blank=True, default="")
    logo_url = models.URLField(blank=True, default="")
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=0,
        help_text="Tax rate as a percentage (e.g. 8.875 for 8.875%)",
    )
    estimated_minutes_per_order = models.PositiveIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    class Plan(models.TextChoices):
        STARTER = "starter", "Starter"
        GROWTH = "growth", "Growth"
        PRO = "pro", "Pro"

    class Status(models.TextChoices):
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        CANCELED = "canceled", "Canceled"
        INCOMPLETE = "incomplete", "Incomplete"

    restaurant = models.OneToOneField(Restaurant, on_delete=models.CASCADE, related_name="subscription")
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.STARTER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIALING)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    trial_end = models.DateTimeField(blank=True, null=True)
    current_period_start = models.DateTimeField(blank=True, null=True)
    current_period_end = models.DateTimeField(blank=True, null=True)
    cancel_at_period_end = models.BooleanField(default=False)
    order_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_active(self):
        """Subscription allows usage if trialing, active, or past_due."""
        return self.status in ("trialing", "active", "past_due")

    @property
    def order_limit(self):
        """Get order limit from settings based on plan."""
        from django.conf import settings

        plan_config = settings.SUBSCRIPTION_PLANS.get(self.plan, {})
        return plan_config.get("order_limit", 0)

    @property
    def overage_count(self):
        """Number of orders exceeding the plan limit."""
        return max(0, self.order_count - self.order_limit)

    def __str__(self):
        return f"{self.restaurant.name} - {self.plan} ({self.status})"


class RestaurantStaff(models.Model):
    class StaffRole(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        KITCHEN = "kitchen", "Kitchen"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_roles")
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="staff")
    role = models.CharField(max_length=10, choices=StaffRole.choices)
    invited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "restaurant")

    def __str__(self):
        return f"{self.user.email} @ {self.restaurant.name} ({self.role})"


class MenuCategory(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=100)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order"]
        verbose_name_plural = "menu categories"

    def __str__(self):
        return f"{self.restaurant.name} - {self.name}"


class MenuItem(models.Model):
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    image_url = models.URLField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.name


class MenuItemVariant(models.Model):
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="variants")
    label = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.menu_item.name} - {self.label} (${self.price})"


class MenuItemModifier(models.Model):
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="modifiers")
    name = models.CharField(max_length=100)
    price_adjustment = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.menu_item.name} + {self.name} (${self.price_adjustment})"


class ConnectedAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.OneToOneField(
        Restaurant, on_delete=models.CASCADE, related_name="connected_account"
    )
    stripe_account_id = models.CharField(max_length=255, unique=True)
    onboarding_complete = models.BooleanField(default=False)
    payouts_enabled = models.BooleanField(default=False)
    charges_enabled = models.BooleanField(default=False)
    pending_refund_balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ConnectedAccount({self.restaurant.name}, {self.stripe_account_id})"


class Payout(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        IN_TRANSIT = "in_transit"
        COMPLETED = "completed"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="payouts"
    )
    stripe_transfer_id = models.CharField(max_length=255, unique=True)
    stripe_payout_id = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fee_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    fee_fixed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    orders_count = models.PositiveIntegerField()
    period_start = models.DateField()
    period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payout({self.restaurant.name}, {self.amount} {self.currency}, {self.status})"
