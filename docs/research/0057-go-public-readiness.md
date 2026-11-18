# 0057 - Go-public readiness

Date: 2026-11-18. For the ultraplan (docs/plan/README.md), dimension E
go-public readiness. Audit only: history identity, leaks at HEAD and in
history, what a public reader sees, the operator's public-repo pattern, CI,
the pre-push hook and GGG's asks of public tools. Nothing was fixed.
Status: verified

## Sources (all accessed 2026-11-18)

- GGG-DEV: https://www.pathofexile.com/developer/docs (re-read anonymously
  this session: the non-affiliation sentence, the commercial-revenue line,
  the "officially authorised" presentation line, the 7i reverse-engineering
  line, the identifiable User-Agent rule and "Don't embed keys or
  credentials in a distributed binary" are all still on the page).
- GH-PVR: https://docs.github.com/en/code-security/security-advisories/working-with-repository-security-advisories/configuring-private-vulnerability-reporting-for-a-repository
- GH-DSU: https://docs.github.com/en/code-security/dependabot/dependabot-security-updates/configuring-dependabot-security-updates
- GH-ACT: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository
- GH-RULES: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- GH-RUN: https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job
  (labels re-checked at verification on
  https://docs.github.com/en/actions/reference/runners/github-hosted-runners:
  windows-latest, windows-2025, windows-2025-vs2026 and windows-2022 exist).
- GH-BP (added at verification): https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
  (direct pushes to a branch with required checks are allowed once the
  checks have passed on those commits).
- GH-DOPT (added at verification): https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference
  (`cooldown`, default 3 days, github-actions supports only default-days;
  `exclude-paths` per ecosystem, version updates only).
- GH-ABOUT-RS (added at verification): https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
  (availability line names Team and Enterprise plans; personal-account
  private repos are not addressed).
- GH-REL-API: the public releases API of the three first-party actions
  (checkout, setup-python, setup-node), read with an authenticated
  read-only gh call: checkout v7.0.1 (2026-07-20) commit 3d3c42e5aac5ba805825da76410c181273ba90b1;
  setup-python v7.1.0 (2026-10-22) commit 6d4fd22b20465ccc0f7354476588e8df7c9ca0e0;
  setup-node v7.1.0 (2026-10-08) commit 949feb2413d6458794dcd2491c4babbbce0c15c1.
- PEERS: read-only gh calls over the operator's own account (12
  repositories, 7 public), described generically; no name is recorded.
- Repo: ops/fleet_kit/fleet_identity.py, ops/fleet_kit/fleet_identity_guard.yml,
  tools/leak_sweep.py, .githooks/, tools/al_loop.py, README.md, NOTICE,
  LICENSE, SECURITY.md, CONTRIBUTING.md, THIRD-PARTY.md, .gitignore,
  .gitattributes, .claude/settings.json, tests/test_fleet_kit_conformance.py.
- Research 0001 (GGG policy), 0046 R9 (go-public wiring), 0047 (file
  structure), 0049 (suite speed), 0052 R7 and 0053 R6 (release and CI).

## Summary

