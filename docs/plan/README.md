# AshLight plan (ultraplan, 2026-11-17)

The operator ordered (2026-11-17) a deep review of AshLight and one
complete, sequenced plan that normal sessions then execute in waves. This
directory holds the plan. The research it rests on lives in
`docs/research/`.

## State: complete (2026-11-18)

Every file listed below is at HEAD with `Status: verified` (research
notes) or `Status: final` (plan sections), read back 2026-11-18. Nothing
here is redone. The plan of record is `docs/plan/packages.json`, checked
by `python tools/plan_check.py check` (396 packages, 39 waves; decision
0077); `07-execution-plan.md` is its readable form, `08-orchestration.md`
says how a session runs a wave, `09-operator-acts.md` is the one batched
operator ask. The rulings behind the plan are ledgered in decision 0078.

To change the plan: patch `packages.json` (07, How the two files are
kept), keep 07 in step, then run `python tools/plan_check.py check` and
`python -m pytest -q tests/test_plan_check.py`.

## How a session starts a wave

The operator types `continue`. The session reads `AL-NEXT-SESSION.txt`
(the `WAVE POINTER:` line, the `DEFERRED:` lines, the operator records)
and follows `08-orchestration.md` from section 1. It asks the operator
nothing: every item of 09 has a default in force.

1. The main session dispatches one start agent (08 section 1). It checks
   the ground (`git status --short` empty, branch `main`,
   `python ops/fleet_kit/fleet_checklist.py stale` exit 0), validates the
   plan (`python tools/plan_check.py check`), finds the open wave from the
   pointer and the ROADMAP rows (the open-row command of 08 section 1
   step 4; `python tools/plan_check.py wave <n>` prints the wave), reads
   the session group from `packages.json` and returns the item-13
   checklist.
2. Dispatch (08 section 2): one builder per open worktree package, each
   in its own sidecar worktree `w<n>-<ID>` with the builder prompt
   template; the main-checkout acts as one serial chain; one watcher.
3. Reviews and verification per package (08 section 5), merge batches on
   the integration worktree `w<n>-int` with one integrator commit and one
   whole suite per batch (08 sections 4 and 6), then the wave close and
   the new pointer line (08 section 7).
4. The next wave of the session group starts the same way; `/done` runs
   unprompted when no checklist row is left. A session that stops early
   resumes at the first unmerged package of the open wave.

The first wave to run is wave 1 (session 1 = waves 1 to 3).

## Work list - research notes

- [x] docs/research/0035-data-sources-ggg-api.md - B1 GGG OAuth character API, API Reference, Data Exports, developer docs
- [x] docs/research/0036-data-sources-poe-ninja.md - B1 poe.ninja PoE2 contract
- [x] docs/research/0037-data-sources-pob-repoe-tree.md - B1 PoB-PoE2 releases, repoe-fork, GGG passive tree export
- [x] docs/research/0038-features-review.md - B2 features: gaps vs player value, cut or merge
- [x] docs/research/0039-utilities-review.md - B3 utilities: gaps vs player value, cut or merge
- [x] docs/research/0040-visual-design-review.md - B4 visual design
- [x] docs/research/0041-typography-review.md - B5 typography
- [x] docs/research/0042-usability-review.md - B6 usability
- [x] docs/research/0043-glanceability-zero-click-audit.md - B7 glanceability and every remaining click or paste
- [x] docs/research/0044-accessibility-review.md - B8 accessibility
- [x] docs/research/0045-security-local-surface.md - B9 token, CSP, Host / Origin, local API surface
- [x] docs/research/0046-security-electron-supply-chain.md - B9 Electron hardening and supply chain
- [x] docs/research/0047-file-structure-review.md - B10 file structure
- [x] docs/research/0048-performance-budgets-review.md - B11 speed, RAM, FPS budgets
- [x] docs/research/0049-test-suite-speed.md - B12 test suite speed
- [x] docs/research/0050-reliability-review.md - B13 reliability
- [x] docs/research/0051-observability-review.md - B14 observability
- [x] docs/research/0052-deployment-reference-pattern.md - B15 / F reference install, build, release, update, uninstall pattern
- [x] docs/research/0053-packaging-release-options.md - B15 / F packaging and release options
- [x] docs/research/0054-competitive-poe-tools.md - B16 competitive review: PoE trade and overlay tools
- [x] docs/research/0055-competitive-companions-overlays.md - B16 competitive review: other games' companions and overlays
- [x] docs/research/0056-third-party-repo-review.md - C a reviewed third-party repo set
- [x] docs/research/0057-go-public-readiness.md - E go-public readiness
- [x] docs/research/0058-automation-watchers.md - G no-reminder automation and upstream watchers

## Work list - plan sections

- [x] docs/plan/01-open-items.md - D every open item with its unblock condition
- [x] docs/plan/02-findings.md - one consolidated ranked findings list (machine-readable source: docs/plan/findings.json)
- [x] docs/plan/03-target-design.md - target design: Play tab, tab set, overlay, type scale, colour tokens
- [x] docs/plan/04-go-public.md - E go-public plan
- [x] docs/plan/05-deployment.md - F deployment plan
- [x] docs/plan/06-automation.md - G automation plan
- [x] docs/plan/07-execution-plan.md and docs/plan/packages.json - waves and work packages
- [x] docs/plan/08-orchestration.md - orchestration script outline for the executing sessions
- [x] docs/plan/09-operator-acts.md - the one batched operator ask

## Then - landed 2026-11-18

- [x] decisions for the settled calls: 0046 (go public), 0077 (execution
  model), 0078 (rulings ledger); numbers 0047 to 0076 are reserved for
  the packages that write them (07, Reserved decision numbers);
- [x] ROADMAP rows for every package (`python tools/plan_check.py rows`;
  read back: every package id is in ROADMAP.md exactly once);
- [x] the CLAUDE.md public-repo section (decision 0046);
- [x] the pre-push flip: `.githooks/pre-push` is the guarded push (only
  `main` and `v*` release tags, `tools/push_guard.py`, the identity check
  and the leak sweep over every pushed object; no override);
- [x] `AL-NEXT-SESSION.txt` rewritten so a plain "continue" starts wave 1.

What is still open of the landing itself is carried in
`AL-NEXT-SESSION.txt` (its `DEFERRED:` lines), never here.

## Loop

The headless loop stays paused (`ops/loop/control/HALT`, operator
wind-down 2026-11-17) through waves 1 to 5, so lanes do not race the
plan's ROADMAP edits. HALT is removed only by package AUTO-21, the last
act of wave 6, after its six checks (07, HALT removal and the headless
loop; 08 section 8); no session removes it by hand. After that the loop
takes the rows `packages.json` marks `owner: loop` and the other rows 08
section 8 lists, never a row tagged BLOCKED.
