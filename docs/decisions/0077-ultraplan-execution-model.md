# 0077 - Ultraplan execution model: waves in sessions, loop tail (ULTRAPLAN)

Date: 2026-11-18. Source: operator order 2026-11-17 (a deep review and one
complete, sequenced plan that normal sessions then execute in waves);
docs/plan/07-execution-plan.md with its review record and the close-out
rulings of 2026-11-18; docs/plan/08-orchestration.md; docs/plan/06
(Loop and wave interplay, The point at which HALT is removed);
docs/plan/packages.json; tools/plan_check.py; research 0047 (file
structure), 0049 (test-suite speed and merge throughput) and 0058 (loop);
rulings Q-17 and LE-166 (decision 0078).

Number: 0047 to 0076 are reserved for packages (docs/plan/07, Reserved
decision numbers; the reserved_decisions list of packages.json). A
decision written outside a package takes the next number after that
block, so this record is 0077 and the rulings ledger is 0078.

## Decision

1. Plan of record. docs/plan/packages.json (schema 1) is the plan;
   tools/plan_check.py validates it (`check`), prints a wave in merge
   order (`wave <n>`) and prints the ROADMAP rows (`rows`).
   docs/plan/07 explains the file and never repeats a package. The
   planning builder outside the tree is retired (LE-166). The plan
   changes only by a small patch of packages.json (ASCII, LF, JSON
   indent 1) that keeps each wave's merge_order, the package order, the
   sessions list and the hotspots list in step, with the matching lines
   of 07, followed by `python tools/plan_check.py check` and
   `python -m pytest -q tests/test_plan_check.py`. Where docs/plan/04,
   05 or 06 word a point differently, 07 wins.
2. Package. One unit of work for one agent, at most 90 minutes, with its
   files, tests, acceptance line and dependencies. 396 packages: 339
   session packages in waves 0 to 37, 16 loop-owned, 41 parked.
3. Wave. A set of packages that may run at the same time, each in its
   own worktree. Every dependency sits in a strictly earlier wave; inside
   a wave no two packages share a file, a new file or a serial group. A
   wave ends with main green and its rows flipped. Width: at most 12
   worktree packages (11 in wave 1; waves 4, 18, 19 and 22 carry 13 or
   14 and run a fourth merge batch) and at most 4 main-checkout acts. The
   number of waves is set by the file chains (one editor of a file a
   wave; web/index.html has 35 editors), not by the width.
4. Session. Consecutive waves that one operator `continue` runs
   hands-off: 10 sessions after the landing, each filled up to 520
   minutes and at most 5 waves. Wave 0 (PLAN-LANDING) is the planning
   session's own act and needs no `continue`. The grouping is a
   forecast: a session that stops early writes the same wave pointer and
   the next `continue` resumes at the first unmerged package of the open
   wave. The hand-off line `WAVE POINTER: wave <n> done, next wave
   <n+1>` is the claim; the ROADMAP rows decide; a `DEFERRED:` line
   carries a package into the next dispatch.
5. Gate order (ruling Q-17). Per package, in its worktree: the test
   files of its `tests` field as a file-named run, `npm test --prefix
   app` when it touches app/ or web/, and the design-reviewer pass where
   the package asks for one. Through the suite gate instead: the timing
   files and any subset over 90 s until TEST-SELECT is on main (wave 8),
   and the fixed-port files until TEST-PORT-LEASE is on main (wave 5).
   Per merge batch (4 packages in merge order, 5 in wave 1), on an
   integration worktree under the merge lock: merge the tips, the
   integrator's commit, then one whole suite through the suite gate and
   `npm test --prefix app`; on green main moves to the integration tip.
   Main never moves without a whole green suite. Wave 1 measures the
   escape rate of the subsets; above 10 percent the batch drops to 3
   until TEST-SELECT has landed. The policy text for the test selector
   is recorded by TEST-WAVE-GATE-POLICY (reserved 0060) when it lands.
6. Integrator. One integrator per wave is the only writer of ROADMAP.md,
   CLAUDE.md, AL-NEXT-SESSION.txt, the three README indexes and
   docs/design/reviews.log. A package never edits them: it returns its
   row flip, Settled bullet, index line and review line (its
   integrator_edits) and the integrator applies them as one commit per
   merge batch, after the merges and before the batch suite. A red
   Settled-list or index test of a batch suite is the integrator's
   commit to fix, never a reason to back a package out. The rows are
   landed once, in wave 0; a package only flips its row. No agent takes
   "the next number" of the decision series: a package uses the number
   reserved for it.
7. Main-checkout acts (isolation none: docs, records, the first push,
   the HALT removal) run one at a time in merge order, each committed or
   read back before the next starts, never while main is being moved.
8. Owners and the loop tail. A package is owned by `session` (its row
   carries `BLOCKED: session wave <n>`) or by `loop` (16 rows: no design
   review, no operator act, no hotspot file, nothing under web/,
   app/overlay/, app/shared/ or the loop's own code, no new decision, no
   test tied to live processes, no P0 or first-value work, no session
   package waiting on it). The headless loop takes a loop row once HALT
   is removed and the rows named in its `DEPENDS:` are done. A session
   never waits for the loop: no session package depends on a loop
   package, and the validator checks it. How the two never take the same
   row is docs/plan/08 section 8; AUTO-06 records it (reserved 0055)
   when it lands.
