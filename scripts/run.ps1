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
  sidecar Logs dir. OVL-ELECTRON-SETUP (decision 0068): electron.exe is
  checked against config/electron_pin.json (tools/electron_pin.py
  verify-exe; a full hash only when its size or mtime changed) before the
  client starts; a changed exe is refused, the dashboard opens in the
  browser instead and the log names the fix (run scripts\setup.ps1 again).
  REL-INSTALLED-RUN-CHECK: an installed copy ships no tools\electron_pin.py;
  there run.ps1 checks the private runtime's electron.exe itself against
  the shipped config\electron_pin.json entry whose zip SHA-256 the runtime
  folder's install marker (ashlight-runtime.json) records, with the same
  size-or-mtime fast path (<home>\build\electron-exe-installed.json), and
  a refusal names the installer repair, never setup.ps1.
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
  starts nothing unless the recorded opt-in (ops\runtime\autostart.json)
  says enabled; then, with the client installed, the client starts
  tray-only (--client --tray: tray and overlay, no companion window,
  REL-AUTOSTART-TRAY), without it the core and supervisor only. Never
  opens the browser.
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
# REL-RUNTIME-SCRIPTS (F-047, DEP-06): Python, Electron and the paths come
# from scripts\al_env.ps1 only; in an installed copy that is the private
# runtime and <payload>\boot.py, in a checkout PATH Python and -m.
. (Join-Path $PSScriptRoot 'al_env.ps1')

$py = Get-AlPython
if ($Port -ne 0) {
    if ($Port -lt 8960 -or $Port -gt 8979) { throw "-Port $Port is outside AshLight's port block 8960-8979." }
    $env:AL_PORT = [string]$Port
}
$paths = Get-AlPaths
# The port rule (server\al\ports.py resolve). -c with the root put first on
# sys.path: the same line works under the private runtime, whose ._pth
# ignores the current folder.
Push-Location -LiteralPath $AlEnvRoot
try {
    $port = [int]((& $py -c "import os, sys; sys.path.insert(0, sys.argv[1]); from server.al import paths, ports; print(ports.resolve(os.environ, paths.load_local_config()))" $AlEnvRoot) -join '').Trim()
} finally {
    Pop-Location
}
foreach ($dir in @($paths.runtime, $paths.logs, $paths.temp)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
$log = Join-Path $paths.logs 'run.log'

# RUN-OBS-LOGS-SHELL (F-090): run.log (run.ps1 and stop.ps1) is bounded and
# in the one line format of AshLight's logs (server\al\logs.py): over 1 MB
# at start it moves to run.log.1 (one old file kept; a move that fails, the
# file held open elsewhere, keeps appending), every line is
# '<UTC ISO stamp> <LEVEL> run[<pid>] <message>' and each start opens with
# the build banner (server\al\buildinfo.py build_id, version plus 12 hex).
function Add-AlRunLine([string]$Path, [string]$Level, [string]$Name, [string]$Message) {
    $stamp = [DateTime]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'",
        [System.Globalization.CultureInfo]::InvariantCulture)
    Add-Content -Path $Path -Value ($stamp + ' ' + $Level + ' ' + $Name + '[' + $PID + '] ' + $Message) -Encoding ASCII
}

function Get-AlBuildId {
    $ErrorActionPreference = 'Continue'
    $b = ''
    Push-Location -LiteralPath $AlEnvRoot
    try {
        $b = ((& $py -c "import sys; sys.path.insert(0, sys.argv[1]); from server.al import buildinfo; print(buildinfo.build_id())" $AlEnvRoot 2>$null) -join '').Trim()
    } catch {
        $b = ''
    } finally {
        Pop-Location
    }
    if ($b -match '^[0-9A-Za-z.+-]{1,64}$') { return $b }
    return 'unknown'
}

function Start-AlRunLog([string]$Path, [string]$Name, [string]$Build) {
    $old = $Path + '.1'
    try {
        if ((Test-Path -LiteralPath $Path -PathType Leaf) -and ((Get-Item -LiteralPath $Path).Length -gt 1048576)) {
            if (Test-Path -LiteralPath $old -PathType Leaf) {
                [System.IO.File]::Replace($Path, $old, [NullString]::Value)
            } else {
                [System.IO.File]::Move($Path, $old)
            }
        }
    } catch {
        # held open elsewhere: keep appending to the old file
    }
    Add-AlRunLine $Path 'INFO' $Name ("AshLight $Build $Name start (pid $PID, powershell " + [string]$PSVersionTable.PSVersion + ')')
}

