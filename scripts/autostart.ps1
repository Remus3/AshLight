<#
.SYNOPSIS
  Opt-in logon autostart of AshLight (CORE-AUTOSTART, decision 0011).
  Windows PowerShell 5.1 compatible. OFF by default.
.DESCRIPTION
  -Enable registers a current-user scheduled task "AshLight Autostart"
  (trigger: at this user's logon, 30 s delay; run level Limited, no admin
  rights) whose action runs pythonw.exe -m server.al.autostart_entry from
  the checkout root (REL-AUTOSTART-ENTRY). pythonw has no console, and the
  entry point starts scripts\run.ps1 -Autostart with no window (no console
  flash), which starts the desktop client tray-only (--client --tray: tray
  and overlay, no companion window; REL-AUTOSTART-TRAY) when it is
  installed, else the core alone. The opt-in is recorded in the gitignored
  ops\runtime\autostart.json; the entry point and run.ps1 -Autostart both
  honour it (a task left behind after -Disable is a no-op).
  -Disable removes the task and records the opt-out. -Status prints both.
  The task itself is written, read back and removed by scripts\al_shell.ps1
  (Register-AlLogonTask / Unregister-AlLogonTask / Get-AlLogonTask); a task
  of the same name whose action points outside this checkout is left alone.
  Every action is idempotent. Enabling is a deliberate operator act.
.PARAMETER Enable
  Register the task and record the opt-in.
.PARAMETER Disable
  Remove the task and record the opt-out.
.PARAMETER Status
  Print the opt-in record and whether the task is registered (read only).
.PARAMETER DryRun
  With -Enable or -Disable: print the task definition / the removal as JSON
  and change nothing (no task registered or removed, no opt-in file written).
