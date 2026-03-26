import pytest
from unittest.mock import patch


@pytest.mark.django_db
class TestProcessDailyPayoutsTask:
    @patch("restaurants.services.payout_service.PayoutService.process_all_payouts")
    def test_task_calls_process_all_payouts(self, mock_process):
        from restaurants.tasks import process_daily_payouts

        process_daily_payouts()
        mock_process.assert_called_once()
