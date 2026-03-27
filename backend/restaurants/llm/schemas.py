from decimal import Decimal
from pydantic import BaseModel, Field


class ParsedMenuVariant(BaseModel):
    label: str
    price: Decimal = Field(max_digits=8, decimal_places=2)


class ParsedMenuItem(BaseModel):
    name: str
    description: str | None = None
    variants: list[ParsedMenuVariant] = Field(min_length=1)


class ParsedMenuCategory(BaseModel):
    name: str
    items: list[ParsedMenuItem]


class ParsedMenuPage(BaseModel):
    categories: list[ParsedMenuCategory]


class ParsedMenu(BaseModel):
    categories: list[ParsedMenuCategory]
