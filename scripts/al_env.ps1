<#
.SYNOPSIS
  The ONE place AshLight's PowerShell scripts find Python, Electron and the
  paths (REL-RUNTIME-SCRIPTS, F-047, DEP-06). Windows PowerShell 5.1.
.DESCRIPTION
  Dot-source this file (". (Join-Path $PSScriptRoot 'al_env.ps1')"); it
  defines functions only, plus $AlEnvRoot, the folder above scripts\ (the
  repository in a checkout, the payload root <home>\app\<version> in an
  installed copy). No other script holds its own Python lookup.

  The mode follows server\al\paths.py install_mode(): installed when AL_HOME
  names the home, or when the payload root is <home>\app\<version> and
  <home>\install.json is a file; else a checkout. A home whose path text has
  a "steamapps" or "Path of Exile 2" component is refused by path text only
  (paths.home_refusal: no registry read, no listing of any game folder).

  Get-AlPython [-Windowless]
    Installed: the marker's private runtime,
    <home>\runtime\<marker "python">\python.exe (pythonw.exe when
    -Windowless and that file exists); one plain folder name, never a path
    out of <home>\runtime. Checkout: python, else py, from PATH (pythonw
    from PATH first when -Windowless). Throws when none is usable.
  Get-AlPythonCmd -Module <m> [-ArgList <a>] [-Windowless]
    The whole command as a string array, the PowerShell twin of
    paths.python_cmd(): checkout <python> -m <m> <a...>; installed
    <python> <root>\boot.py <m> <a...> (the embeddable runtime's ._pth
    ignores the current folder, so -m finds nothing there).
  Invoke-AlPython <m> [<a>...]
    Runs that command from $AlEnvRoot and writes its output; the exit code
    is in $LASTEXITCODE. Arrays in the argument list are flattened.
  Get-AlPaths
    The parsed JSON of server.al.paths (the one path resolver), through
    Invoke-AlPython; throws when it fails.
  Get-AlElectron
    Installed: <home>\runtime\<marker "electron">\electron.exe (the pinned,
    unmodified zip the installer fetched); $null when the marker names no
    usable folder. Checkout: app\node_modules\electron\dist\electron.exe.
    The client is always started with the app folder (<root>\app) as its
    first argument, never a resources\app folder.
  Format-AlArgs <a>
    The arguments for one command line (scripts\al_detach.ps1 joins them
    with spaces): an argument with a space, a tab or a quote, or an empty
    one, is wrapped in double quotes.
#>

$AlEnvRoot = Split-Path -Parent $PSScriptRoot

function Get-AlHomeRefusal([string]$AlHome) {
    foreach ($part in ($AlHome -split '[\\/]+')) {
        $bare = $part.TrimEnd('. ').ToLowerInvariant()
        if ($bare -eq 'steamapps' -or $bare -eq 'path of exile 2') {
            return ("the install home may not lie in a '" + $part + "' folder (a Steam " +
                "library or the game's own folder); install AshLight in its own folder")
        }
    }
    return $null
}

# The install home (AL_HOME, else two levels above the payload root when the
# payload root sits in an 'app' folder and install.json is there), or $null in
# a checkout. One stat of the marker inside the home.
function Get-AlInstallHome([string]$Root = $AlEnvRoot) {
    $AlHome = $null
    $fromEnv = ([string]$env:AL_HOME).Trim().Trim('"')
    if ($fromEnv) {
        $AlHome = [System.IO.Path]::GetFullPath($fromEnv)
    } else {
        $parent = Split-Path -Parent $Root
        if ($parent -and ((Split-Path -Leaf $parent) -ieq 'app')) {
            $up = Split-Path -Parent $parent
            if ($up -and (Test-Path -LiteralPath (Join-Path $up 'install.json') -PathType Leaf)) {
                $AlHome = $up
            }
        }
    }
    if (-not $AlHome) { return $null }
    $reason = Get-AlHomeRefusal $AlHome
    if ($reason) { throw $reason }
    return $AlHome
}

