# 0046 - Go public: guarded push, private first, public on gates

Date: 2026-11-18. Source: operator order, session brief 2026-11-18 (quoted
verbatim below; the hand-off carries the same words in the lines OPERATOR
GO Q-23 step 1 and step 4 from its next rewrite), with the 2026-11-17 item
E order (going public is ordered) as context; research 0057; plan
docs/plan/04-go-public.md (package GP-02); rulings Q-23, Q-24, Q-25 and
the close-out rulings of docs/plan/07 (LE-01).

The operator's words (session brief 2026-11-18, verbatim):

> "The operator has ordered going public. Record that as a decision
> (docs/decisions/NNNN-go-public.md: decision, alternatives, why, reverses
> if), update CLAUDE.md "Public-repo hygiene" and ROADMAP, and flip
> .githooks/pre-push from refuse-all to the normal guarded push
> (fleet_identity pre-push check stays)." ... "Before first push: verify
> every commit has only operator identity and no AI/bot trailer; leak
> sweep clean (no machine path, account id, email, sibling tree name, no
> friend name). A rewrite runs only via fleet_rewrite.py on MAIN's order -
> if needed, file the request, do not rewrite. The only operator act left
> is gh auth login if gh is not authenticated, batched into the one ask."

## Decision

1. AshLight is published on GitHub under the operator's account. This
   lifts the 2026-11-16 order that kept the repository local only.
2. Full history is published. No rewrite and no fresh root: re-read on
   2026-11-18 at HEAD cf270e5, the identity check finds 0 violations in 9
   classes over 433 commits on main (447 on all refs, clean), one author
   / committer identity with a GitHub noreply address, 0 attribution
   lines; the leak sweep finds 0 at HEAD and 0 in history with the needle
   arm armed (24 local needles). The plan-04 scan of the names of the
   third-party set reviewed in research 0056 found owner 0 and own
   repositories 0; GP-01 arms those names and re-runs every scan on the
   commit that is pushed. A rewrite would run only on MAIN's ORDER via
   fleet_rewrite.py; none is requested.
3. Only main and v* release tags are ever pushed, each to the same name.
   Lane and keep refs stay local. .githooks/pre-push enforces this,
   refuses deletes, moved tags and non-fast-forwards, and runs the
   fleet_identity pre-push check and the leak sweep on every push. The
   refuse-all behaviour and the AL_ALLOW_PUSH override are removed.
4. Private first: the repository is created private, main is pushed, and
   both workflows must be green. It becomes public only when every P0
   finding of the plan has landed (at least F-001, F-002 and F-005 with
   their three test files green on the flip commit), the scans of point
   2 are re-run clean on that commit, the community files and metadata
   are in place, and the operator's message to poe.ninja is sent or
   skipped in writing (ruling Q-05).
5. Nothing is merged on GitHub. Pull requests from Dependabot or from
   contributors are proposals: each is re-applied locally as an operator
   commit, pushed, and closed with a one-line comment (FLEET item 17);
   contributors are credited in the release notes. Dependabot alerts and
   security updates are on.
6. CI: one Windows workflow (pytest, node tests, leak sweep, PowerShell
   parse) and a byte copy of the kit's identity guard. Every action is
   pinned by full commit SHA; the token is read-only; no secret is used;
   CI never turns web data on and never calls a GGG or poe.ninja host.
7. Protection on main: one ruleset with no bypass blocks deletion and
   force pushes; a second requires the checks fleet-identity-guard and
   test, with the repository admin role as its only bypass so the
   operator's direct pushes of fresh commits land. No pull-request rule.
8. The project's own repository address may appear in tracked files (the
   README install line, the update-check constant, release metadata). It
   lives in config/public_repo.json and the leak sweep allows exactly
   that string. Every other account id, path, email and sibling name
   stays barred (ruling Q-24).
9. The public page says "Unofficial" and "Not affiliated with Grinding
   Gear Games", uses the game's name only descriptively, shows only
   AshLight's own art, and has no Sponsors link or FUNDING file.
10. Licence: Apache-2.0 for AshLight's own code; NOTICE names "The
    AshLight authors"; nothing third-party is bundled (decisions 0009,
    0018).
11. Releases: immutable releases on before the first v* tag; no code
    signing at first (ruling Q-22). The release procedure is plan 05.

## Alternatives

- Stay local only: rejected by the operator's order.
- A fresh root commit or a rewritten history: rejected; no scan needs
  it, a rewrite needs MAIN's ORDER, and the documents cite commits by
  hash.
- Public from the first push: rejected; a private first push proves CI
  and the settings with nothing exposed, and the tracked notes describe
  three defects that must be fixed before strangers can read them.
- Keep the AL_ALLOW_PUSH override: rejected; an override that lets any
  ref out is the leak the ref rule exists to stop.
- Merging pull requests on GitHub: rejected; a web merge has a
  non-operator committer (FLEET item 17).
- Refusing outside contributions: rejected; re-applying them keeps one
  identity in history and still lets people help.
- A pull-request-required rule on main: rejected; it blocks the session
  push and the loop's push worker.
- Required checks with no bypass: rejected; GitHub then rejects every
  direct push of commits CI has not yet seen.
- The address only in release assets and local config: rejected; a
  public project must say where to get it (Q-24).
- Game screenshots, a funding link: rejected; outside the Game ToS
  floor.

## Why

The operator ordered it. History and tree are clean, so the full record
(including the ToS floor rulings a cautious player wants to see) can be
shown. The guarded hook keeps the two checks that mattered while local
and adds the ref rule that matters once a remote exists. Private first
and gate-driven steps need no operator click beyond a signed-in gh.

## Reverses if

- The operator withdraws the order (then: repository private or deleted
  by the operator, hook back to refuse-all).
- A leak or identity hit is found in pushed history (then: private at
  once, rewrite request to MAIN).
- GitHub stops letting a repository admin push fresh commits past
  required checks (then: classic protection, or checks not required and
  the gap reported to MAIN).
- FLEET item 17 changes its rule on merges or required checks.
- GGG's rules for public tools change (research 0001 is re-read).
