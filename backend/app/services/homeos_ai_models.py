"""Pydantic output models for HomeOS Pydantic AI agents.

Each model is the structured return type of one agent. Default values
allow TestModel to return zero-state instances without validation errors.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HomeOSPreferences(BaseModel):
    flat_type: str | None = None
    max_price: float | None = None
    commute_priority: Literal["low", "medium", "high"] = "medium"
    school_priority: Literal["low", "medium", "high"] = "low"
    risk_tolerance: Literal["low", "medium"] = "low"
    appreciation_priority: Literal["medium", "high"] = "medium"


class HomeOSAvatar(BaseModel):
    label: str = "HomeOS Agent"
    buyer_type: Literal["family", "single", "couple", "investor"] = "single"
    summary: str = ""
    preferences: HomeOSPreferences = Field(default_factory=HomeOSPreferences)


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
    narrative: str = ""


class RiskEvidence(BaseModel):
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
