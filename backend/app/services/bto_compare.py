"""BTO vs Resale comparison for a town + flat type.

Joins three sources for one decision view:
  * BTO offered price       (bto_price_ranges, data.gov.sg)
  * BTO ballot competitiveness (bto_application_rates, HDB portal)
  * Resale median price + growth (live resale transactions)

The resale side aggregates all transactions once and is cached (shared, changes
only when data changes), so the endpoint is cheap.
"""
from __future__ import annotations

import statistics

from app.repositories.base import Repository
from app.services.cache import SWRCache

WAIT_YEARS_TEXT = "~3–4 years"
_resale_cache = SWRCache(ttl=6 * 3600)


def _norm_room(s: str | None) -> str:
    """Canonicalise a flat/room type: '4-room' / '4 ROOM' -> '4 ROOM'."""
    return (s or "").strip().upper().replace("-", " ").replace("  ", " ")


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values)) if values else None


def _resale_index(repo: Repository) -> dict:
    """{(TOWN, ROOM): {median_price, median_psf, count, annual:{year:median}}}."""
    blocks = list(repo.blocks())
    town_of = {b.block_id: (b.town or "").upper() for b in blocks}
    agg: dict = {}
    for t in repo.transactions():
        town = town_of.get(t.block_id)
        if not town:
            continue
        key = (town, _norm_room(t.flat_type))
        d = agg.setdefault(key, {"prices": [], "psfs": [], "annual": {}})
        d["prices"].append(t.resale_price)
        d["psfs"].append(t.psf)
        d["annual"].setdefault(int(t.transaction_month[:4]), []).append(t.resale_price)
    out = {}
    for key, d in agg.items():
        out[key] = {
            "median_price": _median(d["prices"]),
            "median_psf": round(statistics.median(d["psfs"]), 1) if d["psfs"] else None,
            "count": len(d["prices"]),
            "annual": {y: _median(v) for y, v in d["annual"].items()},
        }
    return out


def _resale_index_cached(repo: Repository) -> dict:
    return _resale_cache.get("all", lambda: _resale_index(repo))


def _cagr(annual: dict[int, float]) -> float | None:
    years = sorted(annual)
    if len(years) < 2:
        return None
    y0, y1 = years[0], years[-1]
    p0, p1 = annual[y0], annual[y1]
    if not p0 or y1 == y0:
        return None
    return round(((p1 / p0) ** (1.0 / (y1 - y0)) - 1.0) * 100, 2)


def options(repo: Repository, engine) -> dict:
    """Towns + flat types that have BTO price data (the comparable set)."""
    from sqlalchemy import text
    with engine.connect() as conn:
        towns = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT town FROM bto_price_ranges ORDER BY town"))]
        rooms = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT room_type FROM bto_price_ranges ORDER BY room_type"))]
    return {"towns": towns, "flat_types": rooms}


def compare(repo: Repository, engine, town: str, flat_type: str) -> dict:
    from sqlalchemy import text
    town_u = town.strip().upper()
    room = _norm_room(flat_type)

    # ── BTO offered price (latest year) + price-by-year ────────────────────────
    with engine.connect() as conn:
        price_rows = conn.execute(text("""
            SELECT financial_year, min_selling_price, max_selling_price
            FROM bto_price_ranges
            WHERE UPPER(town) = :t AND REPLACE(UPPER(room_type), '-', ' ') = :r
            ORDER BY financial_year
        """), {"t": town_u, "r": room}).mappings().all()
        # BTO ballot rate for this town in the latest exercise that has it.
        rate_row = conn.execute(text("""
            SELECT exercise_id,
                   SUM(flat_supply) AS units, SUM(total_applicant_no) AS apps
            FROM bto_application_rates
            WHERE UPPER(estate_name) = :t
              AND REPLACE(UPPER(flat_type), '-', ' ') LIKE :r || '%'
            GROUP BY exercise_id ORDER BY exercise_id DESC LIMIT 1
        """), {"t": town_u, "r": room}).mappings().first()

    bto_by_year = {r["financial_year"]: round(((r["min_selling_price"] or 0)
                   + (r["max_selling_price"] or 0)) / 2) for r in price_rows
                   if r["min_selling_price"] and r["max_selling_price"]}
    latest = price_rows[-1] if price_rows else None
    bto_mid = (round(((latest["min_selling_price"] or 0) + (latest["max_selling_price"] or 0)) / 2)
               if latest and latest["min_selling_price"] and latest["max_selling_price"] else None)
    bto_rate = (round((rate_row["apps"] or 0) / rate_row["units"], 2)
                if rate_row and rate_row["units"] else None)

    bto = {
        "available": bto_mid is not None,
        "latest_year": latest["financial_year"] if latest else None,
        "min_price": latest["min_selling_price"] if latest else None,
        "max_price": latest["max_selling_price"] if latest else None,
        "mid_price": bto_mid,
        "app_rate": bto_rate,
        "wait_years": WAIT_YEARS_TEXT,
    }

    # ── Resale side ────────────────────────────────────────────────────────────
    idx = _resale_index_cached(repo).get((town_u, room))
    resale = {
        "available": idx is not None and idx["median_price"] is not None,
        "median_price": idx["median_price"] if idx else None,
        "median_psf": idx["median_psf"] if idx else None,
        "txn_count": idx["count"] if idx else 0,
        "cagr_pct": _cagr(idx["annual"]) if idx else None,
        "wait_years": "Move in within months",
    }

    # ── Gap ────────────────────────────────────────────────────────────────────
    gap = {"price_diff": None, "price_pct": None, "annual_saving": None}
    if bto_mid and resale["median_price"]:
        diff = resale["median_price"] - bto_mid
        gap["price_diff"] = diff
        gap["price_pct"] = round(diff / bto_mid * 100, 1)
        gap["annual_saving"] = round(diff / 3.5) if diff > 0 else 0

    # ── Price series overlay (common years) ────────────────────────────────────
    resale_annual = idx["annual"] if idx else {}
    years = sorted(set(bto_by_year) | set(resale_annual))
    price_series = [{"year": y, "bto": bto_by_year.get(y), "resale": resale_annual.get(y)}
                    for y in years]

    return {"town": town, "flat_type": flat_type, "bto": bto, "resale": resale,
            "gap": gap, "price_series": price_series}
