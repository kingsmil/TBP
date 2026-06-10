from __future__ import annotations

import os
from typing import Any


def is_mock_mode() -> bool:
    from app.config import settings
    return os.getenv("HOMEOS_AGENT_MODE", settings.homeos_agent_mode).lower() == "mock"


def mock_delay_seconds() -> float:
    raw = os.getenv("HOMEOS_MOCK_DELAY_SECONDS", "1")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 1.0


def mock_transaction_data(block_id: int, prefs: dict) -> dict[str, Any]:
    flat_type = prefs.get("flat_type") or "4 ROOM"
    max_price = prefs.get("max_price", 700_000)
    median = 650_000.0
    return {
        "transaction_count": 4,
        "median_price": median,
        "median_psf": round(median / 90, 2),
        "window_months": 6,
        "budget_signal": "within_budget" if max_price and median <= max_price else "above_budget",
        "confidence": "medium",
    }


def mock_proximity_data(block_id: int) -> dict[str, Any]:
    return {
        "connections": [
            {"type": "mrt", "name": "Nearest operational MRT", "distance_m": 480, "signal": "strong"},
            {"type": "primary_school", "name": "Primary schools within 1km", "count": 1, "signal": "moderate"},
        ]
    }


def mock_appreciation_data(block_id: int) -> dict[str, Any]:
    return {"appreciation_score": 60, "risk_level": "low", "narrative": "Mock appreciation data."}


def mock_future_dev_data(block_id: int) -> dict[str, Any]:
    return {
        "future_mrt": {"stations": [], "nearest_future_mrt_distance_m": None},
        "future_supply": {"supply_risk_level": "low", "bto_projects_within_1km": 0},
    }


def mock_accessibility_data(block_id: int) -> dict[str, Any]:
    return {"bus_stops_within_500m": 3, "nearest_bus_distance_m": 120}


def mock_commute_data(block_id: int, prefs: dict) -> dict[str, Any]:
    workplaces = prefs.get("work_locations") or []
    if not workplaces:
        return {"available": False, "destinations": [], "worst_commute_min": None}
    destinations = [
        {"name": name, "resolved": True, "travel_min": 35.0, "transfers": 0, "mode": "pt"}
        for name in workplaces
    ]
    return {"available": True, "destinations": destinations, "worst_commute_min": 35.0}


def mock_bus_routes_data(block_id: int) -> dict[str, Any]:
    return {"available": True, "nearest_stop_code": "00000", "services": ["12", "38"], "destination_examples": []}


def mock_search_data(prefs: dict, limit: int) -> list[dict[str, Any]]:
    return []
