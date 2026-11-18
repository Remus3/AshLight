# 04 - Go public

Date: 2026-11-18. Ultraplan plan section (docs/plan/README.md).
Status: final

Inputs: research 0057 (primary), 0046 (R3, R9, R10), 0053 (R6), 0045 (F1,
F2), 0050 (F32); docs/plan/findings.json (findings F-004, F-006, F-008,
F-009, F-013, F-016, F-020, F-021, F-046, F-075, F-079, F-081, F-148,
F-200; rulings Q-03, Q-05, Q-22, Q-23, Q-24, Q-25); docs/plan/01
("OPERATOR: GitHub remote"); CLAUDE.md (FLEET items 4, 10, 14, 17, the
Public-repo hygiene section); ROADMAP.md:2059-2061. Checked in this
session: .githooks/pre-push, tests/test_fleet_kit_conformance.py:152-165,
tools/leak_sweep.py, tools/al_loop.py (push path), the kit guard workflow,
app/package.json, the hero files, and three read-only scans (section
"Scans run for this section").

## Goal

Done means every line below is true and read back:

1. The repository exists on GitHub under the operator's account, is
   public, and `git ls-remote --heads --tags origin` lists
   `refs/heads/main`, (later) `refs/tags/v*`, and nothing else except
   `refs/heads/dependabot/*` branches that GitHub's Dependabot creates on
   the server (`refs/pull/*` are GitHub's own and are not listed by
   `--heads --tags`). No `fleet-lanes` or `al/keep` ref ever left the
   machine.
2. Every commit reachable from the pushed main has the one operator
   identity as author and committer and no AI or bot attribution line
   (`fleet_identity.py check --history --by-class main`: 0 in all 9
   classes), re-run on the commit that is pushed.
3. The leak sweep is clean over the tree and over every reachable commit
   with the needle arm ARMED, including the names of the third-party set
   reviewed in research 0056 (owner slot 0, own-repository slots 0).
4. `.githooks/pre-push` no longer refuses every push. It lets only main
   and `v*` tags out, refuses deletes and non-fast-forwards, and runs the
   fleet_identity pre-push check and the leak sweep on every push. No
   override variable exists.
5. Two workflows are green on main: `ci` (job `test`: pytest, node tests,
   leak sweep, PowerShell parse) and `fleet-identity-guard` (a byte copy
   of the kit file). Both checks are required on main.
6. The public page is complete: README with the own-art hero, LICENSE,
   NOTICE, THIRD-PARTY, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, issue
   forms, PR template; community profile health 100.
7. Repository settings read back as planned: description, 10 topics,
   wiki / projects / discussions off, issues on, rulesets active,
   Dependabot alerts and security updates on, private vulnerability
   reporting on, secret scanning and push protection on, Actions token
   read-only, actions pinned by full SHA required.
8. Dependabot bump pull requests are never merged on GitHub: each is
   re-applied locally as an operator commit, pushed, and closed with one
   line (FLEET item 17). A test proves the lane tool does exactly that.
9. The three probe-confirmed defects written up in tracked notes (F-001,
   F-002, F-005) were fixed before the visibility flip (F-006).
10. No GGG art, logo or game screenshot is on the page, no funding link
    exists, and the description says "Unofficial" and "Not affiliated".

## Design

### The go

- The operator ordered going public in the session-6 ultraplan order
  (2026-11-17, item E). That order is the "recorded go" ruling Q-23 waits
  for, for both steps: create the remote and push (step 1), and flip to
  public once the gates hold (step 4; Q-23's own recommended option "go
  for both; the flip happens by itself once the P0 list is green").
- The go-public decision (section "Decision text") records the order and
  lifts the 2026-11-16 local-only order that CLAUDE.md:319-321 cites. The
  hand-off records it too (Q-23 "record").
- Marked fallback: if the step that records the decision cannot cite the
  operator's order, Q-23's default holds: stay local, GP-02 stays a ready
  diff, nothing is created. Nothing else in this section changes.
- Owner and name (Q-24): default is the account `gh` is signed in as and
  the name `AshLight` (decision 0001). The operator may name another
  address before GP-09; nothing waits for it.

### Shape

- Full history is published (0057 F1, F2; 0057-X1 not adopted). No rewrite
  and no fresh root: the scans are clean (below). A rewrite would run only
  on MAIN's ORDER via `ops/fleet_kit/fleet_rewrite.py` (FLEET item 17,
  Q-25); this section files no request because none is needed.
- Private first, then public (F-021): create PRIVATE, push main, see both
  workflows green, set metadata, then flip. A private repository publishes
  nothing, so the first push does not wait for the security fixes; the
  flip does (F-006).
- Only main and `v*` tags are ever pushed (F-016, 0057 F3). The 15 local
  lane and keep refs stay local; the hook enforces it.
- Nothing is merged on GitHub. FLEET item 17 allows only the operator as
  author and committer, and a web-UI merge has GitHub as committer. A
  pull request (Dependabot's or a contributor's) is a proposal: it is
  re-applied locally as an operator commit, pushed, and closed with one
  line naming the commit. CONTRIBUTING and the PR template say so
  plainly; contributors are credited in the release notes.
