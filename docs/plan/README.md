# AshLight plan (ultraplan, 2026-11-17)

The operator ordered (2026-11-17) a deep review of AshLight and one
complete, sequenced plan that normal sessions then execute in waves. This
directory holds the plan. The research it rests on lives in
`docs/research/`.

## How to resume

A listed file is DONE when it exists at HEAD and its header carries
`Status: verified` (research notes) or `Status: final` (plan sections).
The next action is always the first listed file that is missing or not
done. Redo only missing files; never redo a done one.

The boxes below are a convenience; the file at HEAD decides.

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
- [ ] docs/plan/02-findings.md - one consolidated ranked findings list
- [ ] docs/plan/03-target-design.md - target design: Play tab, tab set, overlay, type scale, colour tokens
- [ ] docs/plan/04-go-public.md - E go-public plan
- [ ] docs/plan/05-deployment.md - F deployment plan
- [ ] docs/plan/06-automation.md - G automation plan
- [ ] docs/plan/07-execution-plan.md and docs/plan/packages.json - waves and work packages
- [ ] docs/plan/08-orchestration.md - orchestration script outline for the executing sessions
- [ ] docs/plan/09-operator-acts.md - the one batched operator ask

## Then

Once every listed file is done, the plan lands in the tree:

- decisions for every settled call (`docs/decisions/`, next free number
  0046);
- ROADMAP rows for every package;
- the CLAUDE.md public-repo section;
- the pre-push flip (`.githooks/pre-push` refuses every push today);
- `AL-NEXT-SESSION.txt` rewritten so a plain "continue" starts wave 1.

## Loop

The headless loop stays paused (`ops/loop/control/HALT`, operator
wind-down 2026-11-17) while the ultraplan runs, so lanes do not race the
plan's ROADMAP edits. The execution plan (`07-execution-plan.md`) names
the point where HALT is removed.
