' AshLight logon autostart launcher (decision 0011, ROADMAP CORE-AUTOSTART).
' The opt-in scheduled task runs this through wscript.exe so no console
' window ever flashes: it starts scripts\run.ps1 -NoBrowser -Autostart with
' window style 0 (hidden) and does not wait. The repo path is resolved from
' this file's own location at run time; nothing here names a machine path.
' SEC-ACL-SETUP (F-011): Windows PowerShell is started by its System32 path,
' built from %SystemRoot% at run time, never by a bare name a PATH entry or
' the current folder could shadow.
Option Explicit
Dim fso, sh, here, ps, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
ps = sh.ExpandEnvironmentStrings("%SystemRoot%") & _
     "\System32\WindowsPowerShell\v1.0\powershell.exe"
cmd = """" & ps & """ -NoProfile -NonInteractive -ExecutionPolicy Bypass " & _
      "-WindowStyle Hidden -File """ & here & "\run.ps1"" -NoBrowser -Autostart"
sh.Run cmd, 0, False
