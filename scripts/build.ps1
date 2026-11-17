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
    [switch]$Force
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
foreach ($dir in @($paths.build, $paths.logs, $paths.temp)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
$log = Join-Path $paths.logs 'build.log'

function Write-AlLog([string]$Message) {
    $line = (Get-Date -Format 's') + ' ' + $Message
    Add-Content -Path $log -Value $line -Encoding ASCII
    Write-Host $Message
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
$gate = Join-Path $Repo 'ops\fleet_kit\fleet_suite_gate.py'
Push-Location $Repo
try {
    if (Test-Path $gate) {
        $owner = 'al-build.' + $PID
        & $py $gate run --owner $owner -- $py -m pytest -q tests *> $pyLog
    } else {
        & $py -m pytest -q tests *> $pyLog
    }
    $pyRc = $LASTEXITCODE
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
        & npm.cmd test *> $nodeLog
        $nodeRc = $LASTEXITCODE
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
