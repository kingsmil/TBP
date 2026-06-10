#!/usr/bin/env python3
"""
HDB Match — E2E test runner (like setup.py, but for tests).

Boots the compose database if needed, verifies it has seeded data, then runs
the end-to-end test suite (backend/tests/e2e/) against the REAL PostGIS data.

Usage:
  python run_e2e.py            # ensure db up, run E2E tests
  python run_e2e.py --no-up    # assume db is already running
  python run_e2e.py -k search  # pass extra args through to pytest
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
BACKEND = ROOT / "backend"
DEFAULT_DATABASE_URL = "postgresql://hdbmatch:hdbmatch@localhost:5432/hdbmatch"


def _ansi(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def ok(msg):   print(_ansi("32", f"  ✓  {msg}"))
def info(msg): print(_ansi("36", f"  →  {msg}"))
def die(msg):  print(_ansi("31", f"  x  {msg}")); sys.exit(1)


def python_bin() -> str:
    """Prefer the backend venv if it exists, else the current interpreter."""
    venv = BACKEND / ".venv" / "bin" / "python"
    if venv.exists():
        return str(venv)
    return sys.executable


def ensure_db_up() -> None:
    info("Starting compose db (no-op if already up)…")
    r = subprocess.run(["docker", "compose", "up", "-d", "db"], cwd=ROOT)
    if r.returncode != 0:
        die("docker compose up failed — is Docker running?")
    for _ in range(30):
        r = subprocess.run(
            ["docker", "exec", "hdbmatch_postgis", "pg_isready", "-U", "hdbmatch", "-d", "hdbmatch"],
            capture_output=True,
        )
        if r.returncode == 0:
            ok("PostGIS is ready")
            return
        time.sleep(2)
    die("PostGIS did not become healthy within 60s")


def check_seeded() -> None:
    r = subprocess.run(
        ["docker", "exec", "hdbmatch_postgis", "psql", "-U", "hdbmatch", "-d", "hdbmatch",
         "-t", "-A", "-c", "SELECT count(*) FROM hdb_blocks"],
        capture_output=True, text=True,
    )
    count = int(r.stdout.strip() or 0) if r.returncode == 0 else 0
    if count == 0:
        die("Database has no blocks. Seed it first: python setup.py")
    ok(f"Database seeded ({count} blocks)")


def run_tests(extra: list[str]) -> int:
    env = os.environ.copy()
    env.setdefault("DATABASE_URL", DEFAULT_DATABASE_URL)
    # Never make live LLM calls from tests (the suite re-enforces this too).
    env["LLM_PROVIDER"] = "test"
    env.pop("AI_GATEWAY_API_KEY", None)
    info(f"Running E2E tests against {env['DATABASE_URL']}")
    cmd = [python_bin(), "-m", "pytest", "tests/e2e/", "-v", *extra]
    return subprocess.run(cmd, cwd=BACKEND, env=env).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run E2E tests against the compose database.")
    parser.add_argument("--no-up", action="store_true", help="skip docker compose up")
    args, extra = parser.parse_known_args()

    if not args.no_up:
        ensure_db_up()
    check_seeded()
    return run_tests(extra)


if __name__ == "__main__":
    raise SystemExit(main())
