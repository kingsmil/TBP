"""Background auto-refresh for appreciation rankings.

Replaces an external cron: a lightweight asyncio task started in the FastAPI
lifespan checks the rankings' age and rebuilds them in a worker thread when they
are missing or older than RANKINGS_STALE_DAYS (default 30 = monthly). The check
is cheap (one MAX(computed_at) query) and the rebuild runs off the event loop,
so the server stays responsive and boot is never blocked.

Disable with RANKINGS_AUTO_REFRESH=false. Only starts when PostGIS is available,
so tests / mock mode are unaffected.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger(__name__)

CHECK_INTERVAL_S = 6 * 3600  # re-check staleness every 6h


def _enabled() -> bool:
    return os.environ.get("RANKINGS_AUTO_REFRESH", "true").lower() not in ("false", "0", "no")


def _stale_days() -> int:
    try:
        return int(os.environ.get("RANKINGS_STALE_DAYS", "30"))
    except ValueError:
        return 30


def _window_years() -> int:
    try:
        return int(os.environ.get("RANKINGS_WINDOW_YEARS", "10"))
    except ValueError:
        return 10


def _score_top_n() -> int | None:
    """Cap composite scoring to the top-N blocks per region (0 = all)."""
    from app.analysis.appreciation_rankings import DEFAULT_SCORE_TOP_N
    try:
        n = int(os.environ.get("RANKINGS_SCORE_TOP_N", str(DEFAULT_SCORE_TOP_N)))
    except ValueError:
        return DEFAULT_SCORE_TOP_N
    return None if n == 0 else n


def _age_days(engine) -> float | None:
    """Age of the current rankings in days, or None if there are none yet."""
    from sqlalchemy import text
    with engine.connect() as conn:
        ts = conn.execute(text("SELECT MAX(computed_at) FROM region_appreciation_ranking")).scalar()
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0


def _rebuild() -> None:
    """Synchronous rebuild — runs in a worker thread."""
    from app.api.deps import get_engine_or_none, get_repository
    from app.analysis import appreciation_rankings as ar
    engine = get_engine_or_none()
    if engine is None:
        return
    # Background job: include the composite score (bounded to top-N/region).
    blocks, regions = ar.build_rankings(get_repository(), years=_window_years(),
                                        with_score=True, score_top_n=_score_top_n())
    if blocks or regions:
        ar.persist(engine, blocks, regions)
        log.info("Auto-refreshed appreciation rankings: %d blocks, %d regions.",
                 len(blocks), len(regions))


def _bto_age_days(engine) -> float | None:
    from sqlalchemy import text
    with engine.connect() as conn:
        ts = conn.execute(text("SELECT MAX(fetched_at) FROM bto_exercises")).scalar()
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0


def _refresh_bto() -> None:
    """Synchronous BTO ingest — runs in a worker thread."""
    from app.api.deps import get_engine_or_none
    from app.data import bto
    engine = get_engine_or_none()
    if engine is None:
        return
    exercises = bto.discover_exercises()
    if exercises:
        bto.persist(engine, exercises)
        log.info("Auto-refreshed BTO data: %d exercise(s).", len(exercises))
    try:
        prices = bto.fetch_price_ranges()
        bto.persist_price_ranges(engine, prices)
        log.info("Auto-refreshed BTO price ranges: %d row(s).", len(prices))
    except Exception as exc:
        log.warning("BTO price-range refresh failed: %s", exc)
    # MOP resale-availability estimates depend on the launch data just ingested.
    try:
        from app.data import bto_mop
        records = bto_mop.rebuild(engine)
        log.info("Rebuilt BTO MOP resale-availability estimates: %d row(s).", len(records))
    except Exception as exc:
        log.warning("BTO MOP estimate rebuild failed: %s", exc)


def _ura_age_days(engine) -> float | None:
    from app.services.private_property import store
    return store.age_days(engine)


def _refresh_ura() -> None:
    """Seed / refresh private (URA) transactions — runs in a worker thread."""
    from app.api.deps import get_engine_or_none
    from app.data import ura
    engine = get_engine_or_none()
    if engine is None:
        return
    n = ura.rebuild(engine)
    if n:
        log.info("Auto-refreshed private (URA) transactions: %d rows.", n)


def _amenity_age_days(engine) -> float | None:
    from app.services import amenities as amenities_svc
    return amenities_svc.db_age_days(engine)


def _refresh_amenities() -> None:
    """Seed / refresh OneMap amenity POIs — runs in a worker thread."""
    from app.api.deps import get_engine_or_none
    from app.data import amenities as amenities_data
    engine = get_engine_or_none()
    if engine is None:
        return
    total = amenities_data.rebuild(engine)
    if total:
        log.info("Auto-refreshed amenity POIs: %d.", total)


async def _loop() -> None:
    from app.api.deps import get_engine_or_none
    while True:
        try:
            engine = get_engine_or_none()
            if engine is not None:
                age = _age_days(engine)
                if age is None or age >= _stale_days():
                    log.info("Appreciation rankings %s — rebuilding in background…",
                             "missing" if age is None else f"are {age:.0f} days old")
                    await asyncio.to_thread(_rebuild)
                try:
                    bto_age = _bto_age_days(engine)
                    if bto_age is None or bto_age >= _stale_days():
                        log.info("BTO data %s — refreshing in background…",
                                 "missing" if bto_age is None else f"is {bto_age:.0f} days old")
                        await asyncio.to_thread(_refresh_bto)
                except Exception as exc:
                    log.warning("BTO refresh check failed: %s", exc)
                try:
                    ura_age = _ura_age_days(engine)
                    if ura_age is None or ura_age >= _stale_days():
                        log.info("Private (URA) transactions %s — refreshing in background…",
                                 "missing" if ura_age is None else f"are {ura_age:.0f} days old")
                        await asyncio.to_thread(_refresh_ura)
                except Exception as exc:
                    log.warning("URA refresh check failed: %s", exc)
                try:
                    am_age = _amenity_age_days(engine)
                    if am_age is None or am_age >= _stale_days():
                        log.info("Amenity POIs %s — refreshing in background…",
                                 "missing" if am_age is None else f"are {am_age:.0f} days old")
                        await asyncio.to_thread(_refresh_amenities)
                except Exception as exc:
                    log.warning("Amenity refresh check failed: %s", exc)
        except Exception as exc:  # never let the loop die
            log.warning("Ranking refresh check failed: %s", exc)
        await asyncio.sleep(CHECK_INTERVAL_S)


def start_ranking_refresh() -> asyncio.Task | None:
    """Start the background refresh task, or None if disabled / no database."""
    if not _enabled():
        return None
    from app.api.deps import get_engine_or_none
    if get_engine_or_none() is None:
        return None
    try:
        return asyncio.create_task(_loop())
    except RuntimeError:
        return None
