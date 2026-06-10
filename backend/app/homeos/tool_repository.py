from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent

from app.homeos.framework.registry import get_model
from app.homeos.framework.spec import AgentSpec, PrefDimension, ToolSpec
from app.homeos.framework.tool import ToolAdapter

if TYPE_CHECKING:
    from app.repositories.base import Repository


class ToolRepository:
    """Central catalogue for all HomeOS tools and agents."""

    def __init__(self, mock: bool = False) -> None:
        self.mock = mock
        self._tools: dict[str, ToolAdapter] = {}
        self._agents: dict[str, AgentSpec] = {}

    # ── registration ──────────────────────────────────────────────────────────

    def register_tool(self, adapter: ToolAdapter) -> None:
        self._tools[adapter.spec.name] = adapter

    def register_agent(self, spec: AgentSpec) -> None:
        for name in spec.tool_names + spec.prefetch:
            if name not in self._tools:
                raise KeyError(
                    f"Agent '{spec.name}' references unknown tool '{name}'. "
                    f"Register the tool before the agent."
                )
        self._agents[spec.name] = spec

    # ── queries ───────────────────────────────────────────────────────────────

    def get_tool(self, name: str) -> ToolAdapter:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not registered in ToolRepository")
        return self._tools[name]

    def get_agent(self, name: str) -> AgentSpec:
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' not registered in ToolRepository")
        return self._agents[name]

    def tools_for_agent(self, agent_name: str) -> list[ToolAdapter]:
        spec = self.get_agent(agent_name)
        return [self._tools[n] for n in spec.tool_names]

    def agents_using_tool(self, tool_name: str) -> list[str]:
        return [
            name
            for name, spec in self._agents.items()
            if tool_name in spec.tool_names or tool_name in spec.prefetch
        ]

    def describe_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": adapter.spec.name,
                "description": adapter.spec.description,
                "use_case": adapter.spec.use_case,
                "output_schema": adapter.spec.output_type.model_json_schema(),
            }
            for adapter in self._tools.values()
        ]

    def describe_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "tools": spec.tool_names,
                "prefetch": spec.prefetch,
            }
            for spec in self._agents.values()
        ]

    def review_dimensions(self) -> list[PrefDimension]:
        """Union of activating_prefs across tools then agents, registration
        order, deduplicated by field (first declaration wins)."""
        dims: dict[str, PrefDimension] = {}
        for adapter in self._tools.values():
            for d in adapter.spec.activating_prefs:
                dims.setdefault(d.field, d)
        for spec in self._agents.values():
            for d in spec.activating_prefs:
                dims.setdefault(d.field, d)
        return list(dims.values())

    # ── agent builder ─────────────────────────────────────────────────────────

    def build_agent(
        self,
        name: str,
        repo: "Repository",
        block_id: int | None,
        prefs: dict,
        use_prefetch: bool = True,
    ) -> tuple[Agent[Any, Any], dict[str, Any]]:
        """Pre-fetch tool data, inject as context, attach tool closures.

        Returns (Agent, prefetched_context_dict).
        Usage: agent, ctx = tool_repository.build_agent(...); result = await agent.run(prompt)

        use_prefetch=False skips context injection so the agent's declared tools
        become its only data source (used by live tests to prove tool calling).
        """
        spec = self.get_agent(name)

        prefetched: dict[str, Any] = {}
        if use_prefetch:
            for tool_name in spec.prefetch:
                adapter = self._tools[tool_name]
                prefetched[tool_name] = adapter.fetch(repo=repo, block_id=block_id, prefs=prefs)

        context_parts = [
            f"[{k}]\n{json.dumps(v, indent=2)}" for k, v in prefetched.items()
        ]
        system_prompt = spec.system_prompt
        if context_parts:
            system_prompt += "\n\nPre-fetched context:\n" + "\n\n".join(context_parts)

        tools = [
            self._tools[t].as_tool(repo=repo, block_id=block_id, prefs=prefs)
            for t in spec.tool_names
        ]

        agent: Agent[Any, Any] = Agent(
            get_model(),
            output_type=spec.output_type,
            system_prompt=system_prompt,
            tools=tools,
        )
        return agent, prefetched
