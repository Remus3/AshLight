<#
.SYNOPSIS
  AshLight setup (idempotent). Windows PowerShell 5.1 compatible.
.DESCRIPTION
  Checks Python >= 3.11 and Node >= 22.12.0, creates the sidecar dirs, copies
  config/local.example.json to config/local.json only when it is missing, and
  installs the overlay's npm packages only when app/node_modules is missing
  or the lockfile changed (hash stamp in the sidecar Build dir).
  Every path comes from `python -m server.al.paths` (the one resolver).
  Node is optional: without it the core and the dashboard still work.

  TC-PIN (decision 0004 item 3, decision 0018): the optional theorycraft
  calc component (Path of Building PoE2 source + LuaJIT) is OFF by default.
  One run of -TcCalc installs the calc and turns it on: tools/tc_pin.py
  fetches the hash-pinned archives (config/tc_pins.json) into the sidecar
  Cache / Build dirs, verifies SHA-256 and, after a verified install,
  writes "tc_calc": true into config/local.json (every other key kept).
  A mismatch refuses (setup fails) and leaves the setting unchanged; a
  re-run is a no-op. "tc_calc": true already in the file also opts in.

  DESKTOP-CLIENT (decision 0041): with the overlay packages installed, a
  per-user "AshLight" shortcut goes to the Start Menu and the desktop
  (no admin). It starts the pinned Electron with the app and --client (the
  companion window, tray and overlay; the client starts the core itself).
  Its icon is AshLight's own tracked app\assets\icon.ico (BRAND-ICON,
  docs/design/0005-brand-mark.md; no game art). A re-run changes nothing
  when both are current;
  -NoShortcut skips the step.
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$TcCalc,
    [switch]$NoShortcut
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