- History is clean. fleet_identity reports 0 violations in all 9 classes over
  the 390 commits of main and 404 commits on all 16 local refs clean (counts
  re-run at verification; the draft's 370 / 384 predate later commits); one
  author / committer identity tuple across all 404, its address a GitHub
  noreply one; 0 attribution trailers. No rewrite is needed, so no request to
  MAIN via fleet_rewrite.py.
- Leaks: leak_sweep --tree and --history are both 0 findings with the needle
  arm ARMED (24 needles, local config) over every tracked file and all 404
  commits. 12 tracked PNGs (12 PNG paths ever added) carry 0 metadata
  chunks; no blob at HEAD over 500 KB.
  Full history can be published; a fresh root commit buys nothing.
- The brief's premise is wrong: the README hero IS tracked at HEAD
  (assets/brand/readme-hero-{light,dark}.png and .svg, added in 87212c0),
  drawn strokes with no font and no GGG imagery. Keep it where it is.
  app/brand/ holds only index.js, a loader that points the Electron side at
  the tracked icon files (app/brand/index.js:2-6); it is code, not art.
- LICENSE (Apache-2.0, full text), NOTICE, THIRD-PARTY.md, CONTRIBUTING.md,
  SECURITY.md and the GGG disclaimer (README, dashboard, overlay, client
  start page) exist. Missing: .github/ (CI, identity guard, Dependabot,
  issue and PR templates), CODE_OF_CONDUCT. NOTICE names "the operator" as
  copyright holder and uses fleet jargon.
- gh is authenticated (scopes repo, workflow, read:org, gist): creating the
  remote and setting the repository up needs NO operator act.
- Verdict: NO-GO today on 6 blockers (B1-B6 below), all agent work of
  about one day in total; then GO.

## Current state

- Refs: main plus 13 `fleet-lanes/lane-*` refs and 2 `al/keep/*` refs
  (git for-each-ref). No remote (git remote -v is empty). core.hooksPath
  points at .githooks (local config, not tracked).
- Identity gate: commit-msg strips attribution and runs the message leak
  sweep (.githooks/commit-msg:7-8); fleet_identity.py `pre-push`
  (ops/fleet_kit/fleet_identity.py:454-485), `check --history`
  (:536-566) and the server-side `ci-check` (:601-631).
  fleet.operatorIdent holds 1 value locally; a fresh clone has none, which is
  why CI uses ci-check (bot / AI identities only), not pre-push.
- Leak sweep: structural arm (drive paths, user-profile paths, emails, key
  shapes; tools/leak_sweep.py:50-58) plus the gitignored needle arm.
  --history walks `rev-list --all` (:278-289) and scans added lines, paths
  and messages, never author headers and never binary blobs (_is_text,
  :175-176).
- Pre-push hook: refuses every push (.githooks/pre-push:21-23) unless
  `AL_ALLOW_PUSH=1`, which runs fleet_identity pre-push and leak_sweep
  --pre-push over the same ref lines and proceeds (:10-19). Pinned by
  tests/test_fleet_kit_conformance.py:152-165, the line
  `assert "exit 1" in pp.rsplit("fi", 1)[-1]` (:162) pins the refusal.
- Loop auto-push: once `origin` exists the armed loop tick launches a push
  worker when main is clean and ahead of origin/main (tools/al_loop.py:52-57,
  1283-1297); the worker gates, runs leak_sweep --pre-push and pushes
  `origin main` (:1326-1337). With no origin/main yet, `rev-list --count`
  fails and returns 0 (:1296-1297), so the FIRST push is never the loop's.
  Gates come from ops/loop/gates.txt (pytest, npm test, leak sweep --tree).
- Public files at HEAD: README.md (169 lines), LICENSE (201, Apache-2.0),
  NOTICE (19), THIRD-PARTY.md (115; PoB-PoE2 MIT and LuaJIT, fetched not
  bundled), CONTRIBUTING.md (15), SECURITY.md (20), .gitattributes
  (`* text=auto eol=lf`, PNG / ICO binary, the kit -text), .gitignore
  (local config, needles, runtime, control, channel folders).
- Disclaimer: README.md:161-165; web/index.html, app/overlay/index.html and
  app/client/starting.html carry the sentence once each.
- Brand: assets/brand (2 SVG marks, 7 PNG sizes, hero SVG and 2 PNGs),
  app/assets (icon, tray), web/favicon; design record
  docs/design/0005-brand-mark.md:6, 29, 77 (no font, no GGG imagery).
- Developer surface a reader will see: CLAUDE.md (598 lines, FLEET block
  byte-pinned), AL-NEXT-SESSION.txt (141), ROADMAP.md (2061),
  ops/fleet_kit (26 files), ops/loop (gates.txt, slots.py),
  ops/status_board.json, .claude/ (settings.json with project hooks, 3
  agents, done command), moon_sync_inbox/.gitkeep and
  moon_sync_outbox/.gitkeep, a copied fleet ORDER note under
  tests/fixtures/inbox_p164/.

## Findings

F1. Identity history: clean, no rewrite. `fleet_identity.py check
--history --by-class main`: commits 390, distinct flagged 0, all 9 classes
0. `check --all`: 404 commits clean. `ci-check - main`: 390 clean (push,
whole history). Own scan: 1 distinct author / committer tuple over 404
commits; 0 lines matching co-authored-by / signed-off-by / co-developed-by /
"generated with" / session URLs; 0 AI or bot names in identities. The
address is a GitHub noreply one, so publishing history publishes no
personal mailbox. Why it matters: FLEET item 17 is met before the push; no
MAIN rewrite order is needed.

F2. Leaks: clean at HEAD and in history. --tree 0 and --history 0 (needle
arm ARMED, 24 needles; structural arm on). Blind spots: binary blobs and
author headers are not swept; both were checked separately (12 PNGs with
only IHDR / IDAT / IEND chunks, so no tEXt / iTXt / zTXt / eXIf / tIME; 2
ICO files; identity in F1).
History matters as much as HEAD because every reachable commit is public
after a push; it is clean, so the choice between a MAIN-ordered rewrite and
a fresh root commit does not arise. Weighed anyway: a rewrite keeps the
narrative but needs a MAIN order and re-hashes 404 commits (every hash
cited in docs goes stale); a fresh root is cheap but drops the record the
docs cite by hash (decisions and notes cite commits such as b8fda80 and
87212c0). Neither is warranted.

F3. Local-only refs must never reach the remote. 15 refs besides main
(lane and keep branches) are local lane state. `git push --all` or
`--mirror` would publish them and their unreviewed lane commits. The hook
does not restrict which refs go out.

F4. The pre-push hook and its test pin "local only". The normal guarded
push the operator ordered needs the refusal gone while both scans stay.
The CLAUDE.md "Public-repo hygiene" section (CLAUDE.md:317-324), the
al_loop docstring (tools/al_loop.py:52-57) and the ROADMAP operator row
(ROADMAP.md:2059-2061) all describe the refusal and must change in the
same commit. The hand-off also mentions it (AL-NEXT-SESSION.txt:74); /done
rewrites that file, so it follows on its own. The pinning test's docstring
(tests/test_fleet_kit_conformance.py:153-154) says "pre-push refuses" and
changes with the assert. The FLEET block's "pre-push refuses"
(CLAUDE.md:208) means refusing bot commits, not every push: it stays.

F5. Loop auto-push once public. After the first manual push the armed
loop pushes main every tick it is ahead (F-state above), through gates and
the leak sweep. Every hand-off rewrite and ROADMAP edit then becomes public
within 15 minutes. Acceptable (peers publish their hand-off too, F11), but
the push is direct `git push origin main`; with the hook still refusing,
every loop push fails and logs "push failed" until B1 lands.

F6. No CI exists (no .github/). FLEET item 17 (v32) requires the kit's
fleet_identity_guard.yml copied byte-for-byte to
.github/workflows/fleet-identity-guard.yml as a required check
(ops/fleet_kit/fleet_identity_guard.yml:6-9). The suite has never run in a
fresh clone: CLAUDE.md gates and gates.txt assume local config. Suite cost
is about 236 s of test time (research 0049) and 230 node tests in under
1 s, node-only (0049), so Electron's binary download can be skipped in CI;
the overlay smoke test already skips unless AL_OVERLAY_SMOKE=1 on Windows
(tests/test_overlay_smoke.py:175-180).

F7. NOTICE reads as internal. NOTICE:2 "Copyright 2026 the operator" names
no holder a reader can identify; NOTICE:6-7 and :12-13 say "MAIN fleet
kit" and "the same operator's fleet". Apache-2.0 needs no named holder to
be valid, but a placeholder looks unfinished. The vendored kit's own
NOTICE says the same and is byte-pinned (MAIN's to change).

F8. README accuracy, 4 gaps. (a) README.md:62-64 says Node 20 or newer;
`npm test` uses a `node --test` glob and Node 20 is past end of life
(research 0046 F, R3 owns the floor). (b) The desktop client (decision
0041: companion window, tray, overlay in one Electron process started by
run.ps1) is not described; README.md:69-70 still says "overlay (if
installed)" and `-NoOverlay` actually means "no client"
(scripts/run.ps1:146-148, 201); `-NoBrowser` also drops the client
(run.ps1:148), which README.md:71 ("prints the dashboard link instead")
does not say. (c) No word on what ops/, CLAUDE.md, the
hand-off file and ROADMAP are, so the first-screen file list looks like
noise. (d) README.md:119-124 says nothing leaves the computer unless web
data is on; true for the app, but the developer loop (GGG docs watch,
decision 0044; PoB release check, decision 0025) reads the web unattended.
A one-line scope note keeps the claim exact.

F9. SECURITY.md:5 says "Once this repository is public"; private
vulnerability reporting must be switched on per repository (GH-PVR), it is
on in 7 of 7 peers (PEERS).

F10. Missing community files: CODE_OF_CONDUCT (6 of 7 peers have one),
issue templates (all 7 have an ISSUE_TEMPLATE folder), PR template (6 of
7). Research 0051 already plans a .github/ISSUE_TEMPLATE at go-public
(0051:518 in its current working copy). No CHANGELOG (0053 R6 owns it).

F11. The operator's public-repo pattern (7 public of 12; PEERS):
- Files: 6 of 7 publish CLAUDE.md, the vendored kit and the hand-off file
  at the root; none tracks channel folders at the root; all 7 have LICENSE
  (5 Apache-2.0) and .gitattributes; 6 of 7 have community health 100.
- Security: secret scanning and push protection on in 7 of 7; Dependabot
  alerts on in 7 of 7; Dependabot security updates on in only 1 of 7
  (FLEET item 17 says they stay on: a pattern gap to report to MAIN);
  private vulnerability reporting on in 7 of 7.
- Actions: default workflow token read-only and PR approval off in 7 of 7;
  "require full-length SHA pinning" (GH-ACT) off in 7 of 7 although the
  workflows pin by SHA with a tag comment.
- Workflows: identity guard in 5 of 7, CodeQL in 5 of 7, CI on push and
  pull_request to main, contents: read, nightly cron in the largest.
- Protection: 5 of 7 use classic branch protection (admins enforced, no
  force push, no deletion) with NO required status checks, so the identity
  guard runs but is not required (FLEET item 17 says required); 1 uses two
  rulesets (no deletion, no force push, linear history; PR required with 0
  approvals); 1 is unprotected.
- Metadata: description 7 of 7, 8-12 topics each, wiki off and projects
  off in 7 of 7, discussions on in 1, releases in 3 of 7 (one with
  assets).
- Dependabot config: weekly, one group per ecosystem, never merged on
  GitHub; the bump is cherry-picked locally with --no-commit and committed
  as the operator (FLEET item 17).

F12. .claude/settings.json is public too. Its project hooks (subagent-first,
claims) apply to any contributor who opens the clone in Claude Code after
the trust prompt; the subagent-first hook denies main-thread tool calls,
which will puzzle an outsider. Line 17 allows `tools/ash_lane.py`, a file
that does not exist (the lane tool is tools/al_lane.py; research 0047 F13
has it). Peers publish the same settings (F11), so this is a "needs one
sentence in CONTRIBUTING" item, not a mover.

F13. Fleet residue in tests: tests/fixtures/inbox_p164/ holds a real copied
MAIN ORDER note (its file name reads "from-MAIN-ORDER-to-AL-..."). It is
leak-clean but reads as private correspondence. A synthetic note with the
same shape serves the test equally.

F14. Archived ROADMAP narrative (0047 asks this note to decide): publish
it. It is leak-clean, already in history either way, and shows the
safety record (ToS floor rulings) a cautious player wants to see.
Archive placement is 0047's call.

F15. GGG's asks of a public tool (research 0001, re-read GGG-DEV): state
non-affiliation (done, 4 surfaces); never present the tool as developed or
authorised by GGG; no commercial revenue from GGG IP (no paid tier,
donation gate or sale of derived data); no use of GGG or game logos that
imitates an official platform (GGG-DEV; the wider "no GGG trademarks, art
or logos in name, icon or branding" is AshLight's own stricter floor in
CLAUDE.md); call only documented endpoints, obey rate limits, identifiable
User-Agent (GGG-DEV spells out the client-id / version / contact form for
OAuth API clients; AshLight calls no GGG API, and its web requests follow
the CLAUDE.md floor: a truthful User-Agent naming AshLight and its version,
no POESESSID); never embed keys or credentials in code or a
distributed binary. A
public repo adds three concrete checks: the repository description and
topics must read as unofficial and descriptive; no Sponsors / FUNDING.yml
on a GGG-derived tool; no screenshot of the game in the README (the hero is
own art; a future screenshot of the dashboard is fine, of the game is not).

## Recommendations

R1. GP-HOOK: the normal guarded push (blocker B1).
- Action: rewrite .githooks/pre-push to always run fleet_identity pre-push
  and leak_sweep --pre-push over stdin, refuse any ref other than
  refs/heads/main and refs/tags/v*, refuse a delete, then exit 0; drop
  AL_ALLOW_PUSH.
- Impact: H - the loop's push works; lane refs can never leak (F3, F5).
- Effort: S. Risk: L; the identity and leak checks are unchanged code.
- ToS check: no floor rule touched; it only gates git pushes.
- Depends on: nothing. Same commit as R2.
- Files likely touched: .githooks/pre-push,
  tests/test_fleet_kit_conformance.py, new tests/test_pre_push_hook.py.
- Acceptance test: replace the refusal assert at
  tests/test_fleet_kit_conformance.py:162 with: the hook text has no
  "PUSH REFUSED" and no AL_ALLOW_PUSH, both scan lines are still present
  (:160-161), and the file ends in `exit 0`. New test (Windows sh from Git,
  skip when absent): a tmp repo plus a bare remote; a clean commit on main
  pushes (rc 0); a commit adding a planted drive path is refused; pushing a
  `fleet-lanes/x` ref is refused; deleting main is refused. All with
  fleet.operatorIdent set in the tmp repo only.
- ZERO-CLICK: after it lands the loop pushes on its own.

R2. GP-RULES: say "public" everywhere the tree says "local only" (B2).
- Action: in the R1 commit, rewrite CLAUDE.md "Public-repo hygiene"
  (CLAUDE.md:317-324) to "public at <the repo>; push only main and v* tags
  through the guarded hook", fix the al_loop docstring
  (tools/al_loop.py:52-57) and close ROADMAP.md:2059-2061.
- Impact: H - the rules agents read match reality. Effort: S. Risk: L.
- ToS check: none touched.
- Depends on: R1. Files: CLAUDE.md (tree-specific part only, never the
  FLEET block), tools/al_loop.py, ROADMAP.md.
- Acceptance test: grep finds no "refuses every push" or "NO remote" in
  CLAUDE.md, tools/al_loop.py or .githooks; kit conformance test passes.
- ZERO-CLICK: documentation only.

R3. GP-CI: one Windows CI workflow plus the identity guard (B3).
- Action: add .github/workflows/ci.yml and a byte copy of the kit guard at
  .github/workflows/fleet-identity-guard.yml.
- ci.yml shape: on push to main, pull_request to main and
  workflow_dispatch; top-level `permissions: contents: read`; no secrets
  referenced; concurrency per ref with cancel-in-progress for pull
  requests; one job `test` on `windows-2025` (a named label, GH-RUN, so an
  image move is a reviewed change), timeout 30 minutes; steps: checkout
  pinned at 3d3c42e5aac5ba805825da76410c181273ba90b1 (v7.0.1) with
  persist-credentials false; setup-python pinned at
  6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 (v7.1.0), Python 3.11 (the
  floor; a second matrix leg on the newest CPython is optional); pip
  install an exact pytest version; setup-node pinned at
  949feb2413d6458794dcd2491c4babbbce0c15c1 (v7.1.0), Node 24 (0046 R3
  floor); env AL_SIDECAR_ROOT under runner.temp, ELECTRON_SKIP_BINARY_DOWNLOAD=1;
  `python -m pytest -q`; `npm ci --prefix app`; `npm test --prefix app`;
  `python tools/leak_sweep.py --tree` (DEGRADED in CI: structural arm
  only, by design); a powershell.exe 5.1 ParseFile pass over scripts/*.ps1
  (FLEET item 8). Every action is pinned by full SHA with its tag as a
  comment (GH-REL-API); action versions follow the 14-day age rule of
  research 0046.
- Impact: H - FLEET item 17 server side; a public reader sees a green
  check. Effort: M (fresh-clone fixes may surface; see R4).
- Risk: M - first CI in the tree; Windows runner slower than local.
- ToS check: "no GGG endpoint unless documented": CI never sets web_data,
  so no network call to GGG or poe.ninja happens in CI; nothing touches a
  game.
- Depends on: R4 green. Files: .github/workflows/ci.yml,
  .github/workflows/fleet-identity-guard.yml, a new
  tests/test_ci_workflow.py.
- Acceptance test: test_ci_workflow.py parses ci.yml as text and asserts
  every `uses:` has a 40-hex SHA, `permissions: contents: read` at top
  level, no `secrets.` reference, `windows-` runner; and that the guard
  copy is byte-identical to ops/fleet_kit/fleet_identity_guard.yml. After
  the push: `gh run list` shows both workflows green on main.
- ZERO-CLICK: runs on every push with no action.

R4. GP-FRESH: prove the suite in a fresh clone before anything is pushed
(B4).
- Action: clone main into the sidecar Scratch (no hooks, no
  config/local.json, no needle file, AL_SIDECAR_ROOT pointed at a scratch
  folder), run the suite through the suite gate and npm test there; fix
  every test that needs local state (skip or tmp fixture), never by
  weakening a guard.
- Impact: H - avoids a red first public CI. Effort: S-M. Risk: L.
- ToS check: the core started by tests replays fixtures only; a test that
  would discover a live Client.txt must be pinned to a fixture path (the
  session-6 incident).
- Depends on: nothing. Files: tests/ only as needed.
- Acceptance test: the fresh-clone run exits 0 with the same pass count as
  the main checkout minus documented skips; the skip list is recorded in
  the commit.
- ZERO-CLICK: an agent step.

R5. GP-NOTICE: public-facing NOTICE and copyright line (B6).
- Action: replace NOTICE:2 with "Copyright 2026 The AshLight authors"
  (the convention big projects use; it names no person) and reword
  NOTICE:6-7 and :12-13 to "ops/fleet_kit/ is a vendored development kit
  (Apache-2.0, own LICENSE and NOTICE)". Record the license choice
  (Apache-2.0 for own code; nothing third-party bundled; data only as
  attributed sidecar snapshots per decision 0009) in a decision.
- Impact: M. Effort: S. Risk: L - an operator who wants a named holder
  overrides (Open questions).
- ToS check: "no commercial revenue from GGG IP": Apache-2.0 lets others
  sell forks; AshLight itself sells nothing and ships no GGG asset, so
  the floor binds AshLight and holds; NOTICE keeps the non-affiliation
  text.
- Depends on: nothing. Files: NOTICE, a new docs/decisions record.
- Acceptance test: grep NOTICE finds no "the operator" and no "MAIN";
  tests/test_ascii_lf.py passes.
- ZERO-CLICK: documentation only.

R6. GP-REFS: push only main, never the lane refs (B5).
- Action: the first push is `git push -u origin main` through
  fleet_gitlock; never `--all`, `--mirror` or `--tags` without a v*
  filter; R1 enforces it.
- Impact: H. Effort: S. Risk: L.
- ToS check: none touched.
- Depends on: R1. Files: none beyond R1.
- Acceptance test: `git ls-remote origin` lists exactly refs/heads/main
  (and HEAD) after the first push.
- ZERO-CLICK: agent step.

R7. GP-SETUP: create and configure the repository with gh, private first.
- Action, in order: (1) `gh repo create` as PRIVATE with description and
  no auto-init; (2) add origin, push main (R6); (3) wait for both
  workflows green; (4) flip visibility to public; (5) then, because
  branch protection on a private personal repo may need a paid plan
  (UNVERIFIED), set a ruleset on main: block force pushes, restrict
  deletions, require status checks `fleet-identity-guard` and `test`
  (GH-RULES), no PR requirement (the operator merges locally and pushes
  main directly; a PR rule would block the loop);
  (verification correction) the ruleset gets ONE bypass actor, the
  repository admin role, bypass mode always: GitHub lets a commit be pushed
  directly to a branch with required checks only once those checks have
  already passed on it (GH-BP), and the loop pushes fresh local commits to
  main that no CI has seen, so a no-bypass ruleset would reject every loop
  push. With the admin bypass the required checks bind pull requests
  (Dependabot and outside contributors, the web-UI merge case the guard
  exists for, ops/fleet_kit/fleet_identity_guard.yml:11-17) and the
  operator's direct pushes stay gated by the local pre-push identity check
  and leak sweep (R1), while both workflows still run on every push to main;
  (6) enable private vulnerability reporting (GH-PVR), Dependabot alerts
  and security updates (GH-DSU), secret scanning and push protection;
  turn on "require actions pinned to a full-length commit SHA" (GH-ACT;
  peers leave it off, AL starts strict); default workflow token
  read-only, PR approval by Actions off; wiki and projects off,
  discussions off, issues on; (7) topics and description (R9).
- Impact: H. Effort: S. Risk: M - a required check that never reported
  blocks every push: add the ruleset only after step 3 shows the check
  names.
- ToS check: "never present AshLight as developed, authorised or endorsed
  by GGG": the description says unofficial; no GGG art in the social
  preview (use the hero).
- Depends on: R1-R6 landed. Files: none (repository settings).
- Acceptance test: read-back with gh api: visibility public; ruleset
  active with the two required checks and the admin role as the only
  bypass actor; the next loop push lands (tick log "push ok");
  private-vulnerability-reporting enabled true; automated-security-fixes
  enabled true; vulnerability-alerts 204; actions permissions
  sha_pinning_required true; workflow default permissions read.
- ZERO-CLICK: gh is already authenticated; no operator act.

R8. GP-DEPENDABOT: config plus the local re-apply lane (FLEET item 17).
- Action: .github/dependabot.yml with npm in /app and github-actions,
  weekly, one group per ecosystem, cooldown as 0046 R9 (for github-actions
  only `default-days` applies, GH-DOPT); exclude the identity-guard copy
  from github-actions bumps with `exclude-paths:
  [".github/workflows/fleet-identity-guard.yml"]` (GH-DOPT; version
  updates only, so a security update could still open a PR there: close it
  and report to MAIN, the kit owns that file). Bump PRs
  are never merged on GitHub: a lane cherry-picks the PR head with
  --no-commit, regenerates app/package-lock.json locally, commits as the
  operator through fleet_gitlock, pushes main, closes the PR with one
  line. 0046 R9 owns the lane tool; this note only fixes the order:
  config at go-public, lane before the first bump PR is due (7 days).
- Impact: M. Effort: M (lane). Risk: L - a bot PR's red identity check
  is expected and harmless.
- ToS check: none touched.
- Depends on: R7. Files: .github/dependabot.yml, the 0046 R9 lane tool.
- Acceptance test: 0046 R9's fixture test; the YAML lint in R3's test.
- ZERO-CLICK: the lane runs from the loop tick.

R9. GP-META: description, topics, social preview.
- Action: description "Unofficial second-screen dashboard and
  click-through overlay for Path of Exile 2 on Windows. Reads the game's
  log file; never touches the game process. Not affiliated with Grinding
  Gear Games." (verification correction: the draft's "Reads only the
  game's log file" was untrue, AshLight also reads item text on a hotkey
  press and opt-in web data, NOTICE:17-18); topics:
  path-of-exile-2, poe2, overlay, companion-app, dashboard, electron,
  python, windows, path-of-building, loot-filter (10, peers use 8-12);
  social preview: readme-hero-dark.png; no homepage until a release
  page exists; no FUNDING.yml.
- Impact: M - discoverability and an honest first line. Effort: S.
- Risk: L.
- ToS check: "'Path of Exile 2' appears only descriptively" and "no
  revenue from GGG IP": the name is used as a "for" phrase; no funding
  link.
- Depends on: R7. Files: none (settings).
- Acceptance test: `gh repo view --json description,repositoryTopics`
  read-back matches.
- ZERO-CLICK: agent step.

R10. GP-README: four accuracy fixes and a "How this repo is run" section.
- Action: fix F8 (a)-(d); add a short section naming CLAUDE.md, ops/,
  AL-NEXT-SESSION.txt, ROADMAP.md and docs/ as the development process
  (AI-assisted, operator-reviewed, every commit gated by tests, identity
  and leak checks) so an outsider can ignore them; SECURITY.md:5 to the
  present tense; CONTRIBUTING gains one line on the project Claude Code
  hooks (F12) and that hooks are not installed by a clone (`git config
  core.hooksPath .githooks` to opt in).
- Impact: M. Effort: S. Risk: L.
- ToS check: "show the non-affiliation sentence in the README": kept
  verbatim at README.md:163.
- Depends on: 0046 R3 for the Node floor number. Files: README.md,
  SECURITY.md, CONTRIBUTING.md.
- Acceptance test: README names Node 22 or newer (or 0046's floor);
  describes the desktop client and tray; tests/test_ascii_lf.py and the
  leak sweep pass.
- ZERO-CLICK: documentation only.

R11. GP-COMMUNITY: CODE_OF_CONDUCT, issue and PR templates.
- Action: CODE_OF_CONDUCT.md (own short text in AshLight's words, a
  private report route via the Security tab, no email address); issue
  forms for bug (asks for the DIAG-SELF report, decision 0040, already
  redacted, never a raw Client.txt) and feature (asks which ToS floor
  rule it might touch); a PR template with the gate commands.
- Impact: L-M. Effort: S. Risk: L.
- ToS check: the bug form forbids attaching game files or memory dumps
  and asks for the redacted report only.
- Depends on: nothing. Files: CODE_OF_CONDUCT.md,
  .github/ISSUE_TEMPLATE/*.yml, .github/pull_request_template.md.
- Acceptance test: GitHub community profile health 100 (gh api
  community/profile) after the push.
- ZERO-CLICK: documentation only.

R12. GP-TIDY: three small public-surface cleanups.
- Action: replace the copied ORDER note fixture (F13) with a synthetic
  one of the same shape; untrack moon_sync_inbox/.gitkeep and
  moon_sync_outbox/.gitkeep only if the kit tolerates a missing folder
  (it is created at run time in peers; verify before moving); drop the
  stale `tools/ash_lane.py` permission (F12; a settings change, so in the
  operator's batched ask per 0047).
- Impact: L. Effort: S. Risk: L.
- ToS check: none touched.
- Depends on: nothing. Files: tests/fixtures/inbox_p164/,
  tests/test_loop_inbox_p164.py, .gitignore, .claude/settings.json.
- Acceptance test: the inbox tests pass with the synthetic fixture;
  `git ls-files moon_sync_*` empty if moved.
- ZERO-CLICK: agent step.

## Go / no-go for the first push

GO (verified this session):
- Identity: 0 violations, 404 commits on all refs (390 on main), noreply
  address (F1). Re-run both scans right before the push: history grows.
- Leaks: 0 at HEAD, 0 in history, binaries clean (F2).
- LICENSE, NOTICE text present; disclaimer on 4 surfaces; own brand art.
- gh authenticated with repo and workflow scopes.

NO-GO until fixed (all agent work, one commit series, about one day):
- B1 hook refuses every push and lets any ref out: R1.
- B2 rules and docstrings say local only: R2 (same commit as R1).
- B3 no CI and no identity guard workflow: R3.
- B4 suite unproven in a fresh clone: R4 (before R3 is pushed).
- B5 15 local lane / keep refs must stay local: R6 (enforced by R1).
- B6 NOTICE placeholder holder and fleet jargon: R5.

Should-fix before the visibility flip (not blockers): R9, R10, R11.
After the flip: R7 steps 5-7, R8, R12.

Operator act: none. gh is authenticated, so `gh auth login` is not needed.
The only operator input that could change the plan is the copyright-holder
text (Open questions), and R5 has a default.

## Cut or merge

- Merge 0046 R9 (go-public wiring) into R3 + R8 here: same files; 0046
  keeps the lane tool, this note keeps the order and settings.
- Merge 0052 R7's "one Windows CI workflow" into R3 (one ci.yml, not two);
  the release workflow (0053 R6) stays separate and comes later.
- 0051's issue template at go-public folds into R11.

## Rejected

- A history rewrite or a fresh root commit: no finding needs one (F1, F2);
  a rewrite would also need a MAIN order via fleet_rewrite.py.
- A pull-request-required ruleset on main: blocks the loop's direct push
  and the local-merge workflow; force-push and deletion blocks plus
  required checks give the protection that matters.
- Publishing screenshots of the game in the README or social preview:
  GGG art (ToS floor "No GGG trademarks, art or logos in the app name, icon
  or branding").
- A Sponsors / FUNDING.yml link: floor "no ads or donation gate on
  GGG-derived features"; a general donation link on a tool whose value is
  GGG-derived reads as revenue from GGG IP.
- CI with web_data on, or a CI job that calls poe.ninja or GGG docs:
  needless traffic and a contact header in CI; floor "public web data"
  is for the user's opt-in, not for CI.
- Moving CLAUDE.md, the kit or the hand-off out of the tree: 6 of 7 peer
  public repos publish them; the FLEET block is byte-pinned and tested;
  an explanation (R10) costs less than a move.

## Open questions

- Copyright holder text (R5): "The AshLight authors" is the default taken
  here; the operator may prefer a public handle. Operator override only,
  not a blocker.
- Whether a personal-account private repository can carry the ruleset
  before the flip (UNVERIFIED: GH-ABOUT-RS names only Team and Enterprise,
  and the account plan is not readable with the token's scopes; R7
  sequences it after the flip so the answer does not matter).
- Peer gaps for MAIN (not AL work): Dependabot security updates on in 1 of
  7 public peers and the identity guard required in 0 of 7, both against
  FLEET item 17. Report in AL's next batched note to MAIN.
- Whether the kit tolerates absent channel folders (R12); read
  fleet_inbox before moving them.

## Verification

Independent verification, 2026-11-18, by an agent that did not write the
draft.

Checked (re-run or re-read, not taken from the draft):
- Identity: fleet_identity `check --history --by-class main` (390, all 9
  classes 0), `check --all` (404 clean), `ci-check - main` (390 clean);
  own git log scan: 1 identity tuple, 0 trailer lines, noreply domain.
  16 refs, no remote.
- Leaks: leak_sweep --tree (rc 0) and --history, both ARMED with 24
  needles, 0 findings; PNG chunk scan of all 12 tracked PNGs (only IHDR /
  IDAT / IEND); 0 blobs at HEAD over 500 KB.
- Code citations, 24 checked: .githooks/pre-push:2-24, commit-msg:7-8,
  tests/test_fleet_kit_conformance.py:152-165, fleet_identity.py def lines
  454 / 536 / 601, leak_sweep.py:50-58, 175, 278-289, al_loop.py:52-57,
  168-178 (push runs under the kit git lock), 1282-1297, 1322-1338,
  CLAUDE.md:317-324, ROADMAP.md:2059-2061, README.md:62-72, 119-124,
  161-169, NOTICE, SECURITY.md:5, .claude/settings.json:17 (tools/ash_lane.py
  absent), run.ps1:146-148, 201, test_overlay_smoke.py:175-180,
  app/package.json test script, the guard yml, design 0005:6, 29, 77, the
  disclaimer in 3 HTML files, .gitattributes, .gitignore, file line counts.
- gh (read-only): auth status and scopes; latest releases and commit SHAs
  of checkout, setup-python, setup-node (all three match the draft); the 7
  public of 12 peers and every PEERS settings count in F11 (security
  updates 1/7, private reporting 7/7, alerts 7/7, 5 classic protections
  with 0 required checks, 1 with 2 rulesets, 1 unprotected, SHA pinning
  off 7/7, token read-only and PR approval off 7/7, identity guard
  workflow 5/7, 8-12 topics).
- Web: GGG-DEV re-fetched (all six asks present; logos clause narrower
  than drafted), GH-ACT, GH-PVR, GH-DSU, GH-RULES, runner labels, GH-BP,
  GH-DOPT, GH-ABOUT-RS.
- ToS floor: every R and every Rejected item re-tested; none needs the
  floor bent. Settled decisions: none contradicted (0009, 0013, 0015-0017,
  0041 touched only descriptively).

Corrected (10): commit counts 370 / 384 to 390 / 404 (history grew); PNG
count 13 to 12; NOTICE cite :14-15 to :12-13 (twice); 0051 cite :475 to
:518; F15 logo clause narrowed to GGG-DEV's wording and the User-Agent
format scoped to OAuth API clients; R9 description no longer claims
"reads only the game's log file"; R7 ruleset gets the admin role as its
one bypass actor, because a no-bypass required-check rule would reject
every direct loop push (GH-BP); R8 names the real `exclude-paths` option
and its version-updates-only limit; F4 and F8 gained the hand-off,
docstring, FLEET-block and `-NoBrowser` details; app/brand explained.

UNVERIFIED: whether a personal-account private repository can carry a
ruleset or branch protection before the visibility flip (R7 is sequenced
so it does not matter); the fresh-clone suite run (R4, deliberately not
run here: the ground rules forbid the whole suite).
