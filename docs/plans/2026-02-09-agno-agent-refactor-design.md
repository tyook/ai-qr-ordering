# Agno Agent Refactor Design

## Goal

Replace the raw OpenAI client usage in `orders/llm/openai_provider.py` with a lightweight agent framework built on [agno](https://github.com/agno-agi/agno), following patterns from carta-ai.

## Architecture

### New `ai/` module (backend root)

```
backend/
  ai/
    __init__.py
    base_agent.py      # BaseAgent abstract class wrapping agno Agent
    models.py           # Model string → agno model instance resolution
```

### BaseAgent

Thin abstract class providing:

- `get_name()` — agent identifier string
- `get_instructions()` — system prompt
- `get_output_schema()` — Pydantic BaseModel class (or None)
- `get_context(**kwargs)` — returns `dict[str, str]`, formatted as XML sections
- `default_model` — class-level default model string (e.g. `"gpt-4o-mini"`)
- `run(prompt, **kwargs)` — classmethod: resolves model, builds context, creates agno Agent, runs, returns typed response

### Context system

`get_context(**kwargs)` returns a dict where keys become XML tags:

```python
{"customer_order": "two pizzas", "restaurant_menu": "..."}
```

Formatted as:

```xml
<customer_order>
two pizzas
</customer_order>

<restaurant_menu>
...
</restaurant_menu>
```

Passed as agno's `additional_context`.

### Model resolution

A `resolve_model(model_id: str)` function maps string identifiers to agno model instances:

- Strings starting with `gpt-` or `o1-` or `o3-` → `OpenAIChat`
- Strings containing `claude` → `Claude`

Global `LLM_MODEL` Django setting overrides any agent's `default_model`.

### Providers supported

- OpenAI (via `agno.models.openai.OpenAIChat`)
- Anthropic (via `agno.models.anthropic.Claude`)

## OrderParsingAgent

Replaces `OpenAIProvider`. Lives at `orders/llm/agent.py`.

- `default_model = "gpt-4o-mini"`
- `get_instructions()` — existing system prompt (menu ID rules, language detection, etc.)
- `get_output_schema()` → `ParsedOrder` (converted from dataclass to Pydantic BaseModel)
- `get_context()` → `{"customer_order": raw_input, "restaurant_menu": menu_context}`

## Changes to existing code

- `orders/llm/base.py` — Convert dataclasses to Pydantic BaseModel
- `orders/llm/openai_provider.py` — Deleted
- `orders/llm/agent.py` — New: OrderParsingAgent
- `orders/llm/__init__.py` — Updated exports
- `orders/views.py` — `get_llm_provider()` replaced with `OrderParsingAgent.run()`
- `orders/llm/menu_context.py` — Unchanged
- `orders/services.py` — Unchanged
- `config/settings.py` — Add `LLM_MODEL` setting
