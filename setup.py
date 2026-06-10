#!/usr/bin/env python3
"""
HDB Match — cross-platform setup script (Mac, Windows, Linux)

Usage:
  python setup.py              # full setup (requires Docker for PostGIS)
  python setup.py --mock       # skip Docker/DB — in-memory mock data
  python setup.py --run        # setup + launch both servers
  python setup.py --mock --run # mock mode + launch
"""
import argparse
import io
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows so box-drawing / emoji don't crash
if platform.system() == "Windows":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

IS_WIN = platform.system() == "Windows"

# Enable ANSI colours in Windows Terminal / PowerShell 7
if IS_WIN:
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7
        )
    except Exception:
        pass

def _ansi(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"

def ok(msg):   print(_ansi("32", f"  ✓  {msg}"))
def info(msg): print(_ansi("36", f"  →  {msg}"))
def warn(msg): print(_ansi("33", f"  !  {msg}"))
def die(msg):  print(_ansi("31", f"  x  {msg}")); sys.exit(1)

def header(msg):
    print()
    bar = "-" * max(0, 50 - len(msg))
    print(_ansi("36", f"-- {msg} {bar}"))


def run(cmd: list, *, cwd=None, check=True, capture=False, env=None):
    """Run a command, streaming output unless capture=True.
    shell=True is required on Windows so .cmd shims (npm, npx) are resolved."""
    result = subprocess.run(
        cmd, cwd=cwd, check=False,
        capture_output=capture, text=True,
        shell=IS_WIN, env=env,
    )
    if check and result.returncode != 0:
        if capture and (result.stdout or result.stderr):
            print(result.stdout or result.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


ROOT = Path(__file__).parent.resolve()
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def load_env() -> dict:
    """Parse .env file and return a merged environment dict."""
    env = os.environ.copy()
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env.setdefault(key.strip(), val.strip())
    return env

# Virtual-env paths differ by OS
if IS_WIN:
    VENV = BACKEND / ".venv" / "Scripts"
    PYTHON  = VENV / "python.exe"
    PIP     = VENV / "pip.exe"
    UVICORN = VENV / "uvicorn.exe"
else:
    VENV = BACKEND / ".venv" / "bin"
    PYTHON  = VENV / "python"
    PIP     = VENV / "pip"
    UVICORN = VENV / "uvicorn"


# ── 1. Prerequisites ──────────────────────────────────────────────────────────
def check_prerequisites(mock: bool) -> bool:
    header("Checking prerequisites")

    # Python version (the one running this script)
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 10):
        die(f"Python 3.10+ required — found {major}.{minor}\n"
            "   Download: https://python.org")
    ok(f"Python {major}.{minor}")

    # Node 18+
    node = shutil.which("node")
    if not node:
        die("node not found.\n   Install Node 18+ from https://nodejs.org")
    result = run(["node", "--version"], capture=True)
    node_ver = result.stdout.strip().lstrip("v")
    if int(node_ver.split(".")[0]) < 18:
        die(f"Node 18+ required — found {node_ver}")
    ok(f"Node v{node_ver}")

    # npm
    if not shutil.which("npm"):
        die("npm not found — it ships with Node.")
    result = run(["npm", "--version"], capture=True)
    ok(f"npm {result.stdout.strip()}")

    # Docker (full mode only) — check binary exists AND daemon is running
    needs_mock = mock
    if not mock:
        if not shutil.which("docker"):
            warn("Docker not found — switching to mock mode.")
            warn("Install Docker Desktop: https://www.docker.com/products/docker-desktop")
            needs_mock = True
        else:
            try:
                ping = subprocess.run(
                    ["docker", "info"], capture_output=True, text=True,
                    shell=IS_WIN, timeout=15,
                )
                docker_ok = ping.returncode == 0
            except subprocess.TimeoutExpired:
                docker_ok = False
            if not docker_ok:
                warn("Docker is installed but not running — switching to mock mode.")
                warn("Start Docker Desktop and re-run without --mock to use PostGIS.")
                needs_mock = True
            else:
                result = run(["docker", "--version"], capture=True)
                ok(result.stdout.strip())

    return needs_mock


# ── 2. .env file ──────────────────────────────────────────────────────────────
def setup_env():
    header("Environment file")
    env_file = ROOT / ".env"
    example  = ROOT / ".env.example"
    if not env_file.exists():
        shutil.copy(example, env_file)
        ok("Copied .env.example → .env")
        warn("Review .env and add ONEMAP_TOKEN if you have one (enables live routing).")
    else:
        ok(".env already exists — keeping it.")


# ── 3. Docker services ────────────────────────────────────────────────────────
def start_docker():
    header("Starting Docker services")
    run(["docker", "compose", "up", "-d", "db", "redis"], cwd=ROOT)

    info("Waiting for PostGIS…")
    for i in range(30):
        r = run(
            ["docker", "compose", "exec", "-T", "db",
             "pg_isready", "-U", "hdbmatch", "-d", "hdbmatch"],
            cwd=ROOT, check=False, capture=True
        )
        if r.returncode == 0:
            ok("PostGIS ready"); break
        if i == 29:
            die("PostGIS did not become ready.\n   Check: docker compose logs db")
        time.sleep(2)

    info("Waiting for Redis…")
    for i in range(15):
        r = run(
            ["docker", "compose", "exec", "-T", "redis", "redis-cli", "ping"],
            cwd=ROOT, check=False, capture=True
        )
        if "PONG" in r.stdout:
            ok("Redis ready"); break
        if i == 14:
            die("Redis did not become ready.\n   Check: docker compose logs redis")
        time.sleep(2)


# ── 4. Python venv ────────────────────────────────────────────────────────────
def setup_python():
    header("Python environment")
    venv_dir = BACKEND / ".venv"
    if not venv_dir.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)])
        ok("Created backend/.venv")
    else:
        ok("backend/.venv already exists — reusing.")

    info("Installing Python dependencies (this may take a minute)…")
    run([str(PYTHON), "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    run([str(PYTHON), "-m", "pip", "install", "--quiet", "-r", str(BACKEND / "requirements.txt")])
    ok("Python dependencies installed")


# ── 5. DB migrations + seed ───────────────────────────────────────────────────
def setup_database():
    header("Database setup")
    env = load_env()
    info("Running migrations…")
    run([str(PYTHON), "-m", "app.db.migrate"], cwd=BACKEND, env=env)
    ok("Migrations applied")

    if env.get("ONEMAP_TOKEN"):
        info("ONEMAP_TOKEN found — seeding with live HDB data (this takes a few minutes)…")
        run([str(PYTHON), "-m", "app.data.seed_live"], cwd=BACKEND, env=env)
        ok("Live data seeded")
    else:
        info("No ONEMAP_TOKEN — seeding with mock data. Add ONEMAP_TOKEN to .env for live data.")
        run([str(PYTHON), "-m", "app.data.seed"], cwd=BACKEND, env=env)
        ok("Mock data seeded")

    info("Seeding HDB Flat Portal active listings (bundled snapshot)…")
    run([str(PYTHON), "-m", "app.data.seed_listings"], cwd=BACKEND, env=env)
    ok("Active listings seeded (refresh anytime with `make listings-load`)")

    info("Syncing official bus stops and available route dataâ€¦")
    run([str(PYTHON), "-m", "app.data.sync_bus_network"], cwd=BACKEND, env=env)
    if env.get("LTA_DATAMALL_API_KEY"):
        ok("Bus stops and route sequences loaded")
    else:
        warn("Bus stops loaded; add LTA_DATAMALL_API_KEY for route reach overlays.")


# ── 6. Frontend ───────────────────────────────────────────────────────────────
def setup_frontend():
    header("Frontend")
    info("Installing npm packages (this may take a minute)…")
    run(["npm", "install", "--silent"], cwd=FRONTEND)
    ok("Frontend dependencies installed")


# ── 7. Summary banner ─────────────────────────────────────────────────────────
def print_summary(mock: bool):
    activate = (
        r"backend\.venv\Scripts\Activate.ps1" if IS_WIN
        else "source backend/.venv/bin/activate"
    )
    sep = _ansi("32", "=" * 54)
    print()
    print(sep)
    print(_ansi("32", "  Setup complete!"))
    print(sep)
    print(_ansi("32", "  To run manually -- open two terminals:"))
    print()
    print(_ansi("32", "  Terminal 1 (Backend):"))
    print(_ansi("32", f"    {activate}"))
    print(_ansi("32",  "    cd backend"))
    print(_ansi("32",  "    python -m app.run_server"))
    print()
    print(_ansi("32", "  Terminal 2 (Frontend):"))
    print(_ansi("32",  "    cd frontend && npm run dev"))
    print()
    if mock:
        print(_ansi("33", "  ! MOCK MODE -- no PostGIS. Install Docker for full DB."))
    print(_ansi("32", "  Frontend -> http://localhost:5173"))
    print(_ansi("32", "  API docs  -> http://localhost:8010/docs"))
    print(sep)


# ── 8. Auto-run ───────────────────────────────────────────────────────────────
def launch_servers():
    info("Launching backend and frontend… (Ctrl+C to stop both)")
    print()

    backend_cmd  = [str(PYTHON), "-m", "app.run_server"]
    frontend_cmd = ["npm", "run", "dev"]

    if IS_WIN:
        # Open separate windows on Windows so output is visible
        backend_proc = subprocess.Popen(
            ["powershell", "-NoExit", "-Command",
             f"cd '{BACKEND}'; & '{PYTHON}' -m app.run_server"],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        time.sleep(2)
        frontend_proc = subprocess.Popen(
            ["powershell", "-NoExit", "-Command",
             f"cd '{FRONTEND}'; npm run dev"],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    else:
        # Mac/Linux: stream both into current terminal
        backend_proc  = subprocess.Popen(backend_cmd,  cwd=BACKEND)
        time.sleep(2)
        frontend_proc = subprocess.Popen(frontend_cmd, cwd=FRONTEND)

    print(_ansi("32", f"  Backend  (PID {backend_proc.pid})  →  http://localhost:8010/docs"))
    print(_ansi("32", f"  Frontend (PID {frontend_proc.pid})  →  http://localhost:5173"))
    print()

    if IS_WIN:
        print(_ansi("33", "  Close the opened terminal windows to stop the servers."))
    else:
        print(_ansi("33", "  Press Ctrl+C to stop both servers."))
        try:
            backend_proc.wait()
            frontend_proc.wait()
        except KeyboardInterrupt:
            print()
            info("Stopping servers…")
            backend_proc.terminate()
            frontend_proc.terminate()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="HDB Match setup script")
    parser.add_argument("--mock", action="store_true",
                        help="Skip Docker/DB — use in-memory mock data")
    parser.add_argument("--run", action="store_true",
                        help="Launch both servers after setup")
    args = parser.parse_args()

    sep = _ansi("36", "=" * 44)
    print()
    print(sep)
    print(_ansi("36", "         HDB Match  --  Setup"))
    print(sep)
    if args.mock: print(_ansi("33", "  Mode: MOCK (no PostGIS / Docker needed)"))
    if args.run:  print(_ansi("32", "  Will launch servers after setup"))

    mock = check_prerequisites(args.mock)
    setup_env()
    if not mock:
        start_docker()
    setup_python()
    if not mock:
        setup_database()
    setup_frontend()
    print_summary(mock)

    if args.run:
        print()
        launch_servers()


if __name__ == "__main__":
    main()
