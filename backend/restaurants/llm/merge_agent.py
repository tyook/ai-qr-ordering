"""
Menu merge agent using GPT-4o-mini.

Accepts a list of ParsedMenuPage objects (one per scanned image) and merges
them into a single de-duplicated ParsedMenu.
"""

import json
from typing import Any

from pydantic import BaseModel

from ai.base_agent import BaseAgent
from restaurants.llm.schemas import ParsedMenu, ParsedMenuPage

INSTRUCTIONS = """\
You are a menu consolidation assistant. You will receive JSON representing \
multiple pages of a restaurant menu that have been parsed separately. \
Your job is to merge them into a single, clean menu.

Rules:
- Combine items from the same category across pages into one category entry.
- If the same item appears on multiple pages, keep only one copy (deduplicate \
by name within each category).
- Preserve all category and item names exactly as given.
- Do not invent new items or prices.
- The output must contain every item that appeared in any of the input pages.
"""


class MenuMergeAgent(BaseAgent):
    default_model = "gpt-4o-mini"

    def get_name(self) -> str:
        return "MenuMergeAgent"

    def get_instructions(self) -> str:
        return INSTRUCTIONS

    def get_output_schema(self) -> type[BaseModel] | None:
        return ParsedMenu

    def get_context(self, **kwargs: Any) -> dict[str, str]:
        pages: list[ParsedMenuPage] = kwargs.get("pages", [])
        serialized = json.dumps(
            [page.model_dump(mode="json") for page in pages],
            indent=2,
        )
        return {"menu_pages": serialized}

    def prompt(self, **kwargs: Any) -> str:
        return "Merge all the menu pages in <menu_pages> into a single unified menu."

    @classmethod
    def run(cls, pages: list[ParsedMenuPage], **kwargs: Any) -> ParsedMenu:  # type: ignore[override]
        """
        Merge multiple parsed menu pages into one ParsedMenu.

        Short-circuits for a single page: wraps its categories directly
        without an LLM call.

        Args:
            pages: One ParsedMenuPage per scanned image.

        Returns:
            A single ParsedMenu combining all pages.
        """
        if not pages:
            return ParsedMenu(categories=[])

        if len(pages) == 1:
            return ParsedMenu(categories=pages[0].categories)

        instance = cls()
        agent = instance._build_agent(pages=pages)

        result = agent.run(instance.prompt(pages=pages))
        return result.content
