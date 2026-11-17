<#
.SYNOPSIS
  Start AshLight (idempotent). Windows PowerShell 5.1 compatible.
.DESCRIPTION
  Converges to the full running set (OPS-RUN-IDEMP, decision 0010): the core
  hidden (pythonw when available) on 127.0.0.1, the keepalive supervisor and,
  when installed, the Electron overlay - each started only when it is not
  already live (server\al\procs.py decides), so any number of calls leaves
  exactly one of each. Then opens the dashboard with the per-start token in
  the URL fragment. Logs go to the sidecar Logs dir.
.PARAMETER Overlay
  Accepted for compatibility; the overlay now starts by default when
  installed (scripts\setup.ps1 with Node).
.PARAMETER NoOverlay
  Do not start the overlay (one that is already running is left alone).
.PARAMETER NoBrowser
  Do not open the dashboard.
.PARAMETER EdgeApp
  Open the dashboard in an Edge --app window instead of the default browser.
#>
[CmdletBinding()]
param(
    [switch]$Overlay,
    [switch]$NoOverlay,
    [switch]$NoBrowser,
    [switch]$EdgeApp
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$Repo = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'al_detach.ps1')

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
    $port = [int]((& $py -c "from server.al import ports; print(ports.AL_PORT)").Trim())
} finally {
    Pop-Location
}
foreach ($dir in @($paths.runtime, $paths.logs, $paths.temp)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
$log = Join-Path $paths.logs 'run.log'

function Write-AlLog([string]$Message) {
    $line = (Get-Date -Format 's') + ' ' + $Message
    Add-Content -Path $log -Value $line -Encoding ASCII
    Write-Host $Message
}

function Get-AlToken {
    if (Test-Path $paths.token) { return (Get-Content -Path $paths.token -Raw).Trim() }
    return ''
}

function Test-AlHealth {
    $token = Get-AlToken
    if (-not $token) { return $false }
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/api/health" -UseBasicParsing `
            -Headers @{ 'X-AL-Token' = $token } -TimeoutSec 2
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

$env:TEMP = $paths.temp
$env:TMP = $paths.temp
$env:AL_SIDECAR_ROOT = $paths.sidecar

# A stop.request left by scripts\stop.ps1 must not stop this start.
Remove-Item -LiteralPath (Join-Path $paths.runtime 'stop.request') -Force -ErrorAction SilentlyContinue

$pyw = Get-Command pythonw -ErrorAction SilentlyContinue
$exe = if ($pyw) { $pyw.Source } else { $py }
$detachEnv = @{ TEMP = $paths.temp; TMP = $paths.temp; AL_SIDECAR_ROOT = $paths.sidecar }

function Get-AlPlan {
    # Which of core / supervisor / overlay must start (server\al\procs.py).
    $planArgs = @('-m', 'server.al.procs', 'plan')
    if (-not $wantOverlay) { $planArgs += '--no-overlay' }
    if (-not (Test-Path $electron)) { $planArgs += '--overlay-missing' }
    Push-Location $Repo
    try {
        return ((& $py @planArgs) -join "`n") | ConvertFrom-Json
    } finally {
        Pop-Location
    }
}

$electron = Join-Path $Repo 'app\node_modules\electron\dist\electron.exe'
$wantOverlay = -not $NoOverlay
$plan = Get-AlPlan

if (Test-AlHealth) {
    Write-AlLog "run: core already running on 127.0.0.1:$port (no-op)"
} elseif ($plan.status.core.live) {
    Write-AlLog "run: core pid $($plan.status.core.pid) is starting; waiting for it"
    $deadline = (Get-Date).AddSeconds(15)
    while (-not (Test-AlHealth)) {
        if ((Get-Date) -gt $deadline) {
            Write-AlLog "run: core did not answer on 127.0.0.1:$port within 15 s; see $($paths.core_log)"
            exit 1
        }
        Start-Sleep -Milliseconds 250
    }
} else {
    # Detached via WMI (scripts\al_detach.ps1): the core must outlive this
    # script and whatever shell started it. --quiet: core.log is the record.
    $corePid = Start-AlDetached -FilePath $exe -ArgumentList @('-m', 'server.al', '--quiet') `
        -WorkingDirectory $Repo -Environment $detachEnv
    Write-AlLog "run: core launched detached (pid $corePid)"
    $deadline = (Get-Date).AddSeconds(15)
    while (-not (Test-AlHealth)) {
        if ((Get-Date) -gt $deadline) {
            Write-AlLog "run: core did not answer on 127.0.0.1:$port within 15 s; see $($paths.core_log)"
            exit 1
        }
        Start-Sleep -Milliseconds 250
    }
    Write-AlLog "run: core started on 127.0.0.1:$port"
}

# CORE-KEEPALIVE: a detached supervisor restarts the core if it dies
# (decision 0005). It adopts the running core. Started only when no
# supervisor holds its single-instance lock (OPS-RUN-IDEMP), so a re-run
# never spawns a second one. Log: Logs\keepalive.log.
if (@($plan.start) -contains 'supervisor') {
    $supPid = Start-AlDetached -FilePath $exe -ArgumentList @('-m', 'server.al.keepalive', '--port', [string]$port) `
        -WorkingDirectory $Repo -Environment $detachEnv
    Write-AlLog "run: keepalive supervisor launched (pid $supPid; stop with scripts\stop.ps1)"
} else {
    Write-AlLog "run: keepalive supervisor already running (no-op)"
}

$url = "http://127.0.0.1:$port/#token=" + (Get-AlToken)

# The overlay is part of the full running set: started whenever it is
# installed and not already live, independent of -NoBrowser; -NoOverlay
# opts out. Its pid is recorded (ops\runtime\overlay.pid) for stop.ps1.
if (-not $wantOverlay) {
    Write-AlLog 'run: overlay not requested (-NoOverlay)'
} elseif (-not (Test-Path $electron)) {
    Write-AlLog 'run: overlay not installed - run scripts\setup.ps1 with Node 20+'
} elseif (@($plan.start) -contains 'overlay') {
    $ovlPid = Start-AlDetached -FilePath $electron -ArgumentList @('"' + (Join-Path $Repo 'app') + '"') `
        -WorkingDirectory (Join-Path $Repo 'app') -Environment $detachEnv
    Push-Location $Repo
    try {
        & $py -m server.al.procs record-overlay ([string]$ovlPid)
        $recRc = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($recRc -ne 0) {
        Write-AlLog "run: overlay pid $ovlPid exited at once (see the overlay log)"
    } else {
        Write-AlLog "run: overlay started (pid $ovlPid; toggle Alt+Shift+A)"
    }
} else {
    Write-AlLog "run: overlay already running (pid $($plan.status.overlay.pid); no-op)"
}

if (-not $NoBrowser) {
    if ($EdgeApp) {
        $edge = Get-Command msedge -ErrorAction SilentlyContinue
        if ($edge) {
            Start-Process -FilePath $edge.Source -ArgumentList @("--app=$url") | Out-Null
        } else {
            Start-Process $url | Out-Null
        }
    } else {
        Start-Process $url | Out-Null
    }
    Write-AlLog 'run: dashboard opened'
} else {
    Write-Host "Dashboard: $url"
}
exit 0
