"""BTO sales-exercise application-rate ingestion.

Source: the HDB Flat Portal publishes each exercise's flat supply + applications
+ per-category application rates as JSON at

    https://services-homes.hdb.gov.sg/sales/files/apprates/BTO{YYYYMM}.json

This module discovers the available exercises (probing recent months), parses
them, and upserts into bto_exercises + bto_application_rates. It is reference
data that changes only when HDB runs a new exercise (~3x/year), so it is fetched
in the background (monthly via the scheduler), never on a client request.

CLI: python -m app.data.bto [--months-back 48]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import logging
import os

log = logging.getLogger(__name__)

BASE_URL = "https://services-homes.hdb.gov.sg/sales/files/apprates/BTO{ym}.json"
_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def _label(ym: str) -> str:
    try:
        return f"{_MONTHS[int(ym[4:6]) - 1]} {ym[:4]}"
    except (ValueError, IndexError):
        return ym


def parse_exercise(ym: str, raw: dict) -> tuple[dict, list[dict]]:
    """Pure parse of one exercise JSON into (summary, rate_rows). Testable."""
    estates = raw.get("estate_list") or []
    rows: list[dict] = []
    total_units = total_apps = 0
    for e in estates:
        estate = e.get("estate_name")
        for ft in e.get("flat_type_list") or []:
            supply = ft.get("flat_supply") or 0
            apps = ft.get("total_applicant_no") or 0
            total_units += supply
            total_apps += apps
            projects = ft.get("projects") or []
            rates = ft.get("app_rates") or {}
            classes = sorted({p.get("project_classification") for p in projects
                              if p.get("project_classification")})
            rows.append({
                "estate_name": estate,
                "flat_type": ft.get("flat_type"),
                "classification": ", ".join(classes) or None,
                "project_names": ", ".join(p.get("project_name") for p in projects
                                           if p.get("project_name")) or None,
                "flat_supply": supply,
                "total_applicant_no": apps,
                "overall_rate": round(apps / supply, 2) if supply else None,
                "rate_first_time_fam": rates.get("first_time_fam"),
                "rate_second_time_fam": rates.get("second_time_fam"),
                "rate_first_time_singles": rates.get("first_time_singles"),
                "rate_elderly": rates.get("elderly"),
            })
    summary = {
        "exercise_id": ym,
        "label": _label(ym),
        "launch_start_date": raw.get("launch_start_date") or None,
        "launch_end_date": raw.get("launch_end_date") or None,
        "is_final_update": bool(raw.get("is_final_update")),
        "estate_count": len(estates),
        "total_units": total_units,
        "total_applicants": total_apps,
        "overall_app_rate": round(total_apps / total_units, 2) if total_units else None,
    }
    return summary, rows


def fetch_exercise(ym: str, timeout: float = 20.0) -> dict | None:
    """Fetch one exercise's raw JSON, or None if it doesn't exist (404)."""
    import requests
    try:
        r = requests.get(BASE_URL.format(ym=ym),
                         headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                         timeout=timeout)
        if r.status_code != 200:
            return None
        data = r.json()
        return data if data.get("estate_list") else None
    except Exception:
        return None


def discover_exercises(months_back: int = 48) -> list[tuple[dict, list[dict]]]:
    """Probe recent months (and up to 3 ahead) and parse every exercise found."""
    today = _dt.date.today()
    base = today.year * 12 + (today.month - 1)   # months since year 0
    out = []
    for offset in range(-3, months_back + 1):    # negative offset = future months
        year, month0 = divmod(base - offset, 12)
        ym_str = f"{year}{month0 + 1:02d}"
        raw = fetch_exercise(ym_str)
        if raw is not None:
            out.append(parse_exercise(ym_str, raw))
            log.info("BTO exercise %s found.", ym_str)
    return out


def persist(engine, exercises: list[tuple[dict, list[dict]]]) -> None:
    from sqlalchemy import text
    with engine.begin() as conn:
        for summary, rows in exercises:
            conn.execute(text("""
                INSERT INTO bto_exercises
                  (exercise_id, label, launch_start_date, launch_end_date, is_final_update,
                   estate_count, total_units, total_applicants, overall_app_rate, fetched_at)
                VALUES
                  (:exercise_id, :label, :launch_start_date, :launch_end_date, :is_final_update,
                   :estate_count, :total_units, :total_applicants, :overall_app_rate, NOW())
                ON CONFLICT (exercise_id) DO UPDATE SET
                  label=EXCLUDED.label, launch_start_date=EXCLUDED.launch_start_date,
                  launch_end_date=EXCLUDED.launch_end_date, is_final_update=EXCLUDED.is_final_update,
                  estate_count=EXCLUDED.estate_count, total_units=EXCLUDED.total_units,
                  total_applicants=EXCLUDED.total_applicants, overall_app_rate=EXCLUDED.overall_app_rate,
                  fetched_at=NOW()
            """), summary)
            conn.execute(text("DELETE FROM bto_application_rates WHERE exercise_id = :e"),
                         {"e": summary["exercise_id"]})
            if rows:
                for r in rows:
                    r["exercise_id"] = summary["exercise_id"]
                conn.execute(text("""
                    INSERT INTO bto_application_rates
                      (exercise_id, estate_name, flat_type, classification, project_names,
                       flat_supply, total_applicant_no, overall_rate, rate_first_time_fam,
                       rate_second_time_fam, rate_first_time_singles, rate_elderly)
                    VALUES
                      (:exercise_id, :estate_name, :flat_type, :classification, :project_names,
                       :flat_supply, :total_applicant_no, :overall_rate, :rate_first_time_fam,
                       :rate_second_time_fam, :rate_first_time_singles, :rate_elderly)
                """), rows)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Ingest HDB BTO application rates")
    parser.add_argument("--months-back", type=int, default=48,
                        help="How many months back to probe for exercises (default 48)")
    args = parser.parse_args()

    from app.api.deps import get_engine_or_none
    engine = get_engine_or_none()
    if engine is None:
        log.error("No PostGIS database (DATABASE_URL unset/unreachable).")
        return 2

    log.info("Discovering BTO exercises (last %d months)...", args.months_back)
    exercises = discover_exercises(args.months_back)
    if not exercises:
        log.warning("No BTO exercises found.")
        return 1
    persist(engine, exercises)
    log.info("Stored %d BTO exercise(s): %s", len(exercises),
             ", ".join(s["exercise_id"] for s, _ in exercises))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
