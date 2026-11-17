<#
.SYNOPSIS
  AshLight build (idempotent). Windows PowerShell 5.1 compatible.
.DESCRIPTION
  Runs the Python tests and the overlay's node tests, then writes a build
  stamp (sidecar Build\build-stamp.json). A re-run with unchanged sources and
  a green stamp is a no-op; -Force rebuilds. The whole Python suite goes
  through the fleet suite gate when the vendored kit is present.
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$Snapshot,
    [switch]$NoSnapshot
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
Push-Location $Repo
try {
    $paths = ((& $py -m server.al.paths) -join "`n") | ConvertFrom-Json
} finally {
    Pop-Location
}
foreach ($dir in @($paths.build, $paths.logs, $paths.temp)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
$log = Join-Path $paths.logs 'build.log'

function Write-AlLog([string]$Message) {
    $line = (Get-Date -Format 's') + ' ' + $Message
    Add-Content -Path $log -Value $line -Encoding ASCII
    Write-Host $Message
}

# TC-SNAP (decision 0009, AUDIT-SNAPSHOT-OPTIN): refresh the game-data
# snapshot in the sidecar Cache ONLY when the user turned web data on
# (config/local.json "web_data": true, decision 0013) or the build is forced
# with -Snapshot / env AL_SNAPSHOT=1. -NoSnapshot / AL_NO_SNAPSHOT=1 always
# skip and win. The tool skips files checked in the last 24 h; offline or a
# failing source never fails the build.
function Test-AlWebData {
    $cfgFile = Join-Path $Repo 'config\local.json'
    if (-not (Test-Path $cfgFile)) { return $false }
    try {
        $cfg = Get-Content -Path $cfgFile -Raw | ConvertFrom-Json
        return ($cfg.PSObject.Properties.Name -contains 'web_data') -and
            ($cfg.web_data -is [bool]) -and ($cfg.web_data -eq $true)
    } catch {
        return $false
    }
}
$forceSnap = $Snapshot -or ($env:AL_SNAPSHOT -and $env:AL_SNAPSHOT -ne '0')
if ($NoSnapshot -or ($env:AL_NO_SNAPSHOT -and $env:AL_NO_SNAPSHOT -ne '0')) {
    Write-AlLog 'build: game-data snapshot skipped (NoSnapshot)'
} elseif (-not ($forceSnap -or (Test-AlWebData))) {
    Write-AlLog 'build: game-data snapshot skipped (web_data off; -Snapshot or AL_SNAPSHOT=1 forces it)'
} else {
    $snapLog = Join-Path $paths.logs 'build-snapshot.log'
    $snapArgs = @('-m', 'server.al.theorycraft.snapshot')
    if ($forceSnap) { $snapArgs += '--opt-in' }
    Push-Location $Repo
    try {
        $snapRc = Invoke-AlLogged $snapLog $py $snapArgs
        Write-AlLog "build: game-data snapshot rc $snapRc (log $snapLog)"
    } catch {
        Write-AlLog 'build: game-data snapshot failed (ignored)'
    } finally {
        Pop-Location
    }
}

# Source fingerprint: every authored file the build depends on.
function Get-AlSourceHash {
    $roots = @('server', 'web', 'app', 'tests', 'scripts')
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $sb = New-Object System.Text.StringBuilder
    foreach ($r in $roots) {
        $dir = Join-Path $Repo $r
        if (-not (Test-Path $dir)) { continue }
        $files = Get-ChildItem -Path $dir -Recurse -File |
            Where-Object { $_.FullName -notmatch '\\(node_modules|__pycache__|out|dist)\\' } |
            Sort-Object FullName
        foreach ($f in $files) {
            $h = (Get-FileHash -Path $f.FullName -Algorithm SHA256).Hash
            [void]$sb.Append($f.FullName.Substring($Repo.Length)).Append('=').Append($h).Append("`n")
        }
    }
    $bytes = [System.Text.Encoding]::ASCII.GetBytes($sb.ToString())
    return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '')
}

$sourceHash = Get-AlSourceHash
$stampFile = $paths.build_stamp
if ((Test-Path $stampFile) -and -not $Force) {
    try {
        $old = Get-Content -Path $stampFile -Raw | ConvertFrom-Json
        if ($old.ok -and $old.source_hash -eq $sourceHash) {
            Write-AlLog 'build: sources unchanged since the last green build (no-op)'
            exit 0
        }
    } catch {
        Write-AlLog 'build: unreadable stamp, rebuilding'
    }
}

$env:TEMP = $paths.temp
$env:TMP = $paths.temp

$pyLog = Join-Path $paths.logs 'build-pytest.log'
# TEST-CLEAN-CLONE: a clear message, not a traceback, when pytest is missing.
$ErrorActionPreference = 'Continue'
& $py -c "import pytest" 2>$null
$hasPytest = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = 'Stop'
if (-not $hasPytest) {
    Write-AlLog 'build: FAILED - pytest is not installed; run: python -m pip install pytest'
    exit 1
}
$gate = Join-Path $Repo 'ops\fleet_kit\fleet_suite_gate.py'
Push-Location $Repo
try {
    if (Test-Path $gate) {
        $owner = 'al-build.' + $PID
        $pyRc = Invoke-AlLogged $pyLog $py @($gate, 'run', '--owner', $owner, '--', $py, '-m', 'pytest', '-q', 'tests')
    } else {
        $pyRc = Invoke-AlLogged $pyLog $py @('-m', 'pytest', '-q', 'tests')
    }
} finally {
    Pop-Location
}
Write-AlLog "build: python tests rc $pyRc (log $pyLog)"

$nodeRc = $null
$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    $nodeLog = Join-Path $paths.logs 'build-node.log'
    Push-Location (Join-Path $Repo 'app')
    try {
        $nodeRc = Invoke-AlLogged $nodeLog 'npm.cmd' @('test')
    } finally {
        Pop-Location
    }
    Write-AlLog "build: node tests rc $nodeRc (log $nodeLog)"
} else {
    Write-AlLog 'build: Node not found - overlay tests skipped'
}

$ok = ($pyRc -eq 0) -and (($nodeRc -eq $null) -or ($nodeRc -eq 0))
$version = (& $py -c "import sys; sys.path.insert(0, r'$Repo'); from server.al import VERSION; print(VERSION)").Trim()
$stamp = [ordered]@{
    ok          = $ok
    version     = $version
    source_hash = $sourceHash
    python_rc   = $pyRc
    node_rc     = $nodeRc
    built_at    = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
}
$stamp | ConvertTo-Json | Set-Content -Path $stampFile -Encoding ASCII
if (-not $ok) {
    Write-AlLog 'build: FAILED'
    exit 1
}
Write-AlLog "build: ok (stamp $stampFile)"
exit 0
