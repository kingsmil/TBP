"""Read API over the stored BTO exercise + application-rate data.

The data is ingested in the background (app.data.bto, monthly), so these are
simple, fast reads of small reference tables.
"""
from __future__ import annotations


def list_exercises(engine) -> list[dict]:
    from sqlalchemy import text
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT * FROM bto_exercises ORDER BY exercise_id DESC")).mappings().all()
    return [dict(r) for r in rows]


def exercise_detail(engine, exercise_id: str) -> dict | None:
    from sqlalchemy import text
    with engine.connect() as conn:
        ex = conn.execute(text("SELECT * FROM bto_exercises WHERE exercise_id = :e"),
                          {"e": exercise_id}).mappings().first()
        if ex is None:
            return None
        rates = conn.execute(text(
            "SELECT * FROM bto_application_rates WHERE exercise_id = :e "
            "ORDER BY estate_name, flat_type"), {"e": exercise_id}).mappings().all()
    # Group rates by estate for easy display.
    by_estate: dict[str, list] = {}
    for r in rates:
        by_estate.setdefault(r["estate_name"], []).append(dict(r))
    return {
        "exercise": dict(ex),
        "rates": [dict(r) for r in rates],
        "estates": [{"estate_name": name, "flat_types": fts}
                    for name, fts in by_estate.items()],
    }


def latest_exercise(engine) -> dict | None:
    exercises = list_exercises(engine)
    return exercise_detail(engine, exercises[0]["exercise_id"]) if exercises else None


def trends(engine) -> dict:
    """Time series for charts: overall + per-flat-type subscription per exercise."""
    from sqlalchemy import text
    exercises = list_exercises(engine)
    # oldest-first for charting
    overall = [{
        "exercise_id": e["exercise_id"], "label": e["label"],
        "overall_app_rate": float(e["overall_app_rate"]) if e["overall_app_rate"] is not None else None,
        "total_units": e["total_units"], "total_applicants": e["total_applicants"],
    } for e in reversed(exercises)]

    with engine.connect() as conn:
        ft_rows = conn.execute(text("""
            SELECT exercise_id, flat_type,
                   SUM(flat_supply) AS units,
                   SUM(total_applicant_no) AS applicants
            FROM bto_application_rates
            GROUP BY exercise_id, flat_type
        """)).mappings().all()

    by_flat: dict[str, dict] = {}
    for r in ft_rows:
        units = r["units"] or 0
        by_flat.setdefault(r["flat_type"], {})[r["exercise_id"]] = (
            round((r["applicants"] or 0) / units, 2) if units else None)
    flat_types = sorted(by_flat.keys())
    by_flat_type = [{
        "flat_type": ft,
        "series": [{"exercise_id": e["exercise_id"], "label": e["label"],
                    "rate": by_flat[ft].get(e["exercise_id"])}
                   for e in reversed(exercises)],
    } for ft in flat_types]

    return {"overall": overall, "by_flat_type": by_flat_type,
            "exercise_count": len(exercises)}


def price_ranges(engine, town: str | None = None, room_type: str | None = None) -> list[dict]:
    from sqlalchemy import text
    sql = "SELECT * FROM bto_price_ranges"
    where, params = [], {}
    if town:
        where.append("town = :town"); params["town"] = town
    if room_type:
        where.append("room_type = :rt"); params["rt"] = room_type
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY financial_year, town, room_type"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def price_trends(engine, town: str | None = None) -> dict:
    """Midpoint selling price per financial year, by room type (avg across towns
    unless a town is given). Plus the available towns / room types for filters."""
    from sqlalchemy import text
    sql = """
        SELECT financial_year, room_type,
               AVG((min_selling_price + max_selling_price) / 2.0) AS mid
        FROM bto_price_ranges
        WHERE min_selling_price IS NOT NULL AND max_selling_price IS NOT NULL
    """
    params: dict = {}
    if town:
        sql += " AND town = :town"; params["town"] = town
    sql += " GROUP BY financial_year, room_type ORDER BY financial_year"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
        towns = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT town FROM bto_price_ranges ORDER BY town")).all()]
        room_types = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT room_type FROM bto_price_ranges ORDER BY room_type")).all()]

    years = sorted({r["financial_year"] for r in rows})
    by_rt: dict[str, dict[int, float]] = {}
    for r in rows:
        by_rt.setdefault(r["room_type"], {})[r["financial_year"]] = round(float(r["mid"]))
    by_room_type = [{
        "room_type": rt,
        "series": [{"financial_year": y, "mid": by_rt[rt].get(y)} for y in years],
    } for rt in sorted(by_rt.keys())]
    return {"years": years, "by_room_type": by_room_type,
            "towns": towns, "room_types": room_types}
