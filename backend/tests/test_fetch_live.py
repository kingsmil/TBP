from unittest.mock import Mock, patch

from app.data.fetch_live import _datagov_fetch_all, fetch_hdb_transactions


def _response(records, total=10):
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "success": True,
        "result": {"records": records, "total": total},
    }
    return response


@patch("app.data.fetch_live.requests.get")
def test_datagov_key_uses_x_api_key_header(mock_get):
    mock_get.return_value = _response([])

    _datagov_fetch_all("dataset", api_key="secret", page_delay=0)

    assert mock_get.call_args.kwargs["headers"] == {"x-api-key": "secret"}


@patch("app.data.fetch_live.requests.get", side_effect=RuntimeError("offline"))
@patch("app.data.fetch_live._datagov_fetch_all")
def test_hdb_fetch_sorts_newest_and_stops_at_cutoff(mock_fetch, _mock_get):
    mock_fetch.return_value = [
        {"month": "2099-01"},
        {"month": "2000-01"},
    ]

    assert fetch_hdb_transactions(months=24, api_key="secret") == [
        {"month": "2099-01"}
    ]
    kwargs = mock_fetch.call_args.kwargs
    assert kwargs["sort"] == "month desc"
    assert kwargs["page_delay"] == 0.0
    assert kwargs["stop_when"]([{"month": "2000-01"}]) is True
