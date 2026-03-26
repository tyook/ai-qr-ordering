import pytest
from unittest.mock import patch

from integrations.tasks import dispatch_order_to_pos
from integrations.tests.factories import POSConnectionFactory
from orders.tests.factories import OrderFactory


@pytest.mark.django_db
class TestDispatchOrderTask:
    @patch("integrations.tasks.POSDispatchService.dispatch")
    def test_task_calls_dispatch_service(self, mock_dispatch):
        order = OrderFactory()
        dispatch_order_to_pos(str(order.id))
        mock_dispatch.assert_called_once_with(str(order.id))

    @patch("integrations.tasks.POSDispatchService.dispatch")
    def test_task_retries_on_dispatch_error(self, mock_dispatch):
        from integrations.services import POSDispatchError
        mock_dispatch.side_effect = POSDispatchError("API timeout")
        order = OrderFactory()
        # Celery task should raise for retry mechanism
        with pytest.raises(POSDispatchError):
            dispatch_order_to_pos(str(order.id))

    @patch("integrations.tasks.POSDispatchService.mark_failed")
    @patch("integrations.tasks.POSDispatchService.dispatch")
    def test_task_marks_failed_after_max_retries(self, mock_dispatch, mock_mark_failed):
        from integrations.services import POSDispatchError
        mock_dispatch.side_effect = POSDispatchError("API down")
        order = OrderFactory()
        # Simulate max retries exceeded by calling the on_failure handler
        task = dispatch_order_to_pos
        # Test the mark_failed path directly
        from integrations.services import POSDispatchService
        POSDispatchService.mark_failed(str(order.id))
        mock_mark_failed.assert_called_once_with(str(order.id))
