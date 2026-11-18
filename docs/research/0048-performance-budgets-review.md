# 0048 - Performance budgets review (speed, RAM, FPS)

Date: 2026-11-17. For the ultraplan (docs/plan/README.md), dimension B11
speed, RAM, FPS budgets. Scope: what decisions 0002, 0024 (R7) and 0028
promise, what the tests assert, what the core, dashboard, overlay / client
and calc bridge cost (measured), the budgets to adopt, the tests that
enforce them, the cheapest wins and a five-minute OVL-FPS / OVL-BUDGET
protocol. No product code was changed.
Status: verified

## Sources (all accessed 2026-11-17)

S1, S2, S3, S4, S5, S8 and the Electron CPUUsage page were re-fetched
by the verifier on 2026-11-18 and support the claims below.

Web:
- S1 Microsoft Learn, DXGI flip model guidance (page metadata updated
  2026-04-15): https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/for-best-performance--use-dxgi-flip-model
- S2 DirectX developer blog on fullscreen optimizations (2019-12-17):
  https://devblogs.microsoft.com/directx/demystifying-full-screen-optimizations/
- S3 Electron app API (getAppMetrics, disableHardwareAcceleration):
  https://www.electronjs.org/docs/latest/api/app
- S4 Electron ProcessMetric and MemoryInfo structures:
  https://www.electronjs.org/docs/latest/api/structures/process-metric and
  https://www.electronjs.org/docs/latest/api/structures/memory-info
  (all sizes in kilobytes; privateBytes is Windows only), and CPUUsage:
  https://www.electronjs.org/docs/latest/api/structures/cpu-usage
  (idleWakeupsPerSecond always reads 0 on Windows)
- S5 Electron BrowserWindow (page visibility, showInactive, levels):
  https://www.electronjs.org/docs/latest/api/browser-window
- S6 Electron WebPreferences (backgroundThrottling):
  https://www.electronjs.org/docs/latest/api/structures/web-preferences
- S7 Chromium note on Windows native window occlusion:
  https://chromium.googlesource.com/chromium/src/+/master/docs/windows_native_window_occlusion_tracking.md
  (background only; not relied on: Electron's own page, S5, says a
  Windows window reads hidden only when minimised or hidden)
- S8 Microsoft Learn, scheduling priorities (dated 2025-07-14):
  https://learn.microsoft.com/en-us/windows/win32/procthread/scheduling-priorities
- S9 Python subprocess, Windows constants (priority classes, 3.7+):
  https://docs.python.org/3/library/subprocess.html
- S10 Community reports on overlays and flip modes (forum threads, seen
  only through a search summary): UNVERIFIED.
- S11 PoE2 FPS display: a player guide on the official forum (thread
  3852015, search summary only) names a Graphics option "Graph Details";
  whether PoE1's F1 key works in PoE2: UNVERIFIED.

Repo: decisions 0002 (budgets, lines 52-63), 0006, 0024 (R7), 0028, 0029,
0040, 0041, 0042; research 0007, 0012; docs/audit/2026-11-17-audit.md
(P8-5, lines 947-950); ROADMAP OVL-BUDGET, OVL-FPS (lines 56-70).

Own measurements (M1-M10 below): throwaway scripts under
`<sidecar>\Scratch`, at below-normal priority, on the operator's machine
(Windows 10, Python 3.14, Electron 45.3.3). They read only AshLight's own
processes and feed, a test core in a scratch runtime and a headless
browser; never the game, its window or the live Client.txt; no
PresentMon, no ETW (decision 0006).

## Summary

- Normal use is far inside the CPU budgets: live core 0.10 percent of a
  core, client 0.000, dashboard 2.0 ms per push; Electron 169 MB (budget
  250), core 46 MB (budget 60).
- Two defects: the map ladder tick (audit P8-5) costs 2.7 percent of a
  core at 200 session and 500 saved maps, unseen by any test; with the
  calc on, the item check card takes 3.5 to 10.9 s where 0.5 s is possible.
- RAM beside the game: luajit keeps 517 to 527 MB after one press, more
  than the rest of AshLight together (248 MB).
- Of decision 0002's eight budgets, two run in the normal suite (the
  burst, and core idle in part), two only in an opt-in smoke no lane
  runs, two only as static source checks, and two never (core RSS, game
  FPS). The shipped client shape is unmeasured, and the calc's time
  ceilings sit 5.5 to 25 times above today's values.
- Cheapest wins: R1, R2, R3, R7, R10. R4 closes OVL-BUDGET with no
  operator action; R5 makes OVL-FPS one normally played map.

## Current state

### Budgets: written and enforced

Decision 0002 (lines 52-63):
- Core idle under 1 percent of one core over 10 s. Test:
  tests/test_budgets.py:142-185, but over 3 s, and with the tailer, HTTP
  and two feed streams only. The 0.5 s loop that runs ten tick functions
  (server/al/__main__.py:215-265) is not started, so every per-tick cost
  is outside the test. A second test covers the tailer alone at 2
  percent (test_budgets.py:52-65).
