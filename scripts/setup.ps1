<#
.SYNOPSIS
  AshLight setup (idempotent). Windows PowerShell 5.1 compatible.
.DESCRIPTION
  Checks Python >= 3.11 and Node >= 20, creates the sidecar dirs, copies
  config/local.example.json to config/local.json only when it is missing, and
  installs the overlay's npm packages only when app/node_modules is missing
  or the lockfile changed (hash stamp in the sidecar Build dir).
  Every path comes from `python -m server.al.paths` (the one resolver).
  Node is optional: without it the core and the dashboard still work.

  TC-PIN (decision 0004 item 3, decision 0017): the optional theorycraft
  calc component (Path of Building PoE2 source + LuaJIT) is OFF by default.
  Opt in with -TcCalc or "tc_calc": true in config/local.json; then
  tools/tc_pin.py fetches the hash-pinned archives (config/tc_pins.json)
  into the sidecar Cache / Build dirs, verifies SHA-256, refuses on a
  mismatch (setup fails) and is a no-op on a re-run.
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$TcCalc
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

function Get-AlPaths([string]$Python) {
    Push-Location $Repo
    try {
        $json = (& $Python -m server.al.paths) -join "`n"
        if ($LASTEXITCODE -ne 0) { throw 'server.al.paths failed' }
    } finally {
        Pop-Location
    }
    return $json | ConvertFrom-Json
}

$py = Get-AlPython
$pyVer = (& $py -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
if ([version]$pyVer -lt [version]'3.11') {
    throw "Python $pyVer found; AshLight needs 3.11 or newer."
}

$paths = Get-AlPaths $py
foreach ($dir in @($paths.runtime, $paths.temp, $paths.build, $paths.logs, $paths.cache)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
$log = Join-Path $paths.logs 'setup.log'

function Write-AlLog([string]$Message) {
    $line = (Get-Date -Format 's') + ' ' + $Message
    Add-Content -Path $log -Value $line -Encoding ASCII
    Write-Host $Message
}

Write-AlLog "setup: python $pyVer ok"

# Per-host config: copy the example once, never overwrite.
$example = Join-Path $Repo 'config\local.example.json'
$local = Join-Path $Repo 'config\local.json'
if ((Test-Path $example) -and -not (Test-Path $local)) {
    Copy-Item -Path $example -Destination $local
    Write-AlLog 'setup: config/local.json created from the example'
} elseif (Test-Path $local) {
    Write-AlLog 'setup: config/local.json present (kept)'
} else {
    Write-AlLog 'setup: no config example yet (skipped)'
}

# Optional calc component (TC-PIN). Off unless -TcCalc or tc_calc: true.
# tools/tc_pin.py decides the opt-in, does the work and prints one line per
# step on stdout; exit 2 = refused (pin or hash mismatch), 1 = failed.
$tcArgs = @((Join-Path $Repo 'tools\tc_pin.py'), 'setup')
if ($TcCalc) { $tcArgs += '--opt-in' }
$env:TEMP = $paths.temp
$env:TMP = $paths.temp
Push-Location $Repo
try {
    & $py @tcArgs | ForEach-Object { Write-AlLog ("setup: tc: " + $_) }
    $tcRc = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($tcRc -eq 2) { throw 'setup: calc component REFUSED (pin or hash mismatch); see setup.log' }
if ($tcRc -ne 0) { throw "setup: calc component step failed (rc $tcRc); see setup.log" }

# Overlay packages (optional).
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-AlLog 'setup: Node not found - overlay skipped; core and dashboard work without it'
    exit 0
}
$nodeVer = (& $node.Source --version).Trim().TrimStart('v')
if ([version]$nodeVer -lt [version]'20.0') {
    Write-AlLog "setup: Node $nodeVer is older than 20 - overlay skipped"
    exit 0
}
Write-AlLog "setup: node $nodeVer ok"

$app = Join-Path $Repo 'app'
$lock = Join-Path $app 'package-lock.json'
$pkg = Join-Path $app 'package.json'
$hashSource = $pkg
if (Test-Path $lock) { $hashSource = $lock }
$hash = (Get-FileHash -Path $hashSource -Algorithm SHA256).Hash
$stamp = Join-Path $paths.build 'npm-stamp.txt'
$modules = Join-Path $app 'node_modules'
$electronExe = Join-Path $app 'node_modules\electron\dist\electron.exe'

$upToDate = $false
if ((Test-Path $modules) -and (Test-Path $stamp) -and (Test-Path $electronExe)) {
    $upToDate = ((Get-Content -Path $stamp -Raw).Trim() -eq $hash)
}
if ($upToDate -and -not $Force) {
    Write-AlLog 'setup: app/node_modules up to date (no-op)'
    exit 0
}

# Caches and temp stay in the sidecar, never in the drive root.
$env:npm_config_cache = $paths.npm_cache
$env:electron_config_cache = $paths.electron_cache
$env:npm_config_update_notifier = 'false'
$env:npm_config_fund = 'false'
$env:TEMP = $paths.temp
$env:TMP = $paths.temp

$npmLog = Join-Path $paths.logs 'npm-install.log'
Push-Location $app
try {
    if (Test-Path $lock) {
        Write-AlLog 'setup: npm ci'
        & npm.cmd ci --no-audit *>> $npmLog
    } else {
        Write-AlLog 'setup: npm install --save-exact (no lockfile)'
        & npm.cmd install --save-exact --no-audit *>> $npmLog
    }
    if ($LASTEXITCODE -ne 0) { throw "npm failed (rc $LASTEXITCODE); see $npmLog" }
    if (-not (Test-Path $electronExe)) {
        Write-AlLog 'setup: fetching the Electron binary'
        & $node.Source 'node_modules\electron\install.js' *>> $npmLog
        if ($LASTEXITCODE -ne 0) { throw "Electron download failed; see $npmLog" }
    }
} finally {
    Pop-Location
}
if (Test-Path $lock) { $hash = (Get-FileHash -Path $lock -Algorithm SHA256).Hash }
Set-Content -Path $stamp -Value $hash -Encoding ASCII
Write-AlLog 'setup: app/node_modules installed'
exit 0
