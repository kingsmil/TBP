"""Normalise raw URA transaction rows into our PrivateTransaction shape.

URA's PMI_Resi_Transaction service returns an array of projects, each with a
`transaction` array. We flatten + normalise each transaction. Pure functions —
unit-tested, no I/O.
"""
from __future__ import annotations

import datetime as _dt
import hashlib

SQM_TO_SQFT = 10.7639

# URA typeOfSale codes.
_SALE_TYPE = {"1": "NEW_SALE", "2": "SUB_SALE", "3": "RESALE"}

# URA propertyType -> our enum. Landed types are disambiguated by typeOfArea
# ("Strata" => STRATA_LANDED, else LANDED).
_LANDED = {"Terrace", "Semi-detached", "Detached", "Strata Detached",
           "Strata Semidetached", "Strata Terrace"}


def normalise_property_type(raw_type: str | None, type_of_area: str | None) -> str:
    t = (raw_type or "").strip()
    if t == "Executive Condominium":
        return "EC"
    if t == "Condominium":
        return "CONDO"
    if t == "Apartment":
        return "APARTMENT"
    if t in _LANDED or "Strata" in t or t in ("Terrace", "Semi-detached", "Detached"):
        if (type_of_area or "").strip().lower() == "strata" or t.startswith("Strata"):
            return "STRATA_LANDED"
        return "LANDED"
    # Fallback: treat unknown strata as condo-like, land as landed.
    if (type_of_area or "").strip().lower() == "land":
        return "LANDED"
    return "CONDO"


def parse_contract_date(mmyy: str | None) -> str | None:
    """URA contractDate is 'MMYY' (e.g. '0124' = Jan 2024) -> 'YYYY-MM-01'."""
    if not mmyy or len(str(mmyy).strip()) != 4:
        return None
    s = str(mmyy).strip()
    try:
        month = int(s[:2])
        year = 2000 + int(s[2:])
        if not 1 <= month <= 12:
            return None
        return _dt.date(year, month, 1).isoformat()
    except ValueError:
        return None


def _to_float(v) -> float | None:
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _txn_id(project: str, t: dict) -> str:
    raw = f"{project}|{t.get('contractDate')}|{t.get('price')}|{t.get('area')}|{t.get('floorRange')}|{t.get('noOfUnits')}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def normalise_transaction(project_name: str, street: str | None, market_segment: str | None,
                          x: str | None, y: str | None, t: dict) -> dict | None:
    """One URA transaction row -> normalised dict, or None if it's unusable."""
    price = _to_float(t.get("price"))
    area_sqm = _to_float(t.get("area"))
    sale_date = parse_contract_date(t.get("contractDate"))
    if price is None or sale_date is None:
        return None
    area_sqft = round(area_sqm * SQM_TO_SQFT, 1) if area_sqm else None
    psf = round(price / area_sqft, 0) if area_sqft else None
    return {
        "id": _txn_id(project_name, t),
        "project_name": project_name or None,
        "property_type": normalise_property_type(t.get("propertyType"), t.get("typeOfArea")),
        "sale_type": _SALE_TYPE.get(str(t.get("typeOfSale")), "RESALE"),
        "district": str(t.get("district")) if t.get("district") else None,
        "planning_region": market_segment or None,  # CCR / RCR / OCR
        "address": street or None,
        "sale_date": sale_date,
        "price": round(price),
        "area_sqm": round(area_sqm, 1) if area_sqm else None,
        "area_sqft": area_sqft,
        "psf": psf,
        "tenure": (t.get("tenure") or None),
        "floor_range": (t.get("floorRange") or None),
        "source": "URA",
        # SVY21 (EPSG:3414) coords from the project; converted to lat/lon on
        # persist (PostGIS ST_Transform). lat/lon stay None on the in-memory path.
        "svy_x": _to_float(x),
        "svy_y": _to_float(y),
        "lat": None,
        "lon": None,
    }


def normalise_batch(result: list[dict]) -> list[dict]:
    """Flatten a URA `Result` array (projects -> transactions) into our rows.

    Near-identical caveats can hash to the same id; we suffix collisions so every
    transaction keeps a unique, stable id (used as a PK and as a UI key)."""
    out: list[dict] = []
    seen: dict[str, int] = {}
    for proj in result or []:
        name = proj.get("project")
        street = proj.get("street")
        seg = proj.get("marketSegment")
        x, y = proj.get("x"), proj.get("y")
        for t in proj.get("transaction") or []:
            row = normalise_transaction(name, street, seg, x, y, t)
            if row is None:
                continue
            base = row["id"]
            n = seen.get(base, 0)
            seen[base] = n + 1
            if n:
                row["id"] = f"{base}-{n}"
            out.append(row)
    return out