- Core RSS under 60 MB. Not tested; only growth is: under 20 MB after
  50,000 events (test_budgets.py:121-137), and the soak's heap growth.
- 1,000-line burst under 50 ms. Tested (test_budgets.py:37-49); also
  10,000 lines parsed under 250 ms (27-34) and the 32 MB resume scan
  under 500 ms (68-84).
- Overlay idle CPU under 1 percent; all Electron processes under 250 MB
  (tightened to 215 MB and 2 processes). Only in the opt-in live smoke
  (tests/test_overlay_smoke.py:174-214, AL_OVERLAY_SMOKE=1), which no
  suite and no lane sets, and which starts the overlay alone (line 185),
  with no core and no feed. The shipped mode is the client (decision
  0041): tray, overlay and, while open, a companion window with a second
  renderer. That shape has never been measured.
- No frames while no event arrives; acceleration off. Static source
  checks only (test_overlay_smoke.py:47-54, 125-130) and the render gate
  unit tests; nothing counts frames.
- Game FPS loss under 1 percent. Never measured (ROADMAP OVL-FPS); one
  GPU-utilisation proxy at character select with a saturated GPU.

Decisions 0024 R7 and 0028: ceilings in tests/tc_live_util.py:91-101,
asserted by tests/test_math_perf.py and tests/test_math_e2e_live.py only
where the optional component and the reference build exist. Ceiling /
measured: cold start 30 s / 1.2; load 5 s / 0.36; reload 5 s / 0.29; set
item 2 s / 0.09; first press 60 s / 10.9; warm press 30 s / 3.5; repeat
10 s / 1.3; fallback press 30 s / not measured here; luajit peak 768 MB
/ 490 to 527 (decision 0024 R7 records the same ceilings). A fivefold
slowdown passes
every time ceiling.

No budget exists for: the supervisor, the client with the companion
open, snapshot size, feed pushes while idle, dashboard render cost
(UX-PERF measured it once), start-up, press to first card, file polling.

### Measured 2026-11-17

- M1 Imports (`python -X importtime`, core plus HTTP): 253 modules, 87
  ms; a fresh process is done importing after 125 ms, at 29.5 MB.
- M2 Core start (test core, scratch runtime): 1.8 ms with no data; 94.8
  ms with the cached world_areas.json (1.9 MB) and base_items.json (8.2
  MB), of which 74 ms is JSON parsing: 8 parses, 22.1 MB, for 10.1 MB on
  disk. Peak working set 56.7 MB, steady 37 to 40 MB.
- M3 Tick (same core, sessions from tools/synth_client.py): a 4-hour
  campaign session costs 186 microseconds per full tick (0.037 percent
  of a core at 2 Hz) and 17 stat calls. An endgame session of 200 maps:
  966 microseconds, 795 of them in tick_history. With 500 saved maps
  added: 13.4 ms per tick, 2.68 percent of a core.
- M4 Snapshot: 46 keys; 13.7 to 18.0 KB on busy sessions; 107 to 267
  microseconds to build, 72 to 92 to serialise; one push to two streams
  0.50 ms. The fields the overlay reads are 550 bytes (3 percent).
- M5 Live processes (60 s, 13 samples; game idle, overlay hidden,
  companion closed to the tray, calc off, core up 2.5 h): core 45.7 MB
  working set, 35.7 MB private, 0.104 percent CPU (0.17 over its life);
  supervisor 33.6 / 24.0 MB, 0.00 percent; Electron 2 processes, 111.4 /
  74.0 MB and 57.7 / 24.9 MB, summed 169.1 / 98.9 MB, 0.000 percent.
  All of AshLight: 248.4 MB working set, 158.6 MB private.
- M6 Live feed (read-only, 196 s, game idle): state is 6,385 bytes, the
  `diag` key 2,278 of them. After the first frame four more arrived,
  about one a minute, and in each the only changed key was `diag`.
- M7 Dashboard (headless browser over the DevTools protocol, 1440 by
  900, test core on a spare port in the block, 2-hour synthetic
  session): 942 elements, 42 listeners, JS heap 1.3 MB, load 51 ms of
  task time. Idle: 14.9 ms of task time in 10 s (0.15 percent), 11
  layouts. Burst: 60 pushes in 21.6 s at 17.9 KB each cost 2.03 ms of
  task time per push (script 0.62, layout 0.45, style 0.25).
- M8 Budget tests by file: tests/test_budgets.py 6 passed in 7.5 s (core
  idle printed 0.000); tests/test_math_perf.py 3 passed in 12.9 s (cold
  start 1.14 s, load 0.36, reload 0.29, set item 0.09, peak 490 MB).
- M9 Calc press (reference build, bridge driven directly): luajit holds
  252 MB when ready, 287 after the first load, 517 after the first
  press, 525 to 527 after three. First press 10.9 s and 24 calc calls,
  the first two (base and first swap) in 0.37 s; the same item again
  1.33 s (3 calls); an item for another slot 3.46 s (8 calls). The
  weights-only evaluation takes 0.5 ms.
