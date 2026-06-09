"""Tests for the data.gov.sg HDB resale loader transforms."""
from __future__ import annotations

import httpx

from app.data.data_gov_sg import (
    block_from_record,
    geocode_block,
    make_block_id,
    transaction_from_record,
)


def test_make_block_id_is_stable_for_same_address() -> None:
    assert make_block_id("406", "ANG MO KIO AVE 10") == make_block_id(
        " 406 ", "ang mo kio ave 10"
    )


def test_block_from_record_uses_geocode_and_lease_year() -> None:
    record = {
        "town": "ANG MO KIO",
        "block": "406",
        "street_name": "ANG MO KIO AVE 10",
        "lease_commence_date": "1979",
    }
    geocode = {
        "POSTAL": "560406",
        "LONGITUDE": "103.853879910407",
        "LATITUDE": "1.36200453938712",
    }

    block = block_from_record(record, geocode)

    assert block.block_number == "406"
    assert block.street_name == "ANG MO KIO AVE 10"
    assert block.postal_code == "560406"
    assert block.lease_commencement_year == 1979
    assert round(block.point.lon, 6) == 103.85388
    assert round(block.point.lat, 6) == 1.362005


def test_transaction_from_record_normalizes_month_and_numbers() -> None:
    record = {
        "_id": 123,
        "month": "2026-06",
        "block": "406",
        "street_name": "ANG MO KIO AVE 10",
        "flat_type": "4 ROOM",
        "storey_range": "10 TO 12",
        "floor_area_sqm": "93",
        "resale_price": "600000",
    }

    txn = transaction_from_record(record)

    assert txn.transaction_id == 123
    assert txn.block_id == make_block_id("406", "ANG MO KIO AVE 10")
    assert txn.transaction_month == "2026-06-01"
    assert txn.floor_area_sqm == 93
    assert txn.resale_price == 600000


def test_geocode_block_returns_none_after_rate_limit() -> None:
    record = {"block": "406", "street_name": "ANG MO KIO AVE 10"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    assert geocode_block(client, record, retries=1) is None
