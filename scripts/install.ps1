<#
AshLight bootstrap installer (DEP-09, finding F-050; docs/plan/05-deployment.md
"DEP-09 Installer and bootstrap", decisions 0059, 0063 and 0064).

The one pasted PowerShell 5.1 line (the release notes and README carry it):

    irm -UserAgent 'AshLight/<version> (installer)' <release address>/download/v<version>/install.ps1 | iex

or, as a file (the reviewer's and the offline route):

    powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 [-Zip <app zip>] [-RuntimeDir <folder>] [-InstallDir <folder>] [-NoStart]

What it does, in this fixed order, and nothing else:
1. home: -InstallDir, else AL_INSTALL_DIR (the piped route's switch), else
   %LOCALAPPDATA%\Programs\AshLight. A home in a Steam library or the
   game's own folder is refused by its path text alone, before anything
   is read, fetched or written.
2. release files: SHA256SUMS.txt, release.json and AshLight-<version>-app.zip,
   from the project's GitHub release of the stamped version, or from the
   folder of -Zip. release.json and the zip must each match their line in
   SHA256SUMS.txt; a missing line or a wrong hash stops here, before any
   extract.
3. CPython: the embeddable zip pinned in release.json, fetched from
   www.python.org (or taken from -RuntimeDir) and checked against the
   pinned size and SHA-256 before it is unpacked.
4. hand-over: '<python> boot.py server.al.install install' from the
   verified bytes, unpacked under <home>\temp. The installer package
   checks everything again, fetches Electron, lays out the home, writes
   the first-run config (web data off, no Client.txt consent: both stay
   the player's clicks on the first window), self-tests, writes the
   marker and the shortcuts and starts the client. A re-run upgrades or
   repairs in place.

Every web request goes through Get-AlDownload: https only, the hosts in
$AlHosts only (checked on every redirect hop), the User-Agent
'AshLight/<version> (installer)', basic parsing, no cookie, no web
session. No elevation is asked for; every location is per-user. It never
looks for the game, reads no registry and no game folder, and sends no
input anywhere. Self-contained: it runs before any payload exists.
ASCII and LF; Windows PowerShell 5.1.
#>
param(
    [string]$Zip = '',
    [string]$RuntimeDir = '',
    [string]$InstallDir = '',
    [switch]$NoStart,
    # the project's repository '<owner>/<name>'; empty takes $AlRepo below
    [string]$Repo = '',
    # test seam: a script given the hand-over command line in place of
    # running it (tests/test_install_ps1.py)
    [string]$Runner = ''
)

# release.py build stamps the version here (tools/rel_assets.py)
$AlVersion = '__AL_VERSION__'
# config/public_repo.json 'repo' (the go-public address); -Repo overrides
$AlRepo = 'Remus3/AshLight'
$AlName = 'AshLight'
$AlHosts = @('github.com', 'release-assets.githubusercontent.com',
             'objects.githubusercontent.com', 'www.python.org')
$AlVersionPattern = '^\d+\.\d+\.\d+(-[0-9A-Za-z]+(\.[0-9A-Za-z]+)*)?$'
$AlMaxSums = 64KB
$AlMaxRelease = 256KB
$AlMaxAppZip = 16MB
$AlMaxRuntime = 512MB
$AlMaxHops = 5

function Write-AlLine([string]$Text) {
    Write-Host ('AshLight installer: ' + $Text)
}

function Get-AlUserAgent([string]$Version) {
    return ('AshLight/' + $Version + ' (installer)')
}

function Test-AlVersion([string]$Text) {
    return ($Text -match $AlVersionPattern)
}

function Get-AlHomeRefusal([string]$HomePath) {
    # path text only: no stat, no listing, no registry, no library file
    foreach ($part in ($HomePath -split '[\\/]+')) {
        $word = $part.TrimEnd('.', ' ').ToLowerInvariant()
        if ($word -eq 'steamapps' -or $word -eq 'path of exile 2') {
            return ("the install home may not lie in a '" + $part + "' folder " +
                    "(a Steam library or the game's own folder); install " +
                    "AshLight in its own folder")
        }
    }
    return $null
}

function Resolve-AlHome([string]$Given) {
    $text = $Given
    if (-not $text) { $text = [string]$env:AL_INSTALL_DIR }
    $text = $text.Trim().Trim('"')
    if (-not $text) {
        $base = ([string]$env:LOCALAPPDATA).Trim().Trim('"')
        if (-not $base) { $base = Join-Path $HOME 'AppData\Local' }
        $text = Join-Path (Join-Path $base 'Programs') $AlName
    }
    return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($text)
}

function Assert-AlUrl([string]$Url) {
    $uri = $null
    if (-not [Uri]::TryCreate($Url, [UriKind]::Absolute, [ref]$uri)) {
        throw ('not an absolute address: ' + $Url)
    }
    if ($uri.Scheme -ne 'https' -or -not $uri.IsDefaultPort -or $uri.UserInfo) {
        throw ('only plain https addresses are fetched: ' + $uri.Host)
    }
    if ($AlHosts -notcontains $uri.Host.ToLowerInvariant()) {
        throw ('host not allowed: ' + $uri.Host)
    }
    return $uri
}

function Get-AlDownload([string]$Url, [string]$OutFile, [string]$UserAgent, [long]$MaxBytes) {
    # the ONE web call site; every redirect hop is checked against $AlHosts
    $uri = Assert-AlUrl $Url
    for ($hop = 0; $hop -le $AlMaxHops; $hop++) {
        $webErr = $null
        $resp = Invoke-WebRequest -Uri $uri.AbsoluteUri -OutFile $OutFile -PassThru `
            -UserAgent $UserAgent -UseBasicParsing -MaximumRedirection 0 `
            -TimeoutSec 600 -ErrorAction SilentlyContinue -ErrorVariable webErr
        if ($null -eq $resp) {
            $why = 'no answer'
            if ($webErr) { $why = [string]$webErr[0].Exception.Message }
            throw ($uri.Host + ': ' + $why)
        }
        $code = [int]$resp.StatusCode
        if ($code -ge 300 -and $code -lt 400) {
            $loc = [string]$resp.Headers['Location']
            if (-not $loc) { throw ('a redirect without a target from ' + $uri.Host) }
            $next = [Uri]::new($uri, $loc)
            $uri = Assert-AlUrl $next.AbsoluteUri
            continue
        }
        if ($code -ne 200) { throw ('HTTP ' + $code + ' from ' + $uri.Host) }
        if ((Get-Item -LiteralPath $OutFile).Length -gt $MaxBytes) {
            throw ('a download is larger than its limit: ' + (Split-Path -Leaf $OutFile))
        }
        return
    }
    throw ('too many redirects from ' + $uri.Host)
}

function Get-AlSha256([string]$Path) {
    # .NET, not Get-FileHash: a powershell.exe started from PowerShell 7
    # inherits a PSModulePath whose Utility module 5.1 cannot load
    $fs = [IO.File]::OpenRead($Path)
    try {
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $bytes = $sha.ComputeHash($fs) } finally { $sha.Dispose() }
    } finally { $fs.Dispose() }
    return ([BitConverter]::ToString($bytes) -replace '-', '').ToLowerInvariant()
}

function Read-AlCapped([string]$Path, [long]$MaxBytes, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw ($Label + ' is missing') }
    if ((Get-Item -LiteralPath $Path).Length -gt $MaxBytes) { throw ($Label + ' is too large') }
    return [IO.File]::ReadAllText($Path)
}

function Get-AlSumLine([string]$SumsText, [string]$Name) {
    # the one '<sha256>  <name>' line of a file, or a refusal
    $found = @()
    foreach ($line in ($SumsText -split "`n")) {
        $line = $line.TrimEnd("`r")
        if ($line -match '^([0-9a-f]{64})  (.+)$' -and $Matches[2] -ceq $Name) {
            $found += $Matches[1]
        }
    }
    if ($found.Count -ne 1) { throw ('SHA256SUMS.txt has no single line for ' + $Name) }
    return $found[0]
}

function Assert-AlSum([string]$Path, [string]$SumsText, [string]$Name) {
    $want = Get-AlSumLine $SumsText $Name
    if ((Get-AlSha256 $Path) -cne $want) {
        throw ($Name + ' does not match its SHA256SUMS.txt line')
    }
}

function Get-AlPythonPin($Release) {
    $pin = $null
    if ($Release.runtimes) { $pin = $Release.runtimes.python }
    if ($null -eq $pin) { throw 'release.json has no python runtime pin' }
    $url = [string]$pin.url
    $sha = [string]$pin.sha256
    $size = $pin.size
    $file = [string]$pin.file
    $uri = Assert-AlUrl $url
    if ($uri.Host -ne 'www.python.org') { throw 'the python pin is not on www.python.org' }
    $leaf = $uri.AbsolutePath.Substring($uri.AbsolutePath.LastIndexOf('/') + 1)
    if ($leaf -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*\.zip$') { throw 'the python pin names no zip file' }
    if ($file -and $file -cne $leaf) { throw 'the python pin file differs from its url' }
    if ($sha -cnotmatch '^[0-9a-f]{64}$') { throw 'the python pin sha256 is not 64 lower-case hex' }
    if (-not ($size -is [int] -or $size -is [long]) -or $size -le 0 -or $size -gt $AlMaxRuntime) {
        throw 'the python pin size is not a positive integer'
    }
    return @{ url = $uri.AbsoluteUri; file = $leaf; sha256 = $sha; size = [long]$size }
}

function Assert-AlPin([string]$Path, $Pin) {
    if ((Get-Item -LiteralPath $Path).Length -ne $Pin.size) {
        throw ($Pin.file + ' does not have the pinned size')
    }
    if ((Get-AlSha256 $Path) -cne $Pin.sha256) {
        throw ($Pin.file + ' does not match its pinned SHA-256')
    }
}

function Clear-AlStage([string]$Stage, [string]$TempRoot) {
    # only AshLight's own bootstrap folder under <home>\temp is removed
    $full = [IO.Path]::GetFullPath($Stage)
    $root = [IO.Path]::GetFullPath($TempRoot).TrimEnd('\') + '\'
    if (-not $full.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -or
            (Split-Path -Leaf $full) -notlike 'bootstrap-*') {
        throw 'refusing to clear a folder that is not the bootstrap folder'
    }
    if (Test-Path -LiteralPath $full) { Remove-Item -LiteralPath $full -Recurse -Force }
}

function Expand-AlZip([string]$ZipPath, [string]$Dest) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $Dest)
}

function Invoke-AlHandOver([string]$Python, [string[]]$Arguments) {
    if ($Runner) {
        & $Runner $Python @Arguments | Out-Host
    } else {
        & $Python @Arguments | Out-Host
    }
    return [int]$LASTEXITCODE
}

function Invoke-AlBootstrap {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'

    # 1. home, by its text alone
    $homeDir = Resolve-AlHome $InstallDir
    $refusal = Get-AlHomeRefusal $homeDir
    if ($refusal) {
        Write-AlLine ('refused: ' + $refusal)
        return 2
    }
    Write-AlLine ('home ' + $homeDir)

    $stamped = Test-AlVersion $AlVersion
    if (-not $Zip -and -not $stamped) {
        Write-AlLine 'refused: this copy of install.ps1 is not from a release; pass -Zip <app zip>'
        return 2
    }
    $repoName = $Repo
    if (-not $repoName) { $repoName = $AlRepo }
    if (-not $Zip -and $repoName -notmatch '^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$') {
        Write-AlLine 'refused: no repository address (-Repo <owner>/<name>)'
        return 2
    }

    $tempRoot = Join-Path $homeDir 'temp'
    $stage = $null
    $code = 1
    $handedOver = $false
    try {
        # 2. the release files
        if ($Zip) {
            $zipPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Zip)
            if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) { throw 'the -Zip file is missing' }
            $folder = Split-Path -Parent $zipPath
            $sumsPath = Join-Path $folder 'SHA256SUMS.txt'
            $releasePath = Join-Path $folder 'release.json'
            $sumsText = Read-AlCapped $sumsPath $AlMaxSums 'SHA256SUMS.txt'
            Assert-AlSum $releasePath $sumsText 'release.json'
            $release = (Read-AlCapped $releasePath $AlMaxRelease 'release.json') | ConvertFrom-Json
            $version = [string]$release.version
            if (-not (Test-AlVersion $version)) { throw 'release.json names no version' }
            $stage = Join-Path $tempRoot ('bootstrap-' + $version)
            Clear-AlStage $stage $tempRoot
        } else {
            $version = $AlVersion
            $stage = Join-Path $tempRoot ('bootstrap-' + $version)
            Clear-AlStage $stage $tempRoot
            $download = Join-Path $stage 'download'
            New-Item -ItemType Directory -Force -Path $download | Out-Null
            [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
            $base = 'https://github.com/' + $repoName + '/releases/download/v' + $version + '/'
            $ua = Get-AlUserAgent $version
            $sumsPath = Join-Path $download 'SHA256SUMS.txt'
            $releasePath = Join-Path $download 'release.json'
            $zipPath = Join-Path $download ($AlName + '-' + $version + '-app.zip')
            Write-AlLine ('fetching release ' + $version)
            Get-AlDownload ($base + 'SHA256SUMS.txt') $sumsPath $ua $AlMaxSums
            Get-AlDownload ($base + 'release.json') $releasePath $ua $AlMaxRelease
            $sumsText = Read-AlCapped $sumsPath $AlMaxSums 'SHA256SUMS.txt'
            Assert-AlSum $releasePath $sumsText 'release.json'
            $release = (Read-AlCapped $releasePath $AlMaxRelease 'release.json') | ConvertFrom-Json
            if ([string]$release.version -cne $version) { throw ('release.json is not for ' + $version) }
            Get-AlDownload ($base + (Split-Path -Leaf $zipPath)) $zipPath $ua $AlMaxAppZip
        }
        if ($release.name -and [string]$release.name -cne $AlName) { throw ('release.json is not for ' + $AlName) }
        $zipName = $AlName + '-' + $version + '-app.zip'
        if ((Split-Path -Leaf $zipPath) -cne $zipName) { throw ('the app zip is not named ' + $zipName) }
        if ((Get-Item -LiteralPath $zipPath).Length -gt $AlMaxAppZip) { throw 'the app zip is too large' }
        Assert-AlSum $zipPath $sumsText $zipName
        Write-AlLine ('verified ' + $zipName)

        # 3. the pinned CPython zip
        $pin = Get-AlPythonPin $release
        if ($RuntimeDir) {
            $rtDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RuntimeDir)
            $pyZip = Join-Path $rtDir $pin.file
            if (-not (Test-Path -LiteralPath $pyZip -PathType Leaf)) { throw ($pin.file + ' is not in the -RuntimeDir folder') }
        } else {
            $download = Join-Path $stage 'download'
            New-Item -ItemType Directory -Force -Path $download | Out-Null
            [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
            $uaVersion = $version
            if ($stamped) { $uaVersion = $AlVersion }
            $pyZip = Join-Path $download $pin.file
            Write-AlLine ('fetching ' + $pin.file)
            Get-AlDownload $pin.url $pyZip (Get-AlUserAgent $uaVersion) $pin.size
        }
        Assert-AlPin $pyZip $pin
        Write-AlLine ('verified ' + $pin.file)

        # 4. unpack the verified bytes and hand over
        $pyDir = Join-Path $stage 'python'
        $appDir = Join-Path $stage 'app'
        New-Item -ItemType Directory -Force -Path $pyDir | Out-Null
        New-Item -ItemType Directory -Force -Path $appDir | Out-Null
        Expand-AlZip $pyZip $pyDir
        Expand-AlZip $zipPath $appDir
        $python = Join-Path $pyDir 'python.exe'
        $boot = Join-Path (Join-Path $appDir ($AlName + '-' + $version)) 'boot.py'
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'the CPython zip holds no python.exe' }
        if (-not (Test-Path -LiteralPath $boot -PathType Leaf)) { throw 'the app zip holds no boot.py' }
        $handArgs = @($boot, 'server.al.install', 'install', '--zip', $zipPath, '--home', $homeDir)
        if ($RuntimeDir) { $handArgs += @('--runtime-dir', $rtDir) }
        if ($NoStart) { $handArgs += '--no-start' }
        Write-AlLine 'handing over to the installer'
        $handedOver = $true
        $code = Invoke-AlHandOver $python $handArgs
    } catch {
        Write-AlLine ('stopped: ' + $_.Exception.Message)
        $code = 1
    }
    if ($stage) {
        try { Clear-AlStage $stage $tempRoot } catch { Write-AlLine 'the bootstrap folder was left in place' }
    }
    if (-not $handedOver) { return 1 }
    if ($code -ne 0) {
        Write-AlLine ('the installer stopped with code ' + $code + '; its report is <home>\logs\reports\last-install.json')
        return $code
    }
    Write-AlLine 'done'
    return 0
}

$alCode = Invoke-AlBootstrap
if ($MyInvocation.MyCommand.CommandType -eq 'ExternalScript') {
    exit $alCode
}
# piped use (irm | iex): never exit the player's own PowerShell window
$global:LASTEXITCODE = $alCode
