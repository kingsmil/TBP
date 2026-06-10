from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MarketEvidence(BaseModel):
    transaction_count: int = 0
    median_price: float | None = None
    median_psf: float | None = None
    window_months: int = 6
    budget_signal: Literal["within_budget", "above_budget", "unknown"] = "unknown"
    confidence: Literal["high", "medium", "low"] = "low"
    narrative: str = ""


class LocationEvidence(BaseModel):
    connections: list[dict[str, Any]] = Field(default_factory=list)
    commute: dict[str, Any] = Field(default_factory=dict)
    bus_routes: dict[str, Any] = Field(default_factory=dict)
    narrative: str = ""


class RiskEvidence(BaseModel):
    appreciation: dict[str, Any] = Field(default_factory=dict)
    future_mrt: dict[str, Any] = Field(default_factory=dict)
    future_supply: dict[str, Any] = Field(default_factory=dict)
    accessibility: dict[str, Any] = Field(default_factory=dict)
    watchouts: list[str] = Field(default_factory=list)
    score_adjustment: float = 0.0
    narrative: str = ""


class AgentQuestions(BaseModel):
    questions: list[str] = Field(default_factory=list)
    narrative: str = ""


class WorthViewingResult(BaseModel):
    score: float = 0.0
    verdict: Literal["Worth viewing", "Maybe view", "Skip for now"] = "Skip for now"
    confidence: Literal["high", "medium", "low"] = "low"
    top_reasons: list[str] = Field(default_factory=list)
    top_watchouts: list[str] = Field(default_factory=list)
