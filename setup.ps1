# HDB Match — Windows setup script (PowerShell)
#
# Usage:
#   .\setup.ps1              # full setup (requires Docker for PostGIS)
#   .\setup.ps1 -Mock        # skip Docker/DB — in-memory mock data
#   .\setup.ps1 -Run         # setup + launch both servers
#   .\setup.ps1 -Mock -Run   # mock mode + launch
param(
  [switch]$Mock,
  [switch]$Run
)
$ErrorActionPreference = "Stop"

function ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function info($msg) { Write-Host "  --> $msg"  -ForegroundColor Cyan }
function warn($msg) { Write-Host "  [!] $msg"  -ForegroundColor Yellow }
function die($msg)  { Write-Host "  [X] $msg"  -ForegroundColor Red; exit 1 }

function header($msg) {
  Write-Host ""
  Write-Host "── $msg " -ForegroundColor Cyan -NoNewline
  Write-Host ("─" * [Math]::Max(0, 50 - $msg.Length)) -ForegroundColor Cyan
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          HDB Match  —  Setup             ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
if ($Mock) { Write-Host "  Mode: MOCK (no PostGIS / Docker needed)"  -ForegroundColor Yellow }
if ($Run)  { Write-Host "  Will launch servers after setup"          -ForegroundColor Green }
Write-Host ""

# ─── 1. Prerequisites ────────────────────────────────────────────────────────
header "Checking prerequisites"

# Python 3.10+
try { $pyVer = & python --version 2>&1 } catch { die "python not found.`n   Install Python 3.10+ from https://python.org" }
if ($pyVer -match "Python (\d+)\.(\d+)") {
  $major = [int]$Matches[1]; $minor = [int]$Matches[2]
  if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
    die "Python 3.10+ required — found $pyVer"
  }
  ok $pyVer
} else { die "Could not parse Python version: $pyVer" }

# Node 18+
try { $nodeVer = & node --version 2>&1 } catch { die "node not found.`n   Install Node 18+ from https://nodejs.org" }
if ($nodeVer -match "v(\d+)") {
  if ([int]$Matches[1] -lt 18) { die "Node 18+ required — found $nodeVer" }
  ok "Node $nodeVer"
} else { die "Could not parse Node version: $nodeVer" }

# npm
try { $npmVer = & npm --version 2>&1; ok "npm $npmVer" } catch { die "npm not found — it ships with Node." }

# Docker (full mode only)
if (-not $Mock) {
  try {
    $dockerVer = & docker --version 2>&1
    ok $dockerVer
  } catch {
    warn "Docker not found — switching to mock mode."
    warn "Install Docker Desktop to enable PostGIS features."
    $Mock = $true
  }
}

# ─── 2. Environment file ─────────────────────────────────────────────────────
header "Environment file"
if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  ok "Copied .env.example → .env"
  warn "Review .env and add ONEMAP_TOKEN if you have one."
} else {
  ok ".env already exists — keeping it."
}

# ─── 3. Docker services ──────────────────────────────────────────────────────
if (-not $Mock) {
  header "Starting Docker services"
  & docker compose up -d db redis

  info "Waiting for PostGIS…"
  $ready = $false
  for ($i = 1; $i -le 30; $i++) {
    $result = & docker compose exec -T db pg_isready -U hdbmatch -d hdbmatch 2>&1
    if ($LASTEXITCODE -eq 0) { ok "PostGIS ready"; $ready = $true; break }
    Start-Sleep 2
  }
  if (-not $ready) { die "PostGIS did not become ready. Check: docker compose logs db" }

  info "Waiting for Redis…"
  $ready = $false
  for ($i = 1; $i -le 15; $i++) {
    $result = & docker compose exec -T redis redis-cli ping 2>&1
    if ($result -match "PONG") { ok "Redis ready"; $ready = $true; break }
    Start-Sleep 2
  }
  if (-not $ready) { die "Redis did not become ready. Check: docker compose logs redis" }
}

# ─── 4. Python virtual environment ───────────────────────────────────────────
header "Python environment"
$venvActivate = "backend\.venv\Scripts\Activate.ps1"

if (-not (Test-Path "backend\.venv")) {
  & python -m venv backend\.venv
  ok "Created backend\.venv"
} else {
  ok "backend\.venv already exists — reusing."
}

. $venvActivate
info "Installing Python dependencies (this may take a minute)…"
& pip install --quiet --upgrade pip
& pip install --quiet -r backend\requirements.txt
ok "Python dependencies installed"
deactivate

# ─── 5. Database migrations + seed ──────────────────────────────────────────
if (-not $Mock) {
  header "Database setup"
  . $venvActivate

  info "Running migrations…"
  Push-Location backend; & python -m app.db.migrate; Pop-Location
  ok "Migrations applied"

  info "Seeding sample data…"
  Push-Location backend; & python -m app.data.seed; Pop-Location
  ok "Sample data loaded"

  deactivate
}

# ─── 6. Frontend dependencies ────────────────────────────────────────────────
header "Frontend"
info "Installing npm packages (this may take a minute)…"
Push-Location frontend; & npm install --silent; Pop-Location
ok "Frontend dependencies installed"

# ─── 7. Done ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  Setup complete!                                     ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  To run manually — open two terminals:               ║" -ForegroundColor Green
Write-Host "║                                                      ║" -ForegroundColor Green
Write-Host "║  Terminal 1 (Backend):                               ║" -ForegroundColor Green
Write-Host "║    . backend\.venv\Scripts\Activate.ps1              ║" -ForegroundColor Green
Write-Host "║    cd backend                                        ║" -ForegroundColor Green
Write-Host "║    python -m app.run_server                         ║" -ForegroundColor Green
Write-Host "║                                                      ║" -ForegroundColor Green
Write-Host "║  Terminal 2 (Frontend):                              ║" -ForegroundColor Green
Write-Host "║    cd frontend && npm run dev                        ║" -ForegroundColor Green
Write-Host "║                                                      ║" -ForegroundColor Green
if ($Mock) {
  Write-Host "║  [!] MOCK MODE — no PostGIS. Install Docker for DB.  ║" -ForegroundColor Yellow
}
Write-Host "║  Frontend → http://localhost:5173                    ║" -ForegroundColor Green
Write-Host "║  API docs  → http://localhost:8010/docs              ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Green

# ─── 8. Auto-run ─────────────────────────────────────────────────────────────
if ($Run) {
  Write-Host ""
  info "Launching backend and frontend… (Ctrl+C to stop both)"
  Write-Host ""

  . $venvActivate

  # Backend in a new window
  $backendCmd = "cd '$PWD\backend'; python -m app.run_server"
  $backendWindow = Start-Process powershell -ArgumentList "-NoExit", "-Command", ". '$PWD\$venvActivate'; $backendCmd" -PassThru

  Start-Sleep 2

  # Frontend in another new window
  $frontendCmd = "cd '$PWD\frontend'; npm run dev"
  $frontendWindow = Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -PassThru

  Write-Host "  Backend  (PID $($backendWindow.Id))  →  http://localhost:8010/docs" -ForegroundColor Green
  Write-Host "  Frontend (PID $($frontendWindow.Id))  →  http://localhost:5173"      -ForegroundColor Green
  Write-Host ""
  Write-Host "  Close the opened terminal windows to stop the servers." -ForegroundColor Yellow
}
