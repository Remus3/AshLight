# 0060 - Wave gate policy: named-file subset per package, one whole suite per merge batch

Date: 2026-11-19. Source: ruling Q-17 (docs/plan, ultraplan rulings,
decision 0078), unit F-065, package TEST-WAVE-GATE-POLICY; execution
model decision 0077; test selection tool tools/test_select.py
(TEST-SELECT); FLEET item 16c (suite gate).

## Decision

1. A package agent (a session wave builder) runs only the test files
   `python tools/test_select.py` prints for its diff: the ungated list
   file-named, outside the suite gate, and the gated list file-named,
   THROUGH the suite gate (`fleet_suite_gate.py run --owner <id> --`).
2. The ungated list holds no timing test and is capped at about 90 s
   by the tool's static estimate; a timing or budget test, or a subset
   over the cap, goes into the gated list.
3. main moves only after one whole green suite through the suite gate
   per merge batch (the integrator's batch run, or the /done local gate
   for a session's own batch).
4. A headless lane runs its touched tests and the ungated list the tool
   prints; it never runs the whole suite and never calls the suite gate.
   The loop's authoritative gates (ops/loop/gates.txt, whole suite
   included) run once on the finished tree, as before. The lane prompt
   (tools/loop_prompts.py GATES) carries this rule.
5. The /done ritual (.claude/commands/done.md section 1) names the batch
   rule next to its suite-gate command.

## Alternatives

- Ungated subsets without a cap. Rejected: timing tests flake under
  load when several package agents run beside a gated suite.
- The whole suite per package. Rejected: about 200 s per package per
  wave through a machine-wide gate with two slots; a wave of many
  packages queues for most of its run time.

## Why

The kit hook already gates only test runs that name no file, and the
loop prompt already sends producers to targeted tests with the loop
running the authoritative gates. The 90 s cap and the gated timing list
protect against timing flakes under contention. The whole suite per
merge batch keeps the commit gate: the direct map in test_select.py is
not sound, so the batch suite stays the authority and catches what a
subset misses.

## Reverses if

Subset runs cause machine contention or missed regressions, or MAIN's
kit changes item 16c to forbid ungated file-named runs.

## Amendment 2026-11-21 (TEST-SUITE-HOLD-75, adjudicator)

- Target: the gated whole-suite hold target is a 120 s gated median
  (was 75 s); the soak bound (TEST-SUITE-SOAK) is a median under 125 s.
- Workers: phase 1 runs with min(12, CPUs - 4) workers, never under 2;
  phase 2 (the `timing` tests) stays serial.
- Evidence: TEST-SUITE-HOLD-75, third addendum of
  docs/research/0049-test-suite-speed.md: 3 green gated runs at 12
  workers held 117.9, 118.8 and 118.7 s; phase 2 is a fixed 37 to 39 s;
  the one-worker calc group needs 52.7 s on an almost idle box.
- Why 75 s is unreachable: a 75 s hold leaves phase 1 about 37 s, but
  loadgroup keeps the calc group on one worker by design (shared warm
  bridge) and that group alone needs 52.7 s, so no worker count reaches
  75 s on this suite. The target is a suite performance budget, not a
  floor.
- Alternatives: keep 75 s and defer TEST-SUITE-SOAK until the calc group
  is split. Rejected: it blocks the soak proof on a row not yet planned
  while the 120 s gate is already measured green.
- Reverses if: a soak median exceeds 125 s, or a calc group split makes
  under 90 s demonstrable (then tighten).

## Amendment 2026-11-22 (GATE-HOLD, adjudicator)

- Reverse condition of TEST-SUITE-HOLD-75 met: 14 consecutive green
  gated holds since 2026-11-21 20:26 (cmd a9a73e2a48a6e29b, 16 CPUs,
  12 workers, about 5258 tests) have a median of 139.0 s (last 8:
  137.6 s), against the 125 s soak bound (research 0063).
- Interim bound: gated median 145 s, soak bound 150 s. Target: 120 s
  median stays the standing target.
- Recovery: packages TEST-FUZZ-PARALLEL, TEST-LOOP-WINDOW-5S,
  TEST-LUAJIT-RELOADS-12, then TEST-CALC-GROUP-SPLIT, then
  TEST-PROBE-XDIST-2 (research 0063 section 5); a 5-run gated soak
  after the first three and after the split.
- Why: the suite grew 10.5 percent but the hold about 18.5 percent
  (117.3 to 139.0 s); the cost sits in fixed timing windows and the
  one-worker calc group, not in the test count, so it can be fixed. The
  145 s bound sits above the 139 s median; the 155.7 s outlier is a
  single run.
- Alternatives: packages with no interim bound; a permanent 140 s
  target; waiting for a formal soak. Rejected as in research 0063
  section 6.
- Reverses if: a soak median after the packages is at or under 125 s
  (restore the 120 s bound), the split demonstrates under 90 s
  (tighten), or a soak median exceeds 145 s (regression: bisect, do
  not move the number).

## Note 2026-11-24 (GATE-HOLD-BISECT soak record)

- Soak: six exclusive runs of python tools/suite_run.py through the
  suite gate on main eaa74d7 (wave 53 merged), 16 CPUs, 12 workers,
  5904 tests. Pytest-reported phase sums 146.5, 138.5 and 140.8 s;
  then gate-child wall times 140.1, 142.5 and 139.3 s (median 140.1 s).
  The 145 s interim bound holds without a code change, so nothing in
  this decision moves. The 125 s restore condition is not met.
