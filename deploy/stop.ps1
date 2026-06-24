<#
.SYNOPSIS
  Stop the local HTTPS deploy started by deploy/serve.ps1.

.EXAMPLE
  ./deploy/stop.ps1            # stop backend + Caddy + tunnel
  ./deploy/stop.ps1 -StopDb    # also stop the database containers
#>
[CmdletBinding()]
param([switch]$StopDb)
& (Join-Path $PSScriptRoot "serve.ps1") -Stop -StopDb:$StopDb
