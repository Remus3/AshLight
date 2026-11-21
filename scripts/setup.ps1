<#
.SYNOPSIS
  AshLight setup (idempotent). Windows PowerShell 5.1 compatible.
.DESCRIPTION
  Checks Python >= 3.11 and Node >= 22.12.0, creates the sidecar dirs, copies
  config/local.example.json to config/local.json only when it is missing, and
  installs the overlay's npm packages only when app/node_modules is missing
  or the lockfile changed (hash stamp in the sidecar Build dir), always as
  `npm ci --ignore-scripts` from the lockfile (a missing lockfile refuses).
  OVL-ELECTRON-SETUP (decision 0068): the install override variables are
  cleared first, the Electron binary comes only from tools/electron_pin.py
  (AshLight's own fetch, checked against config/electron_pin.json; never
  electron's own installer script), and electron.exe is verified against
  the pin after the install and on every up-to-date run (a changed exe
  makes setup install the packages again from the verified zip).
  LOOP-ELECTRON-POLICY (decision 0070): while AshLight's own client is live
  (its pid record in the runtime folder, or this checkout's electron.exe
  held open), setup ends with one line and exit 3 before npm runs, so a
  bump never swaps files under a running overlay; nothing is changed and a
  later run retries.
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

  DATA-SNAP-SETUP (decisions 0009 / 0013): when config/local.json already
  holds "web_data": true (strictly a JSON true), setup also refreshes the
  game-data snapshot in the sidecar Cache, so one setup command is enough
  once 'Use web data' is ticked. Web data off: no request, no process, and
  setup never forces it (build.ps1 -Snapshot does). -NoSnapshot or
  AL_NO_SNAPSHOT=1 skips it. A failing source never fails setup.
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$TcCalc,
    [switch]$NoShortcut,
    [switch]$NoSnapshot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$Repo = Split-Path -Parent $PSScriptRoot
# REL-RUNTIME-SCRIPTS (F-047): Get-AlPython and Get-AlPaths come from
# scripts\al_env.ps1, the one Python lookup. setup.ps1 is the checkout's
# setup (an installed copy is laid out by the installer), so its own module
# calls below keep the checkout form of Get-AlPythonCmd: <python> -m <module>.
. (Join-Path $PSScriptRoot 'al_env.ps1')
if (Get-AlInstallHome) {
    throw 'setup.ps1 sets up a source checkout; an installed copy is set up and repaired by its installer.'
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

$paths = Get-AlPaths
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

# DATA-SNAP-SETUP (decisions 0009 / 0013, AUDIT-SNAPSHOT-OPTIN): the
# game-data snapshot runs here only when web data is already on, read as
# strictly as the core and build.ps1 read it. No --opt-in is ever passed,
# so the snapshot tool re-checks the same setting itself. server.al.prio
# starts it as a below-normal priority child; it skips files checked in the
# last 24 h, so a re-run is a no-op. Returns a one-line status; an offline
# or failing source is logged, never thrown.
function Test-AlWebDataOn([string]$ConfigFile) {
    if (-not (Test-Path -LiteralPath $ConfigFile)) { return $false }
    try {
        $cfg = Get-Content -LiteralPath $ConfigFile -Raw | ConvertFrom-Json
        return ($null -ne $cfg) -and ($cfg.PSObject.Properties.Name -contains 'web_data') -and
            ($cfg.web_data -is [bool]) -and ($cfg.web_data -eq $true)
    } catch {
        return $false
    }
}

function Invoke-AlSnapshotStep([string]$Python, [string]$RepoRoot, [string]$LogFile, [bool]$Skip) {
    $ErrorActionPreference = 'Continue'
    if ($Skip -or ($env:AL_NO_SNAPSHOT -and $env:AL_NO_SNAPSHOT -ne '0')) {
        return 'skipped (NoSnapshot)'
    }
    if (-not (Test-AlWebDataOn (Join-Path $RepoRoot 'config\local.json'))) {
        return "skipped (web_data off; tick 'Use web data', then run setup again)"
    }
    $snapArgs = @('-m', 'server.al.prio', 'server.al.theorycraft.snapshot')
    Push-Location $RepoRoot
    try {
        & $Python @snapArgs 2>&1 | ForEach-Object { [string]$_ } |
            Set-Content -Path $LogFile -Encoding ASCII
        $rc = $LASTEXITCODE
        return "rc $rc (log $LogFile)"
    } catch {
        return 'failed (ignored)'
    } finally {
        Pop-Location
    }
}

$snapStatus = Invoke-AlSnapshotStep $py $Repo (Join-Path $paths.logs 'setup-snapshot.log') ([bool]$NoSnapshot)
Write-AlLog "setup: game-data snapshot $snapStatus"

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

# OVL-ELECTRON-SETUP (F-044, decision 0068): tools/electron_pin.py is the
# one route for the Electron binary (AshLight User-Agent, size and SHA-256
# from config/electron_pin.json, nothing unpacked before the zip matches)
# and the one check of electron.exe. Exit 0 = ok (or no pin for this
# architecture: no client), 2 = refused, 1 = failed. Every line goes to
# setup.log. verify-exe counts as ok only with its "electron.exe ok" line:
# a machine no pin covers has no trusted exe.
function Invoke-AlElectronPin([string]$Command) {
    $ErrorActionPreference = 'Continue'
    $out = @()
    $rc = 1
    Push-Location $Repo
    try {
        $out = @(& $py (Join-Path $Repo 'tools\electron_pin.py') $Command '--app-dir' $app 2>&1 |
            ForEach-Object { [string]$_ })
        $rc = $LASTEXITCODE
    } catch {
        $out = @([string]$_)
        $rc = 1
    } finally {
        Pop-Location
    }
    foreach ($line in $out) {
        if ($line) { Write-AlLog "setup: electron: $line" }
    }
    if ($Command -eq 'verify-exe' -and $rc -eq 0 -and -not (@($out) -match '^electron\.exe ok')) {
        Write-AlLog 'setup: electron: no pin covers this machine, so electron.exe is not trusted'
        $rc = 2
    }
    return $rc
}

function Assert-AlElectronPin([int]$Rc) {
    if ($Rc -eq 2) {
        throw 'setup: Electron REFUSED (the download or electron.exe does not match config/electron_pin.json; nothing unverified was kept); see setup.log, then run setup again'
    }
    if ($Rc -ne 0) { throw "setup: Electron step failed (rc $Rc); see setup.log, then run setup again" }
}

# The install override variables (research 0046 F2 / R4): electron's
# installer and @electron/get read them to skip the packaged checksums,
# move the download host or redirect the dist folder. AshLight's fetch
# reads none of them; they are removed from this process (and so from
# npm) anyway, so nothing below can be steered by them. The player's own
# environment is left as it is.
function Clear-AlElectronOverrides {
    $names = @(
        'electron_use_remote_checksums', 'ELECTRON_USE_REMOTE_CHECKSUMS',
        'npm_config_electron_use_remote_checksums',
        'ELECTRON_MIRROR', 'electron_mirror', 'npm_config_electron_mirror',
        'ELECTRON_NIGHTLY_MIRROR', 'electron_nightly_mirror', 'npm_config_electron_nightly_mirror',
        'ELECTRON_CUSTOM_DIR', 'electron_custom_dir', 'npm_config_electron_custom_dir',
        'ELECTRON_CUSTOM_FILENAME', 'electron_custom_filename', 'npm_config_electron_custom_filename',
        'ELECTRON_CUSTOM_VERSION', 'electron_custom_version', 'npm_config_electron_custom_version',
        'ELECTRON_OVERRIDE_DIST_PATH',
        'ELECTRON_INSTALL_PLATFORM', 'ELECTRON_INSTALL_ARCH',
        'npm_config_platform', 'npm_config_arch',
        'electron_config_cache', 'npm_config_electron_config_cache',
        'force_no_cache', 'npm_config_force_no_cache'
    )
    foreach ($name in $names) {
        Remove-Item -LiteralPath ('Env:\' + $name) -ErrorAction SilentlyContinue
    }
}

if ($upToDate -and -not $Force) {
    # The fast path still checks electron.exe (a stat when unchanged since
    # the last good check); a changed exe is never kept: the packages are
    # installed again and the exe unpacked again from the verified zip.
    $verifyRc = Invoke-AlElectronPin 'verify-exe'
    if ($verifyRc -eq 0) {
        Write-AlLog 'setup: app/node_modules up to date (no-op)'
        Invoke-AlShortcutStep
        exit 0
    }
    Write-AlLog 'setup: electron.exe is not the pinned one; installing the overlay packages again'
}

# LOOP-ELECTRON-POLICY (F-130, decision 0070): npm ci wipes node_modules
# and the pin step unpacks a new dist, so neither may run under a live
# client. Two signals, both about AshLight's own files only:
# - the process registry: <runtime>\overlay.pid read through
#   server.al.procs.overlay_main_pid (that one pid: alive, image
#   electron.exe, creation time matching); never the game, never a
#   system-wide scan of processes by name;
# - this checkout's own electron.exe opened with no sharing: Windows holds a
#   running image open, so the open fails while any client started from it
#   lives (a shortcut start writes no pid record).
# Returns '' when the client is not live, else the one-line reason. A
# registry read that fails counts as live (fail closed).
function Test-AlClientLive([string]$Python, [string]$RepoRoot, [string]$Runtime, [string]$Exe) {
    $ErrorActionPreference = 'Continue'
    $out = ''
    $rc = 1
    Push-Location $RepoRoot
    try {
        $out = (@(& $Python -c 'import sys; from server.al import procs; print(procs.overlay_main_pid(sys.argv[1]))' $Runtime 2>$null) -join '').Trim()
        $rc = $LASTEXITCODE
    } catch {
        $rc = 1
    } finally {
        Pop-Location
    }
    if ($rc -ne 0 -or $out -notmatch '^\d+$') {
        return 'the process registry could not be read'
    }
    if ([int64]$out -gt 0) {
        return "the AshLight client is running (pid $out)"
    }
    if ($Exe -and (Test-Path -LiteralPath $Exe)) {
        $fh = $null
        try {
            $fh = [System.IO.File]::Open($Exe, [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        } catch [System.IO.IOException] {
            return 'the AshLight client is running (its electron.exe is in use)'
        } catch {
            # no write access to the file (read-only, ACL): not a live-client
            # signal; the registry answered above
            $fh = $null
        } finally {
            if ($fh) { $fh.Dispose() }
        }
    }
    return ''
}

$clientLive = Test-AlClientLive $py $Repo $paths.runtime $electronExe
if ($clientLive) {
    Write-AlLog "setup: overlay packages NOT changed - $clientLive; quit it from its tray icon, then run setup again"
    exit 3
}

Clear-AlElectronOverrides

# Caches and temp stay in the sidecar, never in the drive root.
$env:npm_config_cache = $paths.npm_cache
$env:npm_config_update_notifier = 'false'
$env:npm_config_fund = 'false'
$env:TEMP = $paths.temp
$env:TMP = $paths.temp

$npmLog = Join-Path $paths.logs 'npm-install.log'
Push-Location $app
try {
    # OVL-NPM-LOCK (F-037): the lockfile is the only install route and no
    # package script runs (app/.npmrc says the same); a missing lockfile
    # refuses instead of resolving fresh versions.
    if (-not (Test-Path $lock)) {
        throw 'setup: app/package-lock.json is missing; restore it from the repository (no install without the lockfile)'
    }
    Write-AlLog 'setup: npm ci --ignore-scripts'
    $npmRc = Invoke-AlLogged $npmLog 'npm.cmd' @('ci', '--ignore-scripts', '--no-audit') -Append
    if ($npmRc -ne 0) { throw "npm failed (rc $npmRc); see $npmLog" }
} finally {
    Pop-Location
}
# npm ci (scripts off) leaves the electron package without its binary:
# fetch (or reuse the cached, verified zip), unpack, check electron.exe.
Write-AlLog 'setup: fetching the Electron binary (tools/electron_pin.py)'
Assert-AlElectronPin (Invoke-AlElectronPin 'setup')
if (Test-Path $electronExe) {
    Assert-AlElectronPin (Invoke-AlElectronPin 'verify-exe')
}
if (Test-Path $lock) { $hash = (Get-FileHash -Path $lock -Algorithm SHA256).Hash }
Set-Content -Path $stamp -Value $hash -Encoding ASCII
Write-AlLog 'setup: app/node_modules installed'
Invoke-AlShortcutStep
exit 0
