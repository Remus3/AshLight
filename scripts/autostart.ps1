<#
.SYNOPSIS
  Opt-in logon autostart of AshLight (CORE-AUTOSTART, decision 0011).
  Windows PowerShell 5.1 compatible. OFF by default.
.DESCRIPTION
  -Enable registers a current-user scheduled task "AshLight Autostart"
  (trigger: at this user's logon, 30 s delay; run level Limited, no admin
  rights) whose action runs scripts\autostart_launch.vbs through wscript.exe,
  which starts scripts\run.ps1 -NoBrowser -Autostart hidden (no console
  flash). The opt-in is recorded in the gitignored ops\runtime\autostart.json;
  run.ps1 -Autostart honours it (a task left behind after -Disable is a no-op).
  -Disable removes the task and records the opt-out. -Status prints both.
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

$Repo = Split-Path -Parent $PSScriptRoot
$TaskName = 'AshLight Autostart'
$TaskPath = '\'
$Delay = 'PT30S'
$Launcher = Join-Path $PSScriptRoot 'autostart_launch.vbs'
$Wscript = Join-Path $env:SystemRoot 'System32\wscript.exe'
$UserId = $env:USERNAME
if ($env:USERDOMAIN) { $UserId = $env:USERDOMAIN + '\' + $env:USERNAME }

function Get-AlPython {
    foreach ($name in @('python', 'py')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    throw 'Python 3.11 or newer was not found on PATH.'
}

# The one path resolver (server\al\paths.py; AL_RUNTIME_DIR moves it in tests).
$py = Get-AlPython
Push-Location $Repo
try {
    $paths = ((& $py -m server.al.paths) -join "`n") | ConvertFrom-Json
} finally {
    Pop-Location
}
$OptinFile = Join-Path $paths.runtime 'autostart.json'

function Get-AlDefinition {
    return [ordered]@{
        task_name         = $TaskName
        task_path         = $TaskPath
        description       = 'AshLight: start the local core at logon (opt-in; scripts\autostart.ps1 -Disable removes it).'
        user              = $UserId
        logon_type        = 'Interactive'
        run_level         = 'Limited'
        trigger           = 'AtLogOn'
        trigger_user      = $UserId
        delay             = $Delay
        execute           = $Wscript
        arguments         = '//B //NoLogo "' + $Launcher + '"'
        working_directory = $Repo
        launcher          = $Launcher
        run_ps1_args      = @('-NoBrowser', '-Autostart')
        window            = 'hidden'
        optin_file        = $OptinFile
    }
}

function Get-AlTask {
    try {
        return Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction Stop
    } catch {
        return $null
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
    $task = Get-AlTask
    $out = [ordered]@{
        optin           = (Read-AlOptin)
        task_registered = ($null -ne $task)
        task_state      = $(if ($task) { [string]$task.State } else { '' })
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
    if (-not (Test-Path -LiteralPath $Launcher)) { throw "launcher missing: $Launcher" }
    $existing = Get-AlTask
    $same = $false
    if ($existing) {
        $act = @($existing.Actions)[0]
        $same = ($act.Execute -eq $def.execute -and $act.Arguments -eq $def.arguments)
    }
    if (-not $same) {
        $action = New-ScheduledTaskAction -Execute $def.execute -Argument $def.arguments `
            -WorkingDirectory $def.working_directory
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $UserId
        $trigger.Delay = $Delay
        $principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
        Register-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Action $action `
            -Trigger $trigger -Principal $principal -Settings $settings `
            -Description $def.description -Force | Out-Null
        Write-Host "autostart: task '$TaskName' registered (at logon of $UserId, delay $Delay)"
    } else {
        Write-Host "autostart: task '$TaskName' already registered (no-op)"
    }
    Write-AlOptin $true
    Write-Host "autostart: opt-in recorded in $OptinFile"
    exit 0
}

if ($Disable) {
    $existing = Get-AlTask
    if ($DryRun) {
        $plan = [ordered]@{
            dry_run      = $true
            task_name    = $TaskName
            task_path    = $TaskPath
            would_remove = ($null -ne $existing)
            optin_file   = $OptinFile
            registered   = $false
        }
        $plan | ConvertTo-Json -Compress
        Write-Host 'autostart: DRYRUN - nothing removed, opt-out not recorded'
        exit 0
    }
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
        Write-Host "autostart: task '$TaskName' removed"
    } else {
        Write-Host "autostart: no task '$TaskName' registered (no-op)"
    }
    Write-AlOptin $false
    Write-Host "autostart: opt-out recorded in $OptinFile"
    exit 0
}
