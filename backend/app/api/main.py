"""FastAPI application — Phase 1 endpoints.

Runs against PostGIS when DATABASE_URL is set, otherwise against a seeded
in-memory repository (see app.api.deps). The tile endpoint requires PostGIS;
the reference endpoint works in both modes.
"""
from __future__ import annotations

import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

import httpx

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_commute_provider, get_engine_or_none, get_repository
from app.api.auth import router as auth_router, require_subscribed
from app.api.user_state import router as user_state_router
import json

from fastapi.responses import StreamingResponse, RedirectResponse

from app.api.schemas import (
    NewsItem,
    OutreachRequest,
    CommuteRequest,
    CommuteToPlacesRequest,
    CoupleRequest,
    DreamHomeRequest,
    HomeOSCaseFileRequest,
    HomeOSChatRequest,
    HomeOSInvestigationRequest,
    HomeOSRefineRequest,
    HomeOSScheduleViewingRequest,
    HomeOSStreamRequest,
    LifestyleRequest,
    RecommendationRequest,
    RecommendRequest,
    ScoreRankingRequest,
    DirectTransitRequest,
)
from app.config import settings
from app.core.models import HDBTown, SearchQuery
from app.homeos import case_store as homeos_case_store
from app.homeos.case_assembler import assemble_case_file_from_case
from app.homeos.pipeline import (
    build_homeos_case_file,
    chat_in_case,
    investigate_homeos_profile,
    investigate_stream,
    refine_stream,
    schedule_homeos_viewing,
)
from app.api.tiles import LAYERS, build_tile
from app.repositories.base import Repository
from app.services import accessibility as access_svc
from app.services import analytics as analytics_svc
from app.services import block_agents as block_agents_svc
from app.services import outreach as outreach_svc
from app.services.appreciation import appreciation as appreciation_svc
from app.services.comparison import compare_estates_cached, warm_comparison_cache
from app.services.commute.couple import couple_optimize, recommended_estates
from app.services.commute.optimizer import commute_heatmap, optimize_commute
from app.services.dream_home import dream_home_finder
from app.services.forecasting import block_forecast, estate_forecast
from app.services.future_dev import future_mrt, future_supply
from app.services.lifestyle import block_lifestyle
from app.services.recommendation import recommend
from app.services import score_ranking as score_ranking_svc
from app.analysis import appreciation_rankings as appreciation_rankings_svc
from app.services import bto as bto_svc
from app.services import bto_mop as bto_mop_svc
from app.services import bto_compare as bto_compare_svc
from app.services import recommend_path as recommend_path_svc
from app.services import amenities as amenities_svc
from app.services.private_property import service as private_svc
from app.services import images as images_svc
from app.services.search import search_blocks
from app.services.undervalued import detect_undervalued

from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(application):
    from app.homeos.wiring import setup as homeos_setup
    homeos_setup()
    from app.analysis.scheduler import start_ranking_refresh
    refresh_task = start_ranking_refresh()
    # Warm the shared estate-comparison cache in the background so the first
    # request is already instant (PostGIS only — mock mode is tiny/fast).
    if get_engine_or_none() is not None:
        warm_comparison_cache(get_repository())
    try:
        yield
    finally:
        if refresh_task is not None:
            refresh_task.cancel()


