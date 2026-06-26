"""Estimated BTO Resale Availability — precompute layer.

For each BTO project / estate group we estimate when it may first become eligible
for the resale market:

    estimated_resale_eligible_date = completion/key-collection date + MOP years

The MOP depends on the flat's classification (see CLASSIFICATION_MOP). These are
ESTIMATES — actual eligibility depends on each owner's legal completion date and
physical occupation period. The UI labels them as such.

Two layered data sources (highest priority first):

  1. Manual seed file (data/manual/bto-project-mop-seed.json) — projects with a
     known / best-estimate completion or key-collection date. Authoritative.
  2. Launch metadata already ingested into bto_application_rates + bto_exercises
     (classification + launch date). We estimate completion as launch +
     COMPLETION_OFFSET_MONTHS, so these are LOW confidence.

Seed entries OVERRIDE launch-derived rows for the same
(project_name, town, flat_classification).

Refreshed monthly in the background (app.analysis.scheduler). Never on a request.

CLI:  python -m app.data.bto_mop
See:  docs/BTO_MOP_ESTIMATION_RULES.md
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import pathlib

log = logging.getLogger(__name__)

SEED_PATH = pathlib.Path(__file__).parent / "manual" / "bto-project-mop-seed.json"

# MOP (years) by normalised classification. Update this map when HDB changes the
# MOP policy — and record the change in docs/BTO_MOP_ESTIMATION_RULES.md.
CLASSIFICATION_MOP: dict[str, int] = {
    "STANDARD": 5,
    "UNCLASSIFIED": 5,
    "UNKNOWN": 5,        # default 5, but confidence is lowered for these
    "PLUS": 10,
    "PRIME": 10,
    "PLH": 10,           # Prime Location Public Housing (legacy name for Prime)
}

# Typical gap between a BTO launch and key collection (~3.5 years). Used only for
# launch-derived (LOW-confidence) rows; seed rows carry their own dates.
COMPLETION_OFFSET_MONTHS = 42

_VALID_CLASS = set(CLASSIFICATION_MOP)
_VALID_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
_VALID_SOURCE = {"HDB_LAUNCH_PAGE", "DATA_GOV_HDB_PROPERTY_INFO",
                 "DATA_GOV_COMPLETION_STATUS", "MANUAL_SEED"}


# ── pure helpers (unit-tested) ────────────────────────────────────────────────

def normalise_classification(raw: str | None) -> str:
    """Map a free-text classification to one of the canonical buckets."""
    if not raw:
        return "UNKNOWN"
    s = raw.strip().lower()
    if "plus" in s:
        return "PLUS"
    if "plh" in s:
        return "PLH"
    if "prime" in s:
        return "PRIME"
    if "standard" in s:
        return "STANDARD"
    if "unclassified" in s:
        return "UNCLASSIFIED"
    return "UNKNOWN"


def mop_years(classification: str) -> int:
    """MOP in years for a (already-normalised) classification."""
    return CLASSIFICATION_MOP.get(classification, 5)


def parse_partial_date(value) -> tuple[_dt.date | None, bool]:
    """Parse 'YYYY', 'YYYY-MM' or 'YYYY-MM-DD' -> (date, month_known).

    Year-only resolves to 1 Jan of that year with month_known=False. Returns
    (None, False) for anything unparseable.
    """
    if value is None:
        return None, False
    if isinstance(value, _dt.date):
        return value, True
    s = str(value).strip()
    if not s:
        return None, False
    parts = s.split("-")
    try:
        year = int(parts[0])
        if len(parts) == 1:
            return _dt.date(year, 1, 1), False
        month = int(parts[1])
        day = int(parts[2]) if len(parts) >= 3 else 1
        return _dt.date(year, month, day), True
    except (ValueError, IndexError):
        return None, False


def add_months(d: _dt.date, months: int) -> _dt.date:
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    return _dt.date(year, month, 1)


def add_years(d: _dt.date, years: int) -> _dt.date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 Feb
        return d.replace(year=d.year + years, day=28)


def confidence_for(source_type: str, month_known: bool, explicit: str | None = None) -> tuple[str, str]:
    """Return (confidence, reason). An explicit seed override wins."""
    if explicit and explicit.upper() in _VALID_CONFIDENCE:
        return explicit.upper(), "Confidence set explicitly in manual seed."
    if source_type == "MANUAL_SEED":
        if month_known:
            return "HIGH", "Project-level completion/key-collection month is known."
        return "MEDIUM", "Project-level completion year known; month estimated to January."
    # Launch-derived: only the launch date is known; completion is estimated.
    return "LOW", (f"Completion estimated as launch + {COMPLETION_OFFSET_MONTHS} months "
                   "(no project-level completion date available).")


def make_record(
    *,
    project_name: str,
    town: str | None,
    classification_raw: str | None,
    source_type: str,
    completion: str | None = None,
    key_collection: str | None = None,
    estate: str | None = None,
    launch_exercise: str | None = None,
    flat_types: str | None = None,
    source_url: str | None = None,
    last_verified_at=None,
    confidence_override: str | None = None,
) -> dict:
    """Build one normalised estimate record. Pure — no I/O."""
    classification = normalise_classification(classification_raw)
    years = mop_years(classification)

    comp_date, comp_month_known = parse_partial_date(completion)
    key_date, key_month_known = parse_partial_date(key_collection)
    # Prefer key-collection date as the MOP anchor (it's what HDB actually uses);
    # fall back to completion.
    anchor = key_date or comp_date
    month_known = key_month_known if key_date else comp_month_known
    eligible = add_years(anchor, years) if anchor else None

    confidence, reason = confidence_for(source_type, month_known, confidence_override)
    verified, _ = parse_partial_date(last_verified_at)

    return {
        "project_name": project_name,
        "town": town,
        "estate": estate,
        "launch_exercise": launch_exercise,
        "flat_classification": classification,
        "flat_types": flat_types,
        "estimated_completion_date": comp_date,
        "estimated_key_collection_date": key_date,
        "mop_years": years,
        "estimated_resale_eligible_date": eligible,
        "confidence": confidence,
        "confidence_reason": reason,
        "source_url": source_url,
        "source_type": source_type,
        "last_verified_at": verified,
        "lat": None,
        "lon": None,
    }


def _key(rec: dict) -> tuple:
    return (rec["project_name"], rec.get("town"), rec["flat_classification"])


# ── seed loading + validation ─────────────────────────────────────────────────

def validate_seed(data: dict) -> list[str]:
    """Return a list of human-readable problems (empty == valid)."""
    problems: list[str] = []
    projects = data.get("projects")
    if not isinstance(projects, list):
        return ["seed: 'projects' must be a list"]
    for i, p in enumerate(projects):
        where = f"projects[{i}]"
        if not isinstance(p, dict):
            problems.append(f"{where}: not an object")
            continue
        if not p.get("project_name"):
            problems.append(f"{where}: missing project_name")
        cls = p.get("flat_classification")
        if cls and normalise_classification(cls) == "UNKNOWN" and cls.upper() != "UNKNOWN":
            problems.append(f"{where}: unrecognised flat_classification '{cls}'")
        st = p.get("source_type")
        if st and st not in _VALID_SOURCE:
            problems.append(f"{where}: invalid source_type '{st}'")
        conf = p.get("confidence")
        if conf and conf.upper() not in _VALID_CONFIDENCE:
            problems.append(f"{where}: invalid confidence '{conf}'")
        if not p.get("estimated_completion_date") and not p.get("estimated_key_collection_date"):
            problems.append(f"{where}: needs estimated_completion_date or estimated_key_collection_date")
        for fld in ("estimated_completion_date", "estimated_key_collection_date"):
            if p.get(fld):
                d, _ = parse_partial_date(p[fld])
                if d is None:
                    problems.append(f"{where}: unparseable {fld} '{p[fld]}'")
    return problems


def load_seed(path: pathlib.Path = SEED_PATH) -> list[dict]:
    """Load + validate the seed file into normalised records."""
    if not path.exists():
        log.info("BTO MOP seed file not found at %s — skipping seed.", path)
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    problems = validate_seed(data)
    if problems:
        raise ValueError("Invalid BTO MOP seed file:\n  - " + "\n  - ".join(problems))
    out = []
    for p in data.get("projects", []):
        out.append(make_record(
            project_name=p["project_name"],
            town=p.get("town"),
            estate=p.get("estate"),
            launch_exercise=p.get("launch_exercise"),
            classification_raw=p.get("flat_classification"),
            flat_types=p.get("flat_types"),
            completion=p.get("estimated_completion_date"),
            key_collection=p.get("estimated_key_collection_date"),
            source_url=p.get("source_url"),
            source_type=p.get("source_type") or "MANUAL_SEED",
            last_verified_at=p.get("last_verified_at"),
            confidence_override=p.get("confidence"),
        ))
    return out


# ── launch-derived rows (from already-ingested BTO data) ──────────────────────

def estimate_from_launch_rows(launch_rows: list[dict]) -> list[dict]:
    """Build LOW-confidence records from bto_application_rates joined to exercises.

    Each input row: {estate_name, flat_types, classification, project_names,
    exercise_id, launch_start_date}.
    """
    out = []
    for r in launch_rows:
        launch = r.get("launch_start_date")
        if not launch:
            continue  # can't estimate completion without a launch date
        launch_date, _ = parse_partial_date(launch)
        if launch_date is None:
            continue
        completion = add_months(launch_date, COMPLETION_OFFSET_MONTHS)
        project = (r.get("project_names") or "").strip() or r.get("estate_name")
        out.append(make_record(
            project_name=project,
            town=r.get("estate_name"),
            estate=r.get("estate_name"),
            launch_exercise=r.get("exercise_id"),
            classification_raw=r.get("classification"),
            flat_types=r.get("flat_types"),
            completion=completion.isoformat(),
            source_type="HDB_LAUNCH_PAGE",
            source_url="https://homes.hdb.gov.sg/home/finding-a-flat",
        ))
    return out


def build_estimates(seed: list[dict], launch_rows: list[dict]) -> list[dict]:
    """Merge seed (authoritative) + launch-derived, dedupe, sort by soonest."""
    records: list[dict] = []
    seen: set[tuple] = set()
    for rec in seed:
        if _key(rec) in seen:
            continue
        records.append(rec)
        seen.add(_key(rec))
    for rec in estimate_from_launch_rows(launch_rows):
        if _key(rec) in seen:
            continue
        records.append(rec)
        seen.add(_key(rec))
    records.sort(key=lambda r: (r["estimated_resale_eligible_date"] or _dt.date.max,
                                r["project_name"]))
    return records


# ── DB read of launch metadata + persist ──────────────────────────────────────

def fetch_launch_rows(engine) -> list[dict]:
    """One row per (exercise, estate, classification) with launch date + flat types."""
    from sqlalchemy import text
    sql = """
        SELECT r.exercise_id,
               r.estate_name,
               COALESCE(r.classification, 'UNKNOWN') AS classification,
               STRING_AGG(DISTINCT r.flat_type, ', ' ORDER BY r.flat_type) AS flat_types,
               MAX(r.project_names) AS project_names,
               e.launch_start_date
        FROM bto_application_rates r
        JOIN bto_exercises e ON e.exercise_id = r.exercise_id
        GROUP BY r.exercise_id, r.estate_name, COALESCE(r.classification, 'UNKNOWN'),
                 e.launch_start_date
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).mappings().all()
    return [dict(r) for r in rows]


