"""Runtime configuration (stdlib only, so it imports in any environment)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding the process environment."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


_load_env_file(Path(__file__).resolve().parents[2] / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str | None = os.environ.get("DATABASE_URL")
    redis_url: str | None = os.environ.get("REDIS_URL")
    api_host: str = os.environ.get("API_HOST", "0.0.0.0")
    api_port: int = int(os.environ.get("API_PORT", "8010"))
    srid_wgs84: int = 4326
    srid_svy21: int = 3414
    srid_webmercator: int = 3857
    # Mock fallback when no database is configured.
    mock_seed: int = int(os.environ.get("MOCK_SEED", "42"))
    # HomeOS agent mode: "passthrough" uses Pydantic AI, "mock" uses canned demo copy.
    homeos_agent_mode: str = os.environ.get("HOMEOS_AGENT_MODE", "passthrough")
    # OneMap token — enables live commute routing and geocoding.
    onemap_token: str | None = os.environ.get("ONEMAP_TOKEN") or None
    # data.gov.sg API key — reduces rate-limit errors when fetching live data.
    datagov_api_key: str | None = os.environ.get("DATAGOV_API_KEY") or None
    lta_datamall_api_key: str | None = os.environ.get("LTA_DATAMALL_API_KEY") or None
    exa_api_key: str | None = os.environ.get("EXA_API_KEY") or None
    # URA Private Residential Property Transactions API (Feature 2). When the
    # access key is missing (or PRIVATE_PROPERTY_MOCK_MODE=true), the private
    # property mode runs on bundled fixtures so dev/CI never break.
    ura_access_key: str | None = os.environ.get("URA_ACCESS_KEY") or None
    ura_token_url: str = os.environ.get(
        "URA_TOKEN_URL", "https://eservice.ura.gov.sg/uraDataService/insertNewToken/v1")
    ura_api_url: str = os.environ.get(
        "URA_API_URL", "https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1")
    # Optional: Google Street View Static API key for real façade photos in the
    # detail view. Absent -> falls back to the free OneMap location thumbnail.
    google_maps_api_key: str | None = os.environ.get("GOOGLE_MAPS_API_KEY") or None
    private_property_mock_mode: bool = (
        os.environ.get("PRIVATE_PROPERTY_MOCK_MODE", "").lower() in ("true", "1", "yes")
        or not (os.environ.get("URA_ACCESS_KEY") or "").strip())


settings = Settings()
