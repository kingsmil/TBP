"""Pydantic request bodies for the POST endpoints (Phase 3)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.geo import Point
from app.core.models import HDBTown
from app.services.commute.models import Destination, Person


class DestinationIn(BaseModel):
    name: str
    lat: float
    lon: float
    visits_per_week: float = Field(1.0, ge=0)
    mode: str = "pt"

    def to_domain(self) -> Destination:
        return Destination(self.name, Point(self.lon, self.lat),
                           self.visits_per_week, self.mode)


class CommuteRequest(BaseModel):
    destinations: list[DestinationIn]
    limit: int = Field(100, ge=1, le=2000)

    def domain_destinations(self) -> list[Destination]:
        return [d.to_domain() for d in self.destinations]


class CommutePlaceIn(BaseModel):
    label: str | None = None
    lat: float
    lon: float


class CommuteToPlacesRequest(BaseModel):
    """One origin (a property) → travel time to each of the user's saved places."""
    origin_lat: float
    origin_lon: float
    places: list[CommutePlaceIn] = []


class DirectTransitDestinationIn(BaseModel):
    name: str
    lat: float
    lon: float


class DirectTransitRequest(BaseModel):
    destinations: list[DirectTransitDestinationIn] = Field(..., min_length=1, max_length=5)
    max_walk_minutes: float = Field(6.0, gt=0, le=30)
    modes: list[str] = ["bus", "mrt"]
    town: HDBTown | None = None
    planning_area_id: int | None = None
    flat_type: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    min_psf: float | None = None
    max_psf: float | None = None
    max_mrt_distance_m: float | None = None
    min_schools_within_1km: int | None = None
    limit: int = Field(500, ge=1, le=2000)


class PersonIn(BaseModel):
    label: str
    destinations: list[DestinationIn]

    def to_domain(self) -> Person:
        return Person(self.label, tuple(d.to_domain() for d in self.destinations))


class CoupleRequest(BaseModel):
    person_a: PersonIn
    person_b: PersonIn
    weights: dict[str, float] | None = None
    limit: int = Field(100, ge=1, le=2000)


class LifestyleRequest(BaseModel):
    destinations: list[DestinationIn] = []
    weights: dict[str, float] | None = None


class RecommendationRequest(BaseModel):
    destinations: list[DestinationIn] = []
    weights: dict[str, float] | None = None
    limit: int = Field(10, ge=1, le=200)

    def domain_destinations(self):
        return [d.to_domain() for d in self.destinations] if self.destinations else None


class ScoreRankingRequest(BaseModel):
    """Body for POST /score-ranking — user-weighted property ranking."""
    weights: dict[str, float] = Field(default_factory=dict)
    destinations: list[DestinationIn] = []
    limit: int = Field(20, ge=1, le=200)

    def domain_destinations(self) -> list[Destination] | None:
        return [d.to_domain() for d in self.destinations] if self.destinations else None


class RecommendRequest(BaseModel):
    """Body for POST /compare/recommend — questionnaire answers + optional town."""
    answers: dict[str, str] = Field(default_factory=dict)
    town: str | None = None
    flat_type: str | None = None


class HomeOSInvestigationRequest(BaseModel):
    profile_text: str = Field(..., min_length=10)
    limit: int = Field(5, ge=1, le=20)
    model: str | None = None


class HomeOSCaseFileRequest(BaseModel):
    profile_text: str = Field(..., min_length=10)
    case_id: str | None = None
    model: str | None = None


class HomeOSScheduleViewingRequest(BaseModel):
    profile_text: str = Field(..., min_length=10)
    block_id: int
    availability: list[str] = Field(..., min_length=1)
    contact_name: str = Field(..., min_length=1)
    contact_note: str | None = None
    model: str | None = None


class HomeOSStreamRequest(BaseModel):
    profile_text: str = Field(..., min_length=10)
    limit: int = Field(5, ge=1, le=20)
    model: str | None = None


class HomeOSChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    model: str | None = None


class HomeOSRefineRequest(BaseModel):
    message: str = Field(..., min_length=1)
    model: str | None = None


class DreamHomeRequest(BaseModel):
    max_price: float | None = None
    flat_type: str | None = None
    min_remaining_lease: int | None = None
    max_mrt_distance_m: float | None = None
    min_schools_within_1km: int | None = None
    destinations: list[DestinationIn] = []
    weights: dict[str, float] | None = None
    limit: int = Field(20, ge=1, le=500)

    def to_criteria(self):
        from app.services.dream_home import DreamCriteria
        return DreamCriteria(
            max_price=self.max_price,
            flat_type=self.flat_type,
            min_remaining_lease=self.min_remaining_lease,
            max_mrt_distance_m=self.max_mrt_distance_m,
            min_schools_within_1km=self.min_schools_within_1km,
            destinations=[d.to_domain() for d in self.destinations],
            weights=self.weights,
            limit=self.limit,
        )


class OutreachRequest(BaseModel):
    """Body for POST /listings/{listing_id}/outreach-message."""
    case_id: str | None = None
    contact_name: str | None = None
    availability: list[str] = Field(default_factory=list)
    note: str | None = None


class NewsItem(BaseModel):
    title: str
    url: str
    published_date: str | None = None
    domain: str | None = None
