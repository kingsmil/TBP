<#
.SYNOPSIS
  One-command local HTTPS deploy for HDB Match.

  Checks/installs the tools it needs (Caddy, cloudflared), starts the database,
  backend, and Caddy, then opens a Cloudflare tunnel — auto-selecting:
    * CF_TUNNEL_NAME set  -> named tunnel  (stable URL / your own domain)
    * not set             -> quick tunnel  (temporary *.trycloudflare.com URL)

.EXAMPLE
  ./deploy/serve.ps1            # deploy (install if needed) + open tunnel
  ./deploy/serve.ps1 -Stop      # stop backend + Caddy + tunnel
  ./deploy/serve.ps1 -Stop -StopDb   # also stop the database containers
  ./deploy/serve.ps1 -SkipBuild      # reuse the last frontend build
  ./deploy/serve.ps1 -NoInstall      # don't auto-install missing tools
#>
[CmdletBinding()]
param(
  [switch]$Stop,
  [switch]$StopDb,
  [switch]$SkipBuild,
  [switch]$NoInstall,
  [int]$CaddyPort = 0,
  [string]$TunnelName
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot      # deploy/ -> repo root
Set-Location $Root
$StateDir = Join-Path $Root "deploy/.run"
$PidFile = Join-Path $StateDir "pids.json"
$UrlFile = Join-Path $StateDir "url.txt"

function Read-DotEnv($path) {
  $h = @{}
  if (Test-Path $path) {
    foreach ($line in Get-Content $path) {
      $t = $line.Trim()
      if ($t -and -not $t.StartsWith('#') -and $t.Contains('=')) {
        $i = $t.IndexOf('='); $h[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim()
      }
    }
  }
  return $h
}

function Test-Port($p) {
  try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', $p); $c.Close(); $true }
  catch { $false }
}

function Get-PidOnPort($p) {
  try {
    (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue |
      Select-Object -First 1).OwningProcess
  }
  catch { $null }
}

function Get-TrackedAlive($name) {
  if (-not (Test-Path $PidFile)) { return $null }
  $s = Get-Content $PidFile -Raw | ConvertFrom-Json
  $procId = $s.$name
  if (-not $procId) { return $null }
  return Get-Process -Id ([int]$procId) -ErrorAction SilentlyContinue
}

function Refresh-Path {
  $m = [Environment]::GetEnvironmentVariable('Path', 'Machine')
  $u = [Environment]::GetEnvironmentVariable('Path', 'User')
  $env:Path = "$m;$u"
}

function Ensure-Tool($name, $wingetId) {
  if (Get-Command $name -ErrorAction SilentlyContinue) { return }
  if ($NoInstall) { throw "'$name' not found and -NoInstall set. Install it and retry." }
  Write-Host "> Installing $name..." -ForegroundColor Cyan
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id $wingetId -e --accept-source-agreements --accept-package-agreements --silent
  }
  elseif (Get-Command choco -ErrorAction SilentlyContinue) {
    choco install $name -y
  }
  elseif (Get-Command scoop -ErrorAction SilentlyContinue) {
    scoop install $name
  }
  else {
    throw "No package manager (winget/choco/scoop) found. Install $name manually."
  }
  Refresh-Path
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "$name still not on PATH after install. Open a NEW terminal and re-run."
  }
}

function Save-Pids($map) {
  New-Item -ItemType Directory -Force $StateDir | Out-Null
  ($map | ConvertTo-Json) | Set-Content -Encoding utf8 $PidFile
}

