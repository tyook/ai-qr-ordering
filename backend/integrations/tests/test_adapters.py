import pytest
from integrations.adapters.base import BasePOSAdapter, PushResult
from integrations.adapters.noop import NoopAdapter
from integrations.tests.factories import POSConnectionFactory


@pytest.mark.django_db
class TestNoopAdapter:
    def test_push_order_returns_success(self):
        connection = POSConnectionFactory(pos_type="none")
        adapter = NoopAdapter(connection)
        from orders.tests.factories import OrderFactory
        order = OrderFactory(restaurant=connection.restaurant)
        result = adapter.push_order(order)
        assert isinstance(result, PushResult)
        assert result.success is True
        assert result.external_order_id is None

    def test_validate_connection(self):
        connection = POSConnectionFactory(pos_type="none")
        adapter = NoopAdapter(connection)
        assert adapter.validate_connection() is True
