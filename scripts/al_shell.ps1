<#
.SYNOPSIS
  AshLight shell integration helper (DEP-07). Dot-source it; it only
  defines functions. Windows PowerShell 5.1 compatible, StrictMode 2 clean.
.DESCRIPTION
  One place that writes, reads back and removes AshLight's per-user shell
  entries: the "AshLight" Start Menu and Desktop shortcuts and the per-user
  uninstall entry (HKCU ...\Uninstall\AshLight). No admin rights; never a
  machine-wide (Common*) folder or an HKLM key.

  Rules every function keeps:
  - "Is it ours": an existing shortcut or uninstall entry is changed or
    removed only when its target (shortcut) or InstallLocation (entry) lies
    under the given owner root (Test-AlOurs). One that points elsewhere (an
    installed copy's, another checkout's, someone else's) is left alone and
    reported as 'elsewhere'.
  - Every write is read back; a mismatch throws.
  - A re-run with nothing to change writes nothing ('current').
  - Effect root: a parameter -EffectRoot, else the env AL_SHELL_ROOT. When
    one is set, the Start Menu and Desktop become <root>\Programs and
    <root>\Desktop, the uninstall key moves to a scratch registry path
    (HKCU:\Software\AshLightShellScratch\<id>\Uninstall\AshLight, <id> from
    the root's path), and a shortcut path outside the root is refused.
    Tests and the release stage round trip use it, so the player's real
    Start Menu, Desktop and uninstall entry are never written or removed.
  The logon task functions come with REL-AUTOSTART-ENTRY.
#>

$script:AlShellRealUninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AshLight'
$script:AlShellScratchBase = 'HKCU:\Software\AshLightShellScratch'
$script:AlShellLinkName = 'AshLight.lnk'
$script:AlShellDescription = 'AshLight: a companion app for Path of Exile 2'

function Get-AlShellRoot {
    param([string]$EffectRoot = '')
    $root = $EffectRoot
    if (-not $root) { $root = [string]$env:AL_SHELL_ROOT }
    if (-not $root) { return '' }
    if (-not [System.IO.Path]::IsPathRooted($root)) {
        throw "al_shell: the effect root must be an absolute path: $root"
    }
    return [System.IO.Path]::GetFullPath($root).TrimEnd('\')
}

function Test-AlOurs {
    # True when Path is Root or lies under it (full paths, case-insensitive).
    param([string]$Path, [string]$Root)
    if (-not $Path -or -not $Root) { return $false }
    try {
        $p = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
        $r = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    } catch {
        return $false
    }
    if (-not $p -or -not $r) { return $false }
    if ($p.Equals($r, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    return $p.StartsWith($r + '\', [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-AlShellPlaces {
    # The Start Menu folder, the Desktop folder and the uninstall key, real
    # or redirected under the effect root.
    param([string]$EffectRoot = '')
    $root = Get-AlShellRoot -EffectRoot $EffectRoot
    if ($root) {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($root.ToLowerInvariant()))
        } finally {
            $sha.Dispose()
        }
        $id = (($bytes[0..7] | ForEach-Object { $_.ToString('x2') }) -join '')
        return [pscustomobject]@{
            Scratch      = $true
            Root         = $root
            Programs     = Join-Path $root 'Programs'
            Desktop      = Join-Path $root 'Desktop'
            ScratchKey   = $script:AlShellScratchBase + '\' + $id
            UninstallKey = $script:AlShellScratchBase + '\' + $id + '\Uninstall\AshLight'
        }
    }
    return [pscustomobject]@{
        Scratch      = $false
        Root         = ''
        Programs     = [Environment]::GetFolderPath('Programs')
        Desktop      = [Environment]::GetFolderPath('Desktop')
        ScratchKey   = ''
        UninstallKey = $script:AlShellRealUninstallKey
    }
}

function Get-AlShortcutPaths {
    # The two AshLight.lnk paths (Start Menu, Desktop); a folder Windows
    # does not name is skipped.
    param([string]$EffectRoot = '')
    $places = Get-AlShellPlaces -EffectRoot $EffectRoot
    $out = @()
    foreach ($folder in @($places.Programs, $places.Desktop)) {
        if (-not $folder) { continue }
        $out += (Join-Path $folder $script:AlShellLinkName)
    }
    return $out
}

function Assert-AlShellLink {
    param([string]$LinkPath, [string]$EffectRoot = '')
    $root = Get-AlShellRoot -EffectRoot $EffectRoot
    if ($root -and -not (Test-AlOurs -Path $LinkPath -Root $root)) {
        throw "al_shell: $LinkPath is outside the effect root"
    }
}

function Set-AlShortcut {
    # 'written' (made or rewritten, then read back), 'current' (nothing to
    # change) or 'elsewhere' (an existing link whose target lies outside
    # OwnerRoot; left alone).
    param([string]$LinkPath, [string]$Target, [string]$Arguments, [string]$WorkDir,
          [string]$Icon, [string]$OwnerRoot, [string]$EffectRoot = '')
    Assert-AlShellLink -LinkPath $LinkPath -EffectRoot $EffectRoot
    if (-not (Test-AlOurs -Path $Target -Root $OwnerRoot)) {
        throw "al_shell: the shortcut target is not under the owner root: $Target"
    }
    $shell = New-Object -ComObject WScript.Shell
    $want = $Icon + ',0'
    if (Test-Path -LiteralPath $LinkPath) {
        $old = $shell.CreateShortcut($LinkPath)
        if (-not (Test-AlOurs -Path $old.TargetPath -Root $OwnerRoot)) {
            return 'elsewhere'
        }
        if ($old.TargetPath -eq $Target -and $old.Arguments -eq $Arguments -and
            $old.WorkingDirectory -eq $WorkDir -and $old.IconLocation -eq $want) {
            return 'current'
        }
    }
    $parent = Split-Path -Parent $LinkPath
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $lnk = $shell.CreateShortcut($LinkPath)
    $lnk.TargetPath = $Target
    $lnk.Arguments = $Arguments
    $lnk.WorkingDirectory = $WorkDir
    $lnk.IconLocation = $want
    $lnk.Description = $script:AlShellDescription
    $lnk.WindowStyle = 1
    $lnk.Save()
    $back = $shell.CreateShortcut($LinkPath)
    if (-not (Test-Path -LiteralPath $LinkPath) -or $back.TargetPath -ne $Target -or
        $back.Arguments -ne $Arguments -or $back.WorkingDirectory -ne $WorkDir -or
        $back.IconLocation -ne $want) {
        throw "al_shell: shortcut read-back mismatch: $LinkPath"
    }
    return 'written'
}

function Install-AlShortcuts {
    # Both AshLight shortcuts (Start Menu, Desktop). One result per link:
    # [pscustomobject]@{ Link; Status } with Status as Set-AlShortcut.
    param([string]$Target, [string]$Arguments, [string]$WorkDir, [string]$Icon,
          [string]$OwnerRoot, [string]$EffectRoot = '')
    $results = @()
    foreach ($link in @(Get-AlShortcutPaths -EffectRoot $EffectRoot)) {
        $status = Set-AlShortcut -LinkPath $link -Target $Target -Arguments $Arguments `
            -WorkDir $WorkDir -Icon $Icon -OwnerRoot $OwnerRoot -EffectRoot $EffectRoot
        $results += [pscustomobject]@{ Link = $link; Status = $status }
    }
    return $results
}

function Remove-AlShortcut {
    # 'removed' (gone, read back), 'absent' or 'elsewhere' (target outside
    # OwnerRoot; left alone).
    param([string]$LinkPath, [string]$OwnerRoot, [string]$EffectRoot = '')
    Assert-AlShellLink -LinkPath $LinkPath -EffectRoot $EffectRoot
    if (-not (Test-Path -LiteralPath $LinkPath)) { return 'absent' }
    $shell = New-Object -ComObject WScript.Shell
    $old = $shell.CreateShortcut($LinkPath)
    if (-not (Test-AlOurs -Path $old.TargetPath -Root $OwnerRoot)) { return 'elsewhere' }
    Remove-Item -LiteralPath $LinkPath -Force
    if (Test-Path -LiteralPath $LinkPath) {
        throw "al_shell: shortcut still present after removal: $LinkPath"
    }
    return 'removed'
}

function Get-AlUninstallValues {
    param([string]$InstallLocation, [string]$Version, [string]$Icon)
    $loc = [System.IO.Path]::GetFullPath($InstallLocation).TrimEnd('\')
    $ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $cmd = '"' + $ps + '" -NoProfile -ExecutionPolicy Bypass -File "' +
        (Join-Path $loc 'uninstall.ps1') + '"'
    $values = [ordered]@{
        DisplayName          = 'AshLight'
        DisplayVersion       = $Version
        Publisher            = 'The AshLight authors'
        InstallLocation      = $loc
        UninstallString      = $cmd
        QuietUninstallString = $cmd + ' -Quiet'
    }
    if ($Icon) { $values['DisplayIcon'] = $Icon }
    return $values
}

function Get-AlRegValue {
    param([string]$Key, [string]$Name)
    $item = Get-ItemProperty -LiteralPath $Key -ErrorAction SilentlyContinue
    if ($null -eq $item) { return $null }
    $prop = $item.PSObject.Properties[$Name]
    if ($null -eq $prop) { return $null }
    return $prop.Value
}

function Test-AlUninstallCurrent {
    param([string]$Key, $Values)
    foreach ($name in $Values.Keys) {
        if ([string](Get-AlRegValue -Key $Key -Name $name) -cne [string]$Values[$name]) {
            return $false
        }
    }
    foreach ($name in @('NoModify', 'NoRepair')) {
        $v = Get-AlRegValue -Key $Key -Name $name
        if ($null -eq $v -or [int]$v -ne 1) { return $false }
    }
    if (-not $Values.Contains('DisplayIcon') -and
        $null -ne (Get-AlRegValue -Key $Key -Name 'DisplayIcon')) {
        return $false
    }
    return $true
}

function Set-AlUninstallEntry {
    # The per-user Apps and features entry for the installed copy at
    # InstallLocation. 'written' (read back), 'current' or 'elsewhere' (an
    # existing entry whose InstallLocation lies outside this one; left
    # alone).
    param([string]$InstallLocation, [string]$Version, [string]$Icon = '',
          [string]$EffectRoot = '')
    if (-not $InstallLocation -or -not [System.IO.Path]::IsPathRooted($InstallLocation)) {
        throw "al_shell: InstallLocation must be an absolute path: $InstallLocation"
    }
    if (-not $Version) { throw 'al_shell: a version is required' }
    $key = (Get-AlShellPlaces -EffectRoot $EffectRoot).UninstallKey
    $values = Get-AlUninstallValues -InstallLocation $InstallLocation -Version $Version -Icon $Icon
    if (Test-Path -LiteralPath $key) {
        $have = [string](Get-AlRegValue -Key $key -Name 'InstallLocation')
        if (-not (Test-AlOurs -Path $have -Root $values['InstallLocation'])) { return 'elsewhere' }
        if (Test-AlUninstallCurrent -Key $key -Values $values) { return 'current' }
    } else {
        New-Item -Path $key -Force | Out-Null
    }
    foreach ($name in $values.Keys) {
        New-ItemProperty -LiteralPath $key -Name $name -Value ([string]$values[$name]) `
            -PropertyType String -Force | Out-Null
    }
    foreach ($name in @('NoModify', 'NoRepair')) {
        New-ItemProperty -LiteralPath $key -Name $name -Value 1 -PropertyType DWord -Force | Out-Null
    }
    if (-not $values.Contains('DisplayIcon') -and
        $null -ne (Get-AlRegValue -Key $key -Name 'DisplayIcon')) {
        Remove-ItemProperty -LiteralPath $key -Name 'DisplayIcon' -Force
    }
    if (-not (Test-AlUninstallCurrent -Key $key -Values $values)) {
        throw "al_shell: uninstall entry read-back mismatch: $key"
    }
    return 'written'
}

function Remove-AlUninstallEntry {
    # 'removed' (gone, read back), 'absent' or 'elsewhere' (InstallLocation
    # outside this one; left alone).
    param([string]$InstallLocation, [string]$EffectRoot = '')
    if (-not $InstallLocation -or -not [System.IO.Path]::IsPathRooted($InstallLocation)) {
        throw "al_shell: InstallLocation must be an absolute path: $InstallLocation"
    }
    $key = (Get-AlShellPlaces -EffectRoot $EffectRoot).UninstallKey
    if (-not (Test-Path -LiteralPath $key)) { return 'absent' }
    $have = [string](Get-AlRegValue -Key $key -Name 'InstallLocation')
    if (-not (Test-AlOurs -Path $have -Root $InstallLocation)) { return 'elsewhere' }
    Remove-Item -LiteralPath $key -Recurse -Force
    if (Test-Path -LiteralPath $key) {
        throw "al_shell: uninstall entry still present after removal: $key"
    }
    return 'removed'
}
