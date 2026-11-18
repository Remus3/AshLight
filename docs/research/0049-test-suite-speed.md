# 0049 - Test suite speed

Date: 2026-11-17 (measured and read that day; committed 2026-11-18). For
the ultraplan (docs/plan/README.md), dimension B12 test suite speed.
Scope: where the Python and node suites spend their time, what the
machine-wide suite gate costs a wave of parallel worktree agents, and a
ranked plan (hot spots, parallelism, budgets, wave gate policy). No product
code was changed; two kit gate findings are documented, not fixed.
Verified 2026-11-18 by an independent agent (see "Verification").

Status: verified

## Sources (all accessed 2026-11-17; web sources re-fetched 2026-11-18)

Local measurements (raw files kept in `<sidecar>\Scratch\up-0049\`):

- RUN: the one whole-suite run this brief allowed, through the gate from the
  main checkout at below-normal priority, 23:31 local: the brief's command
  with the full duration listing and a junit report added (`--durations=0
  --durations-min=0 --junitxml=...`, same tests). 2316 passed, 3 skipped,
  237.17 s on pytest's clock; gate row: hold 237.7 s, wait 0.0 s, peak
  commit 1022 MB. Box state: about 25 other agents working, the game
  running, gate otherwise empty. Files: suite_raw.txt, junit.xml.
- GATELOG: the gate's own log `%LOCALAPPDATA%\fleet\suite\durations.jsonl`
  (ops/fleet_kit/fleet_suite_gate.py:43-45): 348 rows for this tree from
  2026-11-16 21:26 to 2026-11-17 21:04 local (23.6 h), before RUN.
- PROBE: one file-named run of 24 slow test files (432 tests, 128.9 s) with
  a scratch-only pytest plugin that counts child processes and main-thread
  time in process creation, child waits, `time.sleep` and thread waits.
- COLLECT: three `--collect-only` runs; MARK: four collect-only runs with
  `-m slow`, `-m git`, `-m server` and the negation, joined to RUN's times.
- NPM: three runs of `npm test --prefix app` (node-only, see F9).
- VERD: `ops/loop/control/gate_verdicts.json` (untracked loop state).
- GIT: `git log` of the same 23.6 h window (354 commits, 150 merges;
  re-counted 2026-11-18 with `--since` / `--until` on the window bounds).

Web:

- PYPI: https://pypi.org/pypi/pytest/json and the same route for
  pytest-xdist, pytest-timeout, execnet, pytest-asyncio, anyio.
- PTCL: https://docs.pytest.org/en/stable/changelog.html
- PTREF: https://docs.pytest.org/en/stable/reference/reference.html
- PTUSE: https://docs.pytest.org/en/stable/how-to/usage.html
- PTFAIL: https://docs.pytest.org/en/stable/how-to/failures.html
- XD-D: https://pytest-xdist.readthedocs.io/en/stable/distribution.html
- XD-H: https://pytest-xdist.readthedocs.io/en/stable/how-to.html
- NODE: https://nodejs.org/api/test.html

## Summary

- The whole Python suite takes 191 s (median of the last 30 green serial
  gate runs) and 238 s under tonight's load (RUN). It was 38 s a day
  earlier: a 5x growth in 24 hours. About 64 s of that step is the
  optional calc component becoming present on this machine around 10h
  (its live tests skip without it, F2); the rest is new tests and load.
  The node suite takes 0.45 s.
- Time is concentrated: 5 of 157 test files hold 60 percent, 23 files hold
  91.5 percent; 1819 of 2319 tests finish in under 10 ms and total 3.2 s.
  Collection (0.5 s), setup (4.9 s) and teardown (5.7 s) are not the issue.
- Four causes explain 73 percent: real `git` child processes in the loop
  tooling tests (about 57 s), the live PoB calc tests (64 s), a static ToS
  floor scan that re-runs 26 regexes over the tree 34 times (28 s), and
  main-thread sleeps (25 s).
- The wave bottleneck is the gate rule "one suite per tree", not the two
  machine slots: every worktree of this tree counts as the same tree. At
  2.03 whole-suite runs per merge (measured) the ceiling is 7.5 to 9.3
  merges per hour however many agents work in parallel. In the measured
  window agents spent 9.0 h waiting on the gate and 10.2 h holding it.
- Best first moves: (R1) a wave policy of named-file subsets per package
  plus one whole suite per merge batch, which lifts the gate ceiling to
  about 64 to 77 packages per hour with no code speed-up; (R2) memoise the
  floor scan (-25.7 s, one test file); (R3) run the whole suite in parallel
  (237 s to about 60-80 s; the loop gate already does this with xdist).
- A slow-test budget (R5) and plugin pinning (R6) stop the regrowth. Two
  kit gate defects are documented for MAIN (F11, F12).

## Current state

- Config: `pytest.ini:1-3` (testpaths, `-p no:cacheprovider`).
  `tests/conftest.py:63-67` registers three markers (slow = call over about
  1.5 s, server = binds a socket, git = spawns real git); nothing reads
  them and no time ceiling exists. One shared fixture: `warm_bridge`
  (`tests/conftest.py:45-60`, session scope).
- Gates: CLAUDE.md "Gates", `.claude/commands/done.md:26-28`,
  `ops/loop/gates.txt` and `scripts/build.ps1:165-172,185` all name the
  whole pytest suite through the gate plus `npm test`. The loop gate adds
  `-n 8 --dist loadfile` when pytest-xdist is importable
  (`tools/al_loop.py:268-304`); the session gate and build.ps1 do not.
- The loop already has the right shape: producers run touched tests only
  (`tools/loop_prompts.py:20-29`) and the loop gates each tree state once,
  verdicts cached by git tree id (`tools/loop_merge.py:19-73`,
  `tools/al_loop.py:61-64`). Interactive worktree agents do not use it:
  they each run whole suites.
- Gate mechanics that matter here (`ops/fleet_kit/fleet_suite_gate.py`):
  2 regular slots (:175); a third "lane" slot for a (tree, command) whose
  median hold over its last 5 runs is at most 130 s (:46-53, :179,
  :1432-1434); no slot while a live holder is the same tree (:134-136,
  :648-654), and a worktree counts as its main checkout (:1368-1373);
  history is keyed by a hash of the exact command words (:1363-1365); a
  waiter gives up after 3600 s (:192); a suite is refused while another
  live agent holds uncommitted test-relevant edits in that checkout
  (:17-23, :1154-1163), so a wave's whole suite needs a clean worktree.
- What needs the gate: the claims hook calls a pytest run "whole" only when
  it names no test file and has no `-k` (lines 874-891 of
  `ops/fleet_kit/fleet_claims.py`). A file-named run is not gated.
- Tool versions here: Python 3.14.4, pytest 9.2.0 (the latest, released
  2026-10-27: PYPI, PTCL), node 24.15.0. The shared interpreter also
  auto-loads five plugin modules the repo never asks for (anyio,
  pytest-asyncio 1.4.1, pytest-timeout 2.4.0, pytest-xdist 3.8.0 with its
  looponfail module); xdist 3.8.0 and timeout 2.4.0 are the latest (PYPI);
  pytest-asyncio 1.4.1 and anyio 4.13.0 trail their latest releases (1.5.0
  of 2026-11-12 and 4.16.0 of 2026-11-01, PYPI, accessed 2026-11-18).
- Decision 0002 allows pytest as the one test dependency and anything else
  only as optional and ImportError-guarded
  (`docs/decisions/0002-stack.md:14-16`).

## Findings

### F1 - Profile of one whole run (RUN)

- 2319 collected, 237.17 s. Test phases sum to 235.8 s (junit); collection
  0.52 s (COLLECT: 0.82-0.90 s wall per collect-only run); interpreter and
  plugin start plus exit about 0.5 s. Setup 4.9 s, call 221.5 s, teardown
  5.7 s (two-decimal listing). Call time is the whole problem.
- Distribution: median test 1.0 ms (kit autouse fixtures included, so the
  per-test fixture cost of `fleet_test_guard.py:221-237` is at most 2.3 s
  in total). 1819 tests under 10 ms total 3.2 s. 231 tests at or over 0.1 s
  total 220.6 s (93.6 percent); 50 at or over 1 s total 139.9 s (59.3
  percent); 6 at or over 5 s total 55.9 s (23.7 percent).
- Per file, seconds (tests): test_al_loop.py 53.8 (153),
  test_math_e2e_live.py 31.7 (6), test_floor_static.py 28.4 (35),
  test_fullstack.py 14.4 (4), test_math_perf.py 13.1 (3), test_keepalive.py
  8.4 (19), test_al_loop_gate_cache.py 7.8 (17), test_fuzz.py 7.4 (30),
  test_budgets.py 7.4 (6), test_procs.py 4.6 (15). Top 5 = 141.4 s (60.0
  percent), top 10 = 176.8 s (75.0 percent), top 23 = 91.5 percent; the
  other 134 files, about 1500 tests, total 20 s.
- By family: loop / lane / kit tooling tests 23 files, 363 tests, 69.5 s
  (29.5 percent of the suite tests the dev loop, not the product);
  `test_audit_*` 17 files, 146 tests, 4.9 s; `test_ux_*`, a11y, design and
  `test_util_*` 20 files, 277 tests, 1.0 s.
- Slowest single tests: test_fullstack calc leg 12.4 s, test_math_e2e_live
  ring case 12.2 s, test_math_perf memory ceiling 11.2 s, test_keepalive
  real-core restart 8.2 s, test_procs stop script 4.4 s.

### F2 - Causes of the slow tail (PROBE plus RUN)

- Child processes: 2086 spawns in the 24 probed files, 2031 of them `git`
  (about 28 ms each). test_al_loop.py alone starts 1543 gits: 43.3 s of its
  51.7 s. test_al_loop_gate_cache.py 273 gits (6.8 of 7.3 s),
  test_leak_sweep.py 132 gits (3.7 of 4.1 s). Each `git_world` builds a
  repo with 4 git calls (`tests/al_loopkit.py:144-159`); 77 git-marked tick
  tests that build no repo still cost 33.9 s because the code under test
  calls real git. Suite-wide: about 57 s (24 percent).
- Live calc (LuaJIT plus PoB, present only where `setup.ps1 -TcCalc` ran):
  63.9 s (27 percent) across test_math_e2e_live, test_math_perf, the
  test_fullstack calc leg, test_math_weapon_type, test_tc_bridge and one
  test_audit_pass7 case. GATELOG shows the step: hold about 95 s to 138 s
  at 10:23 on 2026-11-17, with peak commit going from 230-400 MB to 606 MB
  in the same run.
- Static floor scan: 34 full scans at 0.83 s each = 28.4 s (12 percent).
  One scan is 189 files, 1.68 MB: walk 0.02 s, read 0.005 s, 26 regexes
  0.79 s (`tests/test_floor_static.py:129-141`). The 29 planted cases and 3
  mutation tests each rescan the unchanged copy (:244-253, :256-292).
- Sleeps: 24.7 s of main-thread `time.sleep` in the probed files (10
  percent): test_keepalive.py 6.8 s (0.2 s polls around real processes,
  supervisor `--poll 0.5 --backoff 0.5,1,2`, :334-376), test_budgets.py 6.8
  s (two fixed 3.0 s CPU windows, :60 and :176), test_procs.py 2.9 s (three
  0.5 s settles at :196 plus polls), test_soak.py 2.0 s, test_http_robust
  1.7 s, test_hot_reload.py 1.4 s. Only 50 sleep call sites exist; most are
  20 ms polls.
- Other children: about 13 s (25 PowerShell 5.1 starts, 24 python starts
  for real cores and supervisors, node plus headless Chrome 2.1 s).
- Thread waits 4.5 s: server shutdown waits out the serve loop poll.
  `tests/test_audit_pass5.py:73,107` and `tests/test_cover_gaps.py:249` use
  the 0.5 s default (0.5 s teardown each); 25 other files pass 0.05.
- CPU: test_fuzz.py 7.4 s of time-bounded loops (0.6 s each,
  `tests/test_fuzz.py:35`).
- Port binds are cheap: 24 files pass port 0 to `serve`. No test launches
  Electron: the live overlay smoke is opt-in and skipped, test_procs uses a
  renamed python.exe (`tests/test_procs.py:178-188`), test_dash_console
  drives headless Chrome (2.8 s).

### F3 - Markers exist, are unused and drift

- MARK: slow 45 tests / 118.6 s; git 147 / 68.2 s; server 76 / 84.4 s;
  union 239 tests / 176.9 s (75.0 percent). Unmarked: 2080 tests / 58.8 s,
  of which 28.4 s is the floor scan.
- 21 of 45 slow-marked tests run under 1.5 s (6 under 0.5 s). Two unmarked
  tests exceed 1.5 s: `tests/test_budgets.py:52` (3.3 s) and the first
  planted floor case (1.7 s, it pays the module fixture). 52 unmarked tests
  take 0.5 s or more and total 44.0 s.

### F4 - The gate log: growth, waits, reds (GATELOG, GIT)

- Growth of the green serial median per hour: 38 s (2026-11-16 21h), 54,
  75, 60 (2026-11-17 08h), 137 (10h), 154, 177, 180, 184, 191 (19h), 206
  (20h); RUN 238 s at 23:31. No test or gate noticed.
- 267 serial whole-suite runs: hold 32,332 s in total; wait 22,804 s in
  total, median 30 s, p90 217 s, max 785 s; 111 runs waited over 60 s. 221
  green, 45 red (16.9 percent), 1 killed.
- All 348 rows: 10.25 h of slot time and 9.02 h of waiting in 23.6 h. This
  tree held 76.4 percent of all gate hold time on the machine in the window
  (10 other trees: 29 runs).
- 10 runs had wait plus hold over 600 s, the foreground tool-call ceiling;
  one died with exit 143 at 590 s (wait 435, hold 155).
- 18 command spellings (6 for the serial whole suite; the done ritual, the
  loop gate and build.ps1 each produce a different one; the verifier
  decoded all six serial hashes from `fleet_suite_gate.py:1363-1365`:
  `python -m pytest -q`, the same with `-x`, with `tests`, with `-p
  no:cacheprovider`, with `-x -p no:cacheprovider` and with `-p
  no:cacheprovider -x`; `-x` runs end at the first failure, so red holds
  are short). Lane and memory
  history are per spelling, so each new spelling starts with no history.
- The serial suite lost lane eligibility at 10:23 when its median passed
  130 s. Getting back under 130 s restores a third way in.

### F5 - Wave bottleneck, quantified

- Capacity = 3600 / (r x T) merges per hour, r = suite runs per merge, T =
  hold time. Measured r = 2.03 (304 pytest suite runs, 150 merges). T =
  190.9 s gives 9.3 per hour; 225.7 s gives 7.9; 237.7 s gives 7.5. The
  second machine slot does not help: one suite per tree.
- N packages ready together need N x r x T of gate time: 8 packages 52
  min, 12 packages 78 min, 25 packages 162 min (at 190.9 s), however fast
  the agents work.
- GIT agrees in shape: 37 merges in the 09h hour (suite 60-75 s), 14 at 10h
  (as it passed 137 s), 8-12 per hour at 140-180 s, 4-5 at 180-185 s.
- With a named-file check per package and one whole suite per batch of K
  on an integration worktree, suites per package = (1 + Pred) / K, Pred = 1
  - (1 - e)^K. ASSUMPTION e = 5 percent of packages pass their subset and
  break the suite (to be measured in wave 1). K = 4: 64 packages per hour;
  K = 5: 77; K = 8: 113 (T = 190.9 s). 25 packages at K = 5: 19.5 min of
  gate time against 162 min; 6.6 min once the suite takes 65 s.

### F6 - A direct-affected subset is small (scratch prototype)

- A stdlib `ast` pass over the tests (first-order imports, path literals,
  one hop through test helper modules, plus tests that walk a top folder)
  maps each of 155 product files to test files. With R2 applied the subset
  for a one-file change costs: median 6.4 s; 77 percent under 30 s; 82
  percent under 60 s; 99 percent under 90 s; worst 98 s.
- By area (median): web 3.6 s, app 3.2 s, server/al 8.9 s, theorycraft 6.9
  s, scripts 12.8 s, tools 63.9 s (the loop tests). Heavy: core.py 89 s,
  http.py 87 s, bridge.py 76 s, al_loop.py 74 s.
- A full transitive closure is useless (median 139 s for a server file).
  The direct map is not sound, so the batch suite stays the authority.

### F7 - Parallel options and their measured or simulated speed-up

Ideal makespans come from RUN's per-file totals (largest-first packing);
real runs add contention and about 0.9 s start per process.

- A. Serial plus hot-spot fixes (R2, R11): 236 s to about 205 s (1.15x).
- B. Stdlib file shards (K pytest processes started by a stdlib tool): K=2
  118 s (2.0x), K=3 79 s (3.0x), K=4 59 s (4.0x), K>=5 53.8 s (4.4x, bound
  by test_al_loop.py). With R2, R11 and that file split in three: K=4 51 s,
  K=6 34 s, K=8 32 s (bound by test_math_e2e_live.py).
- C. pytest-xdist when importable. Real data: the loop gate's `-n 8 --dist
  loadfile` runs took 47.8 s median (37 runs, red included). Green runs
  only (13, 26.5-61.9 s): 48.6-61.9 s in the 10h-13h hours when green
  serial runs took 137-163 s (about 2.6x to 3.1x), but 26.5-46.5 s in the
  08h-09h hours when serial took 60-72 s (about 1.5x): the gain is mostly
  the calc and git files spread over workers. Session fixtures run once per
  worker (XD-H), so `warm_bridge` can start in up to 6 workers; xdist runs
  peaked at 0.7 to 3.6 GB commit against 1.0 GB serial. `--dist loadgroup`
  keeps marked groups on one worker (XD-D).
- UNVERIFIED: why 24 of the 37 xdist loop-gate runs were red. 23 of the 25
  red verdicts in VERD hold only a repeated third-party plugin warning
  (F8); no failing test id was recorded anywhere.

### F8 - The suite depends on whatever the interpreter auto-loads

- anyio's pytest plugin emits a pytest removal warning on every run (an
  alias that pytest 10 removes; RUN line 39-44) and pytest-asyncio prints a
  4-line deprecation notice to stderr at start. Neither is used by any test.
- Cost already paid, twice. The stderr notice broke build.ps1 on a clean
  clone under PowerShell 5.1 (ROADMAP TEST-CLEAN-CLONE). And the loop keeps
  the last 1500 characters of gate output (`tools/al_loop.py:242`) but
  stores only the first 300 of those (`tools/loop_merge.py:48`), which in
  an xdist run is the repeated warning block: all 27 round-log entries for
  a red pytest gate in the loop item files carry no failing test id (20
  show the warning lines), so lanes were sent back with nothing to fix.
- Disabling the four plugins cuts a pytest start from 0.85 s to 0.68 s
  (COLLECT) and removes both notices. `PYTEST_DISABLE_PLUGIN_AUTOLOAD` and
  `-p no:NAME` are the documented switches (PTREF, PTUSE).

### F9 - The node suite is free; routing it through the gate is not

- 230 tests in 0.43-0.58 s wall (NPM). All 34 files are node-only source
  and logic tests; none starts Electron or opens a window. `node --test`
  runs each file in its own child process, in parallel (NODE).
- GATELOG: 16 gated `npm test` runs held the gate 10 s in total and waited
  3,193 s in total (max 748 s) behind this tree's own pytest runs.
- 23 of the 34 node test files load `web/` sources (for example
  `app/test/acts.test.js:6`), so "npm test only when app/ changed" would
  miss web changes.

### F10 - Concurrency hazards if two runs of this tree overlap

- Fixed ports with real binds: 8979 (`tests/test_keepalive.py:29,343`),
  8978 (`tests/test_procs.py:27,237`) and 8977 (lines 31 and 212 of
  `tests/test_supervisor.py`). Distinct per file, so one run is safe; two
  worktrees are not. test_hot_reload already takes an OS-chosen port for
  this reason (`tests/test_hot_reload.py:509-511`).
- `free_test_port()` probes 8961 upward, closes, returns
  (`tests/tc_live_util.py:39-51`): two processes can get the same port. Used
  at `tests/test_dash_console.py:73`, `tests/test_fullstack.py:176`,
  `tests/test_math_e2e_live.py:69`.
- Time budgets scale only with gate slot holders
  (`ops/fleet_kit/fleet_test_guard.py:153-169`), not with xdist workers or
  ungated runs: test_budgets, test_fuzz call bounds, test_math_perf and
  test_soak (31.2 s together) can flake under any parallel load.
- Flake history in 26 hours: TEST-413-FLAKE (7d684fd) and FLAKY-EVAL-API
  (5e7b30e), both connection races around early error replies; TEST-FLAKE
  (cbd54d6, a live loop tick writing watched state, fixed by
  `tests/conftest.py:24-42`); TEST-FLAKE-SSE (3a74c57) and the procs race
  (f7323db), both wall-clock assumptions that fail only under a loaded
  full suite. The hand-off NOTE about the test guard tripping on
  loop_items (AL-NEXT-SESSION.txt:91-93) is stale: that path is ignored
  since cbd54d6.
- Oddity: `tests/test_keepalive.py:374` spares the literal pid 13388 in
  its cleanup; a machine-specific leftover.

### F11 - Kit defect (document only): gate crash while others queue

- Where: `ops/fleet_kit/fleet_suite_gate.py:672`,
  `any(_rec(a) and _rec(a).get("exclusive") for a in ahead)` reads each
  older ticket file twice. `_rec` returns None on a read or parse error
  (:274-279).
- Mechanism: between the two reads the ticket's owner gets its slot and
  deletes the ticket (:444-446, called from :710), or rewrites it by
  `os.replace` (:495, :515; on Windows a reader can be refused mid-swap).
  The first read is a dict, the second None: AttributeError.
- Effect: uncaught (main handles only GateRefused, :1533-1558), so the gate
  exits 1 with a traceback, writes no durations row and never runs the
  suite. Exit 1 is also "tests failed": VERD holds a red verdict for
  lane-1 at 2026-11-17 13:20:33 whose detail is this traceback, at the
  second two older waiters of this tree took their slots. The hand-off
  reports one crash (AL-NEXT-SESSION.txt:41-46), possibly the same event.
- Exposure: every waiter runs that line once per second (:201) for each
  ticket ahead, so it rises with queue depth, the exact shape of a wave.
- The same file already uses the safe single read (`_rec(...) or {}`) at
  :568, :594, :753, :770. For MAIN: read once at :672. Not edited here
  (FLEET item 11).

### F12 - Kit observation: "one suite per tree" leaks through the lane

- GATELOG has 16 pairs of this tree's runs that overlap; every pair
  started within 1.5 s of each other and one of the two holds the lane
  slot. Likely mechanism (not reproduced): two waiters poll in the same
  second, both see no same-tree holder (:648-649), then one takes a regular
  slot (:681) and the other the lane (:686); the check and the take are
  not atomic. With F10's fixed ports this can fail tests for no code
  reason. For MAIN, with F11.

## Recommendations

R1. Wave gate policy: named-file subset per package, one whole suite per
merge batch.
- Action: add `tools/test_select.py` (stdlib): from `git diff --name-only`
  against the wave base it prints the test files to run (direct map of F6,
  an always-run hygiene list, any changed or new test file, unknown path =
  the whole area); packages run that list file-named in their own worktree;
  a merge agent merges K = 4 to 5 packages on an integration worktree, runs
  the whole suite once through the gate, records the verdict by git tree
  id as the loop does, then main fast-forwards. On red: run the failing
  files on each package tip, back the culprit out, one more suite.
  `npm test --prefix app` runs ungated every time (0.45 s).
- Impact: H. Gate ceiling 7.5-9.3 to about 64-77 packages per hour; a
  25-package wave needs 20 min of gate time, not 162.
- Effort: M. Risk: a subset misses a cross-module break (the batch suite
  catches it; cost one extra suite); e is unmeasured.
- ToS check: touches no floor rule; the static floor scan, the overlay
  smoke static part and the budget tests stay in the always-run list, so
  the floor guards run for every package.
- Depends on: R4 for overlapping runs; an adjudicator ruling (Open
  question 2); R2 keeps the always-run list cheap.
- Files likely touched: tools/test_select.py (new), its test,
  tools/loop_prompts.py, .claude/commands/done.md, CLAUDE.md Gates.
- Acceptance test: for 20 past merge commits the selected files include
  every test file that commit changed; median selection run under 30 s; a
  dry wave of 8 packages lands with at most 3 whole-suite gate rows.
- ZERO-CLICK: the tool reads the diff itself; no flag, no prompt.

R2. Memoise the static floor scan.
- Action: in `tests/test_floor_static.py` cache per-file regex hits keyed
  by (path, size, mtime_ns), so only new or changed files are re-scanned.
- Impact: M. 28.4 s to about 2.7 s (-10.9 percent of the suite) and the
  floor scan becomes cheap enough for every package check.
- Effort: S. Risk: a wrong cache key hides a planted call.
- ToS check: this file is the floor's static guard (no input, no memory,
  no capture, clipboard only in the hotkey handler). All 29 plants, the 3
  mutation tests and the live-tree scan stay; nothing is skipped.
- Depends on: nothing. Files likely touched: tests/test_floor_static.py.
- Acceptance test: still 35 test ids; file under 4 s; deleting one BANNED
  pattern makes its plant test fail; a plant written with the same size
  and a new mtime is still caught.
- ZERO-CLICK: runs in the suite.

R3. Run the whole suite in parallel.
- Action: give the session gate, done.md and build.ps1 the accelerator the
  loop gate already has: xdist when importable, serial otherwise. Use `-n
  4` (4.0x ideal; 8 workers save 5 s more until R8) and `--dist loadgroup`
  with groups for the calc files and the three fixed-port files; run the
  timing files (F10, 31 s) after the parallel phase. If the plugin is
  ruled out: option B, a stdlib shard tool with the same pins.
- Impact: H. 237 s to about 60-80 s; the suite regains lane eligibility
  (under 130 s) and stays under the 600 s tool ceiling when queued.
- Effort: S for xdist (code exists), M for the shard tool. Risk:
  parallel-only flakes; machines without xdist stay serial.
- ToS check: no floor rule touched; bounded workers at below-normal
  priority keep to the operator order that heavy work must not disturb
  play, and nothing reads the game process to decide.
- Depends on: R4, R6; Open question 1.
- Files likely touched: tools/al_loop.py (share the helper), a small
  tools/ runner, scripts/build.ps1, .claude/commands/done.md, test files
  for group marks.
- Acceptance test: 10 consecutive parallel whole runs green on a quiet
  tree; median hold under 75 s; one command spelling in GATELOG; a run
  with xdist hidden still passes serially.
- ZERO-CLICK: the gate command picks the mode itself.

R4. Make overlapping runs safe.
- Action: a port lease: `free_test_port()` takes the first port in
  8961-8979 for which it can lock a per-port lock file under the sidecar
  Temp and bind, and holds the lock for the test's life; the three
  supervisor tests use it instead of constants (the supervisor needs a
  known port, and AUDIT-P8-LOW P8-4 will refuse ports outside the block);
  in-process servers keep port 0. Mark the timing-sensitive tests `timing`
  and keep them out of ungated subsets.
- Impact: M (prerequisite of R1 and R3; removes a flake source).
- Effort: S. Risk: more than 19 concurrent leases wait for a port.
- ToS check: binds stay on 127.0.0.1 (LAN stays off) and inside the
  assigned block; `server/al/ports.py` is untouched.
- Depends on: nothing. Files likely touched: tests/tc_live_util.py,
  tests/test_keepalive.py, tests/test_procs.py, tests/test_supervisor.py.
- Acceptance test: those files run twice at once from two worktrees, 5
  rounds, all green.
- ZERO-CLICK: test-only.

R5. Slow-test budget and hang guard in conftest.
- Action: in `tests/conftest.py` fail a test whose call exceeds its
  ceiling (unmarked 1.5 s, slow 15 s; scaled by the kit load factor and
  doubled under parallel workers); on a full run fail the session when the
  sum of test time passes a suite ceiling (start 260 s, ratchet to 215 s
  after R2 and R11, then 200 s); print the five worst offenders. Add
  `faulthandler_timeout = 120` and `faulthandler_exit_on_timeout = true`
  to pytest.ini (core pytest, the exit option since 9.0.0: PTCL, PTREF,
  PTFAIL), so a hung test ends in 2 minutes with tracebacks.
- Impact: M. A 5x growth in a day cannot recur unnoticed; a hang no longer
  holds a gate slot until a timeout.
- Effort: S. Risk: false reds under load (hence the scaling); the exit
  option needs pytest 9.0 or newer (README names no minimum today).
- ToS check: no floor rule touched; it complements the overlay budget rule
  enforced by `tests/test_budgets.py`.
- Depends on: R2 first, or the suite ceiling trips at once.
- Files likely touched: tests/conftest.py, pytest.ini, a small test of the
  hook, README (pytest minimum).
- Acceptance test: a planted 2 s unmarked test fails with the budget
  message; a planted 130 s sleep ends the run near 120 s with a traceback.
- ZERO-CLICK: enforced in every run.

R6. Pin the plugin set.
- Action: `addopts = -p no:cacheprovider -p no:anyio -p no:asyncio` (and
  `-p no:timeout`; xdist stays only if R3 adopts it), or set
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` in the gate callers and name xdist
  with `-p`. In the loop, keep the end of the gate output (the failed test
  ids and the count line), not the start of its tail.
- Impact: M. Removes the two notices (F8), gives failure records their
  content back, removes the pytest 10 break, 0.17 s per pytest start.
- Effort: S. Risk: a `-p no:` for an absent plugin is a no-op.
- ToS check: no floor rule touched.
- Depends on: nothing. Files likely touched: pytest.ini, tools/al_loop.py,
  tools/loop_merge.py.
- Acceptance test: a run prints no warnings summary and nothing on stderr;
  `--trace-config` lists no anyio or asyncio plugin; a red gate verdict
  names the failing test.
- ZERO-CLICK: config only.

R7. One gate spelling, and gate crashes are not test failures.
- Action: one helper builds the gate command for done.md, build.ps1 and
  the loop; AL's callers treat gate output containing a kit traceback as
  infrastructure and retry once instead of recording a red verdict.
- Impact: M. One lane and memory history; F11 stops producing false reds.
- Effort: S. Risk: a retry could mask a new kit bug (log every retry).
- ToS check: no floor rule touched; the kit stays unedited (FLEET item 11).
- Depends on: R3 for the final spelling. Files likely touched:
  tools/al_loop.py, scripts/build.ps1, .claude/commands/done.md.
- Acceptance test: a fake gate that prints the :672 traceback and exits 1
  yields one retry and no cached red verdict.
- ZERO-CLICK: automatic.

R8. Split and stub the loop tests.
- Action: split tests/test_al_loop.py (2783 lines, 53.8 s) into three
  files by theme, and give the 77 tick tests that do not test git a stub
  git runner through the existing Deps injection; build `git_world` from a
  session-scoped template copy.
- Impact: M. Unlocks more than 4 workers (bound 53.8 s to 31.7 s) and cuts
  serial time by up to about 30 s.
- Effort: M. Risk: a stub hides a real-git regression (keep the 25
  git_world tests on real git).
- ToS check: no floor rule touched (dev loop tooling only).
- Depends on: nothing. Files likely touched: tests/test_al_loop*.py,
  tests/al_loopkit.py.
- Acceptance test: same test count; PROBE shows under 700 git spawns for
  the three files; each new file under 20 s.
- ZERO-CLICK: test-only.

R9. Tier the live calc tests.
- Action: mark them `calc`; per-package checks include them only when the
  diff touches server/al/theorycraft, config/tc_pins.json or their tests;
  the batch suite always runs them.
- Impact: M (64 s out of most package checks). Effort: S.
- Risk: a core change that breaks the calc leg shows one batch later.
- ToS check: no floor rule touched; the calc stays an unmodified, pinned
  subprocess (decisions 0018, 0022) and its budgets stay as in 0028.
- Depends on: R1. Files likely touched: the seven test files, R1's tool.
- Acceptance test: `-m calc` selects the live tests only (about 64 s).
- ZERO-CLICK: selection is automatic.

R10. Send MAIN the two gate findings.
- Action: when a delivery path exists, one note with F11 and F12 (the
  hand-off item, now with line numbers, mechanism and evidence).
- Impact: M across every tree. Effort: S. Risk: none.
- ToS check: no floor rule touched; the note carries no path, id or email.
- Depends on: an outbound note path (none is configured, see the hand-off).
- Files likely touched: none here. Acceptance test: MAIN acknowledges; a
  later kit reads the ticket once at that line.
- ZERO-CLICK: sent by the loop's inbox path, under the 12 per day cap.

R11. Small timer fixes.
- Action: supervisor constants in the keepalive end-to-end test 0.5 /
  0.5,1,2 to 0.1 / 0.1,0.2,0.4 with a 0.2 s heartbeat (-4 s); pass a 0.05 s
  poll at test_audit_pass5.py:73,107 and test_cover_gaps.py:249 (-1.4 s);
  `AL_FUZZ_S=0.1` in per-package checks only (-6 s there); mark
  tests/test_budgets.py:52 slow; drop the pid literal (F10). Sleeps to
  events: the fixed 0.5 s settles at `tests/test_procs.py:196` become a
  poll for the awaited state with a deadline; the keepalive supervisor
  takes its timings as flags already, so no fake clock is needed there.
  The two 3.0 s CPU windows in test_budgets measure real time and stay.
- Impact: L (about 6 s per whole suite, 6 s per package check).
- Effort: S. Risk: shorter backoff makes the restart test more load
  sensitive (keep its 30 s deadlines).
- ToS check: no floor rule touched; the CPU budget tests keep their 3 s
  windows, because the overlay and core budgets are floor-adjacent.
- Depends on: nothing. Files likely touched: the test files named.
- Acceptance test: the files pass 20 loops under a CPU burner.
- ZERO-CLICK: test-only.

R12. Shared server fixture.
- Action: one `al_server` factory in conftest (core, serve on port 0,
  0.01 s poll, stop and close) replacing the copies (`serve_forever`
  appears in 28 test files, verifier count 2026-11-18).
- Impact: L for speed (about 4 s of teardown), M for upkeep.
- Effort: M. Risk: a behaviour difference in one copy.
- ToS check: binds 127.0.0.1 with the per-start token as today.
- Depends on: nothing. Files likely touched: tests/conftest.py and those
  test files.
- Acceptance test: same test ids pass; `serve_forever` appears in at most
  3 test files.
- ZERO-CLICK: test-only.

## Cut or merge

- Merge: the PowerShell 5.1 ParseFile check exists in four files.
  `tests/test_supervisor.py:224-227` covers every script; delete the six
  repeats at `tests/test_procs.py:81-84`, `tests/test_autostart.py:134-136`
  and `tests/test_run_detach.py:52-54` (-6 tests, -0.5 s, -6 PowerShell
  starts).
- Merge: helpers copied across tests (`gen` 11 files, `scene` 9, `_build`
  8, `_core` 7, `srv` 6, `_wait` 6, `_isolated_git` 5) into conftest or one
  helper module; the code-health audit left them
  (docs/audit/code-health-2026-11-17.md:73-76). See R12.
- Do not merge for speed: the 17 `test_audit_*` files cost 4.9 s in total.
  Re-homing them by subject is a structure question, not a speed one.
  Duplicated coverage: no test function name repeats across the 17 files
  (verifier grep), and each pass imports a different module mix (for
  example `tests/test_audit_pass6.py` trade / upgrade, `test_audit_pass8.py`
  mapladder), so no merge or parametrize candidate was found there.
- Cut: 21 `slow` markers on tests under 1.5 s; the stale hand-off NOTE
  (AL-NEXT-SESSION.txt:91-93); gated `npm test` runs (F9).

## Rejected

- Throttling or pausing test runs by probing the game process, its FPS or
  its frame times: outside the floor (no process-list check of the game,
  decision 0029; no present tracing, decision 0006). Inside the floor:
  below-normal priority and a fixed worker cap.
- Dropping the floor scan, the overlay smoke static checks or the budget
  tests from package checks to save time: they are the floor's guards
  (CLAUDE.md names tests/test_budgets.py and the overlay smoke test).
- Running the live overlay smoke (AL_OVERLAY_SMOKE=1) inside waves: it
  opens the overlay window while the operator plays.
- Hiding a whole-suite pytest from the claims hook inside a script,
  raising the machine slot count from this tree, or patching the kit gate
  at :672 locally: against FLEET items 16 and 11; slots are MAIN's ruling.
- pytest-testmon or any coverage-based selector: two more dependencies
  against decision 0002; the stdlib map of F6 is enough with a batch suite.
- pytest-rerunfailures: hides flakes; the tree's practice is a named root
  cause (ROADMAP FLAKY-EVAL-API).
- Deleting the loop tooling tests (69.5 s) because the loop is paused: the
  loop is ARMED in CLAUDE.md and HALT is temporary; tier them (R1).
- Fewer reloads in the calc memory test (11.2 s): its numbers are settled
  in decision 0028 and its reverses-if is not met.

## Open questions

1. May the session gate, done.md and build.ps1 use pytest-xdist when it is
   importable, as the loop gate does (option C), or must parallelism be
   the stdlib shard tool (option B)? Decision 0002's wording allows an
   optional guarded extra. Needs an adjudicator ruling, then a decision
   file.
2. Is a file-named run of a package's selected tests outside the gate
   within FLEET item 16c? The kit hook says yes (it gates only runs that
   name no file) and the loop prompt already tells lanes to do it. Needs
   an adjudicator ruling recorded as a decision, because the CLAUDE.md
   Gates text changes; a cap (for example 90 s and no `timing` tests) would
   keep the intent.
3. The escape rate e of package subsets (F5 assumes 5 percent). Only wave
   1 can measure it; record red batch suites per batch.
4. Why the loop's xdist runs were red 24 times in 37. Unknown until R6
   restores the failure records and R3's 10-run check is done.

## Verification

Independent verifier, 2026-11-18. The whole suite was not re-run (brief);
RUN was checked from its raw files and one file was re-timed.

Checked:

- Numbers (about 45): RUN totals (2316 passed, 3 skipped, 237.17 s in
  suite_raw.txt); F1 recomputed from junit.xml (2319 cases, 235.8 s, 157
  files, the top-10 per-file list, top 5 / 10 / 23 shares, median 1.0 ms,
  the 10 ms / 0.1 s / 1 s / 5 s bands, the audit family 17 files / 146
  tests / 4.9 s); GATELOG recomputed from the kit's durations.jsonl (348
  rows, 10.25 h hold, 9.02 h wait, 76.4 percent share, 29 runs of 10 other
  trees, 18 spellings, serial 267 runs / 221 green / 45 red / 1 killed,
  wait median 30 s / p90 217 s / max 785 s, last-30 green median 190.9 s,
  the hourly growth series, 10 runs over 600 s, 16 same-tree overlap pairs
  all with a lane holder); F5 capacity and batch arithmetic recomputed
  (9.3 / 7.9 / 7.5 per hour; K = 4 / 5 / 8 gives 64 / 77 / 113; 19.5 and
  6.6 min); GIT merges (150); PROBE summary (431 passed, 1 skipped, 128.9
  s); VERD (25 red verdicts, 23 hold only the anyio warning block, the
  lane-1 13:20:33 verdict carries the :672 traceback); node 34 files, 23
  load `web/`; copied-helper counts (gen 11 ... _isolated_git 5).
