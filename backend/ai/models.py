"""
Model resolution: map a model ID string to an agno Model instance.

Supports OpenAI and Anthropic models. The provider is inferred from the
model ID string (e.g. "gpt-4o-mini" → OpenAIChat, "claude-sonnet-4-20250514" → Claude).
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Known prefixes for each provider
_OPENAI_PREFIXES = ("gpt-", "o1-", "o3-", "o4-")
_ANTHROPIC_KEYWORDS = ("claude",)


def resolve_model(model_id: str):
    """
    Given a model ID string, return the appropriate agno Model instance.

    Raises ValueError if the provider cannot be inferred.
    """
    model_id_lower = model_id.lower()

    if any(model_id_lower.startswith(p) for p in _OPENAI_PREFIXES):
        from agno.models.openai import OpenAIChat

        return OpenAIChat(
            id=model_id,
            api_key=settings.OPENAI_API_KEY or None,
        )

    if any(kw in model_id_lower for kw in _ANTHROPIC_KEYWORDS):
        from agno.models.anthropic import Claude

        return Claude(
            id=model_id,
            api_key=settings.ANTHROPIC_API_KEY or None,
        )

    raise ValueError(
        f"Cannot infer LLM provider from model ID '{model_id}'. "
        f"Expected a model name starting with {_OPENAI_PREFIXES} "
        f"or containing one of {_ANTHROPIC_KEYWORDS}."
    )
