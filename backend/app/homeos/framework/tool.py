from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.homeos.framework.spec import ToolSpec

if TYPE_CHECKING:
    from app.repositories.base import Repository


class ToolAdapter(ABC):
    """Wraps one data-source domain. Exposes sync fetch() and an LLM-callable closure.

    Each subclass must define a `spec: ToolSpec` class attribute.
    """

    spec: ToolSpec

    def __init__(self, mock: bool = False) -> None:
        self.mock = mock

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def description(self) -> str:
        return self.spec.description

    @abstractmethod
    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict:
        """Sync pre-fetch called by ToolRepository before LLM inference."""

    @abstractmethod
    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        """Return a plain callable the LLM can invoke during inference."""
