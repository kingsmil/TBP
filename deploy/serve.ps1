<#
.SYNOPSIS
  Run HDB Match locally and expose it over HTTPS through Cloudflare.

  Auto-selects the tunnel:
    * CF_TUNNEL_NAME set  -> named tunnel  (stable URL / your own domain)
    * not set             -> quick tunnel  (temporary *.trycloudflare.com URL)

  Brings up the backend + Caddy (frontend + /api) and runs the tunnel in the
  foreground. Ctrl+C stops everything it started.

.EXAMPLE
  ./deploy/serve.ps1                 # quick tunnel (or stable if CF_TUNNEL_NAME in .env)
  ./deploy/serve.ps1 -SkipBuild      # reuse the existing frontend build
  ./deploy/serve.ps1 -TunnelName hdb # force a named tunnel
#>
[CmdletBinding()]
param(
  [switch]$SkipBuild,
  [int]$CaddyPort = 0,
  [string]$TunnelName
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot      # deploy/ -> repo root
Set-Location $Root

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

function Require-Tool($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "'$name' not found on PATH. Install it (see deploy/local-https-tunnel.md) and retry."
  }
}

$envv = Read-DotEnv (Join-Path $Root ".env")
if (-not $TunnelName) { $TunnelName = $env:CF_TUNNEL_NAME }
if (-not $TunnelName) { $TunnelName = $envv['CF_TUNNEL_NAME'] }
$tunnelHost = if ($env:CF_TUNNEL_HOSTNAME) { $env:CF_TUNNEL_HOSTNAME } else { $envv['CF_TUNNEL_HOSTNAME'] }
$apiPort = if ($envv['API_PORT']) { $envv['API_PORT'] } else { '8010' }
if ($CaddyPort -le 0) { $CaddyPort = if ($envv['CADDY_PORT']) { [int]$envv['CADDY_PORT'] } else { 8080 } }
$env:CADDY_PORT = "$CaddyPort"   # consumed by deploy/Caddyfile

Require-Tool caddy
Require-Tool cloudflared

$started = @()
function Stop-Started {
  foreach ($p in $started) {
    if ($p -and -not $p.HasExited) {
      try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {}
    }
  }
}

try {
  # 1. Frontend build (skip if up to date / -SkipBuild and dist exists).
  if (-not ($SkipBuild -and (Test-Path "$Root/frontend/dist/index.html"))) {
    Write-Host "> Building frontend..." -ForegroundColor Cyan
    Push-Location "$Root/frontend"; npm run build; Pop-Location
  }

  # 2. Backend (skip if something is already on the API port).
  if (Test-Port $apiPort) {
    Write-Host "> Backend already listening on :$apiPort - reusing it." -ForegroundColor DarkGray
  }
  else {
    Write-Host "> Starting backend on :$apiPort..." -ForegroundColor Cyan
    $py = "$Root/backend/.venv/Scripts/python.exe"
    if (-not (Test-Path $py)) { $py = 'python' }
    $started += Start-Process -FilePath $py -ArgumentList '-m', 'app.run_server' `
      -WorkingDirectory "$Root/backend" -WindowStyle Minimized -PassThru
  }

  # 3. Caddy (frontend + /api on one port).
  if (Test-Port $CaddyPort) {
    Write-Host "> Caddy port :$CaddyPort already in use - reusing it." -ForegroundColor DarkGray
  }
  else {
    Write-Host "> Starting Caddy on :$CaddyPort..." -ForegroundColor Cyan
    $started += Start-Process -FilePath 'caddy' -ArgumentList 'run', '--config', 'deploy/Caddyfile' `
      -WorkingDirectory $Root -WindowStyle Minimized -PassThru
  }

  Start-Sleep -Seconds 3
  Write-Host "> Local app: http://localhost:$CaddyPort" -ForegroundColor DarkGray

  # 4. Tunnel - stable if configured, otherwise a quick tunnel.
  if ($TunnelName) {
    $dest = if ($tunnelHost) { " -> https://$tunnelHost" } else { "" }
    Write-Host "> Stable tunnel '$TunnelName'$dest" -ForegroundColor Green
    Write-Host "  (uses your cloudflared named-tunnel config; see the runbook for setup)" -ForegroundColor DarkGray
    cloudflared tunnel run $TunnelName
  }
  else {
    Write-Host "> No CF_TUNNEL_NAME set - opening a temporary quick tunnel." -ForegroundColor Yellow
    Write-Host "  Watch for the printed https://*.trycloudflare.com URL below." -ForegroundColor DarkGray
    cloudflared tunnel --url "http://localhost:$CaddyPort"
  }
}
finally {
  Write-Host "`n> Shutting down services this script started..." -ForegroundColor Cyan
  Stop-Started
}
