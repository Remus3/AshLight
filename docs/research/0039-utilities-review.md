# 0039 - Utilities review: what earns its place, what to cut, merge, hide or automate

Date: 2026-11-17. For the ultraplan (docs/plan/README.md), dimension B3
utilities. Scope: every player-facing utility that is not a play card
(loot filter add-on and merge, `.build` download, settings transfer, run
history, price watch, character keying, Checks, language notice, graphics
advisor, hot reload, logon autostart, tray, copy helpers, the scripts) and
the whole settings surface. Play features are dimension B2 (0038);
usability and the click audit are B6 / B7 (0042, 0043).
Status: draft

## Sources (all accessed 2026-11-17)

Web:
- POB-REL: https://api.github.com/repos/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases
  (newest release v0.23.1, 2026-07-28: 88,943 installer and 41,395
  portable downloads; no `.build` export in the last 4 release notes).
- EE2-REL: https://api.github.com/repos/Kvan7/Exiled-Exchange-2/releases
  (v0.16.3, 2026-09-06: 324,913 installer downloads; its update manifest
  was fetched 1,608,214 times).
- EE2-DOC: https://kvan7.github.io/Exiled-Exchange-2/download and its
  quick-start and faq pages (the installer build updates itself; one
  settings file under %APPDATA%, copied by hand on migration; hotkeys
  changed in a settings screen opened from the overlay; nine game
  languages; Windowed or Windowed Fullscreen only).
- NS-README: https://github.com/NeverSinkDev/NeverSink-Filter-for-PoE2
  (manual install folder; a subscription on the official filter ladder
  updates by itself; otherwise a manual re-download about monthly;
  FilterBlade for styling; a paid auto-updater). NS-API:
  https://api.github.com/repos/NeverSinkDev/NeverSink-Filter-for-PoE2
  (2,852 stars, MIT, release 0.10.4a on 2026-10-15).
- GGG-FILTER: https://www.pathofexile.com/item-filter/about (Import with
  Optional, PoE2-only conditions; silent on account-hosted filters).
- GGG-GAME: https://www.pathofexile.com/developer/docs/game (item filters
  and the Build Planner `*.build`, version 1, experimental; a build
  reaches the game by a website subscription, by the player's own upload
  there, or from the local planner folder, which the game watches).
- NINJA-BP: https://poe.ninja/posts/poe2-build-planner-prototype (dated
  Friday May 29, year not shown; 2026 fits the weekday: a `.build`
  export for any listed character; passives and skills, no items yet).
- MAXROLL: https://maxroll.gg/poe2/news/poe2planner-character-import-feature
  (updated 2025-03-30: imports the player's own characters by login).
- SNIP-FILTER, search snippets only (the pages answered HTTP 403):
  https://www.exitlag.com/blog/path-of-exile-2-loot-filter/ and
  https://esports.gg/guides/path-of-exile-2/how-to-install-and-use-an-item-filter-in-path-of-exile-2
  (FilterBlade's sync to the account as the simple path; consoles can
  use account filters only).
- SNIP-BUILD, search snippet only (HTTP 403):
  https://mobalytics.gg/poe-2/guides/build-files (guide pages offer one
  planner file per build variant; the planner arrived with patch 0.5.0).
- EXUI-REL: https://api.github.com/repos/Lailloken/Exile-UI/releases
  (v1.65.4, 2026-11-13, switched off three continuous screen-read
  features after GGG's reworded tool policy).
- SK: https://github.com/Sidekick-Poe/Sidekick (closing the window hides
  it in the tray).
- SNIP-GFX, search snippet: https://www.pcgamesn.com/path-of-exile-2/best-settings-pc
  and other guides in the same results (they disagree on Dynamic Resolution).

Repo (read 2026-11-17): the files, decisions and research notes cited
inline. Local observation, one live install, 2026-11-17: the runtime
folder holds no run history, price watch, hints or autostart file; the
snapshot cache holds five repoe-fork files (48.2 MB) and no tree export.

## Summary

- Verdicts on 15 utilities: keep 5 as is, keep and fix 4, merge 3, hide
  and retire on a trigger 2, rebuild 1 (logon autostart saves no click).
- The clicks are in the settings, not the utilities: of 14 player
  settings 3 have a control and 11 need a JSON file the app never
  locates; 5 of 9 Checks fix lines point at PowerShell or that file,
  and ticking "Use web data" alone yields two failing checks.
