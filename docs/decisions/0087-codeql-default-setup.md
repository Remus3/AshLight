# 0087 - CodeQL default setup on (GitHub-managed, no workflow)

Status: accepted 2026-11-27 (adjudicator ruling).

## Decision

CodeQL code scanning runs as GitHub's default setup for python,
javascript-typescript and actions, query suite default, applied with
`gh api -X PATCH repos/<repo>/code-scanning/default-setup`. GitHub manages
the runs: there is no tracked CodeQL workflow, no new token scope in any
workflow, and CodeQL is not a required check on main (the required checks
stay fleet-identity-guard and test). Secret scanning non-provider patterns
and validity checks stay off; secret scanning and push protection stay on.
The intended state is recorded in ops/github/security.json and asserted by
tests/test_repo_settings_files.py. Alerts are read, fixed in the tree or
filed as ROADMAP rows; none is dismissed on GitHub without a recorded
reason.

Read back 2026-11-27: state configured, languages actions, javascript,
javascript-typescript, python, typescript (GitHub expands the two
aliases), schedule weekly; the setup run succeeded with three analyses
(actions 0 results, javascript-typescript 1, python 10). The one
non-test alert, py/redos in tools/loop_gatefail.py (the pytest summary
line pattern), is fixed in the same commit; the 10 alerts in tests/ and
app/test/ (bad-tag-filter, incomplete URL substring checks in test
assertions) are filed as a ROADMAP row, not dismissed.

## Alternatives

- A tracked codeql.yml workflow: rejected, it needs security-events: write,
  outside the workflow permission rules of CLAUDE.md (read-only token,
  watch.yml and release.yml the only exceptions).
- Leave code scanning off (docs/plan/04 "not in this plan"): rejected, the
  default setup costs no permission and no tracked file, and 5 of 7 public
  peers run it.

## Why

Free static analysis of the public tree with no change to the token or
permission floor and no new gate that could block main.

## Reverses if

Default-setup runs cost noise or minutes the operator rejects, or false
positives flood; GitHub makes default setup need a workflow permission;
custom queries or pinned CodeQL versions are needed (then one codeql.yml
with amended permission rules); a real non-provider secret leaks past the
leak sweep (then turn non-provider patterns on).
