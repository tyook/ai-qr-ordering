import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_payout_completed_email(restaurant, amount):
    send_mail(
        subject=f"Payout of ${amount} deposited — {restaurant.name}",
        message=(
            f"Your daily payout of ${amount} has been deposited to your bank account.\n\n"
            f"View details in your Stripe Dashboard."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[restaurant.owner.email],
        fail_silently=True,
    )


def send_payout_failed_email(restaurant, amount):
    send_mail(
        subject=f"Payout of ${amount} failed — {restaurant.name}",
        message=(
            f"Your payout of ${amount} failed. Please check your bank details "
            f"in the Stripe Dashboard and contact support if the issue persists."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[restaurant.owner.email],
        fail_silently=True,
    )


def send_merchant_welcome_email(restaurant) -> None:
    """Send welcome email to a restaurant owner after creating their restaurant."""
    owner = restaurant.owner
    if not owner.email:
        return

    context = {
        "restaurant_name": restaurant.name,
        "restaurant_slug": restaurant.slug,
        "owner_name": owner.first_name or owner.name or "",
        "trial_days": settings.FREE_TRIAL_DAYS,
        "frontend_url": settings.FRONTEND_URL,
    }
    html_message = render_to_string("emails/merchant_welcome.html", context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=f"{restaurant.name} is live on MenuChat!",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send merchant welcome email for %s", restaurant.slug)


def send_subscription_activated_email(restaurant, plan: str) -> None:
    """Send subscription activated email to restaurant owner."""
    owner = restaurant.owner
    if not owner.email:
        return

    plan_config = settings.SUBSCRIPTION_PLANS.get(plan, {})
    plan_name = plan_config.get("name", plan.title())
    order_limit = plan_config.get("order_limit", "Unlimited")

    context = {
        "restaurant_name": restaurant.name,
        "restaurant_slug": restaurant.slug,
        "owner_name": owner.first_name or owner.name or "",
        "plan_name": plan_name,
        "order_limit": order_limit,
        "frontend_url": settings.FRONTEND_URL,
    }
    html_message = render_to_string("emails/subscription_activated.html", context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=f"Subscription activated — {restaurant.name}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send subscription activated email for %s", restaurant.slug)


def send_payment_failed_email(restaurant) -> None:
    """Notify restaurant owner that their subscription payment failed."""
    owner = restaurant.owner
    if not owner.email:
        return

    context = {
        "restaurant_name": restaurant.name,
        "restaurant_slug": restaurant.slug,
        "owner_name": owner.first_name or owner.name or "",
        "frontend_url": settings.FRONTEND_URL,
    }
    html_message = render_to_string("emails/payment_failed.html", context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=f"Payment failed — {restaurant.name}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send payment failed email for %s", restaurant.slug)


def send_team_invitation_email(invitation) -> None:
    """Send invitation email to a prospective team member."""
    context = {
        "restaurant_name": invitation.restaurant.name,
        "invited_by_name": invitation.invited_by.name or invitation.invited_by.email,
        "role_display": "an Admin" if invitation.role == "admin" else "a Member",
        "invite_url": f"{settings.FRONTEND_URL}/invite/{invitation.token}",
        "expires_date": invitation.expires_at.strftime("%B %d, %Y"),
    }
    html_message = render_to_string("emails/team_invitation.html", context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=f"You're invited to join {invitation.restaurant.name} on MenuChat",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send invitation email to %s", invitation.email)


def send_payment_success_email(restaurant, amount_cents: int, plan: str, period_end_timestamp: int) -> None:
    """Notify restaurant owner that their subscription payment was received."""
    owner = restaurant.owner
    if not owner.email:
        return

    plan_config = settings.SUBSCRIPTION_PLANS.get(plan, {})
    plan_name = plan_config.get("name", plan.title())
    amount = f"${amount_cents / 100:,.2f}"
    from datetime import datetime, UTC
    period_end = datetime.fromtimestamp(period_end_timestamp, tz=UTC).strftime("%B %d, %Y")

    context = {
        "restaurant_name": restaurant.name,
        "restaurant_slug": restaurant.slug,
        "owner_name": owner.first_name or owner.name or "",
        "amount": amount,
        "plan_name": plan_name,
        "period_end": period_end,
        "frontend_url": settings.FRONTEND_URL,
    }
    html_message = render_to_string("emails/payment_success.html", context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=f"Payment received — {restaurant.name}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send payment success email for %s", restaurant.slug)
