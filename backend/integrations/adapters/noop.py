from integrations.adapters.base import BasePOSAdapter, PushResult


class NoopAdapter(BasePOSAdapter):
    """Adapter for restaurants with no POS integration. Always succeeds."""

    def push_order(self, order) -> PushResult:
        return PushResult(success=True)

    def cancel_order(self, external_order_id: str) -> bool:
        return True

    def get_order_status(self, external_order_id: str) -> str:
        return "unknown"

    def validate_connection(self) -> bool:
        return True

    def refresh_tokens(self) -> bool:
        return True
