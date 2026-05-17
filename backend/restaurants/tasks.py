import logging

from celery import shared_task
from config.celery import app

from restaurants.services.payout_service import PayoutService

logger = logging.getLogger(__name__)


@app.task(name="restaurants.tasks.auto_resume_orders")
def auto_resume_orders():
    """Re-enable accepting_orders for restaurants that opted into auto-resume."""
    from restaurants.models import Restaurant

    updated = Restaurant.objects.filter(
        accepting_orders=False,
        auto_resume_orders=True,
    ).update(accepting_orders=True)
    if updated:
        logger.info("Auto-resumed orders for %d restaurant(s)", updated)


@app.task(name="restaurants.tasks.process_daily_payouts")
def process_daily_payouts():
    logger.info("Starting daily payout processing")
    PayoutService.process_all_payouts()
    logger.info("Daily payout processing complete")


@shared_task
def send_merchant_welcome_email_task(restaurant_id: str):
    """Send merchant welcome email after restaurant creation (async)."""
    from restaurants.models import Restaurant

    try:
        restaurant = Restaurant.objects.select_related("owner").get(id=restaurant_id)
    except Restaurant.DoesNotExist:
        logger.warning("send_merchant_welcome_email_task: restaurant %s not found", restaurant_id)
        return

    from restaurants.notifications import send_merchant_welcome_email
    send_merchant_welcome_email(restaurant)


@shared_task
def send_subscription_activated_email_task(restaurant_id: str, plan: str):
    """Send subscription activated email after checkout completes (async)."""
    from restaurants.models import Restaurant

    try:
        restaurant = Restaurant.objects.select_related("owner").get(id=restaurant_id)
    except Restaurant.DoesNotExist:
        logger.warning("send_subscription_activated_email_task: restaurant %s not found", restaurant_id)
        return

    from restaurants.notifications import send_subscription_activated_email
    send_subscription_activated_email(restaurant, plan)


@shared_task
def send_payment_failed_email_task(restaurant_id: str):
    """Send payment failed email after subscription goes past_due (async)."""
    from restaurants.models import Restaurant

    try:
        restaurant = Restaurant.objects.select_related("owner").get(id=restaurant_id)
    except Restaurant.DoesNotExist:
        logger.warning("send_payment_failed_email_task: restaurant %s not found", restaurant_id)
        return

    from restaurants.notifications import send_payment_failed_email
    send_payment_failed_email(restaurant)


@shared_task
def send_invitation_email_task(invitation_id: str):
    """Send team invitation email (async)."""
    from restaurants.models import Invitation
    try:
        invitation = Invitation.objects.select_related(
            "restaurant", "invited_by"
        ).get(id=invitation_id)
    except Invitation.DoesNotExist:
        logger.warning("send_invitation_email_task: invitation %s not found", invitation_id)
        return

    from restaurants.notifications import send_team_invitation_email
    send_team_invitation_email(invitation)


@shared_task
def send_payment_success_email_task(restaurant_id: str, amount_cents: int, plan: str, period_end_timestamp: int):
    """Send payment success email after invoice paid (async)."""
    from restaurants.models import Restaurant

    try:
        restaurant = Restaurant.objects.select_related("owner").get(id=restaurant_id)
    except Restaurant.DoesNotExist:
        logger.warning("send_payment_success_email_task: restaurant %s not found", restaurant_id)
        return

    from restaurants.notifications import send_payment_success_email
    send_payment_success_email(restaurant, amount_cents, plan, period_end_timestamp)