function Stop-AppProcesses {
  if (Test-Path $PidFile) {
    $s = Get-Content $PidFile -Raw | ConvertFrom-Json
    foreach ($prop in $s.PSObject.Properties) {
      try { Stop-Process -Id ([int]$prop.Value) -Force -ErrorAction SilentlyContinue } catch {}
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
  }
}

# ── Stop mode ─────────────────────────────────────────────────────────────────
if ($Stop -or $StopDb) {
  Write-Host "> Stopping backend, Caddy and tunnel..." -ForegroundColor Cyan
  Stop-AppProcesses
  if ($StopDb) {
    Write-Host "> Stopping database containers..." -ForegroundColor Cyan
    docker compose stop db redis
  }
  Write-Host "> Stopped." -ForegroundColor Green
  return
}

# ── Resolve config ────────────────────────────────────────────────────────────
$envv = Read-DotEnv (Join-Path $Root ".env")
if (-not $TunnelName) { $TunnelName = $env:CF_TUNNEL_NAME }
if (-not $TunnelName) { $TunnelName = $envv['CF_TUNNEL_NAME'] }
$tunnelHost = if ($env:CF_TUNNEL_HOSTNAME) { $env:CF_TUNNEL_HOSTNAME } else { $envv['CF_TUNNEL_HOSTNAME'] }
$apiPort = if ($envv['API_PORT']) { $envv['API_PORT'] } else { '8010' }
if ($CaddyPort -le 0) { $CaddyPort = if ($envv['CADDY_PORT']) { [int]$envv['CADDY_PORT'] } else { 8080 } }
$env:CADDY_PORT = "$CaddyPort"   # consumed by deploy/Caddyfile

# ── Fully healthy already? Short-circuit. ─────────────────────────────────────
# Only when the tunnel, backend AND Caddy are all up — otherwise fall through and
# (re)start whatever is down, so a dead backend self-heals instead of leaving a
# tunnel that 502s on every /api call.
$liveTunnel = Get-TrackedAlive 'cloudflared'
if ($liveTunnel -and (Test-Port $apiPort) -and (Test-Port $CaddyPort)) {
  $u = if (Test-Path $UrlFile) { (Get-Content $UrlFile -Raw).Trim() } else { '(see deploy/.run/url.txt)' }
  Write-Host "> Already running and healthy (tunnel PID $($liveTunnel.Id))." -ForegroundColor Yellow
  Write-Host "  PUBLIC URL : $u" -ForegroundColor Green
  Write-Host "  LOCAL      : http://localhost:$CaddyPort" -ForegroundColor DarkGray
  Write-Host "  Run ./deploy/stop.ps1 first if you want to restart." -ForegroundColor DarkGray
  return
}

# ── Ensure tools ──────────────────────────────────────────────────────────────
Ensure-Tool caddy CaddyServer.Caddy
Ensure-Tool cloudflared Cloudflare.cloudflared

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker not found. Install Docker Desktop, start it, then re-run."
}
docker info | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Docker isn't running. Start Docker Desktop and re-run." }

Write-Host "> Starting database (db, redis)..." -ForegroundColor Cyan
docker compose up -d db redis | Out-Null

