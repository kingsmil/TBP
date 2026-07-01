"""Query / filter / aggregate over normalised URA private transactions.

Prefers the seeded PostGIS table (app.data.ura) when it's populated — so we
don't re-pull from URA per request — and falls back to the in-memory fetch
(bundled fixtures in mock mode, or a direct live fetch) when there's no DB.
"""
from __future__ import annotations

import statistics

from app.services.private_property import ura_client, store

PROPERTY_TYPES = ["CONDO", "APARTMENT", "EC", "LANDED", "STRATA_LANDED"]
SALE_TYPES = ["NEW_SALE", "RESALE", "SUB_SALE"]
PLANNING_REGIONS = ["CCR", "RCR", "OCR"]
TENURE_TYPES = ["freehold", "leasehold"]
FLOOR_RANGES = [
    "01-05", "06-10", "11-15", "16-20", "21-25", "26-30", "31-35",
    "36-40", "41-45", "46-50", "51-55", "56-60", "61-65", "66-70",
]


def _db_engine():
    """Return an engine only when the seeded table actually has rows."""
    try:
        from app.api.deps import get_engine_or_none
        engine = get_engine_or_none()
        if engine is not None and store.count(engine) > 0:
            return engine
    except Exception:
        pass
    return None


def _filtered(
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
    min_price: int | None = None,
    max_price: int | None = None,
    min_psf: int | None = None,
    max_psf: int | None = None,
    min_area_sqft: float | None = None,
    max_area_sqft: float | None = None,
) -> list[dict]:
    rows = ura_client.all_transactions()
    if project:
        p = project.lower()
        rows = [r for r in rows if r["project_name"] and p in r["project_name"].lower()]
    if address:
        a = address.lower()
        rows = [r for r in rows if r["address"] and a in r["address"].lower()]
    if property_type:
        rows = [r for r in rows if r["property_type"] == property_type.upper()]
    if sale_type:
        rows = [r for r in rows if r["sale_type"] == sale_type.upper()]
    if district:
        rows = [r for r in rows if (r["district"] or "").zfill(2) == district.zfill(2)]
    if planning_region:
        rows = [r for r in rows if (r["planning_region"] or "").upper() == planning_region.upper()]
    if tenure:
        t = tenure.lower()
        if t in {"freehold", "fh"}:
            rows = [r for r in rows if "freehold" in (r["tenure"] or "").lower()]
        elif t in {"leasehold", "lh"}:
            rows = [r for r in rows if r["tenure"] and "freehold" not in r["tenure"].lower()]
    if floor_range:
        rows = [r for r in rows if r["floor_range"] == floor_range]
    if date_from:
        rows = [r for r in rows if r["sale_date"] >= date_from]
    if date_to:
        rows = [r for r in rows if r["sale_date"] <= date_to]
    if min_price is not None:
        rows = [r for r in rows if r["price"] is not None and r["price"] >= min_price]
    if max_price is not None:
        rows = [r for r in rows if r["price"] is not None and r["price"] <= max_price]
    if min_psf is not None:
        rows = [r for r in rows if r["psf"] is not None and r["psf"] >= min_psf]
    if max_psf is not None:
        rows = [r for r in rows if r["psf"] is not None and r["psf"] <= max_psf]
    if min_area_sqft is not None:
        rows = [r for r in rows if r["area_sqft"] is not None and r["area_sqft"] >= min_area_sqft]
    if max_area_sqft is not None:
        rows = [r for r in rows if r["area_sqft"] is not None and r["area_sqft"] <= max_area_sqft]
    return rows


def _stats(rows: list[dict]) -> dict:
    psfs = sorted(r["psf"] for r in rows if r["psf"] is not None)
    prices = [r["price"] for r in rows if r["price"] is not None]
    latest = max(rows, key=lambda r: r["sale_date"]) if rows else None
    return {
        "count": len(rows),
        "median_psf": round(statistics.median(psfs)) if psfs else None,
        "avg_psf": round(statistics.fmean(psfs)) if psfs else None,
        "min_psf": psfs[0] if psfs else None,
        "max_psf": psfs[-1] if psfs else None,
        "median_price": round(statistics.median(prices)) if prices else None,
        "latest": latest,
    }


def transactions(limit: int = 200, **filters) -> dict:
    """Filtered transactions (newest first) + summary metrics."""
    engine = _db_engine()
    if engine is not None:
        return store.transactions(engine, limit=limit, **filters)
    rows = _filtered(**filters)
    rows.sort(key=lambda r: r["sale_date"], reverse=True)
    stats = _stats(rows)
    return {
        "mock": ura_client.is_mock(),
        "summary": {k: v for k, v in stats.items() if k != "latest"},
        "latest": stats["latest"],
        "trend": _monthly_trend(rows),
        "results": rows[:limit],
        "filters": {
            "property_types": PROPERTY_TYPES,
            "sale_types": SALE_TYPES,
            "planning_regions": PLANNING_REGIONS,
            "tenures": TENURE_TYPES,
            "floor_ranges": FLOOR_RANGES,
        },
    }


def _monthly_trend(rows: list[dict]) -> list[dict]:
    """Median PSF + count per sale month, oldest-first (for charts)."""
    by_month: dict[str, list[float]] = {}
    for r in rows:
        if r["psf"] is None:
            continue
        by_month.setdefault(r["sale_date"][:7], []).append(r["psf"])
    return [{"month": m, "median_psf": round(statistics.median(v)), "count": len(v)}
            for m, v in sorted(by_month.items())]


def projects(query: str | None = None, limit: int = 50) -> dict:
    """Distinct projects with txn counts + median PSF, for search/autocomplete."""
    engine = _db_engine()
    if engine is not None:
        return store.projects(engine, query=query, limit=limit)
    rows = ura_client.all_transactions()
    agg: dict[str, dict] = {}
    for r in rows:
        name = r["project_name"]
        if not name:
            continue
        if query and query.lower() not in name.lower():
            continue
        a = agg.setdefault(name, {"project_name": name, "property_type": r["property_type"],
                                  "district": r["district"], "planning_region": r["planning_region"],
                                  "_psf": [], "count": 0})
        a["count"] += 1
        if r["psf"] is not None:
            a["_psf"].append(r["psf"])
    out = []
    import statistics as _st
    for a in agg.values():
        psf = a.pop("_psf")
        a["median_psf"] = round(_st.median(psf)) if psf else None
        out.append(a)
    out.sort(key=lambda a: a["count"], reverse=True)
    return {"mock": ura_client.is_mock(), "count": len(out), "results": out[:limit]}