9. HALT removal point. `ops/loop/control/HALT` stays through the landing
   and waves 1 to 5. It is removed only by AUTO-21, the last act of wave
   6 (session 2), after AUTO-01, LOOP-HANDOFF-PREFIX, LOOP-PREFLIGHT-CMD,
   LOOP-FAILED-PARK, AUTO-02, AUTO-03, LOOP-ROWFILES-MERGE,
   LOOP-ROWFILES-WORK, LOOP-DONE-FOLD, AUTO-04, AUTO-06, LOOP-WAVE-HOLD
   and TEST-PLUGIN-PIN are on main with one whole green suite, and after
   the six checks of F-078 each read back green. A red check leaves HALT
   in place; AUTO-21 then runs again as the first act of the next wave
   and no loop-owned row is released before all six are green. The
   removal is due no later than 2026-12-04. A wave session never removes
   HALT any other way, never installs, removes or starts the scheduled
   task and never starts a tick.
10. Parked packages (wave 99). Operator-gated and externally blocked
    work is parked with its unblock condition and never blocks an open
    package. When a condition reads true the package joins the next open
    wave, never the wave in flight, by the patch of point 1.
11. Operator gates. docs/plan/09-operator-acts.md is the one batched
    ask; no open wave waits for it and every entry has a default in
    force (decision 0078). Only a session that holds the operator's own
    message records an answer, verbatim, in the hand-off.
12. Not ruled at this record (superseded 2026-11-18: both questions
    had been ruled and are applied; the note that ends this point
    says how), left as docs/plan/08 words them until
    ruled: whether the `.claude/worktrees/` fallback may be used before
    the worktree hook of decision 0012 is wired (LE-92, LE-99, LE-100)
    and whether a builder's own stop at 2 x est_min plus a whole-run
    restart is the Workflow equivalent of the kill at 3x (LE-96).
    2026-11-18 note (close-out 2): both had been ruled; the rulings
    were applied late (decision 0078; docs/plan/07, Rulings 2026-11-18
    (close-out 2)). The fallback may be taken without waiting as a
    recorded temporary deviation; it was not needed, because a probe
    of a hand-made sidecar worktree passed on 2026-11-18 and wave 1
    uses that method (docs/plan/08 section 2). The builder's stop at
    2 x est_min plus a whole-run restart at 3 x is accepted as the
    Workflow equivalent of the kill. Also ruled there: GP-09 runs
    alone and holds main to its read-back (R1); a wave may hold up
    to 16 worktree packages in batches of at most 4, each with its
    own whole suite, while a planned wave stays at 12 (R6).
    Same day, after the verification of the close-out 2: the first
    sentence of this point carries a dated 'superseded' marker, so
    that it is not read alone as the present state. Words were added
    only; no recorded word was removed.

## Alternatives

- One whole suite per package: rejected; the suite gate then allows 7.5
  to 9.3 merges an hour whatever the number of agents (research 0049
  F5), so 12 packages would hold the gate for 78 minutes.
- Fewer, wider waves: rejected; the length of the plan is set by the
  one-editor-a-wave file chains, and a wider wave only gives the
  integrator and the merger more to apply at once.
- Every package edits ROADMAP.md, CLAUDE.md and the indexes itself:
  rejected; every merge would conflict on the same lines and the
  Settled-list tests would be red in each worktree (research 0047 R1).
- One integrator commit per wave: rejected; the batch suite needs the
  Settled bullets of its own batch first.
- Keep the external builder as the source of the plan: rejected; it no
  longer reproduced the tracked files.
- Remove HALT before wave 2, as docs/plan/06 first expected: rejected;
  the loop packages form a chain of dependencies and shared loop
  modules, so wave 6 is the earliest point.
- Keep HALT through every wave: rejected; the launch gate and the
  watcher rows would stall, and the loop-owned rows would cost session
  time.
- Give the loop most of the plan: rejected; most packages are hot-file
  or design work, need a design review or an integrator edit, and the
  headless runs cap leaves about 85 runs a day for plan rows.
- An operator click per wave: rejected; the goal is the fewest
  `continue`s (FLEET item 1), and stopping after any wave already
  leaves main green.

## Why

The operator asked for a plan that sessions execute without re-planning.
Fixed waves with disjoint files let up to 12 agents build at once; the
batch gate keeps the rule that main moves only on a whole green suite
while costing about 14 minutes of gate time a wave; one writer for the
shared ledgers removes the merge conflicts the audit of the earlier
lanes found; a validator makes the plan a checked file instead of prose;
and the loop takes only rows it cannot collide on, after the checks that
prove it reads the plan's tags.

## Reverses if

- Wave 1 measures an escape rate that stays above 10 percent with the
  batch at 3 and TEST-SELECT on main (then: a whole suite per package
  for the affected lanes, and the wave times are re-estimated).
- A change the plan needs cannot be expressed in schema 1 of
  tools/plan_check.py (then: a schema change with its test, recorded
  here by a dated amendment).
- The loop and a session work the same row in practice, or the tag
  traffic on ROADMAP.md causes merge conflicts (then: HALT during waves
  until the contract is fixed).
- The six checks cannot read green by 2026-12-04 (then: the fallback of
  docs/plan/06 for the launch gate, and HALT stays).
- MAIN's kit changes FLEET item 16 c to forbid ungated file-named runs,
  or the operator orders another cadence.