- Infer or automate instead of asking: the game-data snapshot, hotkey
  conflicts, the league, the calc flag, the logon start, non-Steam logs.
- Market (F15): filters and `.build` files mostly arrive without a
  local file or from other tools; do not grow AshLight's two file tools.
- With R1-R6: one setup command, a few one-time clicks and one paste per
  character, then no click per session and no PowerShell.

## Current state

### Utility scorecard

Use counts marked "est." are this note's estimate; AshLight has no usage
telemetry (and wants none). Clicks are counted from the Play tab.

- U1 Loot filter add-on download (decision 0031;
  server/al/theorycraft/lootfilter.py:151-192, server/al/http.py:251-263,
  web/index.html:409-421). Who: PC players with a local filter file and
  a loaded build; est. once per build change, while the price tiers age
  from the minute of download. Clicks: 3 (Build tab, fold, Download),
  then a file move and, once, an Import line typed into the player's
  filter. Upkeep: filter grammar per patch; never loaded in game
  (ROADMAP LIVE-FILTER open). Overlap: U2 writes the same blocks; the
  common filters tier by economy (research 0022). Verdict: merge (R8).
- U2 Loot filter merge (decision 0033; lootfilter.py:262-277,
  http.py:498-534, web/index.html:422-429). Who: the same group; est.
  after each update of their main filter (about monthly, NS-README) and
  each build change. Clicks: 4-5 (tab, fold, file pick), then a file move
  and a pick in the game options. Upkeep: byte-identity rules, 2 MB cap
  (lootfilter.py:196); LIVE-FILTER-MERGE open. Verdict: keep as the one
  filter control (R8).
- U3 `.build` download (decision 0034;
  server/al/theorycraft/buildfile.py:251-275, http.py:264-273,
  web/index.html:354-365). Who: players who want their own PoB build in
  the in-game planner; est. once per build version. Clicks: 3, then a
  move into the planner folder. Upkeep: the format is version 1,
  experimental (GGG-GAME); needs the tree export; 9 gear slots only
  (buildfile.py:49-51); TC-BUILDFILE-LIVE open. Overlap: four other
  producers (F9). Verdict: keep folded, fix two texts, retire when the
  pinned PoB release exports it (R9).
- U4 Settings transfer (decision 0036; server/al/settingsio.py:84-161,
  web/index.html:567-577). Who: a player moving PCs; est. once per PC.
  Clicks: 3 out, 4-5 in. Upkeep: each new setting touches ALLOWED, LABELS
  and two test files. Verdict: keep hidden, add the weights (R11).
- U5 Run history, map ladder, zone visits (decisions 0036, 0043;
  server/al/runhistory.py:31-53, server/al/core.py:200-213, 346-390,
  web/index.html:250-268). Who: re-rollers and league starters; fills on
  every finished act. Clicks: 0 to record, 1 to look; the switch and
  Clear are 1 each. Upkeep: schema migrations, new act ids at 1.0.
  Verdict: keep; one switch (ruling C, research 0028) covers all three.
- U6 Price watch (decision 0036; server/al/pricewatch.py:23-31,
  core.py:474-507, web/index.html:467-475). Who: traders who priced a
  unique or stackable; needs web data, a contact and a priced press.
  Clicks: 0 to fill, 1 to look - and nothing tells the player a price
  moved (F10). Overlap: "Price movers this week", same tab, same cache.
  Verdict: merge into the movers block (R10).
- U7 Character keying (decision 0038; server/al/state.py:63, 877,
  1344-1353, web/index.html:114-117). Who: anyone with 2+ characters,
  every session, invisibly. Clicks: 0; the picker is 2. Upkeep: three
  known mis-file cases (ROADMAP UTIL-MULTICHAR); per-character builds
  (decision 0045) depend on it. Verdict: keep; give the pin a control
  instead of a JSON key (R7).
- U8 Checks and Copy report (decision 0040; server/al/diag.py:226-234,
  282-292, web/index.html:528-541). Who: every player at first run and
  whenever something is off. Clicks: 0 (opens itself and marks the
  Settings tab, web/checks.js:86-94); Copy report is 2-3. Upkeep: one
  row and one fix sentence per subsystem (14 rows + 2 conditional).
  Verdict: keep; its fix lines are the problem (F2).
