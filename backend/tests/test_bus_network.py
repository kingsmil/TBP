from unittest.mock import Mock, patch

from app.data.sync_bus_network import fetch_datamall_pages


@patch("app.data.sync_bus_network._get_json")
def test_fetch_datamall_pages_uses_skip_pagination(mock_get):
    mock_get.side_effect = [
        {"value": [{"id": i} for i in range(500)]},
        {"value": [{"id": 500}]},
    ]

    rows = fetch_datamall_pages("BusRoutes", "secret")

    assert len(rows) == 501
    assert mock_get.call_args_list[0].kwargs["params"] == {"$skip": 0}
    assert mock_get.call_args_list[1].kwargs["params"] == {"$skip": 500}
    assert mock_get.call_args_list[0].kwargs["headers"]["AccountKey"] == "secret"
