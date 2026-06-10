from __future__ import annotations

import os

from pydantic_ai.models import Model

_VERCEL_BASE_URL = "https://ai-gateway.vercel.sh/v1"
_DEFAULT_GATEWAY_MODEL = "openai/gpt-5.4-nano"


def get_model(model_override: str | None = None) -> Model:
    gateway_key = os.getenv("AI_GATEWAY_API_KEY", "")
    provider = os.getenv("LLM_PROVIDER", "vercel" if gateway_key else "test")
    model_name = model_override or os.getenv("LLM_MODEL", _DEFAULT_GATEWAY_MODEL)

    if provider in ("vercel",) or (provider == "test" and gateway_key):
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIModel(
            model_name,
            provider=OpenAIProvider(base_url=_VERCEL_BASE_URL, api_key=gateway_key),
        )
    if provider == "bedrock":
        from pydantic_ai.models.test import TestModel
        return TestModel()
    if provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        return AnthropicModel(os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001"))
    if provider == "openrouter":
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIModel(
            model_name,
            provider=OpenAIProvider(
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                api_key=os.getenv("OPENROUTER_API_KEY", ""),
            ),
        )
    from pydantic_ai.models.test import TestModel
    return TestModel()
