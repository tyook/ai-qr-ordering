import stripe
from django.conf import settings
from rest_framework.exceptions import NotFound

from restaurants.models import ConnectedAccount

stripe.api_key = settings.STRIPE_SECRET_KEY


class ConnectService:
    @staticmethod
    def create_onboarding_link(restaurant):
        try:
            account = restaurant.connected_account
        except ConnectedAccount.DoesNotExist:
            stripe_account = stripe.Account.create(
                type="express",
                metadata={"restaurant_id": str(restaurant.id)},
            )
            account = ConnectedAccount.objects.create(
                restaurant=restaurant,
                stripe_account_id=stripe_account.id,
            )

        account_link = stripe.AccountLink.create(
            account=account.stripe_account_id,
            refresh_url=f"{settings.FRONTEND_URL}/dashboard/{restaurant.slug}/connect/refresh",
            return_url=f"{settings.FRONTEND_URL}/dashboard/{restaurant.slug}/connect/complete",
            type="account_onboarding",
        )
        return {"url": account_link.url}

    @staticmethod
    def get_connect_status(restaurant):
        try:
            account = restaurant.connected_account
            return {
                "has_account": True,
                "onboarding_complete": account.onboarding_complete,
                "payouts_enabled": account.payouts_enabled,
                "charges_enabled": account.charges_enabled,
            }
        except ConnectedAccount.DoesNotExist:
            return {
                "has_account": False,
                "onboarding_complete": False,
                "payouts_enabled": False,
                "charges_enabled": False,
            }

    @staticmethod
    def create_dashboard_link(restaurant):
        try:
            account = restaurant.connected_account
        except ConnectedAccount.DoesNotExist:
            raise NotFound("No connected account found. Complete onboarding first.")

        if not account.onboarding_complete:
            raise NotFound("Onboarding not complete.")

        login_link = stripe.Account.create_login_link(
            account.stripe_account_id,
        )
        return {"url": login_link.url}
