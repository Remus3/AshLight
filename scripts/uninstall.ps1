<#
.SYNOPSIS
  Uninstall an installed AshLight copy (DEP-10, decision 0066). Windows
  PowerShell 5.1 compatible, StrictMode 2 clean, self-contained: no
  dot-sourcing and no Python.
.DESCRIPTION
  Run as "<home>\uninstall.ps1" (the Apps and features button runs it with
  -NoProfile -ExecutionPolicy Bypass -File). Nothing is asked by default and
  the player's data in <home>\data is kept.

  1. Validate: install.json beside the script names "AshLight" with schema
     1, and the home passes the path-shape guard (no game library or game
     folder component). Else exit 2 with nothing touched. The script then
     re-runs itself from a copy in the user's temp folder, so the home can
     be removed.
  2. Stop: write <home>\data\stop.request, wait up to -WaitSec seconds for
     AshLight to exit by itself, then end only processes proven ours: a pid
     from our pid files (core.alive, keepalive.json, overlay.pid) whose
     recorded creation time matches, or a python, pythonw or electron
     process whose full image path lies under <home>\runtime\ (decision
     0010). Any other process is never touched.
  3. Logon task: the opt-in task "AshLight Autostart" (decision 0011) is
     unregistered only when its action's working directory (else its
     program) lies in the home. No other task name is ever asked for.
  4. Shortcuts: the two "AshLight.lnk" files (this user's Start Menu
     Programs and Desktop) are removed only when their target lies in the
     home.
  5. Uninstall key: the per-user Uninstall\AshLight key (HKCU) is removed
     only when its InstallLocation lies in the home.
     An item of steps 3 to 5 that points elsewhere is left alone and
     named; one that is ours but stays after its removal is counted in
     step 9. These fixed names are the only places outside the home the
     script reads: no listing, no other key and no other task.
  6. Delete by fixed name only: app, runtime, cache, logs, temp, build,
     staged, install.json, install.json.bak, and inside data the per-run
     files (token, pid files, stop.request, heartbeat, locks).
  7. Without -Purge data\ stays and uninstall.ps1 is removed. With -Purge
     data\ goes to the Recycle Bin, then the empty home is removed.
  8. The last lines say what stays and give one fixed sentence about the
     files the player may have copied elsewhere. The script never looks
     for them: no game folder is listed, stat-ed or opened.
  9. Exit 0 only when nothing but the kept data remains; else exit 1 with
     the one line "uninstall incomplete: <n> items remain" and a report in
     the user's temp folder.
  Checkout mode comes with REL-UNINSTALL-CHECKOUT.

  Every file probe, listing and delete goes through the Test-AlHomePath,
  Get-AlHomeChildren and Remove-AlHomeItem helpers, which refuse any path
  outside the home.

  Effect root (as scripts/al_shell.ps1): the env AL_SHELL_ROOT moves the
  Start Menu and Desktop to <root>\Programs and <root>\Desktop, the
  uninstall key to HKCU Software\AshLightShellScratch\<id>\Uninstall\AshLight
  and the task folder to \AshLightShellScratch\<id>\ (<id> from the root's
  path), for tests and the release stage round trip.

  Tests only: the env AL_UNINSTALL_FAKE names a JSON file that stands in
  for the process table, the Recycle Bin, the task scheduler ("tasks") and
  the registry ("keys"), so a test never lists, stops, recycles,
  unregisters or deletes anything real. It is refused without an effect
  root, so the only shortcuts a test run sees are its own scratch files.
.PARAMETER Purge
  Also remove <home>\data (to the Recycle Bin). Run by hand without -Yes it
  asks once for the typed word PURGE.
.PARAMETER Yes
  The consent for -Purge without the typed word.
.PARAMETER DryRun
  Print the plan and change nothing.
.PARAMETER Quiet
  Print only the last lines (never asks: -Purge then needs -Yes).
