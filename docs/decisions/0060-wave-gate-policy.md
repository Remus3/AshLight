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
