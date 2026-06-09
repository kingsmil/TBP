from unittest.mock import patch

from app import run_server


@patch("app.run_server._existing_backend", return_value={"status": "ok", "mode": "postgis", "blocks": 9168})
@patch("app.run_server.uvicorn.run")
def test_existing_backend_is_reused(mock_run, _mock_existing, capsys):
    assert run_server.main() == 0
    mock_run.assert_not_called()
    assert "Backend already running" in capsys.readouterr().out


@patch("app.run_server._existing_backend", return_value=None)
@patch("app.run_server._port_is_busy", return_value=True)
@patch("app.run_server.uvicorn.run")
def test_foreign_port_conflict_has_clear_error(mock_run, _mock_busy, _mock_existing, capsys):
    assert run_server.main() == 2
    mock_run.assert_not_called()
    assert "occupied by another application" in capsys.readouterr().err


@patch("app.run_server._existing_backend", return_value=None)
@patch("app.run_server._port_is_busy", return_value=False)
@patch("app.run_server.uvicorn.run")
def test_free_port_starts_backend(mock_run, _mock_busy, _mock_existing):
    assert run_server.main() == 0
    mock_run.assert_called_once()
