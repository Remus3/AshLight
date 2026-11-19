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