Start-AlRunLog $log 'run' (Get-AlBuildId)

# The client's Electron (Get-AlElectron): the checkout's npm ci dist, or the
# installed copy's private runtime; '' when the install marker names none.
$electron = [string](Get-AlElectron)
# REL-INSTALLED-RUN-CHECK: the install home ($null in a checkout) picks the
# electron.exe check route and the fix the log lines name.
$alInstallHome = Get-AlInstallHome
$haveElectron = [bool]($electron -and (Test-Path -LiteralPath $electron -PathType Leaf))

# CORE-AUTOSTART (decision 0011): the logon task passes -Autostart; the
# recorded opt-in decides, so a task left behind after -Disable is a no-op.
# REL-AUTOSTART-TRAY (decision 0011 amendment 2026-11-18): with the client
# installed the logon start is the client tray-only (--client --tray: tray
# and overlay, the overlay gated by the log, no companion window); without
# it the core stays alone. A logon start never opens the browser.
$trayOnly = $false
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
    Add-AlRunLine $log 'INFO' 'run' "run: logon autostart, opt-in $state"
    if (-not $optin) { exit 0 }
    # the client is installed when its electron.exe (Get-AlElectron) is there
    if ($haveElectron) {
        $trayOnly = $true
        $mode = 'client tray-only'
    } else {
        $mode = 'core only (client not installed)'
    }
    Add-AlRunLine $log 'INFO' 'run' "run: logon start, $mode"
}

function Write-AlLog([string]$Message, [string]$Level = 'INFO') {
    $stamp = [DateTime]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'",
        [System.Globalization.CultureInfo]::InvariantCulture)
    $line = $stamp + ' ' + $Level + ' run[' + $PID + '] ' + $Message
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

# RUN-START-REASON-CLIENT (F-091): the core's one-line reason for a start
# that could not bind its port (ops\runtime\start-error.json "fix", written
# by server\al\__main__.py), when the record is no older than $Since (UNIX
# seconds); '' otherwise. Printable ASCII, at most 300 characters.
function Get-AlStartError([double]$Since) {
    $file = Join-Path $paths.runtime 'start-error.json'
    try {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { return '' }
        if ((Get-Item -LiteralPath $file).Length -gt 4096) { return '' }
        $doc = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json
        $at = [double]$doc.at
        $fix = ([string]$doc.fix).Trim()
    } catch {
        return ''
    }
    if ($at -lt $Since) { return '' }
    if (-not $fix -or $fix.Length -gt 300 -or $fix -notmatch '^[\x20-\x7e]+$') { return '' }
    return $fix
}

function Get-AlUnixNow {
    return ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0)
}

# Wait up to 15 s for the core to answer. A fresh start-error record ends
# the wait at once and its line is printed; $false when the core is not up.
function Wait-AlCore([double]$Since) {
    $deadline = (Get-Date).AddSeconds(15)
    while (-not (Test-AlHealth)) {
        $why = Get-AlStartError $Since
        if ($why) {
            Write-AlLog "run: core did not start: $why" 'ERROR'
            return $false
        }
        if ((Get-Date) -gt $deadline) {
            Write-AlLog "run: core did not answer on 127.0.0.1:$port within 15 s; see $($paths.core_log)" 'ERROR'
            return $false
        }
        Start-Sleep -Milliseconds 250
    }
    return $true
}

$env:TEMP = $paths.temp
$env:TMP = $paths.temp
$env:AL_SIDECAR_ROOT = $paths.sidecar

# A stop.request left by scripts\stop.ps1 must not stop this start.
Remove-Item -LiteralPath (Join-Path $paths.runtime 'stop.request') -Force -ErrorAction SilentlyContinue

# The core and the supervisor run windowless (pythonw when there is one):
# Get-AlPythonCmd -Windowless gives the exe and the -m / boot.py form.
$exe = Get-AlPython -Windowless
$detachEnv = @{ TEMP = $paths.temp; TMP = $paths.temp; AL_SIDECAR_ROOT = $paths.sidecar; AL_PORT = [string]$port }
$clientUnset = @('ELECTRON_RUN_AS_NODE', 'NODE_OPTIONS')