app = FastAPI(title="HDB Match API", version="0.1.0",
              description="Geospatial analytics platform for Singapore HDB.",
              lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(user_state_router)


@app.get("/health")
def health():
    repo = get_repository()
    return {"status": "ok", "blocks": len(repo.blocks()),
            "mode": "postgis" if get_engine_or_none() else "mock"}


@app.get("/models")
def list_models():
    """List available AI models for HomeOS agents."""
    default_model = os.getenv("LLM_MODEL", "qwen3:8b")
    if os.getenv("LLM_PROVIDER", "ollama") == "ollama" and not default_model.startswith("ollama/"):
        default_model = f"ollama/{default_model}"
    local_models = [
        {"id": "ollama/qwen3:8b", "name": "Qwen3 8B", "provider": "Local Ollama", "local": True},
        {"id": "ollama/llama3.1:8b", "name": "Llama 3.1 8B", "provider": "Local Ollama", "local": True},
        {"id": "ollama/mistral-nemo", "name": "Mistral Nemo 12B", "provider": "Local Ollama", "local": True},
        {"id": "local/hdb-agent", "name": "OpenAI-compatible local server", "provider": "Local", "local": True},
    ]
    cloud_models = [
        {"id": "openai/gpt-5.4-mini", "name": "GPT-5.4 Mini", "provider": "OpenAI"},
        {"id": "openai/gpt-5.4-nano", "name": "GPT-5.4 Nano", "provider": "OpenAI"},
        {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
        {"id": "openai/gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "OpenAI"},
        {"id": "anthropic/claude-sonnet-4.5", "name": "Claude 4.5 Sonnet", "provider": "Anthropic"},
        {"id": "anthropic/claude-3.5-haiku", "name": "Claude 3.5 Haiku", "provider": "Anthropic"},
        {"id": "anthropic/claude-opus-4", "name": "Claude 4 Opus", "provider": "Anthropic"},
        {"id": "meta-llama/llama-3.2-90b", "name": "Llama 3.2 90B", "provider": "Meta"},
        {"id": "meta-llama/llama-3.1-70b", "name": "Llama 3.1 70B", "provider": "Meta"},
        {"id": "google/gemini-2.5-pro", "name": "Gemini 2.5 Pro", "provider": "Google"},
    ]
    return {
        "models": [*local_models, *cloud_models],
        "default": default_model,
        "local_runtime": {
            "ollama_base_url": "http://localhost:11434/v1",
            "openai_compatible_base_url": "http://localhost:8001/v1",
            "notes": "Use ollama/<model> for Ollama or local/<model> for llama.cpp/other OpenAI-compatible local servers.",
        },
    }


@app.get("/properties/search")
def properties_search(
    minx: float | None = None, miny: float | None = None,
    maxx: float | None = None, maxy: float | None = None,
    town: HDBTown | None = None,
    planning_area_id: int | None = None,
    flat_type: str | None = None,
    min_floor_area: float | None = None,
    max_floor_area: float | None = None,
    min_lease_year: int | None = None,
    max_lease_year: int | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_psf: float | None = None,
    max_psf: float | None = None,
    max_mrt_distance_m: float | None = None,
    max_bus_distance_m: float | None = None,
    min_schools_within_1km: int | None = None,
    limit: int = Query(500, ge=1, le=20_000),
    repo: Repository = Depends(get_repository),
):
    bbox = None
    if None not in (minx, miny, maxx, maxy):
        bbox = (minx, miny, maxx, maxy)
    q = SearchQuery(
        bbox=bbox, town=town, planning_area_id=planning_area_id,
        flat_type=flat_type, min_floor_area=min_floor_area,
        max_floor_area=max_floor_area, min_lease_year=min_lease_year,
        max_lease_year=max_lease_year, min_price=min_price, max_price=max_price,
        min_psf=min_psf, max_psf=max_psf, max_mrt_distance_m=max_mrt_distance_m,
        max_bus_distance_m=max_bus_distance_m,
        min_schools_within_1km=min_schools_within_1km, limit=limit,
    )
    results = search_blocks(repo, q)
    return {"count": len(results), "results": results}


@app.get("/properties/{block_id}")
def property_detail(block_id: int, repo: Repository = Depends(get_repository)):
    block = repo.block(block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="block not found")
    prox = repo.proximity(block_id)
    txns = sorted(repo.transactions_for_block(block_id),
                  key=lambda t: t.transaction_month, reverse=True)[:50]
    return {
        "block_id": block.block_id,
        "block_number": block.block_number,
        "street_name": block.street_name,
        "town": block.town,
        "planning_area_id": block.planning_area_id,
        "lon": block.point.lon, "lat": block.point.lat,
        "lease_commencement_year": block.lease_commencement_year,
        "proximity": prox.__dict__ if prox else None,
        "analytics": analytics_svc.block_analytics(repo, block_id),
        "recent_transactions": [
            {"month": t.transaction_month, "flat_type": t.flat_type,
             "resale_price": t.resale_price, "psf": round(t.psf, 2),
             "floor_area_sqm": t.floor_area_sqm, "storey_range": t.storey_range}
            for t in txns
        ],
    }


@app.get("/blocks/agents")
def block_agents(address: str = Query(..., min_length=3),
                 repo: Repository = Depends(get_repository)):
    """Agents marketing units in a block, looked up by address.

    Example: /blocks/agents?address=104A Bidadari Pk Dr
    """
    try:
        data = block_agents_svc.find_block_agents(repo, address)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if data is None:
        raise HTTPException(status_code=404, detail="block not found for address")
    return data


@app.get("/blocks/{block_id}/listings")
def block_listings(
    block_id: int,
    listing_type: str = Query("resale"),
    repo: Repository = Depends(get_repository),
):
    """Active resale/rental listings for a block, cheapest first."""
    if repo.block(block_id) is None:
        raise HTTPException(status_code=404, detail="block not found")
    if listing_type not in {"resale", "rent", "all"}:
        raise HTTPException(status_code=422, detail="listing_type must be resale, rent, or all")
    kind = None if listing_type == "all" else listing_type
    listings = sorted(repo.active_listings_for_block(block_id, kind), key=lambda a: a.price)
    out = []
    for a in listings:
        d = {k: v for k, v in a.__dict__.items() if v is not None}
        d["floor_area_sqft"] = round(a.floor_area_sqft, 1)
        out.append(d)
    return {"count": len(out), "listings": out}


@app.post("/listings/{listing_id}/outreach-message")
def listing_outreach_message(
    listing_id: int,
    body: OutreachRequest,
    repo: Repository = Depends(get_repository),
):
    """AI-prepared WhatsApp message for the chosen listing's seller/agent."""
    try:
        return outreach_svc.prepare_outreach_message(
            repo, listing_id, listing_type=body.listing_type,
            case_id=body.case_id, contact_name=body.contact_name,
            availability=body.availability, note=body.note)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/analytics/estate/{planning_area_id}")
def estate_analytics(planning_area_id: int, flat_type: str | None = None,
                     repo: Repository = Depends(get_repository)):
    data = analytics_svc.estate_analytics(repo, planning_area_id, flat_type)
    if data is None:
        raise HTTPException(status_code=404, detail="estate not found")
    return data


@app.get("/analytics/block/{block_id}")
def block_analytics(block_id: int, flat_type: str | None = None,
                    repo: Repository = Depends(get_repository)):
    data = analytics_svc.block_analytics(repo, block_id, flat_type)
    if data is None:
        raise HTTPException(status_code=404, detail="block not found")
    return data


@app.get("/accessibility/block/{block_id}")
def accessibility_block(block_id: int, repo: Repository = Depends(get_repository)):
    data = access_svc.block_accessibility(repo, block_id)
    if data is None:
        raise HTTPException(status_code=404, detail="block not found")
    return data


@app.get("/accessibility/estate/{planning_area_id}")
def accessibility_estate(planning_area_id: int,
                         repo: Repository = Depends(get_repository)):
    data = access_svc.estate_accessibility(repo, planning_area_id)
    if data is None:
        raise HTTPException(status_code=404, detail="estate not found")
    return data


@app.get("/comparison/estates")
def comparison_estates(
    estates: str | None = Query(None, description="comma-separated planning_area_ids"),
    flat_type: str | None = None,
    repo: Repository = Depends(get_repository),
):
    ids = None
    if estates:
        try:
            ids = [int(x) for x in estates.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid estates list")
    return {"estates": compare_estates_cached(repo, ids, flat_type)}


@app.post("/homeos/investigate")
def homeos_investigate(req: HomeOSInvestigationRequest,
                       repo: Repository = Depends(get_repository),
                       _user=Depends(require_subscribed)):
    return investigate_homeos_profile(repo, req.profile_text, req.limit)


@app.post("/homeos/case-file/{block_id}")
def homeos_case_file(block_id: int, req: HomeOSCaseFileRequest,
                     repo: Repository = Depends(get_repository),
                     _user=Depends(require_subscribed)):
    if req.case_id:
        assembled = assemble_case_file_from_case(req.case_id, block_id)
        if assembled is not None:
            return assembled
    try:
        return build_homeos_case_file(repo, req.profile_text, block_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/homeos/schedule-viewing")
def homeos_schedule_viewing(req: HomeOSScheduleViewingRequest,
                            repo: Repository = Depends(get_repository),
                            _user=Depends(require_subscribed)):
    try:
        return schedule_homeos_viewing(
            repo,
            profile_text=req.profile_text,
            block_id=req.block_id,
            availability=req.availability,
            contact_name=req.contact_name,
            contact_note=req.contact_note,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "block not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc))


@app.post("/homeos/investigate-stream")
async def homeos_investigate_stream(
    req: HomeOSStreamRequest,
    repo: Repository = Depends(get_repository),
    _user=Depends(require_subscribed),
):
    async def event_gen():
        async for event in investigate_stream(repo, req.profile_text, req.limit, req.model):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/homeos/cases")
def homeos_list_cases(_user=Depends(require_subscribed)):
    cases = homeos_case_store.list_cases()
    return [
        {
            "case_id": c["case_id"],
            "created_at": c["created_at"],
            "profile_text": c["profile_text"],
            "status": c["status"],
            "shortlist_count": len(c["shortlist"]),
        }
        for c in cases
    ]


@app.get("/homeos/cases/{case_id}")
def homeos_get_case(case_id: str, _user=Depends(require_subscribed)):
    case = homeos_case_store.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    return case


@app.post("/homeos/cases/{case_id}/chat")
async def homeos_chat(case_id: str, req: HomeOSChatRequest,
                      _user=Depends(require_subscribed)):
    if homeos_case_store.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail="case not found")

    async def chat_gen():
        async for chunk in chat_in_case(case_id, req.message, req.model):
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        chat_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/homeos/cases/{case_id}/refine")
async def homeos_refine(
    case_id: str,
    req: HomeOSRefineRequest,
    repo: Repository = Depends(get_repository),
    _user=Depends(require_subscribed),
):
    case = homeos_case_store.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")

    async def refine_gen():
        async for event in refine_stream(repo, case_id, req.message, req.model):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        refine_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/commute/optimize")
def commute_optimize(req: CommuteRequest,
                     repo: Repository = Depends(get_repository)):
    provider = get_commute_provider()
    return {"results": optimize_commute(repo, provider,
                                        req.domain_destinations(), req.limit)}


@app.post("/commute/heatmap")
def commute_heatmap_endpoint(req: CommuteRequest,
                             repo: Repository = Depends(get_repository)):
    provider = get_commute_provider()
    return {"points": commute_heatmap(repo, provider, req.domain_destinations())}


@app.post("/commute/to-places")
def commute_to_places(req: CommuteToPlacesRequest):
    """Estimated travel time from one property to each saved place. Uses a fast
    distance-based estimate (no external routing) so selection stays instant."""
    from math import radians, sin, cos, asin, sqrt

    def hav_km(lat1, lon1, lat2, lon2) -> float:
        dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        return 2 * 6371 * asin(sqrt(a))

    out = []
    for pl in req.places:
        km = hav_km(req.origin_lat, req.origin_lon, pl.lat, pl.lon)
        road = km * 1.3  # straight-line underestimates road distance
        out.append({
            "label": pl.label,
            "distance_km": round(km, 1),
            "transit_minutes": max(5, round(road / 0.4)),  # ~24 km/h + walk/wait overhead
            "drive_minutes": max(3, round(road / 0.7)),    # ~42 km/h
        })
    return {"results": out}


@app.get("/geocode")
def geocode_address(q: str = Query(..., min_length=2)):
    from app.data.fetch_live import ONEMAP_SEARCH_URL
    from app.services.commute import onemap_auth
    import requests

    token = onemap_auth.current_token()
    if not token:
        raise HTTPException(
            status_code=503,
            detail="OneMap not configured (set ONEMAP_EMAIL/ONEMAP_PASSWORD or ONEMAP_TOKEN)")
    params = {"searchVal": q, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1}
    try:
        session = requests.Session()
        session.trust_env = False
        response = session.get(ONEMAP_SEARCH_URL, params=params,
                               headers={"Authorization": token}, timeout=10)
        # Token expired/invalid: re-mint once and retry.
        if response.status_code == 401:
            token = onemap_auth.refresh()
            if token:
                response = session.get(ONEMAP_SEARCH_URL, params=params,
                                       headers={"Authorization": token}, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"OneMap address search unavailable: {exc}") from exc
    results = response.json().get("results", [])[:8]
    return {"results": [{
        "label": row.get("ADDRESS") or row.get("SEARCHVAL") or q,
        "lat": float(row["LATITUDE"]),
        "lon": float(row["LONGITUDE"]),
    } for row in results if row.get("LATITUDE") and row.get("LONGITUDE")]}


@app.post("/transit/direct-convenience")
def direct_transit_convenience(
    req: DirectTransitRequest,
    repo: Repository = Depends(get_repository),
):
    lookup = getattr(repo, "direct_transit_convenience", None)
    if not callable(lookup):
        raise HTTPException(status_code=501, detail="Direct transit filter requires PostGIS")
    invalid = set(req.modes) - {"bus", "mrt"}
    if invalid or not req.modes:
        raise HTTPException(status_code=400, detail="modes must contain bus and/or mrt")
    return lookup(
        [destination.model_dump() for destination in req.destinations],
        max_walk_m=req.max_walk_minutes * 80.0,
        modes=req.modes,
        property_filters=req.model_dump(include={
            "town", "planning_area_id", "flat_type", "min_price", "max_price",
            "min_psf", "max_psf", "max_mrt_distance_m", "min_schools_within_1km",
        }),
        limit=req.limit,
    )


@app.post("/couple-mode/optimize")
def couple_mode_optimize(req: CoupleRequest,
                         repo: Repository = Depends(get_repository)):
    provider = get_commute_provider()
    try:
        rows = couple_optimize(repo, provider, req.person_a.to_domain(),
                               req.person_b.to_domain(), req.weights, req.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"results": rows, "recommended_estates": recommended_estates(rows)}


@app.post("/lifestyle/block/{block_id}")
def lifestyle_block(block_id: int, req: LifestyleRequest,
                    repo: Repository = Depends(get_repository)):
    provider = get_commute_provider() if req.destinations else None
    dests = [d.to_domain() for d in req.destinations] if req.destinations else None
    data = block_lifestyle(repo, block_id, provider=provider,
                           destinations=dests, weights=req.weights)
    if data is None:
        raise HTTPException(status_code=404, detail="block not found")
    return data


@app.get("/appreciation/{block_id}")
def appreciation_block(block_id: int, repo: Repository = Depends(get_repository)):
    data = appreciation_svc(repo, block_id)
    if data is None:
        raise HTTPException(status_code=404, detail="block not found")
    return data


@app.get("/future-mrt/{block_id}")
def future_mrt_block(block_id: int, repo: Repository = Depends(get_repository)):
    data = future_mrt(repo, block_id)
    if data is None:
        raise HTTPException(status_code=404, detail="block not found")
    return data


@app.get("/future-supply/{block_id}")
def future_supply_block(block_id: int, radius_m: float = 2000.0,
                        repo: Repository = Depends(get_repository)):
    data = future_supply(repo, block_id, radius_m)
    if data is None:
        raise HTTPException(status_code=404, detail="block not found")
    return data


@app.post("/dream-home-finder")
def dream_home(req: DreamHomeRequest, repo: Repository = Depends(get_repository)):
    provider = get_commute_provider() if req.destinations else None
    return dream_home_finder(repo, req.to_criteria(), provider=provider)


@app.get("/forecast/block/{block_id}")
def forecast_block(block_id: int, flat_type: str | None = None,
                   horizon_months: int = 12,
                   repo: Repository = Depends(get_repository)):
    data = block_forecast(repo, block_id, flat_type, horizon_months)
    if data is None:
        raise HTTPException(status_code=404,
                            detail="block not found or insufficient data")
    return data


@app.get("/forecast/estate/{planning_area_id}")
def forecast_estate(planning_area_id: int, flat_type: str | None = None,
                    horizon_months: int = 12,
                    repo: Repository = Depends(get_repository)):
    data = estate_forecast(repo, planning_area_id, flat_type, horizon_months)
    if data is None:
        raise HTTPException(status_code=404,
                            detail="estate not found or insufficient data")
    return data


@app.get("/undervalued")
def undervalued(flat_type: str | None = None,
                repo: Repository = Depends(get_repository)):
    return detect_undervalued(repo, flat_type)


@app.post("/recommendations")
def recommendations(req: RecommendationRequest,
                    repo: Repository = Depends(get_repository)):
    provider = get_commute_provider() if req.destinations else None
    return recommend(repo, provider=provider,
                     destinations=req.domain_destinations(),
                     weights=req.weights, limit=req.limit)


@app.get("/score-ranking/fields")
def score_ranking_fields():
    """The scoring factors available to weight (drives the slider UI)."""
    return {"fields": score_ranking_svc.list_fields()}


@app.post("/score-ranking")
def score_ranking(req: ScoreRankingRequest,
                  repo: Repository = Depends(get_repository)):
    dests = req.domain_destinations()
    provider = get_commute_provider() if dests else None
    return score_ranking_svc.rank(repo, weights=req.weights, provider=provider,
                                  destinations=dests, limit=req.limit)


@app.get("/bto/exercises")
def bto_exercises():
    """All BTO sales exercises with summary (units, applicants, overall rate)."""
    engine = get_engine_or_none()
    if engine is None:
        raise HTTPException(status_code=503, detail="BTO data requires PostGIS")
    return {"results": bto_svc.list_exercises(engine)}


@app.get("/bto/trends")
def bto_trends():
    """Subscription trend across exercises (overall + per flat type)."""
    engine = get_engine_or_none()
    if engine is None:
        raise HTTPException(status_code=503, detail="BTO data requires PostGIS")
    return bto_svc.trends(engine)


@app.get("/amenities")
def amenities_list():
    """Available amenity layers (drives the map's toggle chips)."""
    return {"amenities": amenities_svc.list_amenities()}


@app.get("/amenities/{key}")
def amenities_points(key: str, repo: Repository = Depends(get_repository)):
    """POIs for one amenity layer (schools from our data; rest via OneMap)."""
    data = amenities_svc.amenities(repo, key)
    if data is None:
        raise HTTPException(status_code=404, detail="unknown amenity")
    return {"key": key, "count": len(data), "results": data}


@app.get("/compare/options")
def compare_options(repo: Repository = Depends(get_repository)):
    """Towns + flat types available for the BTO-vs-resale comparison."""
    engine = get_engine_or_none()
    if engine is None:
        raise HTTPException(status_code=503, detail="Comparison requires PostGIS")
    return bto_compare_svc.options(repo, engine)


@app.get("/compare/bto-resale")
def compare_bto_resale(town: str, flat_type: str,
                       repo: Repository = Depends(get_repository)):
    """BTO vs resale for one town + flat type: price gap, ballot odds, trend."""
    engine = get_engine_or_none()
    if engine is None:
        raise HTTPException(status_code=503, detail="Comparison requires PostGIS")
    return bto_compare_svc.compare(repo, engine, town, flat_type)


@app.get("/compare/recommend/questions")
def recommend_questions():
    """The questionnaire schema (drives the recommendation form)."""
    return {"questions": recommend_path_svc.questions()}


@app.post("/compare/recommend")
def recommend_path(req: RecommendRequest,
                   repo: Repository = Depends(get_repository)):
    """Recommend BTO vs Resale from questionnaire answers (+ optional town)."""
    engine = get_engine_or_none()
    return recommend_path_svc.recommend(req.answers, repo=repo, engine=engine,
                                        town=req.town, flat_type=req.flat_type)


@app.get("/bto/price-trends")
def bto_price_trends(town: str | None = None):
    """BTO selling-price midpoint per financial year, by room type."""
    engine = get_engine_or_none()
    if engine is None:
        raise HTTPException(status_code=503, detail="BTO data requires PostGIS")
    return bto_svc.price_trends(engine, town)


@app.get("/bto/price-ranges")
def bto_price_ranges(town: str | None = None, room_type: str | None = None):
    """Raw BTO price-range rows (financial year / town / room type)."""
    engine = get_engine_or_none()
    if engine is None:
        raise HTTPException(status_code=503, detail="BTO data requires PostGIS")
    return {"results": bto_svc.price_ranges(engine, town, room_type)}


@app.get("/bto/exercises/{exercise_id}")
def bto_exercise_detail(exercise_id: str):
    """One exercise: flat supply, applications and rates by estate + flat type."""
    engine = get_engine_or_none()
    if engine is None:
        raise HTTPException(status_code=503, detail="BTO data requires PostGIS")
    data = bto_svc.exercise_detail(engine, exercise_id)
    if data is None:
        raise HTTPException(status_code=404, detail="exercise not found")
    return data


@app.get("/image/property")
def property_image(block_id: int | None = None, lat: float | None = None,
                   lon: float | None = None,
                   repo: Repository = Depends(get_repository)):
    """Best image for a property: real listing photo → Street View → OneMap map.
    Keeps the OneMap token + Google key server-side. 404 when nothing is found
    (the frontend hides the <img> on error)."""
    cache = {"Cache-Control": "public, max-age=86400"}
    if block_id is not None:
        url = images_svc.listing_photo_url(repo, block_id)
        if url:
            return RedirectResponse(url)  # real listing photo (public CDN)
    if lat is not None and lon is not None:
        sv = images_svc.streetview_bytes(lat, lon)
        if sv is not None:
            return Response(content=sv, media_type="image/jpeg", headers=cache)
        murl = images_svc.mapillary_url(lat, lon)
        if murl:
            return RedirectResponse(murl)  # browser loads straight from Mapillary CDN
        om = images_svc.onemap_bytes(lat, lon)
        if om is not None:
            return Response(content=om, media_type="image/png", headers=cache)
    raise HTTPException(status_code=404, detail="no image")


@app.get("/private/transactions")
def private_transactions(
    project: str | None = None,
    address: str | None = None,
    property_type: str | None = None,
    sale_type: str | None = None,
    district: str | None = None,
    planning_region: str | None = None,
    tenure: str | None = None,
    floor_range: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_price: int | None = Query(None, ge=0),
    max_price: int | None = Query(None, ge=0),
    min_psf: int | None = Query(None, ge=0),
    max_psf: int | None = Query(None, ge=0),
    min_area_sqft: float | None = Query(None, ge=0),
    max_area_sqft: float | None = Query(None, ge=0),
    limit: int = Query(200, ge=1, le=5000),
):
    """Private (non-HDB) residential transactions from URA, filtered + summarised.
    Falls back to bundled fixtures when URA credentials are absent (mock=true)."""
    return private_svc.transactions(
        limit=limit, project=project, address=address, property_type=property_type,
        sale_type=sale_type, district=district, planning_region=planning_region,
        tenure=tenure, floor_range=floor_range, date_from=date_from, date_to=date_to,
        min_price=min_price, max_price=max_price, min_psf=min_psf, max_psf=max_psf,
        min_area_sqft=min_area_sqft, max_area_sqft=max_area_sqft)


@app.get("/private/projects")
def private_projects(query: str | None = None, limit: int = Query(50, ge=1, le=200)):
    """Distinct private projects (txn count + median PSF) for search."""
    return private_svc.projects(query=query, limit=limit)


@app.get("/bto/resale-supply")
def bto_resale_supply(
    town: str | None = None,
    classification: str | None = None,
    flat_type: str | None = None,
    earliest_year: int | None = None,
    confidence: str | None = None,
    sort: str = "soonest",
    limit: int = Query(500, ge=1, le=2000),
):
    """Estimated BTO Resale Availability — projects/estates ranked by the soonest
    estimated date they may enter the resale market (completion + MOP). Estimates,
    not confirmed resale dates. See docs/BTO_MOP_ESTIMATION_RULES.md."""
    engine = get_engine_or_none()
    if engine is None:
        raise HTTPException(status_code=503, detail="BTO data requires PostGIS")
    return bto_mop_svc.resale_supply(engine, town=town, classification=classification,
                                     flat_type=flat_type, earliest_year=earliest_year,
                                     confidence=confidence, sort=sort, limit=limit)


@app.get("/rankings/regions")
def rankings_regions(limit: int = Query(50, ge=1, le=100)):
    """Planning areas ranked by 10-year appreciation (precomputed)."""
    engine = get_engine_or_none()
    if engine is None:
        raise HTTPException(status_code=503, detail="Rankings require PostGIS")
    rows = appreciation_rankings_svc.read_region_rankings(engine, limit)
    return {"count": len(rows), "results": rows,
            "computed_at": rows[0]["computed_at"] if rows else None}


@app.get("/rankings/block-scores")
def rankings_block_scores():
    """All block_id -> appreciation_score (precomputed), for client-side blending."""
    engine = get_engine_or_none()
    if engine is None:
        return {"scores": {}}
    return {"scores": appreciation_rankings_svc.block_scores(engine)}


@app.get("/rankings/blocks")
def rankings_blocks(planning_area_id: int | None = None,
                    limit: int = Query(50, ge=1, le=200)):
    """Blocks ranked by 10-year appreciation (precomputed), optionally by area."""
    engine = get_engine_or_none()
    if engine is None:
        raise HTTPException(status_code=503, detail="Rankings require PostGIS")
    rows = appreciation_rankings_svc.read_block_rankings(engine, planning_area_id, limit)
    return {"count": len(rows), "results": rows,
            "computed_at": rows[0]["computed_at"] if rows else None}


def _points_geojson(features):
    return {"type": "FeatureCollection", "features": features}


@app.get("/reference/{layer}")
def reference_layer(layer: str, repo: Repository = Depends(get_repository)):
    """Bounded GeoJSON for point reference layers (works in mock + PostGIS)."""
    def feat(lon, lat, props):
        return {"type": "Feature", "properties": props,
                "geometry": {"type": "Point", "coordinates": [lon, lat]}}
    if layer == "mrt":
        items = [feat(m.point.lon, m.point.lat,
                      {"station_id": m.station_id, "name": m.station_name,
                       "line_name": m.line_name, "status": m.status})
                 for m in repo.mrt_stations("operational")]
    elif layer == "future_mrt":
        items = [feat(m.point.lon, m.point.lat,
                      {"station_id": m.station_id, "name": m.station_name,
                       "opening_year": m.opening_year})
                 for m in repo.mrt_stations("future")]
    elif layer == "schools":
        items = [feat(s.point.lon, s.point.lat,
                      {"school_id": s.school_id, "name": s.school_name})
                 for s in repo.schools()]
    elif layer == "bus_stops":
        items = [feat(b.point.lon, b.point.lat,
                      {"code": b.bus_stop_code, "description": b.description})
                 for b in repo.bus_stops()]
    elif layer == "bto":
        items = [feat(p.point.lon, p.point.lat,
                      {"project_id": p.project_id, "name": p.project_name})
                 for p in repo.bto_projects()]
    else:
        raise HTTPException(status_code=404, detail="unknown layer")
    return _points_geojson(items)


@app.get("/bus-stops/{bus_stop_code}/reach")
def bus_stop_reach(bus_stop_code: str, repo: Repository = Depends(get_repository)):
    lookup = getattr(repo, "bus_stop_reach", None)
    if not callable(lookup):
        raise HTTPException(status_code=501, detail="Bus reach requires PostGIS")
    result = lookup(bus_stop_code)
    if result is None:
        raise HTTPException(status_code=404, detail="bus stop not found")
    if not result["services"]:
        raise HTTPException(
            status_code=503,
            detail="Bus routes are not loaded. Set LTA_DATAMALL_API_KEY and run python -m app.data.sync_bus_network.",
        )
    return result


@app.get("/news", response_model=list[NewsItem])
def get_news():
    from urllib.parse import urlparse
    if not settings.exa_api_key:
        raise HTTPException(status_code=503, detail="EXA_API_KEY is not configured")
    try:
        resp = httpx.post(
            "https://api.exa.ai/search",
            json={
                "query": "Latest Singapore resale and BTO HDB property market news",
                "num_results": 10,
                "type": "neural",
                "category": "news",
            },
            headers={"Authorization": f"Bearer {settings.exa_api_key}"},
            timeout=15.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Exa API error: {exc}") from exc
    raw = resp.json().get("results", [])
    return [
        NewsItem(
            title=item.get("title") or "",
            url=item.get("url") or "",
            published_date=item.get("publishedDate"),
            domain=urlparse(item.get("url", "")).netloc or None,
        )
        for item in raw
    ]


@app.get("/tiles/{layer}/{z}/{x}/{y}.pbf")
def tile(layer: str, z: int, x: int, y: int):
    if layer not in LAYERS:
        raise HTTPException(status_code=404, detail="unknown layer")
    engine = get_engine_or_none()
    if engine is None:
        raise HTTPException(
            status_code=501,
            detail="vector tiles require PostGIS; set DATABASE_URL")
    data = build_tile(engine, layer, z, x, y)
    return Response(content=data, media_type="application/vnd.mapbox-vector-tile")
