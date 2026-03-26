import logging
from config.celery import app
from restaurants.services.payout_service import PayoutService

logger = logging.getLogger(__name__)


@app.task(name="restaurants.tasks.process_daily_payouts")
def process_daily_payouts():
    logger.info("Starting daily payout processing")
    PayoutService.process_all_payouts()
    logger.info("Daily payout processing complete")