# <home>\runtime\<marker[$Key]> or $null: one plain folder name, never a path
# out of <home>\runtime (paths._marker_runtime). The marker is read only when
# it is a file of at most 64 KB.
function Get-AlMarkerRuntime([string]$AlHome, [string]$Key) {
    $marker = Join-Path $AlHome 'install.json'
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { return $null }
    if ((Get-Item -LiteralPath $marker).Length -gt 65536) { return $null }
    try {
        $doc = (Get-Content -LiteralPath $marker -Raw) | ConvertFrom-Json
    } catch {
        return $null
    }
    if ($null -eq $doc -or -not ($doc.PSObject.Properties.Name -contains $Key)) { return $null }
    $name = $doc.$Key
    if (-not ($name -is [string])) { return $null }
    if (-not $name.Trim('. ') -or $name.IndexOfAny([char[]]@('\', '/', ':')) -ge 0) { return $null }
    return (Join-Path (Join-Path $AlHome 'runtime') $name)
}

function Get-AlPython([switch]$Windowless) {
    $AlHome = Get-AlInstallHome
    if ($AlHome) {
        $folder = Get-AlMarkerRuntime $AlHome 'python'
        if (-not $folder) { throw 'The install marker names no usable Python runtime.' }
        $exe = Join-Path $folder 'python.exe'
        if ($Windowless) {
            $quiet = Join-Path $folder 'pythonw.exe'
            if (Test-Path -LiteralPath $quiet -PathType Leaf) { return $quiet }
        }
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
            throw 'The private Python runtime is missing; run the installer repair.'
        }
        return $exe
    }
    $names = @('python', 'py')
    if ($Windowless) { $names = @('pythonw') + $names }
    foreach ($name in $names) {
        $cmd = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($cmd) { return $cmd.Source }
    }
    throw 'Python 3.11 or newer was not found on PATH.'
}

function Get-AlPythonCmd {
    param(
        [Parameter(Mandatory = $true)][string]$Module,
        [string[]]$ArgList = @(),
        [switch]$Windowless
    )
    $exe = Get-AlPython -Windowless:$Windowless
    $tail = @($Module) + @($ArgList | ForEach-Object { [string]$_ })
    if (Get-AlInstallHome) {
        return [string[]](@($exe, (Join-Path $AlEnvRoot 'boot.py')) + $tail)
    }
    return [string[]](@($exe, '-m') + $tail)
}

function Invoke-AlPython {
    $flat = @($args | ForEach-Object { $_ } | ForEach-Object { [string]$_ })
    if ($flat.Count -lt 1) { throw 'Invoke-AlPython: no module named' }
    $rest = @()
    if ($flat.Count -gt 1) { $rest = $flat[1..($flat.Count - 1)] }
    $cmd = Get-AlPythonCmd -Module $flat[0] -ArgList $rest
    $exe = $cmd[0]
    $tail = $cmd[1..($cmd.Count - 1)]
    Push-Location -LiteralPath $AlEnvRoot
    try {
        & $exe @tail
    } finally {
        Pop-Location
    }
}

function Get-AlPaths {
    $json = (Invoke-AlPython 'server.al.paths') -join "`n"
    if ($LASTEXITCODE -ne 0) { throw 'server.al.paths failed' }
    return ($json | ConvertFrom-Json)
}

function Get-AlElectron {
    $AlHome = Get-AlInstallHome
    if ($AlHome) {
        $folder = Get-AlMarkerRuntime $AlHome 'electron'
        if (-not $folder) { return $null }
        return (Join-Path $folder 'electron.exe')
    }
    return (Join-Path $AlEnvRoot 'app\node_modules\electron\dist\electron.exe')
}

function Format-AlArgs([string[]]$ArgList) {
    $out = @()
    foreach ($a in @($ArgList)) {
        $s = [string]$a
        if ($s -eq '' -or $s.IndexOfAny([char[]]@(' ', "`t", '"')) -ge 0) {
            $s = '"' + $s.Replace('"', '\"') + '"'
        }
        $out += $s
    }
    return [string[]]$out
}
