from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PushResult:
    success: bool
    external_order_id: str | None = None
    error_message: str | None = None


class BasePOSAdapter(ABC):
    def __init__(self, connection):
        self.connection = connection

    @abstractmethod
    def push_order(self, order) -> PushResult:
        """Push order to POS. Returns external_order_id on success."""

    @abstractmethod
    def cancel_order(self, external_order_id: str) -> bool:
        """Cancel a previously pushed order."""

    @abstractmethod
    def get_order_status(self, external_order_id: str) -> str:
        """Check order status in POS."""

    @abstractmethod
    def validate_connection(self) -> bool:
        """Test that credentials are still valid."""

    @abstractmethod
    def refresh_tokens(self) -> bool:
        """Refresh expired OAuth tokens."""
