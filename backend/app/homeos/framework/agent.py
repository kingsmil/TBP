from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel


@dataclass
class AgentDefinition:
    """Declares an agent's prompt, output schema, and tool dependencies."""

    name: str
    system_prompt: str
    output_type: type[BaseModel]
    tool_names: list[str] = field(default_factory=list)
    prefetch: list[str] = field(default_factory=list)