- Direct pushes of fresh local commits to main must keep working (the
  session push and the loop's push worker). GitHub accepts a direct push
  to a branch with required checks only when the checks already passed on
  those commits (0057 GH-BP), so the required-checks ruleset carries one
  bypass actor, the repository admin role. Deletion and force-push blocks
  sit in a second ruleset with NO bypass, so they bind the operator too.
  A pull-request-required rule is not used (0057-X2 not adopted).
- CI never turns web data on and calls no GGG or poe.ninja host (0057-X5
  not adopted; floor: public web data is the user's opt-in).
- The page carries no game screenshot, GGG art or logo and no Sponsors or
  FUNDING link (0057-X3, 0057-X4 not adopted; floor: branding and revenue
  rules). The hero is AshLight's own drawn strokes.
- CLAUDE.md, the vendored kit, the hand-off and ROADMAP stay in the tree
  (0057-X6 not adopted); the README explains them in one section.
- The project's own repository address may appear in tracked files as one
  exception to the hygiene rule (Q-24); every other account id, path,
  email and sibling name stays barred.
- Once the public URL exists the default User-Agent contact is the
  project's issues page (Q-03; owned by F-018, recorded as an amendment of
  decisions 0015 and 0016 there, not here).
- Release builds make no poe.ninja request until poe.ninja's yes is
  recorded (F-046, Q-05; owned by the prices work). Here it only gates the
  flip on the operator's message.
- No code signing at first (Q-22); release provenance is F-148 (plan 05).

### Hero image

Located, nothing to create. `assets/brand/readme-hero-light.png` and
`readme-hero-dark.png` (1280 x 400, 64,812 and 64,300 bytes, chunks IHDR /
IDAT / IEND only, so no text or time metadata) and
`assets/brand/readme-hero.svg`, generated by `tools/make_icons.py`, drawn
strokes with no font and no GGG imagery (docs/design/0005-brand-mark.md).
README.md:3-6 already shows it in a `<picture>` block and
`tests/test_brand_assets.py::test_readme_hero_and_disclaimer` pins it. The
only addition is an optional 1280 x 640 social card from the same strokes
(GP-07).

### Scans run for this section (2026-11-18, HEAD fb95c3e)

All read-only; no tracked or local config file was changed.

- Identity: `fleet_identity.py check --history --by-class main`: 413
  commits, 0 in all 9 classes. `check --all`: 427 commits clean (16 refs:
  main, 13 lane refs, 2 keep refs). One author / committer tuple over all
  427, its address a GitHub noreply one. 0 lines matching co-authored-by,
  signed-off-by, co-developed-by or "generated with". No remote exists.
- Leaks with the 24 local needles: 0 at HEAD, 0 in history (427 commits).
- F-004 scan, the reviewed set's names: 40 extra needles passed by the
  `AL_LEAK_NEEDLES` environment variable only (1 owner name, 20
  repositories the owner created, 19 forks; 64 needles with the local
  24). Result: owner slot 0 hits; the 20 own-repository slots 0 hits; 18
  of the 19 fork slots 0 hits; ONE fork slot 3 hits at HEAD and the same
  3 in history. That slot is the name of a widely forked public upstream
  project, cited under its upstream address in a research note that
  predates the review. It does not identify the reviewed set.
- Verdict for Q-25: clean; no rewrite request to MAIN. The call on the
  one fork slot is taken here and is for this session's ruling step to
  confirm; it reverses if the operator wants that upstream name out of
  the tree (then a HEAD edit plus a rewrite request to MAIN, repository
  kept private meanwhile).
- The 0056 draft in history (commit 6901a64) already called the set
  "repo A to repo G": a diff against the verified note finds no owner or
  repository name removed.
- Binaries: the two hero PNGs re-read (above); 0057 found all 12 tracked
  PNGs free of metadata chunks and no blob at HEAD over 500 KB.
- Re-run by the verifier at HEAD 23cc518 (2026-11-18): identity
  `check --history --by-class main` 416 commits, 0 in all 9 classes;
  `check --all` 430 commits clean; leak sweep `--tree` and `--history`
  rc 0, `ARMED needles=24`. The refs besides main are 13
  `refs/fleet-lanes/*` and 2 `refs/al/keep/*` (custom namespaces, not
  branches). The operator's GitHub login is already one of the 24 local
  needles (checked as a boolean, never printed), which is why GP-10's
  allow entry is needed. The 40-needle set-name scan was not re-run here
  (GP-01 re-runs it on the commit that is pushed).

## Work packages

Common to all: no package touches `server/al/state.py` or `web/app.js`.
Ledger files (ROADMAP.md, CLAUDE.md, AL-NEXT-SESSION.txt, the docs
indexes) are written only by the wave integrator (F-017), except GP-02,
which this session's own later step lands. `<ID>` is the caller's owner id
(FLEET item 16). `$R` is `<owner>/AshLight` (section "Repository
settings").

### GP-01 Arm the set-name needles and re-run every scan before the push

- Goal: the scans above hold on the exact commit that is pushed, and the
  reviewed set's names guard every later commit.
- Files touched: `config/leak_needles.json` (gitignored, local only): add
  the set owner's name (the owner of the third-party set reviewed in
  0056, not the operator) and the 20 own-repository names (24 to 45
  needles), plus any distinctive plugin display name of the 7 reviewed
  repositories that differs from its repository name, read from each
  clone's manifest (F-004 "owner, repository and distinctive plugin
  names"; a display name that is a common word or equals a public
  upstream project's name is skipped). Do NOT add fork names that equal a
  public upstream project's name: the tree legitimately names such
  projects. Names come from the remotes and manifests of the clones under
  `<sidecar>\Scratch\tp-review` and the set owner's public repository
  list; they are never written to a tracked file, a note or a commit
  message. No tracked file changes.
- Acceptance tests: `python tools/leak_sweep.py --tree` rc 0 and
  `--history` rc 0, both printing `ARMED needles=<N>` with N >= 45 (the
  sweep prints this line on stderr);
  `python ops/fleet_kit/fleet_identity.py check --history --by-class main`
  prints 0 for all 9 classes; `check --all` prints clean; `git grep -i`
  for the set owner's name over HEAD is empty. Counts go into the GP-09
  progress file, never the names.
- ZERO-CLICK: an agent step; the armed needles then run in pre-commit,
  commit-msg and pre-push with no act.
- Size: S. Depends on: nothing. Findings: F-004 (Q-25).
- Parallel with: everything. Hotspots: none.

### GP-02 Guarded push, rules text and the decision record

- Goal: the tree says and enforces "guarded push" instead of "local only".
- Files touched: `.githooks/pre-push` (text in section "pre-push hook");
  `tests/test_fleet_kit_conformance.py` (the test at :152-165);
  new `tests/test_pre_push_hook.py`; `CLAUDE.md` (tree-specific part
  only: the Public-repo hygiene section, and one new Settled line);
  `tools/al_loop.py` (docstring :52-57, comment :204, docstring
  :1284-1285; no logic change; the file has 1,757 lines and
  `tests/test_loop_split.py:126` asserts fewer than 1,760, so replace
  lines, do not add); `tools/loop_inbox.py:129-130` (prompt text "(AL is
  local only: no remote, no gh)" becomes "(a lane gets no gh)");
  `tools/al_lane.py:54-55` (comment becomes "Dependabot bumps are
  re-applied in the main checkout by tools/dependabot_reapply.py, so no
  gh is granted to a lane.") and `tests/test_p163_lane_tools.py:37`
  (comment `# AL is local only` becomes `# gh stays out of lanes`; the
  assert stays); `.claude/commands/done.md` (:2, :33, :100: push main
  through fleet_gitlock when origin exists) and
  `.claude/agents/adjudicator.md:23` (drop "no push while the repo is
  local only"); new `docs/decisions/NNNN-go-public.md`;
  `docs/decisions/README.md` index line; `ROADMAP.md:2059-2061` (close
  the OPERATOR row as superseded by the GP rows).
- Acceptance tests: `python -m pytest -q tests/test_pre_push_hook.py
  tests/test_fleet_kit_conformance.py tests/test_al_loop_gate_cache.py
  tests/test_loop_split.py tests/test_p163_lane_tools.py
  tests/test_ascii_lf.py` green; `git grep -n "refuses every
  push\|AL_ALLOW_PUSH\|NO remote" -- CLAUDE.md tools .githooks .claude`
  is empty; `git grep -n -i "AL is local only\|repo is local
  only\|never push, local only\|AL: local only" -- CLAUDE.md tools
  .githooks .claude` is empty (the log string `push skipped: local only`
  at tools/al_loop.py:1290 and its test stay on purpose).
- ZERO-CLICK: after it lands a push needs no flag and the loop's push
  worker pushes by itself.
- Size: S. Depends on: nothing. Findings: F-016 (0057 R1, R2, R6); Q-23.
- Parallel with: GP-03 to GP-08. Hotspots: CLAUDE.md, ROADMAP.md.
- Note: if the harness denies edits under `.claude/`, the two wording
  changes there move to the operator batch
  (docs/plan/09-operator-acts.md, OA-6) and the rest
  lands; CLAUDE.md outranks both files.

### GP-03 NOTICE and the licence record

- Goal: NOTICE reads as a public file.
- Files touched: `NOTICE` (line 2 becomes `Copyright 2026 The AshLight
  authors`; lines 6-7 become "ops/fleet_kit/ is a vendored development
  kit (Apache-2.0), unmodified, under its own LICENSE and NOTICE in that
  directory."; lines 12-13 become "ops/loop/slots.py is a shared
  concurrency helper from the same development kit family,
  Apache-2.0."); new `docs/decisions/NNNN-licence-and-notice.md`.
- Acceptance tests: `git grep -n "the operator\|MAIN" -- NOTICE` empty;
  `python -m pytest -q tests/test_ascii_lf.py tests/test_leak_sweep.py`.
- ZERO-CLICK: documentation only.
- Size: S. Depends on: nothing. Findings: F-009 (0057 R5).
- Parallel with: all. Hotspots: none.

### GP-04 Fresh-clone proof

- Goal: the suite passes in a clone with no local state, so the first CI
  run is green.
- Files touched: `tests/` only as needed (a skip with a stated reason or
  a tmp fixture; never a weakened guard).
- Steps: `git clone --branch main --single-branch --no-local .
  "<sidecar>\Scratch\go-public\fresh"`; in the clone no
  `config/local.json`, no needle file, no hooks path, no
  `fleet.operatorIdent`; environment `AL_SIDECAR_ROOT` pointing at
  `<sidecar>\Scratch\go-public\fresh-sidecar`, `AL_LEAK_NEEDLES` unset,
  `ELECTRON_SKIP_BINARY_DOWNLOAD=1`; run the suite once through
  `fleet_suite_gate.py run --owner <ID> -- <a scratch runner that sets
  the clone as cwd and runs python -m pytest -q>`; then `npm ci --prefix
  app --ignore-scripts` and `npm test --prefix app` in the clone.
- Acceptance tests: rc 0 with the main checkout's pass count minus the
  documented skips; the skip list is in the commit message; a second run
  under Python 3.11 if a 3.11 interpreter is installed (CI covers it
  otherwise).
- ZERO-CLICK: an agent step.
- Size: M. Depends on: F-001 (a clone core must never discover the live
  Client.txt). Findings: F-008 (0057 R4).
- Parallel with: GP-02, GP-03, GP-06, GP-07, GP-08. Hotspots: none.
- Floor: test cores replay fixtures only; the operator may be playing.

### GP-05 CI workflows and their lint test

- Goal: `ci` and `fleet-identity-guard` exist, are pinned, and a test
  keeps them that way.
- Files touched: `.github/workflows/ci.yml` (text below);
  `.github/workflows/fleet-identity-guard.yml` (byte copy of
  `ops/fleet_kit/fleet_identity_guard.yml`; never edited); `.gitattributes`
  (add `.github/workflows/fleet-identity-guard.yml -text`);
  `requirements-dev.txt` if F-019 has not added it (pytest 9.2.0, the
  version the main checkout runs, with `--hash` lines for pytest AND
  every transitive dependency it pulls on Windows (iniconfig, packaging,
  pluggy, colorama, pygments at the time of writing; read the list from
  a scratch venv `pip install pytest==9.2.0` then `pip freeze`), because
  `--require-hashes` refuses any unhashed requirement); new
  `tests/test_ci_workflow.py`.
- Acceptance tests: `tests/test_ci_workflow.py` (text parse, stdlib only)
  asserts: every `uses:` line ends in `@<40 hex> # v<tag>`; top-level
  `permissions:` is exactly `contents: read`; no `secrets.`, no
  `pull_request_target`, no `web_data`; job id and name `test` on
  `windows-2025`; job `test-newest` exists and is not named `test`; the
  guard copy is byte-identical to the kit file; every name in
  `requirements-dev.txt` carries a `--hash=sha256:` line. (The ruleset
  context check lives in GP-13's test, so GP-05 does not wait for GP-13.)
  After GP-09: `gh run list --repo "$R" --branch main --limit 4 --json
  workflowName,conclusion` shows both `success`.
- ZERO-CLICK: runs on every push and pull request.
- Size: M. Depends on: GP-04; F-019 (Node floor 22.12.0,
  requirements-dev.txt). Findings: F-013 (0057 R3; CI halves of 0046 R9
  and 0052 R7).
- Parallel with: GP-06, GP-07, GP-08. Hotspots: none.
- Action pins (0057 GH-REL-API, re-read before use with `gh api
  repos/actions/<name>/commits/<tag> --jq .sha`): checkout v7.0.1
  3d3c42e5aac5ba805825da76410c181273ba90b1; setup-python v7.1.0
  6d4fd22b20465ccc0f7354476588e8df7c9ca0e0; setup-node v7.1.0
  949feb2413d6458794dcd2491c4babbbce0c15c1.

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  test:
    name: test
    runs-on: windows-2025
    timeout-minutes: 30
    env:
      ELECTRON_SKIP_BINARY_DOWNLOAD: "1"
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.11"
      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0
        with:
          node-version: "22.12.0"
      - name: sidecar under the runner temp folder
        shell: pwsh
        run: Add-Content $env:GITHUB_ENV "AL_SIDECAR_ROOT=$env:RUNNER_TEMP\al-sidecar"
      - name: dev requirements (hash pinned)
        run: python -m pip install --require-hashes -r requirements-dev.txt
      - name: python tests
        run: python -m pytest -q
      - name: node modules (no scripts, no Electron binary)
        run: npm ci --prefix app --ignore-scripts
      - name: node tests
        run: npm test --prefix app
      - name: leak sweep (structural arm; no needle file in CI by design)
        run: python tools/leak_sweep.py --tree
      - name: PowerShell 5.1 parse of scripts
        shell: powershell
        run: |
          $bad = 0
          Get-ChildItem scripts -Filter *.ps1 | ForEach-Object {
            $e = $null
            [void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$null, [ref]$e)
            if ($e.Count) { $bad++; Write-Output "$($_.Name): $($e[0].Message)" }
          }
          exit $bad
```

  The `runner` context is not available in a job-level `env`, hence the
  step that writes `AL_SIDECAR_ROOT`. 0046 R3 asks CI to run the floor
  and the newest branch, so GP-05 also adds a second, NOT required job
  `test-newest` (name `test-newest`, the same steps with Python "3.14"
  and Node "24", `continue-on-error: true`); a matrix is avoided so the
  required context stays the plain name `test`.

### GP-06 Community files

- Goal: community profile health 100 and forms that keep reports safe.
- Files touched: `CODE_OF_CONDUCT.md` (own short text: be respectful, no
  harassment, stay on topic, no requests for features outside the Game
  ToS floor, the maintainer may hide or close; report privately through
  the Security tab's private report; no email address);
  `.github/ISSUE_TEMPLATE/bug.yml` (asks for the AshLight version,
  Windows version, what happened, and the redacted Checks report of
  decision 0040 in a text area, with a required "I read the report
  before pasting it" checkbox (0051 R6); an optional text area for the
  ledger shape list, English clients only (F-075, 0051 Q5); states
  "never attach Client.txt, game files, memory dumps or screenshots of
  the game");
  `.github/ISSUE_TEMPLATE/feature.yml` (asks what the player wants to
  see and which line of "What AshLight never does" it might touch);
  `.github/ISSUE_TEMPLATE/config.yml` (`blank_issues_enabled: false`; the
  security contact link is added by GP-10 when the address exists);
  `.github/pull_request_template.md` (the two gate commands; a floor
  checklist; the sentence "Pull requests are proposals: an accepted
  change is re-applied by the maintainer as their own commit and this
  pull request is closed with a link to it; you are credited in the
  release notes.").
- Acceptance tests: `python -m pytest -q tests/test_community_files.py
  tests/test_ascii_lf.py tests/test_leak_sweep.py`; new
  `tests/test_community_files.py` (its own file, so GP-05, GP-06 and
  GP-08 never share a test file) asserts `bug.yml` and `feature.yml`
  hold top-level `name:` and `body:`, `bug.yml` has a `checkboxes` item
  with `required: true`, `config.yml` holds `blank_issues_enabled:
  false`, CODE_OF_CONDUCT.md and the PR template exist and hold no `@`
  address; after GP-12: `gh api "repos/$R/community/profile" --jq
  .health_percentage` prints 100.
- ZERO-CLICK: documentation only.
- Size: S. Depends on: nothing. Findings: F-075 (0057 R11; issue half of
  0051 R6).
- Parallel with: all. Hotspots: none.
- Fallback: if health stays under 100 because the own text is not
  recognised, adopt the Contributor Covenant 2.1 text (CC BY 4.0, licence
  check recorded in the GP-03 decision) with the same private route.

### GP-07 README, SECURITY, CONTRIBUTING: the public pass

- Goal: a stranger understands what the repository is and how it is run.
- Files touched: `README.md` (new section "How this repository is run":
  CLAUDE.md, ops/, AL-NEXT-SESSION.txt, ROADMAP.md and docs/ are the
  development process: AI-assisted, operator-reviewed, every commit gated
  by tests, an identity check and a leak sweep; a reader may ignore them;
  one line that the development loop, not the app, reads public web pages
  unattended (decisions 0025, 0044); "Releases: none yet, install from
  source" until plan 05 ships one); `SECURITY.md:5` (present tense, drop
  "Once this repository is public"); `CONTRIBUTING.md` (the re-apply
  policy; the hooks are the maintainer's gates and are not installed by a
  clone, CI runs the same checks; `.claude/settings.json` hooks apply
  only to Claude Code users after its trust prompt); `tools/make_icons.py`
  and `assets/brand/social-preview.png` (optional 1280 x 640 card from
  the hero strokes; no font, no GGG imagery); `tests/test_brand_assets.py`
  (the card has only IHDR / IDAT / IEND chunks).
- Acceptance tests: `python -m pytest -q tests/test_brand_assets.py
  tests/test_ascii_lf.py tests/test_leak_sweep.py`; README still holds
  the non-affiliation sentence verbatim (pinned by test_brand_assets).
- ZERO-CLICK: documentation only.
- Size: S. Depends on: F-019 and F-020 for the quick-start, Node-floor
  and client wording (those findings own the "Quick start (Windows)" section,
  README.md:60-114; this package adds its section after them). Findings: F-020 (0057 R10 half), 0057
  F8 (c), (d), F9, F12.
- Parallel with: GP-02 to GP-06, GP-08. Hotspots: none of the four;
  README.md is shared with F-019, F-020, F-126: run after F-020.

### GP-08 Dependabot config file

- Goal: the config is in the tree before the remote exists.
- Files touched: `.github/dependabot.yml` (below); new
  `tests/test_dependabot_config.py` (key lint: version 2, two
  ecosystems, weekly, limit 2, cooldown keys, the exclude path).
- Acceptance tests: `python -m pytest -q tests/test_dependabot_config.py
  tests/test_ascii_lf.py`.
- ZERO-CLICK: GitHub opens the pull requests; GP-14 handles them.
- Timing: version updates run as soon as the file reaches main, on the
  private repository too, so bump pull requests may open right after
  GP-09; security updates open as soon as an alert exists once settings
  C enable them. Open pull requests are harmless: nothing on GitHub
  merges them (auto-merge off, no one merges); they wait for GP-14.
- Size: S. Depends on: nothing. Findings: F-081 (config half; 0057 R8,
  0046 R9).
- Parallel with: all. Hotspots: none.

```yaml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/app"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 2
    cooldown:
      default-days: 3
      semver-major-days: 14
    groups:
      npm-all:
        patterns: ["*"]
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 2
    cooldown:
      default-days: 3
    exclude-paths:
      - ".github/workflows/fleet-identity-guard.yml"
    groups:
      actions-all:
        patterns: ["*"]
```

  `app/package.json` has one dependency, electron 45.3.3 (exact pin, named
  in CLAUDE.md). An electron bump from Dependabot is only a signal: the
  pin moves through the Electron bump procedure (F-130, F-044), which
  GP-14 calls.

### GP-09 Create the private repository, first push, CI green

- Goal: main is on GitHub, private, with both workflows green.
- Files touched: none tracked (repository and local git config only).
- Steps: section "Before the first push (gates, in order)", gates 1-12.
- Acceptance tests: `gh repo view "$R" --json visibility --jq
  .visibility` prints PRIVATE; `git ls-remote --heads --tags origin`
  lists refs/heads/main and otherwise only `refs/heads/dependabot/*`
  (if GP-08 rode the push); `git rev-parse main` equals `git rev-parse
  origin/main`; both workflow runs `success` on that commit.
- ZERO-CLICK: agent steps; `gh` is already signed in.
- Size: S. Depends on: GP-01, GP-02, GP-03, GP-04, GP-05 (GP-06 to GP-08
  may ride the same push or a later one). Findings: F-021 steps 1-3;
  Q-23.
- Parallel with: nothing (one push). Hotspots: none.

### GP-10 The project's own address in tracked files

- Goal: Q-24's one exception, enforced by the sweep.
- Files touched: new tracked `config/public_repo.json`
  (`{"repo": "<owner>/AshLight"}`, the single source also read by the
  update check of F-055); `tools/leak_sweep.py` (before both arms run on
  a line, blank each exact, case-sensitive occurrence of
  `github.com/<repo>` and of `<repo>` bounded by non-word characters;
  nothing else of the repository owner (the operator's GitHub login,
  already a local needle) is allowed, so the login alone or with another
  repository name still hits its needle slot; the config file itself is
  scanned the same way); `tests/test_leak_sweep.py` (with a made-up
  needle and a made-up repo value: the address passes; the login alone
  HALTs; login plus another repository name HALTs; a missing or
  malformed config file changes nothing); `README.md`, `SECURITY.md`,
  `.github/ISSUE_TEMPLATE/config.yml` (real links: clone address, the
  Security tab's private report link).
- Acceptance tests: `python -m pytest -q tests/test_leak_sweep.py`;
  `python tools/leak_sweep.py --tree` rc 0 ARMED with the address in
  README; `git grep -i` for the login finds only lines holding the full
  address.
- ZERO-CLICK: documentation and one config value.
- Size: S. Depends on: GP-09 (the address must exist). Findings: F-020,
  F-055 (Q-24).
- Parallel with: GP-11. Hotspots: none; `tools/leak_sweep.py` is a
  single-writer file for this package.

### GP-11 Description, topics, features

- Goal: an honest first line and discoverability, set before the flip.
- Files touched: none (settings; commands in "Repository settings" A, B).
- Acceptance tests: the two read-backs in "Repository settings" match
  the planned description, the 10 topics and the feature switches.
- ZERO-CLICK: agent step.
- Size: S. Depends on: GP-09. Findings: F-079 (0057 R9).
- Parallel with: GP-10. Hotspots: none.

### GP-12 Flip to public

- Goal: the repository becomes public only when every flip gate holds.
- Files touched: none tracked; the flip agent writes the gate read-backs
  into its progress file and the hand-off.
- Flip gates, all read back on the commit at origin/main:
  1. Every other P0 finding of the plan has landed (F-001 to F-016
     except F-006, which is this gate; Q-23). The hard minimum is F-006:
     the commits of F-001, F-002 and F-005 are in
     `git log origin/main`, and `python -m pytest -q
     tests/test_http_security.py tests/test_tc_code.py
     tests/test_no_discovery.py` is green.
  2. GP-01 re-run on that commit: identity 0, leaks 0, set names 0.
  3. Both workflows `success` on that commit.
  4. GP-06, GP-07, GP-10, GP-11 landed.
  5. Q-05: the operator's message to poe.ninja is sent, or the operator's
     written skip is recorded (operator act OA-2). The flip does not wait
     for poe.ninja's answer.
  6. No game screenshot, GGG art or funding file in the tree: `git
     ls-files` has no FUNDING file; README images are only
     `assets/brand/*`.
- Then: `gh repo edit "$R" --visibility public
  --accept-visibility-change-consequences`.
- Acceptance tests: `gh repo view "$R" --json visibility --jq
  .visibility` prints PUBLIC; an anonymous `git ls-remote --heads --tags
  "https://github.com/$R"` lists refs/heads/main and otherwise only
  `refs/heads/dependabot/*`.
- ZERO-CLICK: the flip happens by itself once the gates read green.
- Size: S. Depends on: GP-06, GP-07, GP-09, GP-10, GP-11, all P0
  packages, OA-2.
  Findings: F-006, F-021 step 4, F-046 (flip half).
- Parallel with: nothing. Hotspots: none.

### GP-13 Protection and security settings, read back

- Goal: the settings of Goal 7, as tracked files plus read-backs.
- Files touched: new `ops/github/ruleset-main-protect.json`,
  `ops/github/ruleset-main-checks.json`,
  `ops/github/ruleset-release-tags.json`, `ops/github/security.json`,
  `ops/github/branch-protection-fallback.json` (all in "Repository
  settings"); new `tests/test_repo_settings_files.py` (each file is valid
  JSON; only the checks ruleset has a bypass actor; its contexts and the
  fallback file's contexts equal the `name:` of the job in ci.yml and of
  the job in fleet-identity-guard.yml; each required check carries
  `integration_id` 15368; the protect and tag rulesets have no bypass).
- Acceptance tests: every read-back in "Repository settings" C to F
  matches; then one ordinary session push of a fresh commit lands with
  rc 0 (`git rev-parse main` equals `origin/main` afterwards); `gh api
  "repos/$R/rules/branches/main" --jq '[.[].type] | sort | join(",")'`
  prints `deletion,non_fast_forward,required_status_checks`.
- ZERO-CLICK: agent step; later pushes need nothing.
- Size: S. Depends on: GP-12 (rulesets and free secret scanning need a
  public repository on a personal account; 0057 Open questions) and the
  check names seen green in GP-09. Findings: F-021 steps 5-6.
- Parallel with: GP-14, GP-15, GP-16. Hotspots: none.
- Also: report the two peer gaps (Dependabot security updates on in 1 of
  7 public peers; the identity guard required in 0 of 7) in the next
  note to MAIN (F-203 owns the note).

### GP-14 Dependabot re-apply lane

- Goal: bump pull requests are re-applied locally and closed, never
  merged on GitHub.
- Files touched: new `tools/dependabot_reapply.py` (stdlib; `list`,
  `apply <n>`, `close <n>`, `run` = all three for every open bump); a
  launch of `run` as a detached worker at most once per 24 h from the
  loop tick, placed in a `tools/loop_*.py` mixin, never in
  `tools/al_loop.py` (3 lines under its cap); new
  `tests/test_dependabot_reapply.py`.
- Where it runs: in the MAIN checkout, like the loop's push worker,
  never inside a lane worktree (`tools/al_lane.py:51`: commits and
  merges are done by the main session). No headless Claude lane gets a
  gh grant: `tests/test_p163_lane_tools.py:37` keeps asserting that code
  lanes hold no `Bash(gh` tool. While the loop stays HALTed (until
  F-078), a session runs `python tools/dependabot_reapply.py run`.
- Behaviour: `gh pr list --repo "$R" --author "app/dependabot" --state
  open --json number,title,headRefOid,files`; for each: read the changed
  files; an npm bump re-runs the pin procedure locally (F-130, F-044:
  lockfile regenerated with `npm install --prefix app --package-lock-only
  --ignore-scripts`, `npm audit signatures`, the 3-day age rule of
  F-037); an action bump rewrites the `uses:` SHA and tag comment in
  `ci.yml` after re-reading the SHA with gh; gates; one commit as the
  operator through fleet_gitlock (no trailer; the subject names the
  dependency and versions); push main through fleet_gitlock (the
  guarded hook applies); `gh pr close <n> --repo "$R" --comment
  "Applied locally as <sha>."`. A pull request that touches
  `fleet-identity-guard.yml` is closed with "This file is vendored; the
  change is reported upstream." and reported to MAIN. The pull request's
  red `fleet-identity-guard` check is expected.
- Acceptance tests: on a recorded pull-request fixture (JSON plus a tmp
  git repo with a bare remote) the tool yields exactly one local commit
  whose author and committer equal the tmp `fleet.operatorIdent`, no
  trailer line, one push to main and one close comment (gh replaced by a
  recording fake); a guard-file pull request yields no commit and one
  close comment; with fake deps the tick launches the worker once per
  24 h; `python -m pytest -q tests/test_dependabot_reapply.py
  tests/test_p163_lane_tools.py tests/test_loop_split.py` green.
- ZERO-CLICK: the loop tick runs it once F-078 resumes the loop; until
  then the session that handles go-public runs it. Bump pull requests
  can open right after GP-09 (GP-08 timing); they wait unmerged.
- Size: M. Depends on: GP-09, F-037; F-130 for electron bumps (the only
  npm dependency is electron, `app/package.json` devDependencies; its
  13 lockfile entries can still get security bumps). Findings: F-081
  (0057 R8, 0046 R9).
- Parallel with: GP-10 to GP-13, GP-15, GP-16. Hotspots: none.

### GP-15 Release settings

- Goal: the repository is ready for plan 05's first `v*` tag.
- Files touched: none tracked beyond GP-13's tag ruleset file.
- Steps: "Repository settings" G (immutable releases; the tag ruleset).
  The release workflow, SHA256SUMS, SBOM, attestation and changelog are
  plan 05 (F-048, F-074, F-076, F-101, F-148); no release exists at the
  flip and the README says so.
- Acceptance tests: `gh api "repos/$R/immutable-releases" --jq .enabled`
  prints true; `gh api "repos/$R/rulesets" --jq '.[].name'` lists
  `release-tags`; `gh release list --repo "$R"` is empty until plan 05.
- ZERO-CLICK: agent step; tags are pushed by the release procedure.
- Size: S. Depends on: GP-12. Findings: F-021 (immutable releases),
  F-076 (prerequisite), 0053 R6.
- Parallel with: GP-13, GP-14, GP-16. Hotspots: none.

### GP-16 Public-surface tidy

- Goal: three small cleanups after the flip.
- Files touched: `tests/fixtures/inbox_p164/` and
  `tests/test_loop_inbox_p164.py` (a synthetic note of the same shape
  replaces the copied ORDER note); `moon_sync_inbox/.gitkeep`,
  `moon_sync_outbox/.gitkeep` and `.gitignore` only if `fleet_inbox`
  tolerates a missing folder (read it first; otherwise leave them);
  `.claude/settings.json:17` (the stale `tools/ash_lane.py` permission:
  operator batch, OA-6).
- Acceptance tests: `python -m pytest -q tests/test_loop_inbox_p164.py`
  green; `git ls-files "moon_sync_*"` empty if moved.
- ZERO-CLICK: agent step.
- Size: S. Depends on: nothing (after the flip by order only). Findings:
  F-200 (0057 R12).
- Parallel with: GP-13 to GP-15. Hotspots: none.

## Order

Critical path:

1. GP-02 (this session's later step: hook, CLAUDE.md, decision).
2. In parallel: GP-03, GP-06, GP-07 (after F-020), GP-08, and the P0
   security work F-001, F-002, F-005 (owned by the security section).
3. GP-04 (needs F-001), then GP-05 (needs GP-04 and F-019).
4. GP-01 re-run on the commit to push, then GP-09 (private, first push,
   CI green).
5. In parallel: GP-10, GP-11, GP-14 (bump pull requests may already be
   open; they wait unmerged); meanwhile the remaining P0 findings land
   and the operator sends the Q-05 message (OA-2).
6. GP-12 (flip), then at once GP-13.
7. In parallel: GP-15, GP-16.

Dependency check (no cycle): GP-01, GP-02, GP-03, GP-06, GP-08, GP-16
need nothing in this section; GP-04 needs F-001; GP-05 needs GP-04;
GP-07 needs F-020; GP-09 needs GP-01 to GP-05; GP-10, GP-11, GP-14 need
GP-09; GP-12 needs GP-06, GP-07, GP-09, GP-10, GP-11; GP-13 and GP-15
need GP-12. No package needs a later one.

What must come first: F-001 before GP-04 (a clone must not find the live
log); GP-02 before any push; GP-05's check names before GP-13's required
checks (a required check that never reported blocks pull requests); the
flip before the rulesets. The headless loop stays HALTed through this
plan (docs/plan/README.md), so every push until F-078 is a session push.

## Before the first push (gates, in order)

Each gate is a command and the read-back that passes it. A red gate stops
the sequence; nothing is skipped.

1. Go recorded: `docs/decisions/NNNN-go-public.md` exists and
   AL-NEXT-SESSION.txt names it.
2. `gh auth status` exits 0 and lists the scopes `repo` and `workflow`
   (verified 2026-11-18). Otherwise OA-1.
3. `git status --short` empty; `git rev-parse --abbrev-ref HEAD` prints
   `main`; `git remote -v` empty.
4. Identity: `python ops/fleet_kit/fleet_identity.py check --history
   --by-class main` prints 0 for all 9 classes; `python
   ops/fleet_kit/fleet_identity.py check --all` prints clean; `git log
   --all --format="%ae %ce" | sort -u` prints one line ending in the
   GitHub noreply domain.
5. Leaks: `python tools/leak_sweep.py --tree` and `--history` both rc 0
   with `ARMED needles=<N>`, N the GP-01 count (45 or more).
6. Binaries: `python -m pytest -q tests/test_brand_assets.py` green; the
   largest blob reachable from main is under 500 KB (`git rev-list
   --objects main | git cat-file --batch-check="%(objecttype)
   %(objectsize) %(rest)"`, largest `blob` line).
7. Hook: `python -m pytest -q tests/test_pre_push_hook.py
   tests/test_fleet_kit_conformance.py` green; `git config
   core.hooksPath` prints a path ending in `.githooks` (the local config
   holds the absolute path of the checkout's `.githooks`).
8. Public files: `git grep -n "the operator\|MAIN" -- NOTICE` empty.
9. Fresh clone: GP-04's run is green on this commit or on an ancestor
   with only documentation changes since.
10. CI files: `python -m pytest -q tests/test_ci_workflow.py
    tests/test_community_files.py tests/test_dependabot_config.py` green
    (the last two only if GP-06 / GP-08 ride this push).
11. The CLAUDE.md gates on this commit: the suite through
    `fleet_suite_gate.py run --owner <ID> -- python -m pytest -q` and
    `npm test --prefix app`, both green.
12. Create and push (section "Repository settings" A): create PRIVATE;
    `git remote add origin`; `python ops/fleet_kit/fleet_gitlock.py run
    --owner <ID> -- git push -u origin main`; never `--all`, `--mirror`,
    `--tags` or `--force`. Read back: `git ls-remote --heads --tags
    origin` lists refs/heads/main (plus only `refs/heads/dependabot/*`
    once Dependabot runs); both workflows `success`.

The pre-push hook itself re-runs the identity check and the leak sweep
over all 416-plus commits on this first push (a new remote ref gets no
exemption, tools/leak_sweep.py:243-268); expect one to three minutes.

If gate 4 or 5 ever shows a hit: stop, keep everything local, file one
request to MAIN for a rewrite of the named commits (ORDER only,
`fleet_rewrite.py`); do not rewrite, do not create the repository (Q-25).

## Repository settings

Run from the repo root in Git Bash. `R` is set once:

```sh
R="$(gh api user --jq .login)/AshLight"
```

The description, used below:

```text
Unofficial second-screen dashboard and click-through overlay for Path of Exile 2 on Windows. Reads the game's log file; never touches the game process. Not affiliated with Grinding Gear Games.
```

A. Create and first push (GP-09):

```sh
gh repo create "$R" --private --disable-wiki --description "<the description>"
gh repo view "$R" --json visibility,isEmpty --jq '.visibility, .isEmpty'   # PRIVATE, true
git remote add origin "https://github.com/$R.git"
python ops/fleet_kit/fleet_gitlock.py run --owner <ID> -- git push -u origin main
git ls-remote --heads --tags origin                                      # refs/heads/main
gh run list --repo "$R" --branch main --limit 4 --json workflowName,conclusion,headSha
gh api "repos/$R/commits/main/check-runs" --jq '.check_runs[] | "\(.name) \(.conclusion) \(.app.id)"'
```

   The last line prints the check names (`test`, `test-newest`,
   `fleet-identity-guard`) and the id of the app that reported them; that
   id is the `integration_id` used in D (15368, the GitHub Actions app;
   if the read-back shows another id, the D file is corrected before it
   is applied).

B. Description, topics, features (GP-11):

```sh
gh repo edit "$R" --description "<the description>" --enable-issues=true --enable-wiki=false --enable-projects=false --enable-discussions=false --delete-branch-on-merge=true --enable-merge-commit=false --enable-rebase-merge=false --enable-squash-merge=true --enable-auto-merge=false
gh repo edit "$R" --add-topic "path-of-exile-2,poe2,overlay,companion-app,dashboard,electron,python,windows,path-of-building,loot-filter"
gh repo view "$R" --json description,homepageUrl,hasIssuesEnabled,hasWikiEnabled,hasProjectsEnabled,hasDiscussionsEnabled,mergeCommitAllowed,rebaseMergeAllowed
gh repo view "$R" --json repositoryTopics --jq '[.repositoryTopics[].name] | sort | join(",")'
```

   Expected topics line:
   `companion-app,dashboard,electron,loot-filter,overlay,path-of-building,path-of-exile-2,poe2,python,windows`.
   No homepage until a release page exists. Social preview: no write
   command is known for it; see OA-4.

C. Visibility (GP-12) and security features (GP-13):

```sh
gh repo edit "$R" --visibility public --accept-visibility-change-consequences
gh repo view "$R" --json visibility --jq .visibility                      # PUBLIC
gh api -X PUT "repos/$R/vulnerability-alerts"
gh api -i "repos/$R/vulnerability-alerts"                                 # HTTP 204
gh api -X PUT "repos/$R/automated-security-fixes"
gh api "repos/$R/automated-security-fixes" --jq .enabled                  # true
gh api -X PUT "repos/$R/private-vulnerability-reporting"
gh api "repos/$R/private-vulnerability-reporting" --jq .enabled           # true
gh api -X PATCH "repos/$R" --input ops/github/security.json
gh api "repos/$R" --jq '.security_and_analysis | [.secret_scanning.status, .secret_scanning_push_protection.status, .dependabot_security_updates.status] | join(",")'   # enabled,enabled,enabled
```

   `ops/github/security.json`:

```json
{"security_and_analysis": {"secret_scanning": {"status": "enabled"}, "secret_scanning_push_protection": {"status": "enabled"}}}
```

D. Branch protection and required checks (GP-13):

```sh
gh api -X POST "repos/$R/rulesets" --input ops/github/ruleset-main-protect.json
gh api -X POST "repos/$R/rulesets" --input ops/github/ruleset-main-checks.json
gh api "repos/$R/rulesets" --jq '.[] | "\(.id) \(.name) \(.enforcement)"'
gh api "repos/$R/rules/branches/main" --jq '[.[].type] | sort | join(",")'   # deletion,non_fast_forward,required_status_checks
gh api "repos/$R/rulesets/<id of main-checks>" --jq '.bypass_actors'
gh api "repos/$R/rulesets/<id of main-protect>" --jq '.bypass_actors | length'   # 0
```

   A re-run updates in place: `gh api -X PUT "repos/$R/rulesets/<id>"
   --input <file>`.

   `ops/github/ruleset-main-protect.json` (binds everyone, no bypass):

```json
{
  "name": "main-protect",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "bypass_actors": [],
  "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}]
}
```

   `ops/github/ruleset-main-checks.json` (required checks; the repository
   admin role bypasses so a direct push of fresh commits lands; the
   `integration_id` is confirmed by the A read-back before the file is
   applied; actor id 5 is GitHub's documented id for the admin role,
   confirmed after applying by the `.bypass_actors` read-back and by
   GP-13's fresh push landing):

```json
{
  "name": "main-checks",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}],
  "rules": [
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "do_not_enforce_on_create": false,
        "required_status_checks": [
          {"context": "fleet-identity-guard", "integration_id": 15368},
          {"context": "test", "integration_id": 15368}
        ]
      }
    }
  ]
}
```

   Fallback when the ruleset call is refused or a direct push is rejected
   (classic protection; admins not enforced, so the operator's push
   bypasses the checks while force pushes and deletion stay blocked):

```sh
gh api -X PUT "repos/$R/branches/main/protection" --input ops/github/branch-protection-fallback.json
gh api "repos/$R/branches/main/protection" --jq '[.required_status_checks.contexts, .enforce_admins.enabled, .allow_force_pushes.enabled, .allow_deletions.enabled]'
```

```json
{
  "required_status_checks": {"strict": false, "contexts": ["fleet-identity-guard", "test"]},
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

E. Actions (GP-13):

```sh
gh api -X PUT "repos/$R/actions/permissions" -F enabled=true -f allowed_actions=all -F sha_pinning_required=true
gh api "repos/$R/actions/permissions" --jq '[.enabled, .allowed_actions, .sha_pinning_required] | join(",")'   # true,all,true
gh api -X PUT "repos/$R/actions/permissions/workflow" -f default_workflow_permissions=read -F can_approve_pull_request_reviews=false
gh api "repos/$R/actions/permissions/workflow" --jq '[.default_workflow_permissions, .can_approve_pull_request_reviews] | join(",")'   # read,false
```

F. Dependabot and community (GP-13, GP-14):

```sh
gh api "repos/$R/contents/.github/dependabot.yml" --jq .path              # the config is on main
gh pr list --repo "$R" --author "app/dependabot" --state open --json number,title
gh pr close <n> --repo "$R" --comment "Applied locally as <sha>."
gh api "repos/$R/community/profile" --jq .health_percentage               # 100
```

   Alerts and security updates are the first two pairs in C. A bump pull
   request is never merged: GP-14.

G. Releases (GP-15):

```sh
gh api -X PUT "repos/$R/immutable-releases"
gh api "repos/$R/immutable-releases" --jq .enabled                        # true
gh api -X POST "repos/$R/rulesets" --input ops/github/ruleset-release-tags.json
gh release list --repo "$R"                                               # empty until plan 05
```

   `ops/github/ruleset-release-tags.json`:

```json
{
  "name": "release-tags",
  "target": "tag",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}},
  "bypass_actors": [],
  "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}, {"type": "update"}]
}
```

   The immutable-releases endpoint is UNVERIFIED in this plan (research
   read only the documentation page); if it answers 404 the switch is a
   click in the repository settings (OA-3) and gates only the first `v*`
   tag. A tag is pushed only by the release procedure of plan 05:
   `python ops/fleet_kit/fleet_gitlock.py run --owner <ID> -- git push
   origin v<version>`.

Not in this plan: CodeQL default setup (5 of 7 public peers run it, but
no adopted finding asks for it). A later finding may add it; nothing
here depends on it.

## pre-push hook

### Old behaviour and what pins it

- `.githooks/pre-push:10-24`: refuses every push with "PUSH REFUSED"
  unless `AL_ALLOW_PUSH=1`, in which case it runs the identity check and
  the leak sweep and lets any ref out.
- `tests/test_fleet_kit_conformance.py:152-165`
  (`test_git_hooks_wire_identity_and_leak_sweep`): line 162, `assert
  "exit 1" in pp.rsplit("fi", 1)[-1]`, pins the refusal; the docstring
  (:153-154) says "pre-push refuses (AL is local only)".
- `tests/test_al_loop_gate_cache.py:272-285` pins the loop's "push
  skipped: local only" log line when no origin exists. That behaviour and
  string stay (a checkout without origin still skips); no change.

### New hook, exact text

```sh
#!/bin/sh
# AshLight pre-push: the guarded push (go-public decision, 2026-11-18).
# A push is never refused for being a push. Every push must pass, in order:
#   1. Ref rule: only refs/heads/main and refs/tags/v* leave this machine,
#      each to the same name on the remote. A delete, a moved tag and a
#      non-fast-forward of main are refused. Lane and keep refs stay local.
#   2. Kit v13 (FLEET-COMMON 17) identity gate: fleet_identity.py pre-push.
#   3. Leak sweep over what is being pushed: tools/leak_sweep.py --pre-push.
# There is no override variable. Exit 1 = nothing was pushed.

ROOT="$(git rev-parse --show-toplevel)"
REFS="$(cat)"

check_refs() {
  while read -r lref lsha rref rsha; do
    [ -n "$lref" ] || continue
    case "$lsha" in
      *[!0]*) ;;
      *) echo "pre-push: refused - deleting $rref on the remote is not allowed." >&2
         return 1 ;;
    esac
    case "$rref" in
      refs/heads/main|refs/tags/v*) ;;
      *) echo "pre-push: refused - $rref: only refs/heads/main and refs/tags/v* are pushed." >&2
         return 1 ;;
    esac
    if [ "$lref" != "$rref" ]; then
      echo "pre-push: refused - $lref must go to the same name, not to $rref." >&2
      return 1
    fi
    case "$rsha" in
      *[!0]*)
        case "$rref" in
          refs/tags/*) echo "pre-push: refused - $rref exists on the remote; a release tag never moves." >&2
                       return 1 ;;
        esac
        if ! git merge-base --is-ancestor "$rsha" "$lsha" 2>/dev/null; then
          echo "pre-push: refused - $rref would not fast-forward (fetch first; never force)." >&2
          return 1
        fi ;;
    esac
  done
  return 0
}

printf '%s\n' "$REFS" | check_refs || exit 1
printf '%s\n' "$REFS" | python "$ROOT/ops/fleet_kit/fleet_identity.py" pre-push "$@" || exit 1
printf '%s\n' "$REFS" | python "$ROOT/tools/leak_sweep.py" --pre-push "$@" || exit 1
exit 0
```

### Exact behaviour

- Input: git's ref lines on stdin (`<local ref> <local sha> <remote ref>
  <remote sha>`), remote name and URL as arguments, passed on unchanged.
- Allowed: `refs/heads/main` to `refs/heads/main` as a fast-forward or a
  first push; `refs/tags/v*` to the same tag name when the remote has no
  such tag.
- Refused with exit 1 and one line on stderr: any other remote ref (lane,
  keep, any other branch, a tag not starting with `v`); a local ref
  pushed to a different name (`HEAD:main`, `main:other`); a delete; a
  `v*` tag the remote already has; a main push the remote tip is not an
  ancestor of.
- Then, for an allowed set: `fleet_identity.py pre-push` (unchanged kit
  code; refuses a non-operator or bot author or committer and attribution
  lines; needs `fleet.operatorIdent`), then `leak_sweep.py --pre-push`
  (unchanged; added lines, paths and new messages; a first push scans
  every commit). Either failing refuses the push.
- Fail closed: a missing python, kit file or sweep file ends in exit 1
  (the old `[ -f ... ]` guard around the sweep is gone on purpose).
- `AL_ALLOW_PUSH` is ignored; the string stays only in the new hook test
  (case 10) and in dated documents, never in .githooks/, tools/,
  CLAUDE.md or .claude/.
- An empty push (nothing to send) passes: no ref line, both tools get
  empty input.
- Outside contributors do not install the hook (it needs the operator's
  identity setting); CI runs the same two checks server side.

### Test changes

- `tests/test_fleet_kit_conformance.py::test_git_hooks_wire_identity_and_leak_sweep`:
  keep the two scan asserts (:160-161) and the commit-msg and pre-commit
  asserts; replace line 162 with: `"PUSH REFUSED" not in pp`;
  `"AL_ALLOW_PUSH" not in pp`; `pp.rstrip().endswith("exit 0")`;
  `"refs/heads/main|refs/tags/v*" in pp`; in file order: the `check_refs
  || exit 1` line, then the identity line, then the sweep line, then the
  final `exit 0`. Docstring: "commit-msg
  strips, pre-push guards every push (ref rule, identity gate, leak
  sweep), pre-commit runs the leak sweep over staged lines."
- New `tests/test_pre_push_hook.py` (real git under tmp_path; skipped
  when git or its sh is absent; an empty global git config via
  `GIT_CONFIG_GLOBAL`; a tmp work repo with `core.hooksPath` set to a
  copy of `.githooks`, copies of `ops/fleet_kit/fleet_identity.py` and
  `tools/leak_sweep.py` at the same relative paths, `fleet.operatorIdent`
  and `user.name` / `user.email` set in that repo only, and a bare repo
  as `origin`). Cases, each asserting the push return code and the bare
  repo's refs:
  1. a clean commit on main pushes (rc 0, remote main equals local);
  2. a second clean commit fast-forwards (rc 0);
  3. a commit adding a drive-rooted path string built at run time (never
     spelled in the test file) is refused, remote main unchanged;
  4. a `fleet-lanes/x` branch is refused; `al/keep/x` is refused; a ref
     in the loop's real namespaces, `refs/fleet-lanes/x:refs/fleet-lanes/x`
     and `refs/al/keep/x:refs/al/keep/x`, is refused;
  5. `git push origin :main` (delete) is refused;
  6. `git push origin main:other` and `HEAD:main` are refused;
  7. a tag `v0.0.1` pushes; pushing it again after moving it locally with
     `--force` is refused; a tag `rc1` is refused;
  8. a forced push of a rewound main is refused;
  9. a commit whose author is a bot name is refused by the identity gate;
  10. `AL_ALLOW_PUSH=1` in the environment changes none of 4 to 9;
  11. the hook text is ASCII, LF only, starts with `#!/bin/sh`.
- `tools/al_loop.py` text only. Lines 52-57 become: "Push (unless
  --no-push): with no remote named origin the push is a no-op that logs
  "push skipped: local only". With origin, when main is clean and ahead
  of origin/main the tick launches ONE detached `push` worker (plan 098),
  which under the merge lock needs gates green and leak_sweep --pre-push
  clean, then runs `git push origin main`; .githooks/pre-push re-checks
  the ref rule, the identity gate and the leak sweep on every push."
  Line 204 becomes "The loop's gates are the tracked list (CI runs the
  same commands):". Line 1285 drops "(AL: local only)". No test asserts
  these strings.

## CLAUDE.md Public-repo hygiene

Replace the section from the heading `## Public-repo hygiene (local only
for now)` up to, not including, `## Gates` with exactly this text. It is
true both before and after the repository exists. `NNNN` is the number of
the go-public decision.

```text
## Public-repo hygiene (guarded push)

- Publishing is ordered (operator order 2026-11-17; decision NNNN lifts
  the 2026-11-16 local-only order). The GitHub repository is created
  private and flipped to public when the gates of
  `docs/plan/04-go-public.md` hold. Once it exists its address is the one
  value in tracked `config/public_repo.json`.
- Push policy: only `main` and `v*` release tags leave this machine, each
  to the same name on `origin`, always as
  `python ops/fleet_kit/fleet_gitlock.py run --owner <id> -- git push origin main`
  (a tag: `... -- git push origin v<version>`). Never `--all`,
  `--mirror`, `--tags`, `--force` or a delete; lane and keep refs stay
  local. `.githooks/pre-push` enforces the ref rule and runs the
  fleet_identity pre-push check and `tools/leak_sweep.py --pre-push` on
  every push; it has no override. A session pushes after its gated
  commit; the loop's push worker pushes when main is clean, gated and
  ahead of `origin/main`.
- Nothing is merged on GitHub. A pull request (Dependabot's or a
  contributor's) is re-applied locally as an operator commit, pushed, and
  closed with a one-line comment (FLEET item 17). Dependabot alerts and
  security updates stay on.
- Server side: `.github/workflows/fleet-identity-guard.yml` is a byte
  copy of `ops/fleet_kit/fleet_identity_guard.yml`; the checks
  `fleet-identity-guard` and `test` are required on main. Workflows pin
  every action by full commit SHA, use a read-only token and no secret,
  never turn web data on and never call a GGG or poe.ninja host.
- No absolute machine path, account id, email or sibling tree name in any
  tracked file outside `ops/fleet_kit/`; per-host values live in
  gitignored `config/local.json`. One exception (ruling Q-24,
  2026-11-18): the project's own repository address, the
  `config/public_repo.json` value, may appear in tracked files; the leak
  sweep allows exactly that string and nothing else of its owner.
  `tools/leak_sweep.py` runs in pre-commit, commit-msg and pre-push.
- Repository page: the description and topics say unofficial and use
  'Path of Exile 2' only descriptively; no game screenshot, GGG art or
  logo in the README, social preview or release images; no Sponsors link
  and no FUNDING file (Game ToS floor: branding and revenue rules).
- A history rewrite runs only on MAIN's ORDER via `fleet_rewrite.py`.
- ASCII + LF in every authored file (FLEET item 8); `tests/test_ascii_lf.py`.
- Third-party code: none copied without a license check recorded in
  `docs/decisions/`; GPL / AGPL / NC-licensed tools are studied for ideas only.
```

Also in CLAUDE.md, tree-specific part only (never the FLEET block; its
"pre-push refuses" at item 17 means bot commits and stays):

- Gates section, add one line: "A push runs through
  `python ops/fleet_kit/fleet_gitlock.py run --owner <id> -- git push
  origin main`; never a bare push."
- Settled list, add: "Go public: guarded push of main and v* tags only,
  private first then public on the plan-04 gates, full history, nothing
  merged on GitHub, required checks with one admin bypass, the project's
  own address as the one hygiene exception (decision NNNN). Reverses if:
  the operator withdraws the order, a leak or identity hit is found in
  pushed history, GitHub's rules stop letting an admin push fresh commits
  past required checks, or FLEET item 17 changes."

## Decision text

Full draft for `docs/decisions/NNNN-go-public.md`.

```text
# NNNN - Go public: guarded push, private first, public on gates

Date: 2026-11-18. Source: operator order 2026-11-17 (ultraplan item E:
going public is ordered); research 0057; plan docs/plan/04-go-public.md;
rulings Q-23, Q-24, Q-25.

## Decision

1. AshLight is published on GitHub under the operator's account. This
   lifts the 2026-11-16 order that kept the repository local only.
2. Full history is published. No rewrite and no fresh root: on
   2026-11-18 the identity check found 0 violations in 9 classes over
   416 commits on main (430 on all refs, HEAD 23cc518; GP-02 re-reads and
   updates both counts when it writes this file), one author / committer
   identity with a GitHub noreply address, 0 attribution lines; the leak
   sweep found 0 at HEAD and 0 in history with the needle arm armed,
   including the names of the third-party set reviewed in research 0056
   (owner 0, own repositories 0). A rewrite would run only on MAIN's
   ORDER via fleet_rewrite.py; none is requested.
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
   contributors are re-applied locally as operator commits, pushed, and
   closed with a one-line comment (FLEET item 17). Dependabot alerts and
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
```

## Decisions

Rulings this section relies on:

- Q-23 (go for step 1 and step 4; here: given by the operator's order,
  recorded in the decision above; default if not citable: stay local).
- Q-24 (own address in tracked files; one allow entry; GP-10).
- Q-25 (rewrite only on MAIN's ORDER, only on a needle hit; scan clean).
- Q-05 (message to poe.ninja before the flip; release builds link-only
  until its yes; owned by F-046).
- Q-03 (issues page as default contact once public; owned by F-018).
- Q-22 (no code signing at first; owned by F-148).

Decisions to record (numbers assigned later):

1. Go public: guarded push, private first, public on gates. Full text in
   "Decision text".
2. Licence and NOTICE. Decision: Apache-2.0 for own code; NOTICE holder
   "The AshLight authors"; the kit described as a vendored development
   kit; nothing third-party bundled, data only as attributed sidecar
   snapshots. Alternatives: a named person or handle as holder; MIT.
   Why: names no person, matches 5 of 7 public peers, keeps the patent
   grant. Reverses if: the operator wants a named holder, or a bundled
   dependency forces another licence.
3. Contributions are re-applied, never merged (may be folded into 1).
   Decision: pull requests are proposals; the maintainer re-applies and
   closes; credit goes in release notes. Alternatives: merge on GitHub;
   refuse outside contributions. Why: FLEET item 17 allows one identity
   in history. Reverses if: FLEET item 17 changes.
4. Owned elsewhere, listed so nothing is lost: amendment of decisions
   0015 and 0016 for the default contact (F-018, Q-03); the poe.ninja
   answer or default (F-046, Q-05); release provenance and "unsigned"
   (F-148, Q-22).

## Operator acts

The ordered target is "gh auth login is the only operator act". It holds
for everything up to and including the private push and green CI
(GP-01 to GP-11, GP-14): OA-1 only, and gh is already signed in. One
more act is forced by ruling Q-05 (needs_operator: a message to a third
party in the operator's name) and gates only the public flip: OA-2,
which the operator may replace by a written skip (Q-05 "Reverses if").
OA-3 to OA-6 are conditional or optional and gate neither the push nor
the flip.

- OA-1 `gh auth login`, only if gate 2 fails (`gh auth status` not signed
  in, or the scopes `repo` and `workflow` missing). Why no agent: a
  credential and an OAuth grant. Verified signed in on 2026-11-18, so
  this is expected to be nothing.
- OA-2 One message to poe.ninja asking whether per-install polling at the
  tiered cadence (about 200 overview requests a day) is acceptable or a
  project mirror is wanted; or the operator's written skip (Q-05). Why no
  agent: a message to a third party in the operator's name. Gates only
  the flip (GP-12 gate 5); everything up to the private push runs
  without it. Until it is done the repository stays private.
- OA-3 Only if "Repository settings" G answers 404: switch on immutable
  releases in the repository's settings page. Why no agent: no working
  command. Gates only the first `v*` tag (plan 05).
- OA-4 Optional: upload `assets/brand/social-preview.png` as the social
  preview in the repository's settings page. Why no agent: no write
  command is known for it. Default without it: GitHub's generated text
  card, which carries no art and is floor-safe.
- OA-5 Optional override: a named copyright holder (default "The AshLight
  authors") and another owner or name for the repository (default: the
  signed-in account and `AshLight`), each before GP-09.
- OA-6 Batched with F-057 in docs/plan/09-operator-acts.md: drop the stale
  `tools/ash_lane.py` line from `.claude/settings.json` (F-200), and the
  two `.claude/` wording changes of GP-02 if the harness denies them. Why
  no agent: settings edits are the operator's.
- Not an operator act: creating the repository, the first push and the
  flip (ordered; Q-23 recorded in the decision); a rewrite request (not
  needed; it would go to MAIN, not the operator).

## Risks and fallbacks

- The go cannot be cited when the decision is written. Fallback: Q-23's
  default; GP-02 stays a ready diff, GP-03 to GP-08 still land, GP-09
  waits in docs/plan/09-operator-acts.md.
- First CI run red on the Windows runner (slower, no local state).
  Mitigation: GP-04 first. Fallback: fix forward while private; the flip
  needs green.
- The identity guard is red on the first push (a new branch has an
  all-zero "before"). 0057 ran `ci-check - main` clean over the whole
  history. Fallback: stay private, report the kit defect to MAIN; never
  edit the copy.
- The ruleset bypass does not behave as documented and a direct push is
  rejected. Fallback: the classic protection file (settings D); if that
  also blocks pushes, keep both checks running but not required and
  report it to MAIN (the state of 7 of 7 public peers today).
- A required check name that never reports blocks pull requests.
  Mitigation: names are read from a green run (settings A) before D.
- Private-phase Actions minutes are metered (Windows counts double).
  Mitigation: the loop is HALTed, so only session pushes run CI; keep
  the private phase to days.
- Something leaks after the scans (a later commit). Mitigation: the
  needles armed in GP-01 run in pre-commit, commit-msg and pre-push;
  GP-12 re-runs the full scans on the flip commit.
- A lane ref or a force push by habit. Mitigation: the hook's ref rule
  and the no-bypass ruleset; `--no-verify` stays forbidden.
- The hand-off, ROADMAP and research notes become public within minutes
  of each push once the loop resumes. Accepted (0057 F5; 6 of 7 public
  peers do the same); the leak sweep guards them.
- The public notes describe F-001, F-002 and F-005 in detail. Mitigation:
  the flip waits for the fixes (F-006); a later finding scored 4 or more
  joins that list before any release.
- Community health under 100 with an own code of conduct. Fallback: the
  Contributor Covenant text (GP-06).
- Dependabot opens a security pull request on the vendored guard copy.
  Handling: close it, report to MAIN (GP-14).
- Strangers running a source checkout poll poe.ninja before its answer.
  Mitigation: polling needs the web-data opt-in and a contact; release
  builds make no poe.ninja request until the yes is recorded (F-046).
- An unverified command in "Repository settings" (immutable releases,
  the admin role id, the Actions app id). Each has a read-back
  and a stated fallback; none gates the first push or the flip.

## Verification

Independent verifier, 2026-11-18, HEAD 23cc518. Read-only: no core
started, no Client.txt read, no tracked file other than this one
changed, no pytest beyond the docs lint.

Checked against the yardstick (operator order, item E): README with the
own-art hero (located, nothing to create), LICENSE, CONTRIBUTING,
SECURITY, CODE_OF_CONDUCT, issue and PR templates, CI with pytest and
npm test, the kit guard as a required check, Dependabot alerts and
security updates, bump pull requests re-applied and closed (never
merged), branch protection, topics, description, releases (settings now,
first release in plan 05), identity and leak scans before the first
push, rewrite only on MAIN's ORDER (none needed), the pre-push flip with
the identity check kept, and gh auth login as the only act up to the
private push. Each point maps to a package or an OA.

Claims opened and confirmed true: `.githooks/pre-push:10-24` (refuse-all
plus `AL_ALLOW_PUSH`); `tests/test_fleet_kit_conformance.py:152-165`
with the refusal assert at :162; `tests/test_al_loop_gate_cache.py:272`
("push skipped: local only"); `tools/leak_sweep.py` modes `--tree`,
`--history`, `--pre-push`, `--staged`, `--message`, the `AL_LEAK_NEEDLES`
override, the `ARMED needles=` line, and the full scan of a new remote
ref at :243-268; `ops/fleet_kit/fleet_identity.py` `check --history
--by-class`, `check <range>` (so `check --all` works) and `pre-push`;
`ops/fleet_kit/fleet_identity_guard.yml` (job name
`fleet-identity-guard`, checkout pinned at the same SHA as ci.yml);
`ops/fleet_kit/fleet_rewrite.py` exists and runs only on ORDER;
`tools/al_loop.py` :52-57, :204, :1284-1285 and the 1,760-line cap at
`tests/test_loop_split.py:126` (file at 1,757); `.claude/commands/done.md`
:2, :33, :100; `.claude/agents/adjudicator.md:23`;
`.claude/settings.json:17`; `ROADMAP.md:2059-2061`; NOTICE lines 2, 6-7,
12-13; SECURITY.md:5; README.md:3-6 hero block and
`tests/test_brand_assets.py::test_readme_hero_and_disclaimer`; both hero
PNGs 1280 x 400 with only IHDR / IDAT / IEND; `app/package.json` (electron
45.3.3 the only dependency); pytest 9.2.0 local; `gh auth status` signed
in with `repo` and `workflow`; `fleet.operatorIdent` set (1 value); no
`.github/`, no CODE_OF_CONDUCT, no requirements-dev.txt yet. Scans re-run
(section "Scans run"): identity 416 / 430 clean, leaks 0 / 0.

Rulings and findings: Q-03, Q-05, Q-22, Q-23, Q-24, Q-25 applied as
ruled. F-016 and F-021 are marked "blocked: operator decision Q-23";
the operator's go-public order is that go, recorded by the GP-02
decision (Q-23 record: hand-off). Q-24's owner / name defaults to the
signed-in account (OA-5 may override). Nothing relies on a not-adopted
item: 0057-X1 to X6 and 0046-X2 stay rejected in the text. The flip's
only operator-blocked input is Q-05 (OA-2), as ruled. Game ToS floor:
no screenshot, GGG art, logo, funding link or revenue; CI never turns
web data on; descriptive game name only. FLEET: pushes only through
fleet_gitlock and only as the plan orders; no merge on GitHub; no AI
trailer; no release before plan 05's tag.

Corrected (17):
1. Gate 7: `core.hooksPath` holds an absolute path, not `.githooks`.
2. A cycle: GP-05's test asserted GP-13's ruleset file; moved to GP-13.
3. GP-05, GP-06 and GP-08 all wrote `tests/test_ci_workflow.py` in
   parallel; GP-06 and GP-08 now own `tests/test_community_files.py`
   and `tests/test_dependabot_config.py`.
4. `requirements-dev.txt` with `--require-hashes` must hash pytest's
   transitive dependencies too.
5. `test-newest` (0046 R3 "CI runs the floor and the newest branch") is
   now part of GP-05, not optional.
6. GP-06 bug form: report text area with a required "I read it"
   checkbox (0051 R6) and the optional ledger shape list (F-075, 0051
   Q5) were dropped; restored.
7. GP-14 said the first bump pull request comes 7 days after the flip;
   version updates run as soon as the config reaches main (private
   too) and security updates as soon as an alert exists. GP-14 now
   follows GP-09 and open pull requests wait unmerged (GP-08 timing).
8. GP-14 granted gh verbs to headless Claude lanes, against
   `tools/al_lane.py:51` (commits by the main session) and a narrower
   grant; it now runs in the main checkout, lanes keep no gh, and the
   loop launch lives in a `tools/loop_*.py` mixin (al_loop.py cap).
9. GP-14's ZERO-CLICK ignored the HALTed loop; a session runs it until
   F-078.
10. GP-02 missed three "local only" texts: `tools/loop_inbox.py:129-130`,
    `tools/al_lane.py:54-55`, `tests/test_p163_lane_tools.py:37`; added
    with a second grep in the acceptance.
11. `git ls-remote origin` "exactly HEAD and main" is false once
    Dependabot runs (server-side `dependabot/*` branches, `refs/pull/*`);
    Goal 1, GP-09, GP-12, gate 12 and settings A now use `--heads --tags`
    with the allowed set.
12. GP-01 dropped F-004's "distinctive plugin names"; added (N >= 45).
13. "Owner" meant both the set owner (GP-01) and the operator's login
    (GP-10); each is now named. The login is a local needle (checked).
14. Settings A named an `integration_id` that D never used; D's checks
    now carry 15368 with a read-back, and the admin role id 5 is
    confirmed after applying, not before.
15. GP-12 gate 1 listed F-006 among the P0s it gates; F-006 is the gate.
    GP-12 now also depends on GP-06 and GP-07 (its gate 4).
16. CodeQL was an option outside any adopted finding; now out of scope.
17. Stale numbers and paths: decision counts (416 / 430), README
    quick-start lines (60-114), al_loop docstring lines (1284-1285),
    docs/plan/09 named as `09-operator-acts.md`, hook test case 4 adds
    the real `refs/fleet-lanes/*` and `refs/al/keep/*` namespaces.

Open, not a defect of this section: the 40-needle set-name scan was not
re-run by the verifier (GP-01 re-runs it on the pushed commit); the
immutable-releases endpoint and the admin role id stay UNVERIFIED with
fallbacks; `docs/plan/09-operator-acts.md` does not exist yet (listed
in docs/plan/README.md).
