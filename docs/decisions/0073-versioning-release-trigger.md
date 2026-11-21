# 0073 - Versioning and release trigger

Date: 2026-11-21. Package: REL-PUBLISH-GATES (wave 21; units F-074,
DEP-12). Source: docs/plan/05-deployment.md (decision D4, section
"Release procedure", "Who triggers what", package DEP-12), decisions
0046 (guarded push, release tags), 0062 (changelog), 0064 (release
artifact) and 0065 (update policy); adjudicator ruling Q1 of 2026-11-21
(plan commit d1e036c).

## Decision

1. SemVer 0.y.z; the release tag is `v` + VERSION (tools/rel_version.py
   tag_for). A release starts only from a REL-PREP milestone row or an
   explicit version request, and is published only on the operator's
   typed phrase `release X.Y.Z`, never by a lane, a loop tick or an inbox
   responder. A MAIN ORDER carrying the phrase counts (FLEET item 6) and
   is likewise acted on only in an interactive session. CI rebuilds and
   publishes the GitHub release on the tag.
2. One command publishes: `python tools/release.py publish --version
   X.Y.Z --go "release X.Y.Z"` (module tools/rel_publish.py, loaded by
   the DEP-03 dispatcher). It runs every gate, names every refusal at
   once, and a refusal changes nothing (no tag, no push, no file). The
   gates: the phrase equals `release ` + the version; no headless marker
   (the kit progress-owner variable FLEET_PROGRESS_OWNER, or a lane lock
   naming this worktree); a remote named origin exists and names the
   repository of config/public_repo.json ("no remote" otherwise); a
   stage report (stage.json in `<sidecar>/Build/release/<version>/`)
   with verdict PASS, the asked version, HEAD as its commit, at most 24 h
   old and a sums_sha256; a clean tree; the notes file without its STUB
   mark and a current CHANGELOG.md; the tag new locally and on origin;
   origin's main equal to HEAD; HEAD's committer an operator identity
   (local `fleet.operatorIdent`); immutable releases confirmed through
   `gh` (`repos/<repo>/immutable-releases` reads enabled), else by the
   dated `immutable_confirmed` value in config/release.json that the
   operator act records.
3. On a full pass: one annotated tag `vX.Y.Z` on the stage commit whose
   message carries `sums-sha256: <hex of the staged SHA256SUMS.txt>`,
   then one push of that one ref, `git push origin refs/tags/vX.Y.Z`,
   through `ops/fleet_kit/fleet_gitlock.py run --owner <id> --` and the
   guarded pre-push hook. Never `--tags`, `--all`, `--mirror` or a
   branch; main moves under decision 0046's push policy. A failed push
   deletes the local tag again. The result goes to publish.json beside
   the stage report; the read-back of the CI-published release lands
   with the CI release package.
4. `publish --rehearse` runs every gate, prints each one and the line
   `remote: origin (<owner/name>)` (or `remote: none`), and makes no tag
   and no push; origin is only read (one `git ls-remote`, no prompt).
5. `release.py prepush-check` (pre-push stdin lines) refuses a pushed
   `refs/tags/v*` ref without a PASS stage report of that version whose
   commit is the tag's commit, refuses a release tag delete, and passes
   every other ref untouched. Its call in .githooks/pre-push rides the
   go-public guarded-push package, not this one.
6. config/release.json holds `immutable_confirmed` (null until the
   operator act records a date) and an empty `repository` field; the
   address itself is read from config/public_repo.json when it exists
   (one source), the release.json field only as a fallback.
7. Q1 record (adjudicator 2026-11-21): the rehearsal names the configured
   remote and pushes nothing; the no-remote gate is kept and proven by
   the injected-git test (tests/test_release_gates.py). Alternatives were
   dropping the gate, removing origin temporarily, or keeping the old
   accept text (which cannot pass with origin configured). Reverses if:
   the remote is removed.

## Alternatives

- A release per merge to main. Rejected: the operator's order; a release
  is a player-facing event, and every merge would cost a stage run.
- Milestone rows that publish with no phrase (plan 05, marked option).
  Not adopted: the operator wants one typed phrase per release.
- Pushing with `--tags` or tagging inside the loop. Rejected: one
  explicit ref is the only shape decision 0046 lets leave the machine,
  and the loop never tags (static test in tests/test_release_stage.py).
- Fetching origin before the origin/main gate. Rejected: a fetch writes
  refs; one ls-remote read gives the live tip with nothing changed.
- For the no-remote gate (Q1): dropping it, removing origin for the
  rehearsal, or keeping the pre-remote accept text; see item 7.

## Why

The typed phrase, the headless refusal, the pre-push stage check and no
publish path in the loop tools together hold "a release by accident"
(plan 05 risks). Running every gate in one pass names every blocker in
one rehearsal, so the operator's one phrase is the only act left.

## Reverses if

The operator rules that milestones may publish themselves; GitHub drops
the immutable-releases setting (then the dated operator record is the
only confirmation); or the remote is removed (Q1).