# The arguments after the exe of a windowless Python child, quoted for one
# command line (scripts\al_detach.ps1).
function Get-AlDetachArgs([string]$Module, [string[]]$ArgList) {
    $cmd = Get-AlPythonCmd -Module $Module -ArgList $ArgList -Windowless
    return (Format-AlArgs $cmd[1..($cmd.Count - 1)])
}

function Get-AlPlan {
    # Which of core / supervisor / overlay must start (server\al\procs.py).
    # The script passes the command from Get-AlPythonCmd (boot.py under the
    # private runtime in an install); the default is the checkout form, for
    # a caller that loads this function alone with $py and $Repo set.
    param([string[]]$PlanCmd = @($py, '-m', 'server.al.procs', 'plan'))
    $planArgs = @($PlanCmd | Select-Object -Skip 1)
    if (-not $wantOverlay) { $planArgs += '--no-overlay' }
    if (-not ($electron -and (Test-Path -LiteralPath $electron -PathType Leaf))) {
        $planArgs += '--overlay-missing'
    }
    Push-Location -LiteralPath $Repo
    try {
        return ((& $PlanCmd[0] @planArgs) -join "`n") | ConvertFrom-Json
    } finally {
        Pop-Location
    }
}

# OVL-ELECTRON-SETUP (F-044, decision 0068): the client starts only from
# an electron.exe that matches its pin. tools/electron_pin.py verify-exe
# hashes the exe in full only when its size or mtime changed since the
# last good check (sidecar Build\electron-exe-check.json, shared with
# setup.ps1); ok only with exit 0 and its "electron.exe ok" line (a
# machine no pin covers has no trusted exe).
function Test-AlElectronExe {
    # REL-INSTALLED-RUN-CHECK: an installed copy has no tools\electron_pin.py
    $inst = Get-Variable -Name alInstallHome -ValueOnly -ErrorAction SilentlyContinue
    if ($inst) {
        return (Test-AlInstalledElectronExe -Exe $electron `
            -PinFile (Join-Path $AlEnvRoot 'config\electron_pin.json') `
            -CheckFile (Join-Path ([string]$paths.build) 'electron-exe-installed.json'))
    }
    $ErrorActionPreference = 'Continue'
    $out = @()
    $rc = 1
    Push-Location $Repo
    try {
        $out = @(& $py (Join-Path $Repo 'tools\electron_pin.py') 'verify-exe' '--exe' $electron 2>&1 |
            ForEach-Object { [string]$_ })
        $rc = $LASTEXITCODE
    } catch {
        $out = @([string]$_)
        $rc = 1
    } finally {
        Pop-Location
    }
    foreach ($line in $out) {
        if ($line) { Write-AlLog "run: electron: $line" }
    }
    return ($rc -eq 0 -and [bool](@($out) -match '^electron\.exe ok'))
}

# REL-INSTALLED-RUN-CHECK: a small JSON file as an object, or $null when it
# is missing, larger than 64 KB or not JSON.
function Read-AlSmallJson([string]$Path) {
    try {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
        if ((Get-Item -LiteralPath $Path).Length -gt 65536) { return $null }
        return ((Get-Content -LiteralPath $Path -Raw) | ConvertFrom-Json)
    } catch {
        return $null
    }
}

function Get-AlJsonField($Doc, [string]$Name) {
    if ($null -eq $Doc -or -not ($Doc.PSObject.Properties.Name -contains $Name)) { return $null }
    return $Doc.$Name
}

