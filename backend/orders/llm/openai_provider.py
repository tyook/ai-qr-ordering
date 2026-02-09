import json
import logging

from openai import OpenAI
from django.conf import settings

from orders.llm.base import LLMProvider, ParsedOrder, ParsedOrderItem

logger = logging.getLogger(__name__)

openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """You are an order-taking assistant for a restaurant. Given a customer's natural language order and the restaurant's menu, extract the structured order.

Return ONLY valid JSON in this exact format:
{
  "items": [
    {
      "menu_item_id": <int>,
      "variant_id": <int>,
      "quantity": <int>,
      "modifier_ids": [<int>, ...],
      "special_requests": "<string>"
    }
  ],
  "language": "<ISO 639-1 code of the language the customer used>"
}

Rules:
- Only use item_id, variant_id, and modifier_id values from the menu provided
- If the customer doesn't specify a variant, use the DEFAULT variant
- If quantity is not specified, assume 1
- Keep special_requests brief and in English
- Detect the language the customer wrote/spoke in and set the "language" field
- If something the customer asked for is not on the menu, skip it (do NOT invent IDs)
"""


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model

    def parse_order(self, raw_input: str, menu_context: str) -> ParsedOrder:
        user_message = f"""Customer's order:
\"{raw_input}\"

Restaurant menu:
{menu_context}"""

        response = openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        raw_json = response.choices[0].message.content
        logger.info("LLM raw response: %s", raw_json)

        data = json.loads(raw_json)
        items = [
            ParsedOrderItem(
                menu_item_id=item["menu_item_id"],
                variant_id=item["variant_id"],
                quantity=item.get("quantity", 1),
                modifier_ids=item.get("modifier_ids", []),
                special_requests=item.get("special_requests", ""),
            )
            for item in data.get("items", [])
        ]

        return ParsedOrder(items=items, language=data.get("language", "en"))
