# 0047 - File structure and module boundaries review

Date: 2026-11-17. For the ultraplan (docs/plan/README.md), dimension B10
file structure. Scope: where code, tests and docs sit, where parallel
agents collide, and the restructures (state.py, web/, ROADMAP.md, tests,
docs) that let waves of packages land without merge conflicts. Code read
at HEAD b8fda80; nothing but this note was changed. Verified 2026-11-18
at 1f91dc6: no file under server/, tools/, web/, app/, tests/, .claude/
or docs/design changed since b8fda80, so every path:line still holds.
Status: verified

## Sources (all accessed 2026-11-17; the four web pages re-fetched 2026-11-18)

- GIT-ATTR: https://git-scm.com/docs/gitattributes (built-in merge
  drivers, where a custom driver is defined; last updated in git 2.56.0).
- CC-MEM: https://code.claude.com/docs/en/memory (CLAUDE.md size target,
  `@path` imports, path-scoped `.claude/rules/`).
- MDN-SCRIPT:
  https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/script
  (execution order of `defer` scripts, module scripts).
- PYTEST-PATH: https://docs.pytest.org/en/stable/explanation/pythonpath.html
  (prepend and importlib import modes).
- MEASURED: throwaway read-only scripts kept outside the repo in
  `<sidecar>\Scratch\up-0047\` (graph.py: import graph, cycles, layers;
  churn.py, class_churn.py, state_churn.py: `git log --numstat`, merges,
  per-function hunks; state_surface.py; rows.py: a probe built from the
  loop's own regexes; pins.py; funcs.py; copyscan.py), each run as
  `python -I <script> <repo root>`. Repo files are cited as path:line.

## Summary

Agents collide on nine "append here" seams, not on file size: ROADMAP.md
(149 of 206 non-merge commits; both sides of 106 of 150 merges),
reviews.log, three SessionState methods, Core.__init__, do_GET, render()
in web/app.js, the index.html script tags, design 0001 section 9 and the
CLAUDE.md Settled list. The import graph is healthy (72 modules, 0
cycles). Before wave 1: one writer for ledger files, `merge=union` on
append-only logs, reserved doc numbers and a write-set per package (R1),
then the loop parser and hand-off fixes with a ROADMAP prune from 2061 to
about 200 lines (R2). The state.py split is verified with three
corrections and designed in R3 (772 lines to `server/al/text/`, nine
green commits); it clears only 12 of 54 state.py commits, so R5 follows.
web/ gets a shared fmt.js and a panel registry (R4). Leave the server/al
layout, tools/, scripts/, app/ and the flat tests/ alone.

## Current state

Tree (532 tracked files at b8fda80): tests 179, docs 92, server 76, app
64, ops 29 (26 are the vendored kit), web 25, tools 22, assets 12,
scripts 8. server/al (MEASURED graph.py):

- 72 Python modules, about 18,100 lines, one sub-package (theorycraft,
  30 modules). 0 import cycles at module level, with or without the 4
  function-level imports; 11 layers (L0 leaves to L10 `__main__`).
- Fan-out: core.py imports 38 modules (core.py:15-31), http.py 13,
  state.py 12 (state.py:13-24). Fan-in: jsonfile 16, paths 12, num 11,
  theorycraft/item 9, hotreload 8.
- The package boundary runs both ways: acts.py, tradestats.py, price.py
  and state.py import theorycraft modules, and theorycraft/live.py
  imports campaign and upgrade. No module cycle results.
- Three classes hold 2,582 lines: SessionState 1,035 lines / 64 methods
  (state.py:854), Core 861 / 52 (core.py:63), Handler 686 / 41
  (http.py:121).
- 20 of 1,048 functions exceed 50 lines. Longest: Core.__init__ 181
  (core.py:64), SessionState._apply_locked 159 (state.py:1430), main 145
  (__main__.py:145), SessionState.__init__ 117 (state.py:855),
  resume.scan 99 (resume.py:106), Handler.do_GET 83 (http.py:219),
  SessionState.snapshot 82 (state.py:1806).

Largest files (lines): tests/test_al_loop.py 2783, ROADMAP.md 2061,
state.py 1888, tools/al_loop.py 1757, web/app.js 1207, the audit doc
967, core.py 923, http.py 811, design 0001 742, web/index.html 638,
CLAUDE.md 598, web/app.css 570. state.py grew from 1550 to 1888 lines
(+22 percent) and core.py from 671 to 923 (+38 percent) after the
code-health pass measured them the same day
(docs/audit/code-health-2026-11-17.md:13-16).

Churn (MEASURED churn.py): 356 commits in two days (34, then 322), 150 of
them merges. Non-merge commits touching the file (`git log --no-merges
--full-history`) / merges in which both sides changed it (the file
differs from the merge base on both parents; re-measured by the
verifier, the draft's own method gave smaller merge counts):

- ROADMAP.md 149 / 106; docs/design/reviews.log 51 / 41
- server/al/state.py 55 / 33; server/al/core.py 52 / 33
- web/index.html 48 / 33; web/app.js 43 / 29; web/app.css 28 / 15
- CLAUDE.md 37 / 20; docs/design/0001-design-system.md 37 / 18
- server/al/http.py 31 / 23; docs/research/README.md 22 / 9
- every other file 18 or fewer; all of tools/ 48 touches, scripts/ 23

Where inside those files (MEASURED class_churn.py on the path-limited
log; commits touching the area / commits touching the file):

- state.py: snapshot 27/54, __init__ 27/54, the event dispatcher (apply,
  later _apply_locked) up to 28/54, the import block 18/54.
- core.py: Core.__init__ 39/49, the import block 22/49.
- __main__.py: the tick loop in main 17/18 (__main__.py:226-265).
- http.py: do_GET 16/31, the import block 11/31, do_POST 8/31.
- web/app.js: render 29/43, renderEval 13, start 12, tick 10, connect 8.
- web/index.html: the script tag lines 24/48 (index.html:12-32).
- design 0001: section 9, the message templates, 23/36.

web/: 21 classic `defer` scripts and no bundler (index.html:12-32). 20
are UMD view modules (`window.AL<Name>` on the page, CommonJS under
`node --test`; web/acts.js:6-14). app.js is one 1207-line closure of 57
functions with no exports: the token, the SSE link, every render call
and every button wire. 22 of the 34 node test files test web/ modules.

app/: main.js (422 lines) and six loose main-process modules at the
root, client/, overlay/, shared/ (render_gate, layout, format), brand/,
assets/. Low churn: main.js 12 commits, both sides of 5 merges. tools/:
22 flat modules, 8,127 lines; the loop family is 12 files and 5,168
lines. scripts/: 5 PowerShell entry points and 3 helpers. tests/: 157
test files with 1,745 test functions and 7 helper modules, all flat;
app/test/: 34 files, 230 tests. docs/: research (34 notes, 58 when the
ultraplan lands), decisions (44), design (5 plus reviews.log), audit
(3), ops (1), plan (new).

## Findings

- F1 Nine registration seams carry the collisions. Every feature appends
  to the same lists: a ROADMAP row, a reviews.log line, a field, a
  dispatcher arm and a snapshot key in SessionState, wiring in
  Core.__init__, a tick call, a route arm, a line in render(), a script
  tag, a template in design 0001 section 9, a Settled line (shares
  above). Parallel packages then either conflict (worktrees) or queue
  behind one file claim (shared checkout, FLEET item 16 b); both waste
  the operator's budget.
- F2 ROADMAP.md is 87 percent finished work. 151 rows parse; 139 are
  done and take 1,786 of 2,061 lines (MEASURED rows.py). The header says
  "Open work only" and "pruned at /done" (ROADMAP.md:3-5), but the /done
  ritual has no prune step (.claude/commands/done.md:50). Every session
  start reads the file (CLAUDE.md "Session workflow"): 139 KB for 14
  open bullets (12 parse as rows, F3). A median row is 12 lines, the longest 35.
- F3 The loop's row parser misses rows and misreads the hand-off.
  (a) ROW_ID allows only upper-case words joined by `-`
  (tools/loop_base.py:109), so 5 checklist bullets are not rows:
  ROADMAP.md:516, 530, 1277, 1518 (ids containing "1.0") and :2059
  (`OPERATOR:`). Line 530, UTIL-1.0-POST, is open: the loop neither
  lists nor dispatches it. (b) The id AUDIT-TC-WIRE appears twice
  (ROADMAP.md:1797, 1836); the first wins silently
  (tools/loop_roadmap.py:41-42). (c) `handoff_session` wants the line to
  end after the number (tools/al_loop.py:1527), but the live line and
  the /done template carry trailing text (AL-NEXT-SESSION.txt:3,
  done.md:68): it returns None and the checklist header shows the tick's
  fire count (tools/al_loop.py:1539); the only test uses the bare form
  (tests/test_al_loop.py:663). (d) An unknown lane hint, `(docs)` at
  ROADMAP.md:1277: that bullet is unseen today because of its dot, but
  once (a) is fixed the hint falls into the title unnoticed
  (ROW_RX accepts only build / data / review, tools/loop_base.py:110-111).
- F4 Nine of the 15 "Carried forward" bullets in the live hand-off would
  be dispatched as lane work when HALT is lifted (MEASURED: the bullets
  run through copies of SKIP_TAGS, tools/loop_base.py:119-122, and
  handoff_items, tools/loop_roadmap.py:269-292). Four restate open
  ROADMAP rows that are dispatched anyway (MERGE-SEAMS-FOLLOWUP,
  S5-FOLLOWUP, AUDIT-P8-LOW, CODE-HEALTH-FOLLOWUP), three are blocked
  items (BLOCKED_RX is applied to rows only, tools/al_loop.py:1125), two
  are status notes. Each would cost one opus lane run (the unskipped
  bullets become "handoff" work, tools/al_loop.py:1142-1147, routed to
  opus, tools/loop_base.py:73), and the item id is a hash of the bullet text,
  so a reworded bullet is dispatched again after every /done.
- F5 The CODE-HEALTH-FOLLOWUP claim holds, with corrections. The gate
  matches one exact path (tools/design_gate.py:16, 20-22); the reviewer
  agent names it in its trigger and default scope
  (.claude/agents/design-reviewer.md:3, 19); every lane prompt and the
  verifier's FAIL rule name it (tools/loop_prompts.py:12-13, 111-112);
  design 0001 calls it the one place for event text
  (docs/design/0001-design-system.md:17-19, 390-393, 460-462), and the
  reviewer reads 0001 in full as its rulebook (design-reviewer.md:24).
  Corrections: (1) design 0002 is a dated audit of commit 9f79bed
  (docs/design/0002-first-audit.md:3-7); its state.py:25 / :14 / :89
  references are already stale (summarize is at state.py:801) and stay
  as the record. (2) The row omits two test pins:
  tests/test_design_gate.py:17-19, and tests/test_audit_pass2.py:26-33,
  which wants the words "decision 0024" inside state.py; they occur only
  in the comment at state.py:267, which moves. (3) The row says the loop
  works it (ROADMAP.md:2022-2023), but a lane has no `.claude/` write
  grant (tools/loop_inbox.py:39-41). Six JS comments also say "state.py
  <function>" (app/shared/format.js:106, 117; render_gate.js:27;
  app/test/price.test.js:3; web/prices.js:5; web/status.js:111).
- F6 The design gate watches one of 27 server modules that hold player
  text. A scan for sentence-like literals finds 221 in 27 modules: 75 in
  state.py (34 percent), then diag.py 37, theorycraft/health.py 21,
  gfx.py 10, theorycraft/searchstr.py 9, theorycraft/lootfilter.py 8
  (MEASURED copyscan.py, a heuristic). reviews.log scopes name 25 other
  server modules, each added by an author who knew to ask. The class
  itself holds no sentence literal, yet 5 of 57 reviews were state-only
  with zero findings: the gate fired on state-machine work.
- F7 The text move alone does not stop state.py collisions. Of 54
  commits, 12 touched only module-level code, 17 only the class and 25
  both; 42 touched the class (MEASURED state_churn.py). Four setters share
  one body - lock, compare, copy, bump the version - (state.py:1171,
  1213, 1220, 1274; set_run_history also returns a changed flag), each
  paired with
  a field in __init__ and a key in snapshot().
- F8 web/ duplicates helpers and funnels every panel through one
  function. `pad` is defined in 5 files (web/acts.js:17, app.js:37,
  history.js:22, runs.js:18, summary.js:18), `duration` in 4 with one
  variant that takes the absolute value and has no empty form
  (web/history.js:24-30), `clock` in 3 with three behaviours
  (web/app.js:48-51, runs.js:36-39, summary.js:22-28); the overlay has
  its own `pad2` (app/shared/format.js:14). render() runs 10 view
  modules and 5 in-file renderers in sequence with no isolation
  (web/app.js:987-1062): one throwing paint stops every later panel.
- F9 Tests are flat and pinned to today's file names. 21 files are named
  after a batch, pass, plan or kit number (10 audit pass / batch files
  with 73 tests, test_ux_b6, test_ux_b8, four `_p16x` files, two `kit_v`
  files; app/test util9, util13, ux_sweep); one covers five modules
  (tests/test_audit_pass5_low.py). 12 test files import helpers from
  another test file (14 imports, one of them inside a function at
  tests/test_audit_pass3.py:110; such as tests/test_math_weights.py from
  test_tc_delta), 34 add tools/ to sys.path, and tests read sources by
  name: web/index.html in 13 files, web/app.js in 9, web/app.css in 5,
  http.py in 9, scripts/run.ps1 in 10, app/main.js in 13 (MEASURED
  pins.py). ROADMAP.md cites 117 distinct test file names and docs/ 80,
  so a rename breaks evidence trails.
- F10 "Take the next number" collides. docs/decisions/README.md:3-4
  tells every agent to take the next number; 16 commit subjects contain
  the word renumber (decisions 0007 to 0045, research 0029), and one
  commit removed conflict markers that had reached ROADMAP.md (b975d41).
  The ultraplan shows the cure: numbers 0035-0058 were assigned before
  the agents started (docs/plan/README.md:19-42).
- F11 CLAUDE.md is 598 lines against a guidance of under 200 (CC-MEM).
  219 lines are the byte-pinned fleet block; of the 366 tree lines, 234
  are the 45 Settled bullets. A test demands one Settled line per
  decision file (tests/test_audit_batch4.py:19-46), so every decision
  edits CLAUDE.md: 37 commits, both sides of 20 merges.
- F12 No equivalence check for a state refactor is committed. The
  code-health pass proved byte-identical snapshots with an ad hoc replay
  (docs/audit/code-health-2026-11-17.md:136-142); only the generator,
  tools/synth_client.py, is in the tree.
- F13 Small defects. `.claude/settings.json:17` pre-approves
  `python tools/ash_lane.py`, a file that does not exist (the lane tool
  is tools/al_lane.py). The loop reads optional briefs from `docs/plans/`
  (tools/loop_roadmap.py:83-89, tools/loop_prompts.py:58), a directory
  that does not exist, one letter from the new `docs/plan/`.
  CODE-HEALTH-FOLLOWUP item 3 calls core.write_private a CRLF writer,
  but it writes LF (core.py:44); the CRLF sites are __main__.py:141,
  keepalive.py:259, 419, procs.py:223 and hotreload.py:283.

## Recommendations

Ranked, best first. S = up to 2 h of agent time, M = up to a day, L =
more. ZERO-CLICK for all ten: developer-side only; a change lands by
commit or merge and a running core reloads itself in a source checkout
(decision 0042). The player does nothing.

### R1 FS-LEDGERS - one writer for ledger files, union merge, reserved numbers

- Action: packages never edit ROADMAP.md, CLAUDE.md, AL-NEXT-SESSION.txt,
  docs/design/reviews.log or the docs/*/README.md indexes; each returns
  its row flip, review line, Settled line and index line in its result
  and the wave integrator applies them in one commit. Add `merge=union`
  for reviews.log and the two README indexes. Decision and research
  numbers are assigned in docs/plan/packages.json before a wave starts.
  Each package lists the seam files it writes (`writes`: the eleven
  files in "Current state" plus __main__.py); the orchestrator never
  puts two packages with a common seam file in one wave.
- Impact: H. Removes the top two collision files (106 and 41 merges)
  with no code. The loop already works this way for ROADMAP.md
  (tools/loop_prompts.py:50-51) and CLAUDE.md (:36).
- Effort: S (3 lines in .gitattributes, a test of about 25 lines, fields
  in packages.json). Risk: union keeps both sides' lines: right for
  one-line records, wrong for ROADMAP.md, where a flip and an edit of
  one row would both survive. GIT-ATTR documents it for merge, revert
  and cherry-pick; rebase is UNVERIFIED; the loop merges
  (tools/loop_merge.py:104).
- ToS check: no floor rule touched; ledgers hold no game data and
  nothing reaches the game or the network. Depends on: nothing.
  Unblocks: wave 1 and landing the plan's rows. Files likely touched:
  .gitattributes, docs/plan/packages.json, docs/plan/08-orchestration.md,
  docs/decisions/README.md:3-4, a new tests/test_ledger_files.py.
- Acceptance test: in a scratch clone two branches each append a line
  to reviews.log and merge with no conflict, both lines present; the
  new test fails on a duplicate decision number or a malformed row.

### R2 FS-ROADMAP-A - fix the row parser and the hand-off reader, prune

- Action: let ROW_ID take `.` between segments; give the operator bullet
  an id and a BLOCKED tag; read `SESSION: <n>` with trailing text; skip
  a hand-off bullet that starts with an open row id or carries BLOCKED;
  move the 139 done rows to docs/roadmap/archive/2026-11.md and add the
  prune to /done; add a shape test.
- Impact: H for the operator: stops 9 wasted lane runs per hand-off
  (F4), makes UTIL-1.0-POST visible before the 2026-12-11 launch it
  waits for, and cuts the file every session reads by about 90 percent.
- Effort: S for code (about 15 changed lines), S for the prune. Risk: a
  wider id grammar feeds DEP_ID_RX, item file names and keep refs
  (tools/loop_base.py:96, 115-116); the row at ROADMAP.md:530 carries
  BLOCKED, so it becomes listed, not dispatched; the prune breaks
  tests/test_desktop_client.py:138-140 (the only test that reads the
  live ROADMAP.md; the loop tests write their own copy,
  tests/al_loopkit.py:79) unless it reads the archive.
- Sequence: (1) a shape test, marked xfail, listing today's 5 unseen
  bullets, the duplicate id and the odd lane hint; (2) parser and reader
  fixes with unit tests, fix the two bullets, drop the xfail; (3) the
  prune with the test_desktop_client change; (4) the done.md step. All
  while HALT is present.
- ToS check: no floor rule touched; the loop starts only headless agent
  runs, never the game, its files or the network. Depends on: R1.
  Unblocks: removing HALT, rows for every package, R6.
- Files likely touched: tools/loop_base.py, al_loop.py, loop_roadmap.py,
  tests/test_al_loop.py, a new tests/test_roadmap_shape.py, ROADMAP.md,
  docs/roadmap/archive/, done.md, AL-NEXT-SESSION.txt (session only).
- Acceptance test: every `- [ ]` / `- [x]` bullet in ROADMAP.md parses
  as a row with a unique id and a known lane hint; `handoff_session` of
  the live hand-off equals its number; the live hand-off yields no
  dispatchable bullet that names a row or carries BLOCKED; a work-list
  test on a copy of the live files lists UTIL-1.0-POST as blocked (a
  dry-run tick stops at HALT, tools/al_loop.py:1549-1551);
  tests/test_al_loop.py, test_roadmap_shape.py and
  test_desktop_client.py are green.

### R3 FS-STATE-TEXT - move card and event text out of state.py

- Action: move state.py:80-851 (772 lines, all pure functions and
  tables) into a package `server/al/text/`, keep state.py re-exporting
  every name, and move the gate, the reviewer agent, the lane prompts
  and design 0001 to the new path in the same series.
- Target modules (source lines in state.py at b8fda80):
  - text/common.py: 80-106, 165-192, 343-357, 723-727 (field guards,
    number words, the short list, the time guard).
  - text/events.py: 57-58, 69-77, 109-145, 801-851 (summarize, trade
    card sentence, reset reasons, fallbacks).
  - text/price.py: 43-44, 547-720 (price card, poe.ninja lines).
  - text/waystone.py: 360-420.
  - text/itemcheck.py: 148-162, 195-340, 493-540 (verdicts, stat deltas,
    calc notices, eval_card_text).
  - text/buildlive.py: 423-490 (build alert, upgrade notices).
  - text/overlaycard.py: 35-40, 730-798 (card timers, overlay_card).
  - Stays: buffers, TRADE_FIELDS, LISTED, character limits (26-31, 45-54,
    59-68) and the class (854-1888); state.py ends near 1,120 lines.
- Why a package, not one file: different features changed each family
  (item check 9 commits, price 6, events 6, overlay card 4, waystone 3),
  and a path prefix lets the gate cover later text modules unedited.
- Sequence (one commit each, suite green after each; within a commit
  write the new module first and edit state.py second, because the
  supervisor preflights and restarts a live core on each save,
  server/al/keepalive.py:49, __main__.py:44-65): (0) a new
  `tools/state_equiv.py --ref <rev>` that replays tools/synth_client.py
  seeds and a fixed card corpus through the working tree and through an
  export of <rev> in the sidecar Temp and compares the snapshots as
  key-sorted JSON, plus the gate prefix `server/al/text/` added beside
  the old path; (1) common; (2) events; (3) price; (4) waystone; (5)
  itemcheck; (6) buildlive; (7) overlaycard; (8) pins: drop state.py
  from UI_FILES, update tests/test_design_gate.py:17-19,
  tests/test_audit_pass2.py:30, .claude/agents/design-reviewer.md:3, 19,
  tools/loop_prompts.py:12-13, 111-112, design 0001 lines 17-19,
  390-393, 460-462, the six JS comments, one reviews.log line. Step 8
  runs in a session, not a lane (F5). Dated records stay: design 0002
  and 0003, decisions 0014, 0016, 0019, 0029, 0032.
- Impact: M. Clears 12 of 54 commits from state.py, stops the gate
  firing on state-machine work, and gives copy packages (voice,
  accessibility wording, glanceability) one file per card family.
- Effort: M (772 lines moved, about 30 changed in 12 pinned files).
  Risk: a moved name read through the old module. All importers
  (core.py:23 and 43 to 47 test files, by regex) import or read attributes and none patches a
  state constant, so same-object re-exports keep them working, as in the
  loop split (tools/al_loop.py:92-96).
- Tests: the equivalence run reports identical output after every step;
  so do the 14 files that pin the text (229 tests in 7 s: test_summarize,
  test_eval_text, test_price_text, test_trade_text, test_waystone,
  test_waystone_reward, test_build_live, test_ux_b6, test_design_gate,
  test_audit_pass2, test_math_compare, test_math_dps_sanity,
  test_math_weights, test_tc_delta); the whole suite through the suite
  gate before step 8 commits.
- ToS check: floor rules on wording (the "isn't affiliated" line, no GGG
  marks, never presented as endorsed): every string moves byte for byte
  and the disclaimer constant stays in server/al/__init__.py. The static
  floor scan walks server/ recursively (tests/test_floor_static.py:37,
  116), so the new package is covered.
- Depends on: R1. Unblocks: R5, R7, R10 copy sheets, every package that
  rewrites a card sentence. Files likely touched: server/al/state.py,
  server/al/text/*.py (8 new), tools/design_gate.py,
  tools/loop_prompts.py, tools/state_equiv.py, the reviewer agent,
  design 0001, reviews.log, the two tests, six comments.
- Acceptance test: tools/design_gate.py, tools/loop_prompts.py and
  .claude/agents/ no longer name "server/al/state.py";
  `design_gate.is_ui_path` is true for "server/al/text/price.py" and
  false for "server/al/state.py"; state.py holds no sentence literal;
  the equivalence run is identical; suites green; a design-reviewer PASS
  line is recorded.

### R4 FS-WEB-SHELL - shared format helpers, then a panel registry

- Action: (a) one helper each side that knows where dashboard sources
  live (tests/srcpaths.py, app/test/_web.js) and switch the pinned tests
  to it; (b) `web/fmt.js` (UMD, loaded first) with pad, duration and its
  absolute form, clock and its dated form; the five files alias it and
  keep their exports; (c) `window.ALApp.register({name, order, paint,
  tick, wire})` in app.js: each module registers itself, render(), tick()
  and start() become loops with a try / catch per panel, and the eight
  feature blocks inside app.js move to `web/panels/` (events and trades
  111-208, layout 210-303, build 305-612, item check 614-701, weights
  703-805, web data 807-837, rates and price 839-944, graphics 946-985),
  leaving a shell of about 250 lines.
- Impact: H. render, start and tick are the seam in 29, 12 and 10 of 43
  app.js commits; one broken card no longer blanks the cards after it.
- Effort: (a) S-M, 27 test files; (b) S, about 45 duplicate lines out;
  (c) M-L, about 950 lines moved in eight commits. Risk: paint order and
  live-region announcements; keep today's order with explicit `order`
  values. `defer` scripts run in document order and before
  DOMContentLoaded (MDN-SCRIPT), so fmt.js first and app.js last is
  enough; index.html still gains one tag per new panel until R8.
- Tests: the node suite (230) after each move; a new fmt test with the
  behaviours of F8; a registry test (order, a throwing panel is
  isolated); tests/test_dash_console.py and tests/test_a11y.py on the
  real page; design-reviewer on the diff.
- ToS check: the dashboard only shows core data; the Copy-code clipboard
  write stays on the player's click (decision 0014) and moves verbatim;
  no clipboard read, timer or request is added; CSP `script-src 'self'`
  (http.py:38-41) and "no CDN" hold because every file is same-origin.
- Depends on: R1, R9. Unblocks: the target design packages (Play tab,
  tab set), any new card, R8. Files likely touched: web/app.js,
  web/fmt.js, web/panels/*.js (8 new), the 20 web modules,
  web/index.html, app/test/*.test.js, tests/srcpaths.py, the F9 tests.
- Acceptance test: pad, duration and clock are each defined once under
  web/; web/app.js is under 300 lines and names no feature module;
  `npm test --prefix app` and the pytest files that read web/ are green.

### R5 FS-STATE-SEAMS - publish() and per-concern parts of SessionState

- Action: (1) `SessionState.publish(key, view)` for views the core only
  stores (run_history, price_watch, diag; state.py:1171, 1220, 1274),
  merged into snapshot(), the old setters kept as wrappers; (2) split
  the class by concern into mixin modules, each with its own
  `_init_<x>()` and `_view_<x>(now)` called from __init__ and
  snapshot(): cards, trades, characters, idle and summary, published
  views. The dispatcher stays whole because its order matters.
- Impact: M-H. Addresses the 42 of 54 commits that hit the class; after
  (1) a new core-published view needs no state.py edit.
- Effort: (1) S, about 40 lines; (2) M, about 640 lines moved. Risk:
  lock discipline and operation order; R3's tool proves equality, and
  the loop already uses the mixin pattern (tools/loop_inbox.py:438,
  tools/loop_merge.py:76).
- Tests: the equivalence run after every commit; tests/test_bus_state.py,
  test_fuzz.py, test_soak.py, test_e2e_replay.py, test_util_multichar.py,
  test_live_exit.py, test_resume.py; whole suite before the last commit.
- ToS check: state is built only from the opted-in Client.txt tail and
  per-press item text; no new input, read or request.
- Depends on: R3. Unblocks: features that add a snapshot field (the
  S5-FOLLOWUP overlay zone-guide line and persisted upgrade list,
  reliability and observability work). Files likely touched:
  server/al/state.py, server/al/state_*.py (5 new), a new
  tests/test_state_publish.py.
- Acceptance test: equivalence identical; `SessionState` keeps its
  public methods; a test publishes a new key and reads it from
  snapshot() with no edit to state.py.

### R6 FS-ROADMAP-B - rows added and flipped by new files

- Action: keep ROADMAP.md as the one page of open rows, and let writers
  create files only: a new row is `docs/roadmap/new/<ID>.md` holding the
  row bullet as today; a finished row gets `docs/roadmap/done/<ID>.md`
  holding the done note. A loader composes ROADMAP.md, the new files and
  the done markers; one writer (the wave integrator, /done, or the tick
  under its merge lock) folds them into ROADMAP.md and the archive.
  Rows become one line plus a brief in `docs/plan/briefs/<ID>-<slug>.md`
  (replacing the unused `docs/plans/` path) with its `Depends on:` line.
- Impact: M. Adding or flipping a row can no longer conflict; the row
  format, ROW_RX and the prompts stay; one-line rows keep the file small.
- Effort: M (loader about 40 lines, fold tool about 120, tests about
  150; call sites tools/al_loop.py:929-930, 1084, loop_roadmap.py:86,
  309, 337, loop_merge.py:70). Risk: two sources of truth between folds;
  the loader is the only reader and a test fails on a done marker
  without a row.
- Sequence: (1) loader with tests, ROADMAP.md alone still valid; (2) the
  fold tool and its /done step; (3) prompts and CLAUDE.md wording, in a
  session; (4) the briefs directory.
- ToS check: no floor rule touched; tracked text only. Depends on: R2.
  Unblocks: lanes and agents filing follow-up rows in parallel. Files
  likely touched: tools/loop_roadmap.py, al_loop.py, loop_merge.py,
  loop_prompts.py, a new tools/roadmap.py, tests/test_al_loop.py, a new
  tests/test_roadmap_rows.py, done.md.
- Acceptance test: in a scratch clone, two branches each add a row file
  and a done marker and merge with no conflict; the work list shows
  both; a fold leaves no fragment and an unchanged row set.
- Not chosen: one file per row with no ROADMAP.md; it changes every
  consumer (46 ROADMAP mentions in tests/test_al_loop.py alone).

### R7 FS-CORE-SEAMS - tick list, route table, one import per line

- Action: Core keeps a list of (name, callable) ticks and
  __main__.py:226-265 becomes one loop with the same try / except;
  do_GET / do_POST / do_PUT dispatch through per-verb dicts after
  `_guard`; the grouped import at core.py:15-18 becomes one name per
  line, sorted.
- Impact: M. Core.__init__ (39/49), the tick loop (17/18) and do_GET
  (16/31) stop being edited by every feature.
- Effort: ticks S (36 lines out), imports S, routes M. Risk: tick order
  and the guard; keep the order of __main__.py:226-265 and call `_guard`
  before any lookup (http.py:219-223).
- Tests: tests/test_http_security.py, test_http_robust.py,
  test_api_token_hdr.py, test_audit_http_harden.py, test_fullstack.py,
  test_core_crash_log.py; R3's tool for the tick order.
- ToS check: floor rule "Client.txt only after the opt-in": the consent
  gate in ensure_tailing is unchanged; the token, Host / Origin checks,
  CSP and the 127.0.0.1 bind are untouched. Depends on: R3 (its tool).
  Unblocks: packages that add an endpoint or a tick. Files likely
  touched: server/al/core.py, __main__.py, http.py, a new
  tests/test_routes.py.
- Acceptance test: a test registers a tick and a GET route without
  editing __main__.py or do_GET; an unknown path and a missing token
  answer as before.

### R8 FS-WEB-ASSEMBLE - generate the dashboard's script and style tags

- Action: at serve time the core inserts one `<script defer>` per
  `web/panels/*.js` (sorted, before app.js) and one stylesheet link per
  `web/panels/*.css` at a marker in index.html; later, if the target
  design keeps one block per card, per-panel HTML fragments with a
  `slot` and `order` header.
- Impact: M. Removes the script-tag seam (24/48 index.html commits) and
  lets app.css (28 commits) split per panel.
- Effort: tags M (about 60 lines in the core plus tests); fragments L.
  Risk: the 13 test files that read index.html must read the assembled
  page through R4's helper; duplicate ids across fragments need a test.
- Tests: tests/test_http_security.py (CSP header unchanged), the CDP
  console test and tests/test_a11y.py on the assembled page.
- ToS check: no inline script and no remote origin are introduced; the
  page is still served only on 127.0.0.1 with the same CSP. Depends on:
  R4. Unblocks: UI packages that add a card with no shared file edit.
  Files likely touched: server/al/http.py, a new server/al/webpage.py,
  web/index.html, tests/srcpaths.py.
- Acceptance test: adding web/panels/x.js makes GET / contain its tag
  with no edit to index.html; the served page has unique ids.

### R9 FS-TESTS - naming rule, guard tests, folds only when touched

- Action: name test files by subject, never by batch, pass, plan or kit
  number (the id goes in the docstring); helpers live in non-test
  modules; keep tests/ flat. Add a guard test with the 21 batch-named
  files and the 14 test-to-test imports as allow-lists that may only
  shrink. A package that owns a subject moves that subject's tests out
  of a batch file as part of its own change; no big-bang fold.
- Impact: L-M. Effort: S (about 70 lines). Risk: none for the guard; a
  fold must keep the collected test count per moved function.
- ToS check: no floor rule touched (test files only). Depends on:
  nothing. Unblocks: R3 and R4. Files likely touched: a new
  tests/test_test_layout.py.
- Why flat: in the default prepend mode test files without packages
  need unique names, and importlib mode forbids tests importing each
  other (PYTEST-PATH); 12 files do.
- Acceptance test: the guard fails on a new `test_audit_pass9.py` and on
  a new `from test_x import`; both allow-lists shrink wave by wave.

### R10 FS-DOCS - docs layout and structure guards

- Action: (a) docs/plan/ holds the ultraplan (README, 01-09,
  packages.json) and briefs/ from R6; (b) split design 0001 section 9
  rule 2 (lines 399-561, the per-feature templates) into
  `docs/design/copy/<family>.md`, one per text module of R3, leaving the
  rules in 0001; (c) docs/decisions/README.md lists every decision and
  drops "take the next number"; (d) a structure test: the import graph
  of server/al stays acyclic, and every server module with 4 or more
  sentence literals is under a gate path or on a reasoned exempt list.
- Impact: M: section 9 is 23 of 36 commits on design 0001. Effort: S-M.
  Risk: the reviewer must be told to read the copy sheets
  (design-reviewer.md:24).
- ToS check: no floor rule touched; (d) adds a check, never a read of
  game data. Depends on: R1, R3. Unblocks: parallel copy packages.
  Files likely touched: docs/design/0001-design-system.md,
  docs/design/copy/*.md, docs/decisions/README.md, the reviewer agent,
  a new tests/test_structure.py.
- Acceptance test: a planted cycle between two server modules and a new
  module with 5 sentences outside the gate both fail the test.

## Cut or merge

- Cut: regrouping server/al into more sub-packages. The graph has no
  cycle, and about 200 test imports would change for no collision gain.
- Cut: packaging tools/ or moving the loop files. The scheduled task,
  .githooks/pre-commit, the permission list and 34 tests name today's
  paths; tools/ had 48 file touches in 206 commits.
- Cut: restructuring app/ or scripts/. Low churn; 13 tests and the floor
  allow-list name app/main.js; 10 tests name scripts/run.ps1.
- Cut: converting web/ to ES modules now. Native modules need no bundler
  (MDN-SCRIPT), but the registry already removes the seam and the
  conversion rewrites 21 scripts and 34 tests.
- Cut: a custom git merge driver for ROADMAP.md. Drivers are defined in
  .git/config, not in a tracked file (GIT-ATTR), so every clone and
  worktree would need an install step.
- Merge: pad / duration / clock into web/fmt.js (R4); the overlay's
  format.js stays apart (file-system page, own budget, decision 0002).
  `docs/plans/` into `docs/plan/briefs/` (R6); the identical setters
  into publish() (R5); done rows into the archive (R2).
- Split: CODE-HEALTH-FOLLOWUP into three rows: text split (R3, session),
  web helpers (R4 b), CRLF writers with the corrected list (F13).

## Rejected

- A bundler or transpile step (esbuild, Rollup, TypeScript) to divide
  app.js. Decision 0002 keeps the dashboard as static HTML, CSS and
  vanilla JS with no framework (docs/decisions/0002-stack.md:17-18); its
  reversal condition (the overlay misses its budget) is not met, and a
  bundler adds supply chain for no player value.
- Loading a helper or a module loader from a CDN. CLAUDE.md "No CDN at
  runtime"; CSP `script-src 'self'` (http.py:38).
- Moving the clipboard-read wiring out of app/main.js as tidying. Floor
  rule: the clipboard is read only once per manual AshLight hotkey
  press. The one read is pinned to app/main.js at its reviewed anchor
  (tests/test_floor_static.py:89-93); a structure package must not widen
  where a read may live.
- Moving theorycraft/datacredit.py up a level to straighten the package
  boundary. The Settled entry for decision 0020 names that file as the
  only home of credit text (CLAUDE.md:427-430); its reversal conditions
  are not met.
- Moving the Settled list into path-scoped rules to reach 200 lines.
  Rules with `paths` load only while matching files are worked on
  (CC-MEM), so an agent could propose reversing a settled, floor-adjacent
  call (0017, no trade endpoint) without ever seeing it.

## Open questions

- Settled list form: 234 lines against the 200-line guidance (CC-MEM).
  An `@docs/decisions/SETTLED.md` import keeps the context cost and only
  moves the collision, which R1 already removes. Shortening the bullets
  is a rules change: operator or adjudicator.
- Do headless lanes started with lean or bare flags expand CLAUDE.md
  imports and load `.claude/rules/`? Partly answered (CC-MEM, re-read
  2026-11-18): project rules are skipped when `project` is left out of
  `--setting-sources`, so a lane on "project settings only" keeps them;
  bare mode is still UNVERIFIED. It decides whether any rule text may
  ever leave CLAUDE.md.
- `.claude/settings.json:17` (F13): removing a permission entry is a
  settings change; it belongs in the operator's batched ask.
- Should the 1,786 archived ROADMAP lines be published? They are session
  narrative; the go-public note (0057) decides archive or git history.
- Will the target design (docs/plan/03-target-design.md) keep one block
  per card? If not, drop the fragment half of R8.

## Verification

Independent check, 2026-11-18, at HEAD 1f91dc6 (code identical to
b8fda80 for every cited path).

- Code citations (A): about 70 path:line references opened, all but
  three held as written. Fixed: SessionState.snapshot is state.py:1806 (not 1807); the
  opus route for hand-off work is tools/loop_base.py:73 (line 74 is the
  sonnet data lane), now with the dispatch site tools/al_loop.py:1142-1147;
  F3 (d) reworded, since the `(docs)` bullet is invisible today and the
  hint only leaks into a title after the dot fix.
- Numbers (Summary and Findings): re-ran the loop's own ROW_RX on
  ROADMAP.md (156 bullets, 151 rows, 139 done, 12 open, 150 unique ids,
  the 5 unseen lines exactly as F3 lists), the live hand-off through
  handoff_items (15 bullets, 9 unskipped, handoff_session None), commit
  counts with `--full-history` (all 11 match), tracked files (532), the
  21 script tags, pad / duration / clock sites, the render() line-up
  (10 modules, 5 renderers), the 16 "renumber" subjects, state.py
  772-line text region and its top-level names. Corrected: the
  both-sides merge counts (re-measured against the merge base: ROADMAP
  106 not 110, reviews.log 41, state.py 33, core.py 33, index.html 33,
  app.js 29, CLAUDE.md 20, design 0001 18, http.py 23, main.js 5);
  test-to-test imports 12 files / 14 imports (not 11 / 13); state.py
  importers stated as a range (43 to 47 test files by regex); "14 open
  rows" is 14 open bullets of which 12 parse; the setters share a body,
  not six identical lines. No ranking changes.
- Web sources (B): GIT-ATTR (union is built-in and may reorder added
  lines; drivers live in git config; merge, revert, cherry-pick named;
  rebase not named, stays UNVERIFIED; page at git 2.56.0), CC-MEM (target
  under 200 lines; imports do not cut context cost; `paths` rules load
  only on matching files), PYTEST-PATH (unique names in prepend mode;
  importlib forbids test-to-test imports), MDN-SCRIPT (defer keeps
  document order, runs before DOMContentLoaded; module scripts defer by
  default) all re-fetched and confirmed.
- ToS floor (C): all ten recommendations re-tested against each floor
  rule; none reads memory, injects, hooks graphics, touches packets or
  game files, sends input, adds a clipboard / screen read, timer or
  request, calls a trade or undocumented endpoint, or touches branding or
  revenue. R4 keeps the Copy-code write on the player's click; R8 keeps
  CSP and the 127.0.0.1 bind. The five Rejected items stay rejected.
- Settled decisions (D): no recommendation reverses one; R4 and the
  Rejected bundler respect 0002, the datacredit item respects 0020, the
  clipboard item respects 0003, R3 leaves the disclaimer and 0014 click
  write untouched.
- Completeness (E): every brief point is covered (server/al map, churn,
  collisions, state.py split with move order and the gate / reviewer /
  prompts / design-doc claim verified in code with three corrections,
  web/ helpers and app.js division, app/, tools/, scripts/, tests/
  naming policy, docs/ with docs/plan, ROADMAP structure plus both known
  parser defects). Added: the --setting-sources fact to the lanes open
  question.
- Recommendations (F): each carries Action, Impact, Effort, Risk, ToS
  check, Depends on, Files and Acceptance test; ZERO-CLICK is stated once
  for all ten above R1 (developer-side, the player does nothing).
- Hygiene (G): ASCII and LF via the lint; no drive path, email, account
  id, other tree name or private name.
- UNVERIFIED remaining: whether union merge applies during rebase;
  whether bare-mode lanes load CLAUDE.md imports and rules; the
  copyscan.py sentence counts in F6 (a heuristic, not re-run).
