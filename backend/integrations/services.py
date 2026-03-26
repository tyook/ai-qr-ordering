import logging

from django.utils import timezone

from integrations.adapters.base import BasePOSAdapter
from integrations.adapters.noop import NoopAdapter
from integrations.adapters.square import SquareAdapter
from integrations.models import POSConnection, POSSyncLog
from orders.models import Order

logger = logging.getLogger(__name__)


class POSDispatchError(Exception):
    pass


class POSDispatchService:
    @staticmethod
    def dispatch(order_id: str) -> None:
        order = Order.objects.select_related("restaurant").get(id=order_id)

        try:
            connection = POSConnection.objects.get(
                restaurant=order.restaurant, is_active=True
            )
        except POSConnection.DoesNotExist:
            connection = None

        if not connection or connection.pos_type == POSConnection.POSType.NONE:
            Order.objects.filter(id=order.id).update(
                pos_sync_status="not_applicable"
            )
            return

        log = POSSyncLog.objects.create(
            order=order,
            pos_connection=connection,
            status=POSSyncLog.Status.PENDING,
        )

        adapter = POSDispatchService._get_adapter(connection)
        result = adapter.push_order(order)

        if result.success:
            log.status = POSSyncLog.Status.SUCCESS
            log.external_order_id = result.external_order_id
            log.attempt_count += 1
            log.save()

            Order.objects.filter(id=order.id).update(
                pos_sync_status="synced",
                external_order_id=result.external_order_id,
            )
        else:
            log.status = POSSyncLog.Status.RETRYING
            log.last_error = result.error_message
            log.attempt_count += 1
            log.save()

            Order.objects.filter(id=order.id).update(
                pos_sync_status="retrying",
            )
            raise POSDispatchError(
                f"POS dispatch failed: {result.error_message}"
            )

    @staticmethod
    def _get_adapter(connection: POSConnection) -> BasePOSAdapter:
        adapter_map = {
            POSConnection.POSType.NONE: NoopAdapter,
            POSConnection.POSType.SQUARE: SquareAdapter,
        }
        adapter_class = adapter_map.get(connection.pos_type, NoopAdapter)
        return adapter_class(connection)

    @staticmethod
    def mark_failed(order_id: str) -> None:
        """Called after all retries are exhausted."""
        Order.objects.filter(id=order_id).update(pos_sync_status="failed")
        POSSyncLog.objects.filter(
            order_id=order_id, status=POSSyncLog.Status.RETRYING
        ).update(status=POSSyncLog.Status.FAILED)
