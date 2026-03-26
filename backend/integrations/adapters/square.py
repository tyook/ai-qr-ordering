import logging

from square import Square as SquareClient

from integrations.adapters.base import BasePOSAdapter, PushResult
from integrations.encryption import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)


class SquareAdapter(BasePOSAdapter):
    def _get_client(self) -> SquareClient:
        access_token = decrypt_token(self.connection.oauth_access_token)
        return SquareClient(token=access_token)

    def push_order(self, order) -> PushResult:
        client = self._get_client()
        location_id = self.connection.external_location_id
        currency = order.restaurant.currency.upper()

        line_items = []
        for item in order.items.select_related("variant").prefetch_related("modifiers"):
            line_item = {
                "name": item.menu_item.name,
                "quantity": str(item.quantity),
                "base_price_money": {
                    "amount": int(item.variant.price * 100),
                    "currency": currency,
                },
            }
            if item.modifiers.exists():
                line_item["modifiers"] = [
                    {
                        "name": mod.name,
                        "base_price_money": {
                            "amount": int(mod.price_adjustment * 100),
                            "currency": currency,
                        },
                    }
                    for mod in item.modifiers.all()
                ]
            line_items.append(line_item)

        body = {
            "order": {
                "location_id": location_id,
                "reference_id": str(order.id),
                "line_items": line_items,
            },
        }

        # If paid via Stripe, mark as paid externally
        if (
            self.connection.payment_mode == "stripe"
            and order.payment_status == "paid"
        ):
            body["order"]["tenders"] = [
                {
                    "type": "OTHER",
                    "amount_money": {
                        "amount": int(order.total_price * 100),
                        "currency": currency,
                    },
                    "note": "Paid via QR Ordering Platform",
                }
            ]

        try:
            result = client.orders.create_order(body=body)
        except Exception as e:
            return PushResult(success=False, error_message=str(e))

        if result.is_success():
            external_id = result.body["order"]["id"]
            return PushResult(success=True, external_order_id=external_id)
        else:
            errors = "; ".join(e.get("detail", str(e)) for e in result.errors)
            return PushResult(success=False, error_message=errors)

    def cancel_order(self, external_order_id: str) -> bool:
        try:
            client = self._get_client()
            result = client.orders.update_order(
                order_id=external_order_id,
                body={
                    "order": {
                        "location_id": self.connection.external_location_id,
                        "state": "CANCELED",
                        "version": 1,
                    },
                },
            )
            return result.is_success()
        except Exception:
            logger.exception("Failed to cancel Square order %s", external_order_id)
            return False

    def get_order_status(self, external_order_id: str) -> str:
        try:
            client = self._get_client()
            result = client.orders.retrieve_order(order_id=external_order_id)
            if result.is_success():
                return result.body["order"]["state"]
            return "unknown"
        except Exception:
            return "unknown"

    def validate_connection(self) -> bool:
        try:
            client = self._get_client()
            result = client.locations.list_locations()
            return result.is_success()
        except Exception:
            return False

    def refresh_tokens(self) -> bool:
        from django.conf import settings

        try:
            client = SquareClient()
            result = client.o_auth.obtain_token(
                body={
                    "client_id": settings.POS_SQUARE_CLIENT_ID,
                    "client_secret": settings.POS_SQUARE_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": decrypt_token(
                        self.connection.oauth_refresh_token
                    ),
                }
            )
            if result.is_success():
                self.connection.oauth_access_token = encrypt_token(
                    result.body["access_token"]
                )
                if "refresh_token" in result.body:
                    self.connection.oauth_refresh_token = encrypt_token(
                        result.body["refresh_token"]
                    )
                if "expires_at" in result.body:
                    from django.utils.dateparse import parse_datetime
                    self.connection.oauth_token_expires_at = parse_datetime(
                        result.body["expires_at"]
                    )
                self.connection.save()
                return True
            return False
        except Exception:
            logger.exception("Failed to refresh Square tokens")
            return False