- U9 Language notice (decision 0040; server/al/langguard.py,
  web/index.html:86-90). Who: players on a non-English client (a
  competitor supports nine game languages, EE2-DOC). Clicks: 0; Hide is
  1. Upkeep: low. Overlap: the same verdict is a Checks row. Verdict:
  keep; the honest stop-gap until locale packs are possible.
- U10 Graphics advisor (decision 0014; server/al/gfx.py:187-252,
  web/index.html:579-596). Who: a new player on a new PC; est. once.
  Clicks: 3 (Settings tab and two folds), then up to 25 s for the
  hardware read (gfx.py:28). Upkeep: option labels and advice per patch
  (research 0012). Overlap: every settings guide on the web, and they
  disagree (SNIP-GFX). Verdict: hide (done), lift its one line that
  matters, cut at the first label drift (R12).
- U11 Hot reload (decision 0042; server/al/hotreload.py:64-76,
  core.py:823-839). Who: the developer on every edit; every player for
  data files; a git-clone install counts as a source checkout, so a
  pulled update loads by itself. Clicks: 0. Upkeep: the watched-file
  list. Verdict: keep as is; its `hot_reload` key stays undocumented.
- U12 Logon autostart (decision 0011; scripts/autostart.ps1,
  scripts/autostart_launch.vbs:11-13, scripts/run.ps1:82-96). Who: nobody
  yet (no opt-in file on the live install). Clicks: a typed PowerShell
  line of about 70 characters. Upkeep: low. Overlap: the client starts
  the core itself (app/client/window.js:127-145). Verdict: does not earn
  its place as built (F5); new payload and a checkbox (R4).
- U13 Tray (decision 0041; app/client/tray_menu.js:10-21,
  app/client/window.js:205-240). Who: every client user; Quit once per
  session, the rest rarely. Clicks: 2 per action. Upkeep: low. Overlap:
  toggle = hotkey, Restart overlay = Settings button, Minimize = the
  window's own. Verdict: keep the four operator-ordered actions (hiding
  to the tray is the norm, SK); add "Start with Windows" (R4).
- U14 Copy helpers: search strings, look-for-next, PoB code (decisions
  0030, 0014; server/al/theorycraft/searchstr.py:26, 96-132,
  web/index.html:391-397, 403-407, 349-352). Who: levelling players at
  vendors and anyone sorting waystones; the most used click-utility in
  play (est. several times per session). Clicks: 2 on the dashboard,
  then the player's own paste; on one screen add a window switch each
  way. Overlap: poe2.re and other tools' stash-search widgets (research
  0023); AshLight's edge is that the strings come from the loaded build.
  Verdict: keep; a hotkey path for one-screen players is R13.
- U15 Scripts (scripts/setup.ps1, build.ps1, run.ps1, stop.ps1). Who:
  setup - every install, once; build - developers (whole test suite),
  yet also the only snapshot fetcher; run - replaced by the shortcut,
  used inside the client (app/client/launcher.js:44-57); stop - behind
  tray Quit (launcher.js:60-71). Clicks: one typed command each.
  Upkeep: PowerShell 5.1 and idempotence tests. Verdict: keep as
  mechanisms; a player should type only setup (F3, R1, R4, R5).

### Settings surface

config/local.json has 18 top-level keys: 14 for players, 4 for
developers. Format: key - default - set where - read when - could it be
inferred - verdict.

- client_log - blank = Steam libraries are searched - JSON or `--log` -
  once at start (core.py:91) - yes for Steam, not for other launchers -
  R6.
- character - blank = follows the log - JSON - once (core.py:80) -
  already inferred - a pin control replaces the key (R7).
- poll_ms - 250 - JSON - once (core.py:76) - nobody needs it - off the
  documented surface (R7).
- overlay_toggle - Alt+Shift+A; eval_hotkey - Alt+Shift+E - JSON or
  environment - once at client start (app/main.js:81-89) - not
  inferable, but a conflict can be solved without asking - R3.
- web_data - false - dashboard tick (web/index.html:440-443) - every
  call (core.py:557-559) - must be asked (decision 0013) - keep.
- contact - blank - JSON - every call (core.py:561-564) - cannot be
  inferred; a project-level value may replace it (Open question 3) - R2.
- league - blank = the first league poe.ninja lists
  (server/al/ninja.py:78-88; re-read every 6 h, decision 0026) - JSON -
  every call - inferred for the main league only - picker (R2).
- tc_calc - false - JSON and `setup.ps1 -TcCalc`, both - every call
  (core.py:553-555) - could follow the opted-in install - R5.
