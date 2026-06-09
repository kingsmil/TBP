"""FastAPI application — Phase 1 endpoints.

Runs against PostGIS when DATABASE_URL is set, otherwise against a seeded
in-memory repository (see app.api.deps). The tile endpoint requires PostGIS;
the reference endpoint works in both modes.
"""
from __future__ import annotations

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_commute_provider, get_engine_or_none, get_repository
import json

from fastapi.responses import StreamingResponse

from app.api.schemas import (
    OutreachRequest,
    CommuteRequest,
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
    DirectTransitRequest,
)
from app.homeos import case_store as homeos_case_store
from app.homeos.pipeline import (
    build_homeos_case_file,
    chat_in_case,
    investigate_homeos_profile,
    investigate_stream,
    refine_stream,
    schedule_homeos_viewing,
)
from app.api.tiles import LAYERS, build_tile
from app.core.models import SearchQuery
from app.repositories.base import Repository
from app.services import accessibility as access_svc
from app.services import analytics as analytics_svc
from app.services import outreach as outreach_svc
from app.services.appreciation import appreciation as appreciation_svc
from app.services.comparison import compare_estates
from app.services.commute.couple import couple_optimize, recommended_estates
from app.services.commute.optimizer import commute_heatmap, optimize_commute
from app.services.dream_home import dream_home_finder
from app.services.forecasting import block_forecast, estate_forecast
from app.services.future_dev import future_mrt, future_supply
from app.services.lifestyle import block_lifestyle
from app.services.recommendation import recommend
from app.services.search import search_blocks
from app.services.undervalued import detect_undervalued

from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(application):
    from app.homeos.wiring import setup as homeos_setup
    homeos_setup()
    yield


app = FastAPI(title="HDB Match API", version="0.1.0",
              description="Geospatial analytics platform for Singapore HDB.",
              lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
def health():
    repo = get_repository()
    return {"status": "ok", "blocks": len(repo.blocks()),
            "mode": "postgis" if get_engine_or_none() else "mock"}


@app.get("/properties/search")
def properties_search(
    minx: float | None = None, miny: float | None = None,
    maxx: float | None = None, maxy: float | None = None,
    town: str | None = None,
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
    limit: int = Query(500, ge=1, le=5000),
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


@app.get("/blocks/{block_id}/listings")
def block_listings(block_id: int, repo: Repository = Depends(get_repository)):
    """Active HDB Flat Portal listings for a block, cheapest first."""
    if repo.block(block_id) is None:
        raise HTTPException(status_code=404, detail="block not found")
    listings = sorted(repo.active_listings_for_block(block_id), key=lambda a: a.price)
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
            repo, listing_id, case_id=body.case_id, contact_name=body.contact_name,
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
    return {"estates": compare_estates(repo, ids, flat_type)}


@app.post("/homeos/investigate")
def homeos_investigate(req: HomeOSInvestigationRequest,
                       repo: Repository = Depends(get_repository)):
    return investigate_homeos_profile(repo, req.profile_text, req.limit)


@app.post("/homeos/case-file/{block_id}")
def homeos_case_file(block_id: int, req: HomeOSCaseFileRequest,
                     repo: Repository = Depends(get_repository)):
    try:
        return build_homeos_case_file(repo, req.profile_text, block_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/homeos/schedule-viewing")
def homeos_schedule_viewing(req: HomeOSScheduleViewingRequest,
                            repo: Repository = Depends(get_repository)):
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
):
    async def event_gen():
        async for event in investigate_stream(repo, req.profile_text, req.limit):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/homeos/cases")
def homeos_list_cases():
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
def homeos_get_case(case_id: str):
    case = homeos_case_store.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    return case


@app.post("/homeos/cases/{case_id}/chat")
async def homeos_chat(case_id: str, req: HomeOSChatRequest):
    if homeos_case_store.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail="case not found")

    async def chat_gen():
        async for chunk in chat_in_case(case_id, req.message):
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
):
    case = homeos_case_store.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")

    async def refine_gen():
        async for event in refine_stream(repo, case_id, req.message):
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


@app.get("/geocode")
def geocode_address(q: str = Query(..., min_length=2)):
    from app.config import settings
    from app.data.fetch_live import ONEMAP_SEARCH_URL
    import requests

    if not settings.onemap_token:
        raise HTTPException(status_code=503, detail="ONEMAP_TOKEN is not configured")
    try:
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            ONEMAP_SEARCH_URL,
            params={"searchVal": q, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1},
            headers={"Authorization": settings.onemap_token},
            timeout=10,
        )
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
                       "status": m.status}) for m in repo.mrt_stations("operational")]
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
