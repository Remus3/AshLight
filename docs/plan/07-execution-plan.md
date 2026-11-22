# 07 - Execution plan

Date: 2026-11-18. Ultraplan plan section (docs/plan/README.md).
Status: final

Inputs: the verified work packages of the ten clusters (SEC, LOOP, PUB, REL,
PLAY, OVL, DATA, TC, RUN, TEST), the input units of docs/plan/01 to 06 and
docs/plan/findings.json, research 0047 (file structure), 0049 (test-suite
speed and merge throughput) and 0058 (loop), CLAUDE.md, tools/plan_check.py,
and the review of the draft by three lenses (coverage, execution, floor;
section Review record). The machine-readable plan is
docs/plan/packages.json; this file explains it and never repeats a package's
full detail.

## How to read this plan

- Package: one unit of work for one agent, at most 90 minutes, with its
  files, tests, acceptance line and dependencies. All of that is in
  docs/plan/packages.json; `python tools/plan_check.py wave <n>` prints a
  wave's packages in merge order.
- Wave: a set of packages that may run at the same time. Every dependency
  sits in a strictly earlier wave; inside a wave that runs (waves 0 to 37)
  no two packages share a file, a new file or a serial group. The parked
  wave 99 is a holding list, not a wave that runs, and is the one exemption
  (bullet Wave 99 below, and section Parked packages). A wave ends with
  main green and its rows flipped.
- Session: consecutive waves one operator `continue` runs hands-off. The
  grouping is a forecast; a session that stops early resumes at the first
  unmerged package of the open wave.
- Owner: `session` (a wave session runs the package; its ROADMAP row carries
  `BLOCKED: session wave <n>`) or `loop` (the headless loop takes the row
  once HALT is removed and the rows named in its `DEPENDS:` are done). A
  session never waits for the loop: no session package depends on a loop
  package (the validator checks it).
- Wave 0: the plan landing (PLAN-LANDING), the planning session's own act in
  the main checkout. It is session 0 and needs no `continue`; wave 1 starts
  from the hand-off it writes.
- Wave 99: parked packages, each with its unblock condition. Once the
  condition reads true the package joins the next open wave; re-run the
  validator after the move. Parked packages may name the same file or
  serial group (10 files and 3 groups today; section Parked packages lists
  them): nothing in the list runs. The shared-file rule binds a package
  from the wave it joins, so two parked packages that share a file or a
  group never join the same wave, and a parked package never joins a wave
  that already has an editor of one of its files; the validator refuses
  either plan.
- Integrator: the one writer of ROADMAP.md, CLAUDE.md, AL-NEXT-SESSION.txt,
  the three README indexes and docs/design/reviews.log. A package returns
  its row flip, Settled bullet, index line and review line in its result
  (its integrator_edits); the wave integrator applies them on the
  integration worktree, as one commit per merge batch, before that batch's
  whole suite (section Gate commands). The rows themselves are landed once,
  in wave 0; a package only flips its row.
- Main-checkout acts (isolation none) run one at a time in merge order, each
  committed or read back before the next starts and never while main is
  being moved.
- Publishing rests on the operator's own recorded words (section Operator go
  for publishing). The go was recorded on 2026-11-18, so the packages that
  lift the local-only order are scheduled (waves 4 and 5); without the
  hand-off lines they go back to wave 99.
- Decision numbers are reserved here (section Reserved decision numbers); a
  package that writes a decision uses the number given in its new_files
  entry.

How the two files are kept. Until the close-out of 2026-11-18 both files
were written by a builder outside the tree (the AL sidecar folder
Scratch/up-plan: build_plan.py, doc07.py and overrides.json). The builder is
retired: it no longer reproduced the tracked files (PLAN-LANDING listed two
tracked files as new, and 31 operator_act fields had been edited in
packages.json directly). docs/plan/packages.json is now the source of truth
of the plan. To change the plan, patch packages.json with a small script
(ASCII, LF, JSON indent 1), keep each wave's merge_order, the package order
(wave, then merge order), the sessions list and the hotspots list in step,
update the matching lines of this file, and run, from the repository root:

    python tools/plan_check.py check
    python -m pytest -q tests/test_plan_check.py

The validator was extended for this plan (tools/plan_check.py, schema 1
kept): an optional package field `owner`, an optional top-level `sessions`
list, the parked wave exempt from the shared-file rule (it is a holding
list, not a wave that runs), and `rows` now prints `DEPENDS: <ids>.` and
`BLOCKED: session wave <n>.`, the two tags docs/plan/06 asks the landing to
carry.

## Numbers

- Packages: 419 verified in the cluster files; the review added 3
  (PLAN-LANDING, SEC-STEAM-SCAN-A03, DATA-RESEARCH-GAPS) and dropped 1
  (LOOP-PLAN-CONTRACT, its work moved into PLAN-LANDING); 396 in the plan
  after 25 folds.
- Owners: 339 session packages in waves 0 to 37, 16 loop-owned packages, 32
  parked in wave 99.
- Waves: wave 0 (the landing), 37 open waves and the parked wave. Sessions:
  10 operator `continue`s after the landing (session 0), about 75 h 26 min
  of wall-clock in all (6.1 to 8.5 hours each).
- Agent time: about 325 hours in sessions, 11 hours in the loop, 27 hours
  parked.
- Input units: 387 (4 added by the review: A-02, A-03, RG-0056, RG-0055);
  every one is mapped (section Coverage).
- HALT is removed in wave 6 (session 2), by AUTO-21.
- Added 2026-11-19 (docs/plan/10, landed by the wave 11 pre-batch
  integrator): 12 session packages in waves 38 to 42 (session 11);
  UI-CARD-COLLAPSE moved from the drafted wave 38 to wave 41 (it shared
  serial group web-shell, web/index.html and web/app.css with UI-HEADER-TEXT
  and server/al/plug/stores.py with KINDLER-STORE); RUN-BUILD-STAMP-UI
  widened by decision 0082 part 2.

## Wave width and expected time

Width comes from research 0049. Its finding F5: with one whole suite per
package the suite gate allows 7.5 to 9.3 merges an hour whatever the number
of agents (one suite per tree, 191 to 238 s a run, 2.03 runs a merge), so 12
packages would hold the gate for 78 minutes. Its recommendation R1, ruled as
Q-17: each package runs only its named test files (file-named runs are not
gated), and a merge agent runs one whole suite per merge batch of K = 4 on
an integration worktree. At the assumed escape rate of 5 percent a batch
needs a second suite in 19 percent of cases, which gives about 64 packages
an hour.

- Wave 1: 11 worktree packages. SEC-NO-DISCOVERY merges first and alone with
  its own whole suite (it changes how every test core is built), run after
  its own Settled bullet is applied; the other 10 merge in 2 batches of at
  most 5 (R1 allows K = 4 to 5), so the wave has 3 whole-suite gate rows.
  This is the measuring wave: research 0049 left the escape rate open (its
  Open question 3) and names a dry wave of 8 packages with at most 3
  whole-suite gate rows as the acceptance of R1.
- Waves 2 and later: at most 12 worktree packages when planned, in merge
  batches of at most 4; a close-out that adds packages without moving others
  may widen a wave to at most 16 (four batches) (ruling R6, 2026-11-18). Gate
  time for a full wave is about 3 x 1.19 x 4 min = 14 minutes (about 5 once
  the suite runs in parallel), far below the build time of the wave, and the
  integrator has at most 12 results to apply. More, narrower waves were
  preferred over wider ones: the number of waves is set by the file chains
  (section Hotspot schedule), not by the width.
- Main-checkout acts (isolation none: docs, records, the first push, the
  HALT removal) do not take a worktree slot; at most 4 a wave.
- Close-out 2026-11-18: the eight publishing packages joined existing waves
  without moving any other package, so four waves are wider than 12 and run a
  fourth merge batch: wave 4 (14 worktree packages), wave 18 (14), wave 19
  (13) and wave 22 (13). The width of 12 was a parameter of the retired
  builder, not a rule of the validator; each of these waves costs one more
  batch suite (about 10 minutes before wave 10, about 8 after it), which the
  wave times below include. Every batch, the fourth included, has its own
  whole suite before main moves; with the batch lowered to 3 (rule below)
  these waves run five batches.
- If wave 1 measures an escape rate above 10 percent, the session lowers the
  batch to 3 (width 9) until TEST-SELECT has landed (wave 8); the plan needs
  no rebuild for that.
- Until TEST-SELECT (wave 8) is on main, a package's subset is the test list
  in its own `tests` field and the cap of ruling Q-17 (no timing tests, at
  most 90 s per ungated subset) is kept by hand: the timing files
  (tests/test_budgets.py, tests/test_fuzz.py, tests/test_soak.py and
  tests/test_math_perf.py) and any subset expected to run over 90 s go
  through the suite gate as a file-named run.
- Until TEST-PORT-LEASE (wave 5) is on main, the files that bind a fixed or
  probed port (tests/test_keepalive.py, tests/test_procs.py,
  tests/test_supervisor.py, tests/test_dash_console.py,
  tests/test_fullstack.py and tests/test_math_e2e_live.py) go through the
  suite gate too, so two of them never run at the same time (research 0049
  F10).

Expected time of a wave = the longest package in it (all packages run at
once, each in its own worktree) + per merge batch one suite x 1.19 plus 5
minutes of merge work + 10 minutes for the integrator. The suite is taken as
4 minutes until TEST-GATE-CALLERS (wave 10) makes it parallel, then 1.5
minutes. Three terms were added by the review: 10 minutes when the longest
package of the wave is a fold of 85 minutes or more (a second context and
review inside one agent); the full estimate of a package that must run alone
after the last batch (REL-CUTOVER-LIVE, and GP-09 since the close-out); and,
after wave 6, one more suite per merge batch, because a lane suite of the
loop may be ahead of the session's (one suite per tree, research 0049 F5). A
session is filled up to 520 minutes and at most 5 waves.

## Sessions

The goal is the fewest operator `continue`s, not the fewest waves. One
`continue` runs one session; the expected wall-clock is hands-off time. The
loop-owned rows need no session at all. A session of four full waves is long
(about 8 hours); if the account's usage window or the session's context ends
it earlier, the next `continue` resumes the open wave and the count of
sessions rises (three waves a session: 13 sessions). Nothing else changes.

- Session 0: wave 0, 1 session packages, about 1 h 50 min. The planning
  session itself: no `continue`. Delivers: the plan is landed: 08 and 09
  exist, every package has its ROADMAP row, the hand-off starts wave 1.
- Session 1: waves 1 to 3, 42 session packages, about 6 h 47 min. Delivers:
  the no-discovery guard (F-001) is on main; the local HTTP surface is
  pinned by one test file; the isolated demo mode exists (python -m
  server.al --demo).
- Session 2: waves 4 to 6, 41 session packages, about 7 h 27 min. Delivers:
  the Play skeleton (7 fixed regions) is on the page; the private repository
  exists and the first push is green; HALT is removed; the headless loop
  takes the loop-owned rows.
- Session 3: waves 7 to 9, 36 session packages, about 6 h 48 min. Delivers:
  the wave gate policy is recorded and the test selector picks each
  package's subset.
- Session 4: waves 10 to 13, 48 session packages, about 8 h 21 min.
  Delivers: one gate spelling; the whole suite runs in parallel; the item
  check compares against worn gear (worn-gear baseline); the Play tab never
  scrolls (legacy cards are gone).
- Session 5: waves 14 to 17, 49 session packages, about 8 h 10 min.
  Delivers: four tabs: Play, Build and items, Run, Settings; the dashboard
  prints the real keys and can change them; the parse ledger is wired
  (LIVE-1 read-back starts).
- Session 6: waves 18 to 21, 56 session packages (51 planned; 5 joined at
  the wave 18 start, session 16), about 8 h 31 min before they joined.
  Delivers: the bootstrap installer exists; the release stage round trip
  (install, update, rollback, uninstall) passes.
- Session 7: waves 22 to 24, 38 session packages (LOOP-CI-ISSUES joined
  at the wave 18 start, session 16), about 7 h 38 min before it joined.
- Session 8: waves 25 to 29, 17 session packages, about 8 h 10 min.
  Delivers: the Settings rail is complete.
- Session 9: waves 30 to 33, 12 session packages, about 7 h 27 min.
  Delivers: design 0001 and the cockpit decision are rewritten (records).
- Session 10: waves 34 to 37, 7 session packages, about 6 h 07 min.

- Session 11: waves 38 to 43, 13 session packages, about 9 h 00 min. Added
  2026-11-19 from docs/plan/10 (operator requests 2026-11-19, decisions 0081
  to 0083). Delivers: the item info popover and Kindler build generator are
  on the Build tab.

Sessions 8 to 10 are narrow on purpose: what is left there is the tail of
the file chains (one editor of web/index.html a wave), so they cost
wall-clock but little agent time. They hold P2 and P3 work; stopping after
any session leaves main green and every landed feature complete.

## Wave overview

One line per wave: session, width (session packages as worktree +
main-checkout, then loop rows released), expected minutes, goal. The gate is
the same for every session wave (section Gate commands); additions are
named.

- Wave 0 (session 0): width 0 + 1; about 110 min. The plan itself lands:
  docs/plan/08 (how a session runs a wave, the agent contract), docs/plan/09
  (the one batched operator ask), the ROADMAP row of every package and the
  hand-off that makes 'continue' start wave 1. Milestones: the plan is
  landed: 08 and 09 exist, every package has its ROADMAP row, the hand-off
  starts wave 1. Leads: Land the plan: orchestration and operator-acts
  sections, ROADMAP rows, hand-off.
- Wave 1 (session 1): width 11 + 4; about 139 min. What everything else
  stands on: the no-discovery guard, the local security P0s that need
  nothing first, the hardened write path, the first steps of the loop-parser
  fix (the tick split, the test carve and the row lint tool), the ledger
  rule and the slot tables. Milestones: the no-discovery guard (F-001) is on
  main. Leads: A pointed, test or demo core never looks for the live
  Client.txt; Serve /web/ from a fixed name map (closes the UNC path leak);
  Strict build XML intake: refuse an inflated payload holding a NUL byte.
  Gate addition: SEC-NO-DISCOVERY merges first and alone.
- Wave 2 (session 1): width 12 + 3; about 119 min. The second step of the
  foundations: the loop session-line fix, the demo-mode core, the
  fresh-clone proof and the item card seam. Milestones: the local HTTP
  surface is pinned by one test file. Leads: Item card parts registry
  (server side seam); Demo mode core: an isolated instance on a fixture
  folder; LOOP-PREFLIGHT core: session line, dry run past HALT, tick step
  seam.
- Wave 3 (session 1): width 12 + 0; about 149 min. Demo mode is complete;
  the HTTP surface is pinned; the gate output keeps its tail. Milestones:
  the isolated demo mode exists (python -m server.al --demo). Leads: Demo
  mode entry: python -m server.al --demo <fixture dir>; Pin the pytest
  plugin set; register markers; keep the end of the gate output; A failed
  item is parked visibly; a foreign gate failure ends the fix rounds.
- Wave 4 (session 2): width 14 + 1; about 139 min. Leads: Record the
  go-public decision and the rules text; Guarded pre-push hook and its
  tests; Replace the local-only wording in loop tools and ritual files.
- Wave 5 (session 2): width 12 + 1; about 179 min. Milestones: the Play
  skeleton (7 fixed regions) is on the page; the private repository exists
  and the first push is green. Leads: WAVE-INTERPLAY: BLOCKED reason echo
  and the dispatch re-check from HEAD; Plug-in folder: ticks, Checks rows
  and token-gated routes without shared-file edits; setup.ps1 makes the
  sidecar private; the logon launcher starts PowerShell by its System....
- Wave 6 (session 2): width 12 + 1; about 129 min. Milestones: HALT is
  removed; the headless loop takes the loop-owned rows. Leads: Checks note
  when AshLight's folders let someone else write; Move the five CRLF /
  hand-rolled writers onto the jsonfile helper; Play view: context modes,
  item card and kept checks. Gate addition: AUTO-21 last (six checks, then
  HALT is removed).
- Wave 7 (session 3): width 12 + 0, 2 loop; about 141 min. Leads:
  app/test/_web.js: one helper that knows where dashboard sources live (node
  side); tests/srcpaths.py: one helper that knows where dashboard sources
  live (Python side); Core saves retried from the tick with back-off; one
  Checks row while unsaved. Releases 2 loop-owned rows.
- Wave 8 (session 3): width 12 + 0; about 131 min. Leads: web/fmt.js: pad,
  duration and clock defined once; Core restarts a dead log reader and the
  Reading row tells the truth; tools/test_select.py: the test files for a
  diff.
- Wave 9 (session 3): width 12 + 0; about 136 min. Milestones: the wave gate
  policy is recorded and the test selector picks each package's subset.
  Leads: Publish the item check in stages; Record the wave gate policy
  (Q-17) in a decision, the lane prompt and /done; web/registry.js:
  ALApp.register and per-panel isolation in render, tick and start.
- Wave 10 (session 4): width 12 + 0; about 131 min. Milestones: one gate
  spelling; the whole suite runs in parallel. Leads: Item check compares
  against the worn item first; Legacy out 1: old strip tiles, trade card and
  build alert slot; One gate spelling in the loop, gates.txt, build.ps1 and
  /done; kit crash = retry.
- Wave 11 (session 4): width 12 + 0, 1 loop; about 125 min. Milestones: the
  item check compares against worn gear (worn-gear baseline); the Play tab
  never scrolls (legacy cards are gone). Leads: 'I wear this' endpoint,
  worn-gear switch and clear; Legacy out 2: consent, guide, tip, language
  and item cards leave Play; Calc opt-in in one act (setup switch). Releases
  1 loop-owned rows.
- Wave 12 (session 4): width 12 + 0, 2 loop; about 120 min. Leads: Generate
  the dashboard's panel script and style tags at serve time; Quiet base
  button, one filled button; OBS-CRASH: the core writes
  ops/runtime/last-exit.json on every exit path; Checks reads.... Releases 2
  loop-owned rows.
- Wave 13 (session 4): width 12 + 0, 1 loop; about 125 min. Leads: Build id
  in the dashboard footer, overlay About and tray tooltip; Own counters:
  metrics.py and the token-gated GET /api/debug; Game data arrives at start:
  the supervisor runs the snapshot tool hidden. Releases 1 loop-owned rows.
- Wave 14 (session 5): width 12 + 0, 3 loop; about 115 min. Milestones: four
  tabs: Play, Build and items, Run, Settings. Leads: Four tabs: Play, Build
  and items, Run, Settings; Hotkeys in the core: effective keys in the
  snapshot, POST /api/hotkeys, Checks rows for...; Budget log: the core
  records its own footprint once a minute. Releases 3 loop-owned rows.
- Wave 15 (session 5): width 12 + 1; about 135 min. Leads: Counter call
  sites: fetches per host, calc starts and time-outs, press outcome;
  Optional wear key (unset by default); Update from a local zip: verify,
  build beside, self-test, stage.
- Wave 16 (session 5): width 12 + 0, 1 loop; about 115 min. Milestones: the
  dashboard prints the real keys and can change them; the parse ledger is
  wired (LIVE-1 read-back starts). Leads: Dashboard prints the real keys,
  one change-key field per chord, one Play line while the...; Wire the
  ledger: feed_line hook, write tick, drift note, read-back flags, waystone
  shape; Python logs bounded, one format, a banner per start, faulthandler
  on its own file. Releases 1 loop-owned rows.
- Wave 17 (session 5): width 12 + 0, 1 loop; about 125 min. Leads: Build and
  items grid 1: Build, Health and next, Search strings; Overlay legibility
  recipe and two type sizes in the overlay CSS (TD-05, part 1); Contact
  value: a write-only POST and its core setter. Releases 1 loop-owned rows.
- Wave 18 (session 6): width 14 + 0; about 133 min. Leads: Build and items
  grid 2: Last item, Prices with checked items, Item scoring; One hook for
  data checks: diag_data (attach, facts, rows); A bind failure names its
  cause; --port stays in the block (P8-4).
- Wave 19 (session 6): width 13 + 0, 3 loop; about 143 min. Leads: 'Tried in
  game' card on the Checks tool; Map ladder tick is free when nothing
  changed (AUDIT-P8-LOW P8-5); overlay.log and run.log bounded, same stamp
  format. Releases 3 loop-owned rows.
- Wave 20 (session 6): width 12 + 0; about 110 min. Milestones: the
  bootstrap installer exists. Leads: Overlay slider sets the plate alpha
  only: limits 0.80 to 1.0, default 0.86, saved layou...; Overlay view seam
  (server/al/overlayview.py) with the card-slot holder order and the 10...;
  Release stage: the PASS / FAIL report (static gates).
- Wave 21 (session 6): width 12 + 0; about 125 min. Milestones: the release
  stage round trip (install, update, rollback, uninstall) passes. Leads: Run
  grid 1: Acts, Maps and Deaths cards; Quiet feed: no minute stamp or report
  text in the snapshot, ages stepped at 5 minutes; Zone moment card in the
  one card slot, and the guide-line fields for HUD line 2.
- Wave 22 (session 7): width 13 + 0; about 143 min. Leads: Run grid 2:
  Recent, Last session and Characters cards; The report from an allow-list
  of structured fields, with a hardened redactor (P8-7); Overlay HUD line 2:
  the opt-in guide line and the fixed card anchor.
- Wave 23 (session 7): width 12 + 0; about 125 min. Leads: Settings rail 1:
  Checks, Reading and web data, Overlay; Move the overlay page and the
  starting page off file:// onto one app scheme; Teach the item-check key in
  the empty card slot, then retire it.
- Wave 24 (session 7): width 11 + 1; about 190 min. Leads: Contact field in
  the web-data card and honest blocked wording; Five cause rows in Checks;
  Core refuses Origin null and file:// once both local pages load from the
  app scheme.
- Wave 25 (session 8): width 3 + 0, 1 loop; about 93 min. Leads: Find
  Client.txt outside Steam: a typed path on the consent card; OVERLAY-FEED:
  /events?view=overlay sends only the fields the HUD reads, only when one
  c...; luajit leaves when it is not needed. Releases 1 loop-owned rows.
- Wave 26 (session 8): width 2 + 0; about 98 min. Milestones: the Settings
  rail is complete. Leads: Settings rail 2: Keys, Appearance and tools,
  About and data; footer; Core: start the updater by itself, 'Update now'
  and click-only.
- Wave 27 (session 8): width 4 + 0; about 93 min. Leads: Copy pass: eleven
  sentences and four errors never send the player to a script; Accessibility
  CSS: inset focus ring, 24 px targets, forced colours, text spacing; Panel
  move B: layout, weights, web data and graphics panels.
- Wave 28 (session 8): width 3 + 0, 1 loop; about 108 min. Leads: Theme
  choice: Dark, Follow Windows, Light; In-browser accessibility pass in the
  CDP harness; Parse each data file once. Releases 1 loop-owned rows.
- Wave 29 (session 8): width 3 + 0; about 98 min. Leads: Settings group
  'Overlay shows': part switches, presets Full / Cards only, zone-guide
  ch...; Player notes: bounded store, token route and the your-note row;
  Screen-reader pass tool and its refusals.
- Wave 30 (session 9): width 3 + 0; about 118 min. Leads: Card time setting:
  20 / 60 / 200 s (TD-18, optional); Panel move C: remaining Play blocks
  (events and trades, item check, rates and price); Two Checks notes: a
  stale loop tick (dev host) and the Electron end of life.
- Wave 31 (session 9): width 2 + 1; about 108 min. Milestones: design 0001
  and the cockpit decision are rewritten (records). Leads: Player notes:
  edit box on Run and the export option; 'This is my character' pin in the
  picker; poll_ms and character apply without a restart; Records: design
  0001 rewritten, the cockpit decision, decision 0014 amended.
- Wave 32 (session 9): width 3 + 0; about 113 min. Leads: Settings: version
  lines, update line, opt-in wording; P8-8: the session ladder and the Maps
  card no longer mix characters; Supervisor diet and idle backoff.
- Wave 33 (session 9): width 3 + 0; about 108 min. Leads: One spacing scale,
  one badge, one list row, held by a lint; SessionState mixins: cards and
  trades; The page says what really happened to the feed.
- Wave 34 (session 10): width 3 + 0; about 113 min. Leads: 'Start with
  Windows' row on Settings; SessionState mixins: characters; Overlay: one
  plate class.
- Wave 35 (session 10): width 2 + 0; about 118 min. Leads: Weights panel
  marks changes and resets; SessionState mixins: idle and summary, published
  views.
- Wave 36 (session 10): width 1 + 0; about 88 min. Leads: Dashboard: one
  guide block, no separate Zone tip.
- Wave 37 (session 10): width 1 + 0; about 48 min. Leads: Small leftovers:
  Windowed Fullscreen sentence, the dead 501 stub, the no-op switch.
- Wave 38 (session 11): width 4 + 0; about 88 min. Leads: Item info lookup:
  token-gated GET /api/iteminfo over local caches; Drop the visible AshLight
  text left of the tabs; sr-only h1 kept; Kindler template schema and
  checked loader.
- Wave 39 (session 11): width 3 + 0; about 118 min. Leads: Text-parse PoB
  CurrencyNames, WorldAreas and Uniques Source lines under sha256 pins; Item
  names as link-like buttons with the shared item info popover; First
  authored Kindler templates, act 1 to maps.
- Wave 40 (session 11): width 2 + 0; about 118 min. Leads: Kindler
  candidates, PoB scoring and deterministic ranking on the Generate route;
  Build tab sub-tabs: Pasted build plus Kindler tabs with move, rename and
  close.
- Wave 41 (session 11): width 2 + 0; about 108 min. Leads: Collapsible cards
  on Build and items and Run in the desktop client; state in the core;
  Kindler result plan: stages, links, gem timing, passives, ascendancy, item
  focus.
- Wave 42 (session 11): width 1 + 0; about 108 min. Leads: Kindler result
  card with stages and follow Play guidance.
- Wave 43 (session 11): width 1 + 0; about 45 min. Leads: Default contact:
  the project's issues page once the repository is public.
- Wave 99 (parked): 32 packages; no gate; see Parked packages.

## Gate commands

Every session wave, in this order (owner id as CLAUDE.md, FLEET item 16):

1. Per package, in its worktree: the test files of its `tests` field as a
   file-named run (`python -m pytest -q <files>`), `npm test --prefix app`
   when it touches app/ or web/, and for a design_review package the
   design-reviewer pass. Through the suite gate instead (`python
   ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python -m pytest -q
   <files>`): the timing files and any subset over 90 s until TEST-SELECT is
   on main (wave 8), and the fixed-port files until TEST-PORT-LEASE is on
   main (wave 5). A package that adds a decision or a dated amendment leaves
   the two Settled-list tests of tests/test_audit_batch4.py out of its own
   run: they are red in its worktree until the integrator's commit of step
   2.
2. Per merge batch (4 packages in merge order, 5 in wave 1), on an
   integration worktree, under the merge lock, in this order: (a) merge the
   batch's package tips; (b) the integrator applies the batch's
   integrator_edits (row flips, Settled bullets, index lines, review lines)
   as one commit through `python ops/fleet_kit/fleet_gitlock.py run --owner
   <id> -- git commit ...`; (c) `python ops/fleet_kit/fleet_suite_gate.py
   run --owner <id> -- <suite>` and `npm test --prefix app`, where <suite>
   is `python -m pytest -q` up to wave 10 (TEST-GATE-CALLERS) and `python
   tools/suite_run.py` after it; (d) on green, main moves to the integration
   tip. The order matters: many packages add a decision or a dated
   amendment, and the Settled-list tests fail until the bullet is in
   CLAUDE.md, so the suite runs after the integrator's commit, never before
   it.
3. On red in step 2 (c): a failing Settled-list or index test is the
   integrator's commit to fix, never a reason to back a package out;
   otherwise the failing files are run on each package tip, the culprit is
   backed out together with its integrator edits, and one more suite runs. A
   kit traceback in the gate output is infrastructure: one retry, no
   verdict.
4. Main-checkout acts (isolation none) run one at a time in merge order,
   each committed or read back before the next starts, never while main is
   being moved.
5. Wave end: `python tools/plan_check.py check`, `git status --short` empty,
   every session row of the wave flipped.

The loop's rows use the loop's own gates (ops/loop/gates.txt: the whole
suite through the suite gate, npm test, the leak sweep) and its verifier.
The floor guards (tests/test_floor_static.py, the static part of the overlay
smoke test, tests/test_budgets.py) run in every batch suite, so no package
reaches main without them. After wave 6 the loop's lanes run their own
suites: during a merge batch the session holds the loop's merge lock
(LOOP-WAVE-HOLD), a lane suite already running finishes first, and the wave
estimate counts one suite per batch for it.

## Waves

Per wave: goal, hotspot files and their one editor, what the integrator
applies, test files to watch (edited by one package and run by another in
the same wave: the batch suite is the authority there), the gate, then the
packages in merge order. Package line: id [owner, size and minutes, lane,
tier, DR = design review] title. Files (at most five named). Deps.

### Wave 0: plan landing

Goal: The plan itself lands: docs/plan/08 (how a session runs a wave, the
agent contract), docs/plan/09 (the one batched operator ask), the ROADMAP
row of every package and the hand-off that makes 'continue' start wave 1.
Milestones: the plan is landed: 08 and 09 exist, every package has its
ROADMAP row, the hand-off starts wave 1. Leads: Land the plan: orchestration
and operator-acts sections, ROADMAP rows, hand-off.

- Session 0; width 0 worktree + 1 main-checkout, 0 loop rows released; about
  110 minutes.
- Hotspots: none.
- Integrator: ROADMAP.md rows of all 1 packages; AL-NEXT-SESSION.txt:
  PLAN-LANDING; docs/plan/README.md: PLAN-LANDING.
- Gate: python -m pytest -q tests/test_plan_operator_acts.py
  tests/test_plan_check.py tests/test_ascii_lf.py
  tests/test_research_numbers.py tests/test_leak_sweep.py and python
  tools/plan_check.py check, green; one commit through python
  ops/fleet_kit/fleet_gitlock.py run --owner <id> -- git commit; then every
  id of python tools/plan_check.py rows is read back in ROADMAP.md exactly
  once.

- PLAN-LANDING [session, L 90m, build, P0] Land the plan: orchestration and operator-acts sections, ROADMAP rows, hand-off. Files: docs/plan/08-orchestration.md, docs/plan/09-operator-acts.md, tests/test_plan_operator_acts.py. Deps: none.

### Wave 1: loop and watchers, local security, reliability and observability

Goal: What everything else stands on: the no-discovery guard, the local
security P0s that need nothing first, the hardened write path, the first
steps of the loop-parser fix (the tick split, the test carve and the row
lint tool), the ledger rule and the slot tables. Milestones: the
no-discovery guard (F-001) is on main. Leads: A pointed, test or demo core
never looks for the live Client.txt; Serve /web/ from a fixed name map
(closes the UNC path leak); Strict build XML intake: refuse an inflated
payload holding a NUL byte.

- Session 1; width 11 worktree + 4 main-checkout, 0 loop rows released;
  about 139 minutes.
- Hotspots: server/al/core.py (SEC-NO-DISCOVERY); server/al/http.py
  (SEC-STATIC-MAP); server/al/diag.py (SEC-NO-DISCOVERY); scripts/run.ps1
  (SEC-NO-PROXY); server/al/keepalive.py (SEC-NO-PROXY);
  tests/test_diag_self.py (SEC-NO-DISCOVERY); tests/test_keepalive.py
  (SEC-NO-PROXY); tests/test_http_security.py (SEC-STATIC-MAP).
- Integrator: ROADMAP.md rows of all 15 packages; CLAUDE.md:
  SEC-NO-DISCOVERY, GP-03, DATA-GGG-APPLICATION; docs/decisions/README.md:
  LOOP-LEDGERS, GP-03, DATA-GGG-APPLICATION; AL-NEXT-SESSION.txt: AUTO-03,
  RUN-LIVE-CLICKS-STRIKE, DATA-GGG-APPLICATION; docs/design/reviews.log: 1
  lines.
- Batches: 1: SEC-NO-DISCOVERY; 2: SEC-STATIC-MAP, SEC-XML-NUL,
  RUN-DURABLE-JSONFILE, SEC-NO-PROXY, LOOP-SPLIT-TICK; 3: LOOP-TESTS-CARVE,
  PLAY-TD-02-SLOTS, AUTO-03, LOOP-LEDGERS, LOOP-PREFLIGHT-CMD.
- Gate: SEC-NO-DISCOVERY merges first and alone, its whole suite run after
  its own Settled bullet is applied; then per package: its named tests as a
  file-named run (timing files and any subset over 90 s and the fixed-port
  files through the suite gate); main-checkout acts one at a time in merge
  order; per merge batch of 5 on the integration worktree: merge, then the
  integrator's edits for the batch as one commit, then python
  ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python -m pytest -q
  and npm test --prefix app, green, then main moves; then python
  tools/plan_check.py check; the wave closes when every session row is
  flipped and main is clean.

- SEC-NO-DISCOVERY [session, L 75m, build, P0] A pointed, test or demo core never looks for the live Client.txt. Files: server/al/core.py, server/al/logfile.py, server/al/diag.py, tests/conftest.py, tests/test_e2e_replay.py (+4 more). Deps: none.
- SEC-STATIC-MAP [session, L 90m, build, P0] Serve /web/ from a fixed name map (closes the UNC path leak) + Refuse cross-site requests on every route; trim unused allowances. Files: server/al/http.py, tests/test_http_security.py, server/al/static.py. Deps: none.
- SEC-XML-NUL [session, S 25m, build, P0] Strict build XML intake: refuse an inflated payload holding a NUL byte. Files: server/al/theorycraft/codec.py, server/al/theorycraft/model.py, tests/test_tc_code.py, tests/test_tc_code_api.py. Deps: none.
- RUN-DURABLE-JSONFILE [session, M 60m, build, P0] Hardened write path in jsonfile (temp name, fsync, retry, .bak, Saver). Files: server/al/jsonfile.py, tests/test_jsonfile.py. Deps: none.
- SEC-NO-PROXY [session, M 40m, build, P0] Loopback calls never use a proxy. Files: server/al/keepalive.py, scripts/run.ps1, tests/test_keepalive.py, tests/test_run_health_ps.py. Deps: none.
- LOOP-SPLIT-TICK [session, L 90m, build] Split Tick review and work-list methods out of al_loop.py (no behaviour change). Files: tools/al_loop.py, tests/test_loop_split.py, tools/loop_review.py, tools/loop_work.py. Deps: none.
- LOOP-TESTS-CARVE [session, M 45m, build] Carve the loop tests that later packages rewrite into four owner files. Files: tests/test_al_loop.py, tests/test_loop_handoff.py, tests/test_loop_dive.py, tests/test_loop_flip.py, tests/test_loop_plandeps.py. Deps: none.
- PLAY-TD-02-SLOTS [session, L 80m, build, DR] Slot tables: pure priority and eviction functions for Play and the overlay. Files: web/slots.js, app/test/slots.test.js. Deps: none.
- AUTO-03 [session, L 80m, build, P1] ROW-FILES tool: tools/roadmap.py with rows, lint, new and done. Files: tools/roadmap.py, tests/test_roadmap_rows.py, tests/test_roadmap_shape.py. Deps: none.
- LOOP-LEDGERS [session, S 25m, build, P1] FS-LEDGERS: union merge for one-line ledgers and a ledger shape test. Files: .gitattributes, tests/test_ledger_files.py. Deps: none.
- LOOP-PREFLIGHT-CMD [session, M 55m, build, P1] Loop preflight command: gates once on unchanged main, hand-off count. Files: tools/loop_preflight.py, tests/test_loop_preflight.py. Deps: none.
- GP-01 [session, S 25m, review, P0] Arm the set-name needles and re-run every scan. Files: none (an act or a read-back). Deps: none.
- GP-03 [session, S 20m, build, P0] NOTICE as a public file and the licence record. Files: NOTICE, docs/decisions/0047-licence-and-notice.md. Deps: none.
- RUN-LIVE-CLICKS-STRIKE [session, S 10m, review, P0] Strike the tool-click unblock path from TEST-LIVE-CLICKS. Files: none (an act or a read-back). Deps: none.
- DATA-GGG-APPLICATION [session, M 45m, review, P2] Prepare the GGG OAuth application note and its decision. Files: docs/decisions/0004-scope-theorycraft.md, docs/ops/ggg-oauth-application.md, docs/decisions/0048-ggg-oauth-client.md. Deps: none.

### Wave 2: loop and watchers, local security, reliability and observability

Goal: The second step of the foundations: the loop session-line fix, the
demo-mode core, the fresh-clone proof and the item card seam. Milestones:
the local HTTP surface is pinned by one test file. Leads: Item card parts
registry (server side seam); Demo mode core: an isolated instance on a
fixture folder; LOOP-PREFLIGHT core: session line, dry run past HALT, tick
step seam.

- Session 1; width 12 worktree + 3 main-checkout, 0 loop rows released;
  about 119 minutes.
- Hotspots: web/index.html (PLAY-TD-09A-REGION-HOOK); server/al/core.py
  (TC-CARD-PARTS); web/app.js (PLAY-TD-09A-REGION-HOOK); server/al/http.py
  (SEC-CEIL-HTTP); server/al/state.py (TC-CARD-PARTS);
  tests/test_security_surface.py (SEC-SURFACE-PIN); server/al/zoneguide.py
  (RUN-DURABLE-STORE-FILES).
- Integrator: ROADMAP.md rows of all 15 packages; CLAUDE.md: SEC-DEMO-CORE,
  AUTO-04, LOOP-HANDOFF-PREFIX, RUN-DURABLE-STORE-FILES;
  docs/decisions/README.md: SEC-DEMO-CORE, AUTO-04; AL-NEXT-SESSION.txt:
  AUTO-01, LOOP-HANDOFF-PREFIX; docs/design/reviews.log: 2 lines.
- Batches: 1: TC-CARD-PARTS, SEC-DEMO-CORE, AUTO-01, AUTO-04; 2:
  LOOP-ROWFILES-MERGE, LOOP-HANDOFF-PREFIX, AUTO-02, SEC-SURFACE-PIN; 3:
  RUN-DURABLE-STORE-FILES, RUN-TAIL-HEAL-READER, PLAY-TD-09A-REGION-HOOK,
  SEC-CEIL-HTTP.
- Gate: per package: its named tests as a file-named run (timing files and
  any subset over 90 s and the fixed-port files through the suite gate);
  main-checkout acts one at a time in merge order; per merge batch of 4 on
  the integration worktree: merge, then the integrator's edits for the batch
  as one commit, then python ops/fleet_kit/fleet_suite_gate.py run --owner
  <id> -- python -m pytest -q and npm test --prefix app, green, then main
  moves; then python tools/plan_check.py check; the wave closes when every
  session row is flipped and main is clean.

- TC-CARD-PARTS [session, L 75m, build, P1, DR] Item card parts registry (server side seam). Files: server/al/state.py, server/al/theorycraft/live.py, server/al/core.py, tests/test_eval_text.py, server/al/theorycraft/cardparts/__init__.py (+1 more). Deps: none.
- SEC-DEMO-CORE [session, L 80m, build, P1] Demo mode core: an isolated instance on a fixture folder. Files: server/al/paths.py, server/al/ports.py, server/al/demo.py, tests/test_demo_mode.py, docs/decisions/0049-demo-mode.md (+1 more). Deps: SEC-NO-DISCOVERY.
- AUTO-01 [session, L 75m, build, P1] LOOP-PREFLIGHT core: session line, dry run past HALT, tick step seam. Files: tools/al_loop.py, tools/loop_steps/__init__.py, tools/loop_steps/docs_watch.py, tools/loop_steps/tc_drift.py, tests/test_loop_steps.py. Deps: LOOP-SPLIT-TICK.
- AUTO-04 [session, L 75m, build, P3] DIVE-FLOOR: dives lose free web tools and read GGG only at the two docs pages. Files: tools/loop_prompts.py, tools/loop_base.py, tests/test_loop_dive.py, tests/test_p163_lane_tools.py, docs/ops/1.0-launch-runbook.md (+4 more). Deps: LOOP-TESTS-CARVE.
- LOOP-ROWFILES-MERGE [session, M 60m, build, P1] The loop merge closes a row with a done file, not a ROADMAP.md edit. Files: tools/loop_merge.py, tests/test_loop_flip.py. Deps: LOOP-TESTS-CARVE, AUTO-03.
- LOOP-HANDOFF-PREFIX [session, M 40m, build, P1] Hand-off bullets are loop work only with a LOOP: prefix. Files: tools/loop_roadmap.py, tests/test_loop_handoff.py. Deps: LOOP-TESTS-CARVE, LOOP-PREFLIGHT-CMD.
- AUTO-02 [session, M 60m, build, P1] ROADMAP-PRUNE: tools/roadmap_fold.py with prune and fold, first prune run. Files: tests/test_desktop_client.py, tools/roadmap_fold.py, tests/test_roadmap_fold.py. Deps: none.
- SEC-SURFACE-PIN [session, M 45m, build, P0] One test file that pins the local HTTP surface. Files: tests/test_security_surface.py. Deps: SEC-NO-DISCOVERY, SEC-STATIC-MAP, SEC-XML-NUL.
- RUN-DURABLE-STORE-FILES [session, M 50m, build, P0] Store modules save with one .bak and clear it with the data. Files: server/al/runhistory.py, server/al/mapladder.py, server/al/pricewatch.py, server/al/summary.py, server/al/hints.py (+4 more). Deps: RUN-DURABLE-JSONFILE.
- RUN-TAIL-HEAL-READER [session, M 60m, build, P0] Tailer never dies and never replays a backlog (logfile.py). Files: server/al/logfile.py, tests/test_tailer.py. Deps: SEC-NO-DISCOVERY.
- PLAY-TD-09A-REGION-HOOK [session, L 75m, build, P1, DR] Region hook: one registry, pre-linked region files. Files: web/index.html, web/app.js, web/regions.js, app/test/regions.test.js, web/strip.js (+17 more). Deps: PLAY-TD-02-SLOTS.
- SEC-CEIL-HTTP [session, S 30m, build, P3] Ceiling on handler threads. Files: server/al/http.py, tests/test_http_ceilings.py. Deps: none.
- AUTO-25 [session, S 25m, review, P3] KIT-REPORT: draft the one note for the fleet owner. Files: none (an act or a read-back). Deps: none.
- DATA-PRICE-FALLBACK-RUNBOOK [session, S 25m, review, P3] Write down the price source fallback order. Files: docs/ops/price-fallback-runbook.md. Deps: none.
- LOOP-DECISION-TIDY [session, S 25m, review, P3] Housekeeping: stale 'Open (UNVERIFIED)' entries and the duplicate pin log. Files: docs/decisions/0013-web-data.md, docs/decisions/0015-price-check-and-contact.md, docs/decisions/0004-scope-theorycraft.md. Deps: none.

### Wave 3: loop and watchers, tests and code seams, theorycraft

Goal: Demo mode is complete; the HTTP surface is pinned; the gate output
keeps its tail. Milestones: the isolated demo mode exists (python -m
server.al --demo). Leads: Demo mode entry: python -m server.al --demo
<fixture dir>; Pin the pytest plugin set; register markers; keep the end of
the gate output; A failed item is parked visibly; a foreign gate failure
ends the fix rounds.

- Session 1; width 12 worktree + 0 main-checkout, 0 loop rows released;
  about 149 minutes.
- Hotspots: web/index.html (TC-CARD-PARTS-WEB); server/al/core.py
  (TC-PRESS-BUILD); web/app.js (TC-CARD-PARTS-WEB); server/al/http.py
  (TC-PRESS-BUILD); server/al/state.py (OVL-HIDEOUT-AREA);
  server/al/__main__.py (SEC-DEMO-ENTRY); server/al/ninja.py
  (DATA-LEAGUE-IDENTITY); server/al/pricebook.py (DATA-LEAGUE-IDENTITY).
- Integrator: ROADMAP.md rows of all 12 packages; CLAUDE.md: TC-PRESS-BUILD;
  docs/design/reviews.log: 2 lines.
- Batches: 1: SEC-DEMO-ENTRY, TEST-PLUGIN-PIN, LOOP-FAILED-PARK,
  LOOP-ROWFILES-WORK; 2: LOOP-DONE-FOLD, TEST-LAYOUT-GUARD,
  TC-CARD-PARTS-WEB, DATA-LEAGUE-IDENTITY; 3: PLAY-TD-01A-PLAY-STATES,
  TC-PRESS-BUILD, OVL-HIDEOUT-AREA; 4: GP-04.
- Gate: per package: its named tests as a file-named run (timing files and
  any subset over 90 s and the fixed-port files through the suite gate);
  main-checkout acts one at a time in merge order; per merge batch of 4 on
  the integration worktree: merge, then the integrator's edits for the batch
  as one commit, then python ops/fleet_kit/fleet_suite_gate.py run --owner
  <id> -- python -m pytest -q and npm test --prefix app, green, then main
  moves; then python tools/plan_check.py check; the wave closes when every
  session row is flipped and main is clean; GP-04 merges last, rebased on
  main after the other batches, as a batch of one.

- SEC-DEMO-ENTRY [session, M 45m, build, P1] Demo mode entry: python -m server.al --demo <fixture dir>. Files: server/al/__main__.py, tests/fixtures/demo/Client.txt, tests/fixtures/demo/ashlight-demo.json, tests/test_demo_entry.py. Deps: SEC-DEMO-CORE.
- TEST-PLUGIN-PIN [session, M 30m, build, P1] Pin the pytest plugin set; register markers; keep the end of the gate output. Files: pytest.ini, tools/al_loop.py, tools/loop_merge.py, tests/test_al_loop_gate_cache.py, tests/test_pytest_config.py. Deps: none.
- LOOP-FAILED-PARK [session, L 75m, build, P1] A failed item is parked visibly; a foreign gate failure ends the fix rounds. Files: tools/loop_review.py, tools/loop_base.py, tools/loop_inbox.py, tools/loop_gatefail.py, tools/loop_steps/failed_supersede.py (+1 more). Deps: LOOP-SPLIT-TICK, AUTO-01, AUTO-04.
- LOOP-ROWFILES-WORK [session, L 75m, build, P1] The loop work list reads rows through the loader: DEPENDS and exact-id briefs. Files: tools/loop_work.py, tools/loop_roadmap.py, tests/test_loop_plandeps.py, tests/al_loopkit.py, tests/test_loop_rowfiles.py. Deps: LOOP-SPLIT-TICK, LOOP-TESTS-CARVE, AUTO-03, LOOP-HANDOFF-PREFIX, LOOP-ROWFILES-MERGE.
- LOOP-DONE-FOLD [session, M 35m, build, P1] /done folds row files and prunes done rows; the fold round trip is tested. Files: .claude/commands/done.md, tests/test_roadmap_fold_e2e.py. Deps: AUTO-02, AUTO-03, LOOP-HANDOFF-PREFIX.
- TEST-LAYOUT-GUARD [session, S 25m, build, P2] Guard test for test naming and test-to-test imports. Files: tests/test_test_layout.py. Deps: none.
- TC-CARD-PARTS-WEB [session, L 90m, build, P1, DR] Dashboard renders card notes, word and tone from the core + Recover a refused share link in two clicks. Files: web/tc.js, web/app.js, web/index.html, app/test/tc_view.test.js. Deps: TC-CARD-PARTS.
- DATA-LEAGUE-IDENTITY [session, M 60m, build, P1] League identity for launch day: id and name, conditional league GET. Files: server/al/ninja.py, server/al/pricebook.py, docs/ops/1.0-launch-runbook.md, tests/test_price_book.py, tests/test_util_10_ready.py (+2 more). Deps: none.
- PLAY-TD-01A-PLAY-STATES [session, L 75m, build, P1] Play state recipes and the long-string fixture. Files: tests/play_states.py, tests/test_play_states.py. Deps: SEC-NO-DISCOVERY.
- TC-PRESS-BUILD [session, L 75m, build, P1, DR] The item key loads a copied build. Files: server/al/core.py, server/al/http.py, server/al/theorycraft/store.py, app/eval_hotkey.js, app/test/eval.test.js (+4 more). Deps: TC-CARD-PARTS.
- OVL-HIDEOUT-AREA [session, M 35m, build, P2] in_hideout from the area id of the generation line, not an English scene-name substring. Files: server/al/parser.py, server/al/state.py, tests/test_parser.py, tests/test_bus_state.py. Deps: none.
- GP-04 [session, M 60m, build, P0] Fresh-clone proof of the suite. Files: none (an act or a read-back). Deps: SEC-NO-DISCOVERY.

### Wave 4: go-public, Play tab and dashboard, theorycraft

Goal: Leads: Record the go-public decision and the rules text; Guarded
pre-push hook and its tests; Replace the local-only wording in loop tools
and ritual files.

- Session 2; width 14 worktree + 1 main-checkout, 0 loop rows released;
  about 139 minutes.
- Hotspots: web/index.html (TC-FILTER-ONE-CONTROL); server/al/core.py
  (SEC-ACL-APPLY); server/al/http.py (SEC-HELLO-CORE); server/al/state.py
  (DATA-PRICE-CARD-TEXT); web/app.css (PLAY-TD-03-TOKENS); server/al/diag.py
  (PLAY-F-131-STATUS-TABLE); tests/test_ux_review.py (PLAY-TD-03-TOKENS);
  app/main.js (OVL-MAIN-PARTS); tests/test_security_surface.py
  (SEC-HELLO-CORE); server/al/__main__.py (SEC-ACL-APPLY);
  app/client/window.js (OVL-MAIN-PARTS); server/al/keepalive.py
  (SEC-HELLO-CORE); tests/test_diag_self.py (PLAY-F-131-STATUS-TABLE);
  app/shared/render_gate.js (PLAY-F-131-STATUS-TABLE);
  docs/design/0001-design-system.md (PLAY-TD-03-TOKENS);
  tests/test_keepalive.py (SEC-HELLO-CORE); server/al/ninja.py
  (TC-FILTER-ONE-CONTROL).
- Integrator: ROADMAP.md rows of all 15 packages; CLAUDE.md: PUB-GO-DECISION,
  PUB-LOCAL-ONLY-TEXT, SEC-ACL-APPLY, TC-WORN-STORE, OVL-MAIN-PARTS,
  SEC-HELLO-CORE; docs/decisions/README.md: PUB-GO-DECISION, SEC-ACL-APPLY,
  TC-WORN-STORE, OVL-MAIN-PARTS, SEC-HELLO-CORE; AL-NEXT-SESSION.txt:
  PUB-GO-DECISION, PLAY-TD-03-TOKENS; docs/design/reviews.log: 5 lines.
- Watch: tests/test_fleet_kit_conformance.py (GP-02 edits, PUB-GO-DECISION
  runs); tests/test_fleet_kit_conformance.py (GP-02 edits,
  PUB-LOCAL-ONLY-TEXT runs); tests/test_diag_self.py
  (PLAY-F-131-STATUS-TABLE edits, OVL-MAIN-PARTS runs).
- Batches: 1: GP-02, PUB-LOCAL-ONLY-TEXT, LOOP-WAVE-HOLD, SEC-ACL-APPLY; 2:
  GP-05, DATA-PRICE-CARD-TEXT, PLAY-F-131-STATUS-TABLE,
  PLAY-TD-01B-FIT-HARNESS; 3: PLAY-TD-03-TOKENS, TC-PRESS-STAGED-EVAL,
  TC-WORN-STORE, OVL-MAIN-PARTS; 4: SEC-HELLO-CORE, TC-FILTER-ONE-CONTROL.
- Gate: per package: its named tests as a file-named run (timing files and
  any subset over 90 s and the fixed-port files through the suite gate);
  main-checkout acts one at a time in merge order; per merge batch of 4 on
  the integration worktree: merge, then the integrator's edits for the batch
  as one commit, then python ops/fleet_kit/fleet_suite_gate.py run --owner
  <id> -- python -m pytest -q and npm test --prefix app, green, then main
  moves; then python tools/plan_check.py check; the wave closes when every
  session row is flipped and main is clean.

- PUB-GO-DECISION [session, S 25m, build, P0] Record the go-public decision and the rules text. Files: docs/decisions/0046-go-public.md. Deps: none.
- GP-02 [session, L 75m, build, P0] Guarded pre-push hook and its tests. Files: .githooks/pre-push, tests/test_fleet_kit_conformance.py, tests/test_pre_push_hook.py. Deps: none.
- PUB-LOCAL-ONLY-TEXT [session, M 45m, build, P0] Replace the local-only wording in loop tools and ritual files. Files: tools/al_loop.py, tools/loop_inbox.py, tools/al_lane.py, tests/test_p163_lane_tools.py, .claude/commands/done.md (+2 more). Deps: none.
- LOOP-WAVE-HOLD [session, M 55m, build, P1] Wave folder hold and the shared merge lock. Files: tools/loop_merge.py, tools/loop_base.py, tools/loop_review.py, tests/test_loop_wave_hold.py. Deps: LOOP-ROWFILES-MERGE, LOOP-FAILED-PARK.
- SEC-ACL-APPLY [session, L 70m, build, P0] Private runtime files: explicit ACL on the runtime dir and local config. Files: server/al/__main__.py, server/al/core.py, server/al/acl.py, tests/test_acl.py, docs/decisions/0051-private-runtime-files.md. Deps: SEC-NO-DISCOVERY.
- GP-05 [session, M 60m, build, P0] CI workflows and their lint test. Files: .gitattributes, .github/workflows/ci.yml, .github/workflows/fleet-identity-guard.yml, requirements-dev.txt, tests/test_ci_workflow.py. Deps: GP-04.
- DATA-PRICE-CARD-TEXT [session, L 75m, build, P1, DR] Price card words: cache age, league after a change, contact copy + One card per trade request: a repeated whisper refreshes its card. Files: server/al/state.py, server/al/price.py, docs/decisions/0016-price-ui-contract.md, tests/test_price_text.py, tests/test_price_card_age.py (+1 more). Deps: DATA-LEAGUE-IDENTITY.
- PLAY-F-131-STATUS-TABLE [session, M 60m, build, P2, DR] One status vocabulary table for the bar, the overlay, Checks and the strip. Files: web/status.js, app/shared/render_gate.js, server/al/diag.py, app/test/dashboard.test.js, app/test/shared.test.js (+5 more). Deps: none.
- PLAY-TD-01B-FIT-HARNESS [session, L 90m, build, P1] Fit harness, red first (G1, G2, G4-G7, G9). Files: app/test/cdp/play_fit.mjs, tests/test_play_fit.py, docs/design/play-fit-figures.md, tests/play_fit_pending/g.txt, tests/play_fit_pending/c-zone.txt (+9 more). Deps: PLAY-TD-01A-PLAY-STATES, SEC-DEMO-ENTRY.
- PLAY-TD-03-TOKENS [session, L 85m, build, P1, DR] Type, spacing, scale and control-edge tokens. Files: web/app.css, tests/test_ux_review.py, docs/design/0001-design-system.md, tests/test_design_tokens.py. Deps: none.
- TC-PRESS-STAGED-EVAL [session, M 60m, build, P1] evaluate() in all-or-nothing stages. Files: server/al/theorycraft/evaluate.py, tests/test_tc_stages.py. Deps: none.
- TC-WORN-STORE [session, M 60m, build, P1] Worn-gear store and baseline. Files: server/al/theorycraft/worngear.py, tests/test_tc_worn_gear.py, docs/decisions/0052-tc-worn-gear.md. Deps: none.
- OVL-MAIN-PARTS [session, M 60m, build, P1] Main-process parts seam: app/parts/ files loaded by app/parts.js; hotkey registration moves into the first part. Files: app/main.js, app/client/window.js, app/parts.js, app/parts/20-hotkeys.js, app/test/parts.test.js (+1 more). Deps: none.
- SEC-HELLO-CORE [session, L 75m, build, P2, DR] Core hello handshake: GET /api/hello and the supervisor check. Files: server/al/http.py, server/al/keepalive.py, tests/test_keepalive.py, tests/test_security_surface.py, server/al/hello.py (+2 more). Deps: SEC-STATIC-MAP, SEC-NO-PROXY, SEC-SURFACE-PIN.
- TC-FILTER-ONE-CONTROL [session, M 45m, build, P3, DR] One filter control, stamped. Files: web/index.html, web/filtermerge.js, server/al/theorycraft/lootfilter.py, server/al/ninja.py, tests/test_lootfilter.py (+2 more). Deps: TC-CARD-PARTS-WEB.

### Wave 5: Play tab and dashboard, reliability and observability, overlay and client

Goal: Milestones: the Play skeleton (7 fixed regions) is on the page; the
private repository exists and the first push is green. Leads:
WAVE-INTERPLAY: BLOCKED reason echo and the dispatch re-check from HEAD;
Plug-in folder: ticks, Checks rows and token-gated routes without
shared-file edits; setup.ps1 makes the sidecar private; the logon launcher
starts PowerShell by its System....

- Session 2; width 12 worktree + 1 main-checkout, 0 loop rows released;
  about 179 minutes.
- Hotspots: web/index.html (PLAY-TD-09B-SKELETON); server/al/core.py
  (RUN-SEAMS); web/app.js (PLAY-TD-09B-SKELETON); server/al/http.py
  (RUN-SEAMS); server/al/state.py (PLAY-TD-07A-PLAY-VIEW); web/app.css
  (PLAY-TD-09B-SKELETON); server/al/diag.py (RUN-SEAMS);
  tests/test_ux_review.py (PLAY-TD-09B-SKELETON); app/main.js
  (PLAY-TD-04A-DARK-CLIENT); tests/test_security_surface.py (RUN-SEAMS);
  server/al/__main__.py (RUN-SEAMS); app/client/window.js
  (PLAY-TD-04A-DARK-CLIENT); tests/test_ux_b8.py (PLAY-TD-09B-SKELETON);
  scripts/setup.ps1 (SEC-ACL-SETUP); docs/design/0001-design-system.md
  (OVL-GLANCE-RULES); tests/test_a11y.py (PLAY-TD-09B-SKELETON);
  tests/test_keepalive.py (TEST-PORT-LEASE); app/test/tabs.test.js
  (PLAY-TD-09B-SKELETON).
- Integrator: ROADMAP.md rows of all 13 packages; CLAUDE.md: AUTO-06,
  RUN-SEAMS, TC-CAMPAIGN-KEEP, OVL-KEYS-CLIENT; docs/decisions/README.md:
  AUTO-06, RUN-SEAMS, TC-CAMPAIGN-KEEP, OVL-KEYS-CLIENT;
  AL-NEXT-SESSION.txt: GP-09; docs/design/reviews.log: 6 lines.
- Batches: 1: AUTO-06, RUN-SEAMS, SEC-ACL-SETUP, TEST-PORT-LEASE; 2:
  PLAY-TD-07A-PLAY-VIEW, PLAY-TD-09B-SKELETON, TC-CAMPAIGN-KEEP,
  RUN-LEDGER-CORE; 3: OVL-KEYS-CLIENT, PLAY-TD-19A-PAGER, OVL-GLANCE-RULES,
  PLAY-TD-04A-DARK-CLIENT.
- Gate: per package: its named tests as a file-named run (timing files and any
  subset over 90 s and the fixed-port files through the suite gate);
  main-checkout acts one at a time in merge order; per merge batch of 4 on the
  integration worktree: merge, then the integrator's edits for the batch as
  one commit, then python ops/fleet_kit/fleet_suite_gate.py run --owner <id>
  -- python -m pytest -q and npm test --prefix app, green, then main moves;
  then python tools/plan_check.py check; the wave closes when every session
  row is flipped and main is clean; GP-09 runs alone after the last batch is
  on main: from its gate 3 to its read-back no merge, integrator commit, batch
  suite, revert or other act touches main, and the wave closes only after its
  read-back or its DEFERRED line (ruling R1, 2026-11-18).

- AUTO-06 [session, M 50m, build, P1] WAVE-INTERPLAY: BLOCKED reason echo and the dispatch re-check from HEAD. Files: tools/loop_work.py, tests/test_loop_wave.py, docs/decisions/0055-loop-and-wave-contract.md. Deps: LOOP-ROWFILES-WORK, LOOP-WAVE-HOLD, AUTO-01.
- RUN-SEAMS [session, M 60m, build, P2] Plug-in folder: ticks, Checks rows and token-gated routes without shared-file edits. Files: server/al/core.py, server/al/__main__.py, server/al/diag.py, server/al/http.py, tests/test_security_surface.py (+3 more). Deps: SEC-SURFACE-PIN, SEC-NO-DISCOVERY.
- SEC-ACL-SETUP [session, M 40m, build, P0] setup.ps1 makes the sidecar private; the logon launcher starts PowerShell by its System32 path. Files: scripts/setup.ps1, scripts/autostart_launch.vbs, tests/test_autostart.py, tests/test_launcher_paths.py. Deps: SEC-ACL-APPLY.
- TEST-PORT-LEASE [session, M 50m, build, P1] Port lease for tests that bind a port (leases 8962-8969). Files: tests/tc_live_util.py, tests/test_keepalive.py, tests/test_procs.py, tests/test_supervisor.py, tests/test_dash_console.py (+3 more). Deps: SEC-DEMO-CORE.
- PLAY-TD-07A-PLAY-VIEW [session, L 90m, build, DR] Play view: capped strings for strip, feed, notices and build line. Files: server/al/state.py, server/al/playview.py, tests/test_play_view.py. Deps: PLAY-F-131-STATUS-TABLE, DATA-PRICE-CARD-TEXT, PLAY-TD-01A-PLAY-STATES.
- PLAY-TD-09B-SKELETON [session, L 80m, build, P1, DR] Play skeleton: 7 fixed regions on the cockpit grid. Files: web/index.html, web/app.css, web/app.js, tests/test_a11y.py, tests/test_ux_review.py (+2 more). Deps: PLAY-TD-09A-REGION-HOOK, PLAY-TD-03-TOKENS, PLAY-TD-01B-FIT-HARNESS.
- TC-CAMPAIGN-KEEP [session, L 75m, build, P1, DR] Keep-or-vendor verdict with no build loaded. Files: tests/test_eval_text.py, tests/test_price_text.py, server/al/theorycraft/levelrules.py, server/al/data/level_rules.json, server/al/theorycraft/cardparts/keep.py (+2 more). Deps: TC-CARD-PARTS.
- RUN-LEDGER-CORE [session, L 90m, build, P1] Parse ledger module: hit counts and masked shapes (logshapes.py). Files: server/al/parser.py, tests/test_parser.py, server/al/logshapes.py, tests/test_logshapes.py. Deps: SEC-NO-DISCOVERY.
- OVL-KEYS-CLIENT [session, M 60m, build, P1] Hotkeys in the client: re-register on a config change, fall back from a taken key, write ops/runtime/hotkeys.json. Files: app/parts/20-hotkeys.js, app/hotkey.js, app/test/hotkey_cases.json, app/test/hotkey.test.js, app/test/hotkeys_live.test.js (+1 more). Deps: OVL-MAIN-PARTS.
- PLAY-TD-19A-PAGER [session, M 50m, build, P1, DR] Pager: list pages and the Full text page. Files: web/pager.js, app/test/pager.test.js. Deps: PLAY-TD-09A-REGION-HOOK.
- OVL-GLANCE-RULES [session, M 40m, build, P2, DR] Glance budget and notification policy in design 0001, held by tests. Files: docs/design/0001-design-system.md, tests/test_glance_rules.py. Deps: none.
- PLAY-TD-04A-DARK-CLIENT [session, S 25m, build, P2, DR] Dark by default in the desktop client. Files: app/main.js, app/client/window.js, app/client/starting.css, app/test/theme.test.js. Deps: none.
- GP-09 [session, M 50m, build, P0] Create the private repository, first push, CI green. Files: none (an act or a read-back). Deps: GP-01, GP-02, PUB-GO-DECISION, PUB-LOCAL-ONLY-TEXT, GP-03, GP-04, GP-05.

### Wave 6: Play tab and dashboard, local security, reliability and observability

Goal: Milestones: HALT is removed; the headless loop takes the loop-owned
rows. Leads: Checks note when AshLight's folders let someone else write;
Move the five CRLF / hand-rolled writers onto the jsonfile helper; Play
view: context modes, item card and kept checks.

- Session 2; width 12 worktree + 1 main-checkout, 0 loop rows released;
  about 129 minutes.
- Hotspots: web/index.html (PLAY-TD-09C-BAR); server/al/core.py
  (SEC-ACL-CHECK); web/app.js (PLAY-TD-09C-BAR); server/al/http.py
  (SEC-SSE-TAP); server/al/state.py (SEC-SSE-TAP); web/app.css
  (PLAY-TD-09C-BAR); server/al/diag.py (SEC-ACL-CHECK);
  tests/test_security_surface.py (RUN-VERDICTS-CORE); server/al/__main__.py
  (RUN-DURABLE-CRLF); scripts/run.ps1 (DEP-02); server/al/keepalive.py
  (RUN-DURABLE-CRLF); tests/test_diag_self.py (SEC-ACL-CHECK); README.md
  (DEP-02); tests/test_ux_b8.py (PLAY-TD-09C-BAR); scripts/setup.ps1
  (DEP-02); tests/test_a11y.py (PLAY-TD-09C-BAR);
  tests/test_http_security.py (SEC-SSE-TAP); tests/test_ux_settings_io.py
  (OVL-OVERLAY-KEYS).
- Integrator: ROADMAP.md rows of all 13 packages; CLAUDE.md:
  RUN-VERDICTS-CORE; AL-NEXT-SESSION.txt: PLAY-TD-09C-BAR, AUTO-21;
  docs/plan/README.md: AUTO-21; docs/design/reviews.log: 6 lines.
- Batches: 1: SEC-ACL-CHECK, RUN-DURABLE-CRLF, PLAY-TD-07B-PLAY-CARDS,
  PLAY-TD-09C-BAR; 2: PLAY-TD-13-FEED, PLAY-TD-15-BUILDLINE,
  PLAY-TD-14-NOTICE, RUN-VERDICTS-CORE; 3: OVL-OVERLAY-KEYS,
  TEST-STATE-EQUIV, DEP-02, SEC-SSE-TAP.
- Gate: per package: its named tests as a file-named run (timing files and
  any subset over 90 s through the suite gate); main-checkout acts one at a
  time in merge order; per merge batch of 4 on the integration worktree:
  merge, then the integrator's edits for the batch as one commit, then
  python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python -m
  pytest -q and npm test --prefix app, green, then main moves; then python
  tools/plan_check.py check; the wave closes when every session row is
  flipped and main is clean; AUTO-21 runs last: the six checks of F-078,
  then HALT is removed; on a red check HALT stays and AUTO-21 runs again as
  the first act of the next wave.

- SEC-ACL-CHECK [session, M 50m, build, P0] Checks note when AshLight's folders let someone else write. Files: server/al/acl.py, server/al/core.py, server/al/diag.py, tests/test_diag_self.py, tests/test_acl_check.py. Deps: SEC-ACL-APPLY, SEC-NO-DISCOVERY.
- RUN-DURABLE-CRLF [session, S 25m, build, P0] Move the five CRLF / hand-rolled writers onto the jsonfile helper. Files: server/al/__main__.py, server/al/keepalive.py, server/al/procs.py, server/al/hotreload.py, tests/test_durable_lf.py. Deps: RUN-DURABLE-JSONFILE, RUN-SEAMS.
- PLAY-TD-07B-PLAY-CARDS [session, L 90m, build, P1, DR] Play view: context modes, item card and kept checks. Files: server/al/playview.py, server/al/playcards.py, tests/test_play_cards.py. Deps: PLAY-TD-07A-PLAY-VIEW, TC-CARD-PARTS.
- PLAY-TD-09C-BAR [session, L 70m, build, P1, DR] Bar: the mark, the character slot and one status word + MERGE-SEAMS F5 and F7: restart note clears, tool-row class. Files: web/index.html, web/app.css, web/app.js, tests/test_a11y.py, tests/test_ux_b8.py (+2 more). Deps: PLAY-TD-09B-SKELETON, PLAY-F-131-STATUS-TABLE.
- PLAY-TD-13-FEED [session, L 75m, build, P1, DR] Feed T: five one-line rows, trades first. Files: web/feed.js, web/feed.css, tests/play_fit_pending/t.txt, app/test/feed.test.js. Deps: PLAY-TD-09B-SKELETON, PLAY-TD-07A-PLAY-VIEW, PLAY-TD-02-SLOTS.
- PLAY-TD-15-BUILDLINE [session, M 45m, build, P1, DR] Build line B with the Paste a build button. Files: web/buildline.js, web/buildline.css, tests/play_fit_pending/b.txt, app/test/buildline.test.js. Deps: PLAY-TD-09B-SKELETON, PLAY-TD-07A-PLAY-VIEW, PLAY-TD-02-SLOTS.
- PLAY-TD-14-NOTICE [session, M 60m, build, P1, DR] Notice N: one notice at a time. Files: web/notice.js, web/notice.css, tests/play_fit_pending/n.txt, app/test/notice.test.js. Deps: PLAY-TD-09B-SKELETON, PLAY-TD-07A-PLAY-VIEW, PLAY-TD-02-SLOTS.
- RUN-VERDICTS-CORE [session, M 45m, build, P1] Verdict store, token API and read-back script for the 'Tried in game' checks. Files: docs/decisions/0040-self-checks-language-guard.md, tests/test_security_surface.py, server/al/verdicts.py, server/al/plug/verdicts.py, tools/live_verdicts.py (+1 more). Deps: RUN-SEAMS, RUN-DURABLE-JSONFILE.
- OVL-OVERLAY-KEYS [session, M 45m, build, P2, DR] Overlay settings schema: parts switches, quiet town, zone-guide choice in layout.py and layout.js. Files: server/al/layout.py, app/shared/layout.js, tests/test_overlay_layout.py, app/test/layout.test.js, tests/test_ux_settings_io.py. Deps: none.
- TEST-STATE-EQUIV [session, M 60m, build, P2] tools/state_equiv.py and the design gate prefix server/al/text/. Files: tools/design_gate.py, tests/test_design_gate.py, tools/state_equiv.py, tests/test_state_equiv.py. Deps: TEST-LAYOUT-GUARD, LOOP-LEDGERS.
- DEP-02 [session, M 60m, build, P1] The source install works for a stranger. Files: server/al/paths.py, tests/test_sidecar_paths.py, scripts/setup.ps1, scripts/run.ps1, README.md (+3 more). Deps: GP-05, SEC-ACL-APPLY, SEC-ACL-SETUP.
- SEC-SSE-TAP [session, M 55m, build, P2] OBS-SSE-EVENTS: stop sending chat-bearing frames by default. Files: server/al/http.py, server/al/state.py, tests/test_http_security.py, tests/test_fullstack.py, tests/test_e2e_replay.py (+4 more). Deps: SEC-STATIC-MAP, SEC-NO-DISCOVERY.
- AUTO-21 [session, M 45m, review, P1] LOOP-RESUME: remove HALT after the six checks (no later than 2026-12-04). Files: none (an act or a read-back). Deps: AUTO-01, LOOP-HANDOFF-PREFIX, LOOP-PREFLIGHT-CMD, LOOP-FAILED-PARK, AUTO-02, AUTO-03, LOOP-ROWFILES-MERGE, LOOP-ROWFILES-WORK, LOOP-DONE-FOLD, AUTO-04, AUTO-06, LOOP-WAVE-HOLD, TEST-PLUGIN-PIN.

### Wave 7: Play tab and dashboard, tests and code seams, reliability and observability

Goal: Leads: app/test/_web.js: one helper that knows where dashboard sources
live (node side); tests/srcpaths.py: one helper that knows where dashboard
sources live (Python side); Core saves retried from the tick with back-off;
one Checks row while unsaved. Releases 2 loop-owned rows.

- Session 3; width 12 worktree + 1 main-checkout, 2 loop rows released;
  about 141 minutes.
- Hotspots: server/al/core.py (RUN-DURABLE-STORES); server/al/http.py
  (DEP-05); server/al/state.py (TC-VERDICT-CAVEAT); tests/test_ux_review.py
  (TEST-WEB-SRCPATHS-PY); server/al/__main__.py (DEP-05);
  tests/test_ux_b8.py (TEST-WEB-SRCPATHS-PY); app/shared/render_gate.js
  (OVL-PARTS-PAGE); app/test/checks.test.js (TEST-WEB-SRCPATHS-NODE);
  tests/test_a11y.py (TEST-WEB-SRCPATHS-PY); tests/test_keepalive.py
  (TEST-MARKS); app/test/tabs.test.js (TEST-WEB-SRCPATHS-NODE);
  tests/test_http_security.py (TEST-WEB-SRCPATHS-PY);
  app/test/prices.test.js (TEST-WEB-SRCPATHS-NODE); server/al/zoneguide.py
  (PLAY-TD-08A-GUIDE-SHORT-FIELD); tests/test_tc_bridge.py (TEST-MARKS).
- Integrator: ROADMAP.md rows of all 14 packages; CLAUDE.md: DEP-05;
  docs/decisions/README.md: DEP-05; docs/design/reviews.log: 7 lines.
- Watch: tests/test_zone_guide.py (PLAY-TD-08A-GUIDE-SHORT-FIELD edits,
  RUN-DURABLE-STORES runs).
- Batches: 1: TEST-WEB-SRCPATHS-NODE, TEST-WEB-SRCPATHS-PY,
  RUN-DURABLE-STORES, TEST-MARKS; 2: PLAY-TD-11-CONTEXT, PLAY-TD-10-STRIP,
  PLAY-TD-16B-KEPT-CHECKS, PLAY-TD-16A-ITEMCARD; 3: OVL-PARTS-PAGE,
  PLAY-TD-08A-GUIDE-SHORT-FIELD, DEP-05, TC-VERDICT-CAVEAT.
- Gate: per package: its named tests as a file-named run (timing files and
  any subset over 90 s through the suite gate); main-checkout acts one at a
  time in merge order; per merge batch of 4 on the integration worktree:
  merge, then the integrator's edits for the batch as one commit, then
  python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python -m
  pytest -q and npm test --prefix app, green, then main moves; then python
  tools/plan_check.py check; the wave closes when every session row is
  flipped and main is clean.

- TEST-WEB-SRCPATHS-NODE [session, L 70m, build, P2] app/test/_web.js: one helper that knows where dashboard sources live (node side). Files: app/test/about.test.js, app/test/acts.test.js, app/test/audit_tree_url.test.js, app/test/buildlive.test.js, app/test/campaign.test.js (+20 more). Deps: TEST-LAYOUT-GUARD.
- TEST-WEB-SRCPATHS-PY [session, M 45m, build, P2] tests/srcpaths.py: one helper that knows where dashboard sources live (Python side). Files: tests/test_a11y.py, tests/test_brand_assets.py, tests/test_http_security.py, tests/test_lootfilter_merge.py, tests/test_overlay_layout.py (+11 more). Deps: TEST-LAYOUT-GUARD.
- RUN-DURABLE-STORES [session, M 60m, build, P0, DR] Core saves retried from the tick with back-off; one Checks row while unsaved. Files: server/al/core.py, server/al/plug/stores.py, tests/test_durable_stores.py. Deps: RUN-DURABLE-JSONFILE, RUN-SEAMS, RUN-DURABLE-STORE-FILES.
- TEST-MARKS [session, M 60m, build, P1] Mark timing, calc and worker-group tests. Files: tests/test_budgets.py, tests/test_fuzz.py, tests/test_math_perf.py, tests/test_soak.py, tests/test_math_e2e_live.py (+11 more). Deps: TEST-PORT-LEASE, TEST-PLUGIN-PIN.
- PLAY-TD-11-CONTEXT [session, L 85m, build, P1, DR] Context C: guide, town, map and none modes. Files: web/context.js, web/context.css, tests/play_fit_pending/c-zone.txt, app/test/context.test.js. Deps: PLAY-TD-09B-SKELETON, PLAY-TD-07B-PLAY-CARDS, PLAY-TD-02-SLOTS.
- PLAY-TD-10-STRIP [session, M 60m, build, P2, DR] Strip G, the bar words and the stale look. Files: web/strip.js, web/strip.css, tests/play_fit_pending/g.txt, app/test/strip.test.js. Deps: PLAY-TD-09B-SKELETON, PLAY-TD-07A-PLAY-VIEW, PLAY-F-131-STATUS-TABLE, PLAY-TD-02-SLOTS, PLAY-TD-09C-BAR.
- PLAY-TD-16B-KEPT-CHECKS [session, M 35m, build, P1, DR] Kept checks U: the 3 best checked items. Files: web/keptchecks.js, web/keptchecks.css, tests/play_fit_pending/u.txt, app/test/keptchecks.test.js. Deps: PLAY-TD-09B-SKELETON, PLAY-TD-07B-PLAY-CARDS, PLAY-TD-02-SLOTS.
- PLAY-TD-16A-ITEMCARD [session, L 90m, build, P1, DR] Item card I: verdict first, reserved rows. Files: web/itemcard.js, web/itemcard.css, tests/play_fit_pending/i.txt, app/test/itemcard.test.js. Deps: PLAY-TD-09B-SKELETON, PLAY-TD-07B-PLAY-CARDS, PLAY-TD-02-SLOTS.
- OVL-PARTS-PAGE [session, M 60m, build, P2, DR] Overlay page honours the parts switches: a part that is off drops out, an empty HUD plate is absent. Files: app/shared/render_gate.js, app/overlay/overlay.js, app/test/overlay_parts.test.js. Deps: OVL-OVERLAY-KEYS.
- PLAY-TD-08A-GUIDE-SHORT-FIELD [session, S 25m, build] Zone guide short field: loader, cap and view key. Files: server/al/zoneguide.py, tests/test_zone_guide.py, docs/decisions/0043-zone-guide.md. Deps: none.
- DEP-05 [session, L 80m, build, P1] Installed-mode paths (Python side). Files: server/al/paths.py, server/al/ports.py, server/al/procs.py, server/al/__main__.py, server/al/http.py (+3 more). Deps: DEP-02, RUN-DURABLE-JSONFILE, SEC-DEMO-ENTRY.
- TC-VERDICT-CAVEAT [session, M 50m, build, P1, DR] Build caveat on the verdict; alerts name the item-key press. Files: server/al/state.py, tests/test_eval_text.py, tests/test_build_live.py. Deps: TC-CARD-PARTS, TC-PRESS-BUILD.
- OVL-CLIENT-ZOOM [loop, M 50m, build, P2] Probe and restore zoom in the desktop client. Files: app/client/zoom.js, app/parts/30-zoom.js, app/test/zoom.test.js, app/test/electron/zoom_probe.js, tests/test_client_zoom.py. Deps: OVL-MAIN-PARTS.
- AUTO-23 [loop, M 35m, build, P3] DEV-LEDGERS: rotate the sub-agent ledger, flag a stale docs watch, tidy suite logs. Files: tools/ledger_rotate.py, tests/test_ledger_rotate.py. Deps: none.

### Wave 8: tests and code seams, install and release, reliability and observability

Goal: Leads: web/fmt.js: pad, duration and clock defined once; Core restarts
a dead log reader and the Reading row tells the truth; tools/test_select.py:
the test files for a diff.

- Session 3; width 12 worktree + 0 main-checkout, 0 loop rows released;
  about 131 minutes.
- Hotspots: web/index.html (TEST-WEB-FMT); server/al/core.py
  (RUN-TAIL-HEAL-CORE); web/app.js (TEST-WEB-FMT); server/al/http.py
  (TEST-HTTP-ROUTES); server/al/state.py (RUN-TAIL-HEAL-CORE);
  server/al/diag.py (RUN-TAIL-HEAL-CORE); tests/test_security_surface.py
  (TEST-HTTP-ROUTES); tests/test_diag_self.py (RUN-TAIL-HEAL-CORE).
- Integrator: ROADMAP.md rows of all 12 packages; docs/design/reviews.log: 3
  lines.
- Batches: 1: TEST-WEB-FMT, RUN-TAIL-HEAL-CORE, TEST-SELECT,
  TEST-XDIST-DIAG; 2: PLAY-TD-12-CONTEXT-SETUP, GP-06, DEP-03, DEP-01; 3:
  REL-SUBJECT-CHECK, DATA-WEBFETCH-GZIP, OVL-ELECTRON-PIN, TEST-HTTP-ROUTES.
- Gate: per package: its named tests as a file-named run (timing files and
  any subset over 90 s through the suite gate); main-checkout acts one at a
  time in merge order; per merge batch of 4 on the integration worktree:
  merge, then the integrator's edits for the batch as one commit, then
  python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python -m
  pytest -q and npm test --prefix app, green, then main moves; then python
  tools/plan_check.py check; the wave closes when every session row is
  flipped and main is clean.

- TEST-WEB-FMT [session, M 45m, build, P2, DR] web/fmt.js: pad, duration and clock defined once. Files: web/acts.js, web/app.js, web/history.js, web/runs.js, web/summary.js (+3 more). Deps: TEST-WEB-SRCPATHS-NODE, TEST-WEB-SRCPATHS-PY, LOOP-LEDGERS.
- RUN-TAIL-HEAL-CORE [session, M 60m, build, P0, DR] Core restarts a dead log reader and the Reading row tells the truth. Files: server/al/core.py, server/al/state.py, server/al/diag.py, tests/test_e2e_replay.py, tests/test_diag_self.py (+1 more). Deps: RUN-TAIL-HEAL-READER, RUN-SEAMS, RUN-DURABLE-STORES.
- TEST-SELECT [session, L 80m, build, P1] tools/test_select.py: the test files for a diff. Files: tools/test_select.py, tests/test_test_select.py. Deps: TEST-MARKS.
- TEST-XDIST-DIAG [session, M 60m, review, P2] Three diagnosed parallel suite runs: why the loop's xdist runs went red. Files: docs/research/0049-test-suite-speed.md. Deps: TEST-PLUGIN-PIN, TEST-PORT-LEASE, TEST-MARKS.
- PLAY-TD-12-CONTEXT-SETUP [session, M 60m, build, P1, DR] Context C: setup, error and idle modes. Files: web/setupcard.js, web/setupcard.css, tests/play_fit_pending/c-setup.txt, app/test/setupcard.test.js. Deps: PLAY-TD-11-CONTEXT.
- GP-06 [session, M 40m, build, P1] Community files. Files: CODE_OF_CONDUCT.md, .github/ISSUE_TEMPLATE/bug.yml, .github/ISSUE_TEMPLATE/feature.yml, .github/ISSUE_TEMPLATE/config.yml, .github/pull_request_template.md (+1 more). Deps: none.
- DEP-03 [session, M 45m, build, P1] One version, enforced, and the release tool dispatcher. Files: tools/release.py, tools/rel_version.py, tests/test_version.py. Deps: none.
- DEP-01 [session, M 60m, build, P1] Spike: AshLight under the private runtimes. Files: docs/ops/runtime-spike-record.md. Deps: SEC-DEMO-ENTRY.
- REL-SUBJECT-CHECK [session, M 40m, build, P2] Commit subject check in the commit-msg hook. Files: .githooks/commit-msg, tools/commit_subject.py, tests/test_commit_subject.py, tests/fixtures/commit_subjects_untyped.txt. Deps: none.
- DATA-WEBFETCH-GZIP [session, M 40m, build, P1] webfetch: bounded gzip inflate, HTTPException mapping, Retry-After helper. Files: server/al/webfetch.py, tests/test_fuzz.py, tests/test_webfetch_gzip.py. Deps: none.
- OVL-ELECTRON-PIN [session, M 60m, build, P1] Electron pin: config/electron_pin.json and tools/electron_pin.py (hash-pinned fetch, verify, unpack). Files: config/electron_pin.json, tools/electron_pin.py, tests/test_electron_pin.py. Deps: none.
- TEST-HTTP-ROUTES [session, M 60m, build, P3] HTTP route tables per verb. Files: server/al/http.py, tests/test_security_surface.py, tests/test_routes.py. Deps: SEC-SURFACE-PIN.

### Wave 9: install and release, tests and code seams, overlay and client

Goal: Milestones: the wave gate policy is recorded and the test selector
picks each package's subset. Leads: Publish the item check in stages; Record
the wave gate policy (Q-17) in a decision, the lane prompt and /done;
web/registry.js: ALApp.register and per-panel isolation in render, tick and
start.

- Session 3; width 12 worktree + 0 main-checkout, 0 loop rows released;
  about 136 minutes.
- Hotspots: web/index.html (TEST-WEB-REGISTRY); server/al/core.py
  (TC-PRESS-STAGED-LIVE); web/app.js (TEST-WEB-REGISTRY); server/al/http.py
  (TC-PRESS-STAGED-LIVE); server/al/state.py (RUN-ZONE-RESET); app/main.js
  (OVL-SHELL-GUARDS); app/client/window.js (OVL-LINKS-DOWNLOADS);
  server/al/keepalive.py (DEP-06); app/test/client.test.js
  (OVL-LINKS-DOWNLOADS); scripts/setup.ps1 (DEP-07); server/al/ninja.py
  (DATA-PRICE-POLITE); server/al/pricebook.py (DATA-PRICE-POLITE).
- Integrator: ROADMAP.md rows of all 12 packages; CLAUDE.md:
  TEST-WAVE-GATE-POLICY, TEST-SUITE-RUNNER, OVL-LINKS-DOWNLOADS,
  OVL-SHELL-GUARDS, DEP-04; docs/decisions/README.md: TEST-WAVE-GATE-POLICY,
  OVL-SHELL-GUARDS, DEP-04; docs/design/reviews.log: 4 lines.
- Batches: 1: TC-PRESS-STAGED-LIVE, TEST-WAVE-GATE-POLICY,
  TEST-WEB-REGISTRY, TEST-SUITE-RUNNER; 2: RUN-ZONE-RESET, REL-PINFETCH,
  OVL-LINKS-DOWNLOADS, OVL-SHELL-GUARDS; 3: DEP-04, DEP-06, DEP-07,
  DATA-PRICE-POLITE.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  -m pytest -q and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- TC-PRESS-STAGED-LIVE [session, L 85m, build, P1, DR] Publish the item check in stages. Files: server/al/theorycraft/live.py, server/al/core.py, server/al/http.py, tests/test_math_e2e_live.py, docs/decisions/0024-tc-delta.md (+2 more). Deps: TC-PRESS-STAGED-EVAL, TC-PRESS-BUILD, TC-CARD-PARTS.
- TEST-WAVE-GATE-POLICY [session, M 35m, build, P1] Record the wave gate policy (Q-17) in a decision, the lane prompt and /done. Files: tools/loop_prompts.py, .claude/commands/done.md, docs/decisions/0060-wave-gate-policy.md, tests/test_wave_gate_policy.py. Deps: TEST-SELECT, LOOP-LEDGERS.
- TEST-WEB-REGISTRY [session, M 60m, build, P2, DR] web/registry.js: ALApp.register and per-panel isolation in render, tick and start. Files: web/app.js, web/index.html, web/registry.js, app/test/registry.test.js. Deps: TEST-WEB-FMT.
- TEST-SUITE-RUNNER [session, M 60m, build, P2] tools/suite_run.py: the one whole-suite command, parallel when cleared. Files: docs/decisions/0002-stack.md, requirements-dev.txt, tools/suite_run.py, tests/test_suite_run.py. Deps: TEST-XDIST-DIAG, GP-05.
- RUN-ZONE-RESET [session, L 80m, build, P2, DR] One _enter_zone() clears per-zone state, with a zone generation counter + State text move 1: text/common.py and text/events.py. Files: server/al/state.py, tests/test_bus_state.py, tests/test_resume.py, server/al/text/__init__.py, server/al/text/common.py (+1 more). Deps: RUN-TAIL-HEAL-CORE, TEST-STATE-EQUIV, TC-CARD-PARTS.
- REL-PINFETCH [session, M 45m, build, P1] Move the hash-pinned fetch, verify and extract helpers into one stdlib module. Files: tools/tc_pin.py, server/al/pinfetch.py, tests/test_pinfetch.py. Deps: none.
- OVL-LINKS-DOWNLOADS [session, L 85m, build, P2, DR] Narrow external links and downloads in the companion window + Companion window opens on the second monitor on first run. Files: app/client/link.js, app/client/window.js, web/tc.js, app/test/client.test.js, docs/decisions/0041-desktop-client.md (+2 more). Deps: OVL-MAIN-PARTS.
- OVL-SHELL-GUARDS [session, L 75m, build, P2] Electron shell guards: sandbox for every renderer, default-deny navigation / popups / webview, exact IPC senders, quit on debug switches. Files: app/main.js, app/test/audit_electron.test.js, tests/test_overlay_smoke.py, app/guards.js, app/parts/10-guards.js (+2 more). Deps: OVL-MAIN-PARTS.
- DEP-04 [session, L 75m, build, P2] Notes and changelog generator. Files: tools/rel_notes.py, CHANGELOG.md, docs/releases/0.1.0.md, tests/test_release_notes.py, docs/decisions/0062-changelog.md. Deps: DEP-03, REL-SUBJECT-CHECK, AUTO-01, AUTO-03.
- DEP-06 [session, M 55m, build, P1] Runtime resolvers and one command builder. Files: server/al/paths.py, server/al/keepalive.py, server/al/procs.py, boot.py, tests/test_runtime_layout.py. Deps: DEP-01, DEP-02, DEP-05.
- DEP-07 [session, M 60m, build, P3] Shell integration helper: shortcuts and the uninstall entry in one place. Files: scripts/setup.ps1, tests/test_desktop_client.py, scripts/al_shell.ps1, tests/test_shell_integration.py. Deps: DEP-02, SEC-ACL-SETUP.
- GP-11 [session, S 10m, review, P1] Description, topics and feature switches. Files: none. Deps: GP-09.
- DATA-PRICE-POLITE [session, L 70m, build, P1] poe.ninja client: back off, daily retry of a failing type, spaced requests. Files: server/al/ninja.py, server/al/pricebook.py, tests/test_data_ninja.py, tests/test_price_book.py. Deps: DATA-WEBFETCH-GZIP.

### Wave 10: install and release, overlay and client, tests and code seams

Goal: Milestones: one gate spelling; the whole suite runs in parallel.
Leads: Item check compares against the worn item first; Legacy out 1: old
strip tiles, trade card and build alert slot; One gate spelling in the loop,
gates.txt, build.ps1 and /done; kit crash = retry.

- Session 4; width 12 worktree + 0 main-checkout, 0 loop rows released;
  about 131 minutes.
- Hotspots: web/index.html (PLAY-LEGACY-OUT-1); server/al/core.py
  (OVL-COPY-FIRST); web/app.js (PLAY-LEGACY-OUT-1); server/al/http.py
  (RUN-BUILD-STAMP-CORE); server/al/state.py (OVL-COPY-FIRST); web/app.css
  (PLAY-LEGACY-OUT-1); server/al/diag.py (RUN-BUILD-STAMP-CORE);
  tests/test_ux_review.py (PLAY-LEGACY-OUT-1); app/client/window.js
  (OVL-WAKE-COMPANION); app/test/client.test.js (OVL-WAKE-COMPANION);
  tests/test_a11y.py (PLAY-LEGACY-OUT-1); app/test/tabs.test.js
  (PLAY-LEGACY-OUT-1).
- Integrator: ROADMAP.md rows of all 12 packages; CLAUDE.md:
  TEST-GATE-CALLERS, REL-RUNTIME-PINS, OVL-WAKE-COMPANION, OVL-EGRESS-LOCK,
  DEP-08; docs/decisions/README.md: REL-RUNTIME-PINS, DEP-08;
  docs/design/reviews.log: 4 lines.
- Watch: tests/test_eval_text.py (OVL-COPY-FIRST edits, TC-WORN-BASELINE
  runs).
- Batches: 1: TC-WORN-BASELINE, PLAY-LEGACY-OUT-1, TEST-GATE-CALLERS,
  RUN-BUILD-STAMP-CORE; 2: REL-RUNTIME-PINS, OVL-WAKE-COMPANION,
  OVL-EGRESS-LOCK, TEST-FLOOR-MEMO; 3: RUN-DIAG-DATA-AGE, DEP-08,
  REL-INSTALL-HOME, OVL-COPY-FIRST.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  -m pytest -q and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- TC-WORN-BASELINE [session, M 55m, build, P1, DR] Item check compares against the worn item first. Files: server/al/theorycraft/evaluate.py, server/al/theorycraft/live.py, server/al/theorycraft/cardparts/worn.py, tests/test_tc_worn_baseline.py. Deps: TC-WORN-STORE, TC-PRESS-STAGED-LIVE, TC-PRESS-STAGED-EVAL, TC-CAMPAIGN-KEEP.
- PLAY-LEGACY-OUT-1 [session, L 80m, build, P1, DR] Legacy out 1: old strip tiles, trade card and build alert slot. Files: web/index.html, web/app.css, web/app.js, web/regions.js, web/tabs.js (+12 more). Deps: PLAY-TD-10-STRIP, PLAY-TD-13-FEED, PLAY-TD-15-BUILDLINE, PLAY-TD-16B-KEPT-CHECKS.
- TEST-GATE-CALLERS [session, M 60m, build, P2] One gate spelling in the loop, gates.txt, build.ps1 and /done; kit crash = retry. Files: tools/al_loop.py, tools/loop_base.py, ops/loop/gates.txt, scripts/build.ps1, .claude/commands/done.md (+4 more). Deps: TEST-SUITE-RUNNER, TEST-PLUGIN-PIN, TEST-WAVE-GATE-POLICY.
- RUN-BUILD-STAMP-CORE [session, M 30m, build, P1] buildinfo.py: one build id for health, version and the report header. Files: server/al/http.py, server/al/diag.py, server/al/buildinfo.py, tests/test_buildinfo.py. Deps: RUN-SEAMS, RUN-TAIL-HEAL-CORE.
- REL-RUNTIME-PINS [session, M 55m, build, P1] Runtime pin file and the hash-checked runtime fetch. Files: server/al/pinfetch.py, THIRD-PARTY.md, config/runtime_pins.json, tests/test_runtime_pins.py, docs/decisions/0063-installed-runtimes.md. Deps: DEP-01, REL-PINFETCH, OVL-ELECTRON-PIN.
- OVL-WAKE-COMPANION [session, M 50m, build, P3] Bring the companion back when the game wakes, only on another display. Files: app/client/link.js, app/client/window.js, app/client/tray_menu.js, app/test/client.test.js, app/test/client_controls.test.js (+2 more). Deps: OVL-MAIN-PARTS, OVL-LINKS-DOWNLOADS.
- OVL-EGRESS-LOCK [session, M 45m, build, P2] Egress lock on both Electron sessions; no-network CSP for the icon render page. Files: scripts/brand_render.js, docs/decisions/0061-electron-shell-guards.md, app/egress.js, app/parts/15-egress.js, app/test/egress.test.js. Deps: OVL-SHELL-GUARDS.
- TEST-FLOOR-MEMO [session, M 30m, build, P2] Memoise the static floor scan. Files: tests/test_floor_static.py, tests/test_floor_static_cache.py. Deps: none.
- RUN-DIAG-DATA-AGE [session, M 30m, build, P2, DR] Checks row when the game data is older than the game. Files: server/al/acts.py, server/al/plug/dataage.py, tests/test_diag_data_age.py. Deps: RUN-SEAMS.
- DEP-08 [session, L 80m, build, P1] Release build tool: the app zip, MANIFEST and BUILD. Files: tools/rel_build.py, config/ship_list.json, tests/test_release_tool.py, docs/decisions/0064-release-artifact.md. Deps: DEP-03, DEP-04, DEP-06.
- REL-INSTALL-HOME [session, L 70m, build, P1] Installer package: home, marker and the command table. Files: server/al/install/__init__.py, server/al/install/__main__.py, server/al/install/cli.py, server/al/install/home.py, server/al/install/status.py (+1 more). Deps: DEP-05, RUN-DURABLE-JSONFILE, SEC-ACL-APPLY.
- OVL-COPY-FIRST [session, M 60m, build, P1, DR] Empty clipboard at the item-check press shows a 'Copy the item first' card; one read per press stays under test + On the overlay card the item name. Files: server/al/state.py, server/al/core.py, tests/test_eval_text.py, app/test/eval.test.js, tests/test_price_text.py (+1 more). Deps: none.

### Wave 11: install and release, theorycraft, tests and code seams

Goal: Milestones: the item check compares against worn gear (worn-gear
baseline); the Play tab never scrolls (legacy cards are gone). Leads: 'I
wear this' endpoint, worn-gear switch and clear; Legacy out 2: consent,
guide, tip, language and item cards leave Play; Calc opt-in in one act
(setup switch). Releases 1 loop-owned rows.

- Session 4; width 12 worktree + 0 main-checkout, 1 loop rows released;
  about 125 minutes.
- Hotspots: web/index.html (PLAY-LEGACY-OUT-2); server/al/core.py
  (TC-WORN-WIRE); web/app.js (PLAY-LEGACY-OUT-2); server/al/http.py
  (TC-WORN-WIRE); server/al/state.py (TEST-STATE-TEXT-2); web/app.css
  (PLAY-LEGACY-OUT-2); server/al/diag.py (TC-CALC-OPTIN);
  tests/test_ux_review.py (PLAY-LEGACY-OUT-2);
  tests/test_security_surface.py (TC-WORN-WIRE); tests/test_diag_self.py
  (TC-CALC-OPTIN); tests/test_ux_b8.py (PLAY-LEGACY-OUT-2);
  scripts/setup.ps1 (TC-CALC-OPTIN); app/test/checks.test.js
  (PLAY-LEGACY-OUT-2); tests/test_a11y.py (PLAY-LEGACY-OUT-2); web/checks.js
  (PLAY-LEGACY-OUT-2); app/test/tabs.test.js (PLAY-LEGACY-OUT-2);
  server/al/settingsio.py (TC-WORN-WIRE); tests/test_ux_settings_io.py
  (TC-WORN-WIRE).
- Integrator: ROADMAP.md rows of all 13 packages; CLAUDE.md:
  REL-AUTOSTART-ENTRY, DEP-16; docs/decisions/README.md: DEP-16;
  docs/design/reviews.log: 3 lines.
- Watch: tests/test_floor_static.py (TEST-CAPTURE-HELPER edits, TC-WORN-WIRE
  runs).
- Batches: 1: TC-WORN-WIRE, PLAY-LEGACY-OUT-2, TC-CALC-OPTIN,
  REL-AUTOSTART-ENTRY; 2: REL-SBOM, TEST-CAPTURE-HELPER,
  REL-INSTALL-PAYLOAD, REL-INSTALL-SELFTEST; 3: DATA-PROVENANCE,
  RUN-HOTRELOAD-RETRY, DEP-16, TEST-STATE-TEXT-2.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- TC-WORN-WIRE [session, M 45m, build, P1] 'I wear this' endpoint, worn-gear switch and clear. Files: server/al/core.py, server/al/http.py, server/al/settingsio.py, tests/test_ux_settings_io.py, tests/test_security_surface.py (+1 more). Deps: TC-WORN-BASELINE, SEC-SURFACE-PIN.
- PLAY-LEGACY-OUT-2 [session, L 90m, build, P1, DR] Legacy out 2: consent, guide, tip, language and item cards leave Play. Files: web/index.html, web/app.css, web/app.js, web/regions.js, web/hints.js (+9 more). Deps: PLAY-LEGACY-OUT-1, PLAY-TD-11-CONTEXT, PLAY-TD-12-CONTEXT-SETUP, PLAY-TD-14-NOTICE, PLAY-TD-16A-ITEMCARD, PLAY-TD-16B-KEPT-CHECKS.
- TC-CALC-OPTIN [session, M 50m, build, P2, DR] Calc opt-in in one act (setup switch). Files: tools/tc_pin.py, scripts/setup.ps1, server/al/diag.py, web/settingsio.js, tests/test_tc_pin.py (+2 more). Deps: none.
- REL-AUTOSTART-ENTRY [session, L 70m, build, P3] A logon launcher without VBScript. Files: scripts/al_shell.ps1, scripts/autostart.ps1, scripts/autostart_launch.vbs, tests/test_autostart.py, docs/decisions/0011-core-autostart.md (+1 more). Deps: DEP-07, SEC-ACL-SETUP.
- REL-SBOM [session, M 45m, build, P1] SBOM from the pins and the lockfile. Files: tools/sbom.py, tests/test_sbom.py. Deps: REL-RUNTIME-PINS, OVL-ELECTRON-PIN.
- TEST-CAPTURE-HELPER [session, L 70m, build, P2] One capture helper under app/test/cdp/ and the wider floor-scan ban list. Files: tests/test_floor_static.py, tests/test_dash_console.py, app/test/cdp/capture.mjs, tests/test_capture_helper.py, tests/browser_util.py. Deps: TEST-FLOOR-MEMO, TEST-PORT-LEASE, TEST-LAYOUT-GUARD, SEC-DEMO-ENTRY.
- REL-INSTALL-PAYLOAD [session, L 75m, build, P1] Installer package: verify and lay out the payload and the runtimes. Files: server/al/install/payload.py, tests/test_install_payload.py. Deps: REL-INSTALL-HOME, DEP-06, DEP-08, REL-RUNTIME-PINS.
- REL-INSTALL-SELFTEST [session, M 60m, build, P1] Installer package: self-test of a laid-out version. Files: server/al/install/selftest.py, server/al/data/selftest/client_selftest.txt, tests/test_install_selftest.py. Deps: REL-INSTALL-HOME, DEP-06, SEC-DEMO-ENTRY.
- DATA-PROVENANCE [session, M 60m, data, P2] A source and check date on every authored fact. Files: server/al/data/zone_guide.json, server/al/data/zone_notes.json, server/al/campaign.py, server/al/theorycraft/waystone.py, tools/provenance.py (+1 more). Deps: none.
- RUN-HOTRELOAD-RETRY [session, M 30m, build, P2] Hot reload never pins a stale copy on a transient read error. Files: server/al/hotreload.py, tests/test_hot_reload.py. Deps: RUN-DURABLE-CRLF.
- DEP-16 [session, M 50m, build, P1] In-app update notice: the release check client. Files: docs/decisions/0018-tc-pin.md, server/al/updates.py, tests/test_updates.py, docs/decisions/0065-update-policy.md. Deps: DEP-03, DEP-04, DEP-05, RUN-BUILD-STAMP-CORE.
- TEST-STATE-TEXT-2 [session, M 50m, build, P2, DR] State text move 2: text/price.py and text/waystone.py. Files: server/al/state.py, server/al/text/price.py, server/al/text/waystone.py. Deps: RUN-ZONE-RESET.
- TEST-LOOP-SPLIT-MERGE [loop, L 75m, build, P3] Loop tests split 1: merge, gates and dependency themes to tests/test_al_loop_merge.py. Files: tests/test_al_loop.py, tests/al_loopkit.py, tests/test_al_loop_merge.py. Deps: TEST-GATE-CALLERS, AUTO-01, LOOP-HANDOFF-PREFIX, LOOP-PREFLIGHT-CMD, LOOP-FAILED-PARK, LOOP-TESTS-CARVE, AUTO-21, TEST-LAYOUT-GUARD.

### Wave 12: install and release, overlay and client, theorycraft

Goal: Leads: Generate the dashboard's panel script and style tags at serve
time; Quiet base button, one filled button; OBS-CRASH: the core writes
ops/runtime/last-exit.json on every exit path; Checks reads.... Releases 2
loop-owned rows.

- Session 4; width 12 worktree + 0 main-checkout, 2 loop rows released;
  about 120 minutes.
- Hotspots: web/index.html (TEST-WEB-ASSEMBLE); server/al/core.py
  (OVL-OBS-CRASH); server/al/http.py (TEST-WEB-ASSEMBLE); server/al/state.py
  (DATA-GUIDE-MERGE); web/app.css (PLAY-F-159-QUIET-BUTTON);
  server/al/diag.py (OVL-OBS-CRASH); tests/test_ux_review.py
  (PLAY-F-159-QUIET-BUTTON); server/al/__main__.py (OVL-OBS-CRASH);
  app/client/window.js (REL-AUTOSTART-TRAY); scripts/run.ps1
  (REL-AUTOSTART-TRAY); server/al/keepalive.py (OVL-OBS-CRASH);
  tests/test_diag_self.py (OVL-OBS-CRASH); README.md (PUB-README-PLAYERS);
  scripts/setup.ps1 (OVL-NPM-LOCK); server/al/zoneguide.py
  (DATA-GUIDE-MERGE).
- Integrator: ROADMAP.md rows of all 14 packages; CLAUDE.md:
  DATA-GUIDE-MERGE, REL-AUTOSTART-TRAY, DEP-10; docs/decisions/README.md:
  DEP-10; AL-NEXT-SESSION.txt: DATA-GUIDE-MERGE; docs/design/reviews.log: 2
  lines.
- Batches: 1: TEST-WEB-ASSEMBLE, PLAY-F-159-QUIET-BUTTON, OVL-OBS-CRASH,
  REL-INSTALL-SHELL; 2: DATA-GUIDE-MERGE, REL-AUTOSTART-TRAY, OVL-NPM-LOCK,
  PUB-README-PLAYERS; 3: TC-BRIDGE-NEXT, TC-WEIGHTS-DELTA-STORE,
  LOOP-WATCH-GATE, DEP-10.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- TEST-WEB-ASSEMBLE [session, M 60m, build, P3, DR] Generate the dashboard's panel script and style tags at serve time. Files: server/al/http.py, web/index.html, tests/srcpaths.py, server/al/webpage.py, tests/test_webpage.py. Deps: TEST-WEB-REGISTRY, TEST-WEB-SRCPATHS-PY.
- PLAY-F-159-QUIET-BUTTON [session, S 25m, build, P3, DR] Quiet base button, one filled button. Files: web/app.css, tests/test_ux_review.py. Deps: PLAY-LEGACY-OUT-2.
- OVL-OBS-CRASH [session, M 60m, build, P2] OBS-CRASH: the core writes ops/runtime/last-exit.json on every exit path; Checks reads the core and client exit records. Files: server/al/__main__.py, server/al/core.py, server/al/diag.py, server/al/keepalive.py, tests/test_core_crash_log.py (+2 more). Deps: none.
- REL-INSTALL-SHELL [session, M 60m, build, P1] Installer package: shell entries and the first-run config. Files: server/al/install/shell.py, server/al/install/firstrun.py, tests/test_install_shell.py. Deps: REL-INSTALL-HOME, DEP-07, REL-AUTOSTART-ENTRY.
- DATA-GUIDE-MERGE [session, L 70m, data, P2] One guide file: fold zone notes into zone_guide.json. Files: server/al/data/zone_guide.json, server/al/data/zone_notes.json, server/al/zonenotes.py, server/al/zoneguide.py, server/al/state.py (+9 more). Deps: DATA-PROVENANCE, DATA-PRICE-CARD-TEXT, DATA-LEAGUE-IDENTITY.
- REL-AUTOSTART-TRAY [session, L 70m, build, P1] Autostart starts the client tray-only. Files: server/al/autostart_entry.py, scripts/autostart.ps1, scripts/run.ps1, app/client/link.js, app/client/window.js (+4 more). Deps: REL-AUTOSTART-ENTRY, DEP-02.
- OVL-NPM-LOCK [session, M 45m, build, P1] Lock npm down: tracked app/.npmrc, npm ci --ignore-scripts only, electron in dependencies. Files: app/package.json, app/package-lock.json, scripts/setup.ps1, tools/loop_inbox.py, app/.npmrc (+1 more). Deps: none.
- PUB-README-PLAYERS [session, M 60m, build, P1] README quick start for players: shortcut, Stop, Update, Uninstall, Troubleshooting + README, SECURITY, CONTRIBUTING: how the repository is run. Files: README.md, SECURITY.md, CONTRIBUTING.md, tests/test_public_docs.py. Deps: DEP-02.
- TC-BRIDGE-NEXT [session, M 30m, build, P1] Bridge accepts the next PoB main-object shape. Files: server/al/theorycraft/bridge.lua, tests/test_tc_pob_drift_guard.py. Deps: none.
- TC-WEIGHTS-DELTA-STORE [session, M 60m, build, P2] Weights stored as the player's changes only. Files: server/al/theorycraft/weights.py, tests/test_tc_eval_api.py, tests/test_tc_eval.py, tests/test_tc_weights_delta.py. Deps: none.
- LOOP-WATCH-GATE [session, M 40m, build, P1] Watcher web-data gate and URL check: tools/watch_gate.py. Files: tools/watch_gate.py, tests/test_watch_gate.py. Deps: none.
- DEP-10 [session, L 85m, build, P1] Uninstall: stop, delete by fixed name, keep data unless -Purge. Files: scripts/uninstall.ps1, tests/test_uninstall.py, docs/decisions/0066-uninstall-consent.md. Deps: DEP-05, DEP-07.
- TEST-LOOP-SPLIT-LANES [loop, L 75m, build, P3] Loop tests split 2: lane themes to tests/test_al_loop_lanes.py. Files: tests/test_al_loop.py, tests/al_loopkit.py, tests/test_al_loop_lanes.py. Deps: TEST-LOOP-SPLIT-MERGE.
- REL-INSTALL-CALC [loop, M 40m, build, P1] Installer package: calc opt-in in an installed copy. Files: server/al/install/calc.py, tests/test_install_calc.py. Deps: REL-INSTALL-HOME, DEP-06, TC-CALC-OPTIN.

### Wave 13: loop and watchers, reliability and observability, theorycraft

Goal: Leads: Build id in the dashboard footer, overlay About and tray
tooltip; Own counters: metrics.py and the token-gated GET /api/debug; Game
data arrives at start: the supervisor runs the snapshot tool hidden.
Releases 1 loop-owned rows.

- Session 4; width 12 worktree + 0 main-checkout, 1 loop rows released;
  about 125 minutes.
- Hotspots: web/index.html (RUN-BUILD-STAMP-UI); server/al/core.py
  (TC-UPGRADE-PER-SLOT); web/app.js (RUN-BUILD-STAMP-UI); server/al/http.py
  (RUN-METRICS-CORE); server/al/state.py (TEST-STATE-TEXT-3);
  server/al/diag.py (DATA-SNAP-AT-START); app/main.js (RUN-BUILD-STAMP-UI);
  tests/test_security_surface.py (RUN-METRICS-CORE); scripts/run.ps1
  (OVL-ELECTRON-SETUP); server/al/keepalive.py (DATA-SNAP-AT-START);
  tests/test_diag_self.py (DATA-SNAP-AT-START); README.md
  (DATA-SNAP-AT-START); scripts/setup.ps1 (OVL-ELECTRON-SETUP);
  server/al/theorycraft/bridge.py (TC-CALC-CONFINE-PROC);
  tests/test_tc_bridge.py (TC-CALC-CONFINE-PROC); tools/tc_drift.py
  (AUTO-12).
- Integrator: ROADMAP.md rows of all 13 packages; CLAUDE.md:
  RUN-METRICS-CORE, DATA-SNAP-AT-START, OVL-ELECTRON-SETUP, AUTO-12,
  AUTO-05; docs/decisions/README.md: RUN-METRICS-CORE, OVL-ELECTRON-SETUP,
  AUTO-05; docs/design/reviews.log: 4 lines.
- Batches: 1: RUN-BUILD-STAMP-UI, RUN-METRICS-CORE, DATA-SNAP-AT-START,
  PLAY-TD-08B-GUIDE-SHORT-TEXT; 2: TEST-STATE-TEXT-3, OVL-ELECTRON-SETUP,
  AUTO-12, TC-CALC-CONFINE-PROC; 3: AUTO-05, LOOP-WATCH-ROWS,
  REL-UNINSTALL-SHELL, TC-UPGRADE-PER-SLOT.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- RUN-BUILD-STAMP-UI [session, M 30m, build, P1, DR] Build id in the dashboard footer, overlay About and tray tooltip. Files: web/index.html, web/app.js, app/about.js, app/client/tray_menu.js, app/main.js (+1 more). Deps: RUN-BUILD-STAMP-CORE.
- RUN-METRICS-CORE [session, L 75m, build, P1] Own counters: metrics.py and the token-gated GET /api/debug. Files: server/al/http.py, tests/test_security_surface.py, server/al/metrics.py, server/al/plug/debug.py, tests/test_metrics.py (+1 more). Deps: RUN-SEAMS, RUN-BUILD-STAMP-CORE, RUN-TAIL-HEAL-READER.
- DATA-SNAP-AT-START [session, L 70m, build, P1] Game data arrives at start: the supervisor runs the snapshot tool hidden. Files: server/al/keepalive.py, server/al/diag.py, server/al/theorycraft/snapshot.py, README.md, docs/decisions/0009-data-license.md (+4 more). Deps: none.
- PLAY-TD-08B-GUIDE-SHORT-TEXT [session, L 90m, data, DR] Zone guide short lines: author the 93 entries. Files: server/al/data/zone_guide.json. Deps: PLAY-TD-08A-GUIDE-SHORT-FIELD, DATA-GUIDE-MERGE.
- TEST-STATE-TEXT-3 [session, M 50m, build, P2, DR] State text move 3: text/itemcheck.py. Files: server/al/state.py, tests/test_audit_pass2.py, server/al/text/itemcheck.py. Deps: TEST-STATE-TEXT-2.
- OVL-ELECTRON-SETUP [session, M 50m, build, P1] Electron pin wired into setup and run: override variables cleared, install.js replaced, electron.exe verified. Files: scripts/setup.ps1, scripts/run.ps1, tests/test_electron_pin.py, docs/decisions/0068-electron-npm-supply-chain.md. Deps: OVL-NPM-LOCK, OVL-ELECTRON-PIN.
- AUTO-12 [session, M 50m, build, P1] TC-DRIFT-TRIAL-FIX (part 1): re-hash pob2_files from the candidate; prune old candidates. Files: tools/tc_drift.py, tests/test_tc_drift.py, docs/decisions/0025-tc-drift.md. Deps: TC-BRIDGE-NEXT.
- TC-CALC-CONFINE-PROC [session, L 65m, build, P2] Confine the calc child process. Files: server/al/theorycraft/bridge.py, tests/test_tc_bridge.py, docs/decisions/0022-tc-bridge.md. Deps: TC-BRIDGE-NEXT.
- AUTO-05 [session, L 70m, build, P1] WATCH-CORE frame: tools/upstream_watch.py registry, state, cadence, web-data gate. Files: tools/upstream_watch.py, tools/watch_sources/__init__.py, tests/test_upstream_watch.py, docs/decisions/0069-upstream-watch-frame.md. Deps: LOOP-WATCH-GATE.
- LOOP-WATCH-ROWS [session, M 50m, build, P1] Watcher row templates: one validated table folder and a renderer. Files: tools/watch_rows.py, tests/test_watch_rows.py, ops/loop/watch_rows/README.md. Deps: none.
- REL-UNINSTALL-SHELL [session, M 50m, build, P1] Uninstall: logon task, shortcuts and the uninstall key. Files: scripts/uninstall.ps1, tests/test_uninstall.py. Deps: DEP-10, REL-AUTOSTART-ENTRY.
- TC-UPGRADE-PER-SLOT [session, M 55m, build, P2, DR] Trade-search link on every 'Look for next' row. Files: server/al/upgrade.py, server/al/theorycraft/health.py, server/al/theorycraft/store.py, server/al/core.py, web/health.js (+3 more). Deps: TC-WORN-WIRE.
- TEST-LOOP-GIT-TEMPLATE [loop, M 40m, build, P3] git_world from a session-scoped template copy. Files: tests/al_loopkit.py. Deps: TEST-LOOP-SPLIT-LANES.

### Wave 14: reliability and observability, install and release, theorycraft

Goal: Milestones: four tabs: Play, Build and items, Run, Settings. Leads:
Four tabs: Play, Build and items, Run, Settings; Hotkeys in the core:
effective keys in the snapshot, POST /api/hotkeys, Checks rows for...;
Budget log: the core records its own footprint once a minute. Releases 3
loop-owned rows.

- Session 5; width 12 worktree + 0 main-checkout, 3 loop rows released;
  about 115 minutes.
- Hotspots: web/index.html (PLAY-TD-19B-FOUR-TABS); server/al/core.py
  (OVL-KEYS-CORE); server/al/http.py (OVL-KEYS-CORE); server/al/state.py
  (OVL-KEYS-CORE); web/app.css (PLAY-TD-19B-FOUR-TABS); server/al/diag.py
  (OVL-KEYS-CORE); tests/test_ux_review.py (PLAY-TD-19B-FOUR-TABS);
  app/main.js (RUN-BUDGET-LOG-CLIENT); tests/test_security_surface.py
  (OVL-KEYS-CORE); app/client/window.js (REL-AUTOSTART-SWITCH);
  tests/test_diag_self.py (OVL-KEYS-CORE); README.md (AUTO-14);
  tests/test_ux_b8.py (PLAY-TD-19B-FOUR-TABS); scripts/setup.ps1
  (LOOP-ELECTRON-POLICY); app/test/tabs.test.js (PLAY-TD-19B-FOUR-TABS);
  tests/test_tc_bridge.py (TC-CALC-CONFINE-LUA); tools/tc_drift.py
  (TC-CALC-VERIFY-PIN).
- Integrator: ROADMAP.md rows of all 15 packages; CLAUDE.md:
  RUN-BUDGET-LOG-CORE, REL-AUTOSTART-SWITCH, AUTO-14, TC-CALC-VERIFY-PIN,
  LOOP-ELECTRON-POLICY; docs/decisions/README.md: LOOP-ELECTRON-POLICY;
  docs/design/reviews.log: 1 lines.
- Batches: 1: PLAY-TD-19B-FOUR-TABS, OVL-KEYS-CORE, RUN-BUDGET-LOG-CORE,
  RUN-BUDGET-LOG-CLIENT; 2: REL-INSTALL-CMD, REL-AUTOSTART-SWITCH, AUTO-14,
  TC-CALC-VERIFY-PIN; 3: TC-CALC-CONFINE-LUA, AUTO-11, DATA-TREE-HOLD,
  LOOP-ELECTRON-POLICY.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- PLAY-TD-19B-FOUR-TABS [session, M 60m, build, P1, DR] Four tabs: Play, Build and items, Run, Settings. Files: web/index.html, web/tabs.js, web/app.css, app/test/tabs.test.js, tests/test_ux_review.py (+1 more). Deps: PLAY-LEGACY-OUT-2, PLAY-F-159-QUIET-BUTTON.
- OVL-KEYS-CORE [session, L 80m, build, P1] Hotkeys in the core: effective keys in the snapshot, POST /api/hotkeys, Checks rows for both chords. Files: server/al/hotkeys.py, server/al/core.py, server/al/state.py, server/al/http.py, server/al/diag.py (+4 more). Deps: OVL-KEYS-CLIENT, SEC-SURFACE-PIN.
- RUN-BUDGET-LOG-CORE [session, M 60m, build, P1] Budget log: the core records its own footprint once a minute. Files: docs/decisions/0006-fps-measurement-method.md, server/al/budgetlog.py, server/al/plug/budget.py, tests/test_budget_log.py. Deps: RUN-METRICS-CORE.
- RUN-BUDGET-LOG-CLIENT [session, M 30m, build, P1] Client samples its own Electron processes once a minute. Files: app/main.js, app/metrics.js, app/test/metrics.test.js. Deps: RUN-BUILD-STAMP-UI.
- REL-INSTALL-CMD [session, L 75m, build, P1] Installer package: install and repair commands. Files: server/al/install/install.py, server/al/install/repair.py, tests/test_installer.py. Deps: REL-INSTALL-PAYLOAD, REL-INSTALL-SELFTEST, REL-INSTALL-SHELL, DATA-SNAP-AT-START.
- REL-AUTOSTART-SWITCH [session, M 60m, build, P1] 'Start with Windows' in the tray menu. Files: app/client/tray_menu.js, app/client/window.js, app/client/launcher.js, app/client/preload.js, app/test/client_controls.test.js (+1 more). Deps: REL-AUTOSTART-TRAY.
- AUTO-14 [session, L 70m, build, P2] DOCS-FRESH: tools/docs_fresh.py check, with the code-pin facts. Files: README.md, tools/docs_fresh.py, tests/test_docs_fresh.py. Deps: DEP-03, PUB-README-PLAYERS.
- TC-CALC-VERIFY-PIN [session, L 70m, build, P2] Pin contents, not bytes. Files: config/tc_pins.json, tools/tc_pin.py, tools/tc_drift.py, tests/test_tc_pin.py, tests/test_tc_drift.py (+1 more). Deps: TC-CALC-OPTIN, AUTO-12.
- TC-CALC-CONFINE-LUA [session, M 45m, build, P2] Drop dangerous Lua entry points after PoB loads. Files: server/al/theorycraft/bridge.lua, tests/test_tc_bridge.py, tests/test_tc_pob_drift_guard.py. Deps: TC-BRIDGE-NEXT, TC-CALC-CONFINE-PROC.
- AUTO-11 [session, M 40m, build, P2] DOCS-SHAPE: a 'shape' topic in the GGG docs watch. Files: tools/ggg_docs_watch.py, tests/test_ggg_docs_watch.py, docs/decisions/0044-ggg-docs-watch.md. Deps: none.
- DATA-TREE-HOLD [session, M 60m, build, P2] Keep the previous passive tree and resolve each build against the best match. Files: server/al/theorycraft/snapshot.py, server/al/theorycraft/treedata.py, server/al/theorycraft/store.py, tests/test_tc_tree.py, tests/test_tc_tree_ids.py (+1 more). Deps: DATA-SNAP-AT-START.
- LOOP-ELECTRON-POLICY [session, M 50m, build, P2] Electron upgrade policy decision; setup refuses the npm step while the client runs. Files: scripts/setup.ps1, docs/decisions/0070-electron-upgrade-policy.md, tests/test_setup_client_guard.py. Deps: none.
- REL-UNINSTALL-CHECKOUT [loop, M 45m, build, P1] Uninstall: checkout mode. Files: scripts/uninstall.ps1, tests/test_uninstall.py. Deps: REL-UNINSTALL-SHELL.
- RUN-METRICS-PROBE [loop, S 25m, build, P1] python -m server.al.probe: one line per item, exit 0 live, 1 stopped. Files: server/al/probe.py, tests/test_probe.py. Deps: RUN-METRICS-CORE.
- TEST-LOOP-STUB-GIT [loop, L 75m, build, P3] Stub git runner for the tick tests that do not test git. Files: tests/al_loopkit.py, tests/test_al_loop.py, tests/test_al_loop_merge.py, tests/test_al_loop_lanes.py. Deps: TEST-LOOP-GIT-TEMPLATE.

### Wave 15: loop and watchers, reliability and observability, theorycraft

Goal: Leads: Counter call sites: fetches per host, calc starts and
time-outs, press outcome; Optional wear key (unset by default); Update from
a local zip: verify, build beside, self-test, stage.

- Session 5; width 12 worktree + 1 main-checkout, 0 loop rows released;
  about 135 minutes.
- Hotspots: web/index.html (RUN-METRICS-SITES); server/al/core.py
  (RUN-METRICS-SITES); web/app.js (RUN-METRICS-SITES); server/al/http.py
  (RUN-METRICS-SITES); server/al/state.py (TEST-STATE-TEXT-4); app/main.js
  (TC-WORN-KEY); scripts/run.ps1 (OVL-LAUNCH-ENV); README.md
  (RUN-SETTINGS-TRIM-DOCS); app/test/client.test.js (OVL-LAUNCH-ENV);
  app/test/tabs.test.js (PLAY-TD-22B-TAB-FOCUS); server/al/settingsio.py
  (TC-WORN-KEY); tests/test_ux_settings_io.py (TC-WORN-KEY);
  server/al/theorycraft/bridge.py (RUN-METRICS-SITES); tools/tc_drift.py
  (LOOP-WATCH-SETTLED).
- Integrator: ROADMAP.md rows of all 13 packages; CLAUDE.md:
  RUN-METRICS-SITES; docs/decisions/README.md: RUN-METRICS-SITES,
  TEST-DOCS-INDEX; AL-NEXT-SESSION.txt: LOOP-WATCH-SETTLED;
  docs/research/README.md: TEST-DOCS-INDEX; docs/design/reviews.log: 3
  lines.
- Batches: 1: RUN-METRICS-SITES, TC-WORN-KEY, DEP-11, PLAY-TD-22B-TAB-FOCUS;
  2: TEST-STATE-TEXT-4, OVL-LAUNCH-ENV, TEST-DOCS-INDEX, LOOP-WATCH-FILE; 3:
  DEP-13, LOOP-WATCH-META, LOOP-WATCH-SETTLED, TC-GGG-RATELIMIT.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- RUN-METRICS-SITES [session, L 90m, build, P1, DR] Counter call sites: fetches per host, calc starts and time-outs, press outcome + Own consent line for the parse ledger (consent key, route flag, da. Files: server/al/webfetch.py, server/al/theorycraft/bridge.py, server/al/core.py, tests/test_metrics.py, server/al/http.py (+4 more). Deps: RUN-METRICS-CORE, RUN-TAIL-HEAL-CORE, RUN-LEDGER-CORE, RUN-BUILD-STAMP-UI.
- TC-WORN-KEY [session, M 45m, build, P1] Optional wear key (unset by default). Files: app/main.js, app/eval_hotkey.js, server/al/settingsio.py, app/test/eval.test.js, tests/test_floor_static.py (+1 more). Deps: TC-WORN-WIRE, TC-PRESS-BUILD, OVL-KEYS-CORE.
- DEP-11 [session, L 75m, build, P1] Update from a local zip: verify, build beside, self-test, stage. Files: server/al/install/update.py, tests/test_updater.py. Deps: REL-INSTALL-CMD.
- PLAY-TD-22B-TAB-FOCUS [session, M 40m, build, P2, DR] Auto-return to Play keeps focus where the user is. Files: web/tabs.js, app/test/tabs.test.js. Deps: PLAY-TD-19B-FOUR-TABS.
- TEST-STATE-TEXT-4 [session, M 45m, build, P2, DR] State text move 4: text/buildlive.py and text/overlaycard.py. Files: server/al/state.py, server/al/text/buildlive.py, server/al/text/overlaycard.py. Deps: TEST-STATE-TEXT-3.
- OVL-LAUNCH-ENV [session, M 45m, build, P2] Launcher runs tools by absolute path; the client starts without ELECTRON_RUN_AS_NODE and NODE_OPTIONS. Files: app/client/launcher.js, scripts/run.ps1, scripts/al_detach.ps1, app/test/client.test.js, tests/test_audit_exe_path.py. Deps: OVL-ELECTRON-SETUP.
- TEST-DOCS-INDEX [session, M 45m, build, P2] docs_fresh.py: stale markers, index --write, every decision and research file indexed. Files: tools/docs_fresh.py, tests/test_docs_fresh.py, tests/test_docs_index.py. Deps: AUTO-14, LOOP-LEDGERS.
- LOOP-WATCH-FILE [session, L 85m, build, P1] The two row primitives and the unattended add-only commit path (Q-12). Files: tools/watch_file.py, tests/test_watch_file.py. Deps: AUTO-03, AUTO-05, LOOP-WATCH-ROWS.
- DEP-13 [session, M 50m, build, P1] Cut-over tooling: migrate player data from a checkout. Files: server/al/install/migrate.py, tests/test_migrate.py. Deps: REL-INSTALL-CMD.
- LOOP-WATCH-META [session, M 50m, build, P1] Watch sources: repoe-fork data and the GGG passive tree export (metadata only). Files: tools/watch_sources/repoe_fork.py, tools/watch_sources/ggg_tree.py, tests/test_watch_meta.py. Deps: AUTO-05.
- LOOP-WATCH-SETTLED [session, M 55m, build, P1] The GGG docs watch and the PoB release check as registry sources. Files: tools/tc_drift.py, tools/watch_sources/ggg_docs.py, tools/watch_sources/pob_release.py, ops/loop/watch_rows/ggg_docs.json, ops/loop/watch_rows/pob_release.json (+1 more). Deps: AUTO-05, LOOP-WATCH-ROWS, AUTO-11.
- TC-GGG-RATELIMIT [session, M 50m, build, P1] Header-driven rate limiter. Files: server/al/ratelimit.py, tests/test_ratelimit.py. Deps: none.
- RUN-SETTINGS-TRIM-DOCS [session, S 15m, review, P3] Drop four tuning keys from the player docs. Files: README.md, config/local.example.json. Deps: PUB-README-PLAYERS.

### Wave 16: theorycraft, loop and watchers, reliability and observability

Goal: Milestones: the dashboard prints the real keys and can change them;
the parse ledger is wired (LIVE-1 read-back starts). Leads: Dashboard prints
the real keys, one change-key field per chord, one Play line while the...;
Wire the ledger: feed_line hook, write tick, drift note, read-back flags,
waystone shape; Python logs bounded, one format, a banner per start,
faulthandler on its own file. Releases 1 loop-owned rows.

- Session 5; width 12 worktree + 0 main-checkout, 1 loop rows released;
  about 115 minutes.
- Hotspots: web/index.html (OVL-KEYS-WEB); server/al/core.py
  (RUN-LEDGER-WIRE); web/app.js (OVL-KEYS-WEB); server/al/state.py
  (DATA-GUIDE-BOSS); tests/test_ux_review.py (OVL-KEYS-WEB); app/main.js
  (TC-CALC-OPTIN-BUTTON); server/al/__main__.py (RUN-OBS-LOGS-PY);
  server/al/keepalive.py (RUN-OBS-LOGS-PY); README.md (TEST-DOCS-FACTS-UI);
  tests/test_ux_b8.py (OVL-KEYS-WEB); app/test/client.test.js
  (TC-CALC-OPTIN-BUTTON); app/test/checks.test.js (TC-CALC-OPTIN-BUTTON);
  tests/test_keepalive.py (RUN-OBS-LOGS-PY); web/checks.js
  (TC-CALC-OPTIN-BUTTON); web/prices.js (OVL-KEYS-WEB);
  app/test/prices.test.js (OVL-KEYS-WEB); server/al/theorycraft/bridge.py
  (RUN-OBS-LOGS-PY); server/al/zoneguide.py (DATA-GUIDE-BOSS);
  tests/test_tc_bridge.py (RUN-OBS-LOGS-PY); tools/tc_drift.py
  (RUN-OBS-LOGS-PY).
- Integrator: ROADMAP.md rows of all 13 packages; CLAUDE.md:
  TC-CALC-OPTIN-BUTTON, DATA-GUIDE-BOSS; AL-NEXT-SESSION.txt: AUTO-07;
  docs/design/reviews.log: 3 lines.
- Batches: 1: OVL-KEYS-WEB, RUN-LEDGER-WIRE, RUN-OBS-LOGS-PY,
  TC-CALC-OPTIN-BUTTON; 2: REL-UPDATE-SWITCH, TC-GGG-LISTENER,
  DATA-GUIDE-BOSS, LOOP-USAGE-LABEL; 3: TEST-DOCS-FACTS-UI, AUTO-09,
  TC-CHARJSON-SHAPES, AUTO-07.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- OVL-KEYS-WEB [session, L 75m, build, P1, DR] Dashboard prints the real keys, one change-key field per chord, one Play line while the overlay is off. Files: web/index.html, web/app.js, web/prices.js, server/al/hints.py, app/test/prices.test.js (+5 more). Deps: OVL-KEYS-CORE.
- RUN-LEDGER-WIRE [session, M 60m, build, P1, DR] Wire the ledger: feed_line hook, write tick, drift note, read-back flags, waystone shape. Files: server/al/core.py, server/al/plug/ledger.py, tests/test_ledger_wire.py. Deps: RUN-METRICS-SITES.
- RUN-OBS-LOGS-PY [session, L 75m, build, P1] Python logs bounded, one format, a banner per start, faulthandler on its own file + Heavy child processes start below normal priority. Files: server/al/__main__.py, server/al/keepalive.py, server/al/theorycraft/bridge.py, tests/test_core_crash_log.py, tools/tc_drift.py (+6 more). Deps: RUN-BUILD-STAMP-CORE, RUN-DURABLE-CRLF, RUN-METRICS-SITES.
- TC-CALC-OPTIN-BUTTON [session, M 60m, build, P2, DR] 'Set up the Path of Building calc' button in the client. Files: app/client/preload.js, app/main.js, web/checks.js, app/test/client.test.js, app/test/checks.test.js (+1 more). Deps: TC-CALC-OPTIN, TC-WORN-KEY, OVL-KEYS-CLIENT.
- REL-UPDATE-SWITCH [session, L 80m, build, P1] Update: apply-staged, confirm and rollback. Files: server/al/install/switch.py, server/al/install/apply_staged.py, server/al/install/rollback.py, server/al/install/confirm.py, tests/test_update_switch.py. Deps: DEP-11, REL-INSTALL-SHELL.
- TC-GGG-LISTENER [session, M 40m, build, P1] One-shot loopback listener for the OAuth redirect. Files: server/al/ports.py, tests/test_port_resolve.py, server/al/oauthlisten.py, tests/test_oauthlisten.py. Deps: none.
- DATA-GUIDE-BOSS [session, M 35m, data, P2] Boss elements move from campaign.BOSS_ZONES into the guide file. Files: server/al/data/zone_guide.json, server/al/zoneguide.py, server/al/campaign.py, server/al/state.py, tools/provenance.py (+3 more). Deps: DATA-GUIDE-MERGE.
- LOOP-USAGE-LABEL [session, S 25m, build, P1] The row id reaches the lane's usage line. Files: tools/al_lane.py, tests/test_lane_usage_label.py. Deps: none.
- TEST-DOCS-FACTS-UI [session, M 45m, build, P2] docs_fresh.py: hotkeys, budgets, settings keys and tab names. Files: tools/docs_fresh.py, tests/test_docs_fresh.py, README.md. Deps: TEST-DOCS-INDEX.
- AUTO-09 [session, M 55m, build, P2] ELECTRON-WATCH sources: releases, schedule and npm audit. Files: tools/watch_sources/electron.py, tools/watch_sources/npm_audit.py, ops/loop/watch_rows/electron.json, tests/test_watch_electron.py. Deps: AUTO-05, LOOP-WATCH-ROWS, LOOP-ELECTRON-POLICY.
- TC-CHARJSON-SHAPES [session, M 50m, build, P1] charjson reads the item shapes GGG documents today. Files: server/al/theorycraft/charjson.py, tests/tc_fixtures.py, tests/test_tc_json.py. Deps: none.
- AUTO-07 [session, M 60m, build, P1] LAUNCH-GATE: the 1.0 rows open by themselves (due 2026-12-04). Files: docs/ops/1.0-launch-runbook.md, tools/watch_sources/launch.py, ops/loop/watch_rows/launch.json, tests/test_watch_launch.py. Deps: AUTO-03, AUTO-05, LOOP-WATCH-ROWS, LOOP-WATCH-FILE, LOOP-WATCH-META, AUTO-04.
- SEC-CEIL-WEBFETCH [loop, S 30m, build, P3] A total deadline per outbound request. Files: server/al/webfetch.py, tests/test_webfetch_deadline.py. Deps: RUN-METRICS-SITES.

### Wave 17: go-public, theorycraft, tests and code seams

Goal: Leads: Build and items grid 1: Build, Health and next, Search strings;
Overlay legibility recipe and two type sizes in the overlay CSS (TD-05, part
1); Contact value: a write-only POST and its core setter. Releases 1
loop-owned rows.

- Session 5; width 12 worktree + 0 main-checkout, 1 loop rows released;
  about 125 minutes.
- Hotspots: web/index.html (PLAY-TD-19C-BUILD-GRID); server/al/core.py
  (DATA-CONTACT-FIELD); web/app.js (PLAY-TD-19C-BUILD-GRID);
  server/al/http.py (DATA-CONTACT-FIELD); web/app.css
  (PLAY-TD-19C-BUILD-GRID); server/al/diag.py (DATA-CONTACT-FIELD);
  tests/test_ux_review.py (OVL-TD05-LEGIBILITY); app/main.js
  (REL-CLIENT-HOME); server/al/__main__.py (DATA-CONTACT-FIELD);
  tests/test_diag_self.py (DATA-CONTACT-FIELD); tests/test_ux_b8.py
  (PLAY-TD-19C-BUILD-GRID); app/test/client.test.js (REL-CLIENT-HOME);
  docs/design/0001-design-system.md (OVL-TD05-LEGIBILITY);
  tests/test_keepalive.py (TEST-TIMER-FIXES);
  server/al/theorycraft/bridge.py (TC-CALC-VERIFY-USE);
  tests/test_tc_bridge.py (TC-CALC-VERIFY-USE).
- Integrator: ROADMAP.md rows of all 13 packages; CLAUDE.md:
  DATA-CONTACT-FIELD, TC-CALC-VERIFY-USE, LOOP-WATCH-WIRE;
  docs/design/reviews.log: 3 lines.
- Watch: tests/test_p163_lane_tools.py (AUTO-15 edits, GP-14 runs).
- Batches: 1: PLAY-TD-19C-BUILD-GRID, OVL-TD05-LEGIBILITY,
  DATA-CONTACT-FIELD, REL-CLIENT-HOME; 2: TC-CALC-VERIFY-USE, AUTO-15,
  TEST-TIMER-FIXES, TC-GGG-CLIENT-CORE; 3: LOOP-WATCH-WIRE, GP-14,
  PUB-SWEEP-OWN-ADDRESS, PUB-SOCIAL-CARD.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- PLAY-TD-19C-BUILD-GRID [session, L 90m, build, P1, DR] Build and items grid 1: Build, Health and next, Search strings. Files: web/index.html, web/app.css, web/app.js, web/health.js, web/search.js (+4 more). Deps: PLAY-TD-19B-FOUR-TABS, PLAY-TD-19A-PAGER.
- OVL-TD05-LEGIBILITY [session, M 55m, build, P2, DR] Overlay legibility recipe and two type sizes in the overlay CSS (TD-05, part 1). Files: app/overlay/overlay.css, app/overlay/index.html, tests/test_design_contrast.py, tests/test_ux_review.py, docs/design/0001-design-system.md. Deps: OVL-KEYS-WEB, OVL-GLANCE-RULES, PLAY-TD-03-TOKENS, PLAY-TD-04A-DARK-CLIENT.
- DATA-CONTACT-FIELD [session, L 90m, build, P1] Contact value: a write-only POST and its core setter + Prices refresh from the core loop, not the visible page. Files: server/al/http.py, server/al/core.py, server/al/diag.py, docs/decisions/0015-price-check-and-contact.md, tests/test_diag_self.py (+5 more). Deps: none.
- REL-CLIENT-HOME [session, M 50m, build, P1] Installed-mode paths in the Electron client. Files: app/main.js, app/client/launcher.js, app/test/client.test.js, tests/test_install_paths.py, app/client/home.js (+1 more). Deps: DEP-05.
- TC-CALC-VERIFY-USE [session, M 60m, build, P2] Verify the calc component at each start. Files: server/al/theorycraft/bridge.py, server/al/theorycraft/bridge.lua, tests/test_tc_bridge.py, docs/decisions/0022-tc-bridge.md. Deps: TC-CALC-VERIFY-PIN, TC-CALC-CONFINE-LUA, TC-CALC-CONFINE-PROC.
- AUTO-15 [session, L 75m, build, P2] SHOTS: tools/shots.py render and check, the manifest, the lane tool grant. Files: tools/al_lane.py, tests/test_p163_lane_tools.py, tools/shots.py, tests/test_shots.py. Deps: TEST-CAPTURE-HELPER, SEC-DEMO-ENTRY.
- TEST-TIMER-FIXES [session, M 30m, build, P2] Small timer fixes in five test files. Files: tests/test_keepalive.py, tests/test_audit_pass5.py, tests/test_cover_gaps.py, tests/test_procs.py, tests/test_budgets.py. Deps: TEST-PORT-LEASE, TEST-MARKS.
- TC-GGG-CLIENT-CORE [session, M 60m, build, P1] Offline core of a GGG OAuth client. Files: server/al/gggapi.py, tests/test_gggapi.py. Deps: TC-GGG-RATELIMIT, TC-GGG-LISTENER, DATA-GGG-APPLICATION.
- LOOP-WATCH-WIRE [session, M 55m, build, P1] Wire the watcher into the tick in front of HALT; file pending findings after the work list. Files: tools/loop_steps/docs_watch.py, tools/loop_steps/tc_drift.py, docs/decisions/0025-tc-drift.md, tools/loop_steps/upstream_watch.py, tests/test_watch_wire.py. Deps: AUTO-01, AUTO-05, LOOP-WATCH-FILE, LOOP-WATCH-SETTLED.
- GP-14 [session, M 45m, data, P1] Dependabot re-apply tool: list, close and the run loop. Files: tools/dependabot_reapply.py, tests/test_dependabot_reapply.py, tests/fixtures/dependabot/pr_guard.json. Deps: none.
- PUB-SWEEP-OWN-ADDRESS [session, M 45m, build, P1] Leak sweep: allow exactly the project's own repository address. Files: tools/leak_sweep.py, tests/test_leak_sweep.py. Deps: none.
- PUB-SOCIAL-CARD [session, M 40m, build, P1, DR] Own-art social preview card. Files: tools/make_icons.py, tests/test_brand_assets.py, assets/brand/social-preview.svg, assets/brand/social-preview.png. Deps: none.
- TC-ASC-FROM-TREE [loop, M 45m, build, P2] Ascendancy names from the cached tree export. Files: server/al/theorycraft/treedata.py, server/al/theorycraft/charjson.py, server/al/theorycraft/buildlive.py, tests/test_build_live.py, tests/test_util_10_ready.py (+1 more). Deps: TC-CHARJSON-SHAPES, TC-VERDICT-CAVEAT, DATA-TREE-HOLD, DATA-LEAGUE-IDENTITY.

### Wave 18: go-public, web data, reliability and observability

Goal: Leads: Build and items grid 2: Last item, Prices with checked items,
Item scoring; One hook for data checks: diag_data (attach, facts, rows); A
bind failure names its cause; --port stays in the block (P8-4).

- Session 6; width 16 worktree + 0 main-checkout, 0 loop rows released;
  about 133 minutes (GP-10 and AUTO-19 joined at the wave 18 start,
  session 16).
- Hotspots: web/index.html (PLAY-TD-19D-ITEMS-GRID); server/al/core.py
  (DATA-DIAG-SEAM); web/app.js (PLAY-TD-19D-ITEMS-GRID); server/al/http.py
  (DATA-DIAG-SEAM); web/app.css (PLAY-TD-19D-ITEMS-GRID); server/al/diag.py
  (DATA-DIAG-SEAM); tests/test_ux_review.py (PLAY-TD-19D-ITEMS-GRID);
  server/al/__main__.py (RUN-START-REASON-CORE); scripts/run.ps1
  (REL-RUNTIME-SCRIPTS); tests/test_ux_b8.py (PLAY-TD-19D-ITEMS-GRID);
  scripts/setup.ps1 (REL-RUNTIME-SCRIPTS); web/prices.js
  (PLAY-TD-19D-ITEMS-GRID); app/test/prices.test.js
  (PLAY-TD-19D-ITEMS-GRID); server/al/ninja.py (DATA-PRICE-CADENCE);
  server/al/pricebook.py (DATA-PRICE-CADENCE); server/al/zoneguide.py
  (DATA-GUIDE-FACTS); tests/test_tc_bridge.py (LOOP-DRIFT-REF);
  tools/tc_drift.py (LOOP-DRIFT-REF); README.md (GP-10).
- Integrator: ROADMAP.md rows of all 16 packages; CLAUDE.md:
  DATA-PRICE-CADENCE, LOOP-DRIFT-REF, AUTO-19; docs/decisions/README.md:
  DATA-PRICE-CADENCE, AUTO-19; AL-NEXT-SESSION.txt: DATA-PRICE-CADENCE;
  docs/design/reviews.log: 1 lines.
- Watch: tests/test_port_resolve.py (RUN-START-REASON-CORE edits,
  REL-RUNTIME-SCRIPTS runs).
- Batches: 1: PLAY-TD-19D-ITEMS-GRID, DATA-DIAG-SEAM, RUN-START-REASON-CORE,
  DATA-PRICE-CADENCE; 2: REL-RUNTIME-SCRIPTS, LOOP-DRIFT-REF,
  LOOP-WATCH-POBNEXT, RUN-LEDGER-REPORT; 3: PUB-SETTINGS-FILES, GP-08,
  TEST-SUITE-SOAK, DATA-GUIDE-FACTS; 4: PUB-DEPBOT-ACTIONS, PUB-DEPBOT-TICK,
  GP-10, AUTO-19.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- PLAY-TD-19D-ITEMS-GRID [session, L 90m, build, P1, DR] Build and items grid 2: Last item, Prices with checked items, Item scoring. Files: web/index.html, web/app.css, web/app.js, web/prices.js, web/pricewatch.js (+8 more). Deps: PLAY-TD-19C-BUILD-GRID.
- DATA-DIAG-SEAM [session, L 85m, build, P2] One hook for data checks: diag_data (attach, facts, rows) + League picker, server half: write the league key, solo-league mapping. Files: server/al/core.py, server/al/diag.py, server/al/http.py, server/al/leagues.py, server/al/diag_data.py (+2 more). Deps: DATA-CONTACT-FIELD, DATA-LEAGUE-IDENTITY.
- RUN-START-REASON-CORE [session, M 60m, build, P2] A bind failure names its cause; --port stays in the block (P8-4) + One JSON line per own event (events.jsonl). Files: server/al/__main__.py, server/al/ports.py, tests/test_port_resolve.py, server/al/oplog.py, server/al/plug/oplog.py (+1 more). Deps: RUN-OBS-LOGS-PY, RUN-METRICS-SITES, RUN-LEDGER-WIRE.
- DATA-PRICE-CADENCE [session, M 60m, build, P1] Tiered poe.ninja cadence and the release polling gate. Files: server/al/ninja.py, server/al/pricebook.py, docs/decisions/0026-price-book-and-league-rollover.md, docs/decisions/0072-poe-ninja-cadence-and-release-gate.md, tests/test_price_cadence.py, tests/test_price_book.py, tests/test_fullstack.py. Deps: DATA-PRICE-POLITE, DATA-CONTACT-FIELD.
- REL-RUNTIME-SCRIPTS [session, L 80m, build, P1] One PowerShell helper for Python and paths; the client prefers the private runtimes. Files: scripts/run.ps1, scripts/stop.ps1, scripts/setup.ps1, scripts/build.ps1, scripts/autostart.ps1 (+7 more). Deps: DEP-06, REL-AUTOSTART-ENTRY, REL-CLIENT-HOME, REL-RUNTIME-PINS, DEP-02, OVL-ELECTRON-SETUP, OVL-LAUNCH-ENV, SEC-NO-PROXY.
- LOOP-DRIFT-REF [session, M 60m, build, P1] TC-DRIFT-TRIAL-FIX (part 2): trial --ref rehearsal and the GUI reference keyed by tag. Files: tools/tc_drift.py, tests/test_tc_drift.py, tests/tc_live_util.py, tests/test_tc_bridge.py, docs/decisions/0025-tc-drift.md (+1 more). Deps: AUTO-12.
- LOOP-WATCH-POBNEXT [session, M 35m, build, P1] Watch source: PoB-PoE2 next release (master head, weekly). Files: tools/watch_sources/pob_next.py, ops/loop/watch_rows/pob-next.json, tests/test_watch_pob_next.py. Deps: AUTO-05, LOOP-WATCH-ROWS.
- RUN-LEDGER-REPORT [session, M 30m, build, P1] tools/live1_report.py: VERIFIED live / NOT SEEN / NEW SHAPE per LIVE-1 item. Files: tools/live1_report.py, tests/test_live1_report.py. Deps: RUN-LEDGER-CORE, RUN-LEDGER-WIRE.
- PUB-SETTINGS-FILES [session, S 25m, build, P1] Repository settings as tracked files with a lint test. Files: ops/github/ruleset-main-protect.json, ops/github/ruleset-main-checks.json, ops/github/ruleset-release-tags.json, ops/github/security.json, ops/github/branch-protection-fallback.json (+1 more). Deps: GP-05.
- GP-08 [session, S 20m, build, P1] Dependabot config file. Files: .github/dependabot.yml, tests/test_dependabot_config.py. Deps: none.
- TEST-SUITE-SOAK [session, L 75m, review, P2] Prove the parallel gate: 10 green runs, one serial fallback run, one spelling. Files: docs/research/0049-test-suite-speed.md. Deps: TEST-GATE-CALLERS.
- DATA-GUIDE-FACTS [session, M 60m, data, P2] Guide facts from allowed sources: 4 blank zones, point-books wording, coverage. Files: server/al/data/zone_guide.json, server/al/zoneguide.py, tests/test_zone_guide.py, tests/test_provenance.py. Deps: DATA-GUIDE-MERGE, DATA-GUIDE-BOSS.
- PUB-DEPBOT-ACTIONS [session, M 50m, data, P1] Dependabot re-apply tool: actions bumps and the commit, push and close path. Files: tools/dependabot_reapply.py, tests/test_dependabot_reapply.py, tests/fixtures/dependabot/pr_actions.json. Deps: GP-14, GP-02, GP-05.
- PUB-DEPBOT-TICK [session, M 45m, build, P1] Loop tick launches the Dependabot re-apply worker once a day. Files: tools/al_loop.py, tools/loop_depbot.py, tests/test_loop_depbot.py. Deps: GP-14, PUB-LOCAL-ONLY-TEXT.
- GP-10 [session, S 20m, build, P1] The project's own address in tracked files. Files: README.md, SECURITY.md, .github/ISSUE_TEMPLATE/config.yml, config/public_repo.json. Deps: GP-09, PUB-SWEEP-OWN-ADDRESS, GP-06, PUB-README-PLAYERS.
- AUTO-19 [session, M 55m, build, P2] CI-WATCH (workflow half): a daily workflow that writes one key issue per finding. Files: .github/workflows/watch.yml, tools/watch_ci.py, tests/test_watch_ci.py, docs/decisions/0076-ci-issue-protocol.md. Deps: AUTO-05, LOOP-WATCH-GATE, GP-09, GP-05.

### Wave 19: reliability and observability, web data, install and release

Goal: Leads: 'Tried in game' card on the Checks tool; Map ladder tick is
free when nothing changed (AUDIT-P8-LOW P8-5); overlay.log and run.log
bounded, same stamp format. Releases 3 loop-owned rows.

- Session 6; width 13 worktree + 0 main-checkout, 3 loop rows released;
  about 143 minutes.
- Hotspots: web/index.html (RUN-VERDICTS-UI); server/al/core.py
  (RUN-LADDER-TICK); web/app.js (RUN-VERDICTS-UI); server/al/http.py
  (RUN-SUPERVISOR-CLOCK); app/main.js (RUN-OBS-LOGS-SHELL);
  tests/test_security_surface.py (RUN-VERDICTS-UI); app/client/window.js
  (RUN-OBS-LOGS-SHELL); scripts/run.ps1 (RUN-OBS-LOGS-SHELL);
  server/al/keepalive.py (RUN-SUPERVISOR-CLOCK); app/test/client.test.js
  (RUN-OBS-LOGS-SHELL); scripts/setup.ps1 (DATA-SNAP-SETUP);
  app/shared/render_gate.js (TEST-STATE-TEXT-PINS); app/test/checks.test.js
  (RUN-VERDICTS-UI); docs/design/0001-design-system.md
  (TEST-STATE-TEXT-PINS); tests/test_keepalive.py (RUN-SUPERVISOR-CLOCK);
  web/checks.js (RUN-VERDICTS-UI); web/prices.js (TEST-STATE-TEXT-PINS);
  server/al/ninja.py (DATA-PRICE-SHAPE-GUARD); server/al/pricebook.py
  (DATA-PRICE-SHAPE-GUARD); tools/tc_drift.py (TC-BUILDFILE-EXIT-WATCH).
- Integrator: ROADMAP.md rows of all 16 packages; CLAUDE.md:
  RUN-SUPERVISOR-CLOCK; AL-NEXT-SESSION.txt: TEST-STATE-TEXT-PINS;
  docs/design/reviews.log: 3 lines.
- Batches: 1: RUN-VERDICTS-UI, RUN-LADDER-TICK, RUN-OBS-LOGS-SHELL,
  RUN-SUPERVISOR-CLOCK; 2: REL-BUILD-ASSETS, DATA-PRICE-SHAPE-GUARD,
  TEST-STATE-TEXT-PINS, REL-UPDATE-LAUNCH; 3: DATA-SNAP-PROBE,
  OVL-CLIENT-GUARD, PUB-GUIDE-PAGES, DATA-RESEARCH-GAPS; 4: PUB-DEPBOT-NPM.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- RUN-VERDICTS-UI [session, L 90m, build, P1, DR] 'Tried in game' card on the Checks tool + The report is built on the click by GET /api/report and shown in a preview first. Files: web/index.html, web/app.js, web/checks.js, app/test/checks.test.js, tests/test_security_surface.py (+4 more). Deps: RUN-VERDICTS-CORE, RUN-LEDGER-WIRE, RUN-BUILD-STAMP-CORE.
- RUN-LADDER-TICK [session, M 30m, build, P2] Map ladder tick is free when nothing changed (AUDIT-P8-LOW P8-5). Files: server/al/mapladder.py, server/al/core.py, tests/test_util_map_ladder.py, tests/test_budgets.py. Deps: RUN-DURABLE-STORES, RUN-LEDGER-WIRE.
- RUN-OBS-LOGS-SHELL [session, L 90m, build, P2, DR] overlay.log and run.log bounded, same stamp format + run.ps1 and the client's failed page print the start error; client port check (P8-3) + The cli. Files: app/main.js, scripts/run.ps1, scripts/stop.ps1, app/client/window.js, app/client/starting.html (+8 more). Deps: RUN-OBS-LOGS-PY, RUN-BUDGET-LOG-CLIENT, RUN-START-REASON-CORE.
- RUN-SUPERVISOR-CLOCK [session, M 60m, build, P2] Supervisor liveness verdict that cannot misfire. Files: server/al/keepalive.py, server/al/http.py, tests/test_keepalive.py, tests/test_supervisor.py, docs/decisions/0005-core-keepalive.md (+2 more). Deps: RUN-OBS-LOGS-PY, RUN-METRICS-CORE, RUN-SEAMS, RUN-LEDGER-WIRE.
- REL-BUILD-ASSETS [session, L 70m, build, P1] Release build: release.json, stamped installer, notes, SBOM, SHA256SUMS. Files: tools/rel_build.py, tools/rel_assets.py, tests/test_release_assets.py. Deps: DEP-08, REL-SBOM, DATA-PRICE-CADENCE.
- DATA-PRICE-SHAPE-GUARD [session, M 50m, build, P2] A silent poe.ninja shape change keeps the last good prices. Files: server/al/pricebook.py, server/al/ninja.py, tests/test_price_shape_guard.py. Deps: DATA-DIAG-SEAM, DATA-PRICE-CADENCE.
- TEST-STATE-TEXT-PINS [session, M 45m, build, P2, DR] Point the design gate, the reviewer agent, the lane prompt and design 0001 at server/al/text/. Files: tools/design_gate.py, tests/test_design_gate.py, tools/loop_prompts.py, .claude/agents/design-reviewer.md, docs/design/0001-design-system.md (+9 more). Deps: TEST-STATE-TEXT-4, TEST-WAVE-GATE-POLICY.
- REL-UPDATE-LAUNCH [session, M 55m, build, P1] Client launcher: apply a staged update before the core starts. Files: app/client/launcher.js, app/test/launcher.test.js. Deps: REL-UPDATE-SWITCH, REL-RUNTIME-SCRIPTS, REL-CLIENT-HOME.
- DATA-SNAP-PROBE [session, L 80m, build, P2] Probe each fetched snapshot file before it replaces the cached one. Files: server/al/theorycraft/snapshot.py, tests/test_tc_snap.py, server/al/theorycraft/snapprobe.py, tests/test_snap_probe.py. Deps: DATA-TREE-HOLD, DATA-DIAG-SEAM.
- OVL-CLIENT-GUARD [session, M 60m, build, P2] CLIENT-GUARD: the client survives its own errors without a dialog and rebuilds a dead overlay or companion page. Files: app/crashguard.js, app/parts/05-crashguard.js, app/test/crashguard.test.js, tests/test_overlay_smoke.py, app/test/audit_electron.test.js. Deps: OVL-MAIN-PARTS.
- PUB-GUIDE-PAGES [session, M 60m, build, P2] Four-page player guide. Files: docs/guide/download.md, docs/guide/quick-start.md, docs/guide/common-issues.md, docs/guide/faq.md, tests/test_player_guide.py. Deps: PUB-README-PLAYERS.
- DATA-RESEARCH-GAPS [session, M 60m, data] Research gaps: triage table for note 0056 and the adopted-patterns register of note 0055. Files: docs/research/0056-third-party-repo-review.md, docs/research/0055-competitive-companions-overlays.md. Deps: GP-01.
- PUB-DEPBOT-NPM [session, M 60m, data, P1] Dependabot re-apply tool: the npm branch. Files: tools/dependabot_reapply.py, tests/test_dependabot_reapply.py, tests/fixtures/dependabot/pr_npm.json. Deps: PUB-DEPBOT-ACTIONS, OVL-NPM-LOCK.
- DATA-SNAP-SETUP [loop, S 25m, build, P1] setup.ps1 runs the game-data snapshot when web data is already on. Files: scripts/setup.ps1, tests/test_setup_snapshot.py. Deps: REL-RUNTIME-SCRIPTS.
- DATA-TRADESTAT-COVERAGE [loop, M 35m, build, P3] Count trade stat id coverage per source before retiring the PoB fallback. Files: server/al/tradestats.py, server/al/upgrade.py, tests/test_math_tradestat_local.py. Deps: DATA-DIAG-SEAM, TC-UPGRADE-PER-SLOT.
- TC-BUILDFILE-EXIT-WATCH [loop, M 35m, review, P3] .build exit trigger from the PoB release check. Files: tools/tc_drift.py, tests/test_tc_drift.py, docs/decisions/0034-build-file-download.md. Deps: TC-CALC-VERIFY-PIN, AUTO-12, AUTO-05, LOOP-DRIFT-REF.

### Wave 20: overlay and client, install and release, tests and code seams

Goal: Milestones: the bootstrap installer exists. Leads: Overlay slider sets
the plate alpha only: limits 0.80 to 1.0, default 0.86, saved layou...;
Overlay view seam (server/al/overlayview.py) with the card-slot holder order
and the 10...; Release stage: the PASS / FAIL report (static gates).

- Session 6; width 13 worktree + 0 main-checkout, 0 loop rows released;
  about 110 minutes (TEST-SHOTS-TABS joined at the wave 18 start, session
  16).
- Hotspots: web/index.html (OVL-TD05-PLATE); server/al/core.py
  (OVL-CARD-SLOT); web/app.js (TEST-WEB-PANELS-A); server/al/http.py
  (OVL-CARD-SLOT); server/al/state.py (OVL-CARD-SLOT);
  tests/test_ux_review.py (OVL-TD05-PLATE); app/main.js (SEC-HELLO-CLIENT);
  tests/test_security_surface.py (OVL-CARD-SLOT); scripts/run.ps1
  (RUN-SECOND-LINE-PY); server/al/keepalive.py (RUN-SECOND-LINE-PY);
  app/test/client.test.js (SEC-HELLO-CLIENT); tests/test_ux_settings_io.py
  (OVL-TD05-PLATE); server/al/ninja.py (DATA-NINJA-SHAPE-WATCH);
  server/al/pricebook.py (DATA-NINJA-SHAPE-WATCH).
- Integrator: ROADMAP.md rows of all 13 packages; CLAUDE.md:
  RUN-SECOND-LINE-PY, TC-PRESS-SAMPLES; docs/design/reviews.log: 3 lines.
- Batches: 1: OVL-TD05-PLATE, OVL-CARD-SLOT, DEP-12, TEST-WEB-PANELS-A; 2:
  DEP-09, RUN-SECOND-LINE-PY, DATA-NINJA-SHAPE-WATCH, TEST-STRUCTURE-GUARD;
  3: SEC-HELLO-CLIENT, AUTO-10, TC-PRESS-SAMPLES, AUTO-18; 4: TEST-SHOTS-TABS.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- OVL-TD05-PLATE [session, M 45m, build, P2, DR] Overlay slider sets the plate alpha only: limits 0.80 to 1.0, default 0.86, saved layouts migrate once (TD-05, part 2). Files: app/shared/layout.js, server/al/layout.py, web/index.html, app/test/layout.test.js, tests/test_overlay_layout.py (+2 more). Deps: OVL-TD05-LEGIBILITY, OVL-OVERLAY-KEYS.
- OVL-CARD-SLOT [session, L 70m, build, P2, DR] Overlay view seam (server/al/overlayview.py) with the card-slot holder order and the 10 s sample card. Files: server/al/state.py, server/al/http.py, server/al/core.py, tests/test_security_surface.py, server/al/overlayview.py (+1 more). Deps: SEC-SURFACE-PIN.
- DEP-12 [session, M 60m, build, P1] Release stage: the PASS / FAIL report (static gates). Files: tools/rel_stage.py, tests/test_release_stage.py. Deps: REL-BUILD-ASSETS.
- TEST-WEB-PANELS-A [session, L 75m, build, P2, DR] Panel move A: the loaded-build block to web/panels/build.js. Files: web/app.js, web/panels/build.js, app/test/panels.test.js, tests/test_webpage.py, tests/test_srcpaths.py. Deps: TEST-WEB-ASSEMBLE, PLAY-TD-19D-ITEMS-GRID.
- DEP-09 [session, L 70m, build, P1] Bootstrap install.ps1. Files: scripts/install.ps1, tests/test_install_ps1.py. Deps: REL-INSTALL-CMD, REL-BUILD-ASSETS.
- RUN-SECOND-LINE-PY [session, M 60m, build, P2] Nothing stays down: supervisor adopted at start, core restarts a missing supervisor. Files: scripts/run.ps1, server/al/keepalive.py, server/al/procs.py, tests/test_supervisor.py, tests/test_procs.py (+3 more). Deps: RUN-SUPERVISOR-CLOCK, RUN-OBS-LOGS-SHELL.
- DATA-NINJA-SHAPE-WATCH [session, L 75m, build, P2] poe.ninja drift detection in the core: signatures, baseline, league checks. Files: server/al/pricebook.py, server/al/ninja.py, server/al/ninjashape.py, server/al/data/ninja_read_keys.json, tests/test_ninja_shape.py. Deps: DATA-PRICE-SHAPE-GUARD, DATA-LEAGUE-IDENTITY, DATA-DIAG-SEAM.
- TEST-STRUCTURE-GUARD [session, M 45m, build, P3] Structure test: acyclic server imports, player text under a gate path. Files: tests/test_structure.py. Deps: TEST-STATE-TEXT-PINS.
- SEC-HELLO-CLIENT [session, L 70m, build, P2] The Electron client verifies the core before it sends anything. Files: app/main.js, app/eval_hotkey.js, app/client/link.js, app/test/client.test.js, app/hello.js (+3 more). Deps: SEC-HELLO-CORE, RUN-OBS-LOGS-SHELL.
- AUTO-10 [session, M 55m, build, P2] NINJA-WATCH: the poe.ninja docs page and the shape-drift flag. Files: tools/watch_sources/ninja_docs.py, tools/watch_sources/ninja_shape.py, ops/loop/watch_rows/ninja.json, tests/test_watch_ninja.py. Deps: AUTO-05, LOOP-WATCH-ROWS.
- TC-PRESS-SAMPLES [session, M 55m, build, P2] Dev-host capture of sanitized item-press samples. Files: docs/decisions/0045-per-character-build.md, server/al/theorycraft/cardparts/sample.py, tools/press_samples.py, tests/test_press_samples.py. Deps: TC-CARD-PARTS.
- AUTO-18 [session, M 55m, build] LEDGER-SOURCE: live log shapes and snapshot probe results become rows. Files: tools/al_lane.py, tools/watch_sources/ledger.py, ops/loop/watch_rows/ledger.json, tests/test_watch_ledger.py. Deps: AUTO-05, LOOP-WATCH-ROWS, LOOP-WATCH-FILE, LOOP-ROWFILES-WORK, LOOP-USAGE-LABEL.
- TEST-SHOTS-TABS [session, M 60m, build, P2] Screenshots of the Build, Run and Settings tabs and the overlay page. Files: app/test/cdp/capture.mjs, tools/shots.py, tests/test_shots.py, tests/test_capture_helper.py. Deps: AUTO-15, TEST-CAPTURE-HELPER.

### Wave 21: overlay and client, install and release, reliability and observability

Goal: Milestones: the release stage round trip (install, update, rollback,
uninstall) passes. Leads: Run grid 1: Acts, Maps and Deaths cards; Quiet
feed: no minute stamp or report text in the snapshot, ages stepped at 5
minutes; Zone moment card in the one card slot, and the guide-line fields
for HUD line 2.

- Session 6; width 15 worktree + 0 main-checkout, 0 loop rows released;
  about 125 minutes (PLAY-TD-19E-ITEM-TEXT and REL-HOME-REFUSAL-UI joined
  at the wave 18 start, session 16; REL-INSTALLED-RUN-CHECK joined by
  ruling Q2, 2026-11-21).
- Hotspots: web/index.html (PLAY-TD-20A-RUN-GRID); server/al/core.py
  (RUN-QUIET-FEED); server/al/state.py (RUN-QUIET-FEED); web/app.css
  (PLAY-TD-20A-RUN-GRID); server/al/diag.py (RUN-QUIET-FEED);
  tests/test_diag_self.py (RUN-QUIET-FEED); README.md (DEP-14);
  app/shared/render_gate.js (OVL-LINE2-RULE); app/test/checks.test.js
  (RUN-QUIET-FEED); web/checks.js (RUN-QUIET-FEED); web/app.js
  (PLAY-TD-19E-ITEM-TEXT); app/main.js (REL-HOME-REFUSAL-UI).
- Integrator: ROADMAP.md rows of all 15 packages; CLAUDE.md:
  REL-PUBLISH-GATES; docs/decisions/README.md: REL-PUBLISH-GATES;
  docs/design/reviews.log: 5 lines.
- Batches: 1: PLAY-TD-20A-RUN-GRID, RUN-QUIET-FEED, OVL-ZONE-CARD,
  OVL-LINE2-RULE; 2: REL-PUBLISH-GATES, REL-STAGE-ROUNDTRIP, RUN-STOP-RACE,
  OVL-CHECK; 3: OVL-CONTRAST-PIXELS, DEP-14, AUTO-08, AUTO-17; 4:
  PLAY-TD-19E-ITEM-TEXT, REL-HOME-REFUSAL-UI, REL-INSTALLED-RUN-CHECK.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- PLAY-TD-20A-RUN-GRID [session, L 90m, build, DR] Run grid 1: Acts, Maps and Deaths cards. Files: web/index.html, web/app.css, web/acts.js, web/runs.js, app/test/acts.test.js (+1 more). Deps: PLAY-TD-19D-ITEMS-GRID.
- RUN-QUIET-FEED [session, M 60m, build, P2, DR] Quiet feed: no minute stamp or report text in the snapshot, ages stepped at 5 minutes. Files: server/al/diag.py, server/al/core.py, server/al/state.py, web/checks.js, app/test/checks.test.js (+2 more). Deps: RUN-VERDICTS-UI, RUN-LADDER-TICK, RUN-ZONE-RESET.
- OVL-ZONE-CARD [session, L 80m, build, P2, DR] Zone moment card in the one card slot, and the guide-line fields for HUD line 2. Files: server/al/overlayview.py, tests/test_overlay_view.py, tests/test_moment_cards.py. Deps: OVL-CARD-SLOT, OVL-OVERLAY-KEYS, OVL-GLANCE-RULES, PLAY-TD-08A-GUIDE-SHORT-FIELD, RUN-ZONE-RESET, PLAY-TD-07A-PLAY-VIEW.
- OVL-LINE2-RULE [session, M 50m, build, P2, DR] Overlay HUD line 2: one priority order with the 26-character rule (hudLine2). Files: app/shared/render_gate.js, app/shared/format.js, app/test/layout.test.js, app/test/hudline2.test.js. Deps: OVL-PARTS-PAGE, OVL-TD05-PLATE, PLAY-TD-02-SLOTS, PLAY-F-131-STATUS-TABLE.
- REL-PUBLISH-GATES [session, L 85m, build, P1] Publish gates: the operator phrase, the refusals, rehearse and prepush-check. Files: tools/rel_publish.py, config/release.json, tests/test_release_gates.py, docs/decisions/0073-versioning-release-trigger.md. Deps: DEP-12.
- REL-STAGE-ROUNDTRIP [session, L 75m, build, P1] Release stage: scratch-home install, update, rollback, uninstall. Files: tools/rel_stage.py, tests/test_release_stage.py. Deps: DEP-12, DEP-09, REL-UNINSTALL-SHELL, REL-UPDATE-SWITCH.
- RUN-STOP-RACE [session, M 30m, build, P3] Stop only what was running when stop was asked. Files: server/al/procs.py, scripts/stop.ps1, tests/test_procs.py. Deps: RUN-SECOND-LINE-PY, RUN-OBS-LOGS-SHELL.
- OVL-CHECK [session, L 75m, build, P1] OVL-CHECK: developer tool that runs the in-map overlay check as one normally played map. Files: docs/decisions/0006-fps-measurement-method.md, tools/ovl_check.py, tests/test_ovl_check.py. Deps: OVL-CARD-SLOT, OVL-PARTS-PAGE, RUN-BUDGET-LOG-CORE, RUN-BUDGET-LOG-CLIENT, RUN-VERDICTS-UI.
- OVL-CONTRAST-PIXELS [session, M 60m, review, P2] Contrast gate measures rendered pixels: glyph core against the plate over white and a 2 px checker; rendered widths of the worst-case lines. Files: app/test/cdp/overlay_pixels.mjs, tests/test_overlay_pixels.py. Deps: OVL-TD05-PLATE, TEST-CAPTURE-HELPER, SEC-DEMO-ENTRY.
- DEP-14 [session, M 50m, build, P2] Player docs: install, update, uninstall, verify, 'Windows may warn'. Files: README.md, SECURITY.md, THIRD-PARTY.md, tests/test_readme.py. Deps: DEP-02, DEP-03, REL-RUNTIME-PINS, DEP-09, REL-UNINSTALL-SHELL, PUB-README-PLAYERS.
- AUTO-08 [session, M 45m, build, P2] WATCH-HEALTH: a broken watcher is itself a finding. Files: tools/watch_sources/health.py, ops/loop/watch_rows/health.json, tools/loop_steps/watch_health.py, tests/test_watch_health.py. Deps: AUTO-01, AUTO-05, LOOP-WATCH-ROWS.
- AUTO-17 [session, M 45m, build] REFRESH-SOURCE: stale docs, screenshots and an unplanned release become rows. Files: tools/watch_sources/refresh.py, ops/loop/watch_rows/refresh.json, tests/test_watch_refresh.py. Deps: AUTO-05, LOOP-WATCH-ROWS, LOOP-WAVE-HOLD.
- PLAY-TD-19E-ITEM-TEXT [session, M 45m, build, P2, DR] Build card: each worn item's raw item text on a Full text page. Files: web/app.js, tests/test_build_item_text.py. Deps: PLAY-TD-19C-BUILD-GRID, PLAY-TD-19D-ITEMS-GRID.
- REL-HOME-REFUSAL-UI [session, S 30m, build, P2] Show the refused-home sentence before the client exits. Files: app/main.js, app/client/home.js, app/test/home.test.js. Deps: REL-CLIENT-HOME, REL-RUNTIME-SCRIPTS.
- REL-INSTALLED-RUN-CHECK [session, M 45m, build, P2] Installed copy: run.ps1 verifies electron.exe without tools/electron_pin.py and names the installer. Files: scripts/run.ps1, tests/test_install_shell.py. Deps: REL-RUNTIME-SCRIPTS.

### Wave 22: install and release, reliability and observability, overlay and client

Goal: Leads: Run grid 2: Recent, Last session and Characters cards; The
report from an allow-list of structured fields, with a hardened redactor
(P8-7); Overlay HUD line 2: the opt-in guide line and the fixed card anchor.

- Session 7; width 18 worktree + 0 main-checkout, 0 loop rows released;
  about 143 minutes (LOOP-CI-ISSUES joined at the wave 18 start, session
  16; CARD-LINE-LIMIT, BUILD-GEAR-EMPTY-COPY, DEP14-UNINSTALL-LINE and
  HOME-REFUSAL-COPY joined, ZONE-CARD-ITEM-GATE folded into
  OVL-LINE2-GUIDE and REPORT-DOC-QUIET into RUN-REPORT-FIELDS by the
  W22-FOLD ruling, session 18).
- Hotspots: web/index.html (PLAY-TD-20B-RUN-CARDS); server/al/core.py
  (REL-UPDATE-WIRE); web/app.js (PLAY-TD-20B-RUN-CARDS); server/al/http.py
  (REL-UPDATE-WIRE); server/al/state.py (REL-UPDATE-WIRE); web/app.css
  (PLAY-TD-20B-RUN-CARDS); server/al/diag.py (RUN-REPORT-FIELDS);
  app/client/window.js (RUN-SECOND-LINE-CLIENT); app/test/client.test.js
  (RUN-SECOND-LINE-CLIENT); app/shared/render_gate.js (OVL-LINE2-GUIDE);
  app/test/checks.test.js (RUN-REPORT-FIELDS); web/checks.js
  (RUN-REPORT-FIELDS); server/al/settingsio.py (REL-UPDATE-WIRE);
  README.md (DEP14-UNINSTALL-LINE); docs/design/0001-design-system.md
  (HOME-REFUSAL-COPY).
- Integrator: ROADMAP.md rows of all 18 packages; CLAUDE.md:
  REL-UPDATE-WIRE; docs/design/reviews.log: 8 lines.
- Batches: 1: PLAY-TD-20B-RUN-CARDS, RUN-REPORT-FIELDS, OVL-LINE2-GUIDE,
  OVL-ACT-CARD; 2: RUN-BUDGET-TESTS-DET, OVL-TD06-AUTOSCALE, DEP-15,
  REL-UPDATE-WIRE; 3: REL-PUBLISH-READBACK, REL-STAGE-SANDBOX, DEP-19,
  RUN-SECOND-LINE-CLIENT; 4: PUB-HOOK-RELEASE-CHECK, LOOP-CI-ISSUES,
  CARD-LINE-LIMIT, BUILD-GEAR-EMPTY-COPY; 5: DEP14-UNINSTALL-LINE,
  HOME-REFUSAL-COPY.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- PLAY-TD-20B-RUN-CARDS [session, L 80m, build, P1, DR] Run grid 2: Recent, Last session and Characters cards. Files: web/index.html, web/app.css, web/app.js, web/history.js, web/chars.js (+4 more). Deps: PLAY-TD-20A-RUN-GRID.
- RUN-REPORT-FIELDS [session, L 90m, build, P2, DR] The report from an allow-list of structured fields, with a hardened redactor (P8-7) + Keep per-press 'Not counted' lines for the session. Files: server/al/diag.py, server/al/plug/report.py, web/checks.js, app/test/checks.test.js, server/al/theorycraft/live.py (+4 more). Deps: RUN-QUIET-FEED, RUN-METRICS-CORE, RUN-LEDGER-WIRE, RUN-BUDGET-LOG-CORE, GP-06, OVL-OBS-CRASH, TC-PRESS-STAGED-LIVE.
- OVL-LINE2-GUIDE [session, L 75m, build, P2, DR] Overlay HUD line 2: the opt-in guide line and the fixed card anchor. Files: app/shared/render_gate.js, app/overlay/index.html, app/overlay/overlay.js, app/overlay/overlay.css, app/test/overlay_gate.test.js (+1 more). Deps: OVL-LINE2-RULE, OVL-ZONE-CARD, OVL-TD05-LEGIBILITY.
- OVL-ACT-CARD [session, M 40m, build, P2, DR] Act moment card: 12 s when an act split closes, with the gap to the saved best. Files: server/al/overlayview.py, server/al/text/overlaycard.py, tests/test_moment_cards.py, tests/test_overlay_view.py. Deps: OVL-ZONE-CARD.
- RUN-BUDGET-TESTS-DET [session, M 60m, build, P2] Deterministic budget tests: tick cost, idle tick, snapshot size, real loop body. Files: tests/test_budgets.py, tests/test_budget_tick.py, tests/test_budget_snapshot.py. Deps: RUN-LADDER-TICK, RUN-QUIET-FEED.
- OVL-TD06-AUTOSCALE [session, S 25m, build, P3, DR] Overlay physical size: autoScale reference 1200 DIP, budgets re-run (TD-06). Files: app/shared/layout.js, app/test/layout.test.js. Deps: OVL-TD05-PLATE, OVL-LINE2-RULE.
- DEP-15 [session, M 60m, build, P1] Tag-triggered release workflow (file half). Files: .github/workflows/release.yml, tests/test_workflows.py. Deps: REL-BUILD-ASSETS, REL-PUBLISH-GATES, DEP-04, GP-05.
- REL-UPDATE-WIRE [session, M 45m, build, P1] Update check in the core: acknowledgement, tick and snapshot block. Files: server/al/core.py, server/al/http.py, server/al/state.py, server/al/settingsio.py, docs/decisions/0013-web-data.md (+1 more). Deps: DEP-16, DEP-05.
- REL-PUBLISH-READBACK [session, M 50m, build, P1] Publish read-back: release, tag, digests, attestation. Files: tools/rel_publish.py, tools/rel_readback.py, tests/test_release_readback.py. Deps: REL-PUBLISH-GATES.
- REL-STAGE-SANDBOX [session, M 40m, build, P1] Release stage: optional Windows Sandbox phases. Files: tools/rel_stage.py, tests/test_release_stage.py. Deps: REL-STAGE-ROUNDTRIP.
- DEP-19 [session, M 45m, build] CPython pin watch. Files: tools/watch_sources/cpython.py, ops/loop/watch_rows/cpython.json, tests/test_watch_cpython.py. Deps: REL-RUNTIME-PINS, AUTO-05, LOOP-WATCH-ROWS, AUTO-09.
- RUN-SECOND-LINE-CLIENT [session, M 30m, build, P2] The client restarts a core that stays down. Files: app/client/window.js, app/client/launcher.js, app/test/client.test.js. Deps: RUN-OBS-LOGS-SHELL, RUN-SECOND-LINE-PY.
- PUB-HOOK-RELEASE-CHECK [session, S 25m, build, P1] Guarded hook: refuse a v* tag without a PASS stage report. Files: .githooks/pre-push, tests/test_pre_push_hook.py, tests/test_fleet_kit_conformance.py. Deps: GP-02, REL-PUBLISH-GATES.
- LOOP-CI-ISSUES [session, M 50m, build, P2] CI-WATCH (tick half): read the key issues, fail over when CI is silent. Files: tools/watch_sources/ci_issues.py, ops/loop/watch_rows/ci.json, tests/test_watch_ci_issues.py, tools/watch_gate.py, tests/test_watch_gate.py, docs/decisions/0069-upstream-watch-frame.md. Deps: AUTO-19, LOOP-WATCH-ROWS, LOOP-WATCH-FILE, AUTO-08, LOOP-WATCH-GATE.
- CARD-LINE-LIMIT [session, M 40m, build, P2, DR] Card lines fit the 236 px inside width: lower the card character limit. Files: app/shared/format.js, server/al/text/common.py, tests/test_overlay_pixels.py. Deps: OVL-CONTRAST-PIXELS.
- BUILD-GEAR-EMPTY-COPY [session, S 20m, build, P3, DR] Build card empty-gear row says what to do next. Files: web/panels/build.js, tests/test_build_item_text.py. Deps: PLAY-TD-19E-ITEM-TEXT.
- DEP14-UNINSTALL-LINE [session, S 20m, build, P2] README Quick start names the uninstall step. Files: README.md, tests/test_public_docs.py. Deps: DEP-14.
- HOME-REFUSAL-COPY [session, M 60m, build, P2, DR] Refused-home sentence, design 0001 start-up exception and wording, plan 03 section 5.1 widths and line 2 rule. Files: server/al/paths.py, app/client/home.js, app/test/home.test.js, docs/design/0001-design-system.md, docs/plan/03-target-design.md. Deps: REL-HOME-REFUSAL-UI, OVL-CONTRAST-PIXELS, OVL-LINE2-RULE, PLAY-TD-20A-RUN-GRID.

### Wave 23: install and release, overlay and client, tests and code seams

Goal: Leads: Settings rail 1: Checks, Reading and web data, Overlay; Move
the overlay page and the starting page off file:// onto one app scheme;
Teach the item-check key in the empty card slot, then retire it.

- Session 7; width 13 worktree + 1 main-checkout, 0 loop rows released;
  about 125 minutes.
- Hotspots: web/index.html (PLAY-TD-21A-SETTINGS-RAIL); server/al/core.py
  (REL-UPDATE-CHECKS); web/app.js (PLAY-TD-21A-SETTINGS-RAIL);
  server/al/http.py (OVL-APP-SCHEME); web/app.css
  (PLAY-TD-21A-SETTINGS-RAIL); server/al/diag.py (REL-UPDATE-CHECKS);
  tests/test_ux_review.py (PLAY-TD-21A-SETTINGS-RAIL); app/main.js
  (OVL-APP-SCHEME); app/client/window.js (OVL-APP-SCHEME); scripts/run.ps1
  (SEC-HELLO-PS); tests/test_diag_self.py (REL-UPDATE-CHECKS); README.md
  (TEST-SHOTS-RENDER); tests/test_ux_b8.py (PLAY-TD-21A-SETTINGS-RAIL);
  app/shared/render_gate.js (OVL-KEY-HINT); app/test/checks.test.js
  (PLAY-TD-21A-SETTINGS-RAIL); docs/design/0001-design-system.md
  (TEST-COPY-SHEETS); web/checks.js (PLAY-TD-21A-SETTINGS-RAIL);
  tests/test_http_security.py (OVL-APP-SCHEME).
- Integrator: ROADMAP.md rows of all 14 packages; docs/design/reviews.log: 3
  lines.
- Watch: tests/test_ux_review.py (PLAY-TD-21A-SETTINGS-RAIL edits,
  REL-UPDATE-CHECKS runs).
- Batches: 1: PLAY-TD-21A-SETTINGS-RAIL, OVL-APP-SCHEME, OVL-KEY-HINT,
  DEP-17; 2: RUN-BUDGET-TESTS-DASH, REL-UPDATE-CHECKS, SEC-HELLO-PS,
  TEST-SHOTS-RENDER; 3: AUTO-16, AUTO-13, TEST-COPY-SHEETS, AUTO-22; 4: PUB-DEPBOT-FIRST-RUN, RUN-LIVE1-FIXTURES.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- PLAY-TD-21A-SETTINGS-RAIL [session, L 90m, build, P1, DR] Settings rail 1: Checks, Reading and web data, Overlay. Files: web/index.html, web/app.css, web/app.js, web/checks.js, app/test/checks.test.js (+4 more). Deps: PLAY-TD-20B-RUN-CARDS.
- OVL-APP-SCHEME [session, L 70m, build, P3, DR] Move the overlay page and the starting page off file:// onto one app scheme. Files: app/main.js, app/client/window.js, app/egress.js, app/overlay/index.html, app/client/starting.html (+8 more). Deps: OVL-SHELL-GUARDS, OVL-EGRESS-LOCK, OVL-WAKE-COMPANION, OVL-LINE2-GUIDE, OVL-KEYS-CORE, SEC-STATIC-MAP.
- OVL-KEY-HINT [session, M 60m, build, P2, DR] Teach the item-check key in the empty card slot, then retire it. Files: server/al/overlayview.py, app/shared/render_gate.js, app/overlay/overlay.css, tests/test_overlay_view.py, app/test/keyhint.test.js. Deps: OVL-KEYS-CORE, OVL-ACT-CARD, OVL-LINE2-GUIDE.
- DEP-17 [session, L 80m, build, P1] Update, network half: download, verify and stage from a release. Files: server/al/install/update.py, tests/test_updater.py. Deps: DEP-11, DEP-16, DEP-15, REL-UPDATE-SWITCH.
- RUN-BUDGET-TESTS-DASH [session, L 85m, build, P2] Dashboard and overlay paint budgets under test (B13, B14) + P8-6: the console / CSP test paints Checks rows, a hint and ladder_all. Files: app/test/shared.test.js, tests/test_dash_console.py, app/test/cdp/dash_console.mjs, tests/test_dash_perf.py, app/test/cdp/dash_perf.mjs. Deps: RUN-VERDICTS-UI, PLAY-TD-01B-FIT-HARNESS, RUN-QUIET-FEED.
- REL-UPDATE-CHECKS [session, M 45m, build, P1] Checks row and report lines for the install. Files: server/al/diag.py, server/al/core.py, tests/test_diag_self.py, tests/test_update_checks.py. Deps: REL-UPDATE-SWITCH, PLAY-F-131-STATUS-TABLE.
- SEC-HELLO-PS [session, S 30m, build, P2] run.ps1 verifies the core before it sends the token or opens the page. Files: scripts/run.ps1, tests/test_run_health_ps.py. Deps: SEC-HELLO-CORE, SEC-NO-PROXY.
- TEST-SHOTS-RENDER [session, M 30m, data, P2] First screenshot render and the README image block. Files: README.md, docs/shots/manifest.json. Deps: AUTO-15, PUB-README-PLAYERS.
- AUTO-16 [session, S 25m, build, P2] REL-NOTES: notes --count and the REL-PREP row text. Files: tools/rel_notes.py, tests/test_release_notes.py. Deps: DEP-04, AUTO-01.
- AUTO-13 [session, M 60m, build, P3] DIVE-ON-DEMAND: a source may request one dive a day; the idle dive is weekly. Files: tools/loop_roadmap.py, tests/test_loop_dive.py, tools/loop_steps/dive_request.py, tests/test_loop_dive_request.py. Deps: AUTO-01, AUTO-04, AUTO-05, LOOP-ROWFILES-WORK, LOOP-TESTS-CARVE.
- TEST-COPY-SHEETS [session, M 50m, build, P3] Split design 0001 section 9 rule 2 into docs/design/copy/<family>.md. Files: docs/design/0001-design-system.md, .claude/agents/design-reviewer.md, tests/test_structure.py, docs/design/copy/events.md, docs/design/copy/price.md (+4 more). Deps: TEST-STRUCTURE-GUARD.
- AUTO-22 [session, M 45m, build, P3] OVL-SMOKE-DAILY: the tick runs the live overlay smoke once a day while the game is idle. Files: tools/loop_steps/overlay_smoke.py, tests/test_loop_overlay_smoke_step.py. Deps: AUTO-01, SEC-NO-PROXY.
- PUB-DEPBOT-FIRST-RUN [session, S 20m, data, P1] First live run of the Dependabot re-apply tool. Files: none. Deps: GP-09, PUB-DEPBOT-ACTIONS, GP-08.
- RUN-LIVE1-FIXTURES [session, M 60m, build, P1] Turn each live-verified log shape into a fixture line and a test. Files: tests/fixtures/client_live_shapes.txt, tests/test_parser.py, server/al/parser.py. Deps: RUN-LEDGER-WIRE, RUN-LEDGER-REPORT.

### Wave 24: reliability and observability, web data, theorycraft

Goal: Leads: Contact field in the web-data card and honest blocked wording;
Five cause rows in Checks; Core refuses Origin null and file:// once both
local pages load from the app scheme.

- Session 7; width 13 worktree + 1 main-checkout, 0 loop rows released;
  about 190 minutes (PLAY-PAGER-SCALE-24 joined by ruling Q2 as amended,
  2026-11-21; RUN-UNREADABLE-WORD joined by UNREADABLE-RETAG, session 18:
  waves 22 and 23 own render_gate.js, diag.py or design 0001).
- Hotspots: web/index.html (DATA-CONTACT-UI); server/al/core.py
  (TC-WEIGHTS-DELTA-EXPORT); web/app.js (DATA-CONTACT-UI); server/al/http.py
  (OVL-APP-SCHEME-STRICT); app/main.js (RUN-OVERLAY-REMEMBER); README.md
  (TEST-SLOW-BUDGET); app/test/checks.test.js (RUN-EXPLAIN-ROWS);
  web/prices.js (DATA-CONTACT-UI); server/al/settingsio.py
  (TC-WEIGHTS-DELTA-EXPORT); tests/test_http_security.py
  (OVL-APP-SCHEME-STRICT); tests/test_ux_settings_io.py
  (TC-WEIGHTS-DELTA-EXPORT); app/test/prices.test.js (DATA-CONTACT-UI);
  server/al/pricebook.py (DATA-PRICE-TYPES-FILE); server/al/diag.py,
  app/shared/render_gate.js, docs/design/0001-design-system.md
  (RUN-UNREADABLE-WORD).
- Integrator: ROADMAP.md rows of all 14 packages; CLAUDE.md:
  OVL-APP-SCHEME-STRICT, RUN-BUDGET-TESTS-LIVE, TC-PIN-POLICY;
  AL-NEXT-SESSION.txt: REL-CUTOVER-LIVE; docs/design/reviews.log: 5 lines.
- Batches: 1: DATA-CONTACT-UI, RUN-EXPLAIN-ROWS, OVL-APP-SCHEME-STRICT,
  TC-WEIGHTS-DELTA-EXPORT; 2: RUN-BUDGET-TESTS-LIVE, TEST-SLOW-BUDGET,
  DATA-PRICE-TYPES-FILE, TC-PIN-POLICY; 3: RUN-HISTORY-UNDO,
  RUN-OVERLAY-REMEMBER, DATA-SNAP-TRIM, PLAY-PAGER-SCALE-24; 4:
  RUN-UNREADABLE-WORD.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean; REL-CUTOVER-LIVE runs alone after the last
  batch is on main, with nothing else in flight.

- DATA-CONTACT-UI [session, L 85m, build, P1, DR] Contact field in the web-data card and honest blocked wording + League dropdown in the web-data card. Files: web/index.html, web/app.js, web/prices.js, app/test/prices.test.js. Deps: DATA-CONTACT-FIELD, DATA-DIAG-SEAM.
- RUN-EXPLAIN-ROWS [session, M 60m, build, P2, DR] Five cause rows in Checks. Files: app/test/checks.test.js, server/al/plug/explain.py, tests/test_diag_explain.py. Deps: RUN-OBS-LOGS-SHELL, RUN-METRICS-SITES, RUN-SUPERVISOR-CLOCK, RUN-LEDGER-WIRE, RUN-REPORT-FIELDS, OVL-OBS-CRASH.
- OVL-APP-SCHEME-STRICT [session, S 25m, build, P3] Core refuses Origin null and file:// once both local pages load from the app scheme. Files: server/al/http.py, tests/test_http_security.py, tests/test_audit_http_harden.py. Deps: OVL-APP-SCHEME.
- TC-WEIGHTS-DELTA-EXPORT [session, M 50m, build, P2, DR] Settings export schema 2 carries the weight changes. Files: server/al/settingsio.py, server/al/core.py, web/settingsio.js, tests/test_ux_settings_io.py, docs/decisions/0036-run-history-file.md. Deps: TC-WEIGHTS-DELTA-STORE, TC-WORN-WIRE, TC-CALC-OPTIN.
- RUN-BUDGET-TESTS-LIVE [session, M 45m, build, P2] Opt-in live budgets: client process counts, calc ceilings, budget-log bounds. Files: tests/test_overlay_smoke.py, tests/tc_live_util.py, tests/test_budget_log.py, docs/decisions/0024-tc-delta.md. Deps: RUN-BUDGET-LOG-CORE, RUN-BUDGET-TESTS-DET, TC-PRESS-STAGED-LIVE.
- TEST-SLOW-BUDGET [session, M 60m, build, P3] Slow-test budget and hang guard. Files: tests/conftest.py, pytest.ini, README.md, tests/test_pytest_config.py, CONTRIBUTING.md (+2 more). Deps: TEST-FLOOR-MEMO, TEST-TIMER-FIXES, TEST-PLUGIN-PIN, TEST-MARKS, TEST-SUITE-RUNNER, TEST-DOCS-FACTS-UI, PUB-README-PLAYERS, DEP-02.
- DATA-PRICE-TYPES-FILE [session, M 40m, build, P3] Price type lists in a hot-reloaded data file. Files: server/al/pricebook.py, server/al/data/price_types.json, tests/test_price_types_file.py. Deps: DATA-NINJA-SHAPE-WATCH.
- TC-PIN-POLICY [session, M 40m, build, P3] Pin policy written into decision 0018; toolchain cleaned up. Files: docs/decisions/0018-tc-pin.md, docs/decisions/0027-tc-toolchain.md, tools/tc_pin.py, tests/test_tc_pin.py. Deps: TC-CALC-VERIFY-PIN, AUTO-12.
- RUN-HISTORY-UNDO [session, M 30m, build, P3, DR] Undo for Clear run history. Files: web/history.js, tests/test_util_run_history.py, app/test/history.test.js. Deps: RUN-DURABLE-STORES.
- RUN-OVERLAY-REMEMBER [session, M 30m, build, P3] Remember the overlay shown / hidden choice across restarts. Files: app/overlay_gate.js, app/main.js, app/test/overlay_gate.test.js. Deps: RUN-OBS-LOGS-SHELL.
- DATA-SNAP-TRIM [session, S 25m, build, P3] Drop the two unread files from the snapshot fetch list. Files: server/al/theorycraft/snapshot.py, tests/test_tc_snap.py. Deps: DATA-SNAP-PROBE.
- PLAY-PAGER-SCALE-24 [session, M 45m, build, P2] Pager buttons and compact weight inputs stay at least 24 px below UI scale 1. Files: web/app.css, tests/test_play_fit.py, tests/test_ux_review.py. Deps: PLAY-TD-19D-ITEMS-GRID, PLAY-TD-20A-RUN-GRID.
- RUN-UNREADABLE-WORD [session, M 50m, build, P2, DR] One status word for the unreadable Client.txt state. Files: server/al/data/status_words.json, web/status.js, app/shared/render_gate.js, server/al/diag.py, docs/design/0001-design-system.md (+2 more). Deps: TEST-STATE-TEXT-PINS, RUN-REPORT-FIELDS, OVL-KEY-HINT, REL-UPDATE-CHECKS, TEST-COPY-SHEETS.
- REL-CUTOVER-LIVE [session, M 60m, build, P1] Cut-over: the operator's live copy becomes an installed release. Files: none (an act or a read-back). Deps: DEP-13, DEP-09, REL-UNINSTALL-SHELL, REL-UPDATE-LAUNCH, REL-UPDATE-CHECKS, REL-RUNTIME-SCRIPTS, REL-BUILD-ASSETS.

### Wave 25: local security, overlay and client, theorycraft

Goal: Leads: Find Client.txt outside Steam: a typed path on the consent
card; OVERLAY-FEED: /events?view=overlay sends only the fields the HUD
reads, only when one c...; luajit leaves when it is not needed. Releases 1
loop-owned rows.

- Session 8; width 5 worktree + 0 main-checkout, 1 loop rows released; about
  93 minutes.
- Hotspots: web/index.html (SEC-LOG-PATH-FIELD); server/al/core.py
  (TC-CALC-IDLE); web/app.js (SEC-LOG-PATH-FIELD); server/al/http.py
  (OVL-OVERLAY-FEED); web/app.css (SEC-LOG-PATH-FIELD);
  app/shared/render_gate.js (OVL-OVERLAY-FEED);
  server/al/theorycraft/bridge.py (TC-CALC-IDLE).
- Integrator: ROADMAP.md rows of all 6 packages; docs/design/reviews.log: 3
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- SEC-LOG-PATH-FIELD [session, M 50m, build, P2, DR] Find Client.txt outside Steam: a typed path on the consent card. Files: web/index.html, web/app.js, web/app.css, web/logpath.js, app/test/logpath.test.js (+1 more). Deps: SEC-NO-DISCOVERY, PLAY-TD-12-CONTEXT-SETUP.
- OVL-OVERLAY-FEED [session, L 75m, build, P3, DR] OVERLAY-FEED: /events?view=overlay sends only the fields the HUD reads, only when one changes. Files: server/al/http.py, server/al/overlayview.py, app/overlay/overlay.js, app/shared/render_gate.js, app/test/shared.test.js (+2 more). Deps: OVL-KEY-HINT, OVL-APP-SCHEME-STRICT, RUN-QUIET-FEED, RUN-BUDGET-TESTS-DET.
- TC-CALC-IDLE [session, M 55m, build, P3] luajit leaves when it is not needed. Files: server/al/theorycraft/calcwire.py, server/al/theorycraft/bridge.py, server/al/exepin.py, server/al/core.py, tests/test_tc_wire.py (+3 more). Deps: TC-PRESS-STAGED-LIVE, TC-CALC-CONFINE-PROC, TC-CALC-VERIFY-USE, TC-WEIGHTS-DELTA-EXPORT, TC-UPGRADE-PER-SLOT.
- SEC-CEIL-SNAPSHOT [loop, M 45m, build, P3] Snapshot fetch: deadline, per-source cap on disk, one URL check. Files: server/al/theorycraft/snapshot.py, tests/test_tc_snap.py. Deps: SEC-CEIL-WEBFETCH, DATA-SNAP-TRIM.
- DATA-PRICE-TYPE-PROOF [session, M 50m, build, P3] Prove each price type after the first real round. Files: server/al/data/price_types.json, server/al/theorycraft/value.py, server/al/data/ninja_read_keys.json, server/al/ninjashape.py, tools/price_type_report.py (+1 more). Deps: DATA-PRICE-TYPES-FILE, DATA-NINJA-SHAPE-WATCH.
- PUB-GUIDE-DOWNLOAD-PLACE [session, M 45m, build, P2, DR] One download place in README, FAQ and About. Files: README.md, docs/guide/download.md, docs/guide/faq.md, app/about.js, app/main.js (+2 more). Deps: PUB-GUIDE-PAGES, GP-10.

### Wave 26: Play tab and dashboard, install and release

Goal: Milestones: the Settings rail is complete. Leads: Settings rail 2:
Keys, Appearance and tools, About and data; footer; Core: start the updater
by itself, 'Update now' and click-only.

- Session 8; width 2 worktree + 0 main-checkout, 0 loop rows released; about
  98 minutes.
- Hotspots: web/index.html (PLAY-TD-21B-SETTINGS-ABOUT); server/al/core.py
  (REL-UPDATE-TRIGGER); web/app.js (PLAY-TD-21B-SETTINGS-ABOUT);
  server/al/http.py (REL-UPDATE-TRIGGER); web/app.css
  (PLAY-TD-21B-SETTINGS-ABOUT); tests/test_ux_review.py
  (PLAY-TD-21B-SETTINGS-ABOUT); tests/test_security_surface.py
  (REL-UPDATE-TRIGGER); tests/test_ux_b8.py (PLAY-TD-21B-SETTINGS-ABOUT);
  tests/test_a11y.py (PLAY-TD-21B-SETTINGS-ABOUT); server/al/settingsio.py
  (REL-UPDATE-TRIGGER).
- Integrator: ROADMAP.md rows of all 2 packages; docs/design/reviews.log: 1
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- PLAY-TD-21B-SETTINGS-ABOUT [session, L 80m, build, P1, DR] Settings rail 2: Keys, Appearance and tools, About and data; footer. Files: web/index.html, web/app.css, web/app.js, web/rail.js, app/test/client_controls.test.js (+8 more). Deps: PLAY-TD-21A-SETTINGS-RAIL, PLAY-TD-09C-BAR.
- REL-UPDATE-TRIGGER [session, M 60m, build, P1] Core: start the updater by itself, 'Update now' and click-only. Files: server/al/updates.py, server/al/core.py, server/al/http.py, server/al/settingsio.py, tests/test_updates.py (+1 more). Deps: DEP-17, REL-UPDATE-WIRE, DEP-05, DEP-16, SEC-SURFACE-PIN.

### Wave 27: tests and code seams, reliability and observability, Play tab and dashboard

Goal: Leads: Copy pass: eleven sentences and four errors never send the
player to a script; Accessibility CSS: inset focus ring, 24 px targets,
forced colours, text spacing; Panel move B: layout, weights, web data and
graphics panels.

- Session 8; width 4 worktree + 0 main-checkout, 0 loop rows released; about
  93 minutes.
- Hotspots: web/index.html (RUN-NO-DEAD-ENDS); server/al/core.py
  (TEST-CORE-TICKS); web/app.js (TEST-WEB-PANELS-B); server/al/state.py
  (RUN-NO-DEAD-ENDS); web/app.css (PLAY-TD-22A-A11Y-CSS); server/al/diag.py
  (RUN-NO-DEAD-ENDS); tests/test_ux_review.py (PLAY-TD-22A-A11Y-CSS);
  server/al/__main__.py (TEST-CORE-TICKS); docs/design/0001-design-system.md
  (RUN-NO-DEAD-ENDS); tests/test_a11y.py (PLAY-TD-22A-A11Y-CSS);
  web/prices.js (RUN-NO-DEAD-ENDS).
- Integrator: ROADMAP.md rows of all 4 packages; docs/design/reviews.log: 3
  lines.
- Watch: tests/test_ux_review.py (PLAY-TD-22A-A11Y-CSS edits,
  RUN-NO-DEAD-ENDS runs); tests/test_a11y.py (PLAY-TD-22A-A11Y-CSS edits,
  TEST-WEB-PANELS-B runs).
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- RUN-NO-DEAD-ENDS [session, M 60m, build, P2, DR] Copy pass: eleven sentences and four errors never send the player to a script. Files: server/al/diag.py, server/al/state.py, server/al/acts.py, web/index.html, web/settingsio.js (+5 more). Deps: RUN-REPORT-FIELDS, RUN-OBS-LOGS-SHELL, RUN-ZONE-RESET, RUN-DIAG-DATA-AGE, RUN-EXPLAIN-ROWS, DATA-CONTACT-UI, OVL-KEYS-WEB, SEC-LOG-PATH-FIELD, TC-CALC-OPTIN-BUTTON.
- PLAY-TD-22A-A11Y-CSS [session, L 75m, build, P1, DR] Accessibility CSS: inset focus ring, 24 px targets, forced colours, text spacing. Files: web/app.css, web/textspacing.js, tests/test_a11y.py, tests/test_ux_review.py, tests/test_design_tokens.py (+1 more). Deps: PLAY-TD-21B-SETTINGS-ABOUT, PLAY-TD-03-TOKENS.
- TEST-WEB-PANELS-B [session, L 75m, build, P2, DR] Panel move B: layout, weights, web data and graphics panels. Files: web/app.js, app/test/panels.test.js, web/panels/layout.js, web/panels/weights.js, web/panels/webdata.js (+1 more). Deps: TEST-WEB-PANELS-A, PLAY-TD-21B-SETTINGS-ABOUT.
- TEST-CORE-TICKS [session, M 45m, build, P3] Core tick list and one import per line. Files: server/al/core.py, server/al/__main__.py, tests/test_core_ticks.py. Deps: TEST-STATE-EQUIV, SEC-DEMO-ENTRY.

### Wave 28: Play tab and dashboard, reliability and observability

Goal: Leads: Theme choice: Dark, Follow Windows, Light; In-browser
accessibility pass in the CDP harness; Parse each data file once. Releases 1
loop-owned rows.

- Session 8; width 3 worktree + 0 main-checkout, 1 loop rows released; about
  108 minutes.
- Hotspots: web/index.html (PLAY-TD-04B-THEME-CHOICE); server/al/core.py
  (PLAY-TD-04B-THEME-CHOICE); server/al/http.py (PLAY-TD-04B-THEME-CHOICE);
  tests/test_security_surface.py (PLAY-TD-04B-THEME-CHOICE);
  app/client/window.js (PLAY-TD-04B-THEME-CHOICE); server/al/settingsio.py
  (PLAY-TD-04B-THEME-CHOICE); tests/test_ux_settings_io.py
  (PLAY-TD-04B-THEME-CHOICE); server/al/zoneguide.py (RUN-PERF-PARSE-ONCE).
- Integrator: ROADMAP.md rows of all 4 packages; docs/design/reviews.log: 1
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- PLAY-TD-04B-THEME-CHOICE [session, L 75m, build, P2, DR] Theme choice: Dark, Follow Windows, Light. Files: web/index.html, server/al/settingsio.py, server/al/http.py, server/al/core.py, app/client/window.js (+6 more). Deps: PLAY-TD-21B-SETTINGS-ABOUT, PLAY-TD-04A-DARK-CLIENT, SEC-SURFACE-PIN, TEST-CAPTURE-HELPER.
- PLAY-TD-22C-A11Y-CDP [session, L 90m, build, P2] In-browser accessibility pass in the CDP harness. Files: app/test/cdp/a11y.mjs, tests/test_a11y_render.py. Deps: PLAY-TD-22A-A11Y-CSS, PLAY-TD-22B-TAB-FOCUS, PLAY-TD-01A-PLAY-STATES, SEC-DEMO-ENTRY.
- RUN-PERF-PARSE-ONCE [session, M 45m, build, P2] Parse each data file once. Files: server/al/hotreload.py, server/al/acts.py, server/al/campaign.py, server/al/zoneguide.py, server/al/theorycraft/basetypes.py (+2 more). Deps: RUN-HOTRELOAD-RETRY, RUN-DIAG-DATA-AGE, RUN-NO-DEAD-ENDS, RUN-DURABLE-STORES.
- PLAY-F-165-COLOUR-WORD-TEST [loop, S 25m, build, P3] Test: colour never works alone. Files: tests/test_colour_never_alone.py. Deps: PLAY-TD-22A-A11Y-CSS.

### Wave 29: Play tab and dashboard, overlay and client

Goal: Leads: Settings group 'Overlay shows': part switches, presets Full /
Cards only, zone-guide ch...; Player notes: bounded store, token route and
the your-note row; Screen-reader pass tool and its refusals.

- Session 8; width 3 worktree + 0 main-checkout, 0 loop rows released; about
  98 minutes.
- Hotspots: web/index.html (OVL-PARTS-WEB); server/al/core.py
  (PLAY-F-186A-PLAYER-NOTES-STORE); web/app.js (OVL-PARTS-WEB);
  server/al/http.py (PLAY-F-186A-PLAYER-NOTES-STORE); server/al/state.py
  (PLAY-F-186A-PLAYER-NOTES-STORE); web/app.css (OVL-PARTS-WEB);
  tests/test_ux_review.py (OVL-PARTS-WEB); tests/test_security_surface.py
  (PLAY-F-186A-PLAYER-NOTES-STORE); tests/test_a11y.py (OVL-PARTS-WEB).
- Integrator: ROADMAP.md rows of all 3 packages; CLAUDE.md:
  PLAY-F-186A-PLAYER-NOTES-STORE; docs/decisions/README.md:
  PLAY-F-186A-PLAYER-NOTES-STORE; docs/design/reviews.log: 2 lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- OVL-PARTS-WEB [session, M 60m, build, P2, DR] Settings group 'Overlay shows': part switches, presets Full / Cards only, zone-guide choice, 'Show a sample card for 10 s'. Files: web/index.html, web/app.js, web/app.css, tests/test_a11y.py, tests/test_ux_review.py (+2 more). Deps: OVL-OVERLAY-KEYS, OVL-CARD-SLOT, OVL-TD05-PLATE.
- PLAY-F-186A-PLAYER-NOTES-STORE [session, L 80m, build, P3, DR] Player notes: bounded store, token route and the your-note row. Files: server/al/http.py, server/al/core.py, server/al/state.py, server/al/playcards.py, tests/test_security_surface.py (+3 more). Deps: PLAY-TD-07B-PLAY-CARDS, PLAY-TD-04B-THEME-CHOICE, RUN-ZONE-RESET, RUN-HOTRELOAD-RETRY, DATA-GUIDE-MERGE.
- PLAY-F-204A-SR-TOOL [session, M 50m, build, P3] Screen-reader pass tool and its refusals. Files: tools/sr_pass.py, tests/test_sr_pass.py. Deps: PLAY-TD-22C-A11Y-CDP, SEC-DEMO-ENTRY.

### Wave 30: overlay and client, tests and code seams, loop and watchers

Goal: Leads: Card time setting: 20 / 60 / 200 s (TD-18, optional); Panel
move C: remaining Play blocks (events and trades, item check, rates and
price); Two Checks notes: a stale loop tick (dev host) and the Electron end
of life.

- Session 9; width 3 worktree + 0 main-checkout, 0 loop rows released; about
  118 minutes.
- Hotspots: web/index.html (OVL-TD18-CARD-TIME); server/al/core.py
  (LOOP-DEV-CHECKS); web/app.js (TEST-WEB-PANELS-C); server/al/state.py
  (OVL-TD18-CARD-TIME); server/al/diag.py (LOOP-DEV-CHECKS); web/checks.js
  (TEST-WEB-PANELS-C).
- Integrator: ROADMAP.md rows of all 3 packages; docs/design/reviews.log: 2
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- OVL-TD18-CARD-TIME [session, M 45m, build, DR] Card time setting: 20 / 60 / 200 s (TD-18, optional). Files: server/al/layout.py, app/shared/layout.js, server/al/state.py, web/overlayparts.js, web/index.html (+4 more). Deps: OVL-LINE2-GUIDE, OVL-PARTS-WEB, OVL-TD06-AUTOSCALE, OVL-COPY-FIRST, OVL-KEYS-WEB, OVL-OVERLAY-FEED.
- TEST-WEB-PANELS-C [session, L 90m, build, P2, DR] Panel move C: remaining Play blocks (events and trades, item check, rates and price) + Panel move D: view modules register themselves; app.js is a. Files: web/app.js, app/test/panels.test.js, app/test/registry.test.js, web/acts.js, web/buildlive.js (+11 more). Deps: TEST-WEB-PANELS-B, PLAY-LEGACY-OUT-2, PLAY-TD-16A-ITEMCARD.
- LOOP-DEV-CHECKS [session, M 40m, build, P2] Two Checks notes: a stale loop tick (dev host) and the Electron end of life. Files: server/al/diag.py, server/al/core.py, tests/test_diag_dev_notes.py. Deps: none.

### Wave 31: Play tab and dashboard, reliability and observability

Goal: Milestones: design 0001 and the cockpit decision are rewritten
(records). Leads: Player notes: edit box on Run and the export option; 'This
is my character' pin in the picker; poll_ms and character apply without a
restart; Records: design 0001 rewritten, the cockpit decision, decision 0014
amended.

- Session 9; width 2 worktree + 1 main-checkout, 0 loop rows released; about
  108 minutes.
- Hotspots: web/index.html (PLAY-F-186B-PLAYER-NOTES-UI); server/al/core.py
  (RUN-CHARACTER-PIN); server/al/state.py (RUN-CHARACTER-PIN);
  docs/design/0001-design-system.md (PLAY-TD-23-RECORDS);
  server/al/settingsio.py (PLAY-F-186B-PLAYER-NOTES-UI);
  tests/test_ux_settings_io.py (PLAY-F-186B-PLAYER-NOTES-UI).
- Integrator: ROADMAP.md rows of all 3 packages; CLAUDE.md:
  PLAY-TD-23-RECORDS; docs/decisions/README.md: PLAY-TD-23-RECORDS;
  docs/design/reviews.log: 3 lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- PLAY-F-186B-PLAYER-NOTES-UI [session, M 60m, build, P3, DR] Player notes: edit box on Run and the export option. Files: web/index.html, server/al/settingsio.py, web/settingsio.js, tests/test_ux_settings_io.py, web/playernote.js (+1 more). Deps: PLAY-F-186A-PLAYER-NOTES-STORE, PLAY-TD-04B-THEME-CHOICE, PLAY-TD-20A-RUN-GRID.
- RUN-CHARACTER-PIN [session, M 45m, build, P3, DR] 'This is my character' pin in the picker; poll_ms and character apply without a restart. Files: server/al/core.py, server/al/state.py, web/chars.js, app/test/chars.test.js, tests/test_util_multichar.py (+1 more). Deps: RUN-QUIET-FEED, RUN-NO-DEAD-ENDS, RUN-START-REASON-CORE.
- PLAY-TD-23-RECORDS [session, L 90m, build, P3, DR] Records: design 0001 rewritten, the cockpit decision, decision 0014 amended. Files: docs/design/0001-design-system.md, docs/decisions/0014-ui-build-eval-gfx.md, docs/design/0004-glance-review.md, docs/design/play-fit-figures.md, docs/decisions/0075-fixed-cockpit-play.md. Deps: PLAY-TD-02-SLOTS, PLAY-TD-03-TOKENS, PLAY-TD-01B-FIT-HARNESS, DATA-PRICE-CARD-TEXT, PLAY-F-131-STATUS-TABLE, PLAY-TD-07B-PLAY-CARDS, PLAY-TD-08B-GUIDE-SHORT-TEXT, PLAY-TD-09B-SKELETON, PLAY-LEGACY-OUT-2, PLAY-TD-19D-ITEMS-GRID, PLAY-TD-20B-RUN-CARDS, PLAY-TD-21B-SETTINGS-ABOUT, PLAY-TD-04B-THEME-CHOICE, PLAY-TD-22A-A11Y-CSS, PLAY-TD-22B-TAB-FOCUS, PLAY-TD-22C-A11Y-CDP, OVL-TD05-LEGIBILITY, OVL-TD05-PLATE, OVL-TD06-AUTOSCALE, OVL-LINE2-GUIDE, OVL-ACT-CARD, OVL-COPY-FIRST, OVL-KEY-HINT, OVL-GLANCE-RULES, OVL-TD18-CARD-TIME.

### Wave 32: reliability and observability, install and release

Goal: Leads: Settings: version lines, update line, opt-in wording; P8-8: the
session ladder and the Maps card no longer mix characters; Supervisor diet
and idle backoff.

- Session 9; width 3 worktree + 0 main-checkout, 0 loop rows released; about
  113 minutes.
- Hotspots: web/index.html (REL-UPDATE-NOTICE-UI); server/al/core.py
  (RUN-PERF-IDLE-BACKOFF); web/app.js (REL-UPDATE-NOTICE-UI);
  server/al/state.py (RUN-P8-8-CHARMIX); server/al/__main__.py
  (RUN-PERF-IDLE-BACKOFF); server/al/keepalive.py (RUN-PERF-IDLE-BACKOFF);
  tests/test_keepalive.py (RUN-PERF-IDLE-BACKOFF).
- Integrator: ROADMAP.md rows of all 3 packages; AL-NEXT-SESSION.txt:
  RUN-P8-8-CHARMIX; docs/design/reviews.log: 1 lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- REL-UPDATE-NOTICE-UI [session, L 70m, build, P1, DR] Settings: version lines, update line, opt-in wording. Files: web/index.html, web/app.js, web/updates.js, app/test/updates.test.js. Deps: REL-UPDATE-WIRE, PLAY-TD-21A-SETTINGS-RAIL.
- RUN-P8-8-CHARMIX [session, L 85m, build, P2] P8-8: the session ladder and the Maps card no longer mix characters + SessionState.publish(key, view) for views the core only stores. Files: server/al/state.py, server/al/mapladder.py, tests/test_util_map_ladder.py, tests/test_util_multichar.py, tests/test_util_maps_resume.py (+1 more). Deps: RUN-LADDER-TICK, RUN-CHARACTER-PIN, TEST-STATE-TEXT-4, PLAY-TD-07A-PLAY-VIEW.
- RUN-PERF-IDLE-BACKOFF [session, M 30m, build, P3] Supervisor diet and idle backoff. Files: server/al/keepalive.py, server/al/core.py, server/al/__main__.py, server/al/logfile.py, tests/test_keepalive.py (+1 more). Deps: RUN-STOP-RACE, RUN-CHARACTER-PIN, RUN-START-REASON-CORE, RUN-TAIL-HEAL-READER, RUN-BUDGET-TESTS-DET.

### Wave 33: Play tab and dashboard, tests and code seams, reliability and observability

Goal: Leads: One spacing scale, one badge, one list row, held by a lint;
SessionState mixins: cards and trades; The page says what really happened to
the feed.

- Session 9; width 3 worktree + 0 main-checkout, 0 loop rows released; about
  108 minutes.
- Hotspots: web/index.html (PLAY-F-189A-SPACING-BADGE); web/app.js
  (RUN-FEED-TRUTH); server/al/http.py (RUN-FEED-TRUTH); server/al/state.py
  (TEST-STATE-MIXIN-A); web/app.css (PLAY-F-189A-SPACING-BADGE);
  app/shared/render_gate.js (RUN-FEED-TRUTH);
  docs/design/0001-design-system.md (PLAY-F-189A-SPACING-BADGE);
  web/checks.js (PLAY-F-189A-SPACING-BADGE); web/prices.js
  (PLAY-F-189A-SPACING-BADGE).
- Integrator: ROADMAP.md rows of all 3 packages; docs/design/reviews.log: 2
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- PLAY-F-189A-SPACING-BADGE [session, L 90m, build, P3, DR] One spacing scale, one badge, one list row, held by a lint. Files: web/app.css, web/index.html, web/strip.js, web/feed.js, web/notice.js (+7 more). Deps: PLAY-TD-23-RECORDS, PLAY-TD-22A-A11Y-CSS, PLAY-F-186B-PLAYER-NOTES-UI, TEST-CAPTURE-HELPER.
- TEST-STATE-MIXIN-A [session, M 60m, build, P3] SessionState mixins: cards and trades. Files: server/al/state.py, server/al/state_cards.py, server/al/state_trades.py. Deps: RUN-P8-8-CHARMIX.
- RUN-FEED-TRUTH [session, L 75m, build, P3, DR] The page says what really happened to the feed + The dashboard rests when unseen or frozen. Files: web/app.js, web/status.js, server/al/http.py, app/overlay/overlay.js, app/shared/render_gate.js (+3 more). Deps: RUN-SUPERVISOR-CLOCK, RUN-CHARACTER-PIN, RUN-NO-DEAD-ENDS, RUN-BUDGET-TESTS-DASH, SEC-SSE-TAP.

### Wave 34: install and release, tests and code seams, Play tab and dashboard

Goal: Leads: 'Start with Windows' row on Settings; SessionState mixins:
characters; Overlay: one plate class.

- Session 10; width 3 worktree + 0 main-checkout, 0 loop rows released;
  about 113 minutes.
- Hotspots: web/index.html (REL-AUTOSTART-SETTINGS); web/app.js
  (REL-AUTOSTART-SETTINGS); server/al/state.py (TEST-STATE-MIXIN-B).
- Integrator: ROADMAP.md rows of all 3 packages; docs/design/reviews.log: 2
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- REL-AUTOSTART-SETTINGS [session, L 85m, build, P1, DR] 'Start with Windows' row on Settings + Settings: 'Update now', the click-only switch and the staged line. Files: web/index.html, web/app.js, web/updates.js, app/test/updates.test.js, web/autostart.js (+1 more). Deps: REL-AUTOSTART-SWITCH, REL-UPDATE-NOTICE-UI, REL-UPDATE-TRIGGER, PLAY-TD-21A-SETTINGS-RAIL.
- TEST-STATE-MIXIN-B [session, M 60m, build, P3] SessionState mixins: characters. Files: server/al/state.py, server/al/state_chars.py. Deps: TEST-STATE-MIXIN-A.
- PLAY-F-189B-OVERLAY-PLATE [session, M 50m, build, P3, DR] Overlay: one plate class. Files: app/overlay/overlay.css, app/overlay/index.html, tests/test_overlay_plate_class.py. Deps: PLAY-F-189A-SPACING-BADGE.

### Wave 35: theorycraft, tests and code seams

Goal: Leads: Weights panel marks changes and resets; SessionState mixins:
idle and summary, published views.

- Session 10; width 2 worktree + 0 main-checkout, 0 loop rows released;
  about 118 minutes.
- Hotspots: web/index.html (TC-WEIGHTS-DELTA-UI); web/app.js
  (TC-WEIGHTS-DELTA-UI); server/al/state.py (TEST-STATE-MIXIN-C).
- Integrator: ROADMAP.md rows of all 2 packages; docs/design/reviews.log: 1
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- TC-WEIGHTS-DELTA-UI [session, L 90m, build, P2, DR] Weights panel marks changes and resets + .build texts: correct the passives note, name the upload route. Files: web/tc.js, web/app.js, web/index.html, app/test/tc_view.test.js, server/al/theorycraft/buildfile.py (+1 more). Deps: TC-WEIGHTS-DELTA-STORE, TC-CARD-PARTS-WEB.
- TEST-STATE-MIXIN-C [session, L 70m, build, P3] SessionState mixins: idle and summary, published views. Files: server/al/state.py, server/al/state_idle.py, server/al/state_views.py. Deps: TEST-STATE-MIXIN-B.

### Wave 36: web data

Goal: Leads: Dashboard: one guide block, no separate Zone tip.

- Session 10; width 1 worktree + 0 main-checkout, 0 loop rows released;
  about 88 minutes.
- Hotspots: web/index.html (DATA-GUIDE-ONE-BLOCK); web/app.js
  (DATA-GUIDE-ONE-BLOCK); web/app.css (DATA-GUIDE-ONE-BLOCK); web/prices.js
  (DATA-GUIDE-ONE-BLOCK); app/test/tabs.test.js (DATA-GUIDE-ONE-BLOCK);
  app/test/prices.test.js (DATA-GUIDE-ONE-BLOCK).
- Integrator: ROADMAP.md rows of all 1 packages; docs/design/reviews.log: 1
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- DATA-GUIDE-ONE-BLOCK [session, L 70m, build, P2, DR] Dashboard: one guide block, no separate Zone tip + A poe.ninja category link beside the trade link. Files: web/index.html, web/app.js, web/app.css, app/test/tabs.test.js, server/al/price.py (+6 more). Deps: DATA-GUIDE-MERGE, DATA-CONTACT-UI, DATA-PRICE-CARD-TEXT, DATA-LEAGUE-IDENTITY.

### Wave 37: reliability and observability

Goal: Leads: Small leftovers: Windowed Fullscreen sentence, the dead 501
stub, the no-op switch.

- Session 10; width 1 worktree + 0 main-checkout, 0 loop rows released;
  about 48 minutes.
- Hotspots: web/index.html (RUN-LEFTOVERS-CORE); server/al/http.py
  (RUN-LEFTOVERS-CORE); tests/test_security_surface.py (RUN-LEFTOVERS-CORE);
  scripts/run.ps1 (RUN-LEFTOVERS-CORE); tests/test_http_security.py
  (RUN-LEFTOVERS-CORE).
- Integrator: ROADMAP.md rows of all 1 packages; docs/design/reviews.log: 1
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- RUN-LEFTOVERS-CORE [session, M 30m, build, P3, DR] Small leftovers: Windowed Fullscreen sentence, the dead 501 stub, the no-op switch. Files: web/index.html, server/al/http.py, tests/test_http_security.py, scripts/run.ps1, docs/ops/1.0-launch-runbook.md (+3 more). Deps: RUN-FEED-TRUTH, RUN-STOP-RACE.

### Wave 38: operator requests 2026-11-19, cores

Goal: Leads: Item info lookup: token-gated GET /api/iteminfo over local
caches; Drop the visible AshLight text left of the tabs; sr-only h1 kept;
Kindler template schema and checked loader.

- Session 11; width 4 worktree + 0 main-checkout, 0 loop rows released;
  about 88 minutes.
- Hotspots: web/index.html (UI-HEADER-TEXT); web/app.css (UI-HEADER-TEXT);
  tests/test_a11y.py (UI-HEADER-TEXT); server/al/settingsio.py
  (KINDLER-STORE); server/al/pricebook.py (ITEM-INFO-CORE).
- Integrator: ROADMAP.md rows of all 4 packages; docs/design/reviews.log: 1
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- ITEM-INFO-CORE [session, M 45m, build, P2] Item info lookup: token-gated GET /api/iteminfo over local caches. Files: server/al/theorycraft/snapshot.py, server/al/pricebook.py, server/al/iteminfo.py, server/al/plug/iteminfo.py, tests/test_iteminfo.py. Deps: none.
- UI-HEADER-TEXT [session, S 20m, build, P2, DR] Drop the visible AshLight text left of the tabs; sr-only h1 kept. Files: web/index.html, web/app.css, tests/test_brand_assets.py, tests/test_a11y.py. Deps: none.
- KINDLER-DATA [session, M 60m, data, P2] Kindler template schema and checked loader. Files: server/al/theorycraft/archetypes.py, tests/kindler_fixtures.py, tests/test_kindler_data.py. Deps: none.
- KINDLER-STORE [session, M 55m, build, P2] Kindler tabs store ops/runtime/gen_builds.json. Files: server/al/settingsio.py, server/al/runhistory.py, server/al/plug/stores.py, tests/test_settingsio.py, server/al/theorycraft/genstore.py (+2 more). Deps: none.

### Wave 39: operator requests 2026-11-19, popover and templates

Goal: Leads: Text-parse PoB CurrencyNames, WorldAreas and Uniques Source
lines under sha256 pins; Item names as link-like buttons with the shared
item info popover; First authored Kindler templates, act 1 to maps.

- Session 11; width 3 worktree + 0 main-checkout, 0 loop rows released;
  about 118 minutes.
- Hotspots: web/index.html (ITEM-INFO-UI); web/app.js (ITEM-INFO-UI);
  web/prices.js (ITEM-INFO-UI).
- Integrator: ROADMAP.md rows of all 3 packages; docs/design/reviews.log: 1
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- ITEM-INFO-POB-TEXT [session, M 60m, data, P3] Text-parse PoB CurrencyNames, WorldAreas and Uniques Source lines under sha256 pins. Files: config/tc_pins.json, server/al/iteminfo.py, tests/test_tc_pob_drift_guard.py, server/al/theorycraft/pobtext.py, tests/test_tc_pobtext.py. Deps: ITEM-INFO-CORE.
- ITEM-INFO-UI [session, M 60m, build, P2, DR] Item names as link-like buttons with the shared item info popover. Files: web/index.html, web/prices.js, web/pricewatch.js, web/app.js, web/iteminfo.js (+2 more). Deps: ITEM-INFO-CORE.
- KINDLER-TEMPLATES [session, L 90m, data, P2] First authored Kindler templates, act 1 to maps. Files: server/al/data/archetypes.json, tests/test_kindler_templates.py. Deps: KINDLER-DATA.

### Wave 40: operator requests 2026-11-19, engine and tabs

Goal: Leads: Kindler candidates, PoB scoring and deterministic ranking on
the Generate route; Build tab sub-tabs: Pasted build plus Kindler tabs with
move, rename and close.

- Session 11; width 2 worktree + 0 main-checkout, 0 loop rows released;
  about 118 minutes.
- Hotspots: web/index.html (KINDLER-UI-TABS); web/app.css (KINDLER-UI-TABS);
  server/al/theorycraft/bridge.py (KINDLER-ENGINE).
- Integrator: ROADMAP.md rows of all 2 packages; docs/design/reviews.log: 1
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- KINDLER-ENGINE [session, L 90m, build, P2] Kindler candidates, PoB scoring and deterministic ranking on the Generate route. Files: server/al/theorycraft/bridge.py, server/al/theorycraft/kindler.py, server/al/plug/kindler.py, tests/test_kindler_engine.py, tests/test_kindler_live.py. Deps: KINDLER-DATA, KINDLER-TEMPLATES, KINDLER-STORE.
- KINDLER-UI-TABS [session, M 60m, build, P2, DR] Build tab sub-tabs: Pasted build plus Kindler tabs with move, rename and close. Files: web/index.html, web/tc.js, web/app.css, web/kindler.js, web/kindler.css (+1 more). Deps: KINDLER-STORE.

### Wave 41: operator requests 2026-11-19, Kindler plan and card collapse

Goal: Leads: Collapsible cards on Build and items and Run in the desktop
client; state in the core; Kindler result plan: stages, links, gem timing,
passives, ascendancy, item focus.

- Session 11; width 2 worktree + 0 main-checkout, 0 loop rows released;
  about 108 minutes.
- Hotspots: web/index.html (UI-CARD-COLLAPSE); web/app.css
  (UI-CARD-COLLAPSE).
- Integrator: ROADMAP.md rows of all 2 packages; docs/design/reviews.log: 1
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- UI-CARD-COLLAPSE [session, L 80m, build, P2, DR] Collapsible cards on Build and items and Run in the desktop client; state in the core. Files: web/index.html, web/app.css, web/pager.js, server/al/plug/stores.py, web/collapse.js (+4 more). Deps: none.
- KINDLER-PLAN [session, L 80m, build, P2] Kindler result plan: stages, links, gem timing, passives, ascendancy, item focus. Files: server/al/plug/kindler.py, server/al/theorycraft/kindlerplan.py, tests/test_kindler_plan.py. Deps: KINDLER-ENGINE.

### Wave 42: operator requests 2026-11-19, Kindler result card

Goal: Leads: Kindler result card with stages and follow Play guidance.

- Session 11; width 1 worktree + 0 main-checkout, 0 loop rows released;
  about 108 minutes.
- Hotspots: web/index.html (KINDLER-UI-RESULT).
- Integrator: ROADMAP.md rows of all 1 packages; docs/design/reviews.log: 1
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- KINDLER-UI-RESULT [session, L 90m, build, P2, DR] Kindler result card with stages and follow Play guidance. Files: web/index.html, web/kindler.js, web/kindler.css, tests/test_kindler_result_ui.py. Deps: KINDLER-PLAN, KINDLER-UI-TABS, ITEM-INFO-UI.

### Wave 43: parked package released, default contact

Goal: Leads: Default contact: the project's issues page once the repository
is public.

- Session 11; width 1 worktree + 0 main-checkout, 0 loop rows released;
  about 45 minutes.
- Hotspots: web/index.html (DATA-CONTACT-DEFAULT).
- Integrator: ROADMAP.md rows of all 1 packages; docs/design/reviews.log: 1
  lines.
- Gate: per package: its named tests as a file-named run; main-checkout acts
  one at a time in merge order; per merge batch of 4 on the integration
  worktree: merge, then the integrator's edits for the batch as one commit,
  then python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  tools/suite_run.py and npm test --prefix app, green, then main moves; then
  python tools/plan_check.py check; the wave closes when every session row
  is flipped and main is clean.

- DATA-CONTACT-DEFAULT [session, M 45m, build, P1, DR] Default contact: the project's issues page once the repository is public. Files: server/al/webfetch.py, server/al/core.py, server/al/theorycraft/snapshot.py, web/index.html, web/prices.js (+4 more). Deps: DATA-CONTACT-UI, DATA-WEBFETCH-GZIP, DATA-DIAG-SEAM, DATA-SNAP-TRIM, DATA-GUIDE-ONE-BLOCK, GP-10.

## Hotspot schedule

The number of waves is bounded below by the longest chain of packages that
edit one file: one editor a wave. Counts are unparked packages, before and
after folding.

- server/al/state.py: 26 editors, waves 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,
  13, 14, 15, 16, 20, 21, 22, 27, 29, 30, 31, 32, 33, 34, 35.
- web/app.js: 28 editors, waves 2, 3, 5, 6, 8, 9, 10, 11, 13, 15, 16, 17,
  18, 19, 20, 22, 23, 24, 25, 26, 27, 29, 30, 32, 33, 34, 35, 36.
- web/app.css (the dashboard CSS): 18 editors, waves 4, 5, 6, 10, 11, 12,
  14, 17, 18, 21, 22, 23, 25, 26, 27, 29, 33, 36.
- app/main.js (the Electron main file): 12 editors, waves 4, 5, 9, 13, 14,
  15, 16, 17, 19, 20, 23, 24.
- ROADMAP.md (integrator only): every wave; the rows of the wave's packages
  are flipped per merge batch. The rows themselves are landed once, in wave
  0, by PLAN-LANDING from `python tools/plan_check.py rows`; the 118
  packages whose cluster text said 'add the row' now say 'flip the row', so
  no id is added twice.
- CLAUDE.md (integrator only): wave 1: 3; wave 2: 4; wave 3: 1; wave 4: 5;
  wave 5: 4; wave 6: 1; wave 7: 1; wave 9: 5; wave 10: 5; wave 11: 2; wave
  12: 3; wave 13: 5; wave 14: 5; wave 15: 1; wave 16: 2; wave 17: 3; wave
  18: 2; wave 19: 1; wave 20: 2; wave 21: 1; wave 22: 1; wave 24: 3; wave
  29: 1; wave 31: 1 Settled-list edits (62 in all). The packages are named
  in each wave's Integrator line.

The ten most contended files and how the plan handles each:

1. web/index.html: 41 packages in, 35 after folds; waves 2 to 37 (idle in
   7). This file sets the length of the plan. PLAY-TD-09A-REGION-HOOK (wave
   2) pre-links the Play region files, so the seven region steps TD-10 to
   TD-16 never open it. Its editors get one slot a wave by a chain deadline,
   their prerequisites are pulled forward just in time, and the web seam
   packages fill the slots the Play steps cannot use. Folded pairs on this
   file: PLAY-TD-09C-BAR, TC-CARD-PARTS-WEB, TC-WEIGHTS-DELTA-UI,
   RUN-VERDICTS-UI, DATA-CONTACT-UI, DATA-GUIDE-ONE-BLOCK,
   REL-AUTOSTART-SETTINGS, RUN-METRICS-SITES.
2. server/al/core.py: 35 packages in, 32 after folds; waves 1 to 32 (never
   idle). P0 editors first (SEC-NO-DISCOVERY wave 1, alone); TC-CARD-PARTS
   (wave 2) is the one P1 package placed ahead of P0 work here, because the
   Play item card and the worn-gear path stand on its seam; RUN-SEAMS (wave
   5) moves ticks, Checks rows and routes into plug files, which is why the
   RUN packages after it are narrow. TEST-CORE-TICKS (wave 27) comes late:
   no package of this plan gets narrower by it.
3. web/app.js: 34 packages in, 28 after folds; waves 2 to 36 (idle in 4, 7,
   12, 14, 21, 28, 31). Same handling as web/index.html (most editors touch
   both). The region hook keeps the Play steps out; TEST-WEB-REGISTRY (wave
   9) adds the panel registry early; the panel moves follow the Play steps
   that reshape each block (cross entries of the TEST cluster).
4. server/al/http.py: 30 packages in, 28 after folds; waves 1 to 37 (9 idle
   waves). SEC-STATIC-MAP with SEC-CROSS-SITE (wave 1) adds no branch to
   do_GET and maps /web/ from a directory listing, so a new dashboard file
   needs no edit here; RUN-SEAMS gives token-gated plug routes;
   TEST-HTTP-ROUTES (wave 8) builds the route tables right after the surface
   pin.
5. server/al/state.py: 30 packages in, 26 after folds; waves 2 to 35 (idle
   in 17, 18, 19, 23, 24, 25, 26, 28). TC-CARD-PARTS (wave 2) and
   OVL-CARD-SLOT (wave 20, server/al/overlayview.py) are the seams; the Play
   view (PLAY-TD-07A, wave 5) lands before the overlay view; the text move
   starts with RUN-ZONE-RESET (folded with move 1) and the split by concern
   comes last.
6. web/app.css: 19 packages in, 18 after folds; waves 4 to 36 (15 idle
   waves). PLAY-TD-03-TOKENS (wave 4) lands the token block first; the
   region stylesheets are pre-linked by the region hook, so the region steps
   edit their own files.
7. server/al/diag.py: 17 packages in, 17 after folds; waves 1 to 30 (13 idle
   waves). DATA-DIAG-SEAM (wave 18) and the Checks rows of RUN-SEAMS take
   most later rows out of the file; PLAY-F-131-STATUS-TABLE (wave 4) fixes
   the status words before the packages that print them.
8. tests/test_ux_review.py: 15 packages in, 15 after folds; waves 4 to 29
   (11 idle waves). A shared test file: one editor a wave like any source
   file; the type-floor change of PLAY-TD-03-TOKENS lands before the overlay
   legibility step.
9. app/main.js: 14 packages in, 12 after folds; waves 4 to 24 (9 idle
   waves). OVL-MAIN-PARTS (wave 4) adds the main-process parts seam
   (app/parts/), after which the overlay and client packages add a part file
   instead of editing this file; the three RUN client packages on it are
   folded into RUN-OBS-LOGS-SHELL.
10. tests/test_security_surface.py: 14 packages in, 14 after folds; waves 2
   to 37 (22 idle waves). One editor a wave, ordered by deadline and tier.

Seams (research 0047). Packages that split a contended file or move a shared
append-point into its own file come in two kinds. Seams this plan's packages
build on land before everything that depends on them: LOOP-SPLIT-TICK (wave
1), LOOP-TESTS-CARVE (wave 1), LOOP-LEDGERS (wave 1), TC-CARD-PARTS (wave
2), PLAY-TD-09A-REGION-HOOK (wave 2), RUN-SEAMS (wave 5), OVL-MAIN-PARTS
(wave 4), DATA-DIAG-SEAM (wave 18), OVL-CARD-SLOT (wave 20). The web seams
of 0047 R4 and R8 (TEST-WEB-FMT wave 8, TEST-WEB-REGISTRY wave 9,
TEST-WEB-ASSEMBLE wave 12) are pulled forward ahead of their tier on
purpose: each takes a web/index.html slot in a wave where no higher-tier
editor is ready, and the panel moves that depend on them are then not left
for the end. Refactors that help only work after this plan take a hot-file
slot each and make no package of this plan narrower, so they run when their
tier comes up and after the features that asked to precede them: the state
text move (0047 R3, waves 9, 11, 13, 15), the SessionState split (R5, waves
32, 33, 34, 35), the tick list and route tables (R7, waves 8, 27) and the
panel moves (R4, waves 20, 27, 30).

After a text-move package has landed, a later package whose notes name a
moved region of server/al/state.py edits that text where it now lives
(server/al/text/); its files entry server/al/state.py stands for both, so
the one-editor rule still holds.

## Critical path

The plan is as long as the web/index.html chain: 35 editors, one a wave,
from wave 2 to wave 37 (the first editor needs a wave-1 package, so the
floor is one more than the number of editors). In wave order:

PLAY-TD-09A-REGION-HOOK (2) -> TC-CARD-PARTS-WEB (3) ->
TC-FILTER-ONE-CONTROL (4) -> PLAY-TD-09B-SKELETON (5) -> PLAY-TD-09C-BAR (6)
-> TEST-WEB-FMT (8) -> TEST-WEB-REGISTRY (9) -> PLAY-LEGACY-OUT-1 (10) ->
PLAY-LEGACY-OUT-2 (11) -> TEST-WEB-ASSEMBLE (12) -> RUN-BUILD-STAMP-UI (13)
-> PLAY-TD-19B-FOUR-TABS (14) -> RUN-METRICS-SITES (15) -> OVL-KEYS-WEB (16)
-> PLAY-TD-19C-BUILD-GRID (17) -> PLAY-TD-19D-ITEMS-GRID (18) ->
RUN-VERDICTS-UI (19) -> OVL-TD05-PLATE (20) -> PLAY-TD-20A-RUN-GRID (21) ->
PLAY-TD-20B-RUN-CARDS (22) -> PLAY-TD-21A-SETTINGS-RAIL (23) ->
DATA-CONTACT-UI (24) -> SEC-LOG-PATH-FIELD (25) ->
PLAY-TD-21B-SETTINGS-ABOUT (26) -> RUN-NO-DEAD-ENDS (27) ->
PLAY-TD-04B-THEME-CHOICE (28) -> OVL-PARTS-WEB (29) -> OVL-TD18-CARD-TIME
(30) -> PLAY-F-186B-PLAYER-NOTES-UI (31) -> REL-UPDATE-NOTICE-UI (32) ->
PLAY-F-189A-SPACING-BADGE (33) -> REL-AUTOSTART-SETTINGS (34) ->
TC-WEIGHTS-DELTA-UI (35) -> DATA-GUIDE-ONE-BLOCK (36) -> RUN-LEFTOVERS-CORE
(37)

The longest dependency chain by agent minutes (1670 minutes, 22 packages) is
shorter than that, so dependencies alone would allow 22 waves:

SEC-NO-DISCOVERY (1) -> SEC-DEMO-CORE (2) -> SEC-DEMO-ENTRY (3) ->
PLAY-TD-01B-FIT-HARNESS (4) -> PLAY-TD-09B-SKELETON (5) -> PLAY-TD-09C-BAR
(6) -> PLAY-TD-10-STRIP (7) -> PLAY-LEGACY-OUT-1 (10) -> PLAY-LEGACY-OUT-2
(11) -> PLAY-F-159-QUIET-BUTTON (12) -> PLAY-TD-19B-FOUR-TABS (14) ->
PLAY-TD-19C-BUILD-GRID (17) -> PLAY-TD-19D-ITEMS-GRID (18) ->
PLAY-TD-20A-RUN-GRID (21) -> PLAY-TD-20B-RUN-CARDS (22) ->
PLAY-TD-21A-SETTINGS-RAIL (23) -> PLAY-TD-21B-SETTINGS-ABOUT (26) ->
PLAY-TD-22A-A11Y-CSS (27) -> PLAY-TD-22C-A11Y-CDP (28) -> PLAY-TD-23-RECORDS
(31) -> PLAY-F-189A-SPACING-BADGE (33) -> PLAY-F-189B-OVERLAY-PLATE (34)

Milestone targets. A target wave (the deadlines of the retired builder) is
scheduling pressure: the target and everything it stands on are picked
first, earliest target first. A target is missed where a hot file or a
serial group was taken by a package with an earlier target or by P0 work;
the wave it lands in is the plan.

- SEC-DEMO-ENTRY: target wave 3, lands in wave 3 - the isolated demo mode
  exists (python -m server.al --demo).
- TC-CARD-PARTS-WEB: target wave 3, lands in wave 3.
- TEST-PORT-LEASE: target wave 3, lands in wave 5.
- TEST-WEB-FMT: target wave 4, lands in wave 8.
- GP-09: target wave 5, lands in wave 5 - the private repository exists and
  the first push is green.
- TEST-SELECT: target wave 5, lands in wave 8.
- AUTO-21: target wave 6, lands in wave 6 - HALT is removed; the headless
  loop takes the loop-owned rows.
- TEST-WAVE-GATE-POLICY: target wave 6, lands in wave 9 - the wave gate
  policy is recorded and the test selector picks each package's subset.
- TEST-WEB-REGISTRY: target wave 6, lands in wave 9.
- TC-WORN-WIRE: target wave 8, lands in wave 11 - the item check compares
  against worn gear (worn-gear baseline).
- TEST-GATE-CALLERS: target wave 8, lands in wave 10 - one gate spelling;
  the whole suite runs in parallel.
- TEST-WEB-ASSEMBLE: target wave 8, lands in wave 12.
- PLAY-LEGACY-OUT-2: target wave 9, lands in wave 11 - the Play tab never
  scrolls (legacy cards are gone).
- All 24 open P0 packages are merged by wave 8; 2 P0 packages are parked
  (GP-12, RUN-LIVE-CLICKS-CLOSE).

## Dedupe, narrowing, folds and cross entries

Dedupe. No unit is delivered twice. Two units (OPEN-13, S5-FOLLOWUP) are
listed by two clusters because they have parts: the guide facts are DATA's
packages, the overlay guide line is OVL's; both lists are kept. Corrections
made to the cluster packages (each package also says so in its notes):

- DEP-02: requirements-dev.txt is created by GP-05 (P0, go-public CI); this
  package edits the existing file and never creates a second one.
- DEP-19: the row template is its own file ops/loop/watch_rows/cpython.json
  (the folder table of LOOP-WATCH-ROWS), not the single
  ops/loop/watch_rows.json that docs/plan/06 named.
- DATA-GGG-APPLICATION: the cluster file left tests empty; the four docs
  checks of its acceptance line are named as run-only tests.
- DATA-PRICE-FALLBACK-RUNBOOK: the cluster file left tests empty; the four
  docs checks of its acceptance line are named as run-only tests.
- TC-OAUTH-REG: the cluster file left tests empty; the four docs checks of
  its acceptance line are named as run-only tests.
- SEC-ACL-APPLY: tracked text names the built-in admins group by its SID
  S-1-5-32-544: the leak sweep of the dev host matches the group's English
  name, so the code comments, test names and docs of this package use the
  SID wording too.
- OVL-KEYS-CORE now depends on SEC-SURFACE-PIN, which creates
  tests/test_security_surface.py.
- OVL-CARD-SLOT now depends on SEC-SURFACE-PIN, which creates
  tests/test_security_surface.py.
- PLAY-TD-04B-THEME-CHOICE now depends on SEC-SURFACE-PIN, which creates
  tests/test_security_surface.py.
- DEP-02 now depends on GP-05, which creates requirements-dev.txt.
- REL-UPDATE-TRIGGER now depends on SEC-SURFACE-PIN, which creates
  tests/test_security_surface.py.
- DEP-19 now depends on AUTO-05, which creates tools/upstream_watch.py.
- RUN-SEAMS now depends on SEC-SURFACE-PIN, which creates
  tests/test_security_surface.py.
- TC-WORN-WIRE now depends on SEC-SURFACE-PIN, which creates
  tests/test_security_surface.py.
- TEST-SUITE-RUNNER now depends on GP-05, which creates
  requirements-dev.txt.
- TEST-HTTP-ROUTES now depends on SEC-SURFACE-PIN, which creates
  tests/test_security_surface.py.
- RUN-P8-8-CHARMIX: tests/test_util_maps_resume.py joined its files (its
  tests entry adds test_map_open_across_restart_is_saved_under_its_character
  to a tracked file).
- Tier corrections (the P0 unit of the package is delivered elsewhere):
  RUN-LEDGER-WIRE is P1: its P0 unit (F-007, strike the desktop-control
  path) is delivered by RUN-LIVE-CLICKS-STRIKE in wave 1; this package
  delivers the P1 parse ledger (F-061); RUN-LEDGER-REPORT is P1: same as
  RUN-LEDGER-WIRE: the P0 strike is RUN-LIVE-CLICKS-STRIKE; the report is
  F-061 (P1); PUB-HOOK-RELEASE-CHECK is P1: the P0 half of F-016 (the
  guarded push) is GP-02 in wave 1; this package adds the release-tag check
  that needs the release tool (P1 chain).

Folds (28; three added by the W22-FOLD ruling, session 18). Rule: same serial group or same file set, same lane and
isolation, none blocked, combined estimate at most 90 minutes; the id of the
higher-tier package is kept and units, tests, files and integrator edits are
joined. The builder adds four guards: no fold across a dependency that runs
through a third package, no member delayed by more than one dependency
level, tiers at most one apart with P0 folded only with P0, and no fold of a
package that carries an operator act. Kept apart by hand: SEC-NO-DISCOVERY,
AUTO-21, LOOP-SPLIT-TICK, GP-09, GP-02, TC-WORN-KEY, TC-WORN-WIRE,
TEST-PLUGIN-PIN (wave-1 or milestone packages whose fold would delay a
chain). Each line: kept id <- folded ids (minutes).

- REL-AUTOSTART-SETTINGS <- REL-UPDATE-UI (85 min)
- PLAY-TD-09C-BAR <- PLAY-MERGE-SEAMS-F5-F7 (70 min)
- TEST-WEB-PANELS-C <- TEST-WEB-PANELS-SHELL (90 min)
- DATA-PRICE-CARD-TEXT <- PLAY-F-120-TRADE-REFRESH (75 min)
- RUN-ZONE-RESET <- TEST-STATE-TEXT-1 (80 min)
- RUN-P8-8-CHARMIX <- TEST-STATE-PUBLISH (85 min)
- RUN-METRICS-SITES <- RUN-LEDGER-CONSENT (90 min)
- SEC-STATIC-MAP <- SEC-CROSS-SITE (90 min)
- PUB-README-PLAYERS <- GP-07 (60 min)
- TC-CARD-PARTS-WEB <- TC-LINK-RECOVER (90 min)
- TC-WEIGHTS-DELTA-UI <- TC-BUILDFILE-TEXTS (90 min)
- OVL-COPY-FIRST <- OVL-CARD-NAME (60 min)
- DATA-CONTACT-FIELD <- DATA-PRICE-REFRESH-CORE (90 min)
- DATA-DIAG-SEAM <- DATA-LEAGUE-PICKER-API (85 min)
- RUN-OBS-LOGS-SHELL <- RUN-START-REASON-CLIENT (60 min)
- RUN-OBS-LOGS-SHELL <- RUN-EXPLAIN-OVERLAY-STATE (90 min)
- RUN-OBS-LOGS-PY <- RUN-CALC-PRIORITY (75 min)
- RUN-VERDICTS-UI <- RUN-REPORT-ROUTE (90 min)
- RUN-FEED-TRUTH <- RUN-PERF-DASH-IDLE (75 min)
- OVL-LINKS-DOWNLOADS <- OVL-SECOND-DISPLAY (85 min)
- DATA-CONTACT-UI <- DATA-LEAGUE-PICKER-UI (85 min)
- DATA-GUIDE-ONE-BLOCK <- DATA-PRICE-NINJA-LINK (70 min)
- RUN-START-REASON-CORE <- RUN-OPLOG (60 min)
- RUN-BUDGET-TESTS-DASH <- RUN-P8-6-CONSOLE (85 min)
- RUN-REPORT-FIELDS <- RUN-UNKNOWN-ITEM-TEXT (90 min)
- OVL-LINE2-GUIDE <- ZONE-CARD-ITEM-GATE (75 min)
- RUN-REPORT-FIELDS <- REPORT-DOC-QUIET (90 min, docstring edit absorbed)
- HOME-REFUSAL-COPY <- RUN-GRID-DESIGN-WORDS, HUD-PLATE-WIDTH-DOC,
  PLAN03-LINE2-WORDING (60 min)

Cross entries (342 in the cluster files). Each was read and resolved one of
three ways: 142 are covered by a dependency on real package ids (the 151
dependency edges added for them are listed in overrides.json under
cross_hard, each with its reason); 192 are ordering or contract notes on a
shared file, which the one-editor-a-wave rule already enforces (either order
works, the second package rebases; where a note named a direction that
matters it became a dependency); 8 point at a unit no package delivers (an
operator act or a deferred unit) and add nothing.

## Operator go for publishing (Q-23)

- Ruling Q-23 asked for the operator's recorded go before anything is
  created or pushed, and CLAUDE.md calls creating the remote an operator act
  until the edits of PUB-GO-DECISION land. The review (floor lens) parked
  the publishing packages because no tracked file held the operator's words.
- Recorded 2026-11-18 (adjudicator LE-01; section Rulings 2026-11-18
  (close-out)): the operator's go-public order in the session brief of
  2026-11-18 is the go for step 1 (create the private repository and push
  main) and for step 4 (make it public once the plan-04 gates pass). Agents
  create the repository, push and flip. The only operator act left for
  publishing is OA-1, gh auth login, and only if `gh auth status` fails.
  docs/plan/04, 05 and 06 carry dated amendments and now agree with this
  section.
- The record is three lines in AL-NEXT-SESSION.txt: `OPERATOR GO Q-23 step 1
  (2026-11-18): "<the operator's own words>"`, `OPERATOR GO Q-23 step 4
  (2026-11-18): "<the same words>"` (one message may be quoted in both
  lines) and `OA-2 SKIPPED IN WRITING (2026-11-18): "<the operator's own
  words>"`. PLAN-LANDING writes them: the main session, which holds the
  brief, copies the words from it verbatim (never from a plan document or a
  ruling) and reads each line back with `grep -c`. A sentence in a plan
  document is not the record.
- Checked 2026-11-18 (close-out 2): the three quoted texts were compared with
  the brief, word for word. The two OPERATOR GO lines quote its first two
  sentences on going public; the OA-2 line quotes its sentence on the one
  operator act left, now with the brief's own backticks around the command.
  What the lines stand for is the reading of a ruling, never the operator's
  wording: that the order is the go for steps 1 and 4 is ruling LE-01, that
  the sentence on the one act left is the written skip of OA-2 is ruling
  LE-38. The hand-off says so directly under the lines.
- Fallback, kept as a live safeguard (adjudicator LE-27): if the main
  session cannot quote the brief verbatim, no line is written and the
  default of Q-23 applies: stay local, GP-02 stays a ready diff, and the
  eight publishing packages go back to wave 99 before wave 1 starts.
  PUB-GO-DECISION re-reads the step 1 line before it writes decision 0046,
  and GP-09 re-reads it as its gate 1.
- Schedule of the eight packages (none of the other packages moved). Wave 4:
  PUB-GO-DECISION (a main-checkout act) with GP-02 and PUB-LOCAL-ONLY-TEXT
  in the first merge batch, in that merge order, so the CLAUDE.md lift and
  the guarded hook land in one integrator commit and no push can happen
  while CLAUDE.md still says local only. Wave 5: GP-09, alone after the last
  batch. Wave 18: PUB-DEPBOT-ACTIONS and PUB-DEPBOT-TICK. Wave 19:
  PUB-DEPBOT-NPM. Wave 22: PUB-HOOK-RELEASE-CHECK. Each sits in the earliest
  wave its deps and file overlaps allow: the files of PUB-LOCAL-ONLY-TEXT
  have other editors in waves 1 to 3 (LOOP-SPLIT-TICK, AUTO-01, AUTO-04,
  TEST-PLUGIN-PIN, LOOP-FAILED-PARK, LOOP-DONE-FOLD), GP-02 and the decision
  land with it in one batch, and GP-09 needs GP-05 (wave 4) in any case, so
  nothing is later than its dependencies force.
- Still in wave 99 behind them: the packages that need the repository to
  exist (GP-10, GP-11, AUTO-19, LOOP-CI-ISSUES, PUB-DEPBOT-FIRST-RUN, then
  PUB-GUIDE-DOWNLOAD-PLACE and DATA-CONTACT-DEFAULT) join the next open wave
  once GP-09's row is flipped. The public flip (GP-12) waits for packages
  only: every P0 unit on origin/main and flip gates 0 to 6 green; gate 0 is
  the step 4 line and gate 5 is met by the OA-2 skip line. GP-13, GP-15,
  GP-16 and AUTO-20 follow the flip. REL-RC-LIVE and DEP-18 still wait for
  the operator's release phrase (OA-13).
- The safeguards stay as gates, not as operator clicks: identity scan 0 and
  leak sweep 0 with the needles armed (the GP-01 needle file includes every
  friend name the operator's order bars) before the first push, private
  first, and the flip only on P0 green plus the re-run scans. A hit stops
  everything and files one rewrite request to MAIN (fleet_rewrite.py, ORDER
  only).
- Default repository address (adjudicator LE-02): the account gh is signed
  in as and the name AshLight, read live at GP-09 (`gh api user --jq
  .login`); OA-5 stays an optional override. No address sits in a tracked
  file until GP-10 writes config/public_repo.json from the real origin
  remote; features that need the address stay off until then. An existing
  repository of that name stops GP-09; it is never reused or overwritten.
- Preparation that needs no remote stays in the open waves: the scans
  (GP-01), the licence record (GP-03), the fresh-clone proof (GP-04), the CI
  files (GP-05) and the community files.
- The headless loop does not push by itself even with a remote: its push
  worker needs the operator's per-host switch loop_push (OA-11, default off).
  The switch is not built yet: PUB-LOCAL-ONLY-TEXT builds it in wave 4
  (reopened 2026-11-18, ruling R2), and GP-09 waits for that package, so no
  remote exists before the switch does. A session reads the loop's commits
  before its own gated push.

## Port block (8960 to 8979)

Five packages took overlapping parts of the block (demo, self-test, test
leases, the two OAuth redirect ports, the dev checkout). The review gives
one table, defined once by SEC-DEMO-CORE (wave 2) in server/al/ports.py and
pinned by tests/test_ports_alloc.py; DEP-05, TC-GGG-LISTENER and
TEST-PORT-LEASE use the constants and redefine nothing.

- 8960: the core (the live checkout, later the installed copy).
- 8961: AL_DEV_PORT, the dev checkout after the cutover; never leased, never a
  fixed test port.
- 8962 to 8969: TEST_LEASE_PORTS (TEST-PORT-LEASE).
- 8970 to 8975: DEMO_BLOCK and SELFTEST_PORTS, one block; both probe for a free
  port.
- 8976 and 8977: spare.
- 8978 and 8979: OAUTH_REDIRECT_PORTS, fixed (registered with GGG), in no other
  range.

## Parked packages (wave 99)

Operator-gated and externally blocked work never blocks an open package: no
package in waves 1 to 37 depends on a parked one. Each line: id, what it
waits on, who unblocks, the exact condition, and the earliest wave it can
join (one after its last unparked dependency).

Shared files inside the parked list. The rule 'one editor of a file per
wave' is checked for waves 0 to 37 only (`python tools/plan_check.py check`;
recomputed without the validator by
tests/test_plan_check.py::test_real_plan_open_waves_share_no_path_or_group).
The parked list is exempt because nothing in it runs; read back 2026-11-18,
these files and serial groups are named by more than one parked package.
The 'joins wave' figure of a package is its earliest wave by dependencies
only: when two packages of one line below are released together they go to
different waves, a dependency before its dependant, each to the first wave
that has no other editor of its files; docs/plan/08 section 9 step 3 is the
move and its check. The same test fails when a line here falls out of step
with packages.json.

- README.md: REL-RC-LIVE, OVL-ITEM-KEY-CTRL.
- server/al/core.py: TC-IMPORT, DATA-LOOT-TALLY, SEC-STEAM-SCAN-A03,
  AUTO-24.
- server/al/state.py: DATA-LOOT-TALLY, TC-WAYSTONE-TUNE.
- web/index.html: TC-BUILD-FILEPICK, TC-WAYSTONE-TUNE-UI, TC-IMPORT-UI.
- web/tc.js: TC-BUILD-FILEPICK, TC-WAYSTONE-TUNE-UI, TC-TREE-URL.
- web/app.js: TC-BUILD-FILEPICK, TC-WAYSTONE-TUNE-UI, TC-IMPORT-UI.
- app/test/tc_view.test.js: TC-BUILD-FILEPICK, TC-WAYSTONE-TUNE-UI,
  TC-TREE-URL.
- server/al/diag.py: SEC-STEAM-SCAN-A03, AUTO-24.
- tests/test_zone_guide.py: DATA-GUIDE-ACTS-5-6, DATA-GUIDE-GAP-TUNE.
- docs/decisions/0002-stack.md: RUN-OVL-BUDGET-CLOSE, OVL-FPS.
- Serial group item-press: TC-IMPORT, TC-WAYSTONE-TUNE.
- Serial group web-tc: TC-BUILD-FILEPICK, TC-WAYSTONE-TUNE-UI,
  TC-IMPORT-UI, TC-TREE-URL.
- Serial group guide-data: DATA-GUIDE-ACTS-5-6, DATA-GUIDE-GAP-TUNE.

Unblocked by operator (21):

- DATA-LOOT-TALLY: waits on a real stackable item text sample confirming the
  stack-size line. Who: operator. Unblock: TC-PRESS-FIXTURES (TC cluster,
  F-082) is merged: the F-082 sample presses were made with the dev-host
  sample switch on (Q-27) and the stackable fixture with its parsed stack
  size is in the tree. Joins wave 37 or later; also behind parked
  TC-PRESS-FIXTURES.
- DEP-18: waits on the public flip, the project's address in tracked files,
  the release build's poe.ninja switch settled (off by default) and the
  operator's release phrase. Who: operator. Unblock: the repository is
  public (go-public flip package done, all P0 packages green at the flip
  commit), the address package has put the real owner/name into the tracked
  config and the README install line, the release build's poe.ninja switch
  is settled (off, or a decision records poe.ninja's yes), and the operator
  types 'release 0.2.0' in an interactive session. Joins wave 35 or later;
  also behind parked REL-RC-LIVE, GP-12, GP-15.
- REL-RC-LIVE: waits on the private remote, the immutable-releases setting
  and the operator's release phrase. Who: operator. Unblock: the private
  repository exists with main pushed and CI green (go-public remote
  package), the guarded pre-push hook with the prepush-check call is merged,
  immutable releases are on before the first v* tag, and the operator types
  'release 0.2.0-rc.1' in an interactive session. Joins wave 25 or later.
- TC-BUILD-FILEPICK: waits on operator decision Q-02 file half: one line in
  the CLAUDE.md read list allowing a file the player picks in AshLight's own
  page (bytes only, never a path or a stored copy). Who: operator. Unblock:
  the operator adds that read-list line to CLAUDE.md in their own words;
  until then nothing of F-058 is built. Joins wave 4 or later.
- SEC-STEAM-SCAN-A03: waits on operator decision A-03 (one floor line: is
  finding Client.txt through Steam's registry key and libraryfolders.vdf on
  the read list); with no answer the stricter reading applies once the typed
  path field exists. Who: operator. Unblock: the hand-off records the
  operator's A-03 answer, or the ROADMAP row of SEC-LOG-PATH-FIELD is
  flipped and no answer is recorded (then the strict branch is built). Joins
  wave 26 or later.
- AUTO-24: waits on operator decision A-01: one floor line saying whether
  GGG's developer-docs pages outside the API Reference and Data Exports may
  be read (the 12 quotes live on the index page). Who: operator. Unblock:
  the operator writes that floor line in CLAUDE.md and it allows the index
  page. Joins wave 18 or later.
- OVL-ITEM-KEY-CTRL: waits on operator decision Q-09 (two one-minute key
  checks). Who: operator. Unblock: the operator reports whether Alt+Shift+E
  / Alt+Shift+A flip the keyboard layout with two layouts installed and
  names one unbound Ctrl+letter next to C from the game's key binds. Joins
  wave 17 or later.
- AUTO-26: waits on the WorktreeCreate and WorktreeRemove hook entries of
  decision 0012 are not in .claude/settings.json (an agent may not edit
  settings). Who: operator. Unblock: .claude/settings.json names
  tools/wt_sidecar_hook.py under both WorktreeCreate and WorktreeRemove.
  Joins wave 3 or later.
- PLAY-MAP-MODE-ON: waits on A live sighting of the endgame map area prefix
  in the parse ledger of F-061 (RUN cluster). Who: operator. Unblock: python
  tools/live1_report.py (built by RUN-LEDGER-REPORT) prints VERIFIED live
  for the endgame Map area-id prefix item of LIVE-1, after the operator has
  ticked the parse-ledger consent line once and played one map normally.
  Joins wave 19 or later.
- TC-PRESS-FIXTURES: waits on six item presses in normal play with
  dev_press_samples on (rare gear, a unique, a currency stack, a waystone, a
  tablet, a gem; plain and advanced copy). Who: operator. Unblock: at least
  six sanitized candidate files, one per shape, exist under the sidecar
  Scratch press-samples folder. Joins wave 21 or later.
- DATA-GUIDE-GAP-TUNE: waits on two weeks of level-minus-zone-level data per
  campaign zone exit. Who: operator. Unblock: the parse ledger packages
  (RUN-LEDGER-CORE, RUN-LEDGER-CONSENT (folded into RUN-METRICS-SITES),
  RUN-LEDGER-WIRE; F-061) are merged with the per-exit gap bucket, the
  operator has ticked the ledger consent, and the dev host's ledger spans 14
  days of campaign play. Joins wave 17 or later.
- TC-TREE-URL: waits on a cached GGG tree export on the dev host for the
  fixture and the byte-value check (needs web data on with the contact set:
  operator act g). Who: operator. Unblock: the file
  Cache/gamedata/skilltree.json exists under the AL sidecar root
  (treedata.FILE_NAME) after the operator sets the contact and the snapshot
  runs. Joins wave 36 or later.
- PLAY-F-204B-SR-RUN: waits on The operator confirms the game is closed (not
  only that they are not playing) and game_idle is true; speech output and a
  visible browser on this machine. Who: operator. Unblock: The operator says
  in their own words that the game is closed and allows one run with speech
  output and a visible browser; the agent then runs python tools/sr_pass.py
  with the operator flag once, game_idle true, and commits the transcript.
  Joins wave 30 or later.
- RUN-LIVE-CLICKS-CLOSE: waits on one normal login to town or hideout while
  the core runs. Who: operator. Unblock: python tools/live1_report.py prints
  the five TEST-LIVE-CLICKS fields as seen. Joins wave 19 or later.
- RUN-OVL-BUDGET-CLOSE: waits on budget-log rows from normal in-map play.
  Who: operator. Unblock: python -m server.al.budgetlog check prints 10 or
  more rows tagged in map with the overlay shown. Joins wave 25 or later.
- OVL-FPS: waits on one normally played map with tools/ovl_check.py armed
  (Q-18, budget B19). Who: operator. Unblock: the sidecar Logs dir holds an
  ovl_check report JSON that includes the operator's same / dropped answer.
  Joins wave 22 or later.
- RUN-BUILDFILE-LIVE-CLOSE: waits on the operator loads one AshLight-made
  .build in game and clicks Worked or Refused. Who: operator. Unblock:
  ops/runtime/verdicts.json holds a TC-BUILDFILE-LIVE verdict. Joins wave 20
  or later.
- RUN-VERDICTS-CLOSE: waits on three in-game tries by the operator, one
  verdict click each. Who: operator. Unblock: ops/runtime/verdicts.json
  holds verdicts for LIVE-SEARCHSTR, LIVE-FILTER and LIVE-FILTER-MERGE.
  Joins wave 20 or later.
- LOOP-KIT-REPORT-SEND: waits on no outbound note path: loop.dest_inboxes in
  the gitignored config/local.json has no entry for the fleet owner and no
  fleet roster is configured. Who: operator. Unblock:
  loop_base.load_config(root)['dest_inboxes'] holds a MAIN entry (set on the
  host by the operator, or supplied by the fleet owner). Joins wave 3 or
  later.

Unblocked by GGG or poe.ninja (4):

- TC-IMPORT: waits on GGG reopens OAuth registration (the docs watch raises
  ops/runtime/ggg_docs/REG_OPEN) and grants AshLight a public client; event
  fetches and stored refresh also wait for GGG's written answers to F-083
  questions 1 and 2. Who: GGG. Unblock: a client id granted to AshLight is
  recorded in gitignored config/local.json after the operator sends the
  prepared application (F-149). Joins wave 18 or later; also behind parked
  TC-OAUTH-REG.
- DATA-NINJA-RELEASE-ON: waits on poe.ninja's answer to the Q-05 message.
  Who: poe.ninja. Unblock: the operator pastes poe.ninja's written yes (or
  its mirror request, which opens a new decision instead); silence is not
  consent. Joins wave 19 or later.
- DATA-GUIDE-ACTS-5-6: waits on PoE2 1.0 is live and a 1.0 world_areas
  snapshot is cached on the dev host. Who: GGG. Unblock: the launch gate
  GATE-POE2-10 (F-052 / AUTO-07) has flipped: local date 2026-12-11 or later
  and the snapshot metadata shows 1.0; the cache refresh needs web data on
  and the contact set on the dev host (batched ask act g), or an
  operator-run build.ps1 -Snapshot. Joins wave 19 or later.
- TC-OAUTH-REG: waits on GGG reopens OAuth application registration. Who:
  GGG. Unblock: ops/runtime/ggg_docs/REG_OPEN exists (the settled decision
  0044 watch; its index-page read is under operator decision A-01), or the
  hand-off holds the operator's own line 'REG OPEN (operator)'. Joins wave 2
  or later.

Unblocked by another package (13; GP-10 and AUTO-19 joined wave 18 and
LOOP-CI-ISSUES wave 22 at the wave 18 start, session 16):

- TC-WAYSTONE-TUNE: waits on a real waystone sample as a fixture. Who:
  package TC-PRESS-FIXTURES. Unblock: tests/fixtures/press holds a reviewed
  waystone fixture. Joins wave 26 or later; also behind parked
  TC-PRESS-FIXTURES.
- TC-WAYSTONE-TUNE-UI: waits on the core half. Who: package
  TC-WAYSTONE-TUNE. Unblock: TC-WAYSTONE-TUNE is merged. Joins wave 36 or
  later; also behind parked TC-WAYSTONE-TUNE.
- TC-IMPORT-UI: waits on the core half of the import. Who: package
  TC-IMPORT. Unblock: TC-IMPORT is merged. Joins wave 4 or later; also
  behind parked TC-IMPORT.
- AUTO-20: waits on Dependabot alerts and pull requests exist only after the
  public flip. Who: package GP-12. Unblock: the repository is public (GP-12
  done) and .github/dependabot.yml and tools/dependabot_reapply.py are on
  main. Joins wave 19 or later; also behind parked AUTO-19, LOOP-CI-ISSUES,
  GP-12.
- TC-AFFIX-LINE: waits on a real advanced-copy item sample as a fixture.
  Who: package TC-PRESS-FIXTURES. Unblock: tests/fixtures/press holds a
  reviewed advanced-copy gear fixture. Joins wave 3 or later; also behind
  parked TC-PRESS-FIXTURES.
- GP-16: waits on ordered after the public flip (plan 04 order, step 7).
  Who: package GP-12. Unblock: `gh repo view "$R" --json visibility --jq
  .visibility` prints PUBLIC. Joins wave 1 or later; also behind parked
  GP-12.
- GP-12: waits on every P0 unit of the plan on origin/main, and flip gates 0
  to 6 green. Who: packages. Unblock: `grep -c "^OPERATOR GO Q-23 step 4"
  AL-NEXT-SESSION.txt` prints 1 and the line quotes the operator's own words
  with their date, `grep -c "^OA-2 SKIPPED IN WRITING" AL-NEXT-SESSION.txt`
  prints 1, and `python -m pytest -q tests/test_http_security.py
  tests/test_tc_code.py tests/test_no_discovery.py` is green on the commit
  at origin/main. Joins wave 19 or later; also behind parked GP-10, GP-11.
- GP-11: moved to wave 9 on 2026-11-19 (the repository exists; GP-09 is done).
- GP-13: waits on the public flip (rulesets and free secret scanning need a
  public repository on a personal account). Who: package GP-12. Unblock: `gh
  repo view "$R" --json visibility --jq .visibility` prints PUBLIC. Joins
  wave 19 or later; also behind parked GP-12.
- GP-15: waits on the public flip. Who: package GP-12. Unblock: `gh repo
  view "$R" --json visibility --jq .visibility` prints PUBLIC. Joins wave 19
  or later; also behind parked GP-12.

## Coverage

All 387 input units (docs/plan/01 to 06, and 4 the review added from
docs/plan/findings.json) are in the coverage map of packages.json: mapped to
packages, or closed with a reason. Nothing was dropped. A unit that a
package lists is mapped to that package even when an operator gate holds it;
the gate is then the package's blocked field (7 units changed from an
operator string to their packages: CARRY-11, F-040, F-054, F-058, OPEN-04,
OPEN-17, OVL-FPS). Per kind: units, mapped to packages (of which every
delivering package is parked), operator, not adopted, done.

- findings (F-..): 211 units; 202 mapped (13 parked); 1 operator; 8 not
  adopted; 0 done.
- open items (OPEN-..): 50 units; 42 mapped (6 parked); 1 operator; 2 not
  adopted; 5 done.
- automation packages (AUTO-..): 26 units; 26 mapped (4 parked); 0 operator;
  0 not adopted; 0 done.
- carried hand-off items (CARRY-..): 24 units; 17 mapped (4 parked); 4
  operator; 1 not adopted; 2 done.
- target design steps (TD-..): 23 units; 23 mapped (0 parked); 0 operator; 0
  not adopted; 0 done.
- deployment steps (DEP-..): 19 units; 19 mapped (1 parked); 0 operator; 0
  not adopted; 0 done.
- go-public steps (GP-..): 16 units; 16 mapped (3 parked); 0 operator; 0 not
  adopted; 0 done.
- open ROADMAP rows: 14 units; 13 mapped (2 parked); 0 operator; 1 not
  adopted; 0 done.
- operator decisions without a unit until the review (A-..): 2 units; 1
  mapped (1 parked); 1 operator; 0 not adopted; 0 done.
- research gaps (RG-..): 2 units; 2 mapped (0 parked); 0 operator; 0 not
  adopted; 0 done.
- Total: 387 units; 361 mapped (34 parked); 7 operator; 12 not adopted; 7
  done.

Not adopted, with the reason (12):

- CARRY-12 (Operator act (b): LIVE-1 play session and one login): no
  separate play session is asked for; the LIVE-1 lines close from normal
  play through the parse ledger (RUN-LEDGER-WIRE). One operator act remains
  and is in the batch: the ledger consent tick of F-061 (docs/plan/06
  operator act 4); RUN-LIVE1-FIXTURES and PLAY-MAP-MODE-ON wait for it
- F-206 (TC-CURX: currency exchange history): deferred (F-206 disposition):
  no call without an AshLight OAuth client or GGG's written exemption
  (question 3 of DATA-GGG-APPLICATION); cut if poe.ninja's exchange data
  stays sufficient; the ROADMAP row stays BLOCKED
- F-207 (PRICE-VARIANT: a range when several variants match): deferred:
  needs a real item-overview body to confirm that lines carry 'variant';
  revisit after DATA-PRICE-TYPE-PROOF
- F-208 (Peek key for one-screen players): deferred (P4): needs an operator
  taste call, no demand evidence, and the detail must fit the one overlay
  card slot; the companion is never shown over the game (floor audit L1).
- F-209 (PRICE-OVERRIDE: player price overrides): deferred: no demand
  evidence; revisit with F-207
- F-210 (Scoop manifest by the release tool; winget later): deferred (P4):
  the scoop manifest was not checked against the per-user home layout; plan
  05 revisits it after the first public release; winget waits for a signed
  exe or installer
- F-212 (Spike: one press per item by a screen read): deferred spike (one
  screen read per press); after the changed item key the saving is one key
  press per item; no wave before 1.0; the pick-one-of-N recommender
  (0056-Q2) waits with it
- F-213 (CLOCK-STEP: timers survive a clock change): not in this plan (P4,
  low impact, many stamps): no package and no row carries it. Trigger to
  take it up: a wall-clock jump is seen to misfire a timer after
  RUN-SUPERVISOR-CLOCK has landed; one row is filed then
- F-214 (Shared server fixture): not in this plan (duplication only: one
  al_server factory for the 28 serve_forever copies; research 0049 R12): no
  package and no row carries it. Trigger to take it up: a package that
  already edits those test files may fold it in and says so in its result
- OPEN-09 (TC-CURX: hourly exchange history from GGG's Currency Exchange
  API): no package in this plan; the unit is blocked, not dropped (F-206
  disposition): no call without an AshLight OAuth client or GGG's written
  exemption (question 3 of DATA-GGG-APPLICATION); cut if poe.ninja's
  exchange data stays sufficient; the ROADMAP row stays BLOCKED
- OPEN-48 (L16 persisting the S5 (b) upgrade list needs a 0045 amendment):
  ruling Q-26 (b): the BUILD-LIVE upgrade list stays memory-only; reverses
  only on a decision 0045 Reverses-if
- TC-CURX (TC-CURX (build) hourly exchange history): no package in this
  plan; the unit is blocked, not dropped (F-206 disposition): no call
  without an AshLight OAuth client or GGG's written exemption (question 3 of
  DATA-GGG-APPLICATION); cut if poe.ninja's exchange data stays sufficient;
  the ROADMAP row stays BLOCKED

Operator-gated (no package can deliver it) (7):

- A-02 (Floor audit, optional: does the User-Agent bullet bind package
  tool...): A-02 (optional, floor audit) in the one batched ask
  docs/plan/09-operator-acts.md; default in force: strict (npm sends an
  AshLight User-Agent, Electron comes only through AshLight's own fetch
  code, no AshLight script runs pip); an 'own requests only' answer drops
  the .npmrc line and blocks nothing
- CARRY-15 (Operator act (e): logon autostart scripts/autostart.ps1 -Enable
  (op...): OA-7 = hand-off act (e), logon autostart, scripts/autostart.ps1
  -Enable; default in force: OFF (decision 0011, optional). No agent work
  waits on it; after REL-AUTOSTART-SWITCH it is one tick in the tray menu
  instead of a typed command
- CARRY-16 (Operator act (g): UA contact in config/local.json plus web_data
  on...): OA-8 = hand-off act (g): set the User-Agent contact and turn web
  data on on the dev host; default in force: web data off, no contact, no
  poe.ninja request, the trade link only (after DATA-CONTACT-FIELD the
  contact is typed in the dashboard; DATA-PRICE-TYPE-PROOF is the agent work
  that follows)
- CARRY-18 (Operator act (k): review decision 0017 (trade link only)): OA-9
  = hand-off act (k): optional review of decision 0017; default in force:
  0017 stands (the app calls no trade endpoint, it only builds a link;
  ruling Q-06)
- CARRY-19 (OPERATOR DECISION: phone view needs LAN access; CLAUDE.md keeps
  LAN...): Q-11 (phone view). Unblock: the operator names P1, design B or
  design C, or orders a phone view; a decision is then recorded before any
  work (design C also lifts or scopes the bind rule and amends the decision
  0002 token wording). Default in force until then: P0 / design A, no
  AshLight network pa...
- F-205 (Phone view / LAN): Q-11 (phone view). Unblock: the operator names
  P1, design B or design C, or orders a phone view; a decision is then
  recorded before any work (design C also lifts or scopes the bind rule and
  amends the decision 0002 token wording). Default in force until then: P0 /
  design A, no AshLight network pa...
- OPEN-18 (OP-PHONE-LAN: operator decision on a phone view (P0 to P4)): Q-11
  (phone view). Unblock: the operator names P1, design B or design C, or
  orders a phone view; a decision is then recorded before any work (design C
  also lifts or scopes the bind rule and amends the decision 0002 token
  wording). Default in force until then: P0 / design A, no AshLight network
  pa...

Done (nothing left to do) (7):

- CARRY-21 (NOTE: session-5 reap (done in session 6)): AL-NEXT-SESSION.txt
  'Session start checks' records the session-5 reap done in session 6 with
  its read-back; the NOTE bullet is dropped at the next /done
- CARRY-23 (NOTE: tree created 2026-11-16 by MAIN (informational)):
  informational; the NOTE 'tree created 2026-11-16 by MAIN' stays verbatim
  in AL-NEXT-SESSION.txt
- OPEN-20 (NOTE session-5 reap (obsolete; drop at the next /done)):
  AL-NEXT-SESSION.txt 'Session start checks' records the session-5 reap done
  in session 6 with its read-back; the NOTE bullet is dropped at the next
  /done
- OPEN-22 (NOTE: tree created by MAIN (informational, keep verbatim)):
  informational; the NOTE 'tree created 2026-11-16 by MAIN' stays verbatim
  in AL-NEXT-SESSION.txt
- OPEN-40 (L8 no TODO / FIXME markers outside kit and docs (no action)):
  docs/plan/01-open-items.md L8 - no TODO, FIXME, XXX or HACK marker exists
  outside the vendored kit and docs; no action
- OPEN-43 (L11 decision number 0035 intentionally unused; next free 0046 (no
  a...): docs/decisions/README.md records 0035 as intentionally unused; the
  next free number was 0046 when the item was written and is 0079 since
  2026-11-18 (section Reserved decision numbers); no action
- OPEN-47 (L15 LaneLoop task enabled while HALT is set (no defect; do not
  rein...): no defect; the LaneLoop task stays enabled while HALT is set
  (01-open-items L15) and AUTO-21 neither reinstalls nor runs it

Mapped but waiting: 34 units are delivered only by parked packages (A-03,
AUTO-19, AUTO-20, AUTO-24, AUTO-26, CARRY-04, CARRY-05, CARRY-09, CARRY-13,
DEP-18, F-006, F-051, F-057, F-058, F-080, F-100, F-149, F-150, F-182,
F-183, F-184, F-200, F-202, GP-11, GP-12, GP-16, OPEN-08, OPEN-24, OPEN-25,
OPEN-26, OPEN-28, OPEN-37, TC-BUILDFILE-LIVE, TC-IMPORT); they close when
those packages leave wave 99.

## HALT removal and the headless loop

HALT (ops/loop/control/HALT) may be removed after these packages are on main
with one whole green suite: AUTO-01, LOOP-HANDOFF-PREFIX,
LOOP-PREFLIGHT-CMD, LOOP-FAILED-PARK, AUTO-02, AUTO-03, LOOP-ROWFILES-MERGE,
LOOP-ROWFILES-WORK, LOOP-DONE-FOLD, AUTO-04, AUTO-06, LOOP-WAVE-HOLD,
TEST-PLUGIN-PIN. AUTO-21 is the last act of wave 6 (session 2): the six
checks of F-078 (docs/plan/06, The point at which HALT is removed), each
with its read-back, then the marker is deleted and the next tick is read
back. Docs/plan/06 expected this before wave 2; the verified loop packages
form a chain of dependencies and shared loop modules, so the earliest
possible wave is 6. It stays far ahead of the 2026-12-04 date. A red check
leaves HALT in place; AUTO-21 then runs again as the first act of the next
wave, and the loop-owned rows are released only when all six read green.

What the loop needs to respect the plan's dependencies, all landed before
AUTO-21:

- LOOP-ROWFILES-WORK (wave 3): the work list waits on `DEPENDS: <ids>` in
  the row text. `python tools/plan_check.py rows` prints that tag for every
  package with deps, so the landed ROADMAP rows carry it; no per-row plan
  document is needed.
- For a loop-owned package the builder also puts the last earlier editor of
  each of its files into deps, so two rows never work one file at the same
  time and the loop never edits a file ahead of a session package (each such
  package says so in its notes).
- AUTO-06 (wave 5) and LOOP-WAVE-HOLD (wave 4): the BLOCKED reason is
  echoed, a row tagged between work list and dispatch is skipped, a diff
  under a folder a wave holds is parked as wave-hold, and the wave's merge
  agent takes the loop's merge lock.
- LOOP-HANDOFF-PREFIX (wave 2) and AUTO-01 (wave 2): hand-off bullets are
  loop work only with `LOOP:`; a dry run past HALT lists what would be
  dispatched.
- Every session row carries `BLOCKED: session wave <n>` (printed by
  plan_check rows); a row without the word is the loop's.

Loop-owned rows (16). The test for the mark: no design review, no operator
act, no hotspot file, nothing under web/, app/overlay/, app/shared/ or the
loop's own code, no new decision or Settled bullet, no test tied to live
processes, no P0 or first-value work, and no session package waiting on it.
The share is small because most of this plan is hot-file or design work: 103
design review; 53 a session package depends on it; 42 P0 or first-value
path; 41 integrator edit beyond the row (decision, Settled bullet, index);
37 hotspot file; 24 held folder or the loop's own code; 12 test tied to live
processes; 10 main-checkout act; 7 operator act; 2 forced. At 2 to 8
headless runs a row and 85 runs a day left for plan rows (docs/plan/06, Runs
budget) the loop needs 1 to 2 days for them, beside the watcher rows.

- OVL-CLIENT-ZOOM [released after wave 6; M 50m, build] Probe and restore zoom in the desktop client. DEPENDS: OVL-MAIN-PARTS.
- AUTO-23 [released after wave 6; M 35m, build] DEV-LEDGERS: rotate the sub-agent ledger, flag a stale docs watch, tidy suite logs. DEPENDS: none.
- TEST-LOOP-SPLIT-MERGE [released after wave 10; L 75m, build] Loop tests split 1: merge, gates and dependency themes to tests/test_al_loop_merge.py. DEPENDS: TEST-GATE-CALLERS, AUTO-01, LOOP-HANDOFF-PREFIX, LOOP-PREFLIGHT-CMD, LOOP-FAILED-PARK, LOOP-TESTS-CARVE, AUTO-21, TEST-LAYOUT-GUARD.
- TEST-LOOP-SPLIT-LANES [released after wave 11; L 75m, build] Loop tests split 2: lane themes to tests/test_al_loop_lanes.py. DEPENDS: TEST-LOOP-SPLIT-MERGE.
- REL-INSTALL-CALC [released after wave 11; M 40m, build] Installer package: calc opt-in in an installed copy. DEPENDS: REL-INSTALL-HOME, DEP-06, TC-CALC-OPTIN.
- TEST-LOOP-GIT-TEMPLATE [released after wave 12; M 40m, build] git_world from a session-scoped template copy. DEPENDS: TEST-LOOP-SPLIT-LANES.
- REL-UNINSTALL-CHECKOUT [released after wave 13; M 45m, build] Uninstall: checkout mode. DEPENDS: REL-UNINSTALL-SHELL.
- RUN-METRICS-PROBE [released after wave 13; S 25m, build] python -m server.al.probe: one line per item, exit 0 live, 1 stopped. DEPENDS: RUN-METRICS-CORE.
- TEST-LOOP-STUB-GIT [released after wave 13; L 75m, build] Stub git runner for the tick tests that do not test git. DEPENDS: TEST-LOOP-GIT-TEMPLATE.
- SEC-CEIL-WEBFETCH [released after wave 15; S 30m, build] A total deadline per outbound request. DEPENDS: RUN-METRICS-SITES.
- TC-ASC-FROM-TREE [released after wave 16; M 45m, build] Ascendancy names from the cached tree export. DEPENDS: TC-CHARJSON-SHAPES, TC-VERDICT-CAVEAT, DATA-TREE-HOLD, DATA-LEAGUE-IDENTITY.
- DATA-SNAP-SETUP [released after wave 18; S 25m, build] setup.ps1 runs the game-data snapshot when web data is already on. DEPENDS: REL-RUNTIME-SCRIPTS.
- DATA-TRADESTAT-COVERAGE [released after wave 18; M 35m, build] Count trade stat id coverage per source before retiring the PoB fallback. DEPENDS: DATA-DIAG-SEAM, TC-UPGRADE-PER-SLOT.
- TC-BUILDFILE-EXIT-WATCH [released after wave 18; M 35m, review] .build exit trigger from the PoB release check. DEPENDS: TC-CALC-VERIFY-PIN, AUTO-12, AUTO-05, LOOP-DRIFT-REF.
- SEC-CEIL-SNAPSHOT [released after wave 24; M 45m, build] Snapshot fetch: deadline, per-source cap on disk, one URL check. DEPENDS: SEC-CEIL-WEBFETCH, DATA-SNAP-TRIM.
- PLAY-F-165-COLOUR-WORD-TEST [released after wave 27; S 25m, build] Test: colour never works alone. DEPENDS: PLAY-TD-22A-A11Y-CSS.

Later rows the loop may take without a plan change: every watcher row the
frame files (docs/plan/06, Rows the loop may take while sessions run waves),
requested dives, and any parked package that leaves wave 99 and passes the
same test; a session sets its owner in packages.json and re-runs the
validator.

## Reserved decision numbers

Numbers 0046 to 0076 are reserved in wave and merge order (research 0047 R1:
no agent takes the next number). A decision written outside a package takes
the next number after this block. Two are taken that way, both written in the
planning session on 2026-11-18: 0077 (ultraplan execution model) and 0078
(ultraplan rulings ledger). The next free number is 0079. A number already
handed out never moves (the reserved_decisions list of packages.json): the
go-public decision kept 0046 while its package was parked and keeps it in wave
4.

- 0046-go-public.md: PUB-GO-DECISION (wave 4)
- 0047-licence-and-notice.md: GP-03 (wave 1)
- 0048-ggg-oauth-client.md: DATA-GGG-APPLICATION (wave 1)
- 0049-demo-mode.md: SEC-DEMO-CORE (wave 2)
- 0050-research-dive-sources.md: AUTO-04 (wave 2)
- 0051-private-runtime-files.md: SEC-ACL-APPLY (wave 4)
- 0052-tc-worn-gear.md: TC-WORN-STORE (wave 4)
- 0053-main-process-parts.md: OVL-MAIN-PARTS (wave 4)
- 0054-core-hello.md: SEC-HELLO-CORE (wave 4)
- 0055-loop-and-wave-contract.md: AUTO-06 (wave 5)
- 0056-plug-seams.md: RUN-SEAMS (wave 5)
- 0057-tc-campaign-keep.md: TC-CAMPAIGN-KEEP (wave 5)
- 0058-hotkeys-live.md: OVL-KEYS-CLIENT (wave 5)
- 0059-installed-home-layout.md: DEP-05 (wave 7)
- 0060-wave-gate-policy.md: TEST-WAVE-GATE-POLICY (wave 9)
- 0061-electron-shell-guards.md: OVL-SHELL-GUARDS (wave 9)
- 0062-changelog.md: DEP-04 (wave 9)
- 0063-installed-runtimes.md: REL-RUNTIME-PINS (wave 10)
- 0064-release-artifact.md: DEP-08 (wave 10)
- 0065-update-policy.md: DEP-16 (wave 11)
- 0066-uninstall-consent.md: DEP-10 (wave 12)
- 0067-observability-records.md: RUN-METRICS-CORE (wave 13)
- 0068-electron-npm-supply-chain.md: OVL-ELECTRON-SETUP (wave 13)
- 0069-upstream-watch-frame.md: AUTO-05 (wave 13)
- 0070-electron-upgrade-policy.md: LOOP-ELECTRON-POLICY (wave 14)
- 0071-parse-ledger.md: RUN-METRICS-SITES (wave 15)
- 0072-poe-ninja-cadence-and-release-gate.md: DATA-PRICE-CADENCE (wave 18)
- 0073-versioning-release-trigger.md: REL-PUBLISH-GATES (wave 21)
- 0074-player-notes.md: PLAY-F-186A-PLAYER-NOTES-STORE (wave 29)
- 0075-fixed-cockpit-play.md: PLAY-TD-23-RECORDS (wave 31)
- 0076-ci-issue-protocol.md: AUTO-19 (wave 18)

Taken outside a package (not reserved, listed so the next number is plain):

- 0077-ultraplan-execution-model.md: taken 2026-11-18 (planning session)
- 0078-ultraplan-rulings-ledger.md: taken 2026-11-18 (planning session)
- 0079: the next free number

## Contract lines for package agents

- Progress: the last progress write of a task carries the outcome in its
  step text, `done: <result>` or `failed: <cause>`, not the last working
  step (F-198).
- Ledgers: a package never edits ROADMAP.md, CLAUDE.md, AL-NEXT-SESSION.txt,
  the README indexes or docs/design/reviews.log. It returns its row flip,
  review line, Settled line and index line in its result and the integrator
  applies them; decision numbers are the reserved ones (F-017).
- Loop and wave: the loop and a session never take the same row (section
  HALT removal and the headless loop; docs/plan/06, Loop and wave interplay;
  F-033).
- docs/plan/08-orchestration.md (written in the planning session, checked by
  PLAN-LANDING in wave 0) states the same three once more together with how
  a session runs a wave.

## Review record

The draft of this section was reviewed by three independent lenses: coverage
(is every input unit carried), execution (can the waves run as written) and
floor (Game ToS floor and operator authority). Every finding was checked
against the repository before it was applied. Severity S1 blocks the plan,
S2 breaks a wave or drops work, S3 is a smaller fault.

- coverage: 14 findings (1 S1, 6 S2, 7 S3).
- execution: 22 findings (1 S1, 11 S2, 10 S3).
- floor: 14 findings (2 S1, 5 S2, 7 S3).
- All lenses: 50 findings (4 S1, 22 S2, 24 S3). Every S1 and S2 was applied,
  some in another form than the reviewer proposed; no finding was rejected
  outright. The lines under 'Not applied as written' name every part that
  was not taken.
- Before the review: 394 packages (41 parked), 37 open waves, 9 sessions,
  383 units. After: 396 packages (49 parked), wave 0 and 37 open waves, 10
  sessions after the landing, 387 units.

What changed:

- Plan landing (coverage S1, S2): PLAN-LANDING in wave 0 writes docs/plan/08
  and 09, lands the ROADMAP rows and rewrites the hand-off; CARRY-24 is
  mapped to it instead of 'done by construction'; LOOP-PLAN-CONTRACT is
  dropped and its units (F-198, OPEN-44) move there; its test file
  tests/test_plan_operator_acts.py fails when an operator unit, a package
  operator act or an operator decision is missing from 09. (Close-out
  2026-11-18: 08 and 09 were then written in the planning session itself;
  PLAN-LANDING lists them under files and checks them.)
- Gate order (execution S1): the integrator's edits for a batch are
  committed on the integration worktree before the batch suite, so the
  Settled-list tests no longer make every decision-writing batch red;
  SEC-NO-DISCOVERY's whole suite runs after its own bullet.
- Operator go for publishing (floor S1, coverage S2, execution S2): GP-09
  and the packages that lift the local-only order (GP-02, PUB-GO-DECISION,
  PUB-LOCAL-ONLY-TEXT) are parked until the hand-off quotes the operator's
  own words; four packages behind them are parked with them
  (PUB-HOOK-RELEASE-CHECK, PUB-DEPBOT-ACTIONS, PUB-DEPBOT-NPM,
  PUB-DEPBOT-TICK); GP-12 and DEP-18 need the separate words for the flip;
  the milestone 'the private repository exists' left session 2; the
  dependency of REL-PUBLISH-GATES on GP-02 was removed (it edits no hook
  file; PUB-HOOK-RELEASE-CHECK adds the hook line), so the release tooling
  stays in the open waves.
- Loop push (floor S2): the loop's push worker needs the operator's per-host
  switch loop_push (default off), to be built by PUB-LOCAL-ONLY-TEXT (reopened
  2026-11-18, ruling R2; wave 4, before GP-09 adds origin); the stale 'the
  loop is HALTed' assumption left GP-10.
- Steam library scan (floor S1, coverage S2): operator decisions A-02 and
  A-03 are units now; A-03 is carried by the parked package
  SEC-STEAM-SCAN-A03, whose default is the stricter reading (scan removed)
  once the typed path field exists; both are in the batched ask with the
  strict answer first.
- Docs watch pages (floor S2): the REG_OPEN consumers (DATA-GGG-APPLICATION,
  TC-OAUTH-REG, TC-IMPORT, LOOP-WATCH-SETTLED, AUTO-11) name operator
  decision A-01; no new automation is built on the index page while it is
  open; the operator's own report is the second signal.
- REG_OPEN session check (coverage S2): the hand-off line is deleted by
  LOOP-WATCH-SETTLED on three read-backs, not by DATA-GGG-APPLICATION;
  CARRY-01 closes there.
- Route surface pin (execution S2, floor S2): tests/test_security_surface.py
  joined the files of TEST-HTTP-ROUTES (it switches the helper to the route
  tables), RUN-SEAMS and the ten packages that add or remove a route;
  RUN-LEFTOVERS-CORE removes the stub by table entry, not by line range.
- Early-wave test rules (execution S2): timing files and subsets over 90 s,
  and the fixed-port files, go through the suite gate until TEST-SELECT and
  TEST-PORT-LEASE are on main.
- Gate spelling (execution S2): the batch gate reads `python
  tools/suite_run.py` in every wave after TEST-GATE-CALLERS.
- Packages that must not overlap (execution S2): GP-04 merges last, rebased,
  as a batch of one; REL-CUTOVER-LIVE runs alone after the last batch of its
  wave; main-checkout acts run one at a time; AUTO-12 depends on
  TC-BRIDGE-NEXT; TC-CAMPAIGN-KEEP owns tests/test_eval_text.py and
  tests/test_price_text.py; PUB-LOCAL-ONLY-TEXT is written by string anchor.
- Tracked fixtures and installer (floor S2): TC-PRESS-FIXTURES tracks only
  invented item text with a test that refuses a real base or unique name;
  DEP-09 passes an AshLight User-Agent on every web call and its test fails
  without it.
- Folded ids (coverage S2): a folded id in package text now names the
  package that holds it (26 places), and the builder refuses any
  package-like id that is no package, unit, ROADMAP row or listed later row
  id.
- Research gaps (coverage S2, S3): DATA-RESEARCH-GAPS carries the triage
  table of note 0056 and the adopted-patterns register of note 0055 (units
  RG-0056, RG-0055).
- Coverage wording (coverage S3): RUN-DURABLE-CRLF lists its three carried
  units and the stop.ps1 / run.ps1 re-test; operator-gated units that a
  package lists are mapped to it; CARRY-15, CARRY-16 and CARRY-18 carry the
  ids OA-7, OA-8 and OA-9; CARRY-12, F-213, F-214, OPEN-09 and TC-CURX say
  what really happens to them.
- Smaller execution points (S3): wave 1 batches of 5 with the boundaries
  printed per wave; decision numbers reserved for TC-CAMPAIGN-KEEP and
  TC-WORN-STORE; one port table (section Port block); rows are flipped,
  never added twice; a loop term and a fold term in the wave time; larger
  estimates for PLAY-TD-09A-REGION-HOOK, TEST-WEB-SRCPATHS-NODE and
  TEST-MARKS; AUTO-21 may run again in a later wave; creator edges for
  DEP-17 and TEST-LOOP-SPLIT-MERGE; GP-05 names its gh fallback.
- Smaller floor points (S3): the price fallback note names the exchange only
  with a written GGG grant; SEC-HELLO-CORE's reading of the token rule goes
  to a distinct adjudicator before merge; the runtime is named by exact
  version and sha256; DEP-18 lists the second-machine install as an optional
  act; TC-ASC-FROM-TREE adds no name to a tracked table; two stale wordings
  (OVL-CHECK, AUTO-15) are fixed.

Not applied as written (one line each, with the reason):

- Validator rules in tools/plan_check.py (coverage S1: fail when an operator
  unit is missing from 09; coverage S2: fail on an unknown package-like id):
  not added there, because this section changes two files only; the first is
  PLAN-LANDING's test file, the second a refusal of the builder.
- Route pin for RUN-METRICS-SITES, DATA-CONTACT-FIELD, DATA-DIAG-SEAM,
  TC-WEIGHTS-DELTA-STORE and OVL-KEYS-WEB (execution S2, floor S2): not
  given the pin file; checked against their own text, they add no path (new
  fields on existing routes, or the client side of a route another package
  adds).
- TEST-PORT-LEASE into wave 1 (execution S2, one of two offered fixes): not
  moved; it now depends on the port table of SEC-DEMO-CORE, and the other
  offered fix (the fixed-port files through the suite gate) is in force from
  wave 1.
- Unfolding the 90-minute folds (execution S3): not done; est_min cannot
  pass 90 and each fold on the web/index.html chain saves a wave; the second
  offered fix was taken on the wave estimate (10 minutes when the longest
  package is a fold of 85 or more).
- A separate ports package before wave 2 (execution S3, floor S3): the table
  is defined by SEC-DEMO-CORE, the first editor of server/al/ports.py,
  instead of a new package.
- Steam scan off at once (floor S1, 'consider'): taken as the default from
  the moment the typed path field is on main, not earlier, so no install is
  left without a way to name its log; until then SEC-NO-DISCOVERY's narrowed
  scan is in force.
- F-006 mapped to a parked package only (coverage S3): left as it is; it is
  the flip gate itself and is listed under 'Mapped but waiting'.
- DEP-09 User-Agent (floor S2): the finding said no User-Agent was required;
  the package's test entry already asked for it, so the rule was made
  explicit rather than added.

Applied later:

- Aligning the text of docs/plan/04, 05 and 06 on Q-23 (coverage S2, floor
  S1; first left out because those sections are final): applied 2026-11-18
  (LE-01). Each of the three files carries dated amendment lines; see
  section Rulings 2026-11-18 (close-out).

Packages whose text the review changed (54): AUTO-11, AUTO-15, AUTO-21,
DATA-GGG-APPLICATION, DATA-PRICE-FALLBACK-RUNBOOK, DEP-05, DEP-09, DEP-18,
GP-01, GP-02, GP-04, GP-05, GP-09, GP-10, GP-12, LOOP-WATCH-SETTLED,
OVL-CARD-SLOT, OVL-CHECK, OVL-KEYS-CORE, PLAY-F-186A-PLAYER-NOTES-STORE,
PLAY-TD-04B-THEME-CHOICE, PLAY-TD-09A-REGION-HOOK, PUB-DEPBOT-ACTIONS,
PUB-DEPBOT-NPM, PUB-DEPBOT-TICK, PUB-GO-DECISION, PUB-HOOK-RELEASE-CHECK,
PUB-LOCAL-ONLY-TEXT, REL-AUTOSTART-TRAY, REL-CUTOVER-LIVE, REL-RUNTIME-PINS,
REL-UPDATE-TRIGGER, RUN-DURABLE-CRLF, RUN-LEFTOVERS-CORE, RUN-METRICS-CORE,
RUN-SEAMS, RUN-VERDICTS-CORE, RUN-VERDICTS-UI, SEC-DEMO-CORE,
SEC-HELLO-CORE, SEC-NO-DISCOVERY, TC-ASC-FROM-TREE, TC-CAMPAIGN-KEEP,
TC-GGG-LISTENER, TC-IMPORT, TC-OAUTH-REG, TC-PRESS-FIXTURES,
TC-PRESS-SAMPLES, TC-WORN-STORE, TC-WORN-WIRE, TEST-HTTP-ROUTES, TEST-MARKS,
TEST-PORT-LEASE, TEST-WEB-SRCPATHS-NODE.

## Rulings 2026-11-18 (close-out)

After the phase 3 checkpoint the loose ends of sections 01 to 09 were
collected (166 items: 132 already resolved, 15 to fix, 19 needing a ruling).
A distinct adjudicator ruled; the rulings that reached the close-out are
recorded here and were applied to docs/plan/packages.json, this file, 08 and
09 and, as dated amendment lines, to 04, 05 and 06 (their Status stays
final). Each entry: decision, alternatives, why, reverses if.

- LE-01 (who creates the repository, makes the first push and flips it
  public (Q-23)).
  - Decision: The operator's go-public order in the 2026-11-18 session brief
    is the recorded go for Q-23 step 1 (create the private repo and push
    main) and step 4 (make it public once the plan-04 gates pass). Agents
    create the repo, push and flip. The only operator act is OA-1, gh auth
    login, and only if `gh auth status` fails. Nothing is pushed in this
    planning session.
  - Alternatives: (a) Q-23 as first ruled: the operator creates or confirms
    the remote and the flip, and the repo stays local until then. (b) Step 1
    only, with the flip waiting for a separate later go. (c) Treat the
    2026-11-17 'item E' citation as enough without a verbatim record.
  - Why: The order is the operator's own instruction for this session. It
    says going public is ordered and that gh auth login is the only act
    left. FLEET rule 1 keeps only physical acts, passwords and OAuth grants
    for the operator, and gh is already signed in with the repo and workflow
    scopes (04 OA-1, checked 2026-11-18).
  - Why, also: Q-23 waited for a 'recorded go'. Its own record format (07
    'Operator go for publishing') is the operator's words quoted verbatim in
    AL-NEXT-SESSION.txt. This session holds those words, so the condition is
    met. A plan sentence citing 'item E' is not the record (alternative c is
    rejected).
  - Why, also: The CLAUDE.md line 'creating the remote is an operator act'
    and the local-only order are lifted by the operator's own order.
    PUB-GO-DECISION lands that lift, together with GP-02 in one integrator
    commit, before GP-09 can run. So no push ever happens while CLAUDE.md
    still says local only, and the 'no push while local only' floor holds.
  - Why, also: The safeguards stay as gates, not operator clicks: identity
    scan 0 and leak sweep 0 (needles armed) before the first push, private
    first, and the flip only on P0 green plus re-run scans. Any hit stops
    everything and files a rewrite request to MAIN (fleet_rewrite.py, ORDER
    only). Private-first is reversible.
  - Why, also: The Game ToS floor is not touched: no game, process, input or
    GGG endpoint is involved, and CI never turns web data on.
  - Reverses if: The main session cannot copy the operator's words verbatim
    from the brief it holds. Then Q-23's default applies: stay local, GP-02
    stays a ready diff, and the publishing packages stay parked.
  - Reverses if, also: The operator withdraws or narrows the order, for
    example 'private only'. Then drop the step 4 line and leave GP-12
    parked.
  - Reverses if, also: A GP-01, GP-09 gate 4/5 or GP-12 gate 2 scan finds an
    identity, AI-trailer, path, account, email, sibling-tree or friend-name
    hit. Then stay local or private and file the rewrite request to MAIN.
  - Reverses if, also: `gh auth status` fails. Then OA-1 is the single
    batched ask.
- LE-05 (findings.json and ruling Q-23 against docs/plan/04).
  - Decision: Same ruling as LE-01. 04 is right in substance: the operator's
    2026-11-18 order, quoted verbatim in the hand-off, is the Q-23 go.
    findings.json and ruling Q-23 are brought up to date to match it.
  - Alternatives: Follow findings.json and Q-23 as first written: the
    operator creates the repo, and the plan stays local.
  - Why: Q-23's own condition was a recorded operator go. The operator's
    order for this session supplies it, and the hand-off line is the record
    Q-23 asked for.
  - Why, also: 'Stay local' remains the written fallback if the verbatim
    record cannot be made.
  - Reverses if: Same as LE-01.
- LE-27 (GP-09 and GP-12 follow 04; the stay-local fallback).
  - Decision: Same ruling as LE-01. GP-09 and GP-12 follow 04. The
    stay-local fallback stays in PUB-GO-DECISION and in GP-09 gate 1 as a
    live safeguard, not as dead text.
  - Alternatives: Remove the fallback text now that the go is recorded.
  - Why: With the go recorded, gate 1 just re-checks the hand-off line and
    decision 0046 at push time. That costs nothing and catches a lost or
    edited record.
  - Why, also: Keeping the fallback keeps the plan reversible if the order
    is withdrawn.
  - Reverses if: Same as LE-01.
- LE-79 (04, 05 and 06 word the Q-23 go their own way).
  - Decision: Same ruling as LE-01. Align 04, 05 and 06 with dated amendment
    lines rather than rewriting the final sections.
  - Alternatives: Leave 04, 05 and 06 unaligned and rely on 07's 'this
    section wins'.
  - Why: Three documents that disagree on who acts is the kind of drift that
    misleads a later agent. Short dated lines fix it and keep the review
    history readable.
  - Why, also: Once the go is recorded, 07's override rule and 04's reading
    lead to the same result.
  - Reverses if: Same as LE-01.
- LE-81 (the go record is not in the hand-off; eight packages parked).
  - Decision: Same ruling as LE-01. The planning session holds the
    operator's brief, so PLAN-LANDING writes the OPERATOR GO step 1 and step
    4 lines and the OA-2 skip line verbatim and unparks the eight publishing
    packages.
  - Alternatives: Leave the packages parked until a later session that holds
    a new operator message.
  - Why: 07 says PLAN-LANDING writes the record 'if the planning session
    holds such a message'. This one does.
  - Why, also: Leaving them parked would add a wait the operator has already
    ruled out.
  - Reverses if: The main session cannot quote the brief verbatim. Then the
    packages stay parked under Q-23's default.
- LE-107 (GP-09 as an agent package in an open wave).
  - Decision: Same ruling as LE-01. GP-09 stays an agent package in its
    scheduled wave. Its unblock is now satisfied by the verbatim hand-off
    record of the operator's 2026-11-18 order, not by the 'item E' citation
    alone.
  - Alternatives: Move GP-09 into 09 as an operator act.
  - Why: The sources disagreed only because the operator's words were not
    recorded. They now are, and the CLAUDE.md lift lands before GP-09
    through its dependencies.
  - Reverses if: Same as LE-01.
- LE-140 (floor lens: agent steps resting on an untracked brief).
  - Decision: Same ruling as LE-01. Agent steps for repo creation, first
    push and flip are allowed. They rest on the operator's own words in the
    tracked hand-off, not on an untracked brief citation.
  - Alternatives: Keep these steps as operator acts under the stricter
    reading.
  - Why: This is not a Game ToS floor question: GitHub publishing touches no
    game process, input, file or GGG endpoint, so 'stricter floor reading
    wins' does not apply.
  - Why, also: The repo floor 'no push while local only' holds because the
    hygiene lift and the guarded hook land before any push.
  - Why, also: The source problem the finding raised (an untracked brief) is
    fixed by the verbatim tracked record.
  - Reverses if: Same as LE-01.
- LE-160 (07 Review record, 'not applied' line on 04, 05 and 06).
  - Decision: Same ruling as LE-01. Align 04, 05 and 06 on Q-23.
  - Alternatives: Leave them unaligned.
  - Why: Same as LE-79.
  - Reverses if: Same as LE-01.
- LE-02 (default repository owner and name (Q-24)).
  - Decision: The default repository address is `<account gh is signed in
    as>/AshLight`, read live at GP-09 with `gh api user --jq .login`. No
    operator input is needed. OA-5 stays an optional override. 'Placeholder'
    means only that config/public_repo.json is absent until GP-10 writes it
    from the real origin remote.
  - Alternatives: (a) Q-24 operator_note: the operator supplies owner and
    name, and GP-09 waits for it. (b) A placeholder constant in tracked
    config before the remote exists.
  - Why: The operator's order leaves gh auth login as the only act.
    Requiring the operator to supply the address would add a second act for
    a value the signed-in account already gives.
  - Why, also: The name AshLight is settled (decision 0001), and the account
    is the operator's own by definition of the gh sign-in.
  - Why, also: No tracked placeholder string means nothing to forget and no
    fake address leaking into README or the update check. Features that need
    the address stay off until GP-10, as Q-24 intended ('not live until the
    address exists').
  - Why, also: It is reversible: GitHub repos can be renamed or transferred,
    and GP-10 reads the value from origin, so it follows.
  - Reverses if: The operator names another owner or name before GP-09
    (OA-5).
  - Reverses if, also: `gh repo view <login>/AshLight` shows an existing
    repo. Then GP-09 stops and reports; it never reuses or overwrites one.
  - Reverses if, also: Leak-sweep testing shows the allow entry masks other
    ids.
- LE-28 (the floating CI job test-newest beside the exact-pin rule).
  - Decision: Keep test-newest with floating Python 3.14 and Node 24 as a
    non-required job with continue-on-error, and fence it with tests.
  - Alternatives: (a) Pin it to exact patch versions (3.14.x, 24.x.y). (b)
    Drop the job.
  - Why: The exact-pin rule in CLAUDE.md covers dependencies (Electron
    45.3.3, exact npm deps, npm ci from the lockfile). test-newest still
    installs from the hash-pinned requirements-dev.txt and the lockfile, and
    its action SHAs are pinned. Only the runner's interpreter floats.
  - Why, also: The job's purpose (0046 R3: run the floor and the newest
    branch) is early warning on new runtimes. Exact pins would defeat that
    and need manual bumps.
  - Why, also: It is not a required check and failures do not block merges,
    so it cannot gate a release. Shipped artifacts use the builder's exact
    Python (05 step 5).
  - Why, also: It is reversible and cheap. The only cost is metered Windows
    minutes during the short private phase.
  - Reverses if: test-newest produces noise that hides real failures.
  - Reverses if, also: Private-phase Actions minutes become a real cost.
    Then restrict it to `push` on main or a schedule.
  - Reverses if, also: MAIN's kit or the operator rules every CI runtime
    must be exact.
- LE-38 (the release polling gate against ruling Q-05; OA-2).
  - Decision: Keep the stricter gate: release builds make no poe.ninja
    request (ninja.RELEASE_POLLING off, trade link only) until poe.ninja's
    written yes, an approved mirror or the operator's written ruling. The
    poe.ninja message (OA-2) stops being a flip gate: the operator's
    2026-11-18 order is recorded as its written skip, which Q-05 itself
    allows.
  - Alternatives: (a) Q-05 as written: ship the tiered cadence in release
    builds regardless. (b) Keep OA-2 as an operator act that gates the
    public flip.
  - Why: poe.ninja asks apps to proxy through their own backend. A public
    release multiplies per-install requests, and silence is not consent. The
    stricter reading wins (F-046 and the floor audit). The cost to players
    is small: the price card shows the trade link only.
  - Why, also: Q-05's core intent, not getting the price feature cut off by
    a later objection, is better served by not polling from releases than by
    polling while waiting for an answer.
  - Why, also: The operator said gh auth login is the only act left. That
    reads as the written skip Q-05 and 04 already allow, so the flip waits
    for nobody. The release gate removes the risk the message was meant to
    cover.
  - Why, also: It is reversible with one constant flip
    (DATA-NINJA-RELEASE-ON).
  - Reverses if: poe.ninja replies yes: flip the constant through
    DATA-NINJA-RELEASE-ON.
  - Reverses if, also: poe.ninja asks for a mirror or less polling: new
    decision.
  - Reverses if, also: The operator says they want to send the message
    before the flip: OA-2 becomes a gate again.
  - Reverses if, also: Source-checkout polling draws an objection: gate it
    the same way.
- LE-39 (one agent read of poe.ninja's public economy pages
  (DATA-GUIDE-ONE-BLOCK)).
  - Decision: Allowed: the DATA-GUIDE-ONE-BLOCK package agent makes one
    dated read pass of poe.ninja's public, human-facing economy pages to
    record their URL forms. It runs under strict conditions. The fallback is
    a link to the landing page only.
  - Alternatives: (a) Landing-page link only, with no agent web read. (b)
    Derive or guess the URL slugs without reading.
  - Why: The floor governs what AshLight (the app) reads. The app here
    requests nothing and only builds a link the player opens. poe.ninja is
    on the floor's permitted list, and research notes already cite dated web
    reads (CLAUDE.md: every research claim cites a source with an access
    date).
  - Why, also: Guessing slugs (alternative b) is worse than reading. A wrong
    link misleads the player, and the package already bans derived or
    guessed slugs.
  - Why, also: The conditions meet even the strictest reading of the floor's
    web rules: truthful AshLight UA, human pages only, no API or data route,
    bounded and one-off. They are written into the package notes: robots.txt
    first and obeyed, at most one GET per category page form, 30 GETs in
    all, 1 s apart, no page body in a tracked file.
  - Why, also: It is reversible: the table is data in ninjalink.py, and an
    empty table falls back to the landing page.
  - Reverses if: poe.ninja's robots.txt or terms disallow automated reads of
    those pages.
  - Reverses if, also: poe.ninja objects.
  - Reverses if, also: The operator rules that agents may not make web reads
    for research.
  - Reverses if, also: In any of these cases: landing-page link only.
- LE-53 (the build refusal 'a final version without a tag' (DEP-08, plan
  05)).
  - Decision: Accept DEP-08's change: the 'final version without a tag'
    refusal applies to `build --tag` only, and `--ref` builds the staged
    final version before the tag exists. Condition: BUILD and every other
    artifact carry no tag field, so `--ref` and `--tag` builds of one commit
    are byte-identical.
  - Alternatives: (a) Plan 05 as worded: refuse every untagged final build,
    with stage adding a pre-tag flag. (b) Tag first, then stage.
  - Why: 05's own procedure stages the final version before tagging, and the
    tag message binds the staged SHA256SUMS (`sums-sha256`). An untagged
    final build is therefore required, and the old refusal contradicts the
    procedure.
  - Why, also: The refusal's purpose still holds: no untagged final release
    can be published. REL-PUBLISH-GATES tags only the stage commit with a
    PASS report, the guarded pre-push refuses a v* tag without one, and CI
    rebuilds with `--tag` and fails on any hash difference.
  - Why, also: Load-bearing defect found: DEP-08's test said '--ref ...
    BUILD records tag: none'. Release CI (05 step 5) compares the hash of
    its `--tag` build's SHA256SUMS with the staged one. If BUILD differed by
    a tag field, every release would fail CI. So the tag must not be inside
    any artifact.
  - Why, also: Tagging first (alternative b) would push a tag before the
    PASS report exists.
  - Reverses if: The operator wants final versions buildable only from a
    tag. Then stage uses a pre-tag flag and BUILD stays tag-free.
  - Reverses if, also: CI's byte comparison is dropped.

Not applied at this close-out. All 19 items were ruled. Six rulings were not
applied here, because their text was cut off on the way to the fixer: LE-69,
LE-76, LE-92, LE-96, LE-99 and LE-100. They are recorded and applied in
section Rulings 2026-11-18 (close-out 2).

Loose ends fixed without a ruling (15 items):

- LE-20: RUN-BUDGET-TESTS-DET's accept is the pytest command alone; the
  'fails once with its defect put back' rule moved to its notes.
- LE-32, LE-132, LE-148: the stale port ranges in SEC-DEMO-CORE, DEP-05,
  TEST-PORT-LEASE, DEP-01, REL-INSTALL-SELFTEST and REL-STAGE-ROUNDTRIP now
  read as the one table of section Port block (leases 8962 to 8969, demo and
  self-test 8970 to 8975).
- LE-35: the coverage of F-082 also names RUN-LEDGER-CORE and
  RUN-LIVE1-FIXTURES (its Client.txt half).
- LE-54, LE-165: 08's builder commit subject carries a type (`<type>(<ID>):
  <subject>`), which REL-SUBJECT-CHECK enforces from wave 8.
- LE-80, LE-163: PLAN-LANDING lists 08 and 09 under files (both are tracked)
  and keeps only tests/test_plan_operator_acts.py as new.
- LE-91: AUTO-26's default reads as 08 section 2 and decision 0012: a
  hand-run sidecar worktree, with .claude/worktrees only as the fallback.
- LE-93, LE-101: PLAN-LANDING's hand-off edit and accept name the `WAVE
  POINTER: wave 0 done, next wave 1` line and the `DEFERRED:` form of 08,
  and replace the stale 'Next action: operator-led planning session' line.
- LE-150: REL-RUNTIME-PINS and DEP-01 name the embeddable CPython by the
  exact version and sha256 of its pin, not as 3.14.x.
- LE-164: DEP-01 writes its spike record to the new file
  docs/ops/runtime-spike-record.md and no longer edits docs/plan/05.
- LE-166: the planning builder is retired and docs/plan/packages.json is the
  source of truth (section How to read this plan).

What the close-out moved:

- Eight packages left wave 99: PUB-GO-DECISION, GP-02 and
  PUB-LOCAL-ONLY-TEXT to wave 4, GP-09 to wave 5, PUB-DEPBOT-ACTIONS and
  PUB-DEPBOT-TICK to wave 18, PUB-DEPBOT-NPM to wave 19,
  PUB-HOOK-RELEASE-CHECK to wave 22. No other package changed its wave; 41
  packages stay parked.
- Waves 4, 18, 19 and 22 run a fourth merge batch (14, 14, 13 and 13
  worktree packages). In wave 4 the go-public batch is the first one. GP-09
  runs alone after the last batch of wave 5, and its 50 minutes count in
  full.
- Expected time: wave 4 from 129 to 139 minutes, wave 5 from 129 to 179,
  wave 18 from 125 to 133, wave 19 from 135 to 143, wave 22 from 135 to 143;
  session 2 from 6 h 27 min to 7 h 27 min, session 6 from 8 h 15 min to 8 h
  31 min, session 7 from 7 h 30 min to 7 h 38 min. No session passes the
  520-minute budget and the count of sessions stays 10.
- Session 2 delivers the milestone 'the private repository exists and the
  first push is green' again.
- Operator acts: OA-10 is recorded and OA-2 is skipped in writing, so
  neither is asked any more; GP-02, PUB-GO-DECISION and GP-12 name no
  operator act; OA-1 (conditional), OA-5 and OA-11 (optional) are kept.

## Rulings 2026-11-18 (close-out 2)

The close-out audit of 2026-11-18 (HEAD 3e14f77) found that the adjudicator of
the close-out had ruled all 19 loose ends, that 13 rulings were applied
(section Rulings 2026-11-18 (close-out)) and that six were never applied,
because their text was cut off on the way to the fixer. The full text of the
six was read again from the adjudicator's own result and is applied here:
LE-69, LE-76, LE-92, LE-99, LE-100 and LE-96. They are followed by six new
rulings of a distinct adjudicator on gaps the same audit found (R1 to R6).
Each entry: decision, alternatives, why, reverses if, and where it was
applied. Decision 0078 ledgers all twelve.

One fact changed the form of LE-92: its probe was run early, on 2026-11-18 in
the planning session, and it passed. Wave 1 therefore uses hand-made sidecar
worktrees (docs/plan/08 section 2), and the .claude/worktrees fallback stays
unused.

- LE-69 (the stale OVL-FPS acceptance sentence in decision 0002).
  - Decision: Decision 0002 gets one dated, append-only pointer under its Game
    FPS line saying the OVL-FPS acceptance is restated as budget B19 in
    decision 0006. The old sentence stays as written, and no budget changes.
  - Alternatives: (a) Leave 0002 stale, as Q-18's 'no change to 0002'
    literally says. (b) Rewrite 0002's FPS sentence.
  - Why: Q-18's 'no change to 0002' protects 0002's contract: the stack and
    the budgets. A cross-reference changes neither. Leaving a known-stale
    acceptance line misleads the next reader, and the CLAUDE.md 'Reverses if'
    of decision 0002 cites the FPS budget.
  - Why, also: The plan already amends 0002 with a dated clarification (Q-16,
    dev-only test plugins), so a dated note there is the established form.
  - Why, also: Append-only keeps history intact and is reversible.
  - Reverses if: The operator rules decision records must not carry forward
    pointers.
  - Reverses if, also: The B19 result shows a real FPS budget change, which
    needs a real 0002 amendment instead.
  - Applied 2026-11-18: package OVL-FPS (parked on OA-33) lists
    docs/decisions/0002-stack.md under files, its notes carry the line word
    for word and its accept greps it. The line is written when the package
    lands, not now: budget B19 enters decision 0006 only with OVL-CHECK (wave
    21). Section Parked packages lists the file as shared by
    RUN-OVL-BUDGET-CLOSE and OVL-FPS.
- LE-76 (the CI fetch of AUTO-19 beside decision 0013).
  - Decision: Accept AUTO-19 as designed. tools/watch_ci.py does not read
    web_data, runs only when GITHUB_ACTIONS is 'true', fetches only URLs that
    pass watch_gate.check_url, and never touches a GGG or poe.ninja host.
    Decision 0076 records the scope boundary with decision 0013.
  - Alternatives: (a) Give CI its own web_data switch, for example a
    repository variable. (b) Drop the CI watcher and keep all sources on the
    dev loop.
  - Why: Decision 0013 governs the app and the dev host: one web_data opt-in,
    default off, nothing on the network while off. A GitHub runner is project
    infrastructure, not a player's install or the operator's machine, so there
    is no user whose opt-in is missing.
  - Why, also: The guard that matters is kept and tested: it refuses to run
    off a GitHub runner, so it can never bypass web_data on a real machine.
    The URL allow-list and a test that no GGG or poe.ninja host appears in the
    workflow match 04 ('CI never turns web data on and calls no GGG or
    poe.ninja host').
  - Why, also: A repository variable (alternative a) would be an opt-in with
    no user behind it. Dropping the watcher (alternative b) loses unattended
    watching while the dev host is off, against the minimal-interaction order.
  - Reverses if: A CI source needs a GGG or poe.ninja host.
  - Reverses if, also: The operator rules decision 0013 covers CI.
  - Reverses if, also: The GITHUB_ACTIONS guard proves spoofable in a way that
    lets it run on a user machine.
  - Applied 2026-11-18: decision 0076 is reserved for AUTO-19 and does not
    exist yet, so the ruling's 'Scope' sentence stands word for word in the
    notes of AUTO-19 and its accept greps it in the decision file; the Settled
    bullet text in its integrator_edits carries 'never a GGG or poe.ninja
    host; outside decision 0013's scope'; docs/plan/06 (AUTO-19) has a dated
    amendment line. Tests unchanged.
- LE-92 (sidecar worktrees before the hook of decision 0012 is wired (OA-12)).
  - Decision: Do not wait. At the start of session 1, before wave 1, run one
    probe: create a hand-made sidecar worktree with the hook script, have a
    background sub-agent edit and revert a scratch file in it, then remove it
    with the hook's WorktreeRemove. If the edit is allowed, use 08's unwired
    method. If it is refused, use the harness default .claude/worktrees as a
    temporary, recorded fallback until OA-12 is pasted.
  - Alternatives: (a) Waves wait for the operator's OA-12 paste. (b) Run every
    package with isolation none in the main checkout, serialised. (c) Use the
    unwired method untested.
  - Why: Waiting (alternative a) stalls 11 or more wave-1 agents on an
    optional physical act the operator may not do soon, against FLEET rule 1
    and the minimal-interaction order. Serialising in main (alternative b)
    costs hours and raises claim and race risk.
  - Why, also: .claude/worktrees is gitignored, local and leak-free, and it is
    what isolated spawns already used before the hook (08 'What earlier
    sessions did'; decision 0012 Alternatives). It breaks only the sidecar
    placement rule, and only until the paste. It touches no ToS floor and no
    security floor.
  - Why, also: A one-agent probe costs about a minute and removes the
    uncertainty in LE-99. Running untested (alternative c) risks failing 11
    builders at once.
  - Why, also: It is reversible: once OA-12 is pasted the harness places
    worktrees under the sidecar, and /done reaps the fallback ones.
  - Reverses if: The probe shows edits under the sidecar path work: the
    unwired method is used and the fallback is never invoked.
  - Reverses if, also: The operator pastes OA-12: the wired method is used.
  - Reverses if, also: The operator rules the sidecar rule absolute even
    temporarily: then alternative b (serial, isolation none).
  - Applied 2026-11-18: the probe ran early, on 2026-11-18 in the planning
    session, by one sub-agent with the ruling's method (08 section 2,
    'Probe'). The edit was allowed, so the first Reverses-if is met: wave 1
    uses the unwired sidecar method and the fallback is not taken. 08 (the
    probe record, the Fallback bullet, Open points), 09 OA-12, the
    operator_act of AUTO-26 and the hand-off say so.
- LE-99 (edits under a hand-made sidecar worktree were unverified).
  - Decision: Same ruling as LE-92. A one-agent probe at the start of session
    1 settles whether edits are allowed under a hand-made sidecar worktree.
    Creating and removing that one probe worktree is allowed.
  - Alternatives: Leave it unverified and find out when wave 1's builders run.
  - Why: The verifier avoided creating a worktree because it was read-only.
    Session 1 is not, and a probe worktree is created and removed through the
    same hook code the tests already run end to end.
  - Why, also: Nothing irreplaceable is deleted: `git worktree remove` without
    --force refuses a dirty tree.
  - Reverses if: Same as LE-92.
  - Applied 2026-11-18: the probe of 2026-11-18 (see LE-92): Edit and Write
    under the sidecar worktree were allowed with no prompt; the hook's
    WorktreeRemove refused the dirty tree and removed it once it was clean,
    without --force.
- LE-100 (the .claude/worktrees fallback beside decision 0012).
  - Decision: Same ruling as LE-92. The .claude/worktrees fallback is allowed
    as a temporary, recorded deviation from decision 0012's placement. The
    real fix stays OA-12 / AUTO-26.
  - Alternatives: Forbid the fallback and serialise in the main checkout.
  - Why: It is gitignored, leak-free, matches the pre-hook status quo, ends on
    the paste, and is reaped at /done. Serialising costs hours.
  - Reverses if: Same as LE-92.
  - Applied 2026-11-18: 08's Fallback bullet says it is taken without waiting
    and reaped at /done; the hand-off NOTE line stays as 08 states it, and
    OA-12 moves to the top of the one batched ask only when the fallback is
    actually used. It was not needed on 2026-11-18.
- LE-96 (the kill at 3x inside a Workflow run).
  - Decision: Accepted as the Workflow-run equivalent of FLEET item 3's 3x
    kill: the builder stops itself at 2 x est_min, and a run that is still
    silent at 3x is stopped as a whole and restarted with that package id in
    args.defer. Waves where a single-agent kill matters run as plain
    background Agents. If the Monitor tool is not available, the watcher waits
    with a bounded background Bash until-loop.
  - Alternatives: (a) Never use Workflow runs for waves; dispatch plain
    background Agents, which can be stopped one by one. (b) Use Workflow runs
    with no kill at all.
  - Why: FLEET item 3 is meant to ensure no task runs unchecked past 3x its
    ETA. A self-stop at 2x is stricter, and the whole-run stop at 3x enforces
    the limit when a builder hangs. Restarting loses little, because worktrees
    are reused by name (the hook returns the same path), progress files
    persist, and the deferred id is skipped.
  - Why, also: Not using Workflow runs at all (alternative a) gives up their
    batching. Using them with no kill (alternative b) breaks item 3.
  - Why, also: The Monitor tool's schema was not checked. A background Bash
    bounded loop that exits on a changed or stale progress file, re-invoking
    the watcher on exit, is the item-12 'poll in bounded slices' pattern and
    does not depend on that tool. Foreground sleep stays banned.
  - Reverses if: The Workflow API gains a per-agent stop: then the normal 3x
    kill of one agent is used.
  - Reverses if, also: Whole-run restarts lose work in practice, for example
    uncommitted builder state: then waves switch to plain Agents.
  - Reverses if, also: MAIN's kit rules a different Workflow kill rule.
  - Applied 2026-11-18: 08 section 3 (the Kill bullet and the watcher bullet)
    and section 10 (the line on waves that run as plain background Agents).
- R1 (GP-09 runs alone).
  - Decision: GP-09 runs ALONE. It starts only after wave 5's last merge batch
    has moved main. From its gate 3 to its read-back nothing touches main: no
    merge, integrator commit, batch suite, revert or other act. Wave 5 closes
    only after that read-back, or after GP-09's DEFERRED line if a gate is
    red. It does not ride in a merge batch. This is expressed in the gate text
    and the notes, not through serial_group or deps.
  - Alternatives: (a) GP-09 inside a normal merge batch; (b) alone, which is
    chosen; (c) a serial_group or a synthetic dep.
  - Why: Gates 3 to 11 (clean tree, identity, leak, brand, hooks, GP-04
    commit, CI test, whole suite) all read the state of main. A merge landing
    between those gates and the push would send a commit that was never
    scanned or suite-tested, a check-then-push race.
  - Why, also: The plan already said this in the wave 5 gate, 08 section 2 and
    the notes of GP-09 in packages.json; it was never ruled. This ruling makes
    it binding and adds the close and carry rules.
  - Why, also: serial_group is the validator's tool for keeping two file
    editors apart inside a wave. GP-09 edits no file, so a group would mean
    nothing there. The 08 Workflow already treats an act that the gate text
    places 'alone' as one that waits for the last batch.
  - Why, also: Fully reversible: it is text only, and it costs nothing extra
    because the 50 minutes are already counted in wave 5.
  - Reverses if: The merge lock (LOOP-WAVE-HOLD) is proven to cover the whole
    GP-09 gate-to-push span on its own.
  - Reverses if, also: GP-09 is split so that the push is a single atomic step
    that re-runs every gate on the exact commit it pushes.
  - Reverses if, also: The operator orders otherwise.
  - Applied 2026-11-18: the wave 5 gate (packages.json and this file), the
    notes of GP-09 (a red gate defers it to the end of the next wave; after
    AUTO-21 it runs under python tools/loop_merge.py hold), 08 section 2 and
    08 Open points.
- R2 (the loop_push switch that PUB-LOCAL-ONLY-TEXT never built).
  - Decision: ROADMAP row PUB-LOCAL-ONLY-TEXT is reopened. Its remaining work
    is the loop_push switch and the two tests packages.json already names. It
    stays in wave 4, batch 1, with the same files and est_min. GP-09 keeps it
    as a dep, so no origin remote can exist before the switch does.
    CLAUDE.md's push-worker sentence gets the switch condition when the
    package lands.
  - Alternatives: (a) reopen, which is chosen; (b) keep the row ticked and
    move the switch into a 'push worker package'; (c) drop the switch and let
    the loop push by itself as soon as origin exists.
  - Why: Fact checked: push_needed() and push() in tools/al_loop.py have no
    loop_push gate. The two tests named in the tests field
    (test_push_is_skipped_while_the_loop_push_switch_is_off,
    test_push_runs_with_a_fake_origin_and_the_switch_on) do not exist in
    tests/test_al_loop_gate_cache.py. The accept line passed only because it
    runs whole files. So the tick was a false record.
  - Why, also: Option (b) has no target: the push worker already exists, and
    no planned package builds it. PUB-LOCAL-ONLY-TEXT already owns the
    al_loop.py and gate-cache test files in wave 4, where nothing else edits
    them.
  - Why, also: Option (c) undoes the floor-lens review (Review record, 'Loop
    push (floor S2)') and the Q-23 assignment of push approval. Default off
    fails closed. It also adds no operator interaction, because a session
    pushes after its own gated commit.
  - Why, also: Ordering safety holds: GP-09 (wave 5) depends on this package,
    and HALT stays until AUTO-21 (wave 6). So the unswitched worker can never
    see an origin remote.
  - Reverses if: The operator rules that the headless loop may push by itself
    (then drop the switch, and CLAUDE.md keeps its present sentence).
  - Reverses if, also: A later package moves the push worker out of
    tools/al_loop.py (then the switch moves with it).
  - Applied 2026-11-18: PUB-LOCAL-ONLY-TEXT in packages.json (accept,
    integrator_edits, notes), its ROADMAP row (reopened, with a REOPENED
    sentence), the wave 4 Integrator bullet, the Review record bullet 'Loop
    push (floor S2)', 09 OA-11 and the hand-off. tools/al_loop.py is
    untouched: the switch is the package's work in wave 4.
- R3 (the kit fleet_identity pre-push gap and its report to MAIN).
  - Decision: The fleet_identity pre-push gap is folded into the existing kit
    report: row AUTO-25 drafts it in wave 2, and LOOP-KIT-REPORT-SEND sends it
    once OA-21 gives a destination. It is carried in the hand-off KIT DEFECT
    bullet. Decision 0046 is corrected to say 'not yet reported'. No note is
    sent now.
  - Alternatives: (a) send one combined FIX note now; (b) fold the gap into
    AUTO-25 / LOOP-KIT-REPORT-SEND, which is chosen; (c) hand-off carry only.
  - Why: Option (a) cannot be carried out. The outbox holds only its
    placeholder file; nothing has ever been sent. The inbox holds one MAIN
    INFORMATION / TERMINAL note. No loop.dest_inboxes entry or fleet roster
    exists for AL (hand-off KIT DEFECT bullet; OA-21 is open). FLEET item 7
    defines delivery as destination copies that are re-hashed and counted, so
    with no destination there is no delivery to record.
  - Why, also: FLEET item 11 requires the defect to be reported to MAIN and
    never patched locally. The plan already has one report path for the older
    fleet_suite_gate defect (AUTO-25 drafts, LOOP-KIT-REPORT-SEND delivers on
    OA-21). Folding both into that one note also follows item 14 c ('several
    answers go in ONE note').
  - Why, also: Decision 0046 said 'reported to MAIN', which was false. The
    record has to state the truth: drafted later, sent on OA-21.
  - Why, also: The local cover already exists: tools/push_guard.py checks
    taggers, tag objects and the wide trailer rule. Waiting on the kit leaves
    no exposure.
  - Reverses if: A delivery path to MAIN exists (an OA-21 entry or a fleet
    roster), which makes option (a) the right move at the next session.
  - Reverses if, also: MAIN ships a kit version whose fleet_identity checks
    tag objects and wide trailers (then drop item 5 from the draft and amend
    0046 to 'fixed in kit vN').
  - Reverses if, also: MAIN asks for kit defects by another channel.
  - Applied 2026-11-18: AUTO-25 (goal, notes item 5, accept) and
    LOOP-KIT-REPORT-SEND (notes) in packages.json, the Kit gaps clause of
    decision 0046 (amended in place as this ruling words it: 'NOT yet
    reported to MAIN, because ...'; words were added only, and a dated
    correction under the clause quotes its first wording), and the hand-off
    KIT DEFECT bullet. Nothing was sent; no remote and no dest_inboxes value
    was added.
- R4 (three server-side limits of the go-public setup).
  - Decision: (a) The admin always-bypass on main's required checks is
    ACCEPTED as designed. (b) Branch and tag creation on the remote is
    ACCEPTED as designed, plus a read-back clause added to GP-13 so that drift
    is caught. (c) The CI leak sweep running --tree only is ACCEPTED as
    designed. All three acceptances go in a new dated amendment of decision
    0046.
  - Alternatives: Assign each gap to a package as a hard server rule; for (b),
    a no-bypass 'restrict creations' ruleset on every ref except main,
    dependabot/** and v*.
  - Why: (a) Pushes go straight to main, so required checks can only run after
    the push. A no-bypass rule would reject every fresh direct push. Decision
    0046 already rejected 'required checks with no bypass', and its Settled
    entry depends on it. The same gates run before the push anyway: the whole
    suite before every commit, and the pre-push identity check, push_guard and
    object leak sweep on every push. GP-12 gate 3 also reads both workflows
    green before the flip.
  - Why, also: (b) The repository stays private until GP-12, and only the
    operator's account plus Dependabot write to it. The local ref rule plus
    push_guard refuse every ref except main and v*. The release-tag ruleset
    (deletion, non_fast_forward, update; no bypass) already protects v* tags.
    A creation-restricting ruleset would add a new tracked file and an
    amendment to plan 04, and it could break Dependabot's dependabot/*
    branches. A read-back catches the same drift with no risk.
  - Why, also: (c) CI holds no private needles, so --history in CI would add
    only the structural arm over history. GP-09 gate 5 already sweeps the
    history locally, armed, and every later push is swept object by object
    with the needles. CI's tree sweep is a second structural check, not the
    authority.
  - Why, also: Every acceptance is text and can be undone with a ruleset or a
    workflow line later.
  - Reverses if: GitHub lets required checks run before a direct push lands
    (then drop the bypass).
  - Reverses if, also: A second writer (collaborator, app or token) gets push
    access, or a ref outside main, dependabot/* and v* ever appears on the
    remote (then add the creation-restricting ruleset in PUB-SETTINGS-FILES
    and GP-13).
  - Reverses if, also: CI ever receives needles through a secret-free channel,
    or a leak is found in pushed history (then CI also runs --history).
  - Applied 2026-11-18: decision 0046, 'Amendment 2026-11-18 - accepted
    server-side limits (ruling R4)', and GP-13 in packages.json (the ls-remote
    read-back in its accept; its notes say what happens to another ref).
    docs/plan/04 is unchanged.
- R5 (three limits of the leak sweep).
  - Decision: All three leak sweep limits are ACCEPTED and recorded in
    decision 0046: archives and base64 are not decoded; --no-verify skips the
    hooks; binary files get no structural arm. Each gets a named backstop. No
    package is assigned.
  - Alternatives: Assign an archive and base64 decoder, a server-side sweep,
    or a binary structural arm to a package.
  - Why: Archives and base64: checked 2026-11-18, none of the 575 tracked
    files is an archive. The only binaries are 14 png / ico brand and app
    assets, and tests/test_brand_assets.py caps the blob size. Release zips
    never go through git: plan 05 sweeps the staged tree before packing (its
    stage gate step 5). A decoder would cost CPU on every push to guard
    against a file type the repository does not hold.
  - Why, also: --no-verify: only the operator can use it. Every agent rule
    (CLAUDE.md Gates, the rules of 08) forbids it. GP-12 gate 2 re-runs
    leak_sweep --history on origin/main before the repository turns public, so
    a bypassed push is still caught while the repository is private.
  - Why, also: Binary structural arm: left out on purpose (0046 amendment item
    1). Three history images form drive-path shapes by chance. The needle arm
    still reads binaries as UTF-8 and UTF-16, which covers the names that
    matter.
  - Why, also: Recording the limits in the decision (not only in a docstring)
    makes the claim 'a clean run is not proof' auditable.
  - Reverses if: An archive, a packed or base64 blob, or a new binary type
    becomes tracked (then add a decoder or a no-archive test through a
    package).
  - Reverses if, also: A --no-verify push is found on origin.
  - Reverses if, also: A needle is ever found inside a binary or encoded
    object.
  - Applied 2026-11-18: decision 0046, 'Amendment 2026-11-18 - accepted leak
    sweep limits (ruling R5)', and one pointer line in the docstring of
    tools/leak_sweep.py.
- R6 (waves 4, 18, 19 and 22 are wider than 12).
  - Decision: Waves 4, 18, 19 and 22 are ACCEPTED as they stand. The rule:
    merge batches hold at most 4 packages, every batch (the fourth included)
    runs its own whole suite before main moves, and a wave holds at most 16
    worktree packages (4 batches). A new or re-planned wave is still filled to
    12 at most. Above 12 is allowed only where a close-out adds packages
    without moving others. No re-sequence.
  - Alternatives: Re-sequence the 7 extra packages into later waves; lower K
    to 5 to fit 3 batches; accept with a fourth batch, which is chosen.
  - Why: Correctness comes from the batch suite, not the width. Every batch of
    up to 4 gets its own whole suite, so escape exposure per batch is
    unchanged (research 0049 R1 ruled K = 4 as Q-17).
  - Why, also: Wave 3 already runs a fourth batch (GP-04), so the merger and
    the 08 Workflow (one entry per Batches line) handle 4 batches today. 08
    section 2 already lists the four wide waves, and the Workflow caps
    parallel agents at min(16, CPUs - 2), which is 14 on this 16-CPU machine.
  - Why, also: Re-sequencing would move packages past the file-chain order the
    Hotspot schedule settled, for about 8 to 10 minutes saved per wave. The
    extra time is already in the wave and session estimates, and no session
    passes the 520-minute budget.
  - Why, also: Text only and reversible. The escape-rate fallback still
    applies: if K drops to 3, these waves run 5 batches, each with its own
    suite.
  - Reverses if: Wave 1 measures an escape rate above 10 percent and a wide
    wave's extra batch pushes its session over 520 minutes (then move that
    wave's last batch into the next wave).
  - Reverses if, also: The suite gate shows a wide wave holding a slot long
    enough to starve the loop (a stale or OVERRUN gate row).
  - Reverses if, also: A machine with fewer than 14 usable CPUs queues
    builders past the wave estimate.
  - Applied 2026-11-18: section Wave width and expected time, 08 section 2 and
    08 Open points. No package changed its wave.

Also closed at this close-out, without a ruling:

- RUN-LIVE-CLICKS-STRIKE: its accept counted two words in ROADMAP.md, and its
  own row held them (in the title and in the pattern text), so the count could
  never be 0. The title and the pattern were reworded; the accept still counts
  both words in the same two files.
- docs/plan/09: the lines that still said the pre-push hook refuses every push
  now name the guarded push of decision 0046 (commits 7fe4993 and 01c2216);
  the same stale words left the blocked text of the parked packages AUTO-19
  and LOOP-CI-ISSUES.
- Section Reserved decision numbers names 0077 and 0078 as taken and 0079 as
  the next free number; docs/decisions/README.md agrees.
- Decision 0078 was checked against its sources (the rulings and the floor
  audit in docs/plan/findings.json, the adjudicator's result of the
  close-out): the six rulings above were missing and are added; where an
  earlier source reads differently (Q-01, Q-02, Q-05, Q-07, Q-23) the entry
  now names the source that wins; A-01 to A-03 name their source.
- The operator record lines of the hand-off were compared with the brief
  (section Operator go for publishing, bullet Checked 2026-11-18).

## Open points

- The escape rate of package subsets is assumed, not measured; wave 1
  measures it and the width rule above says what follows.
- Session lengths are a forecast from the packages' own estimates;
  docs/plan/08-orchestration.md defines how a session runs a wave and
  resumes.
- The operator acts named by packages (operator_act) and the operator
  decisions are collected in docs/plan/09-operator-acts.md; none of them
  blocks an open wave.
- The three hand-off lines of section Operator go for publishing are written
  by PLAN-LANDING, not by this close-out (only the main session holds the
  operator's brief). Until they are read back the eight publishing packages
  are scheduled on the plan's word, and the fallback of that section sends
  them back to wave 99.
- Closed 2026-11-18 (section Rulings 2026-11-18 (close-out 2)): LE-69, LE-76,
  LE-92 with LE-99 and LE-100, and LE-96 had been ruled at the close-out; only
  their application was missing, and it is done. The worktree probe of LE-92
  ran on 2026-11-18 and passed.
- Closed 2026-11-18 (section Rulings 2026-11-18 (close-out 2)): GP-09 alone
  (R1), PUB-LOCAL-ONLY-TEXT reopened for loop_push (R2), the kit gap report
  path (R3), server-side and leak sweep limits (R4, R5), the wide waves (R6).
- Still open after the close-out 2: the two kit defects and the claims-hook
  path fault seen by the probe are not reported to MAIN (no outbound note
  path; AUTO-25 drafts, LOOP-KIT-REPORT-SEND sends on OA-21); the loop_push
  switch is not built (PUB-LOCAL-ONLY-TEXT, wave 4); decision 0002 gets its
  B19 pointer only when OVL-FPS lands.

## Verification follow-up (2026-11-18)

Two claims about this plan were checked again by independent verifiers
after the landing; what was found and what was changed:

- "Inside every wave no two packages share a file": true for waves 0 to 37
  (0 shared files, new files or serial groups; server/al/state.py,
  web/app.js, server/al/core.py, server/al/http.py, web/index.html and
  web/app.css have one editor a wave), not true for the parked wave 99,
  which the validator exempts on purpose (10 shared files, 6 shared serial
  groups). Changed: the Wave and Wave 99 bullets of 'How to read this plan'
  now say so in the rule itself, section Parked packages lists every shared
  file and group with what a joint release must do, and
  tests/test_plan_check.py recounts the rule without the validator
  (test_real_plan_open_waves_share_no_path_or_group; it also fails when the
  list in Parked packages and packages.json disagree). No package moved;
  the validator is unchanged.
- "Every wave has its gate, and wave 0 is done": every wave 0 to 37 has a
  Gate line, but the wave 0 gate named tests/test_plan_operator_acts.py,
  which was not written, so the gate could not run and row PLAN-LANDING was
  open while the hand-off pointer read 'wave 0 done' beside a DEFERRED
  line. Changed: the test file is written as PLAN-LANDING's tests field
  words it (it found no gap in docs/plan/09, which is unchanged); the whole
  accept line of PLAN-LANDING was read back (the five test files green,
  plan_check ok, both files tracked, the 08 grep 3, 396 of 396 row ids in
  ROADMAP.md exactly once, pointer line 1, stale Next-action line 0,
  operator record lines 3); the row is flipped and the hand-off's DEFERRED
  line is dropped. The open-row command of docs/plan/08 section 1 step 4
  prints 'none open' for wave 0 and the 15 ids of wave 1. The Open point
  above on the three hand-off lines is thereby closed: they are in the
  hand-off and read back.

After the close-out 2 the verifiers checked its claims again. Four did not
hold as worded; what was found and what was changed (2026-11-18):

- Decision 0046 still read 'reported to MAIN' in its Kit gaps clause, with
  the dated correction only under it. Ruling R3 words a replacement for that
  clause; its first application had kept the old clause.
  - Decision: the clause is amended in place, exactly as ruling R3 words it.
  - Alternatives: (a) keep the old clause and let the correction under it
    stand alone; (b) rewrite the whole paragraph.
  - Why: R3 rules on this very clause. Its wording adds words only ('NOT
    yet', the reason, the ruling and its date), so no recorded word is lost
    and the file no longer states a report that never happened. The
    correction under the clause stays and now quotes the first wording, so
    the change can be read from the file itself.
  - Reverses if: the operator or MAIN rules that no text above an amendment
    of a decision file may ever change; the clause then gets its first
    wording back and the correction alone stands.
- Decision 0077 point 12 still opened with 'Not ruled at this record' above
  its dated note. The same form was used: a dated 'superseded' marker stands
  inside that sentence (words added only), and the note under it says so.
  With it, no tracked file outside the vendored kit presents LE-69, LE-76,
  LE-92, LE-99, LE-100 or LE-96 as waiting for a ruling.
- The hand-off: three Carried forward bullets of the state before the
  close-out 2 had been dropped as acted on (RUN-LIVE-CLICKS-STRIKE, 07 Open
  points, docs/plan/09 Checked on this machine). They are back in tighter
  wording, each with what was read back. A close-out drops no carried
  bullet; /done may drop an item that was acted on (FLEET item 5). All 30
  bullets of that state are present, beside the one NOTE the close-out 2
  added; SESSION stays 6 and the next action stays wave 1.
