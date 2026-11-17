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

if (Test-AlHealth) {
    Write-AlLog "run: core already running on 127.0.0.1:$port (no-op)"
} else {
    $pyw = Get-Command pythonw -ErrorAction SilentlyContinue
    if ($pyw) {
        Start-Process -FilePath $pyw.Source -ArgumentList @('-m', 'server.al', '--quiet') `
            -WorkingDirectory $Repo -WindowStyle Hidden | Out-Null
    } else {
        Start-Process -FilePath $py -ArgumentList @('-m', 'server.al') `
            -WorkingDirectory $Repo -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $paths.logs 'core.out.log') `
            -RedirectStandardError (Join-Path $paths.logs 'core.err.log') | Out-Null
    }
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

$url = "http://127.0.0.1:$port/#token=" + (Get-AlToken)

if ($Overlay) {
    $electron = Join-Path $Repo 'app\node_modules\electron\dist\electron.exe'
    if (Test-Path $electron) {
        # Electron's single-instance lock makes a second start a no-op.
        Start-Process -FilePath $electron -ArgumentList @('"' + (Join-Path $Repo 'app') + '"') `
            -WorkingDirectory (Join-Path $Repo 'app') | Out-Null
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
