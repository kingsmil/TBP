#!/usr/bin/env bash
# HDB Match — one-shot setup (and optional run) script
#
# Usage:
#   bash setup.sh              # full setup (requires Docker for PostGIS)
#   bash setup.sh --mock       # skip Docker/DB — runs with in-memory mock data
#   bash setup.sh --run        # setup + immediately launch both servers
#   bash setup.sh --mock --run # mock mode + launch
set -euo pipefail

# ─── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC}  $*"; }
info() { echo -e "${CYAN}→${NC}  $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
die()  { echo -e "${RED}✗  $*${NC}" >&2; exit 1; }
header() {
  echo ""
  echo -e "${CYAN}${BOLD}── $* ────────────────────────────────────────────${NC}"
}

MOCK_MODE=false
RUN_MODE=false
for arg in "$@"; do
  [[ "$arg" == "--mock" ]] && MOCK_MODE=true
  [[ "$arg" == "--run"  ]] && RUN_MODE=true
done

# Detect OS for venv activation path
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  VENV_ACTIVATE="backend/.venv/Scripts/activate"
else
  VENV_ACTIVATE="backend/.venv/bin/activate"
fi

echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║          HDB Match  —  Setup             ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════╝${NC}"
[[ "$MOCK_MODE" == true ]] && echo -e "${YELLOW}  Mode: MOCK (no PostGIS / Docker needed)${NC}"
[[ "$RUN_MODE"  == true ]] && echo -e "${GREEN}  Will launch servers after setup${NC}"
echo ""

# ─── 1. Prerequisites ─────────────────────────────────────────────────────────
header "Checking prerequisites"

# Python 3.10+
if ! command -v python3 &>/dev/null; then
  die "python3 not found.\n   Install Python 3.10+ from https://python.org and re-run."
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [[ $PY_MAJOR -lt 3 ]] || { [[ $PY_MAJOR -eq 3 ]] && [[ $PY_MINOR -lt 10 ]]; }; then
  die "Python 3.10+ required — found $PY_VER.\n   Download: https://python.org"
fi
ok "Python $PY_VER"

# Node 18+
if ! command -v node &>/dev/null; then
  die "node not found.\n   Install Node 18+ from https://nodejs.org and re-run."
fi
NODE_VER=$(node --version | sed 's/v//' | cut -d. -f1)
if [[ $NODE_VER -lt 18 ]]; then
  die "Node 18+ required — found $(node --version).\n   Download: https://nodejs.org"
fi
ok "Node $(node --version)"

# npm
command -v npm &>/dev/null || die "npm not found — it usually ships with Node."
ok "npm $(npm --version)"

# Docker (only needed in full mode)
if [[ "$MOCK_MODE" == false ]]; then
  if ! command -v docker &>/dev/null; then
    warn "Docker not found — switching to mock mode (no PostGIS)."
    warn "Install Docker Desktop to enable full DB features."
    MOCK_MODE=true
  else
    ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
  fi
fi

# ─── 2. Environment file ──────────────────────────────────────────────────────
header "Environment file"
if [[ ! -f .env ]]; then
  cp .env.example .env
  ok "Copied .env.example → .env"
  warn "Review .env and add ONEMAP_TOKEN if you have one (enables live routing)."
else
  ok ".env already exists — keeping it."
fi

# ─── 3. Docker services (full mode only) ─────────────────────────────────────
if [[ "$MOCK_MODE" == false ]]; then
  header "Starting Docker services"
  docker compose up -d db redis

  info "Waiting for PostGIS…"
  for i in $(seq 1 30); do
    if docker compose exec -T db pg_isready -U hdbmatch -d hdbmatch &>/dev/null; then
      ok "PostGIS ready"; break
    fi
    [[ $i -eq 30 ]] && die "PostGIS did not become ready in 60s. Check: docker compose logs db"
    sleep 2
  done

  info "Waiting for Redis…"
  for i in $(seq 1 15); do
    if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
      ok "Redis ready"; break
    fi
    [[ $i -eq 15 ]] && die "Redis did not become ready. Check: docker compose logs redis"
    sleep 2
  done
fi

# ─── 4. Python virtual environment ───────────────────────────────────────────
header "Python environment"

if [[ ! -d backend/.venv ]]; then
  python3 -m venv backend/.venv
  ok "Created backend/.venv"
else
  ok "backend/.venv already exists — reusing."
fi

# shellcheck disable=SC1090
source "$VENV_ACTIVATE"
info "Installing Python dependencies (this may take a minute)…"
pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements.txt
ok "Python dependencies installed"
deactivate

# ─── 5. Database migrations + seed (full mode only) ──────────────────────────
if [[ "$MOCK_MODE" == false ]]; then
  header "Database setup"
  source "$VENV_ACTIVATE"

  info "Running migrations…"
  (cd backend && python -m app.db.migrate)
  ok "Migrations applied"

  info "Seeding sample data…"
  (cd backend && python -m app.data.seed)
  ok "Sample data loaded"

  deactivate
fi

# ─── 6. Frontend dependencies ─────────────────────────────────────────────────
header "Frontend"
info "Installing npm packages (this may take a minute)…"
(cd frontend && npm install --silent)
ok "Frontend dependencies installed"

# ─── 7. Done ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║  ✓  Setup complete!                                  ║${NC}"
echo -e "${GREEN}${BOLD}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}${BOLD}║                                                      ║${NC}"
echo -e "${GREEN}${BOLD}║  To run manually — open two terminals:               ║${NC}"
echo -e "${GREEN}${BOLD}║                                                      ║${NC}"
echo -e "${GREEN}${BOLD}║  Terminal 1 (Backend):                               ║${NC}"
echo -e "${GREEN}  source ${VENV_ACTIVATE}${NC}"
echo -e "${GREEN}  cd backend && python -m app.run_server${NC}"
echo -e "${GREEN}${BOLD}║                                                      ║${NC}"
echo -e "${GREEN}${BOLD}║  Terminal 2 (Frontend):                              ║${NC}"
echo -e "${GREEN}  cd frontend && npm run dev${NC}"
echo -e "${GREEN}${BOLD}║                                                      ║${NC}"
[[ "$MOCK_MODE" == true ]] && \
echo -e "${YELLOW}  ⚠  MOCK MODE — no PostGIS. Install Docker for full DB.  ${NC}"
echo -e "${GREEN}${BOLD}║                                                      ║${NC}"
echo -e "${GREEN}${BOLD}║  Frontend → http://localhost:5173                    ║${NC}"
echo -e "${GREEN}${BOLD}║  API docs  → http://localhost:8010/docs              ║${NC}"
echo -e "${GREEN}${BOLD}║                                                      ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════╝${NC}"

# ─── 8. Auto-run (--run flag) ────────────────────────────────────────────────
if [[ "$RUN_MODE" == true ]]; then
  echo ""
  info "Launching backend and frontend…"
  info "Press Ctrl+C to stop both servers."
  echo ""

  # Start backend in background
  # shellcheck disable=SC1090
  source "$VENV_ACTIVATE"
  MOCK_ARG=""
  [[ "$MOCK_MODE" == true ]] && MOCK_ARG="--env-file /dev/null"
  (cd backend && python -m app.run_server) &
  BACKEND_PID=$!

  # Give backend a moment to start
  sleep 2

  # Start frontend in foreground (so Ctrl+C lands here first)
  (cd frontend && npm run dev) &
  FRONTEND_PID=$!

  echo ""
  echo -e "${GREEN}  Backend  PID ${BACKEND_PID}  →  http://localhost:8010/docs${NC}"
  echo -e "${GREEN}  Frontend PID ${FRONTEND_PID}  →  http://localhost:5173${NC}"
  echo ""

  # Wait for either process; kill both on exit
  trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM EXIT
  wait $BACKEND_PID $FRONTEND_PID
fi