- overlay - primary monitor, top-right, scale 1.0, opacity 0.9, margin
  16 (server/al/layout.py:29-30) - dashboard form - watched by the
  client (main.js:369) - the game's monitor cannot be read inside the
  floor - keep.
- underlevel_gap - 3 (server/al/underlevel.py:16-18); price_watch_pct -
  25 (pricewatch.py:29-30); boots_speed_level - 16
  (server/al/campaign.py:28-30) - JSON - each tick - constants in
  practice - off the documented surface (R7).
- run_history - on (runhistory.py:51-53) - dashboard tick - each tick -
  a privacy switch - keep.
- Developer keys: port (8960), hot_reload (on in a source checkout),
  tc_drift_live_unattended (false), loop.* - keep out of player docs.

Outside that file: the Client.txt consent (Allow button; floor), the
autostart opt-in (PowerShell only), stat weights and the sidegrade band
(dashboard form), the remembered tab and the hidden language notice
(browser storage), overlay shown or hidden (memory only: back to shown
at every start, app/overlay_gate.js:22). 13 `AL_*` environment variables
(server/, app/, scripts/) and 19 script switches exist; a player should
need none of them.

### Other UTIL rows

UTIL-MAPS / -MAPS-RESUME, -DEATHS, -PACE, -SESSION-SUMMARY, -MOVERS,
-WAYSTONE / -REWARD, -UNDERLEVEL, -CAMPAIGN-CHECKS and -MAP-LADDER are
passive play features with no click (verdicts in 0038). UTIL-OVERLAY-MAP
is not done by design, UTIL-1.0-POST waits for 2026-12-11, and
UTIL-CRAFT-SLOTS and UTIL-ATLAS-PROGRESS are listed only.

## Findings

- F1 The settings surface is JSON-first. 11 of 14 player settings have
  no control. The page says "AshLight's settings file" twice
  (web/index.html:176-177, 515-516) and a Checks fix says it a third
  time (server/al/diag.py:45-46); nothing says where the file is. Why it
  matters: a player who is not a developer cannot change a hotkey, the
  league or the contact at all.
- F2 Checks finds problems but hands most fixes to a terminal. Of the 9
  fix sentences (diag.py:36-46, 193-194), 5 name a PowerShell script or
  the JSON file (run, contact, calc, snapshot, hotkey). A fresh install
  that ticks "Use web data" gets two failing rows (no contact,
  diag.py:118-125; no game data, diag.py:158-164) and a lasting "fix"
  mark on the Settings tab (web/checks.js:94).
- F3 The game-data snapshot has no automatic path. Only build.ps1
  fetches it (scripts/build.ps1:63-98); the README runs build before
  run (README.md:66-73), while the switch that allows the fetch is on
  the dashboard, reachable only after run. A first install in README
  order has no snapshot, and nothing refreshes it later: after 1.0
  (2026-12-11, research 0021) the zone table is stale until the player
  types the command in diag.py:44. Nine things read it: zone levels,
  waypoint graph, base names, flask hints, trade stat ids, tree names
  (core.py:100-142), under-level fallback, filter base check, `.build`
  passive ids. The first fetch is about 48 MB (the live cache).
- F4 The contact gates more than prices. Without it poe.ninja is off
  (server/al/ninja.py:227-229) and the tree source is skipped
  (server/al/theorycraft/snapshot.py:43), as the live install shows (no
  `skilltree.json`). The `.build` note then says web data alone fetches
  the tree (buildfile.py:153-156): wrong twice (contact, and a build
  run).
- F5 Autostart saves zero clicks. The logon task forces -NoBrowser
  (scripts/run.ps1:82-96, 148): core and supervisor start, but no client,
  no tray, no overlay (decision 0041 point 2 says so on purpose). The
  player still clicks the shortcut, and the client would have started
  the core anyway (app/client/window.js:127-145). An early core start
  buys nothing, because state is rebuilt from the log at any start
  (decision 0008).
- F6 Hotkeys cannot be changed while running, and the page shows
  constants. The keys are read once (app/main.js:81-89, 392-403); the
  1 s config watch only moves the overlay (main.js:369). The fix
  sentence ends with "run scripts\run.ps1" (diag.py:45-46), but with a
  live client that script only raises the window (run.ps1:223-225): the
  key is not re-registered. The page prints the default keys as text
  (web/index.html:174-176, 203, 515; web/prices.js:322).
