<#
.SYNOPSIS
  Stop every AshLight process on purpose: core, keepalive supervisor and
  overlay. Windows PowerShell 5.1 compatible.
.DESCRIPTION
  Writes ops\runtime\stop.request. The core sees it within a second and exits
  cleanly (it removes core.alive and its token); the keepalive supervisor
  sees a user stop and exits too. If the core has not exited after the
  timeout, its pid (from core.alive) is stopped, only when it is a python
  process; stop.request still marks it as a user stop. Then
  `python -m server.al.procs stop` stops the supervisor (forced only if it
  did not exit by itself) and the Electron overlay, by pids proven ours
  (OPS-STOP, decision 0010). scripts\run.ps1 removes stop.request on the
  next start. Exit 1 when anything is left running.
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
$rc = 0
if (-not (Test-Path -LiteralPath $alive)) {
    Write-AlLog 'stop: core stopped cleanly (keepalive will not restart it)'
} else {
    $proc = if ($corePid -gt 0) { Get-Process -Id $corePid -ErrorAction SilentlyContinue } else { $null }
    if ($null -eq $proc) {
        Write-AlLog 'stop: no core running (stale core.alive left in place)'
    } elseif ($proc.ProcessName -notlike 'python*') {
        Write-AlLog "stop: pid $corePid is not a python process; not touching it"
        $rc = 1
    } else {
        Stop-Process -Id $corePid -Force
        Write-AlLog "stop: core pid $corePid did not exit in $TimeoutSec s; stopped it (keepalive will not restart it)"
    }
}

# OPS-STOP: then the keepalive supervisor (it exits by itself on stop.request;
# forced after the wait) and the Electron overlay, each only by a pid proven
# ours (server\al\procs.py: recorded pid + creation time, or an electron.exe
# inside this checkout's app\node_modules). Never the game, never another app.
Push-Location $Repo
try {
    $out = (& $py -m server.al.procs stop --wait $TimeoutSec) -join "`n"
    $procRc = $LASTEXITCODE
} finally {
    Pop-Location
}
try {
    $report = $out | ConvertFrom-Json
    Write-AlLog ("stop: supervisor " + $report.supervisor + '; overlay ' + $report.overlay)
    if (@($report.left).Count -gt 0) {
        Write-AlLog ('stop: still running: ' + (@($report.left) -join ', '))
    }
} catch {
    Write-AlLog "stop: process registry gave no report: $out"
}
if ($procRc -ne 0) { $rc = 1 }
exit $rc
