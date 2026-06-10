from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


@dataclass
class PrefDimension:
    """A buyer-preference dimension that activates a tool or agent capability.

    query_key: SearchQuery key whose absence in the executed query means
               "never stated" (search-side dims).
    default:   for dims that never reach the SearchQuery — the value that
               means "never stated" (e.g. risk_tolerance default 'low').
    Exactly one of query_key/default should be set.
    """

    field: str
    prompt: str
    question: str = ""
    query_key: str | None = None
    default: Any | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    use_case: str
    output_type: type[BaseModel]
    activating_prefs: list[PrefDimension] = field(default_factory=list)

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
    activating_prefs: list[PrefDimension] = field(default_factory=list)
