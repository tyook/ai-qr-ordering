"""
Lightweight base agent wrapping agno's Agent.

Inspired by carta-ai's BaseAgnoAgent but stripped down for simplicity.
Provides: model resolution, structured output, and XML context injection.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from agno.agent import Agent
from django.conf import settings
from pydantic import BaseModel

from ai.models import resolve_model

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base for all agents in the project.

    Subclasses must implement:
        - get_name()
        - get_instructions()
        - get_output_schema()

    Optionally override:
        - default_model (class var)
        - get_context(**kwargs)
    """

    default_model: str = "gpt-4o-mini"

    # ── Abstract interface ──────────────────────────────────────────────

    @abstractmethod
    def get_name(self) -> str:
        """Return a short identifier for this agent."""
        ...

    @abstractmethod
    def get_instructions(self) -> str:
        """Return the system-level instructions (prompt)."""
        ...

    @abstractmethod
    def get_output_schema(self) -> Optional[Type[BaseModel]]:
        """Return a Pydantic model class for structured output, or None."""
        ...

    def get_context(self, **kwargs: Any) -> dict[str, str]:
        """
        Return context sections as {tag_name: content}.
        Override in subclasses to inject context into the agent prompt.
        """
        return {}

    # ── Internal helpers ────────────────────────────────────────────────

    def _resolve_model(self):
        """Resolve model: global LLM_MODEL setting overrides default_model."""
        model_id = getattr(settings, "LLM_MODEL", "") or self.default_model
        return resolve_model(model_id)

    @staticmethod
    def _format_context(context: dict[str, str]) -> str:
        """Format context dict as XML sections."""
        if not context:
            return ""
        sections = []
        for tag, content in context.items():
            sections.append(f"<{tag}>\n{content}\n</{tag}>")
        return "\n\n".join(sections)

    def _build_agent(self, **kwargs: Any) -> Agent:
        """Create the underlying agno Agent instance."""
        model = self._resolve_model()
        context = self.get_context(**kwargs)
        additional_context = self._format_context(context)
        output_schema = self.get_output_schema()

        return Agent(
            name=self.get_name(),
            model=model,
            instructions=self.get_instructions(),
            additional_context=additional_context or None,
            output_schema=output_schema,
            structured_outputs=output_schema is not None,
            markdown=False,
        )

    # ── Public API ──────────────────────────────────────────────────────

    @classmethod
    def run(cls, prompt: str = "", **kwargs: Any) -> Any:
        """
        Instantiate the agent, run it, and return the typed response.

        Args:
            prompt: The user-facing message to send to the agent.
            **kwargs: Passed to get_context() for context building.

        Returns:
            The parsed output_schema instance (if structured) or a string.
        """
        instance = cls()
        agent = instance._build_agent(**kwargs)

        run_prompt = prompt or instance.prompt(**kwargs)
        logger.info("[%s] Running with model=%s", instance.get_name(), agent.model)

        result = agent.run(run_prompt)
        return result.content

    def prompt(self, **kwargs: Any) -> str:
        """
        Default prompt for the agent. Override for agents that have a
        standard prompt and don't need one passed to run().
        """
        return ""