- F7 The calc opt-in is two steps in two places. `setup.ps1 -TcCalc`
  installs the component (tools/tc_pin.py:553-556) but the core also
  needs `"tc_calc": true` (server/al/theorycraft/calcwire.py:10,
  core.py:553-555). The import sentence names only the script
  (web/settingsio.js:34-38), and an import never turns the flag on, so
  a moved install shows the calc off with no switch in the app.
- F8 Non-Steam installs dead-end at consent. Discovery walks Steam
  libraries only (server/al/logfile.py:135-153). The API accepts a path
  (http.py:673-677), the page never sends one (web/app.js:1092), and the
  card just says to start the game once (web/app.js:1040). Likewise only
  the first league is kept (ninja.py:78-88), so a hardcore or standard
  player prices against the wrong league unless they type an id.
- F9 The `.build` download has four competitors and omits GGG's easier
  route. PoB merged its own export on 2026-08-27 (research 0017; not
  released yet, POB-REL), poe.ninja exports any listed character
  (NINJA-BP), guide sites ship files (SNIP-BUILD). GGG's page also lets
  a player upload their own file on the game's website, after which the
  game loads it (GGG-GAME); the dashboard copy names only the folder
  move (web/index.html:356-358).
- F10 Price watch is invisible. A moved price shows only inside its card
  on the Items tab; the only tab mark in the app is the Checks one
  (web/checks.js:94). Nobody will tune its threshold in a JSON file.
- F11 The filter pair is two paths to one outcome, unproven in game.
  One fold holds three paragraphs and two controls
  (web/index.html:409-430); both LIVE rows are open; whether an Import
  line works in an account filter is not documented (GGG-FILTER). Each
  refresh costs a manual move, by the floor.
- F12 Settings transfer moves the cheap part: 12 keys
  (settingsio.py:84-97), not the stat weights a player tuned by hand.
  Four imported keys (character, poll_ms, both hotkeys) stay inactive
  until a restart and the sentence does not say so (core.py:76, 80;
  main.js:81-89).
- F13 The one advisor line that matters is three clicks deep: play in
  Windowed Fullscreen, the only mode the overlay works in
  (gfx.py:201-202), sits behind two folds (index.html:543-544, 581-582).
- F14 Leftovers: POST /api/clipboard-read answers 501 (http.py:311-317)
  although the read lives in the client by design (decision 0003);
  run.ps1 keeps a no-op -Overlay switch (run.ps1:15-17); the overlay's
  shown or hidden choice is forgotten at every start (overlay_gate.js:22).
- F15 What players use around companion tools. Filters: the best-known
  project (2,852 stars, NS-API) reaches players by a self-updating
  ladder subscription or FilterBlade's account sync; only the manual
  path leaves a local file, re-downloaded about monthly (NS-README,
  SNIP-FILTER). Planners: Path of Building (130,338 downloads of the
  newest release, POB-REL) and web planners that import the player's
  own characters by login (MAXROLL), which AshLight cannot do while
  OAuth registration is closed. Exports: PoB codes, share links and,
  since 0.5.0, `.build` files (F9). Backups: no product; a widely used
  price-check overlay keeps one settings file that players copy by
  hand (EE2-DOC). Two norms AshLight lacks: settings changed inside the
  app and updates without a command (324,913 installer downloads and
  1.6 million update-manifest fetches for that overlay's newest release,
  EE2-REL); the update check belongs to B15 (0052, 0053).

## Recommendations

R1 Let the game-data snapshot refresh itself.
- Action: run the existing snapshot tool (it already checks web_data,
  the contact and a 24 h gate) as a hidden, low-priority process from
  run.ps1 at each start and from the keepalive supervisor when web data
  turns on, then daily while the log is idle. Never from the core.
- Impact: H (nine data consumers; Acts 5-6 rows at 1.0 with no step).
  Effort: M. Risk: a 48 MB first fetch during play - start and idle
  time only, one run at a time.
- ToS check: "public web data" rule; same sources, opt-in, User-Agent
  and contact as decision 0009; nothing bundled.
- Depends on: Open question 1. Files: scripts/run.ps1,
  server/al/keepalive.py, theorycraft/snapshot.py, diag.py, README.md.
- Acceptance: web data off -> no request at start (existing test); on
  -> a test core with a fake fetch has the files within one supervisor
  poll, no second request inside 24 h; no fix line names build.ps1.
