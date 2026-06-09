"""Repository / engine selection for the API.

If DATABASE_URL is set and the SQLAlchemy stack is importable, use PostGIS.
Otherwise fall back to a seeded in-memory repository so the API runs out of the
box (useful for frontend development before the database is provisioned).
"""
from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.repositories.base import Repository


@lru_cache(maxsize=1)
def get_repository() -> Repository:
    if settings.database_url:
        try:
            from app.db.session import get_engine
            from app.repositories.postgis import PostgisRepository
            engine = get_engine()
            with engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return PostgisRepository(engine)
        except Exception as exc:  # pragma: no cover - import/connection failure
            import logging
            logging.getLogger(__name__).warning(
                "PostGIS unavailable (%s); falling back to in-memory mock", exc)
    from app.data.seed import build_seeded_repo
    repo, _ = build_seeded_repo(seed=settings.mock_seed)
    return repo


@lru_cache(maxsize=1)
def get_commute_provider():
    """OneMap routing when ONEMAP_TOKEN is set, else the heuristic fallback."""
    import os
    if os.environ.get("ONEMAP_TOKEN"):
        try:
            from app.services.commute.onemap import OneMapCommuteProvider
            return OneMapCommuteProvider()
        except Exception:  # pragma: no cover
            import logging
            logging.getLogger(__name__).warning(
                "OneMap provider unavailable; using heuristic fallback")
    from app.services.commute.provider import HeuristicCommuteProvider
    return HeuristicCommuteProvider(list(get_repository().mrt_stations()))


@lru_cache(maxsize=1)
def get_engine_or_none():
    """Engine for tile/reference SQL, or None in mock mode."""
    if not settings.database_url:
        return None
    try:
        from app.db.session import get_engine
        return get_engine()
    except Exception:  # pragma: no cover
        return None