- M10 Other: `python -m server.al --check` 207 ms; importing the
  supervisor adds 11.5 MB (ssl, http.client, urllib, email). AshLight's
  own logs: stop to listening 3.6 s, core launch to listening at most
  1.1 s, overlay live and dashboard shown within 1 s of the client
  start. The dev supervisor (1 s poll) used 0.9 CPU-seconds in 2.5 h.

## Findings

- F1 (high) The map ladder tick breaks the core budget. tick_history
  calls tick_ladder on every tick (server/al/core.py:390, 419-442);
  record and view each compare every session map with every saved one
  (server/al/mapladder.py:171-189, 195-206). M3: 13.4 ms per tick at 200
  and 500 maps, linear in both, also while the game is closed; a normal
  evening (40 maps, 500 saved) is about 0.5 percent of a core. It is
  the only AshLight cost that grows with play time.
- F2 (high) The item check is as slow as its slowest part. The press
  runs evaluate to the end before anything is published
  (server/al/theorycraft/live.py:123-139; evaluate.py:199-243, 335-339):
  M9 3.5 s warm, 10.9 s first; the price card of the same press waits
  too (server/al/core.py:271-272). The card expires 20 s after the press
  (server/al/state.py:35, 1842-1844), so a first-press card shows for 9
  s, and a press over 20 s, which the 30 and 60 s budgets allow, never
  shows on the overlay. The hotkey's request times out after 5 s
  (app/eval_hotkey.js:57): the log says the check was not sent although
  the core finishes it, and its one-request guard clears (line 47), so
  a second press stacks a second calc run.
- F3 (medium) The feed is not quiet when nothing happens. The Checks
  report carries a minute stamp (server/al/diag.py:282-285) and "N min
  ago" texts (49-60, 89-97), so the state version moves every minute and
  every stream gets a full snapshot (M6), which the hidden overlay
  parses. `diag` is also the largest key of a quiet snapshot (36 percent).
- F4 (medium) One snapshot for every consumer. Each stream builds and
  serialises its own copy per push (server/al/http.py:723, 758, 766,
  773); the overlay parses all of it (app/overlay/overlay.js:85-93) for
  3 percent of the bytes (M4); tick_diag builds one every 5 s to read
  a few fields (server/al/core.py:852). Cheap today, but every dashboard
  feature added grows the overlay's work.
- F5 (medium) The tests do not measure what ships (section above). Also
  the idle test's CPU clock moves in 15.6 ms steps, so a 3 s window
  resolves 0.5 percent at best, and timing budgets widen with machine
  load (fleet_test_guard.budget): soft exactly when a suite is busy.
- F6 (medium) RAM in play with the calc on. luajit starts at core start
  when a build is loaded (server/al/theorycraft/pobout.py:92;
  core.py:172-179), never stops while the opt-in is on, and keeps its
  high-water mark (M9; decision 0028). It runs at normal priority
  (bridge.py:171-175): a first press is up to 11 s of one full core
  beside the game.
- F7 (low to medium) Start-up parses its data two to four times.
  Watched.get runs a full-parse check, then the loader's own parse
  (server/al/hotreload.py:147-150); FlaskCache and NamesCache both read
  base_items.json (campaign.py:81-87; theorycraft/basetypes.py:69-75);
  TableCache and the area graph both read world_areas.json
  (acts.py:213-219; zoneguide.py:160-161). M2: 22.1 MB parsed at start
  and 16.5 MB more on the first tick, for 10.1 MB of files; the RSS
  budget's headroom (peak 56.7 of 60 MB) goes to these copies.
- F8 (low) With the calc on, the 5 s Checks tick re-hashes luajit.exe
  every time (server/al/exepin.py:91-97 through bridge.py:83-97,
  theorycraft/calcwire.py:109-114 and core.py:889).
- F9 (low) Idle is not idle, but it is cheap. While the game may be
  closed the tailer still stats 4 times a second, the loop ticks twice a
  second with 17 stats (local.json 6 times), Checks reads the process
  list and 64 KB of log every 5 s, and a source checkout polls files
  every second in three processes. All of it is the 0.10 percent of M5.
- F10 (low) Dashboard cost is fine (M7). Small wastes: the 1 Hz ticker
  writes text without comparing (web/app.js:97-102), a layout a second
  even with frozen clocks; render runs every painter while minimised
  (web/app.js:987-1062; only tick checks, line 92); and on Windows a
  window covered by the game still counts as visible (S5), so a
  companion behind the game keeps painting, in software, as
  acceleration is off for the whole app (app/main.js:113).
- F11 (low) The supervisor holds 33.6 MB for a poll loop; a third of it
  is the import of urllib.request (server/al/keepalive.py:32).