#>
[CmdletBinding()]
param(
    [switch]$Enable,
    [switch]$Disable,
    [switch]$Status,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$picked = @($Enable, $Disable, $Status) | Where-Object { $_ }
if (@($picked).Count -ne 1) {
    Write-Host 'usage: autostart.ps1 -Enable | -Disable | -Status [-DryRun]'
    exit 2
}

. (Join-Path $PSScriptRoot 'al_shell.ps1')

$Repo = Split-Path -Parent $PSScriptRoot
$TaskName = 'AshLight Autostart'
$TaskPath = (Get-AlShellPlaces).TaskPath
$Delay = 'PT30S'
$Description = 'AshLight: start AshLight in the tray at logon (opt-in; scripts\autostart.ps1 -Disable removes it).'
$UserId = $env:USERNAME
if ($env:USERDOMAIN) { $UserId = $env:USERDOMAIN + '\' + $env:USERNAME }

function Get-AlPython {
    foreach ($name in @('python', 'py')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    throw 'Python 3.11 or newer was not found on PATH.'
}

# The one path resolver (server\al\paths.py; AL_RUNTIME_DIR moves it in
# tests) and the task action from the entry point itself (paths.python_cmd).
$py = Get-AlPython
Push-Location $Repo
try {
    $paths = ((& $py -m server.al.paths) -join "`n") | ConvertFrom-Json
    $taskAction = ((& $py -m server.al.autostart_entry --task-action) -join "`n") | ConvertFrom-Json
} finally {
    Pop-Location
}
$OptinFile = Join-Path $paths.runtime 'autostart.json'

function Get-AlDefinition {
    $exe = [string]$taskAction.execute
    $window = 'console'
    if ((Split-Path -Leaf $exe) -ieq 'pythonw.exe') { $window = 'hidden' }
    return [ordered]@{
        task_name         = $TaskName
        task_path         = $TaskPath
        description       = $Description
        user              = $UserId
        logon_type        = 'Interactive'
        run_level         = 'Limited'
        trigger           = 'AtLogOn'
        trigger_user      = $UserId
        delay             = $Delay
        execute           = $exe
        arguments         = [string]$taskAction.arguments
        working_directory = [string]$taskAction.working_directory
        launcher          = [string]$taskAction.launcher
        run_ps1_args      = @('-Autostart')
        client_args       = @('--client', '--tray')
        logon_start       = 'tray client (core only without the client)'
        window            = $window
        optin_file        = $OptinFile
    }
}

function Read-AlOptin {
    if (-not (Test-Path -LiteralPath $OptinFile)) { return $false }
    try {
        $o = (Get-Content -LiteralPath $OptinFile -Raw) | ConvertFrom-Json
        return [bool]$o.enabled
    } catch {
        return $false
    }
}

function Write-AlOptin([bool]$On) {
    New-Item -ItemType Directory -Force -Path $paths.runtime | Out-Null
    $rec = [ordered]@{
        enabled = $On
        task    = $TaskPath + $TaskName
        updated = (Get-Date -Format 's')
    }
    $json = ($rec | ConvertTo-Json -Compress) + "`n"
    [System.IO.File]::WriteAllText($OptinFile, $json, (New-Object System.Text.ASCIIEncoding))
}

if ($Status) {
    $task = Get-AlLogonTask -TaskName $TaskName
    $out = [ordered]@{
        optin           = (Read-AlOptin)
        task_registered = ($null -ne $task)
        task_ours       = ($null -ne $task -and (Test-AlTaskOurs -Task $task -OwnerRoot $Repo))
        task_state      = $(if ($task) { Get-AlTaskField -Object $task -Name 'State' } else { '' })
        optin_file      = $OptinFile
    }
    $out | ConvertTo-Json -Compress
    exit 0
}

$def = Get-AlDefinition

if ($Enable) {
    if ($DryRun) {
        $def['dry_run'] = $true
        $def['registered'] = $false
        $def | ConvertTo-Json -Compress
        Write-Host 'autostart: DRYRUN - nothing registered, opt-in not recorded'
        exit 0
    }
    if (-not (Test-Path -LiteralPath $def.launcher)) { throw "launcher missing: $($def.launcher)" }
    if ($def.window -ne 'hidden') {
        throw "pythonw.exe was not found beside $($def.execute); nothing registered"
    }
    $res = Register-AlLogonTask -TaskName $TaskName -Execute $def.execute -Arguments $def.arguments `
        -WorkDir $def.working_directory -UserId $UserId -Delay $Delay -Description $Description `
        -OwnerRoot $Repo
    if ($res -eq 'elsewhere') {
        Write-Host "autostart: a task '$TaskName' of another AshLight folder exists; left alone, opt-in not recorded"
        exit 3
    }
    if ($res -eq 'current') {
        Write-Host "autostart: task '$TaskName' already registered (no-op)"
    } else {
        Write-Host "autostart: task '$TaskName' registered (at logon of $UserId, delay $Delay)"
    }
    Write-AlOptin $true
    Write-Host "autostart: opt-in recorded in $OptinFile"
    exit 0
}

if ($Disable) {
    if ($DryRun) {
        $existing = Get-AlLogonTask -TaskName $TaskName
        $ours = ($null -ne $existing -and (Test-AlTaskOurs -Task $existing -OwnerRoot $Repo))
        $plan = [ordered]@{
            dry_run        = $true
            task_name      = $TaskName
            task_path      = $TaskPath
            would_remove   = $ours
            task_elsewhere = ($null -ne $existing -and -not $ours)
            optin_file     = $OptinFile
            registered     = $false
        }
        $plan | ConvertTo-Json -Compress
        Write-Host 'autostart: DRYRUN - nothing removed, opt-out not recorded'
        exit 0
    }
    $res = Unregister-AlLogonTask -TaskName $TaskName -OwnerRoot $Repo
    if ($res -eq 'removed') {
        Write-Host "autostart: task '$TaskName' removed"
    } elseif ($res -eq 'elsewhere') {
        Write-Host "autostart: the task '$TaskName' belongs to another AshLight folder; left alone"
    } else {
        Write-Host "autostart: no task '$TaskName' registered (no-op)"
    }
    Write-AlOptin $false
    Write-Host "autostart: opt-out recorded in $OptinFile"
    exit 0
}
