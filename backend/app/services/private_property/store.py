"""PostGIS persistence + reads for private (URA) transactions.

Seeded once and refreshed monthly (app.data.ura), so filtering/aggregation runs
in SQL over the stored table rather than re-fetching ~137k rows from URA. The
service layer prefers this when a populated table exists, and falls back to the
in-memory fetch (mock/no-DB) otherwise.
"""
from __future__ import annotations

PROPERTY_TYPES = ["CONDO", "APARTMENT", "EC", "LANDED", "STRATA_LANDED"]
SALE_TYPES = ["NEW_SALE", "RESALE", "SUB_SALE"]
PLANNING_REGIONS = ["CCR", "RCR", "OCR"]
TENURE_TYPES = ["freehold", "leasehold"]
FLOOR_RANGES = [
    "01-05", "06-10", "11-15", "16-20", "21-25", "26-30", "31-35",
    "36-40", "41-45", "46-50", "51-55", "56-60", "61-65", "66-70",
]

_COLS = ("id", "project_name", "property_type", "sale_type", "district",
         "planning_region", "address", "sale_date", "price", "area_sqm",
         "area_sqft", "psf", "tenure", "floor_range", "source")


def count(engine) -> int:
    from sqlalchemy import text
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM private_transactions")).scalar() or 0


def age_days(engine):
    from datetime import datetime, timezone
    from sqlalchemy import text
    with engine.connect() as conn:
        ts = conn.execute(text("SELECT MAX(fetched_at) FROM private_transactions")).scalar()
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0


def persist(engine, rows: list[dict]) -> int:
    """Replace the table contents with the freshly-fetched rows (idempotent)."""
    from sqlalchemy import text
    if not rows:
        return 0
    payload = [{**{c: r.get(c) for c in _COLS},
                "svy_x": r.get("svy_x"), "svy_y": r.get("svy_y")} for r in rows]
    cols = ", ".join(_COLS)
    placeholders = ", ".join(f":{c}" for c in _COLS)
    # Convert SVY21 (3414) x/y -> WGS84 (4326) lat/lon in PostGIS at insert time.
    # Params are cast explicitly so Postgres can infer their type.
    x, y = "CAST(:svy_x AS double precision)", "CAST(:svy_y AS double precision)"
    geom = f"ST_Transform(ST_SetSRID(ST_MakePoint({x}, {y}), 3414), 4326)"
    have_xy = f"({x} IS NOT NULL AND {y} IS NOT NULL)"
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE private_transactions"))
        # Chunk to keep parameter counts sane for 100k+ rows.
        CHUNK = 5000
        for i in range(0, len(payload), CHUNK):
            conn.execute(text(
                f"INSERT INTO private_transactions ({cols}, lat, lon, fetched_at) VALUES "
                f"({placeholders}, "
                f"CASE WHEN {have_xy} THEN ST_Y({geom}) END, "
                f"CASE WHEN {have_xy} THEN ST_X({geom}) END, "
                f"NOW()) ON CONFLICT (id) DO NOTHING"),
                payload[i:i + CHUNK])
    return len(payload)