- F12 (medium) FPS, in principle. The overlay is a separate topmost
  layered window. Over a borderless flip-model game, content on top
  makes the compositor compose every frame again, compose in reverse, or
  keep the direct path on a hardware plane (S1); Microsoft calls the
  cost slight and gives no number (S2); reports of added latency are
  forum evidence (S10). The effect exists only while the plate is
  visible and does not shrink with its size (280 by 176 pixels here).
  The overlay's own work is tiny: acceleration off (app/main.js:113), at
  most 4 pushes a second (server/al/http.py:43), a paint only when a HUD
  string changes (app/shared/render_gate.js:189-195), one timer to the
  next minute (app/overlay/overlay.js:48-57). So the in-map check asks
  one thing: does the visible plate change the game's present path
  enough to see. Only the game's own FPS display shows that (decision
  0006 method 1): utilisation proxies cannot at a saturated GPU
  (decision 0002's own limit), 1 percent is 1.2 frames at 120 and cannot
  be read off a moving counter, and the game's Foreground FPS Cap
  (research 0012) hides any loss at the cap. The written acceptance is
  not provable with the cleared methods.
- F13 (low) Hot reload treats any checkout with a `.git` entry as a
  developer's (server/al/hotreload.py:64-76); a clone is today's only
  install path (decision 0041 point 9), so every user gets the 1 s
  polls. Negligible cost (M10); one for the deployment notes. Start-up
  itself is good: about 1.1 s to a listening core.
- F14 (low; added by the verifier) Throttling and frame caps. Neither
  window sets backgroundThrottling (app/main.js:233,
  app/client/window.js:161), so the default applies: timers and
  animations throttle while a page is hidden (S5, S6). The overlay is
  hidden by the idle gate with a window hide, so while the game may be
  closed its one timer is throttled, but it still parses every feed
  frame (F3; R7 and R8 fix that). While shown, the render gate already
  caps paints at the feed's 4 a second (B13), so no separate frame-rate
  cap is needed. The companion stays "visible" behind the game (F10).

## Recommendations

### Budgets to adopt

Measured value in brackets. "Det." is a deterministic check (counts or
bytes), hard also on a loaded machine; the rest are timings.

- B1 Core loop, idle, worst-case fixture (200 session maps, 500 saved):
  under 0.5 percent of one core over 10 s [2.7; 0.10 live].
- B2 One full tick: under 2 ms on that fixture [13.4], under 0.3 ms on
  the campaign fixture [0.19].
- B3 Det. Idle tick: at most 20 stat calls, no file read [17, 0].
- B4 Det. Five idle minutes on a fake clock: no state version change
  [one a minute].
- B5 Core working set: steady under 60 MB, peak under 80 MB, with 10 MB
  of data files [46 live; 40 / 57 on the test core].
- B6 Det. Bytes parsed at start: at most 1.2 times the bytes on disk
  [3.8]. Core start under 300 ms [95]; imports under 250 ms [125].
- B7 Det. Snapshot under 32 KB on the busy fixture [18.0], no key over
  8 KB [3.7], overlay view under 2 KB [550 bytes possible].
- B8 Feed: at most 4 state frames a second per stream (kept); snapshot
  plus serialise under 1 ms [0.2 to 0.34].
- B9 Supervisor working set under 35 MB [33.6], under 25 after R12.
- B10 Client, companion closed: at most 2 processes, summed working
  set under 200 MB [169.1], private under 120 MB [98.9].
- B11 Client, companion open: at most 3 processes; provisional ceiling
  300 MB until R4's first log [unmeasured].
- B12 Overlay CPU under 0.2 percent of a core idle [0.000], under 1
  percent while the HUD updates in a map [unmeasured].
- B13 Det. Overlay paints: none for a snapshot that changes no HUD
  string; at most 4 a second.
- B14 Dashboard: at most 1,500 elements [942], 5 ms of task time per
  push [2.0], 3 ms per idle second [1.5], JS heap under 8 MB [1.3].
- B15 Press to first card on the feed under 0.5 s, calc on or off [3.5
  to 10.9 s with the calc on]; to PoB numbers under 2 s warm.
- B16 Calc ceilings at about 2.5 times today's values: cold start 5 s,
  load 1.5 s, reload 1 s, set item 0.5 s, all probes 30 s first and 12 s
  warm, repeat 4 s.
  Settled-decision check: this tightens decision 0024 R7 and the 0028
  budgets; it does not reverse them. R7's own clause ("a re-measure
  after a pin move or on the target machine says otherwise") is met by
  M8 and M9, so it lands as an R7 amendment with those numbers.
- B17 luajit peak 768 MB until R9 lands, then 400 MB; gone within a
  minute of R9's idle rule.
- B18 All of AshLight beside the game, calc off: under 350 MB [248].
- B19 Game FPS: no change visible on the game's own display with the
  HUD on; system-wide proxies inside their own noise (R5, questions).

Ranking: R1 to R12 are ordered by impact over effort, with R4 and R5
ahead of R6 because they close the two operator-blocked ROADMAP rows.

### R1 LADDER-TICK - make the map ladder tick free when nothing changed

- Action: save finished maps when a map closes; key saved maps by (area
  id, seed); rebuild the all-sessions view only when the session rows
  or the saved list changed.
- Impact: H. Removes up to 2.7 percent of a core for endgame players
  and the only cost that grows with play time.
- Effort: S. Risk: a map rebuilt after a restart must still match its
  saved record within 120 s (mapladder.MATCH_S); tests exist.
- ToS check: no floor rule is touched; it reorders work on data already
  derived from the opted-in Client.txt.
- Depends on: none. Closes audit P8-5. Files: server/al/mapladder.py,
  core.py, tests/test_util_map_ladder.py, tests/test_budgets.py.
- Acceptance: B1 and B2 on the 200 plus 500 fixture; ladder tests green.
- ZERO-CLICK: nothing to do; the ladder still fills by itself.

### R2 CALC-PRIORITY - heavy child processes below normal priority

- Action: start luajit, and every batch child AshLight runs (the code
  preflight, the drift trial, the snapshot build), with the
  below-normal priority class (S8, S9). The core and the client stay at
  normal: they cost nothing (M5).
- Impact: M to H. A probe burst stops competing with the game's
  threads: a below-normal process's normal thread has base priority 6
  against 8 for a normal one, and the scheduler preempts the lower one
  whenever a higher one is ready (S8; dynamic priority boosts aside).
- Effort: S. Risk: a press takes longer on a saturated CPU; with R3
  the first card does not depend on it.
- ToS check: "never touches the game process": only AshLight's own
  child processes get a creation flag.
- Depends on: none. Files: server/al/theorycraft/bridge.py,
  keepalive.py, tools/tc_drift.py, scripts/build.ps1,
  tests/test_tc_bridge.py.
- Acceptance: a test reads the priority class of the started luajit
  and of the preflight child and expects below normal.
- ZERO-CLICK: automatic.

### R3 PRESS-STAGED - publish the item check in stages

- Action: answer the hotkey's request at once; publish the weights
  card first, then PoB's DPS and EHP change when the base and swap
  calls return, then the per-mod rows when the probes finish, each as
  an update that keeps the card's time. One press in flight per core:
  a second press replaces the pending probes.
- Impact: H with the calc on: first card in under 0.5 s where it took
  3.5 to 10.9 s; the full 20 s on screen; no false "not sent" line; no
  stacked calc runs. None with the calc off.
- Effort: M. Risk: a card that changes while read (the design notes
  decide the words); each stage must stay all or nothing, as today.
- ToS check: "clipboard ... ONLY once per manual press": unchanged, the
  same single read feeds every stage; nothing is sent to the game.
- Depends on: the usability and glance notes for the staged wording.
  Decisions 0014 (one card slot, 20 s), 0016 (one press time for the
  item and price cards, core.py:260-274) and 0024 stand.
- Files: server/al/theorycraft/live.py, evaluate.py, server/al/core.py,
  http.py, app/eval_hotkey.js, web/tc.js, tests/test_tc_delta.py,
  tests/test_math_e2e_live.py.
- Acceptance: B15; with a fake calc that sleeps, the first state frame
  carrying the card arrives in under 0.5 s and the request returns in
  under 1 s; a killed calc still leaves the weights card.
- ZERO-CLICK: the same one press; the card fills in by itself.

### R4 BUDGET-LOG - AshLight records its own footprint

- Action: on top of the counters in research 0051 (R4): once a minute
  the client's main process logs `app.getAppMetrics()` per process
  (working set, private bytes, CPU percent; S3, S4; not idle wake-ups,
  which Electron always reports as 0 on Windows), the
  core logs its own working set and CPU seconds and luajit's when up,
  each row tagged with its state (game idle or active, in a map, overlay
  shown, companion open, calc on). A bounded file in `<sidecar>\Logs`
  and one Checks row ("AshLight uses N MB").
- Impact: H. OVL-BUDGET's missing figures (active overlay, client with
  the companion) collect themselves in normal play; every later budget
  breach is seen without a measurement session.
