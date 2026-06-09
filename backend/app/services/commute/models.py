"""Commute domain types (Phase 3)."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.geo import Point


@dataclass(frozen=True)
class Destination:
    """A place the user travels to, with how often (round trips per week)."""
    name: str
    point: Point
    visits_per_week: float = 1.0
    mode: str = "pt"  # 'pt' (public transport) | 'walk' | 'drive'


@dataclass(frozen=True)
class CommuteResult:
    """One origin->destination journey estimate."""
    total_minutes: float
    walk_minutes: float
    transfers: int
    distance_m: float
    mode: str


@dataclass(frozen=True)
class Person:
    """A person in couple mode: a label plus their destinations."""
    label: str
    destinations: tuple[Destination, ...]
