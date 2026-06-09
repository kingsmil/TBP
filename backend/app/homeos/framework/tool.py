from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.repositories.base import Repository


class ToolAdapter(ABC):
    """Wraps one data-source domain. Exposes sync fetch() and an LLM-callable closure."""

    name: str
    description: str

    def __init__(self, mock: bool = False) -> None:
        self.mock = mock

    @abstractmethod
    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict:
        """Sync pre-fetch called by AgentRegistry before LLM inference."""

    @abstractmethod
    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        """Return a plain callable the LLM can invoke during inference."""
