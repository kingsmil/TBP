"""SQLAlchemy engine factory for the PostGIS connection.

Production only (needs SQLAlchemy + psycopg). Imported lazily by the repo
selector so the app still runs in mock mode without these installed.
"""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.config import settings


def _sqlalchemy_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    return url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set")
    # future=True for SQLAlchemy 2.0 style; pool_pre_ping to survive idle drops.
    return create_engine(
        _sqlalchemy_url(settings.database_url),
        future=True,
        pool_pre_ping=True,
    )
