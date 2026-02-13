from pydantic import BaseModel, Field


class ParsedOrderItem(BaseModel):
    menu_item_id: int
    variant_id: int
    quantity: int = 1
    modifier_ids: list[int] = Field(default_factory=list)
    special_requests: str = ""


class ParsedOrder(BaseModel):
    items: list[ParsedOrderItem]
    language: str = "en"
