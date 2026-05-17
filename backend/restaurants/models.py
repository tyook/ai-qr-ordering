import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Restaurant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=100)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_restaurants")
    currency = models.CharField(max_length=3, default="USD", help_text="ISO 4217 currency code")
    phone = models.CharField(max_length=20, blank=True, default="")
    street_address = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    zip_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="US")
    google_place_id = models.CharField(max_length=255, blank=True, default="")
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    homepage = models.URLField(blank=True, default="")
    logo_url = models.URLField(blank=True, default="")
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=0,
        help_text="Tax rate as a percentage (e.g. 8.875 for 8.875%)",
    )
    estimated_minutes_per_order = models.PositiveIntegerField(default=10)
    payment_model = models.CharField(
        max_length=20,
        choices=[("upfront", "Pay Upfront"), ("tab", "Open Tab")],
        default="upfront",
    )
    accepting_orders = models.BooleanField(default=True)
    auto_resume_orders = models.BooleanField(default=True)
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
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_roles")
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="staff")
    role = models.CharField(max_length=10, choices=StaffRole.choices)
    permissions = models.JSONField(default=dict, blank=True)
    invited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "restaurant")

    def __str__(self):
        return f"{self.user.email} @ {self.restaurant.name} ({self.role})"


class Invitation(models.Model):
    class InviteStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=10, choices=[("admin", "Admin"), ("member", "Member")])
    permissions = models.JSONField(default=dict, blank=True)
    token = models.CharField(max_length=64, unique=True, editable=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_invitations"
    )
    status = models.CharField(
        max_length=10, choices=InviteStatus.choices, default=InviteStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant", "email"],
                condition=models.Q(status="pending"),
                name="unique_pending_invitation",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return self.status == "pending" and timezone.now() > self.expires_at

    def __str__(self):
        return f"Invite {self.email} to {self.restaurant.name} ({self.status})"


class MenuVersion(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        AI_UPLOAD = "ai_upload", "AI Upload"
        TOAST_SYNC = "toast_sync", "Toast Sync"

    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="menu_versions"
    )
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=False)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class MenuCategory(models.Model):
    version = models.ForeignKey(
        MenuVersion, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=100)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SOLD_OUT = "sold_out", "Sold out"
        INACTIVE = "inactive", "Inactive"

    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    image_url = models.URLField(blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    is_upsellable = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

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


class Table(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="tables")
    name = models.CharField(max_length=50, help_text="Display name, e.g. 'Patio 3'")
    number = models.CharField(max_length=20, help_text="Short identifier used in QR URL, e.g. 'A1'")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("restaurant", "number")
        ordering = ["number"]

    def __str__(self):
        return f"{self.restaurant.name} - Table {self.number}"


class OperatingHours(models.Model):
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="operating_hours")
    day_of_week = models.IntegerField(choices=DayOfWeek.choices)
    open_time = models.TimeField()
    close_time = models.TimeField()

    class Meta:
        ordering = ["day_of_week", "open_time"]

    def __str__(self):
        return f"{self.restaurant.name} - {self.get_day_of_week_display()}: {self.open_time}-{self.close_time}"


class HolidayOverride(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="holiday_overrides")
    date = models.DateField()
    label = models.CharField(max_length=100, help_text="e.g. Christmas, Vacation")
    is_closed = models.BooleanField(default=True)
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ("restaurant", "date")
        ordering = ["date"]

    def __str__(self):
        status = "Closed" if self.is_closed else f"{self.open_time}-{self.close_time}"
        return f"{self.restaurant.name} - {self.label} ({self.date}): {status}"


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