- Where the time goes: phase 1 is throughput-bound, about 950
  worker-seconds over 12 workers (each busy about 78 s, ending 81 to
  84 s), plus a 3 s start. Phase 2 is 47 to 50 s of serial calc and
  budget calls. The one tail in phase 1 is
  tests/test_shots.py::test_real_render_from_a_real_demo_core (about
  24 s). As a single test late in file order it starts at 63 to 66 s
  and ends 6 to 8 s after every other worker, in all six runs.
- Finding: the pinned pytest 9.2.0 with pytest-xdist 3.8.0 ignores
  xdist_group. Pytest 9 builds nodeid from Node._id, and xdist 3.8
  still writes item._nodeid, so no "@group" suffix reaches the
  scheduler. A minimal repro with 8 tests in one group on 4 workers
  spread them over all 4 workers. In the soaks the calc-a, calc-b and
  supervisor groups also spread across workers. --dist loadgroup
  therefore runs as plain load: the calc group split and the
  supervisor group are not in force. A test-side fix (an xdist_group
  on test_shots to start the render in the first wave) measured no
  effect for this reason and was dropped.
- Next: a row to restore grouping (pin a pytest / xdist pair that
  honours xdist_group, or set the group in tests/conftest.py), then
  re-soak. Re-pinning the calc groups may lengthen phase 1 (research
  0063). Starting the render first is worth about 6 s of phase 1 once
  grouping or ordering works.
- Reverses if: a soak median exceeds 145 s (bisect, do not move the
  number), or grouping is restored and the soak median changes by more
  than 5 s (record the new figures here).

## Amendment 2026-11-24 (TEST-XDIST-GROUP-RESTORE)

- Cause confirmed: pytest-xdist 3.8.0 (the newest release) marks a
  grouped item under --dist loadgroup by assigning item._nodeid =
  "<nodeid>@<group>", while pytest 9.2.0 derives Node.nodeid from
  Node._id, so the worker's collection ids carried no group and
  loadgroup ran as plain load. Not the marker registration, not the
  suite_run arguments, not another conftest hook.
- Fix (test side, pins unchanged): tests/conftest.py wraps
  pytest_collection_finish and, only for an item holding an
  xdist-written _nodeid that differs from its nodeid, puts the
  suffixed id in place (the id's own parse) while the worker sends its
  collection, then restores the plain id. The scheduler dispatches by
  index, so reports, the slow budget and nodeid-keyed tables keep the
  plain id. xdist is not imported. tests/test_xdist_group.py runs a
  child pytest on 4 workers and fails when a group splits (it failed
  before the fix with 6 grouped tests on gw0 to gw3).
- Order: tools/suite_run.py names the test_shots render in
  AL_SUITE_FIRST and tests/conftest.py moves it to the front of the
  collection, so it is dispatched in the first wave after the
  multi-test groups.
- Soak: three exclusive runs of python tools/suite_run.py through the
  suite gate on the package commit, 16 CPUs, 12 workers, 5898 passed
  plus 9 skipped in phase 1 and 21 timing tests in phase 2, all green.
  Gate-child wall 135.6, 137.7 and 136.9 s, median 136.9 s (phase 1
  80.1, 82.1, 81.3 s; phase 2 54.6, 54.7, 54.6 s). Against the
  140.1 s median of the GATE-HOLD-BISECT record, 3.2 s faster: under
  the 5 s record threshold, inside the 145 s interim bound, above the
  125 s restore condition, so no bound moves.
- Alternatives: pin an older pytest that still honours item._nodeid.
  Rejected: it moves a hash-pinned test dependency back across a major
  version and there is no newer xdist release with a fix; the
  conftest wrapper is smaller and untouched by a future fixed xdist
  (it acts only when the ids differ).
- Reverses if: pytest-xdist ships a release that sets the group
  through Node._id (then drop the wrapper and keep the test), pytest
  stops parsing a "@group" id through NodeId.parse, a soak median
  exceeds 145 s (bisect, do not move the number), or a soak median
  reaches 125 s or under (restore the 120 s bound).

## Amendment 2026-11-24 (GATE-HOLD-D dropped)

- Soak: three exclusive runs of python tools/suite_run.py through the
  suite gate on main with TEST-XDIST-GROUP-RESTORE merged (wave 57),
  all green: gate hold 139.7, 136.8 and 134.5 s, median 136.8 s
  (phase 1 about 84 s, phase 2 about 55 s, 21 timing tests).
- History of exclusive soak medians: 146 s (wave 52), 140.1 s
  (GATE-HOLD-BISECT), 136.9 s (TEST-XDIST-GROUP-RESTORE), 136.8 s
  (wave 57). Inside the 145 s interim bound, above the 125 s restore
  condition, so no bound moves.
- Decision: GATE-HOLD-D is dropped (adjudicator ruling 2026-11-24).
  Its only work, kept branch worktree-w52-GATE-HOLD-D at tip
  4f493017b82ad93cce73aa799843cc60b7fb5e9a (a shared session git
  template in tests/al_loopkit.py and tests/test_al_loop_gate_cache.py,
  measured at about 0.5 s), cannot close the 12 s gap to 125 s and is
  not merged; the gain sits inside the about 5 s soak spread. The
  interim bound stays at a 145 s median (soak 150 s) and the target
  stays 120 s. Follow-up row: TEST-SERIAL-PHASE-CUT (the serial timing
  phase, about 55 s).
- Alternatives: re-defer it (rejected: a package that cannot meet its
  accept line stays open for ever); cherry-pick 4f49301 alone
  (rejected: 0.5 s cannot be measured against the soak spread and
  costs a gated run).
- Reverses if: a later soak shows the shared git template alone is
  worth 5 s or more (then cherry-pick the recorded sha), a soak median
  after a later package is at or under 125 s (restore 120 s), a soak
  median exceeds 145 s (bisect, do not move the number), or the
  operator rules the interim bound tightened or the 120 s target
  dropped.