#>
[CmdletBinding()]
param(
    [switch]$Purge,
    [switch]$Yes,
    [switch]$DryRun,
    [switch]$Quiet,
    [int]$WaitSec = 10,
    # internal: set by the run that made the temp copy
    [string]$FromHome = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$script:MarkerName = 'install.json'
$script:CopyPrefix = 'AshLight-uninstall-'
$script:ReportName = 'AshLight-uninstall-report.txt'
$script:RefusedParts = @('steamapps', 'path of exile 2')
$script:DeleteNames = @('app', 'runtime', 'cache', 'logs', 'temp', 'build', 'staged',
    'install.json', 'install.json.bak')
$script:RunFiles = @('token', 'token.reuse', 'core.alive', 'keepalive.json',
    'keepalive.lock', 'overlay.pid', 'stop.request', 'restart.request', 'hotreload.json')
$script:PidFiles = @('core.alive', 'keepalive.json', 'overlay.pid')
$script:ImageNames = @('python', 'pythonw', 'electron')
$script:CopiedSentence = ("AshLight hands out ashlight.filter and its .build files as " +
    "downloads; if you copied them into the game's filter or planner folder, " +
    "they are still there.")
$script:Problems = New-Object System.Collections.ArrayList
# steps 3 to 5: the only names outside the home the script ever uses
$script:LinkName = 'AshLight.lnk'
$script:TaskName = 'AshLight Autostart'
$script:RealKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\AshLight'
$script:ScratchKeyBase = 'Software\AshLightShellScratch'
$script:ScratchTaskBase = '\AshLightShellScratch\'
$script:Shell = $null
$script:LinkPaths = @()
$script:ShellLeft = New-Object System.Collections.ArrayList
$script:HomeDir = ''
$script:Fake = [string]$env:AL_UNINSTALL_FAKE

function Write-AlStep([string]$Message) {
    if (-not $Quiet) { [Console]::Out.WriteLine('uninstall: ' + $Message) }
}

function Write-AlLast([string]$Message) {
    [Console]::Out.WriteLine($Message)
}

function Stop-AlRefused([string]$Message) {
    # Exit 2: nothing was touched.
    [Console]::Out.WriteLine('uninstall refused: ' + $Message)
    Remove-AlOwnCopy
    exit 2
}

function Get-AlFullPath([string]$Path) {
    if (-not $Path) { return '' }
    try {
        return [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    } catch {
        return ''
    }
}

function Test-AlUnder {
    # True when Path is Root or lies under it (full paths, case-insensitive).
    param([string]$Path, [string]$Root)
    $p = Get-AlFullPath $Path
    $r = Get-AlFullPath $Root
    if (-not $p -or -not $r) { return $false }
    if ($p.Equals($r, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    return $p.StartsWith($r + '\', [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-AlInHome([string]$Path) {
    if (-not $script:HomeDir -or -not (Test-AlUnder -Path $Path -Root $script:HomeDir)) {
        throw "uninstall: $Path is outside the home; refused"
    }
}

function Test-AlHomePath {
    param([string]$Path, [switch]$Leaf)
    Assert-AlInHome $Path
    if ($Leaf) { return (Test-Path -LiteralPath $Path -PathType Leaf) }
    return (Test-Path -LiteralPath $Path)
}

function Get-AlHomeChildren {
    param([string]$Path, [switch]$Recurse)
    Assert-AlInHome $Path
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { return @() }
    if ($Recurse) {
        return @(Get-ChildItem -LiteralPath $Path -Force -Recurse -ErrorAction SilentlyContinue)
    }
    return @(Get-ChildItem -LiteralPath $Path -Force -ErrorAction SilentlyContinue)
}

function Remove-AlHomeItem {
    # A direct delete of one fixed-name item in the home (-Empty: the home
    # itself, only when it is empty); a failure is recorded, never fatal
    # (step 9 counts what remains).
    param([string]$Path, [switch]$Empty)
    Assert-AlInHome $Path
    if (-not (Test-Path -LiteralPath $Path)) { return }
    try {
        if ($Empty) {
            if (@(Get-ChildItem -LiteralPath $Path -Force).Count -gt 0) { return }
            Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
        } else {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
        }
    } catch {
        [void]$script:Problems.Add("could not delete ${Path}: " + $_.Exception.Message)
    }
}

function Get-AlHomeRefusal([string]$HomePath) {
    # The path-shape guard of server/al/paths.py home_refusal: path text
    # only, no registry read and no listing.
    if (-not $HomePath -or -not [System.IO.Path]::IsPathRooted($HomePath)) {
        return 'the home is not an absolute path'
    }
    $full = Get-AlFullPath $HomePath
    if (-not $full) { return 'the home is not a usable path' }
    $rootOnly = [System.IO.Path]::GetPathRoot($full).TrimEnd('\')
    if ($full.Equals($rootOnly, [System.StringComparison]::OrdinalIgnoreCase)) {
        return 'the home may not be a drive root'
    }
    foreach ($part in ($full -split '[\\/]+')) {
        $p = $part.TrimEnd('. ').ToLowerInvariant()
        if ($script:RefusedParts -contains $p) {
            return "the home may not lie in a '$part' folder"
        }
    }
    return ''
}

function Test-AlMarker([string]$HomePath) {
    # '' when <home>\install.json is AshLight's marker, else the reason.
    $marker = Join-Path $HomePath $script:MarkerName
    if (-not (Test-AlHomePath $marker -Leaf)) {
        return 'no install.json beside the script (this is not an AshLight install home)'
    }
    try {
        $doc = (Get-Content -LiteralPath $marker -Raw -Encoding UTF8) | ConvertFrom-Json
    } catch {
        return 'install.json is not readable JSON'
    }
    if ($null -eq $doc -or -not ($doc -is [System.Management.Automation.PSCustomObject])) {
        return 'install.json is not a JSON object'
    }
    $names = @($doc.PSObject.Properties | ForEach-Object { $_.Name })
    if (($names -notcontains 'name') -or ($doc.name -isnot [string]) -or ($doc.name -cne 'AshLight')) {
        return 'install.json does not name AshLight'
    }
    if (($names -notcontains 'schema') -or -not (($doc.schema -is [int]) -or ($doc.schema -is [long])) -or
            ($doc.schema -ne 1)) {
        return 'install.json has an unknown schema'
    }
    return ''
}

# --- processes (step 2) -------------------------------------------------------

function Read-AlFake {
    $doc = (Get-Content -LiteralPath $script:Fake -Raw -Encoding UTF8) | ConvertFrom-Json
    return $doc
}

function Save-AlFake($Doc) {
    $text = $Doc | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($script:Fake, $text + "`n", (New-Object System.Text.UTF8Encoding($false)))
}

function Get-AlProcessTable {
    # Candidate processes as {pid, path, created}: those named in our pid
    # files and those whose image is python, pythonw or electron. Real mode
    # asks Windows by name or by pid only; it never opens another process.
    param([int[]]$Pids)
    $out = @()
    if ($script:Fake) {
        $doc = Read-AlFake
        $stopRequested = Test-AlHomePath (Join-Path (Join-Path $script:HomeDir 'data') 'stop.request')
        foreach ($p in @($doc.processes)) {
            if ($null -eq $p) { continue }
            if ($stopRequested -and [bool]$p.graceful) { continue }
            $out += [pscustomobject]@{ Pid = [int]$p.pid; Path = [string]$p.path; Created = [long]$p.created }
        }
        return $out
    }
    $seen = @{}
    $procs = @(Get-Process -Name $script:ImageNames -ErrorAction SilentlyContinue)
    foreach ($id in $Pids) {
        if ($id -gt 0) { $procs += @(Get-Process -Id $id -ErrorAction SilentlyContinue) }
    }
    foreach ($proc in $procs) {
        if ($null -eq $proc -or $seen.ContainsKey($proc.Id)) { continue }
        $seen[$proc.Id] = $true
        $path = ''
        $created = [long]0
        try { $path = [string]$proc.Path } catch { $path = '' }
        try { $created = [long]$proc.StartTime.ToFileTimeUtc() } catch { $created = [long]0 }
        $out += [pscustomobject]@{ Pid = [int]$proc.Id; Path = $path; Created = $created }
    }
    return $out
}

function Get-AlPidRecords {
    # {pid, created} from the pid files in data\ (unreadable ones skipped).
    $data = Join-Path $script:HomeDir 'data'
    $out = @()
    foreach ($name in $script:PidFiles) {
        $file = Join-Path $data $name
        if (-not (Test-AlHomePath $file)) { continue }
        try {
            $doc = (Get-Content -LiteralPath $file -Raw -Encoding UTF8) | ConvertFrom-Json
            $out += [pscustomobject]@{ Pid = [int]$doc.pid; Created = [long]$doc.created; File = $name }
        } catch {
            continue
        }
    }
    return $out
}

function Get-AlOurProcesses {
    # The processes proven ours: a pid-file pid whose recorded creation time
    # (never 0) matches, or an image under <home>\runtime\.
    $records = @(Get-AlPidRecords)
    $runtime = Join-Path $script:HomeDir 'runtime'
    $ours = @()
    foreach ($proc in @(Get-AlProcessTable -Pids @($records | ForEach-Object { $_.Pid }))) {
        $byFile = $false
        foreach ($rec in $records) {
            if ($rec.Pid -eq $proc.Pid -and $rec.Created -ne 0 -and $rec.Created -eq $proc.Created) {
                $byFile = $true
            }
        }
        $byImage = $false
        if ($proc.Path) {
            $full = Get-AlFullPath $proc.Path
            $byImage = $full.StartsWith((Get-AlFullPath $runtime) + '\', [System.StringComparison]::OrdinalIgnoreCase)
        }
        if ($byFile -or $byImage) { $ours += $proc }
    }
    return $ours
}

function Stop-AlOurProcess($Proc) {
    if ($script:Fake) {
        $doc = Read-AlFake
        $doc.processes = @(@($doc.processes) | Where-Object { $null -ne $_ -and [int]$_.pid -ne $Proc.Pid })
        $doc.stopped = @(@($doc.stopped) + @($Proc.Pid) | Where-Object { $null -ne $_ })
        Save-AlFake $doc
        return
    }
    try {
        Stop-Process -Id $Proc.Pid -Force -ErrorAction Stop
        Wait-Process -Id $Proc.Pid -Timeout 10 -ErrorAction SilentlyContinue
    } catch {
        [void]$script:Problems.Add("could not stop process $($Proc.Pid): " + $_.Exception.Message)
    }
}

function Invoke-AlStop {
    $data = Join-Path $script:HomeDir 'data'
    if (Test-AlHomePath $data) {
        try {
            Set-Content -LiteralPath (Join-Path $data 'stop.request') -Value 'stop' -Encoding ASCII
        } catch {
            [void]$script:Problems.Add('could not write stop.request: ' + $_.Exception.Message)
        }
    }
    $deadline = (Get-Date).AddSeconds([Math]::Max(0, $WaitSec))
    $ours = @(Get-AlOurProcesses)
    while ($ours.Count -gt 0 -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
        $ours = @(Get-AlOurProcesses)
    }
    if ($ours.Count -eq 0) {
        Write-AlStep 'no AshLight process is running'
        return
    }
    foreach ($proc in $ours) {
        Write-AlStep ("stopping AshLight process " + $proc.Pid)
        Stop-AlOurProcess $proc
    }
}

# --- shell entries (steps 3 to 5) ----------------------------------------------

function Get-AlShellPlaces {
    # The Start Menu and Desktop folders, the uninstall key (under HKCU) and
    # the task folder: real, or redirected by AL_SHELL_ROOT exactly as
    # scripts/al_shell.ps1 Get-AlShellPlaces does. Path text only.
    $root = [string]$env:AL_SHELL_ROOT
    if ($root) {
        if (-not [System.IO.Path]::IsPathRooted($root)) {
            throw 'AL_SHELL_ROOT is not an absolute path'
        }
        $root = [System.IO.Path]::GetFullPath($root).TrimEnd('\')
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($root.ToLowerInvariant()))
        } finally {
            $sha.Dispose()
        }
        $id = (($bytes[0..7] | ForEach-Object { $_.ToString('x2') }) -join '')
        return [pscustomobject]@{
            Scratch  = $true
            Programs = Join-Path $root 'Programs'
            Desktop  = Join-Path $root 'Desktop'
            Key      = $script:ScratchKeyBase + '\' + $id + '\Uninstall\AshLight'
            TaskPath = $script:ScratchTaskBase + $id + '\'
        }
    }
    return [pscustomobject]@{
        Scratch  = $false
        Programs = [Environment]::GetFolderPath('Programs')
        Desktop  = [Environment]::GetFolderPath('Desktop')
        Key      = $script:RealKey
        TaskPath = '\'
    }
}

function Get-AlFakeList($Doc, [string]$Name) {
    $prop = $Doc.PSObject.Properties[$Name]
    if ($null -eq $prop -or $null -eq $prop.Value) { return @() }
    return @($prop.Value | Where-Object { $null -ne $_ })
}

function Add-AlFakeNote($Doc, [string]$Name, [string]$Text) {
    # A trace line in the fake (what was asked for or removed), so a test
    # can prove which names the script used.
    $list = @(Get-AlFakeList $Doc $Name) + @($Text)
    $Doc | Add-Member -NotePropertyName $Name -NotePropertyValue $list -Force
}

function Assert-AlShellLink([string]$Path) {
    # Only the two fixed AshLight.lnk paths of step 4 pass.
    $full = Get-AlFullPath $Path
    foreach ($link in $script:LinkPaths) {
        if ($full -and $full.Equals($link, [System.StringComparison]::OrdinalIgnoreCase)) { return }
    }
    throw "uninstall: $Path is not an AshLight shortcut path; refused"
}

function Test-AlShellLink([string]$Path) {
    Assert-AlShellLink $Path
    return (Test-Path -LiteralPath $Path -PathType Leaf)
}

function Get-AlLinkTarget([string]$Path) {
    # The target of one fixed shortcut, read only (the link is never saved).
    Assert-AlShellLink $Path
    $shell = New-Object -ComObject WScript.Shell
    try {
        return [string]$shell.CreateShortcut($Path).TargetPath
    } finally {
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell)
    }
}

function Remove-AlShellLink([string]$Path) {
    Assert-AlShellLink $Path
    Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
}

function Get-AlTaskRecord {
    # {Execute, WorkDir} of the task $script:TaskName in the task folder
    # of the places, or $null. No other task name is ever asked for.
    $where = $script:Shell.TaskPath + $script:TaskName
    if ($script:Fake) {
        $doc = Read-AlFake
        if (-not $DryRun) {
            Add-AlFakeNote $doc 'task_queries' $where
            Save-AlFake $doc
        }
        $found = $null
        foreach ($t in @(Get-AlFakeList $doc 'tasks')) {
            if ([string]$t.path -eq $script:Shell.TaskPath -and [string]$t.name -eq $script:TaskName) {
                $found = [pscustomobject]@{ Execute = [string]$t.execute; WorkDir = [string]$t.working_directory }
            }
        }
        return $found
    }
    try {
        $task = Get-ScheduledTask -TaskName $script:TaskName -TaskPath $script:Shell.TaskPath -ErrorAction Stop
    } catch {
        return $null
    }
    if ($null -eq $task) { return $null }
    $exe = ''
    $wd = ''
    $acts = @($task.Actions)
    if ($acts.Count -gt 0 -and $null -ne $acts[0]) {
        $p = $acts[0].PSObject.Properties['Execute']
        if ($null -ne $p -and $null -ne $p.Value) { $exe = [string]$p.Value }
        $p = $acts[0].PSObject.Properties['WorkingDirectory']
        if ($null -ne $p -and $null -ne $p.Value) { $wd = [string]$p.Value }
    }
    return [pscustomobject]@{ Execute = $exe; WorkDir = $wd }
}

function Test-AlTaskInHome($Task) {
    # As scripts/al_shell.ps1 Test-AlTaskOurs: the working directory, else
    # the program, must lie in the home.
    if ($null -eq $Task) { return $false }
    $wd = $Task.WorkDir.Trim('"')
    if ($wd) { return (Test-AlUnder -Path $wd -Root $script:HomeDir) }
    return (Test-AlUnder -Path $Task.Execute.Trim('"') -Root $script:HomeDir)
}

function Remove-AlTask {
    if ($script:Fake) {
        $doc = Read-AlFake
        $keep = @(Get-AlFakeList $doc 'tasks' | Where-Object {
            -not ([string]$_.path -eq $script:Shell.TaskPath -and [string]$_.name -eq $script:TaskName) })
        $doc | Add-Member -NotePropertyName tasks -NotePropertyValue $keep -Force
        Add-AlFakeNote $doc 'removed_tasks' ($script:Shell.TaskPath + $script:TaskName)
        Save-AlFake $doc
        return
    }
    Unregister-ScheduledTask -TaskName $script:TaskName -TaskPath $script:Shell.TaskPath -Confirm:$false -ErrorAction Stop
}

function Get-AlKeyLocation {
    # $null when the uninstall key of the places is absent, else its
    # InstallLocation text ('' when it has none). HKCU only, read only.
    if ($script:Fake) {
        $doc = Read-AlFake
        if (-not $DryRun) {
            Add-AlFakeNote $doc 'key_queries' $script:Shell.Key
            Save-AlFake $doc
        }
        $keys = $doc.PSObject.Properties['keys']
        if ($null -eq $keys -or $null -eq $keys.Value) { return $null }
        $entry = $keys.Value.PSObject.Properties[$script:Shell.Key]
        if ($null -eq $entry) { return $null }
        $loc = $null
        if ($null -ne $entry.Value) { $loc = $entry.Value.PSObject.Properties['InstallLocation'] }
        if ($null -eq $loc -or $null -eq $loc.Value) { return '' }
        return [string]$loc.Value
    }
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($script:Shell.Key, $false)
    if ($null -eq $key) { return $null }
    try {
        return [string]$key.GetValue('InstallLocation', '')
    } finally {
        $key.Close()
    }
}

function Remove-AlKey {
    if ($script:Fake) {
        $doc = Read-AlFake
        $keys = $doc.PSObject.Properties['keys']
        if ($null -ne $keys -and $null -ne $keys.Value) {
            $keys.Value.PSObject.Properties.Remove($script:Shell.Key)
        }
        Add-AlFakeNote $doc 'removed_keys' $script:Shell.Key
        Save-AlFake $doc
        return
    }
    [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($script:Shell.Key, $false)
}

function Invoke-AlTaskStep {
    # Step 3; -Plan only prints what would happen.
    param([switch]$Plan)
    $where = $script:Shell.TaskPath + $script:TaskName
    $task = Get-AlTaskRecord
    if ($null -eq $task) { return }
    if (-not (Test-AlTaskInHome $task)) {
        Write-AlStep ('leaving the logon task ' + $where + ': it points elsewhere')
        return
    }
    if ($Plan) {
        Write-AlStep ('would remove the logon task ' + $where)
        return
    }
    Write-AlStep ('removing the logon task ' + $where)
    try {
        Remove-AlTask
    } catch {
        [void]$script:Problems.Add("could not remove the logon task ${where}: " + $_.Exception.Message)
    }
    if ($null -ne (Get-AlTaskRecord)) { [void]$script:ShellLeft.Add('logon task ' + $where) }
}

function Invoke-AlLinkStep {
    # Step 4; -Plan only prints what would happen.
    param([switch]$Plan)
    foreach ($link in $script:LinkPaths) {
        if (-not (Test-AlShellLink $link)) { continue }
        $target = ''
        try { $target = Get-AlLinkTarget $link } catch { $target = '' }
        if (-not (Test-AlUnder -Path $target -Root $script:HomeDir)) {
            Write-AlStep ('leaving ' + $link + ': it points elsewhere')
            continue
        }
        if ($Plan) {
            Write-AlStep ('would remove ' + $link)
            continue
        }
        Write-AlStep ('removing ' + $link)
        try {
            Remove-AlShellLink $link
        } catch {
            [void]$script:Problems.Add("could not remove ${link}: " + $_.Exception.Message)
        }
        if (Test-AlShellLink $link) { [void]$script:ShellLeft.Add($link) }
    }
}

function Invoke-AlKeyStep {
    # Step 5; -Plan only prints what would happen.
    param([switch]$Plan)
    $where = 'HKCU\' + $script:Shell.Key
    $loc = Get-AlKeyLocation
    if ($null -eq $loc) { return }
    if (-not (Test-AlUnder -Path $loc -Root $script:HomeDir)) {
        Write-AlStep ('leaving the uninstall entry ' + $where + ': it points elsewhere')
        return
    }
    if ($Plan) {
        Write-AlStep ('would remove the uninstall entry ' + $where)
        return
    }
    Write-AlStep ('removing the uninstall entry ' + $where)
    try {
        Remove-AlKey
    } catch {
        [void]$script:Problems.Add("could not remove the uninstall entry ${where}: " + $_.Exception.Message)
    }
    if ($null -ne (Get-AlKeyLocation)) { [void]$script:ShellLeft.Add('uninstall entry ' + $where) }
}

# --- delete (steps 6 and 7) ----------------------------------------------------

function Get-AlDeletePlan {
    # The fixed-name items that exist now, home first, then data's run files.
    $plan = @()
    foreach ($name in $script:DeleteNames) {
        $p = Join-Path $script:HomeDir $name
        if (Test-AlHomePath $p) { $plan += $p }
    }
    $data = Join-Path $script:HomeDir 'data'
    foreach ($name in $script:RunFiles) {
        $p = Join-Path $data $name
        if (Test-AlHomePath $p) { $plan += $p }
    }
    return $plan
}

function Send-AlDataToRecycleBin([string]$Data) {
    Assert-AlInHome $Data
    if (-not (Test-AlHomePath $Data)) { return }
    try {
        if ($script:Fake) {
            $bin = [string](Read-AlFake).recycle
            if (-not $bin -or (Test-AlUnder -Path $bin -Root $script:HomeDir)) {
                throw 'the fake recycle folder is not set or lies in the home'
            }
            Move-Item -LiteralPath $Data -Destination (Join-Path $bin ('data-' + [guid]::NewGuid().ToString('N')))
            return
        }
        Add-Type -AssemblyName Microsoft.VisualBasic
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($Data,
            [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
            [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)
    } catch {
        [void]$script:Problems.Add("could not move $Data to the Recycle Bin: " + $_.Exception.Message)
    }
}

function Get-AlRemaining {
    # Every path that should be gone but is not. Kept data (without -Purge)
    # is not counted, except the per-run files inside it.
    param([bool]$KeepData)
    $out = @()
    if (-not (Test-AlHomePath $script:HomeDir)) { return $out }
    $data = Join-Path $script:HomeDir 'data'
    foreach ($item in @(Get-AlHomeChildren -Path $script:HomeDir -Recurse)) {
        $full = Get-AlFullPath $item.FullName
        if ($KeepData -and (Test-AlUnder -Path $full -Root $data)) { continue }
        $out += $full
    }
    if ($KeepData) {
        foreach ($name in $script:RunFiles) {
            $p = Join-Path $data $name
            if (Test-AlHomePath $p) { $out += $p }
        }
    } elseif ($out.Count -eq 0) {
        $out += $script:HomeDir
    }
    return $out
}

function Remove-AlOwnCopy {
    # The temp copy removes itself at the end: only that exact file, only
    # when it is a copy this script made in the temp folder.
    $self = Get-AlFullPath $PSCommandPath
    $leaf = Split-Path -Leaf $self
    if ($FromHome -and $leaf.StartsWith($script:CopyPrefix, [System.StringComparison]::OrdinalIgnoreCase) -and
            -not (Test-AlUnder -Path $self -Root $script:HomeDir)) {
        try { Remove-Item -LiteralPath $self -Force -ErrorAction Stop } catch { }
    }
}

function Get-AlTempDir {
    $t = [string]$env:TEMP
    if (-not $t) { $t = [System.IO.Path]::GetTempPath() }
    return (Get-AlFullPath $t)
}

# --- step 1: validate ------------------------------------------------------------

$homeArg = $FromHome
if (-not $homeArg) { $homeArg = $PSScriptRoot }
$why = Get-AlHomeRefusal $homeArg
if ($why) { Stop-AlRefused $why }
$script:HomeDir = Get-AlFullPath $homeArg
$why = Test-AlMarker $script:HomeDir
if ($why) { Stop-AlRefused $why }
$tempDir = Get-AlTempDir
if (-not $tempDir -or (Test-AlUnder -Path $tempDir -Root $script:HomeDir)) {
    Stop-AlRefused 'the temp folder lies in the home'
}
try {
    $script:Shell = Get-AlShellPlaces
} catch {
    Stop-AlRefused $_.Exception.Message
}
if ($script:Fake -and -not $script:Shell.Scratch) {
    Stop-AlRefused 'AL_UNINSTALL_FAKE needs AL_SHELL_ROOT (no real shell entry is read in a test)'
}
foreach ($folder in @($script:Shell.Programs, $script:Shell.Desktop)) {
    if ($folder) { $script:LinkPaths += (Get-AlFullPath (Join-Path $folder $script:LinkName)) }
}
if ($script:Fake) {
    $fakeDoc = Read-AlFake
    if (-not $DryRun -and $FromHome) {
        $fakeDoc | Add-Member -NotePropertyName ran_from -NotePropertyValue (Get-AlFullPath $PSCommandPath) -Force
        Save-AlFake $fakeDoc
    }
}

if ($DryRun) {
    Write-AlStep ('dry run for ' + $script:HomeDir + '; nothing is changed')
    foreach ($proc in @(Get-AlOurProcesses)) {
        Write-AlStep ('would stop AshLight process ' + $proc.Pid)
    }
    Invoke-AlTaskStep -Plan
    Invoke-AlLinkStep -Plan
    Invoke-AlKeyStep -Plan
    foreach ($p in @(Get-AlDeletePlan)) { Write-AlStep ('would delete ' + $p) }
    $data = Join-Path $script:HomeDir 'data'
    if ($Purge -and (Test-AlHomePath $data)) {
        Write-AlStep ('would move ' + $data + ' to the Recycle Bin')
    } elseif (Test-AlHomePath $data) {
        Write-AlStep ('would keep ' + $data)
    }
    Write-AlStep ('would delete ' + (Join-Path $script:HomeDir 'uninstall.ps1'))
    exit 0
}

if (-not $FromHome) {
    # The consent for -Purge, then the re-run from a temp copy.
    if ($Purge -and -not $Yes) {
        if ($Quiet -or [Console]::IsInputRedirected) {
            Stop-AlRefused '-Purge needs -Yes when no one can type PURGE'
        }
        $typed = Read-Host 'This also removes your AshLight settings and history (to the Recycle Bin). Type PURGE to go on'
        if ($typed -cne 'PURGE') { Stop-AlRefused 'PURGE was not typed; nothing was changed' }
    }
    $copy = Join-Path $tempDir ($script:CopyPrefix + [guid]::NewGuid().ToString('N') + '.ps1')
    Copy-Item -LiteralPath $PSCommandPath -Destination $copy -Force
    $ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $argText = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $copy + '" -FromHome "' +
        $script:HomeDir + '" -WaitSec ' + [string]$WaitSec
    if ($Purge) { $argText += ' -Purge -Yes' }
    if ($Quiet) { $argText += ' -Quiet' }
    Set-Location -LiteralPath $tempDir
    [Environment]::CurrentDirectory = $tempDir
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $ps
    $info.Arguments = $argText
    $info.UseShellExecute = $false
    $info.WorkingDirectory = $tempDir
    $child = [System.Diagnostics.Process]::Start($info)
    $child.WaitForExit()
    exit $child.ExitCode
}

# --- the temp copy does the work -----------------------------------------------

Set-Location -LiteralPath $tempDir
[Environment]::CurrentDirectory = $tempDir

# step 2
Invoke-AlStop

# steps 3 to 5
Invoke-AlTaskStep
Invoke-AlLinkStep
Invoke-AlKeyStep

# step 6
foreach ($p in @(Get-AlDeletePlan)) {
    Write-AlStep ('deleting ' + $p)
    Remove-AlHomeItem $p
}

# step 7
$data = Join-Path $script:HomeDir 'data'
$keep = (-not $Purge) -and (Test-AlHomePath $data)
if ($Purge) {
    if (Test-AlHomePath $data) {
        Write-AlStep ('moving ' + $data + ' to the Recycle Bin')
        Send-AlDataToRecycleBin $data
    }
}
Remove-AlHomeItem (Join-Path $script:HomeDir 'uninstall.ps1')
if (-not $keep) { Remove-AlHomeItem -Path $script:HomeDir -Empty }

# steps 8 and 9
$left = @(Get-AlRemaining -KeepData $keep) + @($script:ShellLeft)
if ($left.Count -gt 0) {
    $report = Join-Path $tempDir $script:ReportName
    $lines = @('AshLight uninstall report', ('home: ' + $script:HomeDir), 'items that remain:')
    $lines += @($left | ForEach-Object { '  ' + $_ })
    if ($script:Problems.Count -gt 0) {
        $lines += 'problems:'
        $lines += @($script:Problems | ForEach-Object { '  ' + $_ })
    }
    try {
        [System.IO.File]::WriteAllText($report, (($lines -join "`n") + "`n"), (New-Object System.Text.UTF8Encoding($false)))
        Write-AlStep ('report: ' + $report)
    } catch {
        Write-AlStep 'the report could not be written'
    }
    Write-AlLast ('uninstall incomplete: ' + $left.Count + ' items remain')
    Remove-AlOwnCopy
    exit 1
}
if ($keep) {
    Write-AlLast ('AshLight is removed. Kept: ' + $data + ' (your settings, history and builds).')
} else {
    Write-AlLast 'AshLight is removed. Nothing was kept.'
}
Write-AlLast $script:CopiedSentence
Remove-AlOwnCopy
exit 0
