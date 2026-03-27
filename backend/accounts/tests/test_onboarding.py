import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from accounts.services import user_to_dict


# ── Task 1: Model field defaults ─────────────────────────────────

class TestOnboardingModelFields(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="onboard@test.com",
            password="testpass123!",
            first_name="Test",
            last_name="User",
        )

    def test_onboarding_completed_defaults_to_false(self):
        self.assertFalse(self.user.onboarding_completed)

    def test_onboarding_dismissed_defaults_to_false(self):
        self.assertFalse(self.user.onboarding_dismissed)

    def test_onboarding_completed_can_be_set_true(self):
        self.user.onboarding_completed = True
        self.user.save(update_fields=["onboarding_completed"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.onboarding_completed)

    def test_onboarding_dismissed_can_be_set_true(self):
        self.user.onboarding_dismissed = True
        self.user.save(update_fields=["onboarding_dismissed"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.onboarding_dismissed)


# ── Task 2: user_to_dict and serializer ──────────────────────────

class TestUserToDictOnboarding(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="dict@test.com",
            password="testpass123!",
            first_name="Dict",
            last_name="User",
        )

    def test_user_to_dict_contains_onboarding_completed(self):
        data = user_to_dict(self.user)
        self.assertIn("onboarding_completed", data)
        self.assertFalse(data["onboarding_completed"])

    def test_user_to_dict_contains_onboarding_dismissed(self):
        data = user_to_dict(self.user)
        self.assertIn("onboarding_dismissed", data)
        self.assertFalse(data["onboarding_dismissed"])

    def test_user_to_dict_contains_owns_restaurant(self):
        data = user_to_dict(self.user)
        self.assertIn("owns_restaurant", data)
        self.assertFalse(data["owns_restaurant"])

    def test_user_to_dict_reflects_true_values(self):
        self.user.onboarding_completed = True
        self.user.onboarding_dismissed = True
        self.user.save()
        data = user_to_dict(self.user)
        self.assertTrue(data["onboarding_completed"])
        self.assertTrue(data["onboarding_dismissed"])


class TestUserProfileSerializerOnboarding(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="serial@test.com",
            password="testpass123!",
            first_name="Serial",
            last_name="User",
        )

    def test_serializer_includes_onboarding_fields(self):
        from accounts.serializers import UserProfileSerializer

        serializer = UserProfileSerializer(self.user)
        self.assertIn("onboarding_completed", serializer.data)
        self.assertIn("onboarding_dismissed", serializer.data)

    def test_serializer_onboarding_fields_are_read_only(self):
        from accounts.serializers import UserProfileSerializer

        serializer = UserProfileSerializer(self.user, data={
            "onboarding_completed": True,
            "onboarding_dismissed": True,
            "first_name": "Serial",
        }, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self.user.refresh_from_db()
        # Should remain False because they are read-only
        self.assertFalse(self.user.onboarding_completed)
        self.assertFalse(self.user.onboarding_dismissed)


# ── Task 3: Onboarding endpoints ─────────────────────────────────

@pytest.mark.django_db
class TestOnboardingEndpoints(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="endpoint@test.com",
            password="testpass123!",
            first_name="Endpoint",
            last_name="User",
        )

    def test_complete_requires_authentication(self):
        response = self.client.post("/api/account/onboarding/complete/")
        self.assertEqual(response.status_code, 401)

    def test_dismiss_requires_authentication(self):
        response = self.client.post("/api/account/onboarding/dismiss/")
        self.assertEqual(response.status_code, 401)

    def test_complete_sets_onboarding_completed(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/account/onboarding/complete/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.onboarding_completed)

    def test_dismiss_sets_onboarding_dismissed(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/account/onboarding/dismiss/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.onboarding_dismissed)

    def test_complete_is_idempotent(self):
        self.client.force_authenticate(user=self.user)
        self.client.post("/api/account/onboarding/complete/")
        response = self.client.post("/api/account/onboarding/complete/")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.onboarding_completed)

    def test_dismiss_is_idempotent(self):
        self.client.force_authenticate(user=self.user)
        self.client.post("/api/account/onboarding/dismiss/")
        response = self.client.post("/api/account/onboarding/dismiss/")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.onboarding_dismissed)
