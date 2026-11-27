# Public flip record, 2026-11-27

Operator order this session (2026-11-27): "public flip". Plan:
docs/plan/04-go-public.md GP-12 and GP-13. Every value below was read
back after the act, never assumed from the command.

## CI made green (gate 3, gate 12)

The ci job `test` had been red since 2026-11-21. Commit 307d5da fixed
each root cause (see its message). Read back on 307d5da (origin/main):

- ci run 46079475413 attempt 1: conclusion success (job test success).
- ci run 46079475413 attempt 2 (full `gh run rerun`): conclusion
  success (test success, test-newest success).
- fleet-identity-guard run 46079475566: success.

Gate 12 counts two consecutive green ci runs on the same main commit via
a full `gh run rerun` (plan 04 gate 12, decision 0080).

## Flip gates (GP-12), read back on 307d5da

1. P0 findings: tests/test_http_security.py, tests/test_tc_code.py,
   tests/test_no_discovery.py: 69 passed.
2. GP-01: fleet_identity check --history --by-class main: 0 in all 9
   classes over 2341 commits. Leak sweep --tree rc 0 (ARMED needles=44);
   history sweep over origin/main rc 0. The `--all` identity check and
   `--history` sweep flag only GitHub's own Dependabot branches
   (refs/remotes/origin/dependabot/*, bot author and Signed-off-by), which
   are not on main and are never merged (FLEET item 17).
3. Both workflows success on 307d5da (above).
4. GP-06, GP-07 (folded into PUB-README-PLAYERS), GP-10, GP-11 landed
   (docs/roadmap/archive/2026-11.md).
5. OA-2 skipped in writing (hand-off line `OA-2 SKIPPED IN WRITING`).
6. `git ls-files` has no FUNDING file; README images are
   assets/brand/readme-hero-light.png and docs/shots/*.png. Gate 6
   amended 2026-11-27 by adjudicator ruling to allow docs/shots/* own-UI
   demo renders (plan 04 GP-12 gate 6 text).

## Flip

- `gh repo edit <repo> --visibility public
  --accept-visibility-change-consequences`: rc 0.
- `gh repo view --json visibility`: PUBLIC.
- Anonymous `git ls-remote --heads --tags`: refs/heads/main and
  refs/heads/dependabot/npm_and_yarn/app/npm-all-fc2ad58da4 only.

## GP-13 settings, read back

- vulnerability-alerts: HTTP 204. automated-security-fixes: true.
  private-vulnerability-reporting: true.
- security_and_analysis (secret scanning, push protection, Dependabot
  security updates): enabled,enabled,enabled.
- Rulesets: main-protect (active, bypass_actors []), main-checks
  (active, bypass_actors [RepositoryRole 5, always]); required checks
  fleet-identity-guard and test, integration_id 15368 (confirmed by the
  check-runs read-back of main).
- rules/branches/main: deletion,non_fast_forward,required_status_checks.
- actions/permissions: true,all,true; workflow permissions: read,false.
- .github/dependabot.yml on main; open Dependabot pull requests: none;
  community health: 100.
- Fresh push after the rulesets: the commit carrying this record (see
  the hand-off for its sha and the main == origin/main read-back).

## Follow-ups

- test-newest (continue-on-error) red on attempt 1 with a11y.mjs "no
  DevTools endpoint": row TEST-A11Y-NEWEST-DEVTOOLS.
- Rows waiting on the flip (GP-14, GP-15, GP-16 and the release rows)
  are now unblocked for wave planning.
