# 0070 - Electron upgrade policy

Date: 2026-11-20. Source: package LOOP-ELECTRON-POLICY (wave 14), finding
F-130 (docs/plan/02-findings.md), research 0046 R1 (a) to (f).
Builds on: decisions 0002 (stack and budgets), 0010 (one process
registry), 0013 (web data opt-in), 0029 (idle state), 0041 (desktop
client), 0068 (Electron and npm supply chain), 0069 (upstream watcher
frame).

## Decision

The Electron pin (app/package.json, app/package-lock.json,
config/electron_pin.json) moves by these rules. The dev-loop watcher
(ELECTRON-WATCH, a source of the decision 0069 frame) and every bump lane
follow them; the app itself never checks versions.

1. Line. AshLight follows the newest stable Electron major.
2. Patch and minor. Weekly, to the newest release of the pinned major
   that is at least 3 days old. Fast path: within 24 h, still to a
   release at least 3 days old where one exists, when `npm audit` reports
   an advisory on a pinned package.
3. Major. Major N+1 is adopted between 14 and 42 days after its .0.0
   release, one major at a time (never N+2 in one bump).
4. End of life. The pin never runs past its line's end-of-life date (the
   `eol` value config/electron_pin.json carries). From 30 days before that
   date the dev host shows a Checks note and the watcher files a ROADMAP
   row; the note is computed offline from the tracked date, so no app
   request is needed (decision 0013 untouched).
5. Gates per bump, by reference: the npm checks of F-037 (decision 0068
   item 1: `npm ci --ignore-scripts` from the lockfile, `npm audit
   signatures`, the 3-day wait), the hash record of F-044 (decision 0068
   items 2 and 4: config/electron_pin.json rewritten from the public
   release with the zip and electron.exe SHA-256 and size, verified at
   setup and run), `npm test --prefix app`, the static guards, and the
   live overlay smoke only in the decision 0029 idle state (log
   staleness, never a process check, no input). A major also re-measures
   the decision 0002 budgets.
6. Apply. A bump is a loop row filed by the watcher and worked by a lane
   in its own worktree (which warms the sidecar caches); the main checkout
   installs at its next setup / run while the client is not live.
   scripts/setup.ps1 refuses the npm step while AshLight's own client
   runs: it ends with one line ("overlay packages NOT changed - <reason>;
   quit it from its tray icon, then run setup again") and exit 3 before
   npm runs. Nothing is changed and no stamp is written, so the bump row
   stays open and a later tick's lane run retries it.
7. A HALTed tick may read the two public JSON files and record the bump
   finding in its checklist, but files, bumps and commits nothing
   (ruling Q-13).

The client-live test in setup.ps1 (Test-AlClientLive) reads two signals,
both about AshLight's own files:
- the process registry: `<runtime>\overlay.pid` through
  `server.al.procs.overlay_main_pid` (that one pid: alive, image
  electron.exe, creation time matching). It never looks at the game and
  never scans the system's processes by name;
- this checkout's own `app\node_modules\electron\dist\electron.exe`
  opened for read-write with no sharing: Windows keeps a running image
  open, so the open fails while any client started from that file lives.
A registry read that fails counts as live (fail closed).

## Choices the package text left open (ruled)

- Second signal (the exe in-use probe). The registry alone misses a
  client started from the Start Menu or desktop shortcut, which writes no
  pid record (only run.ps1 records one). Alternatives: registry only
  (misses shortcut starts, so npm could wipe a live dist); procs.status
  (its directory scan enumerates every process by image name, which the
  package notes rule out). The probe opens only AshLight's own file and
  no process, so it is kept. A failure other than a sharing violation
  (read-only file, ACL) is not taken as a live client.
- Exit code 3 for the refusal. Alternatives: exit 0 (a lane would read
  the step as done and close the row) or throw (exit 1, read as a broken
  setup). 3 is unused by setup.ps1 and means "not now, retry".
- Place: after the up-to-date fast path, right before the override
  clearing and `npm ci`. The fast path changes no file (verify-exe only
  reads), so a live client does not block a no-op setup.
- A registry read failure refuses (fail closed): the same Python already
  ran `server.al.paths` above, so a failure here is rare, and a wrong
  "not live" would swap files under a running overlay.

## Alternatives

- Bump by hand when someone notices: rejected (research 0046 F1: nothing
  watched the pin, and Electron's exposure grows by itself).
- Always the newest release at once: rejected; the 3-day wait and the
  14-day major floor let a bad upstream release be pulled first.
- Stay on one major until its end of life: rejected; it leaves the
  largest jump for the last weeks and loses fixes not back-ported.
- Have the app check for new Electron versions: rejected; decision 0013
  (no request while web data is off) and the update path of decision 0065
  ship whole releases, not runtime bumps.

## Why

Electron is the one dependency whose exposure grows without any change on
AshLight's side (research 0046 F1). A written policy gives the watcher and
the lanes one rule set with waiting periods and gates, and the setup guard
means a bump can never replace files under a running overlay; the refusal
is one line with its fix, and the loop retries by itself.

## Reverses if

- A bad upstream release passes the waiting period and the gates.
- Electron changes its release schedule (majors, support window).
- The operator rules bumps must be manual.
