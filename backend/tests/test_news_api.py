"""Tests for GET /news endpoint."""
from __future__ import annotations

from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def _mock_exa_response(results: list[dict]) -> Mock:
    mock_resp = Mock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"results": results}
    return mock_resp


@patch("app.api.main.httpx.post")
@patch("app.api.main.settings")
def test_news_returns_mapped_items(mock_settings, mock_post):
    mock_settings.exa_api_key = "test-key"
    mock_post.return_value = _mock_exa_response([
        {
            "title": "HDB resale prices hit new high",
            "url": "https://straitstimes.com/hdb-prices",
            "publishedDate": "2026-06-01T00:00:00Z",
        },
        {
            "title": "BTO launch June 2026",
            "url": "https://channelnewsasia.com/bto",
            "publishedDate": "2026-05-28T00:00:00Z",
        },
    ])

    resp = client.get("/news")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["title"] == "HDB resale prices hit new high"
    assert data[0]["url"] == "https://straitstimes.com/hdb-prices"
    assert data[0]["published_date"] == "2026-06-01T00:00:00Z"
    assert data[0]["domain"] == "straitstimes.com"
    assert data[1]["domain"] == "channelnewsasia.com"


@patch("app.api.main.settings")
def test_news_503_when_no_api_key(mock_settings):
    mock_settings.exa_api_key = None

    resp = client.get("/news")

    assert resp.status_code == 503
    assert "EXA_API_KEY" in resp.json()["detail"]


@patch("app.api.main.httpx.post")
@patch("app.api.main.settings")
def test_news_502_on_exa_error(mock_settings, mock_post):
    import httpx as _httpx
    mock_settings.exa_api_key = "test-key"
    mock_post.side_effect = _httpx.HTTPError("upstream down")

    resp = client.get("/news")

    assert resp.status_code == 502


@patch("app.api.main.httpx.post")
@patch("app.api.main.settings")
def test_news_empty_results(mock_settings, mock_post):
    mock_settings.exa_api_key = "test-key"
    mock_post.return_value = _mock_exa_response([])

    resp = client.get("/news")

    assert resp.status_code == 200
    assert resp.json() == []
