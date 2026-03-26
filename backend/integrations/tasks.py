import logging

from celery import shared_task
from django.conf import settings

from integrations.services import POSDispatchError, POSDispatchService

logger = logging.getLogger(__name__)

RETRY_DELAYS = getattr(settings, "POS_DISPATCH_RETRY_DELAYS", [30, 120, 600, 1800])


@shared_task(
    bind=True,
    max_retries=len(RETRY_DELAYS),  # 4 retries = 5 total attempts (initial + 4 retries)
    acks_late=True,
)
def dispatch_order_to_pos(self, order_id: str) -> None:
    """Dispatch order to POS with idempotency check and exponential backoff."""
    # Idempotency: skip if already synced (prevents double dispatch from
    # ConfirmPaymentView + webhook both firing for the same order)
    from orders.models import Order
    if Order.objects.filter(id=order_id, pos_sync_status="synced").exists():
        return

    try:
        POSDispatchService.dispatch(order_id)
    except POSDispatchError as exc:
        retry_num = self.request.retries
        if retry_num < len(RETRY_DELAYS):
            countdown = RETRY_DELAYS[retry_num]
            logger.warning(
                "POS dispatch failed, retrying in %ds: order=%s error=%s",
                countdown,
                order_id,
                exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        else:
            logger.error("POS dispatch failed after all retries: order=%s", order_id)
            POSDispatchService.mark_failed(order_id)
    except Exception:
        logger.exception("Unexpected error in POS dispatch: order=%s", order_id)
        POSDispatchService.mark_failed(order_id)