# TEST-CLEAN-CLONE: under $ErrorActionPreference 'Stop', Windows PowerShell
# 5.1 turns the first stderr line of a redirected native command (a pytest
# plugin warning, an npm notice) into a terminating error. Native tools run
# here with 'Continue' (function scope) and their exit code decides.
function Invoke-AlLogged([string]$LogFile, [string]$Exe, [string[]]$ArgList, [switch]$Append) {
    $ErrorActionPreference = 'Continue'
    if ($Append) {
        & $Exe @ArgList 2>&1 | ForEach-Object { [string]$_ } | Add-Content -Path $LogFile -Encoding ASCII
    } else {
        & $Exe @ArgList 2>&1 | ForEach-Object { [string]$_ } | Set-Content -Path $LogFile -Encoding ASCII
    }
    return $LASTEXITCODE
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
# DEP-02 (F-019): 3.11 stays the floor, but python.org ships no Windows
# installer for a security-only branch; one advisory line, never a stop.
if (@('3.11', '3.12') -contains $pyVer) {
    Write-AlLog "setup: note - Python $pyVer still works, but python.org has no Windows installer for that branch any more; a new install should take 3.13 or newer"
}

# SEC-ACL-SETUP (F-011, decision 0051): AshLight's own folders and the
# per-host config get the private ACL (the player, SYSTEM, the local admins
# group; inheritance off) through 'python -m server.al.acl apply', which
# runs System32 icacls by its absolute path and is a no-op on a path that
# is already private. Every line goes to setup.log; a failure is a warning
# line and never stops setup.
function Invoke-AlAcl([string]$Target) {
    $ErrorActionPreference = 'Continue'
    $out = @()
    $rc = 1
    Push-Location $Repo
    try {
        $out = @(& $py -m server.al.acl apply $Target 2>&1 | ForEach-Object { [string]$_ })
        $rc = $LASTEXITCODE
    } catch {
        $out = @([string]$_)
        $rc = 1
    } finally {
        Pop-Location
    }
    foreach ($line in $out) {
        if ($line) { Write-AlLog "setup: $line" }
    }
    if ($rc -ne 0) {
        Write-AlLog "setup: WARNING acl not applied (exit $rc), setup goes on: $Target"
    }
}

Invoke-AlAcl $paths.sidecar
Invoke-AlAcl $paths.runtime

# TEST-CLEAN-CLONE: build.ps1 runs the test suite with pytest (a dev tool,
# never imported by the app). Say so here instead of failing in build.ps1.
$ErrorActionPreference = 'Continue'
& $py -c "import pytest" 2>$null
$hasPytest = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = 'Stop'
if ($hasPytest) {
    Write-AlLog 'setup: pytest ok (build.ps1 runs the tests with it)'
} else {
    Write-AlLog 'setup: pytest not found - the app runs without it, but build.ps1 needs it: python -m pip install pytest'
}

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
if (Test-Path $local) {
    Invoke-AlAcl $local
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
if ($tcRc -eq 2) { throw 'setup: calc component REFUSED (pin or hash mismatch); the calc setting is unchanged; see setup.log' }
if ($tcRc -ne 0) { throw "setup: calc component step failed (rc $tcRc); see setup.log" }

# Overlay packages (optional).
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-AlLog 'setup: Node not found - overlay skipped; core and dashboard work without it'
    exit 0
}
# DEP-02 (F-019): the floor is the pinned Electron's engines.node value in
# app/package-lock.json (tests/test_source_install.py keeps them equal).
$nodeFloor = '22.12.0'
$nodeVer = (& $node.Source --version).Trim().TrimStart('v')
$nodeNum = ($nodeVer -split '[-+]')[0]
if ([version]$nodeNum -lt [version]$nodeFloor) {
    Write-AlLog "setup: Node $nodeVer is older than $nodeFloor - overlay skipped"
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
# DESKTOP-CLIENT (decision 0041): the per-user Start Menu and desktop
# shortcuts. DEP-07: written and read back by scripts/al_shell.ps1 (the one
# place for AshLight's shortcuts and uninstall entry). Idempotent: a
# shortcut is rewritten only when its target, arguments, folder or icon
# differ; one whose target lies outside this checkout (an installed copy's,
# another checkout's) is left alone. AL_SHELL_ROOT redirects the writes to
# a scratch folder.
. (Join-Path $PSScriptRoot 'al_shell.ps1')

function Invoke-AlShortcutStep {
    if ($NoShortcut) {
        Write-AlLog 'setup: shortcuts skipped (-NoShortcut)'
        return
    }
    if (-not (Test-Path $electronExe)) {
        Write-AlLog 'setup: shortcuts skipped (the client is not installed)'
        return
    }
    $icon = Join-Path $app 'assets\icon.ico'
    if (-not (Test-Path $icon)) { throw 'setup: app\assets\icon.ico is missing' }
    $iconState = 'app\assets\icon.ico'
    $linkArgs = '"' + $app + '" --client'
    $results = @(Install-AlShortcuts -Target $electronExe -Arguments $linkArgs -WorkDir $app `
        -Icon $icon -OwnerRoot $Repo)
    $made = @($results | Where-Object { $_.Status -eq 'written' })
    $other = @($results | Where-Object { $_.Status -eq 'elsewhere' })
    if ($other.Count -gt 0) {
        Write-AlLog ("setup: " + $other.Count + " AshLight shortcut(s) point outside this checkout (left alone)")
    }
    if ($made.Count -gt 0) {
        Write-AlLog ("setup: AshLight shortcut written (" + $made.Count + "; icon " + $iconState + ")")
    } else {
        Write-AlLog 'setup: AshLight shortcuts up to date (no-op)'
    }
}

if ($upToDate -and -not $Force) {
    Write-AlLog 'setup: app/node_modules up to date (no-op)'
    Invoke-AlShortcutStep
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
        $npmRc = Invoke-AlLogged $npmLog 'npm.cmd' @('ci', '--no-audit') -Append
    } else {
        Write-AlLog 'setup: npm install --save-exact (no lockfile)'
        $npmRc = Invoke-AlLogged $npmLog 'npm.cmd' @('install', '--save-exact', '--no-audit') -Append
    }
    if ($npmRc -ne 0) { throw "npm failed (rc $npmRc); see $npmLog" }
    if (-not (Test-Path $electronExe)) {
        Write-AlLog 'setup: fetching the Electron binary'
        $elRc = Invoke-AlLogged $npmLog $node.Source @('node_modules\electron\install.js') -Append
        if ($elRc -ne 0) { throw "Electron download failed (rc $elRc); see $npmLog" }
    }
} finally {
    Pop-Location
}
if (Test-Path $lock) { $hash = (Get-FileHash -Path $lock -Algorithm SHA256).Hash }
Set-Content -Path $stamp -Value $hash -Encoding ASCII
Write-AlLog 'setup: app/node_modules installed'
Invoke-AlShortcutStep
exit 0
