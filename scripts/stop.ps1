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
# REL-RUNTIME-SCRIPTS: Python and the paths from scripts\al_env.ps1 only
# (the private runtime in an installed copy, PATH Python in a checkout).
. (Join-Path $PSScriptRoot 'al_env.ps1')

$paths = Get-AlPaths
New-Item -ItemType Directory -Force -Path $paths.runtime, $paths.logs | Out-Null
$log = Join-Path $paths.logs 'run.log'
$alive = Join-Path $paths.runtime 'core.alive'
$request = Join-Path $paths.runtime 'stop.request'

# RUN-OBS-LOGS-SHELL (F-090): run.log in the one line format of AshLight's
# logs (server\al\logs.py), as scripts\run.ps1 writes it: over 1 MB at
# start it moves to run.log.1 (one old file kept; a failed move keeps
# appending), every line is '<UTC ISO stamp> <LEVEL> stop[<pid>] <message>'
# and each start opens with the build banner.
function Write-AlLog([string]$Message, [string]$Level = 'INFO') {
    $stamp = [DateTime]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'",
        [System.Globalization.CultureInfo]::InvariantCulture)
    $line = $stamp + ' ' + $Level + ' stop[' + $PID + '] ' + $Message
    Add-Content -Path $log -Value $line -Encoding ASCII
    Write-Host $Message
}

function Get-AlBuildId {
    $ErrorActionPreference = 'Continue'
    $b = ''
    $py = Get-AlPython
    Push-Location -LiteralPath $AlEnvRoot
    try {
        $b = ((& $py -c "import sys; sys.path.insert(0, sys.argv[1]); from server.al import buildinfo; print(buildinfo.build_id())" $AlEnvRoot 2>$null) -join '').Trim()
    } catch {
        $b = ''
    } finally {
        Pop-Location
    }
    if ($b -match '^[0-9A-Za-z.+-]{1,64}$') { return $b }
    return 'unknown'
}

function Start-AlStopLog([string]$Build) {
    $old = $log + '.1'
    try {
        if ((Test-Path -LiteralPath $log -PathType Leaf) -and ((Get-Item -LiteralPath $log).Length -gt 1048576)) {
            if (Test-Path -LiteralPath $old -PathType Leaf) {
                [System.IO.File]::Replace($log, $old, [NullString]::Value)
            } else {
                [System.IO.File]::Move($log, $old)
            }
        }
    } catch {
        # held open elsewhere: keep appending to the old file
    }
    $stamp = [DateTime]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'",
        [System.Globalization.CultureInfo]::InvariantCulture)
    Add-Content -Path $log -Value ($stamp + ' INFO stop[' + $PID + '] AshLight ' + $Build +
        ' stop start (pid ' + $PID + ', powershell ' + [string]$PSVersionTable.PSVersion + ')') -Encoding ASCII
}

Start-AlStopLog (Get-AlBuildId)

function Get-AlCorePid {
    if (-not (Test-Path -LiteralPath $alive)) { return 0 }
    try {
        return [int]((Get-Content -LiteralPath $alive -Raw | ConvertFrom-Json).pid)
    } catch {
        return 0
    }
}

function Get-AlOwnCorePid {
    # server\al\procs.py core_pid: the core.alive pid only when its image is
    # python* and its creation time matches the recorded one; else 0.
    try {
        $st = ((Invoke-AlPython server.al.procs status) -join "`n") | ConvertFrom-Json
        return [int]$st.core.pid
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
    } elseif ((Get-AlOwnCorePid) -ne $corePid) {
        # SUP-2: the core died and another process got its pid (any image,
        # python included); the recorded creation time does not match.
        Write-AlLog "stop: pid $corePid is not the AshLight core (its pid was reused); not touching it"
    } else {
        Stop-Process -Id $corePid -Force
        Write-AlLog "stop: core pid $corePid did not exit in $TimeoutSec s; stopped it (keepalive will not restart it)"
    }
}

# OPS-STOP: then the keepalive supervisor (it exits by itself on stop.request;
# forced after the wait) and the Electron overlay, each only by a pid proven
# ours (server\al\procs.py: recorded pid + creation time, or an electron.exe
# inside this checkout's app\node_modules). Never the game, never another app.
$out = (Invoke-AlPython server.al.procs stop '--wait' $TimeoutSec) -join "`n"
$procRc = $LASTEXITCODE
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
