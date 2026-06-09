"""Pydantic output models for HomeOS Pydantic AI agents.

Each model is the structured return type of one agent. Default values
allow TestModel to return zero-state instances without validation errors.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

_FLAT_TYPE_MAP = {
    "2room": "2 ROOM", "2-room": "2 ROOM", "2 room": "2 ROOM",
    "3room": "3 ROOM", "3-room": "3 ROOM", "3 room": "3 ROOM",
    "4room": "4 ROOM", "4-room": "4 ROOM", "4 room": "4 ROOM",
    "5room": "5 ROOM", "5-room": "5 ROOM", "5 room": "5 ROOM",
    "executive": "EXECUTIVE", "exec": "EXECUTIVE",
}


class HomeOSPreferences(BaseModel):
    flat_type: str | None = None
    max_price: float | None = None
    town: str | None = None                    # e.g. "QUEENSTOWN", "TAMPINES"
    min_schools_within_1km: int | None = None  # explicit school count from user
    commute_priority: Literal["low", "medium", "high"] = "medium"
    school_priority: Literal["low", "medium", "high"] = "low"
    risk_tolerance: Literal["low", "medium"] = "low"
    appreciation_priority: Literal["medium", "high"] = "medium"

    @field_validator("flat_type", mode="before")
    @classmethod
    def normalise_flat_type(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalised = _FLAT_TYPE_MAP.get(v.lower().strip())
        return normalised if normalised else v.upper().strip()

    @field_validator("town", mode="before")
    @classmethod
    def normalise_town(cls, v: str | None) -> str | None:
        return v.upper().strip() if v else None


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