# ── geocoding: place each project on the map ──────────────────────────────────

_ONEMAP_SEARCH = "https://www.onemap.gov.sg/api/common/elastic/search"


def geocode_onemap(query: str) -> tuple[float, float] | None:
    """Best-effort lat/lon for a project name via OneMap's public search."""
    import requests
    if not query:
        return None
    try:
        r = requests.get(_ONEMAP_SEARCH, params={
            "searchVal": query, "returnGeom": "Y", "getAddrDetails": "N", "pageNum": 1,
        }, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code != 200:
            return None
        results = (r.json() or {}).get("results") or []
        if results:
            return float(results[0]["LATITUDE"]), float(results[0]["LONGITUDE"])
    except Exception:
        return None
    return None


def town_centroids(engine) -> dict[str, tuple[float, float]]:
    """Centroid (lat, lon) per town from hdb_blocks — the geocoding fallback."""
    from sqlalchemy import text
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT UPPER(town) AS town,
                   ST_Y(ST_Centroid(ST_Collect(geom))) AS lat,
                   ST_X(ST_Centroid(ST_Collect(geom))) AS lon
            FROM hdb_blocks WHERE geom IS NOT NULL GROUP BY UPPER(town)
        """)).all()
    return {r.town: (float(r.lat), float(r.lon)) for r in rows if r.lat is not None}


def _jitter(name: str) -> tuple[float, float]:
    """Small deterministic offset so same-town projects don't stack exactly."""
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return ((h % 1000) / 1000 - 0.5) * 0.012, ((h // 1000 % 1000) / 1000 - 0.5) * 0.012


def geocode_records(engine, records: list[dict]) -> None:
    """Fill lat/lon on each record: OneMap by project name, town-centroid fallback."""
    import time
    centroids = town_centroids(engine)
    located = 0
    for rec in records:
        try:
            name = (rec.get("project_name") or "").split(",")[0].strip()
            coord = geocode_onemap(name)
            if coord is None:
                base = centroids.get((rec.get("town") or "").upper().strip())
                if base is not None:
                    dlat, dlon = _jitter(rec.get("project_name") or name)
                    coord = (base[0] + dlat, base[1] + dlon)
            if coord is not None:
                rec["lat"], rec["lon"] = coord
                located += 1
        except Exception as exc:
            log.warning("Geocode failed for %s: %s", rec.get("project_name"), exc)
        time.sleep(0.12)  # be gentle with OneMap
    log.info("Geocoded %d/%d BTO projects.", located, len(records))


def persist(engine, records: list[dict]) -> None:
    from sqlalchemy import text
    if not records:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO bto_project_mop_estimates
              (project_name, town, estate, launch_exercise, flat_classification,
               flat_types, estimated_completion_date, estimated_key_collection_date,
               mop_years, estimated_resale_eligible_date, confidence, confidence_reason,
               source_url, source_type, last_verified_at, lat, lon, updated_at)
            VALUES
              (:project_name, :town, :estate, :launch_exercise, :flat_classification,
               :flat_types, :estimated_completion_date, :estimated_key_collection_date,
               :mop_years, :estimated_resale_eligible_date, :confidence, :confidence_reason,
               :source_url, :source_type, :last_verified_at, :lat, :lon, NOW())
            ON CONFLICT (project_name, town, flat_classification) DO UPDATE SET
              estate=EXCLUDED.estate, launch_exercise=EXCLUDED.launch_exercise,
              flat_types=EXCLUDED.flat_types, lat=EXCLUDED.lat, lon=EXCLUDED.lon,
              estimated_completion_date=EXCLUDED.estimated_completion_date,
              estimated_key_collection_date=EXCLUDED.estimated_key_collection_date,
              mop_years=EXCLUDED.mop_years,
              estimated_resale_eligible_date=EXCLUDED.estimated_resale_eligible_date,
              confidence=EXCLUDED.confidence, confidence_reason=EXCLUDED.confidence_reason,
              source_url=EXCLUDED.source_url, source_type=EXCLUDED.source_type,
              last_verified_at=EXCLUDED.last_verified_at, updated_at=NOW()
        """), records)


def rebuild(engine) -> list[dict]:
    """Load seed + launch data, build estimates, persist. Returns the records."""
    seed = load_seed()
    launch_rows = fetch_launch_rows(engine)
    records = build_estimates(seed, launch_rows)
    geocode_records(engine, records)
    persist(engine, records)
    return records


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    from app.api.deps import get_engine_or_none
    engine = get_engine_or_none()
    if engine is None:
        log.error("No PostGIS database (DATABASE_URL unset/unreachable).")
        return 2
    records = rebuild(engine)
    log.info("Stored %d BTO MOP estimate(s) (%d from seed).",
             len(records), sum(1 for r in records if r["source_type"] == "MANUAL_SEED"))
    return 0 if records else 1


if __name__ == "__main__":
    raise SystemExit(main())
