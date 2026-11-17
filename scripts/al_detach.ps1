<#
.SYNOPSIS
  Start a process fully detached from the caller. Windows PowerShell 5.1.
.DESCRIPTION
  Dot-source this file, then call Start-AlDetached. The process is created by
  WMI Win32_Process.Create, so its parent is the WMI provider host: it is not
  in the caller's process tree or job object and survives the caller (a tool
  shell, a sub-agent, a console window) being closed or tree-killed.
  Start-Process would make it a child of the caller instead.
  Win32_ProcessStartup.EnvironmentVariables REPLACES the whole environment,
  so the caller's environment is copied and the overrides applied on top.
  Returns the new process id; throws when WMI refuses.
#>

function Start-AlDetached {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [hashtable]$Environment = @{}
    )
    $vars = @{}
    $all = [System.Environment]::GetEnvironmentVariables()
    foreach ($k in $all.Keys) { $vars[[string]$k] = [string]$all[$k] }
    foreach ($k in $Environment.Keys) { $vars[[string]$k] = [string]$Environment[$k] }
    $block = [string[]]@($vars.Keys | Sort-Object | ForEach-Object { $_ + '=' + $vars[$_] })

    $cmd = '"' + $FilePath + '"'
    if ($ArgumentList.Count -gt 0) { $cmd = $cmd + ' ' + ($ArgumentList -join ' ') }

    $startup = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{
        ShowWindow           = [uint16]0
        EnvironmentVariables = $block
    }
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine               = $cmd
        CurrentDirectory          = $WorkingDirectory
        ProcessStartupInformation = $startup
    }
    if ($null -eq $r -or $r.ReturnValue -ne 0) {
        $code = if ($null -eq $r) { 'null' } else { [string]$r.ReturnValue }
        throw "Win32_Process.Create failed (ReturnValue $code) for $FilePath"
    }
    return [int]$r.ProcessId
}
