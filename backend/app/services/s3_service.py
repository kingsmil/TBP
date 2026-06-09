"""S3-backed data store for HDB Match.

Two use-cases:
  - Raw data archive: upload HDB transaction CSVs fetched from data.gov.sg so
    they can be replayed without hitting the public API again.
  - Analytics cache: persist expensive computed results (estate analytics,
    forecasts) as JSON blobs so the API can serve them without hitting PostGIS
    on every cold request.

All keys live under well-known prefixes so the bucket stays organised:
  data/hdb/transactions/<year>-<month>.csv
  cache/analytics/estate/<planning_area_id>.json
  cache/forecast/block/<block_id>.json
"""
from __future__ import annotations

import io
import json
import os
from typing import Any

from botocore.exceptions import ClientError  # type: ignore

from app.core.aws_config import get_s3

BUCKET = os.getenv("AWS_S3_BUCKET", "hdb-match-data")

# ── helpers ──────────────────────────────────────────────────────────────────


def _key_exists(key: str) -> bool:
    try:
        get_s3().head_object(Bucket=BUCKET, Key=key)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "404":
            return False
        raise


# ── transaction CSV archive ──────────────────────────────────────────────────


def upload_transaction_csv(year: int, month: int, csv_bytes: bytes) -> str:
    """Store a monthly HDB transaction CSV and return its S3 key."""
    key = f"data/hdb/transactions/{year:04d}-{month:02d}.csv"
    get_s3().put_object(
        Bucket=BUCKET,
        Key=key,
        Body=csv_bytes,
        ContentType="text/csv",
        ServerSideEncryption="AES256",
    )
    return key


def download_transaction_csv(year: int, month: int) -> bytes | None:
    """Return the raw CSV bytes for a month, or None if not archived yet."""
    key = f"data/hdb/transactions/{year:04d}-{month:02d}.csv"
    if not _key_exists(key):
        return None
    obj = get_s3().get_object(Bucket=BUCKET, Key=key)
    return obj["Body"].read()


def list_archived_months() -> list[str]:
    """Return YYYY-MM strings for every archived transaction file."""
    paginator = get_s3().get_paginator("list_objects_v2")
    months: list[str] = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix="data/hdb/transactions/"):
        for obj in page.get("Contents", []):
            filename = obj["Key"].split("/")[-1]          # e.g. 2024-03.csv
            months.append(filename.removesuffix(".csv"))
    return sorted(months)


# ── analytics JSON cache ──────────────────────────────────────────────────────


def cache_put(key: str, payload: Any, ttl_seconds: int | None = None) -> None:
    """Write a JSON-serialisable payload to S3 under the cache/ prefix."""
    body = json.dumps(payload, default=str).encode()
    extra: dict[str, Any] = {
        "ContentType": "application/json",
        "ServerSideEncryption": "AES256",
    }
    if ttl_seconds is not None:
        # S3 doesn't support TTL natively; store it as metadata so callers
        # can check freshness if needed.
        extra["Metadata"] = {"ttl-seconds": str(ttl_seconds)}
    get_s3().put_object(Bucket=BUCKET, Key=f"cache/{key}", Body=body, **extra)


def cache_get(key: str) -> Any | None:
    """Return the deserialised JSON at cache/<key>, or None on miss."""
    try:
        obj = get_s3().get_object(Bucket=BUCKET, Key=f"cache/{key}")
        return json.loads(obj["Body"].read())
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return None
        raise


def cache_invalidate(key: str) -> None:
    get_s3().delete_object(Bucket=BUCKET, Key=f"cache/{key}")


# ── report export ─────────────────────────────────────────────────────────────


def upload_report(report_id: str, html_bytes: bytes) -> str:
    """Store a generated HTML report and return a presigned URL (1 hour)."""
    key = f"reports/{report_id}.html"
    get_s3().put_object(
        Bucket=BUCKET,
        Key=key,
        Body=html_bytes,
        ContentType="text/html",
        ServerSideEncryption="AES256",
    )
    url: str = get_s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=3600,
    )
    return url
