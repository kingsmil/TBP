"""Read API over the precomputed Estimated BTO Resale Availability table.

The estimates are built in the background (app.data.bto_mop), so these are fast
reads of a small reference table. Supports the UI's filters + sort options.
"""
from __future__ import annotations

_SORTS = {
    # key -> ORDER BY clause (NULLs always last so undated rows sink)
    "soonest": "estimated_resale_eligible_date ASC NULLS LAST, project_name ASC",
    "town": "town ASC NULLS LAST, estimated_resale_eligible_date ASC",
    "completion": "estimated_completion_date ASC NULLS LAST, project_name ASC",
    "confidence": "CASE confidence WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END, "
                  "estimated_resale_eligible_date ASC NULLS LAST",
}


def resale_supply(
    engine,
    town: str | None = None,
    classification: str | None = None,
    flat_type: str | None = None,
    earliest_year: int | None = None,
    confidence: str | None = None,
    sort: str = "soonest",
    limit: int = 500,
) -> dict:
    """Filtered + sorted estimates, plus facet lists for the filter dropdowns."""
    from sqlalchemy import text

    where: list[str] = []
    params: dict = {}
    if town:
        where.append("town = :town"); params["town"] = town
    if classification:
        where.append("flat_classification = :cls"); params["cls"] = classification.upper()
    if flat_type:
        where.append("flat_types ILIKE :ft"); params["ft"] = f"%{flat_type}%"
    if earliest_year:
        where.append("EXTRACT(YEAR FROM estimated_resale_eligible_date) >= :yr")
        params["yr"] = earliest_year
    if confidence:
        where.append("confidence = :conf"); params["conf"] = confidence.upper()

    clause = (" WHERE " + " AND ".join(where)) if where else ""
    order = _SORTS.get(sort, _SORTS["soonest"])
    params["lim"] = max(1, min(limit, 2000))

    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT * FROM bto_project_mop_estimates{clause} "
            f"ORDER BY {order} LIMIT :lim"), params).mappings().all()
        towns = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT town FROM bto_project_mop_estimates "
            "WHERE town IS NOT NULL ORDER BY town")).all()]
        classes = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT flat_classification FROM bto_project_mop_estimates "
            "ORDER BY flat_classification")).all()]
        confidences = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT confidence FROM bto_project_mop_estimates")).all()]

    return {
        "count": len(rows),
        "results": [_row(r) for r in rows],
        "facets": {
            "towns": towns,
            "classifications": classes,
            "confidences": sorted(confidences, key=lambda c: ["HIGH", "MEDIUM", "LOW"].index(c)
                                  if c in ("HIGH", "MEDIUM", "LOW") else 99),
            "sorts": list(_SORTS.keys()),
        },
    }


def _row(r) -> dict:
    """Serialise one DB row (dates -> ISO strings) for JSON."""
    def iso(v):
        return v.isoformat() if v is not None else None
    return {
        "id": r["id"],
        "project_name": r["project_name"],
        "town": r["town"],
        "estate": r["estate"],
        "launch_exercise": r["launch_exercise"],
        "flat_classification": r["flat_classification"],
        "flat_types": r["flat_types"],
        "estimated_completion_date": iso(r["estimated_completion_date"]),
        "estimated_key_collection_date": iso(r["estimated_key_collection_date"]),
        "mop_years": r["mop_years"],
        "estimated_resale_eligible_date": iso(r["estimated_resale_eligible_date"]),
        "confidence": r["confidence"],
        "confidence_reason": r["confidence_reason"],
        "source_url": r["source_url"],
        "source_type": r["source_type"],
        "last_verified_at": iso(r["last_verified_at"]),
        "lat": r["lat"],
        "lon": r["lon"],
    }
