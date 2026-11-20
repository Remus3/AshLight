# 0011 - Core autostart at logon: opt-in current-user scheduled task

Date: 2026-11-17. Trigger: ROADMAP row CORE-AUTOSTART (filed by decision
0005 option C: autostart is a separate concern with its own opt-in).

## Decision

- `scripts/autostart.ps1 -Enable | -Disable | -Status [-DryRun]` (Windows
  PowerShell 5.1, idempotent). OFF by default; enabling is a deliberate
  operator act: `powershell -ExecutionPolicy Bypass -File
  scripts\autostart.ps1 -Enable`.
- -Enable registers ONE scheduled task, `\AshLight Autostart`, for the
  current user only: trigger at that user's logon with a 30 s delay,
  principal LogonType Interactive, RunLevel Limited (no admin rights),
  10 min execution limit, IgnoreNew. Action: `wscript.exe //B //NoLogo
  "<repo>\scripts\autostart_launch.vbs"`, the repo path resolved at run
  time from the script's own location (no machine path tracked).
- The launcher starts `scripts\run.ps1 -NoBrowser -Autostart` with window
  style 0, so no console flashes at logon.
- Amended 2026-11-19 (REL-AUTOSTART-ENTRY, findings F-170 / DEP-07): the
  action is no longer wscript. It is `pythonw.exe -m
  server.al.autostart_entry` (built by paths.python_cmd) with the checkout
  root as working directory; the entry point checks the opt-in and starts
  `scripts\run.ps1 -NoBrowser -Autostart` through Windows PowerShell by
  its System32 path with CREATE_NO_WINDOW and does not wait.
  `scripts\autostart_launch.vbs` is deleted (Windows is retiring VBScript).
  The task is written, read back and removed by `scripts\al_shell.ps1`
  (Register-AlLogonTask / Unregister-AlLogonTask / Get-AlLogonTask, the
  DEP-07 effect-root rule); a task of the same name whose action's working
  directory lies outside the checkout is left alone, and -Enable then
  records no opt-in.
- The opt-in is recorded in the gitignored `ops/runtime/autostart.json`
  ({enabled, task, updated}). `run.ps1 -Autostart` reads it and is a
  logged no-op unless enabled, so a task left behind (e.g. after a manual
  file edit) never starts anything the operator turned off.
- -Disable removes the task and records enabled false. -Status is read
  only. -DryRun prints the task definition (or the removal) as JSON and
  changes nothing; the tests use it with tripwires on every cmdlet that
  could register a task or write the registry.
- The keepalive supervisor (decision 0005) starts with the core as usual.
  Never touches the game process (decision 0003 floor).

## Alternatives

- HKCU Run key: no admin, but no delay, no "start only once" setting, and
  any child console flashes unless wrapped anyway; harder to inspect.
- Startup folder shortcut: no admin and visible to the user, but no delay
  and a shortcut to a .ps1 opens a console; also easy to leave orphaned.
- Scheduled task at logon (chosen): native delay, IgnoreNew, a clear
  name in Task Scheduler, user-scope without elevation when the trigger
  names the current user, scriptable Status / Disable.
- Calling `schtasks.exe /sc onlogon`: needs elevation on Windows 10;
  rejected.

## Reverses if

Register-ScheduledTask is refused for a standard user on the target
machine (then the HKCU Run key with the same pythonw entry point), or logon
autostart is no longer wanted (then -Disable and remove the row).

## Amendment 2026-11-18 (REL-AUTOSTART-TRAY, plan unit F-073, ruling Q-08)

- Decision: when the opt-in is on, the logon start is the desktop client
  tray-only, not the core alone. The pythonw entry point
  (`server.al.autostart_entry`, no VBScript) starts `scripts\run.ps1
  -Autostart` only (no `-NoBrowser`). run.ps1 -Autostart checks the
  opt-in as before; with the client installed
  (`app\node_modules\electron\dist\electron.exe`) it converges the core
  and supervisor and starts the client as `electron app --client --tray`;
  without the client it stays core-only. A logon start never opens the
  browser, and a client that is already live is left alone (a second
  `--client` start would show its window). In tray-only mode the client
  builds the tray and connects the core, creates no companion window and
  takes no focus; the overlay is gated by the log as always (decision
  0029, Client.txt freshness only, never a process check). A tray click
  or the Start Menu shortcut's `--client` start shows the window. The
  task description now reads "start AshLight in the tray at logon"
  (an existing task is rewritten once on the next -Enable).
- Alternatives: core-only at logon (the old behaviour) - kept only as
  the no-client path and the memory fallback: it gives no tray and no
  overlay until the player opens the client, which is a click per
  logon; start the full client with its window - rejected: a window
  popping up at logon, possibly over the game; start the tray client
  on the first fresh log line (the F-073 fallback) - not taken: it
  needs a new core tick that spawns Electron, and the measured footprint
  below does not call for it.
- Why: zero-click after the one opt-in: every logon brings up the tray,
  the overlay (hidden while the game is idle) and the core with no click
  and no window. Memory: tray-only is the client process without the
  companion renderer, the same process set the overlay smoke measures
  (decision 0002, UX-OVL-RAM: 2 processes, about 180 MB summed working
  set, under the 250 MB budget). The live tray-only idle measurement
  (`<sidecar>/Logs/tray_idle.json`) is cross-checked by the budget-log
  package (RUN) once it lands; a package build never starts Electron.
- Reverses if: the task is refused for a standard user, autostart is no
  longer wanted, or idle tray-mode memory exceeds the decision 0002
  budget (then core-only at logon, and the tray client starts on the
  first fresh log line).