- Re-timed: tests/test_floor_static.py alone, 35 passed in 29.5 s at
  below-normal priority (F2 says 28.4 s); individual plants 0.89-0.94 s.
- Code citations (about 40 opened): pytest.ini, conftest markers and
  warm_bridge, the gate (:43-45, :46-53, :134-136, :175, :179, :192, :201,
  :274-279, :444-446, :495, :515, :568, :594, :648-654, :672, :681, :686,
  :710, :753, :770, :1154-1163, :1363-1373, :1432-1434, main's handler),
  the claims hook's whole-suite test, al_loop.py :242 and :268-304,
  loop_merge.py :48, loop_prompts.py :20-29, done.md :26-28, gates.txt,
  build.ps1 :165-172 and :185, decision 0002 :14-16, al_loopkit.py
  :144-159, the fixed test ports, free_test_port, the guard's load factor,
  the three 0.5 s server polls, test_keepalive.py:374, test_fuzz.py:35,
  test_procs.py:196, the four PowerShell parse tests, the hand-off lines,
  ROADMAP TEST-CLEAN-CLONE and AUDIT-P8-LOW P8-4. All hold.
- Web (8 sources re-fetched 2026-11-18): PyPI versions and the pytest
  9.2.0 date; the changelog places `faulthandler_exit_on_timeout` in
  9.0.0; the reference lists it and `PYTEST_DISABLE_PLUGIN_AUTOLOAD`;
  xdist docs show session fixtures run per worker unless made to run once
  and list `loadgroup`; node docs say each test file runs in its own child
  process, bounded by `--test-concurrency`.
- ToS floor: all 12 recommendations re-read against every floor rule; none
  reads the game process, sends input, captures the screen or calls a web
  endpoint; nothing moved to Rejected. Settled decisions: none contradicted;
  the xdist question stays open against decision 0002, not reversed.
- Brief coverage: every point present; added the audit-file duplication
  check and the sleeps-to-events note (both were thin).

Corrected: GIT commit count 355 to 354; merges per hour 38 / 16 to 37 /
14; the xdist speed-up split into green-only runs (2.6x-3.1x at 137-163 s
serial, about 1.5x at 60-72 s), so R3's target is 60-80 s, not 60-70 s;
the 5x growth now names the calc component's share; R12's file count 25
to 28; pytest-asyncio and anyio noted as not the latest; the six serial
command spellings decoded and listed (F4).

UNVERIFIED: F12's race mechanism (inferred from timing, not reproduced);
the escape rate e (assumed 5 percent); the cause of the red xdist runs;
F6's subset timings (scratch prototype, not re-run); PROBE's per-cause
splits (git, sleep, thread waits) beyond its summary line.