$started = @{}
try {
  # 1. Frontend build.
  if (-not ($SkipBuild -and (Test-Path "$Root/frontend/dist/index.html"))) {
    Write-Host "> Building frontend..." -ForegroundColor Cyan
    Push-Location "$Root/frontend"; npm run build; Pop-Location
  }

  # 2. Backend (reused if its port is up; tracked either way so -Stop is clean).
  if (Test-Port $apiPort) {
    Write-Host "> Backend already on :$apiPort - reusing it." -ForegroundColor DarkGray
    $bpid = Get-PidOnPort $apiPort
    if ($bpid) { $started.backend = $bpid }
  }
  else {
    Write-Host "> Starting backend on :$apiPort..." -ForegroundColor Cyan
    $py = "$Root/backend/.venv/Scripts/python.exe"
    if (-not (Test-Path $py)) { $py = 'python' }
    $p = Start-Process -FilePath $py -ArgumentList '-m', 'app.run_server' `
      -WorkingDirectory "$Root/backend" -WindowStyle Minimized -PassThru
    $started.backend = $p.Id
  }

  # Wait for the backend to actually accept connections (so a silent crash is
  # reported instead of surfacing later as a 502 from Caddy).
  if (-not (Test-Port $apiPort)) {
    Write-Host "> Waiting for backend on :$apiPort..." -ForegroundColor DarkGray
    $bd = (Get-Date).AddSeconds(20)
    while (-not (Test-Port $apiPort) -and (Get-Date) -lt $bd) { Start-Sleep -Milliseconds 500 }
  }
  if (-not (Test-Port $apiPort)) {
    Write-Host "! Backend did NOT come up on :$apiPort - /api calls will 502." -ForegroundColor Red
    Write-Host "  Check the minimized backend window, or run it directly to see the error:" -ForegroundColor Red
    Write-Host "    cd backend; .\.venv\Scripts\python.exe -m app.run_server" -ForegroundColor Red
  }

  # 3. Caddy.
  if (Test-Port $CaddyPort) {
    Write-Host "> Caddy port :$CaddyPort already in use - reusing it." -ForegroundColor DarkGray
    $cpid = Get-PidOnPort $CaddyPort
    if ($cpid) { $started.caddy = $cpid }
  }
  else {
    Write-Host "> Starting Caddy on :$CaddyPort..." -ForegroundColor Cyan
    $p = Start-Process -FilePath 'caddy' -ArgumentList 'run', '--config', 'deploy/Caddyfile' `
      -WorkingDirectory $Root -WindowStyle Minimized -PassThru
    $started.caddy = $p.Id
  }
  Save-Pids $started
  Start-Sleep -Seconds 3
  Write-Host "> Local app: http://localhost:$CaddyPort" -ForegroundColor DarkGray

  # 4. Tunnel. Reuse an existing live tunnel (e.g. we only restarted a dead
  # backend); otherwise start a fresh one. PID tracked for -Stop.
  $log = Join-Path $StateDir "cloudflared.log"
  $publicUrl = $null

  if ($liveTunnel) {
    Write-Host "> Tunnel already running (PID $($liveTunnel.Id)) - reusing it." -ForegroundColor DarkGray
    $cf = $liveTunnel
    $started.cloudflared = $cf.Id
    if (Test-Path $UrlFile) { $publicUrl = (Get-Content $UrlFile -Raw).Trim() }
  }
  else {
    Remove-Item $log, $UrlFile -Force -ErrorAction SilentlyContinue
    if ($TunnelName) {
      $cf = Start-Process -FilePath 'cloudflared' -ArgumentList 'tunnel', 'run', $TunnelName `
        -NoNewWindow -PassThru
      if ($tunnelHost) { $publicUrl = "https://$tunnelHost" }
    }
    else {
      Write-Host "> Opening a temporary quick tunnel..." -ForegroundColor Yellow
      $cf = Start-Process -FilePath 'cloudflared' `
        -ArgumentList 'tunnel', '--url', "http://localhost:$CaddyPort", '--logfile', $log `
        -NoNewWindow -PassThru
      $deadline = (Get-Date).AddSeconds(30)
      while (-not $publicUrl -and (Get-Date) -lt $deadline -and -not $cf.HasExited) {
        Start-Sleep -Milliseconds 500
        if (Test-Path $log) {
          $hit = Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' `
            -ErrorAction SilentlyContinue | Select-Object -First 1
          if ($hit) { $publicUrl = $hit.Matches[0].Value }
        }
      }
    }
    $started.cloudflared = $cf.Id
    if ($publicUrl) { Set-Content -Encoding ascii $UrlFile $publicUrl }
  }
  Save-Pids $started

  Write-Host ""
  Write-Host "  ============================================================" -ForegroundColor Green
  if ($publicUrl) {
    Write-Host "   PUBLIC URL : $publicUrl" -ForegroundColor Green
  }
  else {
    Write-Host "   Tunnel starting - see the cloudflared output for the URL." -ForegroundColor Yellow
  }
  Write-Host "   LOCAL      : http://localhost:$CaddyPort" -ForegroundColor DarkGray
  Write-Host "   (also saved to deploy/.run/url.txt)" -ForegroundColor DarkGray
  Write-Host "  ============================================================" -ForegroundColor Green
  Write-Host "  Press Ctrl+C to stop (or run: ./deploy/stop.ps1)." -ForegroundColor DarkGray
  Wait-Process -Id $cf.Id
}
finally {
  Write-Host "`n> Shutting down services this script started..." -ForegroundColor Cyan
  Stop-AppProcesses
}
