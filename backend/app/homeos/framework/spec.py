from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel


@dataclass
class ToolSpec:
    name: str
    description: str
    use_case: str
    output_type: type[BaseModel]

    def __post_init__(self) -> None:
        if not (isinstance(self.output_type, type) and issubclass(self.output_type, BaseModel)):
            raise TypeError(
                f"output_type must be a BaseModel subclass, got {self.output_type!r}"
            )


@dataclass
class AgentSpec:
    name: str
    description: str
    system_prompt: str
    output_type: type[BaseModel]
    tool_names: list[str] = field(default_factory=list)
    prefetch: list[str] = field(default_factory=list)