# REL-INSTALLED-RUN-CHECK (decisions 0063, 0068): the installed copy's check
# of its private electron.exe, with no Python and no tools\electron_pin.py
# (config\ship_list.json ships neither the tool nor its cache helpers).
# The runtime folder's install marker (ashlight-runtime.json, written by the
# installer after the pinned zip's size and SHA-256 matched) names the zip;
# the shipped config\electron_pin.json arch entry with that zip_sha256 gives
# exe_size and exe_sha256. The size is checked every start; the full SHA-256
# runs only when size or mtime changed since the last good check recorded in
# CheckFile. Ok only when every step holds; each result is one log line.
function Test-AlInstalledElectronExe([string]$Exe, [string]$PinFile, [string]$CheckFile) {
    $ErrorActionPreference = 'Continue'
    $why = $null
    $spec = $null
    $marker = Read-AlSmallJson (Join-Path (Split-Path -Parent $Exe) 'ashlight-runtime.json')
    $pin = Read-AlSmallJson $PinFile
    $zipSha = [string](Get-AlJsonField $marker 'sha256')
    if ($null -eq $marker -or [string](Get-AlJsonField $marker 'name') -ne 'electron' -or
        $zipSha -cnotmatch '^[0-9a-f]{64}$') {
        $why = 'the Electron runtime has no valid install marker'
    } elseif ($null -eq $pin -or $null -eq (Get-AlJsonField $pin 'arch')) {
        $why = 'config\electron_pin.json is missing or unreadable'
    } elseif ([string](Get-AlJsonField $marker 'version') -cne [string](Get-AlJsonField $pin 'version')) {
        $why = 'the Electron runtime is not the version this release pins'
    } else {
        $arches = Get-AlJsonField $pin 'arch'
        foreach ($p in @($arches.PSObject.Properties)) {
            if ([string](Get-AlJsonField $p.Value 'zip_sha256') -ceq $zipSha) { $spec = $p.Value }
        }
        if ($null -eq $spec) { $why = 'no pinned Electron zip matches the runtime' }
    }
    $wantSha = [string](Get-AlJsonField $spec 'exe_sha256')
    $wantSize = Get-AlJsonField $spec 'exe_size'
    if (-not $why -and ($wantSha -cnotmatch '^[0-9a-f]{64}$' -or -not ($wantSize -is [int] -or $wantSize -is [long]) -or
            [long]$wantSize -le 0)) {
        $why = 'the Electron pin entry is malformed'
    }
    $item = $null
    if (-not $why) {
        $item = Get-Item -LiteralPath $Exe -ErrorAction SilentlyContinue
        if ($null -eq $item -or $item.PSIsContainer) {
            $why = 'electron.exe missing'
        } elseif ([long]$item.Length -ne [long]$wantSize) {
            $why = 'electron.exe size ' + $item.Length + ' differs from the pinned ' + $wantSize
        }
    }
    if ($why) {
        Write-AlLog "run: electron: refused: $why"
        return $false
    }
    $key = [System.IO.Path]::GetFullPath($Exe)
    $ticks = [long]$item.LastWriteTimeUtc.Ticks
    $last = Read-AlSmallJson $CheckFile
    if ($null -ne $last -and [string](Get-AlJsonField $last 'path') -ieq $key -and
        [string](Get-AlJsonField $last 'sha256') -ceq $wantSha -and
        [string](Get-AlJsonField $last 'size') -eq [string]$item.Length -and
        [string](Get-AlJsonField $last 'mtime_ticks') -eq [string]$ticks) {
        Write-AlLog 'run: electron: electron.exe ok (unchanged since last check)'
        return $true
    }
    $got = ''
    try {
        $got = ([string](Get-FileHash -LiteralPath $Exe -Algorithm SHA256).Hash).ToLowerInvariant()
    } catch {
        $got = ''
    }
    if ($got -cne $wantSha) {
        Write-AlLog 'run: electron: refused: electron.exe sha256 differs from the pinned one'
        return $false
    }
    try {
        $dir = Split-Path -Parent $CheckFile
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        $doc = [ordered]@{ path = $key; sha256 = $got; size = [long]$item.Length; mtime_ticks = $ticks }
        $tmp = $CheckFile + '.tmp'
        [System.IO.File]::WriteAllText($tmp, (($doc | ConvertTo-Json) -replace "`r`n", "`n") + "`n",
            [System.Text.Encoding]::ASCII)
        Move-Item -LiteralPath $tmp -Destination $CheckFile -Force
    } catch {
        # the record is only a fast path; the next start hashes again
    }
    Write-AlLog 'run: electron: electron.exe ok (hashed)'
    return $true
}
# DESKTOP-CLIENT (decision 0041): the "overlay" component is the client
# process; it is wanted only when a window is wanted and the browser is not.
$wantOverlay = -not ($NoOverlay -or $NoBrowser -or $Browser -or $EdgeApp)
# REL-AUTOSTART-TRAY: the logon start wants the client (tray-only), no browser
if ($trayOnly) { $wantOverlay = $true }
$plan = Get-AlPlan -PlanCmd (Get-AlPythonCmd -Module 'server.al.procs' -ArgList @('plan'))

