<#
.SYNOPSIS
  Stop AshLight on purpose (the keepalive supervisor will NOT restart it).
  Windows PowerShell 5.1 compatible.
.DESCRIPTION
  Writes ops\runtime\stop.request. The core sees it within a second and exits
  cleanly (it removes core.alive and its token); the keepalive supervisor
  sees a user stop and exits too. If the core has not exited after the
  timeout, its pid (from core.alive) is stopped, only when it is a python
  process; stop.request still marks it as a user stop. scripts\run.ps1
  removes stop.request on the next start.
.PARAMETER TimeoutSec
  How long to wait for the clean exit before forcing it.
#>
[CmdletBinding()]
param(
    [int]$TimeoutSec = 15
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$Repo = Split-Path -Parent $PSScriptRoot

function Get-AlPython {
    foreach ($name in @('python', 'py')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    throw 'Python 3.11 or newer was not found on PATH.'
}

$py = Get-AlPython
Push-Location $Repo
try {
    $paths = ((& $py -m server.al.paths) -join "`n") | ConvertFrom-Json
} finally {
    Pop-Location
}
New-Item -ItemType Directory -Force -Path $paths.runtime, $paths.logs | Out-Null
$log = Join-Path $paths.logs 'run.log'
$alive = Join-Path $paths.runtime 'core.alive'
$request = Join-Path $paths.runtime 'stop.request'

function Write-AlLog([string]$Message) {
    $line = (Get-Date -Format 's') + ' ' + $Message
    Add-Content -Path $log -Value $line -Encoding ASCII
    Write-Host $Message
}

function Get-AlCorePid {
    if (-not (Test-Path -LiteralPath $alive)) { return 0 }
    try {
        return [int]((Get-Content -LiteralPath $alive -Raw | ConvertFrom-Json).pid)
    } catch {
        return 0
    }
}

Set-Content -LiteralPath $request -Value 'stop' -Encoding ASCII
$corePid = Get-AlCorePid
$deadline = (Get-Date).AddSeconds($TimeoutSec)
while ((Test-Path -LiteralPath $alive) -and ((Get-Date) -lt $deadline)) {
    Start-Sleep -Milliseconds 250
}
if (-not (Test-Path -LiteralPath $alive)) {
    Write-AlLog 'stop: core stopped cleanly (keepalive will not restart it)'
    exit 0
}
$proc = if ($corePid -gt 0) { Get-Process -Id $corePid -ErrorAction SilentlyContinue } else { $null }
if ($null -eq $proc) {
    Write-AlLog 'stop: no core running (stale core.alive left in place)'
    exit 0
}
if ($proc.ProcessName -notlike 'python*') {
    Write-AlLog "stop: pid $corePid is not a python process; not touching it"
    exit 1
}
Stop-Process -Id $corePid -Force
Write-AlLog "stop: core pid $corePid did not exit in $TimeoutSec s; stopped it (keepalive will not restart it)"
exit 0