- Effort: M. Risk: log growth (cap it at 1 MB, oldest dropped).
- ToS check: "NEVER read or write game process memory" and decision
  0029 (no process-list check for the game): only AshLight's own
  process handle and Electron's own process tree are read; decision
  0006 method 3 names these counters.
- Depends on: research 0051 R4 (same work package); open question 3.
- Files: app/main.js (or a new app/metrics.js), server/al/core.py,
  diag.py, tests/test_budget_log.py (new), app/test/metrics.test.js.
- Acceptance: a replayed log with a breach fails
  tests/test_budget_log.py and a clean one passes; the sampler adds
  under 0.01 percent CPU; no row holds a path, a name or a pid.
- ZERO-CLICK: automatic; the operator only plays.

### R5 OVL-CHECK - the in-map check as one normally played map

- Action: a developer-only tool, `tools/ovl_check.py`, armed by a
  session, not by the operator. Protocol:
  1. Arm: `python tools/ovl_check.py arm` writes a flag in ops/runtime
     and starts a detached watcher at below-normal priority; the
     hand-off re-arms it after a reboot.
  2. Trigger: the watcher reads AshLight's own state every 5 s and
     starts once the player has been inside an open map for 20 s. It
     never looks at the game's process or window.
  3. Run, 4.5 minutes: nine 30 s blocks in the order hidden, shown,
     updating, updating, shown, hidden, hidden, shown, updating. Hidden
     hides the overlay window as the idle gate does; it returns with
     showInactive, so focus never moves (S5). Updating changes a word
     in the status slot 4 times a second, the feed's own cap. The first
     5 s of each block are dropped.
  4. Recorded every second: AshLight's own processes (decision 0006
     method 3, from R4); system-wide totals only (method 2): 3D engine
     utilisation, processor time, nvidia-smi utilisation when present;
     and from AshLight's own state the area id and level, so a block
     with a zone change, a death or a card is left out.
  5. The operator keeps the game's FPS display on and plays. At the end
     the dashboard asks once: FPS looked the same, or FPS dropped while
     the HUD was on. No answer is recorded as none.
  6. Output: a JSON file and a 15-line summary in `<sidecar>\Logs`; the
     next session copies the numbers into decision 0002 and flips
     OVL-FPS and OVL-BUDGET.
  Verdict: pass when overlay CPU is under 1 percent in shown and
  updating blocks, Electron is inside B10 / B11, both system-wide
  counters differ between hidden and the other blocks by less than the
  hidden blocks differ among themselves, and the answer is not
  "dropped". The report says what it is: a proxy, blind at a saturated
  GPU or at the FPS cap, display mode not detected.