def _where(
    project,
    address,
    property_type,
    sale_type,
    district,
    planning_region,
    tenure,
    floor_range,
    date_from,
    date_to,
    min_price,
    max_price,
    min_psf,
    max_psf,
    min_area_sqft,
    max_area_sqft,
):
    clauses, params = [], {}
    if project:
        clauses.append("project_name ILIKE :proj"); params["proj"] = f"%{project}%"
    if address:
        clauses.append("address ILIKE :addr"); params["addr"] = f"%{address}%"
    if property_type:
        clauses.append("property_type = :pt"); params["pt"] = property_type.upper()
    if sale_type:
        clauses.append("sale_type = :st"); params["st"] = sale_type.upper()
    if district:
        clauses.append("LPAD(district, 2, '0') = :dist"); params["dist"] = district.zfill(2)
    if planning_region:
        clauses.append("planning_region = :region"); params["region"] = planning_region.upper()
    if tenure:
        t = tenure.lower()
        if t in {"freehold", "fh"}:
            clauses.append("LOWER(COALESCE(tenure, '')) LIKE '%freehold%'")
        elif t in {"leasehold", "lh"}:
            clauses.append("tenure IS NOT NULL AND LOWER(tenure) NOT LIKE '%freehold%'")
    if floor_range:
        clauses.append("floor_range = :floor_range"); params["floor_range"] = floor_range
    if date_from:
        clauses.append("sale_date >= :df"); params["df"] = date_from
    if date_to:
        clauses.append("sale_date <= :dt"); params["dt"] = date_to
    if min_price is not None:
        clauses.append("price >= :min_price"); params["min_price"] = min_price
    if max_price is not None:
        clauses.append("price <= :max_price"); params["max_price"] = max_price
    if min_psf is not None:
        clauses.append("psf >= :min_psf"); params["min_psf"] = min_psf
    if max_psf is not None:
        clauses.append("psf <= :max_psf"); params["max_psf"] = max_psf
    if min_area_sqft is not None:
        clauses.append("area_sqft >= :min_area_sqft"); params["min_area_sqft"] = min_area_sqft
    if max_area_sqft is not None:
        clauses.append("area_sqft <= :max_area_sqft"); params["max_area_sqft"] = max_area_sqft
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def transactions(engine, limit=200, project=None, address=None, property_type=None, sale_type=None,
                 district=None, planning_region=None, tenure=None, floor_range=None,
                 date_from=None, date_to=None, min_price=None, max_price=None,
                 min_psf=None, max_psf=None, min_area_sqft=None, max_area_sqft=None) -> dict:
    from sqlalchemy import text
    where, params = _where(
        project, address, property_type, sale_type, district, planning_region,
        tenure, floor_range, date_from, date_to, min_price, max_price,
        min_psf, max_psf, min_area_sqft, max_area_sqft,
    )
    with engine.connect() as conn:
        summary = conn.execute(text(f"""
            SELECT COUNT(*) AS count,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY psf) AS median_psf,
                   AVG(psf) AS avg_psf, MIN(psf) AS min_psf, MAX(psf) AS max_psf,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) AS median_price
            FROM private_transactions{where}"""), params).mappings().first()
        trend = conn.execute(text(f"""
            SELECT TO_CHAR(sale_date, 'YYYY-MM') AS month,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY psf) AS median_psf,
                   COUNT(*) AS count
            FROM private_transactions{where}
            {'AND' if where else 'WHERE'} psf IS NOT NULL
            GROUP BY month ORDER BY month"""), params).mappings().all()
        rows = conn.execute(text(
            f"SELECT * FROM private_transactions{where} "
            f"ORDER BY sale_date DESC LIMIT :lim"), {**params, "lim": limit}).mappings().all()
        latest = rows[0] if rows else None

    def num(v, r=0):
        return round(float(v), r) if v is not None else None
    return {
        "mock": False,
        "summary": {
            "count": summary["count"],
            "median_psf": num(summary["median_psf"]),
            "avg_psf": num(summary["avg_psf"]),
            "min_psf": num(summary["min_psf"]),
            "max_psf": num(summary["max_psf"]),
            "median_price": num(summary["median_price"]),
        },
        "latest": _row(latest) if latest else None,
        "trend": [{"month": t["month"], "median_psf": round(float(t["median_psf"])),
                   "count": t["count"]} for t in trend],
        "results": [_row(r) for r in rows],
        "filters": {
            "property_types": PROPERTY_TYPES,
            "sale_types": SALE_TYPES,
            "planning_regions": PLANNING_REGIONS,
            "tenures": TENURE_TYPES,
            "floor_ranges": FLOOR_RANGES,
        },
    }


def projects(engine, query=None, limit=50) -> dict:
    from sqlalchemy import text
    where, params = ("", {})
    if query:
        where, params = " WHERE project_name ILIKE :q", {"q": f"%{query}%"}
    params["lim"] = limit
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT project_name,
                   MODE() WITHIN GROUP (ORDER BY property_type) AS property_type,
                   MODE() WITHIN GROUP (ORDER BY district) AS district,
                   MODE() WITHIN GROUP (ORDER BY planning_region) AS planning_region,
                   COUNT(*) AS count,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY psf) AS median_psf
            FROM private_transactions
            {where} {'AND' if where else 'WHERE'} project_name IS NOT NULL
            GROUP BY project_name ORDER BY count DESC LIMIT :lim"""), params).mappings().all()
    return {"mock": False, "count": len(rows), "results": [{
        "project_name": r["project_name"], "property_type": r["property_type"],
        "district": r["district"], "planning_region": r["planning_region"],
        "count": r["count"],
        "median_psf": round(float(r["median_psf"])) if r["median_psf"] is not None else None,
    } for r in rows]}


def _row(r) -> dict:
    d = dict(r)
    sd = d.get("sale_date")
    d["sale_date"] = sd.isoformat() if hasattr(sd, "isoformat") else sd
    d.pop("fetched_at", None)
    d["price"] = int(d["price"]) if d["price"] is not None else None
    return d
