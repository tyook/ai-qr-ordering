import uuid

import stripe
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from accounts.managers import UserManager


class User(AbstractUser):
    class AuthProvider(models.TextChoices):
        EMAIL = "email", "Email"
        GOOGLE = "google", "Google"
        APPLE = "apple", "Apple"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, default="")
    stripe_customer_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )

    # Merged from Customer model
    auth_provider = models.CharField(
        max_length=10, choices=AuthProvider.choices, default=AuthProvider.EMAIL
    )
    auth_provider_id = models.CharField(max_length=255, blank=True, default="")
    dietary_preferences = models.JSONField(default=list, blank=True)
    allergies = models.JSONField(default=list, blank=True)
    preferred_language = models.CharField(max_length=10, blank=True, default="en-US")

    username = None
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    @property
    def is_restaurant_owner(self):
        return self.owned_restaurants.exists() or self.staff_roles.exists()

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_or_create_stripe_customer(self):
        if self.stripe_customer_id:
            return self.stripe_customer_id
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe_customer = stripe.Customer.create(
            email=self.email,
            name=self.name,
            metadata={"user_id": str(self.id)},
        )
        self.stripe_customer_id = stripe_customer.id
        self.save(update_fields=["stripe_customer_id"])
        return self.stripe_customer_id

    def __str__(self):
        return self.email