- ZERO-CLICK: nothing beyond the one web-data tick.

R2 One card for web data: contact field and league picker.
- Action: add to "Prices and web data" a write-only contact field
  (saved in the gitignored local config; the API still says only
  whether one is set) and a league picker fed by the league list
  already fetched; the two Checks rows link there.
- Impact: H (prices, movers, price watch, filter tiers and the tree
  export hang on these values). Effort: M. Risk: the contact is personal
  data - say where it goes; never echo or export it (settingsio.py:108).
- ToS check: "truthful User-Agent" and "never a POESESSID" untouched;
  decision 0015 item 1 holds (read only from the local config).
- Depends on: none. Files: web/index.html, web/prices.js,
  server/al/http.py, core.py, ninja.py, diag.py.
- Acceptance: after a POST no response or log holds the value; a league
  pick changes the next overview request; no failing web-data row.
- ZERO-CLICK: one typed value per install; the league is asked only of
  players outside the main league.

R3 Hotkeys: show the real keys, rebind in the app, heal conflicts.
- Action: put the two effective keys in the snapshot and print them
  where the page prints the defaults; one "change key" field each
  (checked by hotkeys.safe_accelerator); the client re-registers on a
  config change and reports the result in a runtime file; a taken key
  falls back to the first free one of a short safe list; fix diag.py:45.
- Impact: H (a taken key now costs a JSON edit, Quit and a relaunch).
  Effort: M. Risk: a global shortcut takes the key from every program -
  keep "Ctrl or Alt held, never a game key" (hotkeys.py:24-28).
- ToS check: nothing is sent to the game; the clipboard read stays one
  per manual press (decision 0003).
- Depends on: none. Files: app/main.js, app/hotkey.js,
  server/al/hotkeys.py, state.py, diag.py, web/index.html, web/app.js.
- Acceptance: node test - a config change swaps the registration with
  no restart; a taken key yields a reported alternate; the page holds
  no literal key text.
- ZERO-CLICK: conflicts heal by themselves; rebinding is optional.

R4 Autostart that is worth enabling.
- Action: a "Start with Windows" checkbox in the tray and on the
  Settings tab (it runs the existing autostart script hidden), and a
  logon task that starts the client in a new tray-only mode (no
  companion window; overlay gated by the log) instead of the core alone.
