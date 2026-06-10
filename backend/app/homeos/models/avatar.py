from __future__ import annotations

from typing import Literal

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
    town: str | None = None
    min_schools_within_1km: int | None = None
    commute_priority: Literal["low", "medium", "high"] = "low"
    school_priority: Literal["low", "medium", "high"] = "low"
    risk_tolerance: Literal["low", "medium"] = "low"
    appreciation_priority: Literal["medium", "high"] = "medium"
    work_locations: list[str] = Field(default_factory=list)
    bus_reliance: Literal["low", "high"] = "low"

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
