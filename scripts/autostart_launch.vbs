' AshLight logon autostart launcher (decision 0011, ROADMAP CORE-AUTOSTART).
' The opt-in scheduled task runs this through wscript.exe so no console
' window ever flashes: it starts scripts\run.ps1 -NoBrowser -Autostart with
' window style 0 (hidden) and does not wait. The repo path is resolved from
' this file's own location at run time; nothing here names a machine path.
Option Explicit
Dim fso, sh, here, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass " & _
      "-WindowStyle Hidden -File """ & here & "\run.ps1"" -NoBrowser -Autostart"
sh.Run cmd, 0, False
