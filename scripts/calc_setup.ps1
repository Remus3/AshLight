<#
.SYNOPSIS
  Set up the optional Path of Building calc component (decision 0018 opt-in)
  for the desktop client's "Set up the calc" button. Windows PowerShell 5.1
  compatible. Takes no parameter.
.DESCRIPTION
  TC-CALC-OPTIN-BUTTON (decision 0041 amendment 2026-11-20, rulings Q-08,
  W16-1, W16-2). The client runs this file hidden, with no argument,
  through app/client/launcher.js setupCalc (the absolute System32
  PowerShell); the dashboard's Checks button is the player's opt-in.
  1. It first lowers its own priority to BelowNormal; the Python child and
     the LuaJIT build it starts inherit that class, so the setup never
     competes with the game.
  2. In a checkout it resolves Python the way scripts\autostart.ps1 does
     (python, else py, from PATH) and runs tools\tc_pin.py setup --opt-in
     from the checkout root: the same step as setup.ps1 -TcCalc, which
     turns the calc on only after a verified install.
  3. In an installed copy (<home>\install.json two levels above the payload
     root, or AL_HOME) it runs the marker's private runtime
     (<home>\runtime\<marker "python">\python.exe) with the payload's
     boot.py: installer calc --opt-in (server.al.install calc, DEP-09).
  It never runs setup.ps1 (decision 0070 refuses the npm step while the
  client runs). Its output goes to calc_setup.log in AshLight's Logs folder
  when the path resolver answers. Exit code: the child's (0 ok, 2 refused,
  1 failed), 1 when no Python is found. Nothing here touches the game.
#>
[CmdletBinding()]
param()

# BelowNormal first, before any other work (inherited by every child).
try {
    (Get-Process -Id $PID).PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
} catch {
    Write-Host 'calc setup: priority not lowered'
}

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

# The install home the way server\al\paths.py install_home finds it:
# AL_HOME, else two levels above the payload root when install.json is there.
function Get-AlInstallHome {
    $fromEnv = ([string]$env:AL_HOME).Trim().Trim('"')
    if ($fromEnv) { return [System.IO.Path]::GetFullPath($fromEnv) }
    $up = Split-Path -Parent (Split-Path -Parent $Repo)
    if ($up -and (Test-Path -LiteralPath (Join-Path $up 'install.json') -PathType Leaf)) {
        return $up
    }
    return $null
}

# <home>\runtime\<marker "python">\python.exe: one plain folder name, never
# a path out of <home>\runtime (server\al\paths.py _marker_runtime).
function Get-AlInstalledPython([string]$AlHome) {
    $marker = Join-Path $AlHome 'install.json'
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
        throw 'The install marker is missing; nothing done.'
    }
    $doc = (Get-Content -LiteralPath $marker -Raw) | ConvertFrom-Json
    $name = ''
    if ($doc.PSObject.Properties.Name -contains 'python') { $name = [string]$doc.python }
    if (-not $name.Trim('. ') -or $name.IndexOfAny([char[]]@('\', '/', ':')) -ge 0) {
        throw 'The install marker names no usable Python runtime; nothing done.'
    }
    $exe = Join-Path (Join-Path (Join-Path $AlHome 'runtime') $name) 'python.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw 'The private Python runtime is missing; nothing done.'
    }
    return $exe
}

$log = $null
function Write-AlCalcLog([string]$Line) {
    $text = (Get-Date -Format 's') + ' ' + $Line
    Write-Host $text
    if ($script:log) {
        try {
            [System.IO.File]::AppendAllText($script:log, $text + "`n", (New-Object System.Text.ASCIIEncoding))
        } catch {
            $script:log = $null
        }
    }
}

try {
    $alHome = Get-AlInstallHome
    if ($alHome) {
        $py = Get-AlInstalledPython $alHome
        $lead = @((Join-Path $Repo 'boot.py'))
        $work = @((Join-Path $Repo 'boot.py'), 'server.al.install', 'calc', '--opt-in')
    } else {
        $py = Get-AlPython
        $lead = @('-m')
        $work = @((Join-Path $Repo 'tools\tc_pin.py'), 'setup', '--opt-in')
    }
} catch {
    Write-Host ('calc setup: ' + $_.Exception.Message)
    exit 1
}

$rc = $null
Push-Location $Repo
try {
    try {
        $paths = ((& $py @lead 'server.al.paths') -join "`n") | ConvertFrom-Json
        New-Item -ItemType Directory -Force -Path $paths.logs | Out-Null
        $log = Join-Path $paths.logs 'calc_setup.log'
    } catch {
        $log = $null
    }
    Write-AlCalcLog 'calc setup: started (decision 0018 opt-in from the client)'
    $ErrorActionPreference = 'Continue'
    & $py @work | ForEach-Object { Write-AlCalcLog ('calc setup: ' + $_) }
    $rc = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
} finally {
    Pop-Location
}
if ($null -eq $rc) { $rc = 1 }
if ($rc -eq 0) {
    Write-AlCalcLog 'calc setup: done'
} elseif ($rc -eq 2) {
    Write-AlCalcLog 'calc setup: REFUSED (pin or hash mismatch); the calc setting is unchanged'
} else {
    Write-AlCalcLog "calc setup: failed (rc $rc)"
}
exit $rc
