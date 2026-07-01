from __future__ import annotations

import os

from pydantic_ai.models import Model

_VERCEL_BASE_URL = "https://ai-gateway.vercel.sh/v1"
_DEFAULT_GATEWAY_MODEL = "openai/gpt-5.4-nano"
_DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_LOCAL_OPENAI_BASE_URL = "http://localhost:8001/v1"


def _openai_compatible_model(model_name: str, base_url: str, api_key: str = "local") -> Model:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    return OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(base_url=base_url, api_key=api_key),
    )


def _split_prefixed_model(model_name: str, prefix: str) -> str:
    return model_name[len(prefix):] or model_name


def get_model(model_override: str | None = None) -> Model:
    gateway_key = os.getenv("AI_GATEWAY_API_KEY", "")
    provider = os.getenv("LLM_PROVIDER", "vercel" if gateway_key else "test")
    model_name = model_override or os.getenv("LLM_MODEL", _DEFAULT_GATEWAY_MODEL)

    if model_name.startswith("ollama/"):
        return _openai_compatible_model(
            _split_prefixed_model(model_name, "ollama/"),
            os.getenv("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_BASE_URL),
            os.getenv("OLLAMA_API_KEY", "ollama"),
        )

    if model_name.startswith("local/") or model_name.startswith("llama-cpp/"):
        prefix = "llama-cpp/" if model_name.startswith("llama-cpp/") else "local/"
        return _openai_compatible_model(
            _split_prefixed_model(model_name, prefix),
            os.getenv("LOCAL_OPENAI_BASE_URL", _DEFAULT_LOCAL_OPENAI_BASE_URL),
            os.getenv("LOCAL_OPENAI_API_KEY", "local"),
        )

    if provider == "vercel":
        return _openai_compatible_model(
            model_name,
            _VERCEL_BASE_URL,
            gateway_key,
        )
    if provider == "ollama":
        return _openai_compatible_model(
            model_name,
            os.getenv("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_BASE_URL),
            os.getenv("OLLAMA_API_KEY", "ollama"),
        )
    if provider in ("local", "local-openai", "llama-cpp"):
        return _openai_compatible_model(
            model_name,
            os.getenv("LOCAL_OPENAI_BASE_URL", _DEFAULT_LOCAL_OPENAI_BASE_URL),
            os.getenv("LOCAL_OPENAI_API_KEY", "local"),
        )
    if provider == "bedrock":
        from pydantic_ai.models.test import TestModel
        return TestModel()
    if provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        return AnthropicModel(os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001"))
    if provider == "openrouter":
        return _openai_compatible_model(
            model_name,
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            os.getenv("OPENROUTER_API_KEY", ""),
        )
    from pydantic_ai.models.test import TestModel
    return TestModel()
