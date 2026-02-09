import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from restaurants.managers import UserManager


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff"
        ADMIN = "admin", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.OWNER)
    phone = models.CharField(max_length=20, blank=True, default="")

    username = None  # Remove username field
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    def __str__(self):
        return self.email


class Restaurant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=100)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_restaurants")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class RestaurantStaff(models.Model):
    class StaffRole(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        KITCHEN = "kitchen", "Kitchen"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="staff_roles")
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="staff")
    role = models.CharField(max_length=10, choices=StaffRole.choices)
    invited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "restaurant")

    def __str__(self):
        return f"{self.user.email} @ {self.restaurant.name} ({self.role})"