- Impact: H. Closes both operator-blocked rows with nothing but play.
- Effort: M. Risk: the HUD blinks for 4.5 minutes of one map; a
  developer control in product code. Gate (verifier correction): NOT
  hotreload.dev_enabled, because that is true in every clone
  (hotreload.py:64-76) and a clone is today's only install (F13); the
  mode answers only while the arm flag that tools/ovl_check.py writes
  exists, with the per-start token, and clears the flag when done; a
  static test proves no other path reaches it.
- ToS check: "NEVER send input to the game": the phases switch through
  AshLight's own window calls, no key is synthesised. "the screen ONLY
  once per manual press ... no timer": nothing reads the screen.
  Decision 0006: methods 1 to 3 only, no counter keyed to a game pid,
  and the system-wide sampler is a tool the shipped app never starts.
- Depends on: R4; the Electron hardening note for the control channel.
- Files: tools/ovl_check.py (new), server/al/http.py and core.py (the
  developer-only mode), app/shared/render_gate.js, app/overlay_gate.js,
  web/checks.js, tests/test_ovl_check.py (new), docs/decisions/0002.
- Acceptance: on a test core with a synthetic map session the tool
  runs its nine blocks against a fake clock, writes the report and
  clears its flag; the mode is refused while the arm flag is absent,
  also in a source checkout.
- ZERO-CLICK: play one map. One optional click at the end; no floor
  rule asks for a press.

### R6 BUDGET-TESTS - enforce the numbers above

- Action: add or change these tests.
  - tests/test_budgets.py: the real loop body for 10 s on the
    worst-case fixture (B1, slow-marked); absolute working set in a
    child process (B5).
  - tests/test_budget_tick.py (new, deterministic, under 100 ms): B2,
    B3, B4. tests/test_budget_start.py (new): B6 with a counting JSON
    parser. tests/test_budget_snapshot.py (new): B7.
  - tests/test_dash_perf.py with app/test/cdp/dash_perf.mjs (new): B14
    from Performance.getMetrics, on the headless harness that
    tests/test_dash_console.py already uses.
  - app/test: 1,000 snapshots that differ only outside the HUD fields
    give 0 paints (B13).
  - tests/test_overlay_smoke.py: one opt-in live smoke in two shapes,
    overlay alone and client with the companion (B10, B11).
  - tests/tc_live_util.py: B16, plus first-card and PoB-number keys.
  - tests/test_budget_log.py: R4's log, when present, inside B9 to B12,
    B17 and B18.
- Impact: H as a guard: today a tenfold regression in any tick passes.
- Effort: M. Risk: timing flakes; prefer the deterministic checks and
  keep fleet_test_guard.budget on the timed ones.
- ToS check: tests only; the live smoke shows AshLight's own window
  and stays opt-in.
- Depends on: R1 for B1 / B2; the file-structure note (0047 R7, a tick
  list) or a small `Core.tick_all()`; the test-speed note (0049) for
  the slow-marked test. Files: as listed, and server/al/core.py.
- Acceptance: each new test fails with its defect put back once and
  passes without it. ZERO-CLICK: the suite runs them.

### R7 QUIET-FEED - no push when nothing changed

- Action: take the minute stamp out of the snapshot (stamp the report
  when it is copied); step the "N min ago" texts at 5 minutes; read the
  Checks facts without building a snapshot.
- Impact: M to L. The feed is silent while nothing happens: no minute
  wake-up for the hidden overlay or the dashboard.
- Effort: S. Risk: a Checks row a few minutes stale; fine for "ago".
- ToS check: no floor rule touched; text of AshLight's own checks.
- Depends on: none. Files: server/al/diag.py, core.py, web/checks.js,
  tests/test_diag_self.py. Acceptance: B4. ZERO-CLICK: automatic.

### R8 OVERLAY-FEED - a small feed for the overlay

- Action: `/events?view=overlay` sends only the fields the HUD reads
  and only when one of them changes; the dashboard keeps the full feed;
  the server shares one serialised frame per view among its streams.
- Impact: M. The overlay renderer wakes for HUD changes only and stops
  depending on the dashboard's growth; 550 bytes in place of 18 KB.