# RUN-SECOND-LINE-PY (F-127, decision 0005 amendment 2026-11-18): the
# supervisor starts right after the core and BEFORE the health wait, handed
# the new core's pid (--adopt-pid: watched as a starting core for 60 s), so
# a slow core start still ends with one core and a supervisor; a core that
# finds no supervisor later starts one itself (server\al\plug\secondline.py).
$corePid = 0
$waitSince = -1
if (Test-AlHealth) {
    Write-AlLog "run: core already running on 127.0.0.1:$port (no-op)"
} elseif ($plan.status.core.live) {
    Write-AlLog "run: core pid $($plan.status.core.pid) is starting; waiting for it"
    # started by someone else just before: its record may be up to 60 s old
    $waitSince = (Get-AlUnixNow) - 60
} else {
    # Detached via WMI (scripts\al_detach.ps1): the core must outlive this
    # script and whatever shell started it. --quiet: core.log is the record.
    $coreArgs = Get-AlDetachArgs 'server.al' @('--quiet', '--port', [string]$port)
    $waitSince = (Get-AlUnixNow) - 1
    $corePid = Start-AlDetached -FilePath $exe -ArgumentList $coreArgs `
        -WorkingDirectory $AlEnvRoot -Environment $detachEnv
    Write-AlLog "run: core launched detached (pid $corePid)"
}

# CORE-KEEPALIVE: a detached supervisor restarts the core if it dies
# (decision 0005). It adopts the running core, or the one just launched
# (--adopt-pid). Started only when no supervisor holds its single-instance
# lock (OPS-RUN-IDEMP), so a re-run never spawns a second one. Log:
# Logs\keepalive.log.
if (@($plan.start) -contains 'supervisor') {
    $supList = @('--port', [string]$port)
    if ([int]$corePid -gt 0) { $supList += @('--adopt-pid', [string]$corePid) }
    $supArgs = Get-AlDetachArgs 'server.al.keepalive' $supList
    $supPid = Start-AlDetached -FilePath $exe -ArgumentList $supArgs `
        -WorkingDirectory $AlEnvRoot -Environment $detachEnv
    Write-AlLog "run: keepalive supervisor launched (pid $supPid; stop with scripts\stop.ps1)"
} else {
    Write-AlLog "run: keepalive supervisor already running (no-op)"
}

if ($waitSince -ge 0) {
    # a core that is slow to answer stays watched by the supervisor
    if (-not (Wait-AlCore $waitSince)) { exit 1 }
    if ([int]$corePid -gt 0) { Write-AlLog "run: core started on 127.0.0.1:$port" }
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
} elseif (-not $haveElectron) {
    # REL-INSTALLED-RUN-CHECK: an installed copy names the installer
    $fix = 'run scripts\setup.ps1 with Node 22.12.0 or newer'
    if ($alInstallHome) { $fix = 'run the installer repair (re-run the install line)' }
    Write-AlLog "run: client not installed - $fix"
} elseif ($trayOnly -and -not (@($plan.start) -contains 'overlay')) {
    # a live client is left alone: a second --client start would show its window
    Write-AlLog "run: client already running (pid $($plan.status.overlay.pid)); logon start leaves it alone"
} elseif (-not (Test-AlElectronExe)) {
    # refused: never start an exe that is not the pinned one; an installed
    # copy has no setup.ps1 route, so its line names the installer repair
    $fix = 'run scripts\setup.ps1 again to restore it'
    if ($alInstallHome) { $fix = 'run the installer repair (re-run the install line) to restore it' }
    Write-AlLog "run: client NOT started - electron.exe is not the pinned one; $fix"
} else {
    # The app folder (<root>\app: the repository's app\ or the payload's) is
    # the first argument in both modes, never a resources\app folder: the
    # installed Electron is the unmodified zip (decision 0063).
    $appDir = Join-Path $AlEnvRoot 'app'
    $clientArgs = @(Format-AlArgs @($appDir, '--client'))
    if ($trayOnly) { $clientArgs += '--tray' }
    # OVL-LAUNCH-ENV (F-110): an inherited ELECTRON_RUN_AS_NODE or
    # NODE_OPTIONS would turn electron.exe into a Node script host before any
    # app code runs; the client never gets either.
    $ovlPid = Start-AlDetached -FilePath $electron -ArgumentList $clientArgs `
        -WorkingDirectory $appDir -Environment $detachEnv -Unset $clientUnset
    $clientShown = $true
    if (@($plan.start) -contains 'overlay') {
        Invoke-AlPython server.al.procs record-overlay ([string]$ovlPid)
        $recRc = $LASTEXITCODE
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

if ($clientShown -and $trayOnly) {
    Write-AlLog 'run: AshLight client started in the tray (logon; no window)'
} elseif ($clientShown) {
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
