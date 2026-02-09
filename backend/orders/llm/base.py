from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ParsedOrderItem:
    menu_item_id: int
    variant_id: int
    quantity: int
    modifier_ids: list[int] = field(default_factory=list)
    special_requests: str = ""


@dataclass
class ParsedOrder:
    items: list[ParsedOrderItem]
    language: str = "en"


class LLMProvider(ABC):
    @abstractmethod
    def parse_order(self, raw_input: str, menu_context: str) -> ParsedOrder:
        ...
