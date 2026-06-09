"""Idempotent local backend launcher."""
from __future__ import annotations

import json
import socket
import sys
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

from app.config import settings


def _health_url() -> str:
    host = "127.0.0.1" if settings.api_host in {"0.0.0.0", "::"} else settings.api_host
    return f"http://{host}:{settings.api_port}/health"


def _existing_backend() -> dict | None:
    try:
        with urlopen(_health_url(), timeout=2) as response:
            body = json.loads(response.read().decode("utf-8"))
            return body if response.status == 200 and body.get("status") == "ok" else None
    except (OSError, URLError, ValueError):
        return None


def _port_is_busy() -> bool:
    host = "127.0.0.1" if settings.api_host in {"0.0.0.0", "::"} else settings.api_host
    with socket.socket() as sock:
        return sock.connect_ex((host, settings.api_port)) == 0


def main() -> int:
    existing = _existing_backend()
    if existing is not None:
        print(
            f"Backend already running at {_health_url()} "
            f"({existing.get('mode', 'unknown')}, {existing.get('blocks', '?')} blocks)."
        )
        return 0
    if _port_is_busy():
        print(
            f"Port {settings.api_port} is occupied by another application. "
            "Change API_PORT in the root .env file.",
            file=sys.stderr,
        )
        return 2
    uvicorn.run("app.api.main:app", host=settings.api_host, port=settings.api_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
