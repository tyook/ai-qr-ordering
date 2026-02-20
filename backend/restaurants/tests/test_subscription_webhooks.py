import pytest
import json
from unittest.mock import patch, MagicMock
from rest_framework import status
from restaurants.tests.factories import RestaurantFactory
from restaurants.models import Subscription
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestSubscriptionWebhooks:
    @patch("stripe.Webhook.construct_event")
    def test_checkout_completed_activates_subscription(self, mock_construct, api_client):
        restaurant = RestaurantFactory()
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            stripe_customer_id="cus_test123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
        )

        mock_construct.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "mode": "subscription",
                    "subscription": "sub_new123",
                    "customer": "cus_test123",
                    "metadata": {
                        "restaurant_id": str(restaurant.id),
                        "plan": "growth",
                    },
                }
            },
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        sub.refresh_from_db()
        assert sub.stripe_subscription_id == "sub_new123"
        assert sub.plan == "growth"
        assert sub.status == "active"

    @patch("stripe.Webhook.construct_event")
    def test_subscription_updated_changes_status(self, mock_construct, api_client):
        restaurant = RestaurantFactory()
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            stripe_subscription_id="sub_test123",
            stripe_customer_id="cus_test123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )

        mock_construct.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "status": "past_due",
                    "current_period_start": int(timezone.now().timestamp()),
                    "current_period_end": int((timezone.now() + timedelta(days=30)).timestamp()),
                    "cancel_at_period_end": False,
                    "items": {
                        "data": [
                            {
                                "price": {
                                    "id": "price_growth_monthly",
                                    "metadata": {},
                                }
                            }
                        ]
                    },
                    "metadata": {"plan": "growth"},
                }
            },
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        sub.refresh_from_db()
        assert sub.status == "past_due"

    @patch("stripe.Webhook.construct_event")
    def test_subscription_deleted_marks_canceled(self, mock_construct, api_client):
        restaurant = RestaurantFactory()
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            stripe_subscription_id="sub_test123",
            stripe_customer_id="cus_test123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )

        mock_construct.return_value = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test123",
                }
            },
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        sub.refresh_from_db()
        assert sub.status == "canceled"
