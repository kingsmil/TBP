from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.homeos.framework.agent import AgentDefinition
from app.homeos.framework.tool import ToolAdapter

if TYPE_CHECKING:
    from app.repositories.base import Repository

_VERCEL_BASE_URL = "https://ai-gateway.vercel.sh/v1"
_DEFAULT_GATEWAY_MODEL = "openai/gpt-5.4-nano"


def get_model() -> Model:
    gateway_key = os.getenv("AI_GATEWAY_API_KEY", "")
    provider = os.getenv("LLM_PROVIDER", "vercel" if gateway_key else "test")
    model_name = os.getenv("LLM_MODEL", _DEFAULT_GATEWAY_MODEL)

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


class ToolRegistry:
    def __init__(self, mock: bool = False) -> None:
        self._adapters: dict[str, ToolAdapter] = {}
        self.mock = mock

    def register(self, adapter: ToolAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> ToolAdapter:
        if name not in self._adapters:
            raise KeyError(f"Tool '{name}' not registered")
        return self._adapters[name]


class AgentRegistry:
    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._definitions: dict[str, AgentDefinition] = {}
        self._tools = tool_registry

    def register(self, defn: AgentDefinition) -> None:
        self._definitions[defn.name] = defn

    def build(
        self,
        name: str,
        repo: "Repository",
        block_id: int | None,
        prefs: dict,
    ) -> tuple[Agent[Any, Any], dict[str, Any]]:
        """
        Pre-fetches tool data, injects as context, attaches tool closures.
        Returns (Agent, prefetched_context_dict).
        Caller: agent, ctx = registry.build(...); result = await agent.run(prompt)
        """
        defn = self._definitions[name]

        prefetched: dict[str, Any] = {}
        for tool_name in defn.prefetch:
            adapter = self._tools.get(tool_name)
            prefetched[tool_name] = adapter.fetch(repo=repo, block_id=block_id, prefs=prefs)

        context_parts = [
            f"[{k}]\n{json.dumps(v, indent=2)}" for k, v in prefetched.items()
        ]
        system_prompt = defn.system_prompt
        if context_parts:
            system_prompt += "\n\nPre-fetched context:\n" + "\n\n".join(context_parts)

        tools = [
            self._tools.get(t).as_tool(repo=repo, block_id=block_id, prefs=prefs)
            for t in defn.tool_names
        ]

        agent: Agent[Any, Any] = Agent(
            get_model(),
            output_type=defn.output_type,
            system_prompt=system_prompt,
            tools=tools,
        )
        return agent, prefetched
