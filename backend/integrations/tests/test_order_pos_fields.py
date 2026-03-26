import pytest
from orders.tests.factories import OrderFactory


@pytest.mark.django_db
class TestOrderPOSFields:
    def test_default_pos_sync_status(self):
        order = OrderFactory()
        assert order.pos_sync_status == "not_applicable"
        assert order.external_order_id is None

    def test_pos_collected_payment_status(self):
        order = OrderFactory(payment_status="pos_collected")
        assert order.payment_status == "pos_collected"

    def test_set_external_order_id(self):
        order = OrderFactory()
        order.external_order_id = "sq_order_abc123"
        order.pos_sync_status = "synced"
        order.save()
        order.refresh_from_db()
        assert order.external_order_id == "sq_order_abc123"
        assert order.pos_sync_status == "synced"