- Impact: H (the only path to a session with no click: the overlay
  appears with the game's first fresh log line). Effort: M. Risk: about
  180 MB idle from logon (app/main.js:121-126) - measure; fallback:
  core-only at logon, tray client on the first fresh log line.
- ToS check: the overlay stays a separate click-through window inside
  the client; game start is read from Client.txt freshness only
  (decision 0029); opt-in, off by default, per-user task.
- Depends on: Open question 2. Files: scripts/autostart.ps1,
  autostart_launch.vbs, run.ps1, app/main.js, app/client/tray_menu.js.
- Acceptance: -DryRun shows the tray-client action; node test - tray
  mode builds tray and overlay, no companion window, no focus call; a
  test-port run records idle memory against the 250 MB budget.
- ZERO-CLICK: one tick once.

R5 Calc opt-in in one act.
- Action: now, `setup.ps1 -TcCalc` writes `"tc_calc": true` after a
  verified install, and the import and Checks texts name one step;
  later, a "Set up the Path of Building calc" button in the client runs
  the same script hidden and reports in Checks.
- Impact: M-H (PoB-backed deltas, decision 0024, need a terminal and a
  JSON edit today). Effort: S, then M. Risk: a hash refusal must leave
  the flag untouched.
- ToS check: optional tools stay hash-pinned, unmodified and fetched
  only on the player's opt-in (decision 0018); the click is that opt-in.
- Depends on: the button needs a second client action (decision 0041
  point 7 allows one). Files: scripts/setup.ps1, tools/tc_pin.py,
  web/settingsio.js, diag.py; later app/client/preload.js, launcher.js.
- Acceptance: in a sandbox the switch leaves the flag set and the calc
  row passing with no edit; a forced mismatch leaves the flag as it was.
- ZERO-CLICK: one opt-in instead of two.

R6 Find Client.txt outside Steam.
- Action: a "Can't find Client.txt?" field on the consent card for the
  folder or file, sent through the existing consent API; discovery also
  tries the standalone client's default folder once that path is
  confirmed (Open question 7).
- Impact: M (a non-Steam install stops at step one; 1.0 brings
  free-to-play players through several launchers). Effort: S. Risk:
  low; the path check exists (logfile.py:106-132).
- ToS check: only Client.txt, only after the opt-in; a folder stat
  reads no game file; the game's registry keys and config files stay
  unread (research 0032).
- Depends on: none. Files: web/index.html, web/app.js, logfile.py.
- Acceptance: a posted path starts the tailer; a bad one shows the
  existing error; discovery finds a fake non-Steam tree in a temp dir.
- ZERO-CLICK: discovery first; the field shows only if nothing is found.

R7 Trim the documented surface.
- Action: drop poll_ms, underlevel_gap, price_watch_pct and
  boots_speed_level from the README and the example file (they keep
  working); replace the `character` key by a "this is my character"
  pin in the picker; apply poll_ms and character without a restart; the
  README player path becomes setup, then the shortcut (after R1).
- Impact: M (with R2-R6: 6 settings, 2 switches, the calc and
  autostart, each with a control). Effort: S. Risk: none.
- ToS check: settings and docs only; no data source or game contact.
- Depends on: R1 for the README part. Files: README.md,
  config/local.example.json, server/al/core.py, state.py, web/chars.js.
- Acceptance: the README names no setting without a control; an edit
  of the two keys takes effect within one tick.
- ZERO-CLICK: fewer things asked.

R8 One filter control, stamped, verified before it grows.
- Action: the merge becomes the one primary control, the plain download
  a small secondary link; the section header carries date and league;
  LIVE-FILTER-MERGE runs before any further filter work.
- Impact: M (one paragraph and control instead of three and two;
  staleness visible). Effort: S. Risk: none new.
- ToS check: "never modify any game file" - still a download the
  player places (decisions 0031, 0033); cached prices only.
- Depends on: the operator's in-game load. Files: web/index.html,
  web/filtermerge.js, server/al/theorycraft/lootfilter.py.
- Acceptance: one primary control; date and league in the merged
  section; byte-identity tests green.
- ZERO-CLICK: the content regenerates itself; the move stays the player's.

R9 `.build`: fix the texts, name the upload route, plan the exit.
- Action: correct the passives note (F4); add GGG's second route to the
  copy (upload on the game's website); the daily PoB release check
  (decision 0025) raises a note when a release exports `.build` itself,
  and the download is then retired.
- Impact: L-M. Effort: S. Risk: players who paste a share link and have
  no PoB lose a route - guide sites cover them.
- ToS check: download only (decision 0034); the upload is the player's
  own browser act; AshLight calls no endpoint.
- Depends on: none. Files: buildfile.py, web/index.html, tc_drift.py.
- Acceptance: note text test; a fake release body naming the export
  raises the note.
- ZERO-CLICK: the exit trigger needs no reminder.

R10 Fold price watch into price movers and make a move visible.
- Action: "Your checked items" rows on top of the movers block and a
  mark on the "Items and prices" tab when one moved; the card goes.
- Impact: M. Effort: S. Risk: the live-region cap (12 of 12) - the tab
  mark adds none.
- ToS check: cached poe.ninja book only, only while web data is on
  (decision 0036).
- Depends on: none. Files: web/index.html, pricewatch.js, prices.js.
- Acceptance: node test - a moved item sets the mark and renders above
  the movers; the no-request test stays green.
- ZERO-CLICK: fills from the press the player already makes.

R11 Settings transfer carries the stat weights.
- Action: export schema 2 adds the weights and the sidegrade band; the
  import sentence names any key that waits for a restart.
- Impact: L (once per PC, but it then moves the only hand-tuned data).
  Effort: S. Risk: a bad file - same validator, whole-file refusal.
- ToS check: own settings only; never contact, token, cookie or paths;
  an import never turns web data or the calc on (decision 0036).
- Depends on: none. Files: settingsio.py, core.py, web/settingsio.js.
- Acceptance: a round trip keeps the weights; schema 1 files still load.
- ZERO-CLICK: nothing in play.

R12 Small items: one graphics sentence, three leftovers.
- Action: show "play in Windowed Fullscreen" on the first-run card and
  as a Checks note, and remove the advisor if 1.0 renames an option
  label; delete the clipboard-read stub; remember the overlay's shown
  or hidden choice in a runtime file; drop run.ps1 -Overlay.
- Impact: L. Effort: S. Risk: tests that name the stub or the switch.
- ToS check: advice only, no game file read or written; the one
  clipboard read stays the client's per-press one.
- Depends on: none. Files: web/index.html, server/al/diag.py, http.py,
  app/overlay_gate.js, scripts/run.ps1, docs/ops/1.0-launch-runbook.md.
- Acceptance: the note shows in Checks; the route answers 404; a
  hidden overlay stays hidden after a client restart.
- ZERO-CLICK: the sentence shows itself; one toggle fewer per session.

R13 Search-string hotkey for one-screen players.
- Action: an optional third hotkey writes the next search string to the
  clipboard per press and names it on the overlay card; unset by default.
- Impact: M without a second screen (the dashboard path is 2 clicks and
  two window switches). Effort: M. Risk: a third global key; the card
  must say what was copied.
- ToS check: nothing is typed into the game; one clipboard write per
  manual press, no watcher, no timer; decision 0014 names clicks only
  (Open question 4).
- Depends on: R3 and that ruling. Files: app/main.js,
  app/overlay/overlay.js, server/al/state.py.
- Acceptance: node test - one write per press, a held key does not
  repeat, none without a press; the overlay keeps its two lines.
- ZERO-CLICK: one press instead of tab, Copy and a window switch.

## Cut or merge

- Cut now: the clipboard-read stub and the no-op -Overlay switch (R12);
  four keys from player docs (R7).
- Cut on a trigger: the `.build` download when the pinned PoB release
  exports it (R9); the graphics advisor at the first option-label drift
  (R12); autostart.ps1 as a typed command once the checkbox exists (the
  script stays as the mechanism).
- Merge: filter download into the merge control (R8); price watch into
  price movers (R10); contact and league into the web-data card (R2).
- Hide: settings transfer and graphics stay folded; port, hot_reload
  and the drift key stay out of player docs.
- Automate away: snapshot fetch (R1), hotkey conflicts (R3), the league
  (R2), the calc flag (R5), the logon start (R4), the overlay choice
  (R12), non-Steam log discovery (R6).
- Keep as is: run history with ladder and visits, character keying,
  language notice, hot reload, copy helpers, the Checks structure.

## Rejected

- Writing the filter or the `.build` into the game's folders, even by a
  Save dialog in the client: floor "never modify any game file"; the
  reversal conditions of decisions 0031 and 0034 are not met.
- Reading the game's own config or registry keys for display mode,
  language, league or install path: outside the Client.txt allowance
  (research 0032).
- Finding the game process or window to start or place the overlay:
  decision 0029, no process-list check.
- Typing or pasting a search string into the game, or sending Ctrl+C:
  synthesized input, floor.
- A clipboard watcher that checks items by itself: floor, one read per
  manual press (another tool switched such reads off on 2026-11-13,
  EXUI-REL).
- A filter upload or build subscription through GGG's account API: OAuth
  only, registration closed (ROADMAP TC-OAUTH-REG); never a cookie.
- Sending the Checks report anywhere by itself: ruling J (research 0032).
- A snapshot fetch by the core on demand: decision 0009 item 2; R1 keeps
  the fetch in a separate process.
- A paid updater or tier, as one filter tool sells (floor: no revenue
  from GGG intellectual property); bundled filters or game data (0009).

## Open questions

1. R1 needs decision 0009 item 2 and the 0013 amendment reworded (they
   tie the fetch to build.ps1). Their "Reverses if" names users missing
   the data and the switch; the evidence here is structural (F3), not
   observed on other players. Needs an adjudicator.
2. R4 changes what the logon task starts and adds a tray item; decision
   0041 point 2 states "no overlay at logon". Needs an adjudicator or
   the operator, with the idle memory number.
3. Once a public repository exists, may the User-Agent carry a
   project-level contact (its public issue page) so that no player
   types one? Decision 0015 puts the contact in the local config only.
   Needs an adjudicator, together with the go-public note (0057).
4. R13: is a clipboard write on an AshLight hotkey press inside decision
   0014, which names clicks? Needs an adjudicator.
5. Does an Import line work in an account-hosted or followed filter, and
   what share of PC players keep a local filter file? UNVERIFIED
   (GGG-FILTER is silent); the in-game check answers the first part.
6. Which PoB release ships the `.build` export, and does it write into
   the planner folder itself? UNVERIFIED until a release after v0.23.1.
7. The standalone client's default log folder for PoE2: UNVERIFIED
   (research 0002).
