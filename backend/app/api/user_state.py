"""Saved user-state endpoints (Feature 1).

All routes require an authenticated user (require_user). In dev the
AUTH_REQUIRED=false bypass yields user_id=0 (a stable seeded row), so saving
works locally without registering. Anonymous production users get 401 and the
frontend keeps their state in localStorage until they log in.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import CurrentUser, require_user
from app.api.deps import get_engine_or_none
from app.services import user_state as svc
from pydantic import BaseModel

router = APIRouter(prefix="/me", tags=["user-state"])


def _engine():
    engine = get_engine_or_none()
    if engine is None:
        raise HTTPException(status_code=503, detail="Saved state requires PostGIS")
    return engine


# ── preferences ───────────────────────────────────────────────────────────────

class PreferencesBody(BaseModel):
    preferred_property_modes: str | None = None
    last_search_mode: str | None = None
    commute_weight: float | None = None
    lifestyle_weight: float | None = None
    affordability_weight: float | None = None
    schools_weight: float | None = None
    mrt_weight: float | None = None
    future_mrt_weight: float | None = None
    max_budget: int | None = None
    preferred_towns: str | None = None
    preferred_flat_types: str | None = None
    preferred_private_property_types: str | None = None
    metadata_json: dict[str, Any] | None = None


@router.get("/preferences")
def get_preferences(user: Annotated[CurrentUser, Depends(require_user)]):
    return svc.get_preferences(_engine(), user.user_id) or {}


@router.put("/preferences")
def put_preferences(body: PreferencesBody,
                    user: Annotated[CurrentUser, Depends(require_user)]):
    data = body.model_dump(exclude_none=True)
    return svc.upsert_preferences(_engine(), user.user_id, data)


# ── saved locations ───────────────────────────────────────────────────────────

class LocationBody(BaseModel):
    label: str
    address: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lng: float | None = None
    location_type: str = "custom"


class LocationPatch(BaseModel):
    label: str | None = None
    address: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lng: float | None = None
    location_type: str | None = None


@router.get("/locations")
def list_locations(user: Annotated[CurrentUser, Depends(require_user)]):
    return {"results": svc.list_locations(_engine(), user.user_id)}


@router.post("/locations")
def create_location(body: LocationBody,
                    user: Annotated[CurrentUser, Depends(require_user)]):
    return svc.create_location(_engine(), user.user_id, body.model_dump())


@router.patch("/locations/{loc_id}")
def update_location(loc_id: int, body: LocationPatch,
                    user: Annotated[CurrentUser, Depends(require_user)]):
    row = svc.update_location(_engine(), user.user_id, loc_id,
                              body.model_dump(exclude_none=True))
    if row is None:
        raise HTTPException(status_code=404, detail="location not found")
    return row


@router.delete("/locations/{loc_id}")
def delete_location(loc_id: int,
                    user: Annotated[CurrentUser, Depends(require_user)]):
    if not svc.delete_location(_engine(), user.user_id, loc_id):
        raise HTTPException(status_code=404, detail="location not found")
    return {"deleted": loc_id}
