"""
Order parsing agent using agno.

Replaces the raw OpenAI provider with a structured agent that supports
multiple LLM providers and returns a typed ParsedOrder response.
"""

from typing import Any, Optional, Type

from pydantic import BaseModel

from ai.base_agent import BaseAgent
from orders.llm.base import ParsedOrder

INSTRUCTIONS = """\
You are an order-taking assistant for a restaurant. Given a customer's \
natural language order and the restaurant's menu, extract the structured order.

Rules:
- Only use menu_item_id, variant_id, and modifier_id values from the menu provided
- If the customer doesn't specify a variant, use the DEFAULT variant
- If quantity is not specified, assume 1
- Keep special_requests brief and in English
- Detect the language the customer wrote/spoke in and set the "language" field
- If something the customer asked for is not on the menu, skip it (do NOT invent IDs)
"""


class OrderParsingAgent(BaseAgent):
    default_model = "gpt-4o-mini"

    def get_name(self) -> str:
        return "OrderParsingAgent"

    def get_instructions(self) -> str:
        return INSTRUCTIONS

    def get_output_schema(self) -> Optional[Type[BaseModel]]:
        return ParsedOrder

    def get_context(self, **kwargs: Any) -> dict[str, str]:
        context = {}
        if "raw_input" in kwargs:
            context["customer_order"] = kwargs["raw_input"]
        if "menu_context" in kwargs:
            context["restaurant_menu"] = kwargs["menu_context"]
        return context

    def prompt(self, **kwargs: Any) -> str:
        return "Parse the customer's order from the provided context."
