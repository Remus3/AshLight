# 0050 - Reliability review

Date: 2026-11-17. For the ultraplan (docs/plan/README.md), dimension B13
reliability. Scope: every way AshLight's own parts (core, keepalive
supervisor, desktop client and overlay, calc bridge, runtime files, logs)
fail or go quietly wrong, what detects it today, and what would make it heal
by itself and say so in one line. Research and judgement only; no product
code was changed.
Status: draft

## Sources (all accessed 2026-11-17)

- PY-OS: https://docs.python.org/3/library/os.html (os.replace, os.fsync)
- PY-TIME: https://docs.python.org/3/library/time.html (monotonic, time)
- PY-LOG: https://docs.python.org/3/library/logging.handlers.html
- MS-QPC: https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps
- MS-MOVE: https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw
- EL-WC: https://www.electronjs.org/docs/latest/api/web-contents
- EL-GONE: https://www.electronjs.org/docs/latest/api/structures/render-process-gone-details
- EL-APP: https://www.electronjs.org/docs/latest/api/app
- EL-INIT: https://raw.githubusercontent.com/electron/electron/main/lib/browser/init.ts
- NODE-EV: https://nodejs.org/api/events.html (error events)
- SSE: https://html.spec.whatwg.org/multipage/server-sent-events.html
- FILES: https://danluu.com/file-consistency/ (crash consistency of file
  writes; rests on Pillai et al., OSDI 2014)
- X1: scratch experiments run for this note on 2026-11-17, on temp files
  only (never the live runtime dir, the live Client.txt or the game);
  scripts untracked in the sidecar Scratch folder, results quoted inline.
- X2: AshLight's own logs on the operator's machine (`<sidecar>\Logs`),
  counts only, and one GET of /api/health on the live core (200 in 1 ms,
  "tailing": true).
- Repo: decisions 0005, 0008, 0010, 0011, 0023, 0029, 0036, 0041, 0042;
  research 0002; design 0001 sections 7.1 and 11; the files cited inline.

## Summary

Crashes are handled well: a dead core is relaunched after a 5 s poll plus
a 2 s backoff, a hung one inside 97 s; in 21.6 h of supervisor log it
never had to act (X2). The weak side is failure that does not crash: of
31 failure modes, 8 heal by themselves, 12 stay wrong with no cause shown
and 10 need a manual act. Three were reproduced on temp files (X1): one
listener exception kills the log reader for good while the Checks card
still says it is reading; a Client.txt that vanishes and returns, or is
trimmed, replays from byte 0 as live events (24 MB in 0.59 s left 3,200
deaths and 5 open trade cards); a failed run-history write is never
retried. The client has no failure handling, runtime writes are atomic
but not durable, no log is capped. Twelve ranked fixes (R1-R12) and 26
chaos tests follow; none bends the floor or reverses a settled decision.

## Current state

- Supervisor (decision 0005): `server/al/keepalive.py`. Poll 5 s (1 s with
  code reload on), heartbeat stale after 90 s, start grace 60 s, backoff 2
  to 120 s, 5 restarts per 900 s, then a logged give-up (keepalive.py:37-51,
  264-381); single-instance lock (keepalive.py:163-180). The core writes
  `core.alive` every 30 s with pid, port and creation time
  (`__main__.py`:91, 133-142, 266-271).
- Process registry (decision 0010): `server/al/procs.py` proves a process
  ours by pid + image + creation time, or an electron.exe under this
  checkout (procs.py:63-76, 139-154). run.ps1 starts only what `procs
  plan` says is missing; stop.ps1 writes stop.request, waits 15 s, then
  stops the rest.
- Client (decision 0041): one Electron process owns companion window, tray
  and overlay. It reloads both pages when the token file changes, polled
  every 5 s (app/main.js:371-379), and starts the core once per window
  open when /api/health fails (app/client/window.js:125-145).
- Tailer and resume (decisions 0008, 0023): 250 ms stat poll, no handle
  held between polls, 4 MB per poll, lines over 64 KB dropped
  (logfile.py:20-26, 277-346); at first start a backward scan of at most
  32 MB rebuilds zone, level, deaths, act splits and map runs
  (resume.py:40-42, 106-204).
- Hot reload (decision 0042): data files keep the last good copy with a
  Checks row (hotreload.py:118-163); a code change runs a preflight, then
  a clean restart that keeps the token (keepalive.py:404-426).
- Runtime files: every store is bounded (run history 20 runs x 12
  characters, price watch 20 items, map ladder 500 maps x 12, summaries
  20, hints 50 characters). Writes go through `server/al/jsonfile.py`:
  temp file plus os.replace, no fsync, no retry (jsonfile.py:46-62).
