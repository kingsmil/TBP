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

  # 2. Backend.
  if (Test-Port $apiPort) {
    Write-Host "> Backend already on :$apiPort - reusing it." -ForegroundColor DarkGray
  }
  else {
    Write-Host "> Starting backend on :$apiPort..." -ForegroundColor Cyan
    $py = "$Root/backend/.venv/Scripts/python.exe"
    if (-not (Test-Path $py)) { $py = 'python' }
    $p = Start-Process -FilePath $py -ArgumentList '-m', 'app.run_server' `
      -WorkingDirectory "$Root/backend" -WindowStyle Minimized -PassThru
    $started.backend = $p.Id
  }

  # 3. Caddy.
  if (Test-Port $CaddyPort) {
    Write-Host "> Caddy port :$CaddyPort already in use - reusing it." -ForegroundColor DarkGray
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

  # 4. Tunnel (shares this console so the URL is visible; PID tracked for -Stop).
  if ($TunnelName) {
    $dest = if ($tunnelHost) { " -> https://$tunnelHost" } else { "" }
    Write-Host "> Stable tunnel '$TunnelName'$dest" -ForegroundColor Green
    $cf = Start-Process -FilePath 'cloudflared' -ArgumentList 'tunnel', 'run', $TunnelName `
      -NoNewWindow -PassThru
  }
  else {
    Write-Host "> No CF_TUNNEL_NAME set - opening a temporary quick tunnel." -ForegroundColor Yellow
    Write-Host "  Watch for the https://*.trycloudflare.com URL below." -ForegroundColor DarkGray
    $cf = Start-Process -FilePath 'cloudflared' -ArgumentList 'tunnel', '--url', "http://localhost:$CaddyPort" `
      -NoNewWindow -PassThru
  }
  $started.cloudflared = $cf.Id
  Save-Pids $started
  Write-Host "> Press Ctrl+C to stop (or run: ./deploy/serve.ps1 -Stop)." -ForegroundColor DarkGray
  Wait-Process -Id $cf.Id
}
finally {
  Write-Host "`n> Shutting down services this script started..." -ForegroundColor Cyan
  Stop-AppProcesses
}
