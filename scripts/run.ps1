<#
.SYNOPSIS
  Start AshLight (idempotent). Windows PowerShell 5.1 compatible.
.DESCRIPTION
  Starts the core hidden (pythonw when available) on 127.0.0.1, then opens
  the dashboard with the per-start token in the URL fragment. -Overlay also
  starts the Electron overlay. When the core already answers its health
  check, the core start is a no-op. Logs go to the sidecar Logs dir.
.PARAMETER Overlay
  Also start the transparent overlay (needs scripts\setup.ps1 with Node).
.PARAMETER NoBrowser
  Do not open the dashboard.
.PARAMETER EdgeApp
  Open the dashboard in an Edge --app window instead of the default browser.
#>
[CmdletBinding()]
param(
    [switch]$Overlay,
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

if (Test-AlHealth) {
    Write-AlLog "run: core already running on 127.0.0.1:$port (no-op)"
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
# (decision 0005). It adopts the running core; a second copy exits at once
# (single-instance lock), so this is idempotent. Log: Logs\keepalive.log.
$supPid = Start-AlDetached -FilePath $exe -ArgumentList @('-m', 'server.al.keepalive', '--port', [string]$port) `
    -WorkingDirectory $Repo -Environment $detachEnv
Write-AlLog "run: keepalive supervisor launched (pid $supPid; stop with scripts\stop.ps1)"

$url = "http://127.0.0.1:$port/#token=" + (Get-AlToken)

if ($Overlay) {
    $electron = Join-Path $Repo 'app\node_modules\electron\dist\electron.exe'
    if (Test-Path $electron) {
        # Electron's single-instance lock makes a second start a no-op.
        $null = Start-AlDetached -FilePath $electron -ArgumentList @('"' + (Join-Path $Repo 'app') + '"') `
            -WorkingDirectory (Join-Path $Repo 'app')
        Write-AlLog 'run: overlay started (toggle Alt+Shift+A)'
    } else {
        Write-AlLog 'run: overlay not installed - run scripts\setup.ps1 with Node 20+'
    }
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