- Calc bridge (decision 0022): start on demand, kill on timeout, one
  restart with replay, else the card falls back to stat weights and says
  so (bridge.py:214-235, 302-316).
- Self-checks (decision 0040): 14 Checks rows, among them Reading, Overlay
  and Keepalive (diag.py:226-234); a failed Keepalive row tells the player
  to run a script (diag.py:39, 174-180).
- Logs, all under `<sidecar>\Logs`, none with a cap or rotation: core.log
  (`__main__.py`:73), keepalive.log (keepalive.py:535-545), run.log
  (run.ps1:98-102), overlay.log (app/main.js:49-60; UTC stamps, the others
  local time), tc-bridge.log (PoB's stderr, bridge.py:158-165). Sizes
  after about one day (X2): 7.7, 9.6, 18.8, 13.7 and 387.8 KB; the bridge
  log is 89 percent of the bytes (865 build loads, about 21 lines each).
- Tests today cover the supervisor state machine, the registry and a real
  stop, tailer basics, resume, hot reload, soak, fuzz and HTTP robustness.
  The gaps F3-F8, F10-F13 and F19-F23 below have no test.

## Findings

Per failure mode: detection today, behaviour today, gap, fix (R), chaos
test (C). Tag = what the player gets today: [heals], [silent] (stays
wrong, no cause shown) or [manual].

Supervision and processes

- F1 Core crash. [heals]
  Detect: the supervisor poll finds the pid gone with core.alive left
  behind (keepalive.py:335-341).
  Today: relaunch after the backoff (keepalive.py:354-381); state rebuilt
  by the resume scan; overlay and companion reload on the new token.
  Gap: a plain browser tab keeps the old token; its EventSource stops for
  good on the 401 (http.py:210; SSE) and the pill says "reconnecting"
  forever (web/status.js:36). Nothing tells the player a restart
  happened. Open trade cards are not rebuilt (by design, decision 0008).
  Fix: R5 (restart line), R10. Test: tests/test_keepalive.py:336 exists.
- F2 Core hang (whole process stuck). [heals]
  Detect: heartbeat older than 90 s and /api/health failing
  (keepalive.py:276-280). Today: terminate, relaunch. No gap; see F3, F4.
- F3 Core half alive. [silent]
  Detect: none. The main loop writes the heartbeat and runs every tick
  (`__main__.py`:215-271); the HTTP server has its own thread.
  Today: a stuck main loop with a live HTTP thread reads "ok" (stale
  heartbeat but healthy is left alone, keepalive.py:276,
  tests/test_keepalive.py:221): no log discovery, no saves, no idle
  state, no data reload, for good. A dead HTTP thread with a fresh
  heartbeat is never probed: health is asked only once the heartbeat is
  stale. Fix: R5. Test: C21.
- F4 False kill after sleep, and wall-clock interval math. [heals]
  Today: one failed 3 s health check is enough to kill once the heartbeat
  reads stale (keepalive.py:194, 276), and after a sleep longer than 90 s
  it always reads stale. Every interval uses wall clock
  (keepalive.py:213), which can move backwards (PY-TIME): a clock set
  back N seconds delays a pending restart by N seconds
  (keepalive.py:327-330). time.monotonic ignores clock changes and keeps
  counting through sleep on Windows (PY-TIME, MS-QPC).
  Gap: false kills are decision 0005's own reversal condition; none is
  recorded yet (X2). Fix: R5. Test: C19, C20.
- F5 Supervisor dead or gave up. [manual]
  Detect: Checks row "Keepalive ... is not running" (diag.py:174-180,
  232), visible only while a core still runs. Today: nothing restarts it;
  after a give-up nobody reads the status in keepalive.json
  (keepalive.py:371-375) and the core stays down until the player starts
  AshLight again. Fix: R3. Test: C17, C18.
- F6 Slow start leaves no supervisor. [manual]
  Detect: the same Checks row. Today: run.ps1 exits 1 when the core has
  not answered within 15 s, before it reaches the supervisor start
  (run.ps1:155-160, 169-174, 184-190); the client itself waits 30 s
  (app/client/window.js:33). A slow cold boot leaves a core with no
  supervisor for the whole session: the client never calls run.ps1 again
  while health answers. Fix: R3. Test: C16.
- F7 Client main-process error or crash. [manual]
  Today: app/ has no uncaughtException or unhandledRejection handler, so
  Electron's default handler opens a native error box (EL-INIT): a modal
  that takes focus, against design 0001 section 7.1 and checklist N2. The
  log stream has no error listener (app/main.js:49-60): a write error
  (disk full, locked file) is thrown as an uncaught exception (NODE-EV;
  X1: plain node exits with code 1). After a native crash nothing
  restarts the client (decision 0041 point 2): overlay, tray and both
  hotkeys are gone until the player reopens it. Fix: R2. Test: C13, C14.
- F8 Overlay renderer crash or hang. [manual]
  Today: no render-process-gone, unresponsive, did-fail-load or
  child-process-gone handler exists in app/ (EL-WC, EL-GONE, EL-APP), so
  the overlay stays dead or blank until the player uses tray "Restart
  overlay" (app/main.js:292-304; 0 uses in 50 overlay starts, X2). With
  the compositor in the browser process (app/main.js:113-120) a
  compositor fault is an F7. Fix: R2. Test: C15.
- F9 Calc bridge crash or hang. [heals]
  Detect: stdout EOF or a 60 s call timeout (bridge.py:38, 214-235).
  Today: kill, restart once with the build and items replayed, else the
  card says it used stat weights; the bridge exits on stdin EOF when the
  core dies (bridge.lua:424-426). Gap: only its log (F23).

Client.txt

- F10 Log reader thread dies. [silent]
  Detect: only /api/health turns "tailing": false (http.py:234-238); the
  Checks row stays "Reading Client.txt." (diag.py:80-86): its flag is set
  on start and cleared only on "missing" (state.py:1572-1580).
  Today: bus.publish calls listeners unguarded (bus.py:78-79); the tailer
  loop catches OSError only (logfile.py:245-251); ensure_tailing never
  restarts a dead thread (core.py:730-734). X1: after one listener
  exception the thread was dead, the row read PASS, no later line arrived.
  Gap: one bug in any listener stops all log reading until a restart; 20
  minutes later the overlay hides as "game may be closed" (decision
  0029). The fuzz suite lowers the odds, not the cliff.
  Fix: R1. Test: C1, C2.
- F11 The same file goes missing and comes back, or a configured path
  appears late. [silent]
  Today: any file seen after "missing" is read from byte 0
  (logfile.py:288-295), also a configured path that did not exist at
  start (core.py:608-614). X1: a 1,000-line file renamed away and back
  was re-emitted in full; so was one that appeared late. Every line gets
  the receipt time (state.py:3, 1422), so old whispers become new trade
  cards and old deaths count again: 24 MB replayed in 0.59 s left 3,200
  deaths and 5 open trade cards (X1).
  Gap: "missing first means new" is wrong for an external or late-mounted
  drive, a sleep that drops a USB disk, or a logon start before the game
  drive is ready. Fix: R1. Test: C3, C4.
- F12 Trimmed or truncated in place. [silent]
  Today: offset back to 0 (logfile.py:296-300); whatever the file still
  holds replays as live (X1: 499 of 1,000 lines after a trim to the
  newest half). Whether the game itself ever trims the log is UNVERIFIED
  (research 0002); players and cleanup tools do. Fix: R1. Test: C5.
- F13 File locked or unreadable. [silent]
  Today: an open or stat error is swallowed and retried every 250 ms with
  no status event (logfile.py:245-251; X1: sharing violation 32, zero
  events). It heals when the lock goes; a lasting cause (rights, a broken
  mount) ends in the wrong "game may be closed" state and a hidden
  overlay. Fix: R1. Test: C6.
- F14 Path moved. [manual]
  Today: a discovered path is followed to another Steam library
  (core.py:717-742, tests/test_e2e_replay.py:313); a configured path is
  never looked for again (core.py:733) and the Checks row's fix line
  talks about starting the game (diag.py:68-71). Fix: R1 (row text); Q6.
- F15 Very large file. [heals]
  Today: start at the end, 32 MB backward scan, 4 MB per poll; size alone
  is safe. When the scan hits the cap before the game-start marker,
  counts are partial and only /api/state says so (core.py:696-699).
  Fix: R11 adds the row. The risk sits in F11 and F12.
- F16 Encoding and garbage. [heals]
  Today: UTF-8 with replacement, BOM skipped, NUL runs and lines over 64 KB
  dropped and counted (logfile.py:312-346). No gap found.
- F17 A game update changes line shapes. [silent]
  Detect: none; the language guard covers language only (decision 0040).
  Today: lines stop matching, values freeze, every Checks row stays green.
  PoE2 1.0 is due 2026-12-11 (research 0018, 0021). Fix: R11. Test: C26.
- F18 Resume scan error. [silent]
  Today: any exception from the scan is swallowed with no log line
  (logfile.py:259-263); zone, level and deaths stay empty until the next
  event. Fix: R1 (log it, one Checks note).

Files and disk

- F19 Power loss or crash in the middle of a write. [manual]
  Detect: none. Today: temp file, then os.replace, no flush to disk
  (jsonfile.py:46-53). A rename is atomic in normal running only, not
  across a crash (PY-OS, FILES); os.fsync and a write-through move exist
  for that (PY-OS, MS-MOVE). A torn or empty file reads as the default
  (jsonfile.py:21-37) and the next save overwrites it: history silently
  starts empty. For config/local.json it is worse: reads fall back to {}
  (web data off, contact, paths, layout and port gone) and every write
  is refused (core.py:294-310, http.py:49, 363-364) until the file is
  fixed by hand. No backup copy exists. Fix: R4. Test: C9.
- F20 Replace race on Windows. [silent]
  Today: os.replace raises PermissionError while another handle holds the
  target open without delete sharing (X1: winerror 5, temp file left
  behind, old content kept); antivirus, the indexer or a second reader
  can do that. No retry exists, and the fixed temp name `<name>.tmp`
  (jsonfile.py:40-43) collides if two writers ever meet.
  Fix: R4. Test: C7, C8.
- F21 A failed write is not retried. [silent]
  Today: the stores change memory first, then save. After one failed save
  the next tick finds memory equal to the new data and skips the write
  (runhistory.py:192-208 with core.py:356-362; mapladder.py:171-189). X1:
  the first record raised, the next two returned False, the file was
  never written. A summary card is marked saved before the attempt
  (core.py:775-779); the hint store stops persisting for the session
  after one error (hints.py:113-120); the visits file is retried at 2 Hz
  with no back-off (core.py:399-408). A finished run can be lost at the
  next restart and nothing says so. Fix: R4. Test: C10, C11.
- F22 Disk full. [manual]
  Today: settings answer "AshLight couldn't save the settings."
  (http.py:49); history, visits and price watch fail as F21; core logging
  drops records quietly; the client hits F7. Fix: R4, R2. Test: C11, C14.
- F23 Logs without caps. [silent]
  Today: see Current state. The main loop logs a full traceback for a
  failing tick on every 0.5 s pass (`__main__.py`:226-265): 2 a second,
  about 0.2 GB a day at 1.2 KB each. Fix: R6. Test: C22, C23.
- F24 CRLF writers. [hygiene]
  Checked on disk (X1): core.alive, keepalive.json and overlay.pid end in
  CR LF (`__main__.py`:141, keepalive.py:259, procs.py:223: write_text
  with no newline argument); the token, consent.json and hotreload.json
  are LF (core.py:44 is already fixed). Two flag files share the pattern
  (keepalive.py:419, hotreload.py:283). Nothing breaks: FLEET item 8
  only. Fix: R4.

Environment

- F25 Port in use. [manual]
  Detect: bind error in core.log, exit code 2 (`__main__.py`:170-173).
  Today: run.ps1 waits 15 s and exits 1; after 30 s the client shows a
  generic line about Python (app/client/starting.html:15). The cause is
  never named. Fix: R8. Test: C24.
- F26 Double start and stop/start race. [manual]
  Today: double starts converge (plan, exclusive bind at http.py:99-102,
  supervisor lock, Electron single-instance lock). But stop terminates
  every electron.exe under the checkout (procs.py:271-276), so a client
  reopened while stop.ps1 still runs can be killed. X2: 1 of 39 stops
  logged "still running: overlay" in the second a new start launched the
  core. Fix: R9. Test: C25.
- F27 Stale pid and flag files. [heals]
  Today: stale core.alive, keepalive.json and overlay.pid read as not
  live (creation time, image); stop.request and restart.request are
  cleared at start (`__main__.py`:201-203, run.ps1:126). Nit: procs.py:172
  and 178 call int() on the pid without the guard of procs.py:132-135.
- F28 Clock step inside the session state. [silent]
  Today: zone, session, act and pace times are wall-clock receipt times
  (state.py:3, 1422); a clock step moves them by the step. The resume
  scan maps log stamps to epoch by local-time rules (resume.py:252-262),
  so the repeated hour at the end of daylight saving can be an hour off.
  Sleep is fine: the idle state after 20 quiet minutes is correct.
  Fix: R12 (low).
- F29 Logon autostart (decision 0011). [manual]
  Today: starts core and supervisor only (decision 0041 point 2): no
  overlay, tray or hotkey until the player opens the client. Inherits
  F6. Python missing from PATH fails before run.log exists
  (run.ps1:55-78). Fix: R3 for F6; Q2 for the tray question.
- F30 Network trouble with web data on. [silent]
  Today: a refresh starts only when a page asks GET /api/rates
  (http.py:287-293), and the page asks every 5 minutes only while visible
  and connected (web/app.js:800, 901-903). With the window closed to the
  tray (decision 0041 point 4) prices never refresh. A truncated chunked
  body or a bad status line escapes the transport as http.client errors
  that are not FetchError (webfetch.py:163; X1) and ends the refresh
  thread with a traceback and no `last_error` (ninja.py:285). A failed
  attempt blocks the next one for an hour (ninja.py:11-13, 56).
  Fix: R7. Test: C12.
- F31 Hot reload and updates. [heals]
  Today: last good copy plus a Checks row for a bad data file; a bad code
  edit keeps the running core; a new core that dies never loops. Gaps:
  any stat error drops the last good copy to the default with no note
  (hotreload.py:110-115, 144-146); outside a source checkout nothing
  restarts the core after an update replaces its files, so old code can
  serve new web files (for research 0052).

What the player sees today, by tag: [heals] 8 (F1, F2, F4, F9, F15, F16,
F27, F31), only F9 and F31 say so; [silent] 12 (F3, F10-F13, F17, F18,
F20, F21, F23, F28, F30); [manual] 10 (F5-F8, F14, F19, F22, F25, F26,
F29); hygiene 1 (F24).

## Recommendations

- R1 TAIL-HEAL: the log reader never dies and never replays a backlog.
  Action: guard each line callback (log the first error, count the rest,
  keep reading); let ensure_tailing restart a dead reader thread; when the
  same file identity returns, continue from the old offset; after any other
  break read from byte 0 only if the file is new and at most 64 KB, else
  jump to the end and run the existing resume scan; after 20 failed polls
  (5 s) publish an "unreadable" status; log a failed resume scan.
  Impact: H - removes F10-F13 and F18. Effort: M. Risk: a log recreated
  by a game restart must still be read from its first line; the 64 KB
  rule covers it (a new log is seen within 250 ms).
  ToS check: floor rule "READ ONLY ... Client.txt, tailed only after the
  user's opt-in": same file, same opt-in, read-only with full sharing,
  fewer bytes read than today. Decision 0008 stands (scan only).
  Depends on: none. Files: server/al/logfile.py, core.py, state.py,
  diag.py, tests/test_tailer.py, tests/test_e2e_replay.py.
  Acceptance: C1-C6; tailer, e2e and budget suites stay green.
  ZERO-CLICK: automatic; one line ("AshLight restarted its log reader.").
- R2 CLIENT-GUARD: the client survives its own errors without a dialog.
  Action: in app/main.js add uncaughtException and unhandledRejection
  handlers that log and carry on (3 in 60 s: app.relaunch, exit; EL-APP); an
  error listener on the log stream; render-process-gone, unresponsive
  (30 s) and did-fail-load handlers that rebuild the overlay window, at
  most 3 times in 10 minutes, and reload the companion; a
  child-process-gone log line.
  Impact: H - no modal over the game, the overlay comes back by itself.
  Effort: S. Risk: a handler can hide a real bug; every event is logged
  with its stack and the caps stop a loop.
  ToS check: floor rule "the overlay is a SEPARATE ... click-through,
  non-focusable window ... must not cost game FPS": handlers run only on
  failure events in the main process, the page gets no timer.
  Depends on: none. Files: app/main.js, app/client/window.js, app/test/
  (new guard test), tests/test_overlay_smoke.py.
  Acceptance: C13-C15; node tests and the overlay budget test stay green.
  ZERO-CLICK: automatic; the tray tooltip changes only after the cap.
- R3 SECOND-LINE: nothing stays down.
  Action: run.ps1 starts the supervisor before it waits for health and
  hands it the core pid (new --adopt-pid, 60 s start grace); the core
  starts a missing supervisor (not live for 3 Checks ticks, no
  stop.request, at most once per 5 minutes); the client checks
  /api/health every 30 s and after 4 failures (120 s) runs run.ps1 once,
  at most once per 15 minutes, and shows the supervisor's give-up reason
  from keepalive.json when there is one.
  Impact: H - removes F5, F6 and the manual fix line. Effort: M. Risk:
  restart loops; every layer keeps its cap and stop.request wins.
  ToS check: only AshLight's own python processes are started or stopped,
  proven by pid and creation time (decision 0010); the game process is
  never listed (decision 0029). Decision 0041 stands: the supervisor
  never starts Electron.
  Depends on: none. Files: scripts/run.ps1, server/al/keepalive.py,
  core.py, procs.py, app/client/window.js, app/client/launcher.js,
  tests/test_supervisor.py, tests/test_procs.py, app/test/client.test.js.
  Acceptance: C16-C18. ZERO-CLICK: automatic; "Keepalive was not running;
  AshLight started it again." on the Checks card.
- R4 DURABLE-WRITES: one hardened write path for every runtime file.
  Action: in jsonfile write_text / write_bytes use a unique temp name,
  flush and os.fsync before os.replace, retry the replace 5 times over
  250 ms on PermissionError, remove the temp file on failure; keep one
  `.bak` of the last good copy for the files that hold player data
  (config/local.json, consent, run history, map ladder, visits, builds)
  and restore from it when the main file does not parse; give the stores
  a dirty flag flushed from the core tick with back-off 1, 5, 30, 60 s;
  move the CRLF writers of F24 onto the helper.
  Impact: H - removes F19-F22 and F24. Effort: M. Risk: fsync cost,
  measured at +0.7 ms (2 KB) and +1.0 ms (700 KB) per write on the target
  machine (X1); the heartbeat stays unsynced.
  ToS check: local files in the repo's runtime dir and the AL sidecar only
  (CLAUDE.md Sidecar rule, tests/test_sidecar_paths.py); no game file.
  Decision 0036 stands (bounded files, same allow-list).
  Depends on: none. Files: server/al/jsonfile.py, core.py, runhistory.py,
  mapladder.py, pricewatch.py, summary.py, hints.py, zoneguide.py,
  `__main__.py`, keepalive.py, procs.py, hotreload.py, diag.py,
  tests/test_jsonfile.py.
  Acceptance: C7-C11; the three files of F24 end in LF. ZERO-CLICK:
  automatic; one Checks row while a store is unsaved; "Settings were
  damaged and restored from the last good copy."
- R5 SUPERVISOR-CLOCK: a liveness verdict that cannot misfire.
  Action: time.monotonic for every interval in keepalive.py; a stale kill
  needs 2 failed health checks 5 s apart; a poll gap over 3 polls + 10 s
  opens a 60 s no-kill grace; /api/health gains loop_age_s and a value
  over 60 counts as a failed check; with a fresh heartbeat health is still
  probed every 30 s and 3 failures in a row count as hung; keepalive.json
  records last_restart {at, reason} and the Checks card shows it for 10
  minutes.
  Impact: M - closes F3 and F4 and gives F1 and F2 their one line.
  Effort: S to M. Risk: worst-case hang recovery grows from 97 s to
  102 s, inside the 120 s budget tests/test_keepalive.py:83 asserts.
  ToS check: only AshLight's own core is probed (loopback, token) and
  terminated (python image, creation time); no game contact.
  Depends on: none. Files: server/al/keepalive.py, `__main__.py`, http.py,
  diag.py, tests/test_keepalive.py, tests/test_supervisor.py.
  Acceptance: C19-C21; supervisor suites stay green. ZERO-CLICK: automatic;
  "AshLight restarted its core at 21:14 (it had stopped answering)."
- R6 LOG-CAPS: every log bounded.
  Action: core.log on RotatingFileHandler (2 MB, 2 backups; PY-LOG) with
  faulthandler on its own small file; a repeating tick error is logged
  once, then once a minute with a count; keepalive.log, run.log,
  overlay.log and tc-bridge.log rotate at open when over 1 MB, one old
  file kept.
  Impact: M - at most about 14 MB of logs; ends F23. Effort: S. Risk: a
  rotation fails while another process holds the file; these logs have
  one writer each and a failed rotation keeps appending.
  ToS check: AshLight's own logs in the sidecar; no game file.
  Depends on: research 0051 for format choices. Files: server/al/
  `__main__.py`, keepalive.py, theorycraft/bridge.py, scripts/run.ps1,
  scripts/stop.ps1, app/main.js, tests/test_core_crash_log.py.
  Acceptance: C22, C23. ZERO-CLICK: automatic; no line needed.
- R7 PRICE-TICK: prices refresh without a visible page.
  Action: the core loop calls rates.refresh_async() once a minute while
  web data is on and the log is not idle (the hourly gates decide); map
  http.client.HTTPException to FetchError in webfetch._open_once; a
  failure that got no HTTP answer may retry after 5 minutes, at most 3
  times an hour, if research 0036 finds that inside poe.ninja's terms.
  Impact: M - fresh prices with the window closed to the tray. Effort: S.
  Risk: none new for poe.ninja: still at most one request per endpoint
  per hour (ninja.py:56), and none while idle.
  ToS check: floor rules "public web data ... poe.ninja" and "truthful
  User-Agent"; decision 0013 opt-in and decision 0026 gates unchanged; no
  new host, no trade endpoint.
  Depends on: research 0036 for the retry part only. Files: server/al/
  core.py, webfetch.py, ninja.py, tests/test_data_ninja.py,
  tests/test_price_book.py.
  Acceptance: C12, plus a refresh with no HTTP client connected and none
  while idle or opted out. ZERO-CLICK: automatic.
- R8 START-REASON: a start failure names its cause.
  Action: on a bind failure the core probes the port once; an AshLight
  core answering means "already running", anything else writes
  ops/runtime/start-error.json; run.ps1 and the client's failed page
  print that one line; the port checks of AUDIT-P8-LOW P8-3 and P8-4 land
  in the same change.
  Impact: M - a first-run blocker gets a cause instead of a Python hint.
  Effort: S. Risk: low.
  ToS check: loopback only; "Bind 127.0.0.1 only" and the port block stay.
  Depends on: none. Files: server/al/`__main__.py`, ports.py,
  scripts/run.ps1, app/client/window.js, app/client/starting.html,
  starting.js, app/main.js, tests/test_port_resolve.py.
  Acceptance: C24. ZERO-CLICK: the line names the one fix; moving to a
  free port in the block by itself is Q5.
- R9 STOP-RACE: stop only what was running when stop was asked.
  Action: procs.stop terminates only overlay pids created before
  stop.request was written and ignores younger ones in its final check.
  Impact: L to M - a quick quit and reopen keeps the new client (F26).
  Effort: S. Risk: low.
  ToS check: own processes only, proven by image path and creation time.
  Depends on: none. Files: server/al/procs.py, scripts/stop.ps1,
  tests/test_procs.py. Acceptance: C25. ZERO-CLICK: automatic.
- R10 FEED-TRUTH: the page says what really happened to the feed.
  Action: when the EventSource is closed, web/app.js asks /api/health; a
  401 shows "AshLight restarted. Open it again from the tray." instead of
  "reconnecting", anything else reconnects every 3 s; the SSE keep-alive
  becomes a named event so the overlay marks the feed stale after 45 s.
  Impact: L - plain browser tabs and a frozen core only. Effort: S.
  Risk: low. ToS check: loopback API only; the per-start token rule is
  unchanged. Depends on: none. Files: web/app.js, web/status.js,
  server/al/http.py, app/overlay/overlay.js, app/shared/.
  Acceptance: a page test with a 401 after a live feed shows the line.
  ZERO-CLICK: the client window already reloads itself; a browser tab
  cannot get the new token by design, so one honest line is the minimum.
- R11 LOG-DRIFT: notice a changed log format and a capped scan.
  Action: count prefixed lines that carry a known anchor ("Generating
  level", "[SCENE]", "is now level", "has been slain") but match no
  pattern; 3 in a session add a Checks note; add a note when the resume
  scan hit its 32 MB cap. Counts only, no line text kept.
  Impact: M around the 1.0 patch. Effort: S. Risk: a false note; the
  live-shapes fixture must produce 0.
  ToS check: Client.txt lines already tailed; nothing stored or sent.
  Depends on: none. Files: server/al/parser.py, state.py, diag.py,
  tests/test_parser.py, tests/test_diag_self.py.
  Acceptance: C26. ZERO-CLICK: automatic; "The game's log looks different
  from what AshLight knows (a game update?)."
- R12 CLOCK-STEP: timers survive a clock change.
  Action: the core loop compares wall and monotonic deltas each pass; a
  difference over 5 s shifts the state's stored stamps by the step under
  the state lock and logs one line.
  Impact: L - rare; wrong timers and act splits until the next zone.
  Effort: M. Risk: many stamps; one SessionState method, property test.
  ToS check: no floor rule touched (the core's own clock math).
  Depends on: none. Files: server/al/`__main__.py`, state.py, acts.py,
  runs.py, pace.py, tests/test_bus_state.py.
  Acceptance: a fixed-clock test: a +3600 s step leaves zone time, act
  splits and the idle state unchanged. ZERO-CLICK: automatic.

Sequencing for parallel waves: R2 and R9 share no file with the rest. R1,
R4 and R7 each add one small hook to core.py; R5, R6 and R8 all edit
`__main__.py`. Run R1, R2, R4, R9 in one wave, then R5 + R6 + R8 as one
package, then R3, R7, R10-R12. Land each chaos test first as an expected
failure, then the fix.

## Chaos tests (CI, no game)

All use tmp runtime dirs under the existing guard (tests/conftest.py);
pytest unless marked node; "Win" needs Windows (share modes, process APIs,
PowerShell 5.1). Each stays under 2 s except C16, C17 and C25 (real
processes, about 15 s each; a `chaos` marker lets research 0049 shard
them). Setup -> expected result:

- C1 A listener raises on one line -> thread alive, next line delivered.
- C2 The reader thread dies -> restarted within 5 s; row not PASS between.
- C3 1,000-line file renamed away and back -> 0 lines re-emitted.
- C4 Missing path, then an old 1,000-line file appears -> 0 events, state restored.
- C5 File trimmed in place to its newest half -> deaths unchanged, no trade card.
- C6 (Win) File held with share mode 0 for 6 s -> "unreadable" within 5 s, then cleared.
- C7 os.replace fails twice with PermissionError -> third try lands, no temp file left.
- C8 (Win) A reader holds the target during a write -> never a torn file.
- C9 config/local.json cut to 0 bytes, then to half -> backup restored, a write works.
- C10 A run-history write fails once -> a later tick writes the run.
- C11 Writes fail for 30 ticks -> at most 4 attempts, one Checks row, cleared on success.
- C12 Transport raises IncompleteRead / BadStatusLine -> an error result, last_error set.
- C13 (node) Uncaught exception in main -> logged, error box never called, process lives.
- C14 (node) The log stream emits an error -> nothing is thrown.
- C15 (node) render-process-gone -> window rebuilt; not the 4th time inside 10 minutes.
- C16 (Win) run.ps1 with a core that needs 20 s -> one core, a supervisor running after.
- C17 (Win) Supervisor killed -> restarted by the core within 20 s; not under stop.request.
- C18 (node) 4 failed health checks -> one start; a second streak inside 15 min -> none.
- C19 Wall clock steps back 3,600 s during a pending restart -> it still fires on time.
- C20 A 600 s poll gap, then one failed health check -> no kill; two more later -> kill.
- C21 Stale heartbeat, health ok, loop_age_s 300 -> relaunch; with a fresh loop -> left.
- C22 A tick raises on 600 passes -> core.log grows by under 50 KB.
- C23 core.log starts at 2.1 MB -> rotated at the next record.
- C24 (Win) A plain socket holds the port -> exit 2, the error file names the port.
- C25 (Win) A fake overlay starts after stop.request -> stop leaves it.
- C26 Three anchor lines in a changed shape -> one Checks note; live-shapes fixture -> none.

## Cut or merge

- Merge CODE-HEALTH-FOLLOWUP item 3 (CRLF) into R4: same lines of code.
- Merge S5-FOLLOWUP item b (checked-item list lost on a restart) into R4:
  if it is persisted, it uses the same store helper and backup.
- Merge AUDIT-P8-LOW P8-3 and P8-4 (port checks) into R8.
- Keep tray "Restart overlay" as the manual fallback (0 uses so far).
- Add no new watchdog process: R3 gives each existing part a neighbour.

## Rejected

- Check the process list for the game to tell "game closed" from "log
  unreadable": against decision 0029; its reversal conditions are not met.
- Persist session state on every event: rejected by decision 0008; no
  evidence for its reversal (0 crashes logged, the cap not shown to fail).
- Let the supervisor start Electron: against decision 0041 point 2.
- Keep the token across a crash restart so browser tabs reconnect: it
  widens decision 0042's narrow reuse (a restart the supervisor asked
  for, 120 s) and weakens the per-start token; the client window already
  heals, so the gain is a browser tab only.
- A scheduled task that polls the supervisor every minute: decision 0005
  alternative B; the log shows no supervisor failure.
- A Windows service for the core: needs admin rights, against the
  no-admin stance of decisions 0011 and 0041.
- Write a marker into the game's log folder, or hold Client.txt open, to
  detect rotation: the floor forbids modifying any game file, and the
  tailer holds no handle between polls on purpose (logfile.py:277-280).
- Send a key to the game so it writes a log line as a liveness probe:
  any synthesized input is outside the floor.

## Open questions

- Q1 (adjudicator): after a native crash of the client, may the core
  start it again? Decision 0041 point 2 names only the supervisor.
- Q2 (operator): should logon autostart bring the client up in the tray,
  so overlay and hotkeys exist when the game starts? Decision 0041 says
  no overlay at logon today; the cost is the client's RAM while idle.
- Q3: how long is a cold core start at logon on the target machine? The
  15 s limit in run.ps1 was never measured cold (needs a reboot).
- Q4: does PoE2 itself ever truncate or rotate Client.txt, and how fast
  does the log grow with chat on? Both UNVERIFIED in research 0002; they
  set the real margin of the 32 MB scan cap.
- Q5 (adjudicator): on a port conflict, move to the next free port in the
  block by itself, or only say so (R8)?
- Q6: when a configured Client.txt path is gone and discovery finds
  exactly one other log, switch by itself or only offer it?
- Q7: the retry spacing after a network failure with no HTTP answer (R7)
  waits for research 0036's reading of poe.ninja's terms.
