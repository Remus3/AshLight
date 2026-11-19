<#
.SYNOPSIS
  Start AshLight (idempotent). Windows PowerShell 5.1 compatible.
.DESCRIPTION
  Converges to the full running set (OPS-RUN-IDEMP, decision 0010): the core
  hidden (pythonw when available) on 127.0.0.1, the keepalive supervisor and,
  when installed, the AshLight desktop client (Electron, --client: the
  companion window, tray and overlay; decision 0041) - each started only
  when it is not already live (server\al\procs.py decides), so any number
  of calls leaves exactly one of each. The overlay exists only while the
  client runs (operator order 2026-11-17): there is no overlay-only start.
  Without the client installed (or with -Browser) the dashboard opens in the
  browser with the per-start token in the URL fragment. Logs go to the
  sidecar Logs dir.
.PARAMETER Overlay
  Accepted for compatibility; the client (with its overlay) starts by
  default when installed (scripts\setup.ps1 with Node).
.PARAMETER NoOverlay
  Do not start the client (and so no overlay); the dashboard opens in the
  browser instead. A running client is left alone.
.PARAMETER NoBrowser
  Open no window: neither the client nor the browser (the core and
  supervisor only; the client starts the core this way itself).
.PARAMETER Browser
  Open the dashboard in the default browser instead of the client.
.PARAMETER Port
  Core port for this run (block 8960-8979). Default: env AL_PORT, then
  "port" in config\local.json, then 8960 (server\al\ports.py resolve).
  Lets a second checkout run beside the first. Core, keepalive and overlay
  all get the same port.
.PARAMETER EdgeApp
  Open the dashboard in an Edge --app window instead of the default browser.
.PARAMETER Autostart
  Set only by the opt-in logon task (scripts\autostart.ps1, decision 0011):
  implies -NoBrowser and starts nothing unless the recorded opt-in
  (ops\runtime\autostart.json) says enabled.
#>
[CmdletBinding()]
param(
    [switch]$Overlay,
    [switch]$NoOverlay,
    [switch]$NoBrowser,
    [switch]$EdgeApp,
    [switch]$Browser,
    [int]$Port = 0,
    [switch]$Autostart
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
if ($Port -ne 0) {
    if ($Port -lt 8960 -or $Port -gt 8979) { throw "-Port $Port is outside AshLight's port block 8960-8979." }
    $env:AL_PORT = [string]$Port
}
Push-Location $Repo
try {
    $paths = ((& $py -m server.al.paths) -join "`n") | ConvertFrom-Json
    $port = [int]((& $py -c "import os; from server.al import paths, ports; print(ports.resolve(os.environ, paths.load_local_config()))").Trim())
} finally {
    Pop-Location
}
foreach ($dir in @($paths.runtime, $paths.logs, $paths.temp)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
$log = Join-Path $paths.logs 'run.log'

# CORE-AUTOSTART (decision 0011): the logon task passes -Autostart; the
# recorded opt-in decides, so a task left behind after -Disable is a no-op.
if ($Autostart) {
    $NoBrowser = [switch]$true
    $optin = $false
    $optinFile = Join-Path $paths.runtime 'autostart.json'
    if (Test-Path -LiteralPath $optinFile) {
        try {
            $optin = [bool]((Get-Content -LiteralPath $optinFile -Raw | ConvertFrom-Json).enabled)
        } catch {
            $optin = $false
        }
    }
    $state = if ($optin) { 'on' } else { 'off (no-op)' }
    Add-Content -Path $log -Value ((Get-Date -Format 's') + " run: logon autostart, opt-in $state") -Encoding ASCII
    if (-not $optin) { exit 0 }
}

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
    # Loopback only: an explicit empty proxy (PowerShell 5.1 has no -NoProxy),
    # so the token never reaches a proxy whatever the session or system names.
    $r = $null
    try {
        $req = [System.Net.WebRequest]::Create("http://127.0.0.1:$port/api/health")
        $req.Proxy = New-Object System.Net.WebProxy
        $req.Timeout = 2000
        $req.Headers.Add('X-AL-Token', $token)
        $r = $req.GetResponse()
        return ([int]$r.StatusCode -eq 200)
    } catch {
        return $false
    } finally {
        if ($r) { $r.Close() }
    }
}

$env:TEMP = $paths.temp
$env:TMP = $paths.temp
$env:AL_SIDECAR_ROOT = $paths.sidecar

# A stop.request left by scripts\stop.ps1 must not stop this start.
Remove-Item -LiteralPath (Join-Path $paths.runtime 'stop.request') -Force -ErrorAction SilentlyContinue

$pyw = Get-Command pythonw -ErrorAction SilentlyContinue
$exe = if ($pyw) { $pyw.Source } else { $py }
$detachEnv = @{ TEMP = $paths.temp; TMP = $paths.temp; AL_SIDECAR_ROOT = $paths.sidecar; AL_PORT = [string]$port }

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
# DESKTOP-CLIENT (decision 0041): the "overlay" component is the client
# process; it is wanted only when a window is wanted and the browser is not.
$wantOverlay = -not ($NoOverlay -or $NoBrowser -or $Browser -or $EdgeApp)
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
    $corePid = Start-AlDetached -FilePath $exe -ArgumentList @('-m', 'server.al', '--quiet', '--port', [string]$port) `
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

# DESKTOP-CLIENT (decision 0041): the client (companion window, tray and
# the overlay, one Electron process) is started detached with --client. When
# it is already live, a second --client start only asks it to show its
# window (single-instance lock) and exits; its pid is not recorded. The
# client's pid is recorded (ops\runtime\overlay.pid) for stop.ps1.
$clientShown = $false
if (-not $wantOverlay) {
    Write-AlLog 'run: client not requested (-NoOverlay / -NoBrowser / -Browser)'
} elseif (-not (Test-Path $electron)) {
    Write-AlLog 'run: client not installed - run scripts\setup.ps1 with Node 20+'
} else {
    $clientArgs = @('"' + (Join-Path $Repo 'app') + '"', '--client')
    $ovlPid = Start-AlDetached -FilePath $electron -ArgumentList $clientArgs `
        -WorkingDirectory (Join-Path $Repo 'app') -Environment $detachEnv
    $clientShown = $true
    if (@($plan.start) -contains 'overlay') {
        Push-Location $Repo
        try {
            & $py -m server.al.procs record-overlay ([string]$ovlPid)
            $recRc = $LASTEXITCODE
        } finally {
            Pop-Location
        }
        if ($recRc -ne 0) {
            Write-AlLog "run: client pid $ovlPid exited at once (see the overlay log)"
            $clientShown = $false
        } else {
            Write-AlLog "run: client started (pid $ovlPid; overlay toggle Alt+Shift+A)"
        }
    } else {
        Write-AlLog "run: client already running (pid $($plan.status.overlay.pid)); asked it to show its window"
    }
}

if ($clientShown) {
    Write-AlLog 'run: dashboard shown in the AshLight client'
} elseif (-not $NoBrowser) {
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