- Effort: M. Risk: a field the HUD needs is left out; one list in one
  place, with a test that walks render_gate.js.
- ToS check: no floor rule touched; same token, same loopback feed.
- Depends on: R7. Files: server/al/http.py, state.py,
  app/overlay/overlay.js, app/shared/render_gate.js,
  tests/test_budget_snapshot.py, app/test/shared.test.js.
- Acceptance: B7, B13; the overlay tests pass on the small view.
  ZERO-CLICK: automatic.

### R9 CALC-IDLE - luajit leaves when it is not needed

- Action: stop the calc process after 20 minutes without a press and
  when the game goes idle; start it again on the next press or build
  load (1.2 s plus 0.4 s, hidden behind R3's first card). After R3,
  measure a full collect after every probe load: decision 0028 put that
  at about 300 MB and rejected it only for the 0.2 s per load in front
  of the card. Cache the luajit hash check by file time and size (F8).
- Impact: M. 290 to 525 MB returned while the player is not checking
  items; peak budget from 768 towards 400 MB.
- Effort: S for the stop, S to M for the collect. Risk: a slower first
  probe set after a stop; the stop rule must not fire mid-press.
- ToS check: no floor rule touched; AshLight's own optional child
  process, which gets only pasted build text and hotkey-read item text.
- Depends on: R3 for the collect. Decision 0028's own reverse clause
  (the ceiling costs more than it saves) applies only if the measured
  first card is unchanged; record the numbers as an amendment.
- Files: server/al/theorycraft/calcwire.py, bridge.py, bridge.lua,
  server/al/exepin.py, tests/test_tc_wire.py, tests/test_math_perf.py.
- Acceptance: B17; with a fake clock the provider stops the process
  after the idle time and a later press answers. ZERO-CLICK: automatic.

### R10 PARSE-ONCE - read each data file once

- Action: let the watched-file check hand its parsed document to the
  loader; share one parse of base_items.json between the flask and
  base-name tables and one of world_areas.json between the level table
  and the area graph.
- Impact: L to M. 38.7 MB parsed becomes 10.1; about 45 ms off the
  start and 15 MB off the peak, which is the RSS budget's headroom.
- Effort: S. Risk: the last-good-copy rule of decision 0042 must hold
  per table.
- ToS check: no floor rule touched; cached snapshot files, read only.
- Depends on: none. Files: server/al/hotreload.py, acts.py,
  campaign.py, zoneguide.py, theorycraft/basetypes.py,
  tests/test_hot_reload.py. Acceptance: B6. ZERO-CLICK: automatic.

### R11 DASH-IDLE - the dashboard rests when unseen or frozen

- Action: write a clock only when its text changed; skip the painters
  while the page is hidden and paint once on return; stop the 1 Hz
  ticker while the game is idle.
- Impact: L. Removes the per-second layout and all work in a minimised
  companion. A companion covered by the game still paints (S5).
- Effort: S. Risk: a stale panel after a restore; paint on
  visibilitychange.
- ToS check: no floor rule touched; AshLight's own page.
- Depends on: none. Files: web/app.js, app/test/dashboard.test.js,
  tests/test_dash_perf.py.
- Acceptance: B14's idle line; a hidden-page run shows 0 layouts.
  ZERO-CLICK: automatic.

### R12 SMALL-TRIMS - supervisor diet and idle backoff

- Action: import the HTTP client only inside the health probe; stat
  local.json once per tick; tick once a second and poll the log once a
  second while the game is idle.
- Impact: L. About 10 MB and half of an already small idle CPU.
- Effort: S. Risk: the first log line after idle is seen up to 0.75 s
  later.
- ToS check: no floor rule touched; fewer reads of the same opted-in
  file.
- Depends on: none. Files: server/al/keepalive.py, core.py,
  __main__.py, logfile.py, tests/test_keepalive.py.
- Acceptance: B3 and B9. ZERO-CLICK: automatic.

## Cut or merge

- R4 and research 0051 R4 are one work package: the counters come from
  there, the states, the file and the budget check from here.
- OVL-BUDGET merges into R4 (it closes from the log) and OVL-FPS into
  R5; drop the hand measurement from the operator's list.
- Audit P8-5 merges into R1; F8 into R9; F13 into the deployment notes.
  test_tailer_idle_cpu_under_2_percent is superseded by R6's loop test.
- Cut: destroying the overlay window while the game is closed (58 MB
  freed when RAM does not matter, for a new rebuild path).
- Cut: a Tauri or native overlay now. Decision 0002 reverses only on a
  missed budget; the measured 169 MB is inside it.

## Rejected

- PresentMon, CapFrameX, RTSS or any ETW present trace of the game,
  also for development: decision 0006 and the floor's "READ ONLY what
  GGG permits". GPU or CPU counters keyed to the game's pid: the same.
- Finding the game's window, display mode, focus or process to pause
  work or to time the check: the floor's "never touches the game
  process" and decision 0029 (log staleness only).
- A timed or repeated screen capture of the FPS readout, or an OCR
  loop: the floor allows the screen once per manual press, never a timer.
- Synthesising the overlay toggle key to switch phases: any
  synthesised input is outside the floor.
- Drawing inside the game to keep its direct present path: injection
  and graphics hooks are outside the floor.
- Turning hardware acceleration back on for the overlay: decision 0002
  keeps it off so the overlay never queues GPU work beside the game;
  its reverse condition is not met.
- Raising any AshLight process above normal priority (opposite of R2).

## Open questions

1. Adjudicator: restate the OVL-FPS acceptance as B19? The 1 percent
   figure and the 1 percent lows cannot be resolved by the methods
   decision 0006 clears (F12).
2. Adjudicator: may the developer-only check save one screen capture
   per manual AshLight hotkey press, cropped to the game's FPS readout,
   for a session to read later? The floor allows a per-press screen
   read; decision 0006's cleared list does not name it. Not part of R5
   until ruled.
3. Adjudicator: decision 0006 item 4 says nothing from the measurement
   ships. This note reads that as the on / off FPS measurement and
   treats own-process counters (R4) as decision 0040's Checks class.
   The same question covers R5's armed phase-switch mode, which is code
   in the product even though only a session-run tool can arm it.
4. After R4's first log: is the client with the companion open inside
   250 MB? If not, raise the client budget to B11 or close the
   companion to the tray by default (decision 0041's reverse clause).
5. Which key or option shows the game's FPS display in PoE2 and where
   it draws (S11): UNVERIFIED; one glance by the operator. The overlay's
   default corner is top-right, where the guide puts the graph.
6. Whether a hardware plane keeps the game on its direct path under
   the plate on this GPU and driver: not knowable inside the floor;
   R5's hidden and shown blocks answer the practical question.

## Verification

Independent verifier, 2026-11-18.

Checked:
- Code (A): cited locations in 30 files opened; all hold after the fixes
  below (decision 0002 lines 52-63; test_budgets.py 27-185;
  __main__.py 215-265, ten calls per tick; test_overlay_smoke.py 34-36,
  47-54, 125-130, 175-214; tc_live_util.py 91-101; core.py 172-179,
  260-274, 390, 419-442, 852, 889; mapladder.py 27, 31, 171-206;
  live.py 123-139; state.py 35, 1843; eval_hotkey.js 47, 57; diag.py
  49-60, 89-97, 282-285, 302-310; http.py 43, 723-773; overlay.js
  48-57, 85-93; render_gate.js 189-195; hotreload.py 64-76, 147-150;
  campaign.py 81; basetypes.py 69-75; acts.py 213; zoneguide.py
  160-161; exepin.py 91-97; bridge.py 171-175; keepalive.py 32, 48;
  logfile.py 20; web/app.js 92-102, 987-1062; app/main.js 113, 233;
  layout.js 35 (280 by 176); decision 0028 lines 42-43, 62; decision
  0006; ROADMAP 56-70; audit P8-5 947-950).
- Web (B): 7 sources re-fetched (S1, S2, S3, S4 with MemoryInfo and
  CPUUsage, S5, S8); all support the claims as now worded.
- Measurements: 2 of 10 re-run. M8: tests/test_budgets.py 6 passed in
  7.6 s. M3 / F1: an own micro-benchmark of MapLadder.record plus view
  with 200 session maps took 11.8 ms per tick with 500 saved maps in
  all and 14.1 ms with 700 (2.4 to 2.8 percent of a core at 2 Hz),
  matching M3 and the audit's independent 10 ms. M1, M2, M4 to M7, M9
  and M10 are the author's own measurements, not repeated (M9 would
  start a 500 MB luajit beside a possibly running game); M9 agrees with
  decisions 0024 R7 and 0028 (511 MB peak, 12.4 s first press).
- ToS floor (C): all 12 recommendations and the 7 rejected ideas tested
  against each floor rule; none needs the floor bent. Settled decisions
  (D): no silent contradiction; B16 recorded as an amendment under
  0024 R7's own clause.
- Completeness (E): every brief point covered; background throttling
  and frame-rate caps were missing and are now F14.
- Format (F): all 12 recommendations carry the nine fields; a ranking
  line was added.

Corrected (8):
1. R4 listed idle wake-ups; Electron reports them as 0 on Windows.
2. R5's gate relied on "outside a source checkout", which is every
   install today (F13); now an arm-flag gate, and open question 3
   extended to it.
3. R5's unverifiable "the operator has said restarts mid-game are fine"
   removed.
4. R3 cited decision 0016 for the one card slot; that is decision 0014.
5. R2 overstated the scheduler ("run only when nothing normal wants
   it"); reworded to base priority 6 against 8 with preemption (S8).
6. Summary's "half of the written budgets" replaced by the exact split.
7. F8's call chain lacked calcwire.py:109-114.
8. The calc ceilings omitted fallback_press_s; S7 marked not relied on.

UNVERIFIED (unchanged): S10 and S11 (search summaries only); the PoE2
FPS display key (open question 5); the author-only measurements listed
above. Note for the plan: ROADMAP OVL-BUDGET records 3 Electron
processes and about 204 MB at character select, while M5 saw 2
processes and 169 MB with the companion closed; R4's log should settle
which shape is normal.
