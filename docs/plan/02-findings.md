# 02 - Findings

Date: 2026-11-18. Ultraplan plan section (docs/plan/README.md); machine-readable source: docs/plan/findings.json.

Status: draft

## Summary

214 findings from 314 recommendations of 25 sources: P0 16, P1 65, P2 69, P3 54, P4 10. 218 ids not adopted (213 rejected by their own files, 5 recommendations). 28 open decisions in 10 clusters; 89 source questions settled or folded into findings.

What matters most, in order:
1. Three confirmed defects are documented in tracked research and must be fixed before anything is public: the token-free /web/ route resolves UNC paths (F-002), a build payload with a NUL byte passes the DTD guard (F-005), and a core with a missing log path tails the live Client.txt outside the opt-in indicator (F-001). F-006 ties the visibility flip to them.
2. Two data-integrity defects sit beside them: runtime files are written without fsync, retry or backup (F-014) and a log break can replay a backlog into thousands of false deaths (F-015).
3. History has not been scanned for the names of the reviewed third-party set (F-004); it is the one go-public unknown.
4. Nothing in the plan runs in parallel safely until the ledger rule (F-017), the loop parser fix (F-024) and safe overlapping tests (F-022) land; HALT comes off only after six checks (F-078).
5. No-scroll Play is measured and fits with every sibling change applied: build F-025, put the budgets under test (F-066), adopt one type scale (F-053) and four tabs (F-067).
6. The build pain has two floor-safe fixes ready (F-042, F-058, one ruling) and one that only the operator can allow (F-071); a current-shape character paste loses every mod today (F-035).
7. The item pain: a staged verdict that answers at once (F-059), a keep-or-vendor verdict with no build (F-060), a worn-gear baseline (F-070) and an honest caveat on every verdict (F-043).
8. Prices are silently blocked today without a typed contact (F-018) and refresh only while the page is open (F-036); league identity must be ready before 2026-12-11 (F-031).
9. Go-public is about two days of agent work plus the operator's go: guarded push and rules (F-016), CI (F-013), fresh-clone proof (F-008), then F-021; a stranger's source install is broken until F-019.
10. Deployment like the reference app is one design now (per-user home, version folders, pinned runtimes, install line, Apps & features entry, staged updates): F-038 first, then F-049, F-047, F-048, F-050, F-063, F-077.
11. No-reminder automation: one watcher frame (F-030), rows filed as add-only files (F-029), a launch gate that opens the 1.0 rows by itself before 2026-12-10 (F-052), policy quotes under watch (F-051).
12. The open live checks close without scheduled operator sessions: log shapes by a consented parse ledger (F-061), RAM and CPU by AshLight's own budget log (F-032), in-game tries by one click each (F-062).
13. Reliability and observability follow as P2: the client survives its own errors, nothing stays down, every log is bounded, Checks explains causes.
14. Dated items: tree hold by 2026-12-08, launch gate by 2026-12-10, league identity by 2026-12-11, Electron 45 line ends about 2027-04-27, GGG registration expected to reopen about 2027-01.
15. The operator is asked once (docs/plan/09): the open decisions below, a handful of one-minute acts and four in-game tries (F-040); every item carries a default.
16. Blocked on others: GGG OAuth registration (F-080, F-149) and an outbound note path to the fleet owner (F-203).

## Method

- Inputs: the eight extraction files of the 25 sources (314 recommendations, 213 rejected ideas, 146 open questions, 168 cut / merge candidates, 111 findings without a recommendation) and the completeness critic's duplicates, conflicts and gaps.
- Merging: recommendations that describe the same change become one finding that keeps every source id; the critic's owner note supplies the design.
- A recommendation that bundles separable work is split: its id sits in the sources of the finding that carries its main part, and the other finding says 'Split:' in its notes.
- Every source id therefore appears exactly once, in a finding's sources or in not_adopted.
- Sources that are not recommendation ids (a finding without a recommendation, a critic gap) are marked as such.
- Floor: read strictly; where its text does not clearly permit something it is treated as outside, and where two files disagree the stricter reading is the resolution unless a ruling says otherwise.
- Settled decisions stand: a part that needs to change one whose Reverses-if is not met is not adopted, or becomes a question when the operator's explicit wants depend on it; amendment lines that only add detail are recorded with the landing commit.
- Tiers: P0 = confirmed defects that leak, lose or corrupt data or weaken a floor guarantee, plus the go-public blockers B1-B7 and what else must hold before the first public push; P1 = the operator's explicit wants (no-scroll Play, few tabs, zero-click, the build and item pains, go-public, deployable like the reference app, no-reminder automation) and what unblocks them; P2 = high player value and hardening; P3 = worthwhile; P4 = defer.
- Rank inside a tier: findings that can start (plan, needs-ruling, operator) before blocked ones, deferred last; then score = impact (H 3, M 2, L 1) divided by effort (S 1, M 2, L 3) plus 0.5 per finding that directly depends on it (at most 3; the three findings that gate all parallel work get the full 3); a finding never ranks before a same-tier finding it depends on; ties keep the order of the operator's want list.
- Rank numbers run through the tiers, so rank 1 is the first P0 finding.
- Dispositions: plan (a session or wave can do it now), blocked (the exact condition is stated), needs-ruling (question ids of the Open decisions section), operator (the act), defer (why).
- Field text (risk, ToS check, acceptance, ZERO-CLICK, files) comes from the owning source unless the merge changed it; R-, F- and B-numbers inside such text are that source's own.

## Tier P0 - defects and what must hold before the first public push

### F-001 - NO-DISCOVERY: a pointed, test or demo core never looks for the live Client.txt

- Rank 1, tier P0; area security; kind fix.
- Action: Core gains discover=False whenever a runtime or log path is passed; a configured but missing client_log stays configured (Checks row), with no Steam-scan fall-through; a consent path that is a file must be named Client.txt; add tests/test_no_discovery.py.
- Impact / effort / risk: H / S / A test relying on discovery fails loudly (the point); 2 discovery tests already monkeypatch.
- ToS check: Narrows Client.txt reading to the instance whose indicator the player sees; reads nothing new.
- Sources: 0050-R0, P01-R2, P01-CORE-LOG-NO-FALLBACK, P01-L13, 0045-R7
- Depends on: nothing
- Acceptance: tests/test_no_discovery.py: a core given a runtime or a log path never calls discovery; a configured missing path with a fake Steam library present stays the configured path and shows a Checks row; a consent path that is a file not named Client.txt is refused; the e2e discovery tests still pass with their monkeypatch.
- ZERO-CLICK: Automatic; missing configured path shows one Checks line ('The Client.txt path in your settings is missing.').
- Disposition: plan
- Notes: Lands first and alone. Split: part (d) of 0050-R0 (supported demo start) is carried by F-034. Go-public blocker B7 (c). If the configured path is gone and discovery finds one other log, AshLight only offers it (0050-Q6).

### F-002 - Serve /web/ from a fixed name map (closes the UNC path leak)

- Rank 2, tier P0; area security; kind security.
- Action: Build the map of files under web/ at start and on each hot-reload scan; answer /web/<name> by exact lookup only, with no filesystem call on request text.
- Impact / effort / risk: H / S / Low; a new web file is served after the next scan.
- ToS check: No floor rule touched; removes an unintended outbound connection.
- Sources: 0045-R1
- Depends on: nothing
- Acceptance: Tails with two leading slashes, a drive name, a stream suffix, a trailing dot and a device name each get 404 while a spy on Path.resolve, os.stat and open sees no request text; every file in web/ still loads.
- ZERO-CLICK: Code change, nothing for the player.
- Disposition: plan
- Notes: Confirmed by probe (0045 F1, score 6). Go-public blocker B7 (a).

### F-003 - Refuse cross-site requests on every route; trim unused allowances

- Rank 3, tier P0; area security; kind security.
- Action: 403 when Sec-Fetch-Site is present and neither same-origin nor none (one exception: Origin null on GET /events for the overlay); send Cross-Origin-Resource-Policy same-origin and Vary; drop /api/state and /api/health from the null-origin list; no version in Server; no OS error text in API errors.
- Impact / effort / risk: M / S / Clients without the header behave as today; overlay file page expected to send cross-site (UNVERIFIED in Electron 45; overlay smoke decides), hence the exception.
- ToS check: Floor untouched.
- Sources: 0045-R3
- Depends on: F-002
- Acceptance: With Sec-Fetch-Site: cross-site every route answers 403 except GET /events with Origin null; with same-origin, none or no header existing suites pass; overlay smoke still reports its feed live.
- ZERO-CLICK: Code change.
- Disposition: plan
- Notes: Should-fix before the visibility flip (0057). First step: log the overlay's real Sec-Fetch-Site and Origin once on a fixture core (research gap: value in Electron 45 is unverified).

### F-004 - Scan full history for the reviewed third-party set's names before any push

- Rank 4, tier P0; area go-public; kind security.
- Action: Add the owner, repository and distinctive plugin names of the set reviewed in note 0056 as needles in the gitignored local config only; re-run the leak sweep over HEAD and every commit reachable from main; record counts (never the names) in plan 04.
- Impact / effort / risk: H / S / A hit in history means the first push cannot be the full history as it stands (Q-25).
- ToS check: No floor rule touched; operator order: the reviewed third-party set stays unidentified.
- Sources: CRITIC-GAP-08
- Depends on: nothing
- Acceptance: Sweep reports 0 needle hits at HEAD and in history, or lists the commits with hits for Q-25; no needle value appears in any tracked file.
- ZERO-CLICK: No operator act unless hits are found.
- Disposition: plan
- Notes: History holds the 0056 draft (commit 6901a64) whose wording the verifier later made generic; the 0057 scan used 24 local needles that do not hold the set's names.

### F-005 - Strict build XML intake: refuse an inflated payload holding a NUL byte

- Rank 5, tier P0; area security; kind security.
- Action: decode_bytes refuses an inflated payload with a NUL byte (codec.py:141); keep the DOCTYPE / ENTITY text search as the second layer; keep the surrogateescape round trip so decision 0021 stays byte exact.
- Impact / effort / risk: M / S / A PoB export in UTF-16, if one ever existed, would be refused with a clear message.
- ToS check: Floor untouched; build text stays user-pasted input parsed locally (decision 0004).
- Sources: 0045-R2
- Depends on: nothing
- Acceptance: Share codes holding UTF-16 documents (both byte orders, with/without BOM) with an entity get 400 from POST /api/build-code and nothing is saved; decision 0021 real-export fixtures still round-trip byte-exact.
- ZERO-CLICK: Code change.
- Disposition: plan
- Notes: Confirmed by probe (0045 F2, score 4). Go-public blocker B7 (b). Forcing a UTF-8 parser is recorded as not a fix.

### F-006 - GP-SECFIX: security fixes green at the flip commit (blocker B7)

- Rank 6, tier P0; area go-public; kind security.
- Action: The visibility flip waits until F-002, F-005 and F-001 have landed and tests/test_http_security.py, tests/test_tc_code.py and tests/test_no_discovery.py pass at the flip commit; plan 04 lists B7 in its go / no-go.
- Impact / effort / risk: H / S / L; R0 (c) makes tests relying on discovery fail loudly (intended).
- ToS check: (c) narrows Client.txt reading to the one instance whose indicator the player sees; (a)(b) remove an unintended SMB connection and entity expansion in pasted build text; no game file/process/input.
- Sources: 0057-R13
- Depends on: F-001, F-002, F-005
- Acceptance: Green at flip commit: 0045 R1 cases in test_http_security (two-slash, drive, stream-suffix, trailing-dot, device tails 404, spy sees no resolve/stat/open of request text; every web/ file loads); 0045 R2 cases in test_tc_code (UTF-16 LE/BE with/without mark with entity -> 400, nothing saved; 0021 fixtures byte-exact); 0050 C27 in test_no_discovery (no spy called, no tailer). Flip agent reads git log for three fix commits and runs those files.
- ZERO-CLICK: Code changes only.
- Disposition: plan
- Notes: Private create, push and CI green may go first; only the flip to public is gated.

### F-007 - Strike the desktop-control unblock path from TEST-LIVE-CLICKS

- Rank 7, tier P0; area docs; kind docs.
- Action: Remove 'or a desktop-tool grant to the lane' from the TEST-LIVE-CLICKS row (ROADMAP.md:54); the row closes by the passive read-back of F-061.
- Impact / effort / risk: H / S / Low.
- ToS check: Enforces 'NEVER send input to the game': a tool that clicks Login or character select synthesizes input.
- Sources: P01-L6
- Depends on: nothing
- Acceptance: The row text no longer names any input path; the static floor scan stays green.
- ZERO-CLICK: No operator act.
- Disposition: plan
- Notes: Split: this is part 2 of P01-R8 (rid carried by F-169). ROADMAP.md is a ledger file: the edit goes through the one writer of F-017.

### F-008 - GP-FRESH: prove the suite in a fresh clone (blocker B4)

- Rank 8, tier P0; area tests; kind test.
- Action: Clone main into the sidecar Scratch (no hooks, no local.json, no needle file, AL_SIDECAR_ROOT in scratch), run the suite through the suite gate and npm test; fix every test that needs local state by a skip or a tmp fixture, never by weakening a guard.
- Impact / effort / risk: H / M / L.
- ToS check: Test cores replay fixtures only; a test that would discover live Client.txt must be pinned to a fixture path (session-6 incident).
- Sources: 0057-R4
- Depends on: F-001
- Acceptance: Fresh-clone run exits 0 with main checkout pass count minus documented skips; skip list recorded in commit.
- ZERO-CLICK: An agent step.
- Disposition: plan

### F-009 - GP-NOTICE: public-facing NOTICE and copyright line (blocker B6)

- Rank 9, tier P0; area go-public; kind docs.
- Action: NOTICE: 'Copyright 2026 The AshLight authors'; describe ops/fleet_kit/ as a vendored development kit (Apache-2.0, own LICENSE and NOTICE); record the licence choice in a decision.
- Impact / effort / risk: M / S / L; operator may override with a named holder.
- ToS check: Apache-2.0 lets others sell forks; AshLight sells nothing and ships no GGG asset; NOTICE keeps non-affiliation text.
- Sources: 0057-R5
- Depends on: nothing
- Acceptance: grep NOTICE finds no 'the operator' and no 'MAIN'; test_ascii_lf passes.
- ZERO-CLICK: Documentation only.
- Disposition: plan

### F-010 - One test file that pins the local HTTP surface

- Rank 10, tier P0; area security; kind test.
- Action: tests/test_security_surface.py: a pinned table of every route (method, token rule, body cap) compared with the routes read from http.py, a pinned reply header set, and the cases of F-002, F-005, F-003, F-001.
- Impact / effort / risk: M / S / None.
- ToS check: Floor untouched.
- Sources: 0045-R8
- Depends on: F-001, F-002, F-003, F-005
- Acceptance: Adding a route without a table row fails the test; every token route answers 401 without the token.
- ZERO-CLICK: Runs in the suite.
- Disposition: plan

### F-011 - Make AshLight's runtime files private, and say so when they are not

- Rank 11, tier P0; area security; kind security.
- Action: Create the runtime dir and config/local.json with an explicit ACL (player, SYSTEM, local admins; inheritance off) through System32 icacls by absolute path; at core start compare the ACLs of runtime dir, repo root and sidecar root and publish a Checks note with a one-line fix; setup.ps1 applies the same.
- Impact / effort / risk: H / M / Changing ACLs on a folder the player shares on purpose; only AshLight-made folders changed, repo only gets the note.
- ToS check: Floor untouched; AshLight's own folders only, never a game file or folder.
- Sources: 0045-R4
- Depends on: nothing
- Acceptance: A test core's runtime dir and token file list exactly three principals when read back; a dir prepared with one more writer yields the Checks note; no launcher starts a program by bare name.
- ZERO-CLICK: (a)-(d) run by themselves; the note for a shared repo folder asks for one command (rewriting ACLs on the player's checkout unasked would be intrusive).
- Disposition: plan
- Notes: Carries the token-reuse hardening (decision 0042 reuse stays safe only with a private runtime dir). Part (e) rides the installer (F-050).

### F-012 - Loopback calls never use a proxy

- Rank 12, tier P0; area security; kind fix.
- Action: Build the health-check opener with an empty ProxyHandler; give the PowerShell health check the same guarantee and test both.
- Impact / effort / risk: M / S / None known.
- ToS check: Floor untouched.
- Sources: 0045-R5
- Depends on: nothing
- Acceptance: With http_proxy set to a closed local port and no no_proxy, the health check is true against a test core and the fake proxy port sees no connection.
- ZERO-CLICK: Code change.
- Disposition: plan
- Notes: First step is the one-line probe of Windows PowerShell 5.1 proxy behaviour for 127.0.0.1 (unverified in 0045).

### F-013 - GP-CI: one Windows CI workflow plus the identity guard (blocker B3)

- Rank 13, tier P0; area go-public; kind infra.
- Action: Add .github/workflows/ci.yml (push / PR to main, read-only token, no secrets, actions pinned by full SHA, windows runner, pytest and node tests) and the byte copy of the kit identity guard as fleet-identity-guard.yml; a test checks pins and permissions.
- Impact / effort / risk: H / M / M: first CI; Windows runner slower.
- ToS check: CI never sets web_data; no GGG or poe.ninja call; nothing touches a game.
- Sources: 0057-R3
- Depends on: F-008
- Acceptance: test_ci_workflow.py asserts 40-hex SHA on every uses:, top-level contents: read, no secrets., windows- runner; guard copy byte-identical to kit. After push: gh run list shows both green on main.
- ZERO-CLICK: Runs on every push.
- Disposition: plan
- Notes: CI never sets web_data and calls no GGG or poe.ninja host. Absorbs the CI halves of 0046-R9 and 0052-R7.

### F-014 - DURABLE-WRITES: one hardened write path for every runtime file

- Rank 14, tier P0; area reliability; kind fix.
- Action: jsonfile write_text / write_bytes: unique temp name, flush and fsync before os.replace, 5 retries over 250 ms on PermissionError, temp removed on failure; one .bak of the last good copy for player-data files, restored when the main file does not parse; all runtime writers use it and write LF.
- Impact / effort / risk: H / M / fsync cost +0.7 ms (2 KB) and +1.0 ms (700 KB) per write; heartbeat stays unsynced.
- ToS check: Local files in runtime dir and AL sidecar only; decision 0036 stands.
- Sources: 0050-R4
- Depends on: nothing
- Acceptance: C7-C11; the three F24 files end in LF.
- ZERO-CLICK: Automatic; one Checks row while a store is unsaved; 'Settings were damaged and restored from the last good copy.'
- Disposition: plan
- Notes: Absorbs CODE-HEALTH-FOLLOWUP item 3 with the corrected CRLF site list (__main__.py:141, keepalive.py:259 and 419, procs.py:223, hotreload.py:283; 0047 F13).

### F-015 - TAIL-HEAL: the log reader never dies and never replays a backlog

- Rank 15, tier P0; area reliability; kind fix.
- Action: Guard each line callback; ensure_tailing restarts a dead reader thread; the same file identity continues from the old offset; after any other break read from byte 0 only if the file is new and at most 64 KB, else jump to the end and run the resume scan; after 20 failed polls publish an 'unreadable' state.
- Impact / effort / risk: H / M / A log recreated by a game restart must still be read from its first line; 64 KB rule covers it.
- ToS check: Same file, same opt-in, read-only, full sharing, fewer bytes read; decision 0008 stands.
- Sources: 0050-R1
- Depends on: nothing
- Acceptance: C1-C6; tailer, e2e and budget suites green.
- ZERO-CLICK: Automatic; one line ('AshLight restarted its log reader.').
- Disposition: plan
- Notes: The three X1 experiments (24 MB replay, dead listener, unretried history write) become its regression tests on fixture logs (research gap: numbers not re-run by the verifier). Covers the reader-restart half of 0051-R3.

### F-016 - GP-HOOK and GP-RULES: the guarded push and 'public' where the tree says local only (B1, B2, B5)

- Rank 16, tier P0; area go-public; kind infra.
- Action: Rewrite .githooks/pre-push to always run the identity pre-push and leak_sweep --pre-push, allow only refs/heads/main and refs/tags/v*, refuse deletes, drop AL_ALLOW_PUSH; in the same commit update the CLAUDE.md Public-repo hygiene section (tree part), the al_loop docstring and ROADMAP.md:2059-2061; the first push is 'git push -u origin main' through fleet_gitlock.
- Impact / effort / risk: H / S / L; identity and leak checks unchanged code.
- ToS check: No floor rule touched.
- Sources: 0057-R1, 0057-R2, 0057-R6
- Depends on: nothing
- Acceptance: Replace refusal assert at conformance:162: no PUSH REFUSED, no AL_ALLOW_PUSH, both scan lines present, ends in exit 0. New test (Git sh, skip if absent): tmp repo + bare remote; clean main commit pushes; planted drive path refused; fleet-lanes/x ref refused; deleting main refused; fleet.operatorIdent in tmp repo only.
- ZERO-CLICK: After it lands the loop pushes on its own.
- Disposition: blocked: the hook and rule text are an operator order (2026-11-16); built and tested now as a ready diff, merged in the first commit after the operator's go (Q-23)
- Notes: The 15 local lane / keep refs never leave: no --all, --mirror or unfiltered --tags.

## Tier P1 - the operator's explicit wants and what unblocks them

### F-017 - FS-LEDGERS: one writer for ledger files, union merge, reserved numbers

- Rank 17, tier P1; area structure; kind infra.
- Action: Packages never edit ROADMAP.md, CLAUDE.md, AL-NEXT-SESSION.txt, docs/design/reviews.log or the docs README indexes; each returns its row flip, review line, Settled line and index line and the wave integrator applies them in one commit; merge=union for reviews.log and the two indexes; decision and research numbers reserved per package.
- Impact / effort / risk: H / S / Union keeps both sides' lines: right for one-line records, wrong for ROADMAP.md (flip and edit of one row would both survive). Union documented for merge/revert/cherry-pick; rebase UNVERIFIED; the loop merges.
- ToS check: No floor rule touched; ledgers hold no game data, nothing reaches game or network.
- Sources: 0047-R1
- Depends on: nothing
- Acceptance: In a scratch clone two branches each append a line to reviews.log and merge with no conflict, both lines present; new test fails on a duplicate decision number or a malformed row.
- ZERO-CLICK: Developer-side only; lands by commit/merge, player does nothing.
- Disposition: plan
- Notes: Unblocks wave 1 and the landing of the plan's rows. First step: scratch-repo check that merge=union also applies during rebase and cherry-pick (research gap).

### F-018 - PRICE-CONTACT-UX: the contact field at the web-data opt-in, and the truth while blocked

- Rank 18, tier P1; area prices; kind feature.
- Action: A write-only contact field in the 'Prices and web data' card (stored only in config/local.json, read back as contact_set); while blocked the switch reads 'On, but prices need a contact first', never 'arrive within a minute'; rates card, movers and the Play price box name this one step; copy says poe.ninja, not 'the trade site'.
- Impact / effort / risk: H / S / Value leaking into a log, settings export or diag report; keep decision 0015 rules (never echoed, NEVER list in settingsio.py:108, masked in diag).
- ToS check: Truthful-User-Agent rule and poe.ninja's contact ask; value stays in a gitignored file, its only source, so decision 0015 stands.
- Sources: 0036-R1, 0038-R3, 0039-R2, 0042-R1
- Depends on: nothing
- Acceptance: With web_data on and no contact the card names the missing contact; after a POST contact_set is true, the value appears in no GET, export or report, and the first round creates <sidecar>/Cache/ninja/rates.json.
- ZERO-CLICK: One typed value, once (identity cannot be guessed, hygiene bars a tracked default); nothing after.
- Disposition: plan
- Notes: Split: the league picker of 0039-R2 is carried by F-141. Q-03 may remove the typed value for every install once the repo is public.

### F-019 - Make the source install work for a stranger

- Rank 19, tier P1; area setup; kind fix.
- Action: The sidecar default follows the kit's own rule (kit folder exists, else inside the tree); Node floor 22.12.0 in setup.ps1, run.ps1 and README, tested against the Electron engines field; quick start = setup.ps1 then run.ps1 (build.ps1 moves to CONTRIBUTING); Python stays 3.11+ with one advisory line when the branch has no Windows installers; add requirements-dev.txt.
- Impact / effort / risk: H / S / Low; operator's machine keeps its sidecar.
- ToS check: No floor rule touched; fallback path inside AshLight's own folder, never a game folder.
- Sources: 0053-R1, 0046-R3
- Depends on: nothing
- Acceptance: Pytest points kit default at a missing drive, expects sidecar_root() inside tree and ensure_dirs() to pass; TEST-CLEAN-CLONE re-run as stranger (AL_SIDECAR_ROOT unset, kit folder absent); no build.ps1 in README quick start.
- ZERO-CLICK: No new step; same two script calls, no prompt.
- Disposition: plan

### F-020 - A README for players, accurate and honest about how the repo is run

- Rank 20, tier P1; area docs; kind docs.
- Action: Quick start = prerequisites, setup.ps1, then the AshLight shortcut; Stop, Update, Uninstall and Troubleshooting sections with today's real steps; fix the Node floor, the client / tray wording and the -NoOverlay / -NoBrowser meaning; a section 'How this repo is run' naming CLAUDE.md, ops/, the hand-off and ROADMAP as the dev process (AI-assisted, operator-reviewed, gated) and that the dev loop reads the web unattended; SECURITY and CONTRIBUTING follow.
- Impact / effort / risk: M / S / None; 0052 R4 to R6 replace it later.
- ToS check: Documentation only; disclaimer line stays.
- Sources: 0042-R5, 0057-R10
- Depends on: F-019
- Acceptance: Quick start names one command; a doc test finds the words Update, Uninstall and the shortcut.
- ZERO-CLICK: Two typed commands fewer.
- Disposition: plan
- Notes: Should-fix before the flip. The non-affiliation sentence stays verbatim.

### F-021 - GP-SETUP: create and configure the repository, private first

- Rank 21, tier P1; area go-public; kind operator.
- Action: On the operator's go: create the repository private with gh, add origin, push main through the guarded hook, wait for both workflows green, flip to public once F-006 holds, then the ruleset on main (no force push, no deletion, required checks, one admin bypass), private vulnerability reporting, Dependabot alerts and immutable releases.
- Impact / effort / risk: H / S / M: a required check that never reported blocks every push; add ruleset only after step 3 shows check names.
- ToS check: Description says unofficial; no GGG art in social preview (use hero).
- Sources: 0057-R7, P01-OPERATOR-REMOTE
- Depends on: F-004, F-006, F-008, F-009, F-013, F-016, F-020
- Acceptance: gh api read-back: public; ruleset active with two required checks and admin as only bypass; next loop push lands (tick 'push ok'); private-vulnerability-reporting true; automated-security-fixes true; vulnerability-alerts 204; sha_pinning_required true; workflow default permissions read.
- ZERO-CLICK: No sign-in needed; steps 1 and 4 wait for operator's recorded go in batched ask (docs/plan/09) per 2026-11-16 order unless lifted in a recorded decision; every other step agent.
- Disposition: operator: say go for step 1 (private remote) and for step 4 (flip to public); no sign-in is needed (Q-23)
- Notes: Conflict resolved: gh being authenticated removes the sign-in, not the operator's go (order of 2026-11-16). The description says unofficial; no game art in the social preview.

### F-022 - Make overlapping test runs safe and pin the plugin set

- Rank 22, tier P1; area tests; kind test.
- Action: free_test_port() leases the first lockable port in 8961-8979 (lock file under the sidecar Temp) for the test's life and the three supervisor tests use it; mark timing-sensitive tests 'timing'; addopts disable cacheprovider, anyio, asyncio and timeout plugins; the loop keeps the end of the gate output (failed ids and count line).
- Impact / effort / risk: M / S / More than 19 concurrent leases wait for a port.
- ToS check: Binds stay on 127.0.0.1 and inside the assigned block; server/al/ports.py untouched.
- Sources: 0049-R4, 0049-R6
- Depends on: nothing
- Acceptance: Those files run twice at once from two worktrees, 5 rounds, all green.
- ZERO-CLICK: Test-only.
- Disposition: plan

### F-023 - One version, enforced

- Rank 23, tier P1; area deploy; kind infra.
- Action: VERSION in server/al/__init__.py stays the source; a test fails when app/package.json or the lockfile differ; 'tools/release.py bump X.Y.Z' edits all three and writes the notes stub in one commit; the tag must equal v + VERSION (SemVer 0.y.z).
- Impact / effort / risk: H / S / Low.
- ToS check: Truthful User-Agent naming AshLight and its version: header reads VERSION; one source keeps it so.
- Sources: 0052-R2, 0053-R2
- Depends on: nothing
- Acceptance: Test fails when strings differ; a bump on a scratch clone changes exactly four paths; a pre-release sorts below its release.
- ZERO-CLICK: Nothing for the player; the loop never bumps by itself (operator order: only on a milestone or explicit tag).
- Disposition: plan

### F-024 - LOOP-PREFLIGHT / LOOP-PARSER-FIX (before HALT is removed)

- Rank 24, tier P1; area loop; kind fix.
- Action: A hand-off bullet is loop work only with a LOOP: prefix (BLOCKED applies); rename the dotted / colon row ids (UTIL-10-...) and add a lint failing on any row-like bullet that does not parse or repeats an id; handoff_session() matches a SESSION line with trailing text; 'failed' leaves the done states with a keep ref, and the 12 stale failed loop_items are marked first; a gate failure outside the lane diff ends fix rounds; 'al_loop.py preflight' runs the gates once on unchanged main.
- Impact / effort / risk: H / M / Low; (d) could end a round early on a real cross-file break, so item parked visibly.
- ToS check: No floor rule touched; dev tooling.
- Sources: 0058-R1, P01-R1, P01-LOOP-PARSER-FIX, P01-L1, P01-L2, P01-L3, P01-L4, P01-NOTE-TEST-GUARD
- Depends on: nothing
- Acceptance: handoff_items on live hand-off yields 0 work items; lint fails on dotted id; failed fixture item prints checklist line; preflight exits 0 with client running.
- ZERO-CLICK: Nothing for player; operator never has to notice a stall.
- Disposition: plan
- Notes: Conflict resolved: rename plus lint (0058, plan 01), not a wider id grammar (0047-R2). The hand-off NOTE about fleet_test_guard is stale since cbd54d6 (0049 F10): verify once, then /done drops it.

### F-025 - Make Play fit without scrolling: the measured layout

- Rank 25, tier P1; area play-tab; kind design.
- Action: Implement the 0043 prototype: one strip of four tiles (zone, level, deaths, session), the guide as its own card under the strip, trades one line per request (3 rows then a count), then the build alert; the item card leads with the verdict at the zone-timer size; pace, when, calc and expiry lines move to Details or Run.
- Impact / effort / risk: H / M / Longer real strings; covered by B2 spare height and ellipsis on one-line rows (full text in title and Details).
- ToS check: Layout and copy only; reads and sends nothing new. Footer affiliation line stays.
- Sources: 0043-R1, 0040-R2
- Depends on: nothing
- Acceptance: B1, B2, B3 green in headless Chrome on states b, c, c2, d, f, g; design-reviewer pass.
- ZERO-CLICK: Nothing to do; layout fills by itself. Details is an optional click.
- Disposition: plan
- Notes: Conflict resolved: 0043 owns the layout and the test sizes (1280x760, 1920x950, 1264x821); 0040 owns the look (glance band at most 120 px; measured strip is 88-108 px). Settles MERGE-SEAMS F1 and the duplicate under-level line (0042 F22); design 0001 section 4 gets the measured figures.

### F-026 - Hotkeys: show the real keys, rebind in the app, heal conflicts, say when a part is off

- Rank 26, tier P1; area settings; kind feature.
- Action: Put the effective keys in the snapshot and print them wherever defaults are printed; one 'change key' field each; the client re-registers on config change and writes registration results and overlay shown / hidden-by-you to a runtime file the core publishes; a taken key falls back to the first free one of a short safe list; Checks rows for both chords; one Play line while the overlay is switched off.
- Impact / effort / risk: H / M / A global shortcut takes the key from every program; keep 'Ctrl or Alt held, never a game key' (hotkeys.py:24-28).
- ToS check: Nothing sent to the game; clipboard read stays one per manual press (decision 0003).
- Sources: 0039-R3, 0054-R3, 0042-R6
- Depends on: nothing
- Acceptance: Node test: config change swaps the registration with no restart; a taken key yields a reported alternate; page holds no literal key text.
- ZERO-CLICK: Conflicts heal by themselves; rebinding optional.
- Disposition: plan
- Notes: Hotkey budget (conflict resolved): at most 2 global keys registered by default (item check, show / hide); any further key ships unset.

### F-027 - OBS-BUILD-STAMP: one build id everywhere

- Rank 27, tier P1; area observability; kind feature.
- Action: server/al/buildinfo.py: version plus 12-hex commit id read from .git files (no subprocess), a .dev mark while hot reload is on, or the BUILD file an installed copy carries; shown in /api/health, /api/version, the report header, the dashboard footer, overlay About, tray tooltip and the first line of every log.
- Impact / effort / risk: H / S / None for play; User-Agent stays as is (decisions 0013, 0015).
- ToS check: AshLight's own repo files only; no network; no GGG mark.
- Sources: 0051-R2
- Depends on: nothing
- Acceptance: One test per surface asserts the same build string; node test asserts app/package.json version equals VERSION; first core.log line after a start matches version plus 12 hex chars.
- ZERO-CLICK: Computed at start, shown everywhere, no setting.
- Disposition: plan
- Notes: The build id never goes into the User-Agent (0051-X9).

### F-028 - FS-ROADMAP-A: prune ROADMAP to open rows, archive the rest

- Rank 28, tier P1; area loop; kind fix.
- Action: Move the 139 done rows to docs/roadmap/archive/2026-11.md, add the prune to /done, give the operator bullet an id and a BLOCKED tag, add a ROADMAP shape test (xfail first, then green).
- Impact / effort / risk: H / S / Wider id grammar feeds DEP_ID_RX, item file names and keep refs; row at ROADMAP.md:530 carries BLOCKED so becomes listed, not dispatched; prune breaks tests/test_desktop_client.py:138-140 unless it reads the archive.
- ToS check: No floor rule touched; the loop starts only headless agent runs, never the game, its files or network.
- Sources: 0047-R2
- Depends on: F-017, F-024
- Acceptance: ROADMAP.md holds only open rows and the 139 done rows are in docs/roadmap/archive/2026-11.md; the shape test passes on every row-like bullet; the loop's work list is the same before and after the move; /done prunes newly done rows.
- ZERO-CLICK: Developer-side only; player does nothing.
- Disposition: plan
- Notes: Split: the id grammar and hand-off reader halves of 0047-R2 are superseded by F-024. The archive is published as a tracked file (0057 F14) once F-004 is clean. done.md is under .claude/: session work, not a lane.

### F-029 - FS-ROADMAP-B and ROW-GRAMMAR: rows added and flipped by new files

- Rank 29, tier P1; area loop; kind infra.
- Action: ROADMAP.md stays the one page of open rows; unattended writers create files only (new row = docs/roadmap/new/<ID>.md, finished row = docs/roadmap/done/<ID>.md); a loader composes them and one writer folds them in; accept 'DEPENDS: <ids>' in row text, show an unknown dependency as a visible wait, match briefs on the exact id under docs/plan/briefs/, put the row id in the lane's usage label.
- Impact / effort / risk: M / M / Two sources of truth between folds; loader is the only reader and a test fails on a done marker without a row.
- ToS check: No floor rule touched; tracked text only.
- Sources: 0047-R6, 0058-R12
- Depends on: F-028
- Acceptance: In a scratch clone two branches each add a row file and a done marker and merge with no conflict; work list shows both; a fold leaves no fragment and an unchanged row set.
- ZERO-CLICK: Developer-side only; player does nothing.
- Disposition: plan
- Notes: Conflict resolved: file-per-row (0047) is the mechanism behind the watcher's two primitives (0058), so an unattended commit only ever adds a file; DEPENDS: in the row is the one machine-read dependency form; the non-existent docs/plans/ path is dropped.

### F-030 - WATCH-CORE: one upstream watcher frame on the dev loop

- Rank 30, tier P1; area automation; kind feature.
- Action: One stdlib tools/upstream_watch.py with a source registry, state in ops/runtime/watch/state.json, at most one due source per tick, called before the HALT return; TC-DRIFT and the docs watch become sources; further sources: PoB release and master head, repoe-fork data, GGG tree export, poe.ninja docs page; sources return typed findings (name, key, validated tokens) that the tick files as rows through two primitives.
- Impact / effort / risk: H / M / Unattended commit on main; bounded by diff check (added lines parse as rows, one flipped gate, nothing removed), hooks, daily cap.
- ToS check: Public pages/files/documented APIs via webfetch.py with AshLight UA, no cookie; dev tooling, never player's core (0025, 0044 item 7).
- Sources: 0058-R2, 0037-R5, 0037-R2
- Depends on: F-024, F-029
- Acceptance: Fake fetches drive each source; token failing its pattern files nothing; fourth row in a day waits; HALTed tick records finding, commits nothing.
- ZERO-CLICK: Fully unattended.
- Disposition: needs-ruling: Q-12, Q-13
- Notes: Without Q-12 the watcher only reports. Conflict resolved: no CI job reads poe.ninja or a GGG host; the poe.ninja docs-page source (W6) runs here. Row text never comes from an issue body, release note or commit title (0058-X3).

### F-031 - PRICE-LEAGUE-1.0: league identity ready for launch day (before 2026-12-11)

- Rank 31, tier P1; area prices; kind feature.
- Action: Send If-None-Match on the league GET; cache the whole list as id plus name (id for poe.ninja, name for trade links and labels); show the league on the overlay price line for 24 h after a change; correct runbook step 8 to 'within 6 h'.
- Impact / effort / risk: H / S / (b) adds 20 league reads a day (24, was 4), bodiless when unchanged.
- ToS check: Public-web-data rule (documented route, conditional as ND asks); trade link still only built, never called (decision 0017).
- Sources: 0036-R2
- Depends on: nothing
- Acceptance: A list whose id differs from its name puts the id in the poe.ninja URL and the name in the trade URL; the league GET carries If-None-Match; the overlay price line names the league for 24 h after a change; the runbook says 'within 6 h'.
- ZERO-CLICK: Automatic.
- Disposition: plan
- Notes: Split: part (b), an hourly league re-read, is not adopted: decision 0026 item 4 (6 h or after a 404) stands and its Reverses-if is not met; a core start re-reads anyway.

### F-032 - OBS-COUNTERS and BUDGET-LOG: AshLight records its own footprint

- Rank 32, tier P1; area observability; kind feature.
- Action: server/al/metrics.py (counters, gauges, timing rings), token-gated GET /api/debug and 'python -m server.al.probe'; once a minute the client logs app.getAppMetrics() per own process and the core its working set and CPU seconds (and luajit's when up), tagged game idle / active / in map / overlay shown from Client.txt state; 1 MB cap in <sidecar>\Logs; one Checks row.
- Impact / effort / risk: H / M / Log growth (cap 1 MB, oldest dropped).
- ToS check: No game memory read; decision 0029 (no process-list check for the game): only AshLight's own process handle and Electron's own tree; decision 0006 method 3 names these counters.
- Sources: 0048-R4, 0051-R4, P01-R4, P01-OVL-BUDGET
- Depends on: nothing
- Acceptance: Replayed log with a breach fails test_budget_log.py, clean one passes; sampler adds under 0.01 percent CPU; no row holds a path, name or pid.
- ZERO-CLICK: Automatic; operator only plays.
- Disposition: plan
- Notes: Closes OVL-BUDGET with no operator act. Reads only AshLight's own processes (decision 0006 method 3); conflict resolved: the counters are a Checks-class self-diagnostic (decision 0040), not the on / off FPS measurement of decision 0006 item 4; a one-line note in 0006 at landing.

### F-033 - WAVE-INTERPLAY: the loop and waves contract

- Rank 33, tier P1; area loop; kind design.
- Action: BLOCKED means not for the loop, with a reason the checklist echoes; session-wave rows carry 'BLOCKED: session wave <n>'; the loop never takes rows touching web/, app/overlay/, app/shared/ or event text while a wave owns them; a session reads loop_items/<ID>.json before touching an untagged row; wave agents work in worktrees.
- Impact / effort / risk: H / S / A wave ending early leaves rows tagged; they stay listed as blocked, nothing lost.
- ToS check: No floor rule touched.
- Sources: 0058-R5
- Depends on: F-024
- Acceptance: Dry-run tick on landed ROADMAP lists only loop rows as would dispatch.
- ZERO-CLICK: No operator step; the session ending a wave flips its rows.
- Disposition: plan
- Notes: Written into docs/plan/07 and 08. Holds the six checks that gate F-078.

### F-034 - CORE-DEMO-MODE: a supported isolated instance

- Rank 34, tier P1; area tests; kind infra.
- Action: 'python -m server.al --demo <fixture dir>': runtime, config and fetcher in a scratch folder, local.json ignored, Steam scan off (a missing demo log is an error), web data off or a loopback mock, exit 97 if any open log lies outside the fixture folder.
- Impact / effort / risk: H / M / Low once NO-DISCOVERY has landed.
- ToS check: Reads only a fixture copy; no live log, no network.
- Sources: P01-R5, P01-CORE-DEMO-MODE, P01-L14
- Depends on: F-001
- Acceptance: Demo core given a missing fixture exits non-zero and opens no file outside the fixture dir; live runtime dir untouched (mtime check).
- ZERO-CLICK: Dev only; no player interaction.
- Disposition: plan
- Notes: Split: carries part (d) of 0050-R0 and part (a) of 0058-R8. Unblocks F-066, F-147 and MERGE-SEAMS F1.

### F-035 - Bring charjson to the shapes GGG documents today

- Rank 35, tier P1; area theorycraft; kind fix.
- Action: Accept ItemMod objects as well as strings in implicitMods / explicitMods, read bondedMods, keep removed fields for old pastes, map internal class ids through the cached tree export when present, treat Flask positions above 1 as charms, keep weapon-set membership; fixtures in both shapes.
- Impact / effort / risk: H / S / Low; parser only, old shape still accepted. Effort S for mod fields, M with sets, overrides and class ids.
- ToS check: No floor rule touched; no network, no new read; input is player-pasted text (decision 0004 item 4).
- Sources: 0035-R1
- Depends on: nothing
- Acceptance: A fixture item with ItemMod objects yields its mod lines in the item text; the old fixture still passes; internal and display class names give the same build.
- ZERO-CLICK: Same paste path, no new press.
- Disposition: plan
- Notes: A current-shape paste loses every implicit and explicit mod today. The optional operator paste is dropped; live field forms are observed at the first API call.

### F-036 - PRICE-REFRESH-CORE: prices refresh from the core loop, not the visible page

- Rank 36, tier P1; area prices; kind feature.
- Action: The core loop starts a due refresh once a minute while web data is on and either the log is not idle or /api/rates was read in the last 10 min (hourly gates still decide); map http.client.HTTPException to FetchError; pass the cache age to the card (older than 2 h reads 'price from N h ago', older than 24 h shows the link only).
- Impact / effort / risk: H / S / The card's ninja keys are listed in decisions 0016 / 0026, so this needs an amendment line.
- ToS check: Client.txt rule (staleness of the permitted log read, decision 0029; no process check) and public-web-data rule (opt-in, truthful UA); no input.
- Sources: 0036-R3, 0050-R7
- Depends on: nothing
- Acceptance: With no HTTP client and an active log a fake transport sees one round an hour; with the log idle 20 min, none; exact card text for 3 h and 30 h old caches.
- ZERO-CLICK: Automatic.
- Disposition: plan
- Notes: No faster retry after a failure (0036 rejects it). Adds trigger detail to decisions 0016 / 0026 without reversing them: amendment lines at landing.

### F-037 - Lock npm down

- Rank 37, tier P1; area electron; kind security.
- Action: Tracked app/.npmrc (ignore-scripts, engine-strict, save-exact); setup.ps1 uses 'npm ci --ignore-scripts' and refuses without a lockfile; the lane bump prompt gains --ignore-scripts and the 3-day rule; electron moves to dependencies; the bump gate adds 'npm audit signatures'.
- Impact / effort / risk: M / S / A later package needing its install script (none today); a packager (0053) may want electron as a dev entry.
- ToS check: No floor rule touched; setup-time installs only.
- Sources: 0046-R2
- Depends on: nothing
- Acceptance: Asserts .npmrc keys, no npm call in setup.ps1 without --ignore-scripts, no lockfile-less branch, no hasInstallScript in lockfile, npm audit --omit=dev covering 13 packages.
- ZERO-CLICK: No change for the user.
- Disposition: plan

### F-038 - Spike: run AshLight under the embeddable CPython layout

- Rank 38, tier P1; area deploy; kind test.
- Action: In a scratch folder unpack the hash-checked embeddable zip and a git-archive copy of the tree, add the ._pth line, point AL_SIDECAR_ROOT at scratch, and run a demo core, the supervisor, the calc bridge and a named test subset under that python; record what breaks.
- Impact / effort / risk: H / S / The whole release layout rests on this runtime; today only --check and module imports are proven (0053 M2).
- ToS check: No floor rule touched; fixture log only, never the live Client.txt, spare port of the block.
- Sources: CRITIC-GAP-09
- Depends on: F-034
- Acceptance: Demo core answers /api/health, the supervisor restarts it once, the bridge answers one calc on the reference build (when the calc is installed), the named tests pass; results recorded in plan 05.
- ZERO-CLICK: Dev only.
- Disposition: plan
- Notes: Decides Q-20.

### F-039 - TC-BRIDGE-NEXT: accept the next PoB main-object shape

- Rank 39, tier P1; area theorycraft; kind fix.
- Action: pob_main() also accepts the global __mainObject__, and the 3 failing drift guard rows accept either shape.
- Impact / effort / risk: H / S / Low; the old paths stay.
- ToS check: No floor rule touched; own Lua under the pinned subprocess, inputs stay pasted build text and hotkey-read item text (decision 0004).
- Sources: 0037-R1
- Depends on: nothing
- Acceptance: The 23 patterns pass on the installed pin and on files at the beta head (scratch read or R3 b); live tests stay green on the pin; fake-bridge tests stay green.
- ZERO-CLICK: Nothing for the player; the calc keeps working across the pin move.
- Disposition: plan
- Notes: Must land before the first pin move (runbook step).

### F-040 - One batched operator ask (docs/plan/09)

- Rank 40, tier P1; area other; kind operator.
- Action: Write docs/plan/09 as one ask in three parts: rulings (the open decisions of this file), one-minute acts (settings paste, contact, keyboard-layout check, free-key look, consent line tick), and in-game tries (F-100, F-128); drop the LIVE-1 play session and the RAM half of the FPS test (closed by F-061 and F-032).
- Impact / effort / risk: H / S / Low.
- ToS check: No floor rule touched; every act is the operator's own.
- Sources: P01-OP-ACTS, P01-OP-ACTS-e, P01-OP-ACTS-g, P01-OP-ACTS-h, P01-OP-ACTS-k
- Depends on: nothing
- Acceptance: docs/plan/09 lists every question of the open-decisions section and every operator disposition of this file exactly once, each with a default that applies when unanswered.
- ZERO-CLICK: One ask instead of many; every item carries a default.
- Disposition: operator: answer the one batched ask once
- Notes: (e) autostart stays optional (decision 0011); (g) contact and web_data feed F-018; (h) is Q-15; (k) is Q-06.

### F-041 - A build prompt with its own button, from the first minute

- Rank 41, tier P1; area theorycraft; kind feature.
- Action: Show the 'Your build' card as soon as opt-in is given and no build is loaded; it and the three alert sentences get one button 'Paste a build' that shows the Build tab and focuses the paste box; the empty text says where a code comes from.
- Impact / effort / risk: H / S / A button in a card that is not a live region; keep its words.
- ToS check: Build stays user-pasted text (0004); paste is the player's act; no clipboard read.
- Sources: 0042-R3
- Depends on: nothing
- Acceptance: A consented snapshot with no build and no character carries the prompt; node test clicks the button and finds Build shown and #build-paste focused.
- ZERO-CLICK: Prompt shows and leaves by itself; the paste is the one act the floor-safe sources leave (TC-IMPORT waits on registration).
- Disposition: plan
- Notes: Fits in the alert heading row (0 px, one control). If F-042 lands the alert names that press instead.

### F-042 - Let the item hotkey load a copied build

- Rank 42, tier P1; area theorycraft; kind feature.
- Action: Core.eval_press classifies the text first: a PoB code or character JSON loads the build, a share link loads only with web data on, anything else is the item check as today; the overlay card says 'Build loaded: <name>'; the no-build and stale-build alerts name this press.
- Impact / effort / risk: H / S / Build replaced by accident (card names the build; old file kept as one undo).
- ToS check: Same single clipboard read on the same manual AshLight hotkey press (decision 0003); nothing new read or sent to the game; share-link fetch stays under web-data opt-in (0013) and host allow-list; Build loaded card uses the one overlay card slot (0014 F2).
- Sources: 0043-R4
- Depends on: nothing
- Acceptance: POST /api/eval with a fixture code changes build and returns a Build loaded card; item text still gives a verdict; text paste.detect calls code but fails to decode falls back to item check; a link with web data off gives the existing refusal words.
- ZERO-CLICK: 1 press, required by the floor (one read per manual press).
- Disposition: needs-ruling: Q-02
- Notes: Same single clipboard read on the same manual AshLight hotkey press; only the wording of decision 0004 (user-pasted build text) is in question.

### F-043 - Put the build caveat on the verdict; no verdict while an input is missing

- Rank 43, tier P1; area overlay; kind fix.
- Action: While a build alert is set the overlay item card's third line is a short alert head (at most 34 chars) and the dashboard prints the alert sentence under the verdict; any comparing card shows which input is missing instead of a guessed verdict, and every green or red mark is paired with a word.
- Impact / effort / risk: H / S / Third line loses the top stat while the alert lasts.
- ToS check: Text from Client.txt and pasted build only; overlay stays within 2 lines plus one 3-line card.
- Sources: 0042-R2, 0056-R12
- Depends on: nothing
- Acceptance: Exact-output tests for the three heads; a snapshot with an alert and a fresh item check carries the head in card.line3.
- ZERO-CLICK: Appears and clears by itself with the alert.
- Disposition: plan
- Notes: The line choice goes through the design reviewer (0042-Q3); no operator ruling needed.

### F-044 - Close the Electron chain at both ends

- Rank 44, tier P1; area electron; kind security.
- Action: setup.ps1 clears the install override variables before npm and install.js; tracked config/electron_pin.json holds version, line EOL date, zip SHA-256 and electron.exe SHA-256 and size per arch; setup and run.ps1 verify the exe against it.
- Impact / effort / risk: M / S / arm64 needs its own entry (ship both, or warn and continue on unknown arch).
- ToS check: No floor rule touched; hashes AshLight's own runtime file.
- Sources: 0046-R4
- Depends on: F-037
- Acceptance: With electron_use_remote_checksums=1 setup still verifies against packaged checksums; a one-byte change in a copy of the exe fails the check; pin version equals package.json.
- ZERO-CLICK: Runs inside setup and run.
- Disposition: plan

### F-045 - PRICE-POLITE: back off, compress, space the requests

- Rank 45, tier P1; area prices; kind fix.
- Action: On 429, 403 or 503 stop the round and honour Retry-After bounded to 1-24 h, persisted; after 3 failures in a row retry that type daily; send Accept-Encoding gzip and inflate through a bounded stream (4 MiB); wait 2 s between the 23 GETs; the User-Agent purpose says 'prices'.
- Impact / effort / risk: M / M / Unbounded inflate would be a memory bomb; round lasts about 44 s longer (press never waits).
- ToS check: Truthful-User-Agent rule; follows the source's own requests (caching, low concurrency); no cookie.
- Sources: 0036-R5
- Depends on: nothing
- Acceptance: A 429 with Retry-After 7200 means no request for 2 h across a restart; a gzip body decodes and one inflating past the cap is refused; a type failing 3 times waits 24 h; 22 gaps of 2 s with a fake sleep.
- ZERO-CLICK: Automatic.
- Disposition: plan

### F-046 - GO-PUBLIC-NINJA: ask poe.ninja, ship the tiered cadence either way

- Rank 46, tier P1; area go-public; kind operator.
- Action: Before the flip the operator asks poe.ninja once whether per-install polling at this cadence is acceptable or a project mirror is wanted; with or without an answer ship the tiered cadence (Currency hourly; the other 22 types every 3 h unless pressed in the last 24 h: daily ceiling 552 down to 200 overview GETs); a decision records the outcome.
- Impact / effort / risk: H / S / A mirror republishes poe.ninja data; scheduled jobs slip and stop after 60 idle days. Effort S for (1)(2), L for a mirror.
- ToS check: Public-web-data rule (named source; mirror is AshLight's own file, no GGG endpoint, no trade site); no-revenue rule (free, attributed).
- Sources: 0036-R7
- Depends on: F-036, F-045
- Acceptance: A decision records the answer or the default, and a test proves the daily request ceiling.
- ZERO-CLICK: Nothing for players; one operator message.
- Disposition: operator: one message to poe.ninja, or an explicit skip (Q-05); the cadence change is plan work

### F-047 - Release layout with pinned runtimes and one resolver each

- Rank 47, tier P1; area deploy; kind infra.
- Action: config/runtime_pins.json (embeddable CPython 3.14.x and the Electron zip: url, sha256, size, licence) fetched with the tc_pin code into <home>\runtime\<name>-<ver>\; one PowerShell helper and launcher.js prefer the bundled python(w).exe and paths.electron_exe() the bundled electron.exe; no npm on the player path.
- Impact / effort / risk: H / M / M: six lookups and three paths move; covered by run/stop/procs tests plus a release-layout test. Keep passing app folder to electron.exe (never resources\app) so app.isPackaged stays false and devTools gate at app/main.js:30 behaves.
- ToS check: Runtimes are public web data from python.org and GitHub release assets, no GGG endpoint, truthful UA, no cookie; fetched by setup or release build, never by running core (0018 item 6).
- Sources: 0053-R3
- Depends on: F-019, F-038, F-044
- Acceptance: Scratch copy with no Python/Node on PATH: runtime python.exe -m server.al --check returns 0 and run.ps1 -NoBrowser on spare port answers /api/health; wrong pin hash refuses with exit 2.
- ZERO-CLICK: Fetched inside setup or release build; nothing to install.
- Disposition: needs-ruling: Q-20
- Notes: Conflict resolved (fuses): the shipped electron.exe is the unmodified hash-pinned upstream binary, so no fuse is flipped; the launcher drops ELECTRON_RUN_AS_NODE and NODE_OPTIONS and guards.js quits on inspect switches (F-110); fuses are revisited with a signed packaged exe (decision 0041 item 9).

### F-048 - One release tool that builds and never uploads

- Rank 48, tier P1; area deploy; kind infra.
- Action: tools/release.py build (also build.ps1 -Package): from a tag, a ship list over git ls-files, AshLight-<ver>-app.zip, the offline full zip, install.ps1, MANIFEST / release.json with per-file sha256, SHA256SUMS.txt, the BUILD file and notes, reproducible (sorted entries, tag commit time, bytes from git blobs), written to <sidecar>\Build\release\<version>\; refuse a dirty tree or a tag / VERSION mismatch.
- Impact / effort / risk: H / M / Shipping a dev or fleet file (F9), held by allow-list, leak sweep of staged tree and a deny test.
- ToS check: No GGG trademarks/art and decision 0009 (no game data): only tracked files ship; build fails if anything from sidecar cache is in staged tree; disclaimer ships.
- Sources: 0052-R3, 0053-R4
- Depends on: F-023, F-047
- Acceptance: Two builds of one ref same SHA-256; manifest check catches changed, missing file and unsafe path; nothing under ops/loop, tools, tests or docs listed; zip under 2 MB.
- ZERO-CLICK: One command, no prompt, no upload.
- Disposition: plan
- Notes: Two builds of the same tag must be byte-identical (settles the deflate question; a stored zip is the fallback). No game data, PoB source or LuaJIT in any artifact (decisions 0009, 0018).

### F-049 - Installed-mode paths

- Rank 49, tier P1; area deploy; kind feature.
- Action: server/al/paths.py gains an installed mode (marker above the package, or AL_HOME): state, config, logs, cache and temp resolve under the install home; the kit default counts only when its folder exists; the resolver refuses a home inside a game folder.
- Impact / effort / risk: H / M / Path regressions across the core, held by the path test.
- ToS check: Never modify any game file: resolver and installer refuse a home inside a Steam library or game folder; consent moves with the data folder, no new read.
- Sources: 0052-R1
- Depends on: F-019
- Acceptance: With AL_HOME=<tmp> every runtime path inside <tmp>; with no env and no kit folder none leaves %LOCALAPPDATA%; cores from <tmp>\app\0.1.0 and <tmp>\app\0.1.1 read same consent file; home inside fake game folder refused.
- ZERO-CLICK: Resolved from the marker; nothing to set.
- Disposition: needs-ruling: Q-19
- Notes: Home per the 0053 Fit section: %LOCALAPPDATA%\Programs\AshLight with state in data\ (0052 names two different homes; this one wins).

### F-050 - Installer and bootstrap, local zip first

- Rank 50, tier P1; area deploy; kind feature.
- Action: install.ps1 (PowerShell 5.1) plus a stdlib installer package: verify the zip, lay out <home>\app\<version>\, fetch the hash-pinned runtimes, write the first-run config, self-test, then the marker, two shortcuts and one per-user Apps & features entry; a re-run repairs or upgrades; the pasted install line is the primary route in README.
- Impact / effort / risk: H / L / Embeddable Python layout untested (spike first, F12); Electron zip route needs a recorded decision (Q2).
- ToS check: Downloads only to GitHub release hosts and python.org, named as AshLight installer with version, no cookie, no GGG/trade endpoint; install-time fetch of own runtime, not game data; 0013 untouched. Writes only its home, two shortcuts, one per-user key.
- Sources: 0052-R4
- Depends on: F-011, F-047, F-048, F-049
- Acceptance: Scratch home with fakes: clean install lays out marker, code, data, runtime; tampered zip or missing hash installs nothing; failed self-test leaves no marker and one report; re-run restores deleted shipped file; parses under PS 5.1; pinned Electron equals app/package.json.
- ZERO-CLICK: One pasted line, then the app opens; no elevation prompt.
- Disposition: needs-ruling: Q-20, Q-19
- Notes: Conflict resolved (install shape): the 0053 Fit section adopts the 0052 design (per-user home, app\<version>\ plus marker, Apps & features entry). Amends decisions 0010 and 0041 point 8 at landing. The checkout keeps npm ci.

### F-051 - POLICY-QUOTES: the floor's source quotes under watch

- Rank 51, tier P1; area automation; kind feature.
- Action: Add the 12 baseline quotes of research 0029 as a check in the docs watch: each must appear in the index page text; a missing quote writes ops/runtime/ggg_docs/POLICY_CHANGED, a dev-host Checks note and a review row with 'BLOCKED: session'.
- Impact / effort / risk: H / S / Page reflow reads as change; compare whitespace-normalised.
- ToS check: Same six pages, cadence, identity as 0044; no new request; tool never edits the floor.
- Sources: 0058-R4
- Depends on: nothing
- Acceptance: Fixture page missing quote O3 raises flag naming O3; real cached page raises nothing.
- ZERO-CLICK: Unattended.
- Disposition: plan
- Notes: Same six pages, cadence and identity as decision 0044; no new request.

### F-052 - LAUNCH-GATE: 1.0 rows that open by themselves (before 2026-12-10)

- Rank 52, tier P1; area automation; kind feature.
- Action: Land three parseable rows (UTIL-10-DATA, UTIL-10-NOTES, UTIL-10-LOG) and one gate row; the launch source flips GATE-POE2-10 when the local date is 2026-12-11 or later and the repoe-fork data or the GGG tree export shows version 1.0 or newer, not a preview; add the runbook steps of note 0037 (bridge fix before the first pin move, re-read pob2_files, new GUI reference per pin move, a 1.0-era export fixture, Acts 5-6 and interlude handling).
- Impact / effort / risk: H / S / Slipped launch (two-signal rule) or preview tree read as live (preview filter).
- ToS check: Tree export is GGG's listed data export from its public repo; repoe-fork public repo metadata; no game system, no trade site.
- Sources: 0058-R3, 0037-R7, P01-UTIL-1.0-POST
- Depends on: F-024, F-030
- Acceptance: Clock 2026-12-10 flips nothing; 2026-12-11 with fixture 1.0.0 flips gate once and dependents dispatchable; 'Preview' title flips nothing.
- ZERO-CLICK: Unattended, bar the operator's own play session the floor requires of a log read.
- Disposition: plan
- Notes: Replaces the UTIL-1.0-POST row the loop cannot see. UTIL-10-LOG opens per Q-28. 1.0 ascendancy names and area-id prefixes are unverified until launch.

### F-053 - Dashboard type scale as tokens, with a measured distance rule

- Rank 53, tier P1; area play-tab; kind design.
- Action: AL-owned :root block in web/app.css with six steps (micro 13, meta 14, body 16, title 20, glance 28, hero 40 px); Play text read in play (tile labels, sub lines, status words) uses the 20 px step; write the distance rule (at least 16 arcmin, critical 20, at the reference setup) into design 0001 section 3 with a test.
- Impact / effort / risk: H / M / Hero 40 vs 33.28 px at 1280x760 adds height to an overflowing left column (hence 32 px there); card titles at 20 px add ~6 px per card; sequence after the Play layout work of 0042 / 0043.
- ToS check: Dashboard only (127.0.0.1 page); no floor rule touched.
- Sources: 0041-R3, 0055-R2
- Depends on: F-025
- Acceptance: Re-run evidence pack at 1024x700, 1280x760, 1920x950: only sizes in {13,14,16,20,28,32,40} px; 13 px only under footer.foot; no weight >= 600 under 14 px; no vw in any font-size; Play distinct styles <= 10.
- ZERO-CLICK: Automatic.
- Disposition: plan
- Notes: Conflict resolved: 0041 scale as the token set, 0055 floor (19.2 px) met by the 20 px step; both cases fit with at least 48 px spare (0043 fit table). Q-14 may replace the reference setup.

### F-054 - Item-check default chord: one roll under Ctrl, after two one-minute operator checks

- Rank 54, tier P1; area items; kind operator.
- Action: The operator (1) presses Alt+Shift+E and Alt+Shift+A with two keyboard layouts installed and reports whether the layout flips, (2) looks once at the game's input options for a free Ctrl+letter next to C; then the default item key becomes that second tap under Ctrl (Alt+Shift+E stays a listed alternative).
- Impact / effort / risk: M / S / Clash with a game bind hides that bind while AshLight runs (global shortcut); Checks row reports failed registration. A Ctrl+letter default is taken from browser and every program while AshLight runs.
- ToS check: Still the player's own Ctrl+C, then one manual AshLight hotkey press with one clipboard read; no input sent, no watcher.
- Sources: 0043-R5, 0042-R12
- Depends on: F-026
- Acceptance: Hotkey case table accepts the new default and still refuses every GAME_KEYS entry; B9 (<=3 key presses per item).
- ZERO-CLICK: 2 presses under one hold; floor forbids fewer with the clipboard.
- Disposition: operator: two one-minute checks (Q-09)
- Notes: AshLight never reads the game's key bindings (a game file); the free key comes from the operator's look.

### F-055 - In-app update notice from the core

- Rank 55, tier P1; area deploy; kind feature.
- Action: server/al/updates.py: at most one GET per 24 h of the project's releases/latest (rate-limit headers and ETag honoured), only while web_data is on; a newer tag adds a Settings tab mark and one line (never a window), a fold with the last 3 versions written for players, and 'AshLight <version>' and 'game data from <date>' on two lines; repo name is one constant, empty = off.
- Impact / effort / risk: M / S / Low.
- ToS check: Documented GitHub endpoint, not GGG/trade; truthful UA, no cookie; inside web-data opt-in (0013); a network timer is not a clipboard/screen watcher. Decision 0018 item 6 wording (core fetches nothing from GitHub) needs amendment, not reversal.
- Sources: 0053-R7, 0054-R6
- Depends on: F-021, F-023, F-027
- Acceptance: web_data off: injected transport never called; on: one call per 24 h, 304 costs no parse, 403 with reset honoured; note text passes design voice tests.
- ZERO-CLICK: Note appears by itself; no toast, no prompt.
- Disposition: needs-ruling: Q-21, Q-24
- Notes: Conflict resolved: a version check is allowed only inside the web-data opt-in (0053, 0052); what stays rejected is a check outside it or by default (0046-X3). Blocked in practice until a public release exists.

### F-056 - Fold price watch into price movers and make a move visible

- Rank 56, tier P1; area prices; kind feature.
- Action: 'Your checked items' rows on top of the movers block and a tab mark when one moved; the separate price watch card goes; movers are worded as a trend, not a fact.
- Impact / effort / risk: M / S / Live-region cap (12 of 12); the tab mark adds none.
- ToS check: Cached poe.ninja book only, only while web data is on (decision 0036).
- Sources: 0039-R10
- Depends on: nothing
- Acceptance: Node test: a moved item sets the mark and renders above the movers; the no-request test stays green.
- ZERO-CLICK: Fills from the press the player already makes.
- Disposition: plan

### F-057 - WT-SIDECAR-WIRE: activate the worktree hook

- Rank 57, tier P1; area automation; kind operator.
- Action: The operator pastes the two WorktreeCreate hook entries into .claude/settings.json; a session then checks that one isolated spawn lands under the sidecar Worktree dir and un-skips tests/test_wt_sidecar_hook.py:136; the row reopens as WT-SIDECAR-WIRE.
- Impact / effort / risk: M / S / Low.
- ToS check: No floor rule touched; keeps the Sidecar order (worktrees under the sidecar).
- Sources: P01-WT-SIDECAR-WIRE, P01-L5
- Depends on: nothing
- Acceptance: tools/wt_sidecar_hook.py is named in .claude/settings.json; one isolated agent spawn creates its worktree under <sidecar>\Worktree; the skipped test runs.
- ZERO-CLICK: One paste by the operator, once.
- Disposition: operator: paste the two hook entries into .claude/settings.json (one batched ask)
- Notes: Wave execution spawns isolated worktrees, so this precedes wave 1. An agent may not edit settings.

### F-058 - Load a build from a save file the player picks

- Rank 58, tier P1; area theorycraft; kind feature.
- Action: Beside the paste box a file control lets the player pick a Path of Building save file in the browser; the core gets the bytes only (token API, 2 MB cap, no path, no stored copy), the same bytes as a paste.
- Impact / effort / risk: M / S / Low; the pattern is decision 0033 (the player picks the file in the browser; the core never sees a path).
- ToS check: The player's own act per load; no folder read, no watcher, no game file. Decision 0004 input clause needs the same one-line amendment as F-042.
- Sources: 0054-F2
- Depends on: nothing
- Acceptance: Picking a fixture save file loads the same build as pasting its export code; the request carries no path; nothing is written to disk.
- ZERO-CLICK: One pick per build change; no terminal, no code export in PoB.
- Disposition: needs-ruling: Q-02
- Notes: The floor-safe alternative while F-071 waits for a ruling.

### F-059 - PRESS-STAGED: publish the item check in stages

- Rank 59, tier P1; area theorycraft; kind feature.
- Action: Answer the hotkey request at once; publish the weights card first, then the PoB DPS / EHP change, then per-mod rows, each an update that keeps the card's time; one press in flight per core, a second press replaces pending probes.
- Impact / effort / risk: H / M / A card that changes while read (design notes decide words); each stage must stay all or nothing.
- ToS check: Clipboard once per manual press unchanged: same single read feeds every stage; nothing sent to the game.
- Sources: 0048-R3
- Depends on: nothing
- Acceptance: B15; with a fake sleeping calc the first state frame carrying the card arrives under 0.5 s and the request returns under 1 s; a killed calc still leaves the weights card.
- ZERO-CLICK: Same one press; card fills in by itself.
- Disposition: plan

### F-060 - CAMPAIGN-KEEP: keep-or-vendor verdict with no build loaded

- Rank 60, tier P1; area items; kind feature.
- Action: An AshLight-authored, hot-reloaded rule table (JSON conditions, never evaluated) of level bands and acts with thresholds for life, each resistance and boots movement speed and a count-of-N rule; with no build the card says 'worth keeping: meets 2 of 3 for level 24' or 'vendor'.
- Impact / effort / risk: H / M / Thresholds feel wrong for some builds; label it a levelling rule, show which thresholds held, table tunable via hot reload (0042); boots band must agree with campaign.py boots_speed_level default 16.
- ToS check: Item text from one clipboard read per manual press (0003); level from opted-in Client.txt; act from HUD-ACT; thresholds AshLight's own; nothing copied from repo E.
- Sources: 0056-R2
- Depends on: nothing
- Acceptance: Fixture items at levels 10, 30, 60 give expected keep/vendor verdict and list thresholds met; broken rule file keeps last good copy with a Checks note; a loaded build still uses the normal comparison.
- ZERO-CLICK: No new press; rides the existing item-check hotkey.
- Disposition: plan
- Notes: Own table first (0056-Q3); its entries carry the src and checked fields of F-097. F-070 later replaces it where worn gear is known.

### F-061 - OBS-PARSE-LEDGER: close the live log shapes from normal play

- Rank 61, tier P1; area observability; kind feature.
- Action: ops/runtime/logshapes.json: per-pattern hit counts plus a masked shape ledger (allow-list mask, 200 shapes, under 64 KB, written at most once a minute, two-sighting rule); anchored lines that match no pattern are counted and 3 in a session add a Checks note; tools/live1_report.py prints VERIFIED live / NOT SEEN / NEW SHAPE per LIVE-1 item plus the five TEST-LIVE-CLICKS fields; an item press records the masked waystone property-block shape.
- Impact / effort / risk: H / M / A mask gap; held by allow-list design and a property test; one dict update per line.
- ToS check: Client.txt after opt-in only, read only, nothing sent; GGG user-aware rule met by a new consent line.
- Sources: 0051-R1, P01-R3, 0050-R11, P01-LIVE-1, P01-TEST-LIVE-CLICKS, P01-LIVE-WAYSTONE
- Depends on: nothing
- Acceptance: Property test on 10,000 seeded hostile lines: every stored token is allow-list word, placeholder or punctuation; chat/whisper/speech-like never stored incl. speaker over 48 chars and colon without space; death line for a character named like an allow-list word stores name slot as placeholder; replaying client_live_shapes.txt yields expected pattern ids; file under 64 KB after 1,000,000 lines; no file with consent off or revoked; test_budgets.py green.
- ZERO-CLICK: After one Allow click on the new consent line the ledger fills in normal play, tick writes the note, a lane turns each verified item into a test.
- Disposition: operator: tick the new ledger consent line once (one batched ask); the build is plan work
- Notes: Conflict resolved by the stricter reading: both persisted ledger parts wait for a new consent line beside the Client.txt opt-in; in-memory counters need none; revoking consent deletes the file. No raw line text is ever stored. The LIVE-1 row splits so each item closes on its first live hit.

### F-062 - LIVE-VERDICTS: 'Tried in game' card

- Rank 62, tier P1; area observability; kind feature.
- Action: A Checks-tab card listing the open player checks (TC-BUILDFILE-LIVE, LIVE-SEARCHSTR, LIVE-FILTER, LIVE-FILTER-MERGE, OVL-FPS readings) with Worked / Refused and an optional note; verdicts in a bounded ops/runtime file; a script reads them back and drafts the ROADMAP flips.
- Impact / effort / risk: M / M / Low; nothing sent anywhere.
- ToS check: Dashboard clicks only, nothing sent to the game.
- Sources: P01-LIVE-VERDICTS, P01-R6
- Depends on: nothing
- Acceptance: A verdict posted through the token API appears in the read-back output and the script drafts the matching ROADMAP flip; the verdict file stays bounded; nothing is sent to the game.
- ZERO-CLICK: Each in-game try ends in one click; no reminder, no typed report.
- Disposition: plan
- Notes: Split: the OVL-CHECK half of P01-R6 is F-128.

### F-063 - Uninstall that is complete and needs no Python

- Rank 63, tier P1; area deploy; kind feature.
- Action: uninstall.ps1 at the home root, also behind Apps & features: stop via stop.request and the registry, remove the logon task if present, shortcuts, key, code, runtime, cache, logs, temp; keep data\ unless -Purge (Recycle Bin); exit 1 with one line while anything remains; -DryRun prints the plan.
- Impact / effort / risk: H / M / Deleting a wrong folder, held by fixed child names under a home with a valid marker, else refusal.
- ToS check: Touches no game folder even where player copied an AshLight filter/build file there (0031, 0033, 0034); last lines name those files. Stops only pids proven ours.
- Sources: 0052-R5, 0053-R5
- Depends on: F-050
- Acceptance: Scratch home ends with only data\; -Purge leaves nothing (recycle injected); held file gives exit 1 and the one line; -DryRun changes nothing; PS 5.1 parse.
- ZERO-CLICK: One click in Apps & features; no question by default.
- Disposition: plan
- Notes: 0053-R5's AshLight.cmd first-run wrapper is superseded by the installer (Fit points 5 and 6). Touches no game folder, even where the player copied an AshLight filter or build file.

### F-064 - TC-DRIFT-TRIAL-FIX: a trial that can end green

- Rank 64, tier P1; area automation; kind fix.
- Action: Re-hash pob2_files from the extracted candidate after setup and record old / new hash plus parsed row count for review at apply; add 'trial --ref <branch or commit>' (static by default, never accepted by apply); key the GUI reference by tag (same tag: compare numbers; else per-key deltas and a recorded reference or a session's written acceptance); prune candidates other than the pin and the newest.
- Impact / effort / risk: H / M / Medium; (c) changes what live-green means and needs an adjudicated amendment to decisions 0025 and 0028.
- ToS check: None touched; build-time dev tooling on public repo files; candidate Lua still runs only on the manual trigger.
- Sources: 0037-R3
- Depends on: F-039
- Acceptance: Fakes prove (a) to (d); a rehearsal against beta reports static-green after R1.
- ZERO-CLICK: Static tier unattended; the live tier stays manual by decision 0025.
- Disposition: plan
- Notes: Part (c) adds detail to decisions 0025 and 0028 without reversing them: amendment lines at landing. The pin still moves only via apply, committed by a session.

### F-065 - Wave gate policy: named-file subset per package, one whole suite per merge batch

- Rank 65, tier P1; area tests; kind infra.
- Action: tools/test_select.py (stdlib) prints the test files for a diff (direct map, always-run hygiene list, changed tests, unknown path = whole area); packages run that list file-named in their own worktree; the merge agent merges 4-5 packages on an integration worktree and runs the whole suite once through the gate; live calc tests are marked 'calc' and join a subset only when theorycraft or the pins change.
- Impact / effort / risk: H / M / Subset misses a cross-module break (batch suite catches it, one extra suite); escape rate e unmeasured.
- ToS check: No floor rule touched; static floor scan, overlay smoke static part and budget tests stay in the always-run list.
- Sources: 0049-R1, 0049-R9
- Depends on: F-022
- Acceptance: For 20 past merge commits selected files include every test file the commit changed; median selection run under 30 s; dry wave of 8 packages lands with at most 3 whole-suite gate rows.
- ZERO-CLICK: Tool reads the diff itself; no flag, no prompt.
- Disposition: needs-ruling: Q-17
- Notes: The escape rate of subsets is measured per batch in wave 1 (0049-Q3). The floor's guards (static floor scan, overlay smoke static part, budget tests) are always in the subset.

### F-066 - Put the glance budgets under test

- Rank 66, tier P1; area tests; kind test.
- Action: One CDP test builds the pack states on a demo core and asserts budgets B1-B7: no scroll in the Play columns at 1280x760 and 1920x950 in states b, c, c2, d, f, g; at least 40 px spare in state c; word, element and control caps; first-view controls.
- Impact / effort / risk: H / M / A test core with a missing log path tails the live log (PACK Incident); fixture must create the log file first and pin discovery as the pack script does. Never part of a whole-suite run touching port 8960.
- ToS check: Test only; synthetic log, no game, no live Client.txt.
- Sources: 0043-R2
- Depends on: F-025, F-034
- Acceptance: Red on today's layout (state c: 380 px), green after R1.
- ZERO-CLICK: Runs in the gates; no player act.
- Disposition: plan
- Notes: Closes the open measurements: state g (web data on, item card), B2 and B4 values, and each Play addition (F-069, F-124, F-041, F-068) re-runs it when built.

### F-067 - Four tabs and closed folds; Settings owns the switches it holds and indexes the rest

- Rank 67, tier P1; area play-tab; kind design.
- Action: Tabs: Play, Build and items, Run, Settings. Items and prices merges into Build and items (build, health, search strings, stat weights closed, currency values and movers) and Settings (web data with contact and league, hotkeys, overlay parts, theme, tools, Checks); a short index atop Settings jumps to switches that live elsewhere; Recent and Death recap cap at 8 rows with a fold.
- Impact / effort / risk: H / M / Picked-tab memory names a gone tab (map it to its new home once).
- ToS check: Layout only; web-data switch keeps default OFF and its wording (decision 0013).
- Sources: 0043-R6, 0042-R10
- Depends on: F-018, F-025, F-056
- Acceptance: The tab row has four tabs; budget B8 of note 0043 (tab and fold counts) holds; with folds closed no column scrolls in state f at 1920x950; every switch named in the Settings index jumps to and focuses its control; tab tests and design 0001 list the four tabs.
- ZERO-CLICK: Play still shows by itself; nothing new to press.
- Disposition: plan
- Notes: Conflict resolved: four tabs (0043), not five (0038 cut-or-merge); the three-tab set stays rejected (0043-X9). Design 0001 and the tab tests change with it.

### F-068 - Play follows the context: campaign, map, post-map, idle

- Rank 68, tier P1; area play-tab; kind feature.
- Action: In a map the zone tile shows this map's time and deaths, maps this session, per hour and average; on return to hideout or town a one-line map summary shows for the stay; Last session moves to Run and shows on Play only while the game is idle; build alert, upgrades and tip share one notice slot.
- Impact / effort / risk: M / M / Needs the endgame Map prefix proven by the parse ledger; the Play height must be re-measured.
- ToS check: Client.txt-derived state already in snapshot; dashboard only; no new read.
- Sources: 0038-R6, 0055-R7
- Depends on: F-025, F-061
- Acceptance: Replayed session shows map block in a map, guide in a campaign zone, Last session on Play only while idle; Play fits viewport at 1280x760 and 1920x950 with a trade and a notice.
- ZERO-CLICK: Follows the log.
- Disposition: plan
- Notes: Needs the live endgame Map prefix sighting from F-061. Adds about 47 words and 36 px (0043 fit note): re-run F-066.

### F-069 - Setup card: finish first run in one place

- Rank 69, tier P1; area play-tab; kind feature.
- Action: Replace the consent card by one 'Set up AshLight' card of 4 rows with state glyphs (allow reading Client.txt, your build, prices, overlay); once row 1 is done it folds to one line 'Setup: N steps left' in the Play notice slot that jumps to the controls on Settings.
- Impact / effort / risk: H / M / Play must fit without page scroll (design 0001 section 4): the card replaces the consent card, does not add one.
- ToS check: Row 1 is the floor's Client.txt opt-in with visible indicator, unchanged; rows 2-4 read nothing new; web data stays OFF until ticked (decision 0013).
- Sources: 0054-R1
- Depends on: F-018, F-025, F-026
- Acceptance: Cold profile shows the 4 rows and nothing else on Play; after row 1 the feed is live and rows 2-4 can each be done or skipped without leaving Play; the card then goes; at most 12 live regions; no page scroll at 1280x760.
- ZERO-CLICK: One required click (the floor's opt-in); other rows optional and clear themselves when their data arrives.
- Disposition: plan
- Notes: Conflict resolved: the card is on Play only until consent is given; the controls live on Settings (0039, 0042), which keeps the 8-control cap of Play (0043 B5). Row 1 keeps the opt-in words and the visible indicator unchanged.

### F-070 - Worn-gear baseline: 'I wear this'

- Rank 70, tier P1; area items; kind feature.
- Action: The last checked item can be filed as the worn item of its slot for the current character by an 'I wear this' button on the item card (no new read: the text of that press) or by an optional wear hotkey (unset by default); the item check compares against the worn item first, the PoB plan second, and works with no build on default weights.
- Impact / effort / risk: H / M / Slot choice for rings and one-hand weapons (reuse the slot last compared when texts match, else empty or older slot); a third global hotkey; one press per equip to learn. Store parsed stats, name, base only, bounded 16 slots x 12 characters, with a switch and a Clear button.
- ToS check: Clipboard text of one manual press of an AshLight hotkey; player copies in game; no input sent; nothing leaves the PC. Decision 0004 holds (existing weight scoring).
- Sources: 0038-R1
- Depends on: F-026, F-060
- Acceptance: No build: 'I wear this' on ring A, then a check on ring B gives an ok card naming ring A (today an error); with a build the card carries both lines; the button causes no clipboard read and the optional key reads once per press; with the file ruled in, a restart keeps the worn set and Clear empties it; the static floor scan and the sidecar path test stay green.
- ZERO-CLICK: One manual press per equipped item (floor requires a press); verdicts then follow by themselves.
- Disposition: needs-ruling: Q-26
- Notes: Conflict resolved (hotkey budget): the wear key is not a third default key. Storage form waits for the ruling.

### F-071 - Follow the Path of Building builds folder (zero-paste build)

- Rank 71, tier P1; area theorycraft; kind feature.
- Action: A third build source: after one opt-in showing the folder path, each loop tick stats the folder and loads the newest saved build that fits the played character.
- Impact / effort / risk: H / M / Wrong file picked (bounded by class and level checks and alert naming the file); custom PoB folder; portable or dev PoB keeps user data next to the program (Main.lua:82-84), so default path wrong there and one-time pick is fallback; PoB user path being Documents UNVERIFIED.
- ToS check: Reads the player's own planner files written by PoB, not the game: no game file, process, clipboard, screen, network or input; a file change starts no macro. But the CLAUDE.md floor's READ ONLY list literally names only Client.txt, clipboard/screen per press and public web data; precedents decision 0033 and the 0037 amendment. Verifier: keep as rec, do not build before a recorded ruling; if floor list is exhaustive, R3 moves to Rejected and R4 carries the build pain.
- Sources: 0043-R3
- Depends on: nothing
- Acceptance: With source on, writing a fixture XML into a temp builds folder changes build in the snapshot within one tick; a file of another class is not picked; off by default; no read before opt-in.
- ZERO-CLICK: After the one opt-in, saving in PoB is the only act.
- Disposition: needs-ruling: Q-01
- Notes: Conflict (0043 recommends, 0042-X4 rejects, 0054 and 0035 ask): the floor's READ ONLY list does not name it, so the strict reading treats it as outside until the operator rules. F-042 and F-058 carry the build pain meanwhile.

### F-072 - Let the game-data snapshot arrive without a terminal

- Rank 72, tier P1; area setup; kind feature.
- Action: Step 1 (inside today's decisions): setup.ps1 runs the snapshot step when web_data is already true; README and the Checks fix line say 'tick Use web data, then build' in player words. Step 2 (after the ruling): the launcher runs the existing snapshot tool as a hidden low-priority process at start when web data is on and the cache is missing or older than 24 h.
- Impact / effort / risk: H / M / 48 MB first fetch during play; start and idle time only, one run at a time. Effort S step 1, M step 2.
- ToS check: Public web data rule; same sources, opt-in, User-Agent and contact as decision 0009; nothing bundled.
- Sources: 0039-R1
- Depends on: nothing
- Acceptance: Step 1: setup run with web_data true in a sandbox leaves the five snapshot files, with false makes no request. Step 2: web data off -> no request at start; on -> test core with fake fetch has files within one supervisor poll, no second request inside 24 h; no fix line names build.ps1.
- ZERO-CLICK: Step 2 needs nothing beyond the web-data tick; step 1 still needs one typed command after the tick.
- Disposition: needs-ruling: Q-04 (step 2 only; step 1 is plan work)
- Notes: The core never fetches the snapshot (0037-X1, 0039-X8, 0058-X8 stay rejected).

### F-073 - Autostart that is worth enabling

- Rank 73, tier P1; area electron; kind feature.
- Action: A 'Start with Windows' checkbox in the tray and on Settings (runs the existing autostart script hidden) and a logon task that starts the client in a tray-only mode (no companion window; overlay gated by the log) instead of the core alone.
- Impact / effort / risk: H / M / About 180 MB idle from logon (app/main.js:121-126), measure; fallback: core-only at logon, tray client on first fresh log line.
- ToS check: Overlay stays a separate click-through window inside the client; game start read from Client.txt freshness only (decision 0029); opt-in, off by default, per-user task.
- Sources: 0039-R4
- Depends on: F-032
- Acceptance: -DryRun shows the tray-client action; node test: tray mode builds tray and overlay, no companion window, no focus call; test-port run records idle memory against the 250 MB budget.
- ZERO-CLICK: One tick once.
- Disposition: needs-ruling: Q-08
- Notes: Stays opt-in and OFF by default (decision 0011). The idle memory number comes from F-032.

### F-074 - Stage and publish gates

- Rank 74, tier P1; area deploy; kind infra.
- Action: 'tools/release.py stage' writes a PASS / FAIL stage.json: suite through the gate, node tests, two identical builds, leak sweep of the staged tree, a scratch-home install / update / rollback / uninstall round trip, optional sandbox phases (.wsb with networking and clipboard off, assets in a read-only mapped folder); a v* tag is pushed only after PASS.
- Impact / effort / risk: M / M / A release by accident, held by typed phrase and the loop having no path to it.
- ToS check: Notes and assets pass README brand checks and carry disclaimer; no revenue; publishing touches no game system; CI keeps web data off.
- Sources: 0052-R7
- Depends on: F-048, F-050, F-063
- Acceptance: Every gate has a refusal test where nothing changed; rehearse makes 0 pushes; digest mismatch fails read-back; planted drive path fails CI. Sandbox phases never run while game runs.
- ZERO-CLICK: One operator phrase per release (operator order); everything before and after automatic.
- Disposition: plan
- Notes: Conflict resolved (who cuts a release): local stage is the gate, the published artifact is built, compared and attested by CI on the tag (F-076). The sandbox phases verify the per-user uninstall key on Windows 10 and 11 (undocumented by the vendor).

### F-075 - GP-COMMUNITY: code of conduct, issue forms and PR template

- Rank 75, tier P1; area go-public; kind docs.
- Action: CODE_OF_CONDUCT.md (own short text, private report route, no email); issue forms: bug (asks for the redacted Checks report and the ledger shape list for English clients, never raw Client.txt) and feature (asks which floor rule it might touch); PR template with the gate commands.
- Impact / effort / risk: L / S / L.
- ToS check: Bug form forbids attaching game files or memory dumps; redacted report only.
- Sources: 0057-R11
- Depends on: nothing
- Acceptance: Community profile health 100 (gh api community/profile) after push.
- ZERO-CLICK: Documentation only.
- Disposition: plan
- Notes: Should-fix before the flip. Absorbs the issue-template half of 0051-R6.

### F-076 - Tag-triggered CI release

- Rank 76, tier P1; area deploy; kind infra.
- Action: A workflow on v* tags: tests, tools/release.py build, compare SHA256SUMS with the staged build, provenance attestation, draft release, assets, publish as immutable; actions pinned by commit; the identity guard stays required.
- Impact / effort / risk: H / M / M: first CI in tree; needs remote.
- ToS check: Releases free; text uses game name descriptively, carries disclaimer; no GGG art in release images.
- Sources: 0053-R6
- Depends on: F-021, F-048, F-074, F-101
- Acceptance: RC tag in a test repo yields release whose assets match SHA256SUMS; gh attestation verify and gh release verify-asset pass; notes list every feat/fix subject in range; plain commit triggers nothing.
- ZERO-CLICK: Pushing the tag is the only act.
- Disposition: blocked: the remote exists and immutable releases are on (F-021); the workflow file is prepared before
- Notes: Conflict resolved (changelog): one generator, 'release.py notes' (F-101); tools/changelog.py is not built.

### F-077 - Update and rollback

- Rank 77, tier P1; area deploy; kind feature.
- Action: update --check / --yes / --zip FILE and rollback in the installer package: download, verify size, SHA-256 and attestation, stage into app\<new version>\, self-check, switch the marker at the next client start (or on 'Update now') after a 24 h hold, keep the previous version for rollback; Checks and the copied report show mode, version, previous and the last update result.
- Impact / effort / risk: H / L / A bad release, held by self-test, automatic rollback and one kept previous version.
- ToS check: Decision 0013: check and download behind web-data opt-in; off = Settings shows version and a releases link opened in own browser. Download/extract below-normal priority, never during live session unless clicked. Report redacted, click-only (0040, 0014).
- Sources: 0052-R6, 0053-R8
- Depends on: F-050, F-055, F-076
- Acceptance: N to N+2 with fake release keeps data\ byte for byte; tampered zip refused; failed self-test leaves marker on N with exit 1; rollback restores N and reads back marker and uninstall entry; web data off: fake fetch 0 calls.
- ZERO-CLICK: Web data on: no click, next start runs new version, one line names it. Off: one click on releases link.
- Disposition: needs-ruling: Q-21
- Notes: Conflict resolved (mechanism): marker switch between version folders (0052), not an in-place swap (0053-R8 original). Never while web data is off; the restart is timed by game_idle from the log, never a process check. Network half blocked until a published release exists.

### F-078 - LOOP-RESUME: remove HALT only after the six checks

- Rank 78, tier P1; area loop; kind operator.
- Action: A session removes ops/loop/control/HALT when all six checks of F-033 pass: plan rows in ROADMAP and the lint green; every session row tagged; the hand-off yields 0 loop items; preflight green with the client running; the gate under half the cap; a dry-run tick lists only intended rows. The LaneLoop task stays installed.
- Impact / effort / risk: H / S / A resumed loop without R1 burns runs (L3).
- ToS check: No floor rule touched; every act is the operator's own.
- Sources: P01-LOOP-RESUME, P01-R9, P01-L15
- Depends on: F-024, F-028, F-033
- Acceptance: The dry-run tick after the six checks lists only intended rows; HALT is absent; the next real tick dispatches at most the rows the dry run listed.
- ZERO-CLICK: Tick resumes by itself every 15 minutes.
- Disposition: blocked: the six checks pass; plan 07 names the step and the session that runs it
- Notes: Conflict resolved: the six checks (0058), not 'after R1 lands' (plan 01 R9). The batched ask of P01-R9 is F-040.

### F-079 - GP-META: description, topics, social preview

- Rank 79, tier P1; area go-public; kind docs.
- Action: Set the description ('Unofficial second-screen dashboard and click-through overlay for Path of Exile 2 on Windows. Reads the game's log file; never touches the game process. Not affiliated with Grinding Gear Games.'), the topics and the own-art social preview.
- Impact / effort / risk: M / S / L.
- ToS check: Game name only as a 'for' phrase; no funding link.
- Sources: 0057-R9
- Depends on: F-021
- Acceptance: gh repo view --json description,repositoryTopics read-back matches.
- ZERO-CLICK: Agent step.
- Disposition: blocked: the repository exists (F-021 step 1); done before the flip

### F-080 - TC-IMPORT: character import through GGG's OAuth (the zero-paste end state)

- Rank 80, tier P1; area theorycraft; kind feature.
- Action: A Connect action (web data on) opens GGG's consent page in the system browser; then fetch on events only (core start, character switch, level-up, town / hideout entry when the last fetch is over 5 min old, a Refresh click); tokens in the OS credential store; measure staleness once.
- Impact / effort / risk: H / M / Limits shared with every public client; staleness unknown; the weekly approval. Effort M after R4.
- ToS check: Documented endpoints, player's own account by consent on GGG's page, no POESESSID, nothing sent to the game, headers obeyed; log-based triggers come from the opted-in Client.txt tail and an API read sends no input, so D-IDX's file-change ban (macro rules) is not hit.
- Sources: 0035-R5, P01-TC-IMPORT
- Depends on: F-035, F-116, F-149
- Acceptance: Mocked-flow tests ROADMAP asks for, one live smoke by the operator, and a lapsed grant leaves the last import loaded.
- ZERO-CLICK: No click between approvals; one browser approval per 7 days is GGG's limit (F4). A lapse shows the last import with its age and a quiet reconnect note on the dashboard, never the overlay.
- Disposition: blocked: GGG reopens OAuth registration (docs watch raises REG_OPEN) and grants AshLight a public client
- Notes: Refresh lifetime is 7 days and may not be granted to a desktop app: a lapsed grant is the normal case and the last import stays usable. Never a POESESSID, never another tool's client id.

### F-081 - GP-DEPENDABOT: config plus the local re-apply lane

- Rank 81, tier P1; area go-public; kind infra.
- Action: .github/dependabot.yml (npm in /app and github-actions, weekly, one group per ecosystem, cooldown 3 days and 14 for majors, the identity-guard copy excluded); a lane tool re-applies each open bump locally as an operator commit through the bump gates, pushes and closes the PR with a one-line comment; bump PRs are never merged on GitHub.
- Impact / effort / risk: M / M / L; bot PR red identity check expected and harmless.
- ToS check: None touched.
- Sources: 0057-R8, 0046-R9
- Depends on: F-021, F-037
- Acceptance: 0046 R9 fixture test; YAML lint in R3's test.
- ZERO-CLICK: Lane runs from the loop tick.
- Disposition: blocked: after the flip (F-021); the config file and the lane tool are prepared before

## Tier P2 - high player value and hardening

### F-082 - Real item-press samples before 1.0

- Rank 82, tier P2; area tests; kind test.
- Action: An off-by-default dev switch 'keep this as a test sample' and a sanitizer; during normal play the operator presses once each on rare gear, a unique, a currency stack, a waystone, a tablet and a gem (plain and advanced copy); sanitized samples land in the sidecar and become fixtures after review.
- Impact / effort / risk: H / S / Samples hold names and chat; sanitize and review before commit.
- ToS check: Same reads as normal use (opted-in tail; one clipboard read per press); samples stay local until sanitized.
- Sources: 0038-R4
- Depends on: nothing
- Acceptance: A fixture and passing test per shape; LIVE-1 'remains' list empty or each item says why not reachable; UNVERIFIED comments in parser.py:33-66 updated.
- ZERO-CLICK: A one-time check.
- Disposition: needs-ruling: Q-27; then operator: six presses during normal play
- Notes: Conflict resolved: no scripted 30-minute session; log shapes close passively through F-061; only item-press samples need the operator.

### F-083 - Prepare the GGG application and its decision now

- Rank 83, tier P2; area data-sources; kind decision.
- Action: Write the application note (public client; auth code with PKCE plus refresh; account:characters and account:item_filter with a one-line reason each; loopback redirect URIs on 8979 and 8978; two questions for GGG: refresh tokens for a desktop client, and the public Currency Exchange endpoint) and the decision that amends decision 0004 item 4 for an own client id.
- Impact / effort / risk: H / S / GGG may decline or stay closed; preparation is cheap.
- ToS check: Documentation only; the application is the path D-IDX requires of an executable; no floor rule bent.
- Sources: 0035-R2
- Depends on: nothing
- Acceptance: Every one of the six asks answered with no private value (leak sweep clean); the decision has a Reverses if; the ROADMAP line is corrected.
- ZERO-CLICK: The watch raises REG_OPEN by itself; sending is one operator act because a registration belongs to the operator's account.
- Disposition: plan
- Notes: account:profile is cut from the scope request. The contact in the application follows Q-03. Sending waits for registration (F-149).

### F-084 - LADDER-TICK: make the map ladder tick free when nothing changed

- Rank 84, tier P2; area perf; kind fix.
- Action: Save finished maps when a map closes; key saved maps by (area id, seed); rebuild the all-sessions view only when session rows or the saved list changed.
- Impact / effort / risk: H / S / A map rebuilt after restart must still match its saved record within 120 s (MATCH_S); tests exist.
- ToS check: No floor rule touched; reorders work on data derived from opted-in Client.txt.
- Sources: 0048-R1
- Depends on: nothing
- Acceptance: B1 and B2 on the 200 plus 500 fixture; ladder tests green.
- ZERO-CLICK: Nothing to do; ladder still fills by itself.
- Disposition: plan
- Notes: Closes AUDIT-P8-LOW P8-5 (about 10 ms per 0.5 s tick today).

### F-085 - PRICE-SHAPE-GUARD: a silent shape change keeps the last good prices

- Rank 85, tier P2; area prices; kind fix.
- Action: Treat 'HTTP 200, lines present, no usable entry' and 'fewer than half the lines kept, 5 lines or more' as a shape error: keep the last good entries, set last_error 'shape: ...', publish per-type state in /api/rates and feed the Checks card with the worst type.
- Impact / effort / risk: H / S / An empty type at league start must stay quiet, so zero lines is never an error.
- ToS check: Public-web-data rule; no request added, checks are local.
- Sources: 0036-R4
- Depends on: nothing
- Acceptance: A body with a renamed value key keeps yesterday's entries, sets a 'shape' error and a failing Checks line naming poe.ninja; an empty-lines body raises nothing.
- ZERO-CLICK: Automatic.
- Disposition: plan

### F-086 - Dark unless the player chooses otherwise; one palette for the client window

- Rank 86, tier P2; area electron; kind design.
- Action: Ship <html data-theme="dark"> and set nativeTheme.themeSource to dark before the first window; one Settings choice 'Theme: Dark / Follow Windows / Light'; the start page is always dark with the kit values and the window background matches; replace the 820 px short-window threshold by one that covers the default window.
- Impact / effort / risk: H / S / A player who wants light must find the setting; the start page cannot read it before the core is up (R6 makes that page dark). Effort S for the default, M with the setting.
- ToS check: Display only on AshLight's own windows; no read, input or network rule touched; footer disclaimer untouched.
- Sources: 0040-R1, 0040-R6
- Depends on: nothing
- Acceptance: With prefers-color-scheme light emulated the page background computes to rgb(15,18,22) and a capture has mean relative luminance < 0.05; with the setting on Light it computes to white; a node test proves themeSource is set before window creation.
- ZERO-CLICK: Dark with no action; the choice is one optional click.
- Disposition: plan
- Notes: Both the desktop client and the browser path start dark (static attribute).

### F-087 - Stale and empty values look stale

- Rank 87, tier P2; area play-tab; kind design.
- Action: Set data-fresh="no" on body while the tailer is idle or the feed is down and data-empty on a tile with no value; under either, glance values and timers use the stale text token; the words stay so colour never works alone.
- Impact / effort / risk: H / S / Low; 7.18:1 at 28 px and up stays readable.
- ToS check: Idle state comes only from Client.txt staleness (decision 0029); no process check, no new read.
- Sources: 0040-R3
- Depends on: nothing
- Acceptance: In PACK state d the computed colour of #zone and the three tile values is rgb(153,161,170); in state c rgb(228,232,236); in state a the dashes are muted.
- ZERO-CLICK: Follows the feed by itself.
- Disposition: plan

### F-088 - ZONE-RESET: one function clears per-zone state

- Rank 88, tier P2; area reliability; kind refactor.
- Action: Move every per-zone field reset into one _enter_zone() called from the scene, area-generated and area-entered branches, with a zone generation counter that per-zone timers and cards check before publishing; a test lists the zone-scoped fields.
- Impact / effort / risk: M / S / Changing LIVE-RESUME replay order; keep _REPLAY_TYPES (state.py:1747), run resume tests.
- ToS check: Client.txt lines only.
- Sources: 0056-R7
- Depends on: nothing
- Acceptance: A card scheduled in zone 1 never publishes after a zone 2 generation line; field list test fails if a new zone field skips the reset.
- ZERO-CLICK: Automatic.
- Disposition: plan

### F-089 - Run the whole suite in parallel, with one gate spelling

- Rank 89, tier P2; area tests; kind infra.
- Action: Give the session gate, done.md and build.ps1 the loop gate's accelerator (xdist when importable, serial otherwise; -n 4, loadgroup with groups for calc files and the three fixed-port files, timing files after the parallel phase); one helper builds the gate command; a kit traceback in gate output is infrastructure and retried once.
- Impact / effort / risk: H / S / S for xdist (code exists), M for shard tool. Parallel-only flakes; machines without xdist stay serial.
- ToS check: No floor rule touched; bounded workers at below-normal priority; nothing reads the game process.
- Sources: 0049-R3, 0049-R7
- Depends on: F-022
- Acceptance: 10 consecutive parallel whole runs green on a quiet tree; median hold under 75 s; one command spelling in GATELOG; a run with xdist hidden still passes serially.
- ZERO-CLICK: Gate command picks the mode itself.
- Disposition: needs-ruling: Q-16
- Notes: First step (research gap): three diagnosed parallel runs through the gate to find why 24 of 37 loop-gate xdist runs were red; if the plugin is ruled out, the stdlib shard tool takes its place.

### F-090 - OBS-LOGS: every log bounded, one format

- Rank 90, tier P2; area observability; kind fix.
- Action: Rotate at start when over 1 MB (one old file kept) for core.log, keepalive.log, overlay.log, run.log and tc-bridge.log, with a 2 MB in-run backstop for the core; UTC ISO time stamps, a level word and the pid; a banner line per start; faulthandler on its own small file; a repeating tick error is logged once, then once a minute with a count.
- Impact / effort / risk: M / S / PYLOG: no rollover when backup count is 0; PYFAULT keeps its fd, needs its own always-open file once core log rolls.
- ToS check: AshLight's own files in its sidecar only.
- Sources: 0051-R7, 0050-R6
- Depends on: F-027
- Acceptance: A 1.1 MB log becomes .1 at next start and new file starts with the banner; native-fault test writes to crash file after rollover; no log line holds an absolute path (test).
- ZERO-CLICK: At start, by itself.
- Disposition: plan
- Notes: Conflict resolved: the 0051 rotation scheme (the note that owns the format); 0050 contributes faulthandler and the repeat throttle.

### F-091 - START-REASON: a start failure names its cause; ports stay in the block

- Rank 91, tier P2; area reliability; kind fix.
- Action: On a bind failure the core probes the port once: an AshLight core answering means 'already running', anything else writes ops/runtime/start-error.json that run.ps1 and the client's failed page print; app/main.js refuses a core port outside 8960-8979 and the core refuses --port outside the block (0 for tests).
- Impact / effort / risk: M / S / Low.
- ToS check: Loopback only; bind 127.0.0.1 and the port block stay.
- Sources: 0050-R8
- Depends on: nothing
- Acceptance: C24.
- ZERO-CLICK: The line names the one fix; moving to a free block port by itself is Q5.
- Disposition: plan
- Notes: Carries AUDIT-P8-LOW P8-3 and P8-4. On a conflict AshLight only says so; it never moves to another port by itself (links, shortcuts and the overlay rely on the constant).

### F-092 - HOTRELOAD-RETRY: never pin a stale copy on a transient read error

- Rank 92, tier P2; area reliability; kind fix.
- Action: Watched.get() records the new signature only after a load that succeeded or failed on content; on OSError it leaves the signature unchanged so the next poll retries, with a bounded retry (3 tries, 100 ms); a stat error keeps the last good copy and adds a Checks note.
- Impact / effort / risk: M / S / A permanently unreadable file retries every poll (one stat plus one open per second at most, inside overlay budget 0048); keep note text stable so Checks does not flicker.
- ToS check: Own data files only; nothing game-side.
- Sources: 0056-R4
- Depends on: nothing
- Acceptance: Test loader raises PermissionError once then succeeds with same mtime and size; next get() returns new value; JSON syntax error still keeps last good copy without a retry storm.
- ZERO-CLICK: Fully automatic.
- Disposition: plan
- Notes: Defect at hotreload.py:143-155; also closes the first gap of 0050 F31 (a stat error drops the last good copy with no note).

### F-093 - QUIET-FEED: no push when nothing changed

- Rank 93, tier P2; area perf; kind fix.
- Action: Take the minute stamp out of the snapshot (stamp the report when copied); step 'N min ago' texts at 5 minutes; read Checks facts without building a snapshot.
- Impact / effort / risk: M / S / A Checks row a few minutes stale; fine for 'ago'.
- ToS check: No floor rule touched; text of AshLight's own checks.
- Sources: 0048-R7
- Depends on: nothing
- Acceptance: B4.
- ZERO-CLICK: Automatic.
- Disposition: plan

### F-094 - Overlay legibility recipe and two type sizes

- Rank 94, tier P2; area overlay; kind design.
- Action: Drop the page opacity fade: text is opaque, the slider (relabelled 'Background') sets plate alpha only (default 0.86, floor 0.80); overlay-only secondary and warn text tokens; a soft three-layer shadow, no stroke; HUD lines 16 px, cards and their lines 14 px, status word at HUD size; the '|' span becomes a 10 px gap.
- Impact / effort / risk: H / M / Slider meaning changes from whole HUD to background; saved layouts 0.9-1.0 map linearly onto 0.86-1.0. Halo blur costs one rasterisation per text change (no animation; render_gate unchanged).
- ToS check: Overlay rule / FPS budget (decision 0002): CSS only, no new window behaviour, no repaint frequency change; nothing reads the screen to adapt the plate.
- Sources: 0041-R1, 0041-R2, 0044-R11
- Depends on: nothing
- Acceptance: Unit test composites every overlay text token over the plate at floor and default alpha over #ffffff and #f2e6c8 with 8-bit rounding: primary >= 7, secondary and warn >= 5.5 at floor, >= 7 at default; CDP overlay smoke renders plate over white and asserts brightest-3-percent glyph core of secondary >= 5.5 at floor; html has no opacity rule.
- ZERO-CLICK: Applies at the next overlay start; nothing to press.
- Disposition: plan
- Notes: Conflict resolved: the 0041 recipe (owner) replaces the optional plate change of 0044-R11 and 0040's 'no token change'; the 3.81:1 pack reading is a method error, today's value is about 4.88:1. CSS only, no new repaint. Design 0001 sections 5.2 and 10 are amended through the design reviewer.

### F-095 - Glance budget and notification policy into design 0001, with tests

- Rank 95, tier P2; area overlay; kind design.
- Action: Design 0001 section 10: a card's first line starts with the verdict word or the buyer inside the 34-character clip; a card that leaves the overlay by itself stays findable on the dashboard; section 7.1: no Windows toast, sound or taskbar flash during play. Tests walk every overlay card kind and grep for notification APIs.
- Impact / effort / risk: M / S / L
- ToS check: Display only.
- Sources: 0055-R5, 0055-R6
- Depends on: nothing
- Acceptance: The test fails if a card kind is added to render_gate without a dashboard twin selector.
- ZERO-CLICK: Not player-facing.
- Disposition: plan

### F-096 - Fix the Play column focus and keep focus on the selected tab

- Rank 96, tier P2; area play-tab; kind fix.
- Action: Drop tabindex from #panel-play, keep the two columns as labelled groups with tabindex 0 and draw their ring inside; when Play is shown automatically, focus in the tab row stays on the current tab.
- Impact / effort / risk: M / S / Low; tests/test_a11y.py:202 stays green.
- ToS check: Layout only; touches no floor rule.
- Sources: 0044-R2, 0044-R5
- Depends on: nothing
- Acceptance: R1 walk shows 3 px ring on all four edges of each column at 1280x760 and 1024x700; Play stops 11 -> 10 in PROBE state f; after MERGE-SEAMS F4 the .col groups on Run, Build, Items show the same full ring.
- ZERO-CLICK: No player step.
- Disposition: plan
- Notes: Carries MERGE-SEAMS-FOLLOWUP F4.

### F-097 - PROVENANCE: a source and check date on every authored fact

- Rank 97, tier P2; area data-sources; kind data.
- Action: Add src (research key) and checked (date) fields to entries in the authored data files (boss elements, waystone rules, zone guide, level rules); a test fails on an entry missing them; the 1.0 re-verify list is generated from entries older than the patch.
- Impact / effort / risk: M / S / Churn in data files; fields ignored by readers. Effort S per file.
- ToS check: Own data files; facts stay in own words (decisions 0039, 0043).
- Sources: 0056-R9
- Depends on: nothing
- Acceptance: Data test lists zero entries without src and checked; a script prints entries checked before a given date.
- ZERO-CLICK: List produced by the loop or a test.
- Disposition: plan

### F-098 - Find Client.txt outside Steam

- Rank 98, tier P2; area setup; kind feature.
- Action: A 'Can't find Client.txt?' field on the consent card for the folder or file, sent through the existing consent API; discovery also tries the standalone client's default folder once that path is confirmed.
- Impact / effort / risk: M / S / Low; path check exists (logfile.py:106-132).
- ToS check: Only Client.txt, only after the opt-in; a folder stat reads no game file; game registry keys and config files stay unread (research 0032).
- Sources: 0039-R6
- Depends on: F-001
- Acceptance: A posted path starts the tailer; a bad one shows the existing error; discovery finds a fake non-Steam tree in a temp dir.
- ZERO-CLICK: Discovery first; field shows only if nothing is found.
- Disposition: plan
- Notes: A file path must be named Client.txt (F-001).

### F-099 - Companion window on the second monitor on first run

- Rank 99, tier P2; area electron; kind feature.
- Action: With no usable saved window state and two or more displays, centre the companion on the largest work area that is not the overlay's display.
- Impact / effort / risk: M / S / L: a player whose game is on a non-primary display without the overlay moved there may get the companion on the game display; saved place wins from second start.
- ToS check: Electron display list only, no window or process enumeration of the game (decision 0029 intact).
- Sources: 0055-R1
- Depends on: nothing
- Acceptance: Unit test: work areas [primary 1920x1080, second 2560x1440], overlay on primary, no saved state returns bounds in second; overlay on second returns primary; one area returns today's centred bounds; saved visible bounds still win.
- ZERO-CLICK: Fully automatic on first start; no question.
- Disposition: plan
- Notes: Uses Electron's display list only; no window or process query of the game.

### F-100 - Four in-game tries by the operator

- Rank 100, tier P2; area items; kind operator.
- Action: The operator (1) loads one AshLight-made .build in game, (2) pastes one search string to confirm a leading '!' negates the whole OR group, (3) imports the downloaded filter snippet, (4) loads a merged real filter; each ends in one click on the 'Tried in game' card.
- Impact / effort / risk: M / S / Low.
- ToS check: The player saves files and pastes strings; AshLight writes nothing into game folders and sends nothing to the game (decisions 0031, 0033, 0034).
- Sources: P01-TC-BUILDFILE-LIVE, P01-LIVE-SEARCHSTR, P01-LIVE-FILTER, P01-LIVE-FILTER-MERGE
- Depends on: F-062
- Acceptance: Four verdicts recorded in the bounded verdict file; the read-back script drafts the ROADMAP flips; a refusal files a fix row.
- ZERO-CLICK: Each try ends in one click; no typed report.
- Disposition: operator: four in-game tries, one click each (one batched ask)

### F-101 - REL-NOTES: one changelog generator

- Rank 101, tier P2; area deploy; kind infra.
- Action: 'tools/release.py notes' drafts a version's notes from first-parent merge subjects since the last tag joined to row titles, grouped Added / Changed / Fixed / Security (commit type feat -> Added, fix -> Fixed); each wave ends with a pre-filed REL-PREP-<n> row whose lane curates the draft.
- Impact / effort / risk: M / S / Noisy draft; the lane edits it.
- ToS check: Notes carry not-affiliated statement and no GGG art.
- Sources: 0058-R9
- Depends on: F-023, F-024
- Acceptance: Fixture history of 3 merges yields 3 grouped lines; subject without a type refused.
- ZERO-CLICK: Prepared unattended; one operator phrase per release.
- Disposition: plan

### F-102 - FS-TESTS: test naming rule and guard tests

- Rank 102, tier P2; area tests; kind test.
- Action: Name test files by subject, never by batch or pass number; helpers in non-test modules; a guard test with the 21 batch-named files and 14 test-to-test imports as shrink-only allow-lists.
- Impact / effort / risk: L / S / None for the guard; a fold must keep collected test count per moved function.
- ToS check: No floor rule touched (test files only).
- Sources: 0047-R9
- Depends on: nothing
- Acceptance: Guard fails on a new test_audit_pass9.py and on a new `from test_x import`; both allow-lists shrink wave by wave.
- ZERO-CLICK: Developer-side only; player does nothing.
- Disposition: plan

### F-103 - FS-STATE-TEXT: move card and event text out of state.py

- Rank 103, tier P2; area structure; kind refactor.
- Action: Move state.py:80-851 (pure functions and tables) into a package server/al/text/ with state.py re-exporting every name; move the design gate, reviewer agent, lane prompts and design 0001 references in the same series, one commit each.
- Impact / effort / risk: M / M / A moved name read through the old module; importers only import/read attributes, none patches a state constant, so same-object re-exports keep working.
- ToS check: Wording floor rules (disclaimer, no GGG marks, not endorsed): every string moves byte for byte, disclaimer constant stays in server/al/__init__.py; static floor scan walks server/ recursively so new package covered.
- Sources: 0047-R3, P01-CODE-HEALTH-FOLLOWUP
- Depends on: F-017, F-102
- Acceptance: design_gate.py, loop_prompts.py and .claude/agents/ no longer name server/al/state.py; is_ui_path true for server/al/text/price.py, false for server/al/state.py; state.py holds no sentence literal; equivalence identical after every step (and the 14 text-pinning files, 229 tests); suites green; design-reviewer PASS recorded.
- ZERO-CLICK: Developer-side only; player does nothing.
- Disposition: plan
- Notes: Carries CODE-HEALTH-FOLLOWUP item 1; item 2 (web helper dedup) is in F-135, item 3 (CRLF writers) in F-014. Unblocks parallel copy packages. One step is session-only (.claude/ write).

### F-104 - Memoise the static floor scan; small timer fixes

- Rank 104, tier P2; area tests; kind test.
- Action: tests/test_floor_static.py caches per-file regex hits keyed by (path, size, mtime_ns); shorten the keepalive e2e constants and two 0.5 s polls; AL_FUZZ_S=0.1 in per-package checks only; drop the pid literal.
- Impact / effort / risk: M / S / A wrong cache key hides a planted call.
- ToS check: File is the floor's static guard; all 29 plants, 3 mutation tests and live-tree scan stay; nothing skipped.
- Sources: 0049-R2, 0049-R11
- Depends on: nothing
- Acceptance: Still 35 test ids; file under 4 s; deleting one BANNED pattern makes its plant test fail; a plant with same size and new mtime still caught.
- ZERO-CLICK: Runs in the suite.
- Disposition: plan
- Notes: All 29 plants and the mutation tests of the floor scan stay; CPU budget tests keep their 3 s windows.

### F-105 - CLIENT-GUARD and OBS-CRASH: the client survives its own errors without a dialog, and every exit leaves a record

- Rank 105, tier P2; area electron; kind fix.
- Action: app/main.js: uncaughtException and unhandledRejection handlers that log the stack and carry on (3 in 60 s: relaunch); render-process-gone, unresponsive and did-fail-load handlers rebuild the overlay at most 3 times in 10 minutes and reload the companion; the core writes ops/runtime/last-exit.json on every exit path; Checks reads both.
- Impact / effort / risk: H / M / A handler can hide a real bug; every event logged with stack, caps stop a loop.
- ToS check: Handlers run only on failure events in main process; page gets no timer; overlay rule kept.
- Sources: 0050-R2, 0051-R3
- Depends on: nothing
- Acceptance: Node tests: an error thrown in the main process logs its stack and opens no dialog; three errors in 60 s relaunch once; a killed overlay renderer is rebuilt at most 3 times in 10 minutes; last-exit.json is written on stop, reload, signal and crash; the overlay budget test stays green.
- ZERO-CLICK: Automatic; tray tooltip changes only after the cap.
- Disposition: plan
- Notes: No error box can take focus from the game. The core never restarts the client (decision 0041 point 2); the client relaunches itself.

### F-106 - OBS-SSE-EVENTS: stop sending chat-bearing frames by default

- Rank 106, tier P2; area observability; kind security.
- Action: Stop sending the 'events' SSE frame by default; keep it as a dev tap (/events?tap=1, source checkout only) with text fields removed; drop the unused recent_whispers field from the snapshot; move the 4 tests that read the frame to the tap.
- Impact / effort / risk: M / S / A hidden consumer; grep shows none in web/ or app/.
- ToS check: Reduces what is passed on; reads nothing new.
- Sources: 0051-R8
- Depends on: nothing
- Acceptance: Default stream holds 0 'events' frames over a fixture replay and state pushes still arrive within 250 ms.
- ZERO-CLICK: Nothing to do.
- Disposition: plan
- Notes: Also carries the cut of recent_whispers (0038 cut list: unused and carries chat text).

### F-107 - CALC-PRIORITY: heavy child processes below normal priority

- Rank 107, tier P2; area perf; kind feature.
- Action: Start luajit and every batch child AshLight runs (code preflight, drift trial, snapshot build) with the below-normal priority class; core and client stay at normal.
- Impact / effort / risk: M / S / A press takes longer on a saturated CPU; with R3 the first card does not depend on it.
- ToS check: 'Never touches the game process': only AshLight's own child processes get a creation flag.
- Sources: 0048-R2
- Depends on: nothing
- Acceptance: A test reads the priority class of the started luajit and the preflight child and expects below normal.
- ZERO-CLICK: Automatic.
- Disposition: plan

### F-108 - BUDGET-TESTS: enforce the measured budgets

- Rank 108, tier P2; area perf; kind test.
- Action: test_budgets.py runs the real loop body 10 s on the worst-case fixture and checks absolute working set in a child; new deterministic tests for tick cost, idle tick, start parse count and snapshot size; a CDP dashboard perf test; the calc ceilings of decision 0024 R7 at about 2.5 times today's values.
- Impact / effort / risk: H / M / Timing flakes; prefer deterministic checks, keep fleet_test_guard.budget on timed ones.
- ToS check: Tests only; live smoke shows AshLight's own window and stays opt-in.
- Sources: 0048-R6
- Depends on: F-084
- Acceptance: Each new test fails with its defect put back once and passes without it.
- ZERO-CLICK: The suite runs them.
- Disposition: plan
- Notes: Budgets B1-B19 of note 0048 are adopted as the numbers. The live smoke stays opt-in.

### F-109 - OBS-REPORT: the report built from structured fields

- Rank 109, tier P2; area observability; kind feature.
- Action: GET /api/report builds the report on click from an allow-list of structured fields (build, OS build, Python / Electron versions, Checks rows, counters, last exit and restarts, ledger shapes when on); read-only preview before copy; no log tails by default, an explicit second choice adds them through a hardened redactor.
- Impact / effort / risk: H / M / Copy must stay inside the click's activation; test in client window and a browser.
- ToS check: No upload (ruling J); clipboard written only on the player's click (0014); nothing new read.
- Sources: 0051-R6
- Depends on: F-027, F-032
- Acceptance: Fuzz test with L3 strings and 1,000 seeded variants finds no seeded secret in output; snapshot holds no report text and its version stays still over 3 idle minutes with web data on and last line 5 min old; preview equals copied text byte for byte.
- ZERO-CLICK: One click to copy (0014 requires it); preview costs no extra click.
- Disposition: plan
- Notes: No upload, ever; the clipboard is written only on the player's click. Carries AUDIT-P8-LOW P8-7 (redact must not blank fixed report words).

### F-110 - One hardening pass over the Electron shell

- Rank 110, tier P2; area electron; kind security.
- Action: New app/guards.js before any window: app.enableSandbox(); a web-contents-created default that denies navigation, popups and webview attach unless the creator registered a policy; webgl off; quit on an inspect switch, a remote-debugging port or NODE_OPTIONS without AL_DEV=1; run.ps1 drops ELECTRON_RUN_AS_NODE and NODE_OPTIONS from the client environment; one contract test with a single ban list.
- Impact / effort / risk: M / M / Companion's same-origin reload must stay allowed.
- ToS check: Overlay rule: no new process, timer or window, budgets hold; no input; launcher still starts only repo scripts.
- Sources: 0046-R5
- Depends on: nothing
- Acceptance: With fake webContents an unregistered one has navigation, popups and webview attach refused; both origin spellings granted and a foreign file URL ending /overlay/index.html gets empty reply; fake spawn receives absolute paths; live smoke still shows 2 processes under 215 MB.
- ZERO-CLICK: Nothing for the player.
- Disposition: plan

### F-111 - An egress lock on both Electron sessions

- Rank 111, tier P2; area electron; kind security.
- Action: webRequest.onBeforeRequest on the default session and the client partition cancels every request that is not an app file page, the loopback core on the configured port, or devtools with AL_DEV=1; the icon render page gets a no-network CSP.
- Impact / effort / risk: M / S / Blob and data URLs must pass; one callback per request.
- ToS check: Enforces 'trade site never called by the app' and web-data-off rule inside Electron.
- Sources: 0046-R6
- Depends on: F-110
- Acceptance: Unit test of the allow function over 20 URLs; opt-in smoke with an external image logs one cancelled request.
- ZERO-CLICK: Nothing for the player.
- Disposition: plan
- Notes: A second guard for two floor rules inside the client: the trade site is never called by the app, and nothing hits the network while web data is off.

### F-112 - Narrow external links and downloads

- Rank 112, tier P2; area electron; kind security.
- Action: Open a link only while the companion has focus, at most 1 per second and 5 per minute, https only, with the parsed href, hosts from one tracked list shared with web/tc.js; accept downloads only from the core origin with extension .build, .filter, .json or .txt; log each refusal.
- Impact / effort / risk: M / S / A new link host must join the list; a test enumerates what web/ emits.
- ToS check: Keeps decision 0017 (user opens trade URL in own browser); click stays the player's.
- Sources: 0046-R8
- Depends on: nothing
- Acceptance: routeFor denies without focus, on the sixth link in a minute and for http; a download named x.exe is cancelled.
- ZERO-CLICK: Link click is the player's own act; no new prompt.
- Disposition: plan

### F-113 - UTIL-ASC-FROM-TREE: ascendancy names from the cached tree

- Rank 113, tier P2; area theorycraft; kind fix.
- Action: Read the class to ascendancy map from the cached tree export first, keep the built-in table as fallback, add the 3 missing names now and the 1.0 names when GGG publishes them.
- Impact / effort / risk: M / S / Low.
- ToS check: Names from GGG's published export read from the local cache; nothing new bundled.
- Sources: 0037-R9
- Depends on: nothing
- Acceptance: With a synthetic tree naming a new ascendancy, class_fits knows its class with no code change.
- ZERO-CLICK: Follows the tree file.
- Disposition: plan
- Notes: 1.0 names (0038 F13) are re-checked against the patch notes at launch (F-052).

### F-114 - DIAG-DATA-AGE: say when the game data is older than the game

- Rank 114, tier P2; area observability; kind feature.
- Action: When the log names a campaign or map area id the cached world_areas file lacks, show a Checks row 'Game data is older than your game' with the fix step.
- Impact / effort / risk: M / S / A false row for an id the export never lists; limit to campaign and map ids.
- ToS check: Reads only the opt-in Client.txt and the local cache; no fetch.
- Sources: 0037-R10
- Depends on: nothing
- Acceptance: A replayed log with an unknown campaign id raises the row; a hideout id does not.
- ZERO-CLICK: Shown by itself; the refresh is one build step (Q2).
- Disposition: plan
- Notes: The fix step becomes 'nothing to do' once F-072 step 2 is ruled in.

### F-115 - Give the GGG docs watch a 'shape' topic

- Rank 115, tier P2; area automation; kind feature.
- Action: A topic keyed on the field names the reader uses, so a reference or changelog diff touching them is tagged and the note line names the fields.
- Impact / effort / risk: M / S / None; dev tool, read only.
- ToS check: Public web data: same six documentation pages at same cadence (decision 0044), allowed by robots.txt; not API endpoints, no API call.
- Sources: 0035-R3
- Depends on: nothing
- Acceptance: A synthetic reference diff that retypes explicitMods gets topic 'shape' and a note naming the field.
- ZERO-CLICK: Runs on the loop tick, also while HALTed.
- Disposition: plan

### F-116 - Build the offline core of a GGG client

- Rank 116, tier P2; area data-sources; kind feature.
- Action: In a module outside providers.py with an injected transport: the OAuth User-Agent form, PKCE and state, authorize URL, token exchange and refresh with the 7-day ceiling, the header-driven limiter, a one-shot 127.0.0.1 listener (state and path checked, closes after one request), tokens in the OS credential store; the bearer token never follows a redirect.
- Impact / effort / risk: M / M / Rests on details only GGG's reply settles (port matching, refresh on/off); a declined application wastes the day.
- ToS check: No request possible without a client id; later requests only to API Reference hosts, GGG UA form, headers obeyed dynamically, no POESESSID; listener binds 127.0.0.1 on a block port.
- Sources: 0035-R4
- Depends on: F-083
- Acceptance: D-AUTH's verifier/challenge example round-trips; a refresh never moves the stored ceiling; limiter honours synthetic headers and Retry-After; listener refuses wrong state, path or Host; no token in state snapshot, log, diag report or settings export.
- ZERO-CLICK: Not applicable until wired (R5).
- Disposition: plan
- Notes: No request is possible without a client id; details that depend on GGG's reply stay behind constants.

### F-117 - Recover a refused share link in one click

- Rank 117, tier P2; area theorycraft; kind feature.
- Action: On the web-data-off refusal the status line offers 'Turn on web data and load this link', which saves the opt-in and repeats the load.
- Impact / effort / risk: M / S / A privacy switch behind a button; the label must name it.
- ToS check: The click is the explicit opt-in of 0013; fetch stays one request to an allow-listed host with truthful UA; nothing without the click.
- Sources: 0042-R8
- Depends on: nothing
- Acceptance: Node test: refusal renders the button; a click posts the opt-in, then the same code once.
- ZERO-CLICK: One click replaces four acts.
- Disposition: plan
- Notes: The click is the explicit opt-in of decision 0013; web data is never turned on without it.

### F-118 - Overlay parts chooser, a sample card, and a quiet overlay

- Rank 118, tier P2; area overlay; kind feature.
- Action: Settings group 'Overlay shows' with switches per part and two presets (Full, Cards only), plus 'Show a sample card for 10 s'; the HUD card hides entirely when no part has content; 'hide in town and hideout' for the zone line; in_hideout is decided from the area id of the generation line, not an English scene-name substring.
- Impact / effort / risk: M / M / A hidden HUD hides 'AshLight offline'; a failure word must still show.
- ToS check: Overlay window unchanged (separate, click-through, non-focusable) and paints less; sample is own text, no screen read, no input.
- Sources: 0054-R2, 0056-R6
- Depends on: nothing
- Acceptance: With Cards only the overlay is empty until a card or failure word; Python and JS normalize() agree on new keys; sample shows 10 s and enters no history; budget tests green.
- ZERO-CLICK: Default stays Full; set-once choice saved on change.
- Disposition: plan

### F-119 - Overlay moment cards in the one card slot: zone card and act card

- Rank 119, tier P2; area overlay; kind feature.
- Action: The one card slot also shows a zone card for 12 s on first entry of a campaign zone with a goal and an act card for 12 s when an act split closes; slot order: open trade card, item / price / waystone card, zone or act card, first-run key hint, nothing.
- Impact / effort / risk: H / M / Card covers the corner map 12 s per new zone (design 0001 sec 10 placement); limit to first visit per game run, never over another card, on/off setting.
- ToS check: Opted-in Client.txt tail and AshLight's own guide file, drawn in the separate click-through window; no screen read, no input; overlay budgets (decision 0002) re-run.
- Sources: 0038-R2, P01-L18
- Depends on: F-088, F-095, F-118
- Acceptance: Replayed log entering a guided zone publishes a card of kind zone, 3 lines of at most 34 chars, for 12 s; trade request or item press takes the slot; re-entry shows nothing; data test proves every goal fits or clips; closed act with a saved best shows the gap; static budget tests green.
- ZERO-CLICK: Shows and leaves by itself.
- Disposition: plan
- Notes: Conflict resolved (empty slot, three competing HUD asks): one priority order, no second card and no third HUD line (0040-X5). Settles S5 (a), the UX-ZONE-NOTES overlay word and UTIL-OVERLAY-MAP. On by default with a switch in the parts chooser. Design 0001 section 10 amendment through the design reviewer.

### F-120 - One card per trade request: refresh, do not repeat

- Rank 120, tier P2; area play-tab; kind fix.
- Action: When an incoming trade whisper has the same sender and item text as an open card, update that card's time and price fields instead of appending; recent whispers still log every line.
- Impact / effort / risk: M / S / L: two genuine requests for identical items from one buyer merge; whisper log still shows both.
- ToS check: Client.txt reading only (decision 0003); no input.
- Sources: 0055-R3
- Depends on: nothing
- Acceptance: Three identical whispers from one sender and one from another: trade_requests has 2 rows, the first with the newest 'at'; 'Trade accepted.' still closes one card.
- ZERO-CLICK: Automatic.
- Disposition: plan

### F-121 - An in-browser accessibility pass in the CDP harness

- Rank 121, tier P2; area tests; kind test.
- Action: Extend app/test/cdp with an a11y job over one fixture state: AX tree (no unnamed focusable, no skipped heading level, landmark set), a real Tab walk on every tab with ring visibility per stop, forced-colours emulation, 320 CSS px reflow and the four text-spacing overrides, in dark and light with folds open.
- Impact / effort / risk: H / M / Low; headless Chrome already a test dependency; must skip cleanly where Chrome is absent.
- ToS check: Drives AshLight's own page in windowless Chrome with synthetic Tab keys to that page only; nothing reaches the game, no clipboard or screen read.
- Sources: 0044-R1, 0041-R9
- Depends on: F-034
- Acceptance: New pytest runs ~10 s, fails on a planted clipped ring, planted unnamed button and planted 3:1 pair; green on main after R2 and R3.
- ZERO-CLICK: A test; no player step.
- Disposition: plan
- Notes: Closes the research gap that the WCAG verdict rests on Play only. Drives AshLight's own page in a windowless browser.

### F-122 - One guide file, ready for 1.0

- Rank 122, tier P2; area play-tab; kind data.
- Action: Fold zone_notes.json and the boss table into zone_guide.json (goal, bonus, layout, next, boss element) and print one guide block; fill the 4 blank zones and verify the '+2 point books' wording; one level-gap rule (zoneguide.advice reads underlevel_gap). At launch: drop interlude acts once live ids confirm it and write Acts 5-6 entries within 48 hours.
- Impact / effort / risk: H / M / Thin sources in first two days; ship goals first, leave unsure facts out (decision 0043 rule). Merge is S; 24 zones of own-word notes is the rest.
- ToS check: Public pages read as facts and restated in own words (decisions 0009, 0043), plus build-time area snapshot under web-data opt-in.
- Sources: 0038-R5, P01-S5-FOLLOWUP, P01-L10
- Depends on: F-097
- Acceptance: One data file; every campaign area id in the cached snapshot has a goal or explicit skip; zone tile shows no separate 'Zone tip'; boss hint fires for every zone with a boss element; after launch G5 and G6 ids covered.
- ZERO-CLICK: Data only; file hot-reloads (decision 0042).
- Disposition: plan
- Notes: Split: S5 (a) is F-119, (b) is F-211, (d) (clear-or-push threshold) is tuned from two weeks of F-061 data, (e) is F-050. The launch part is gated by F-052. Facts restated in own words, unsure facts left out.

### F-123 - Upgrade search per slot from the build

- Rank 123, tier P2; area theorycraft; kind feature.
- Action: Put the trade-search link (same builder) on every 'Look for next' row so a search for any slot needs no item press first.
- Impact / effort / risk: M / S / The ?q= link form is undocumented (decision 0017 clause).
- ToS check: Pasted build and cached stat-id snapshot; decision 0017 (URL opened in player's browser; no trade endpoint call); ids per decision 0037.
- Sources: 0038-R7
- Depends on: nothing
- Acceptance: Each next-look row with terms carries a valid search URL (trade.is_search_link); no trade host in the fetch allow-list.
- ZERO-CLICK: Links rebuild with the build; opening one is the click.
- Disposition: plan
- Notes: The app only builds the URL; the player opens it (decision 0017).

### F-124 - Town moment: the vendor search string on Play

- Rank 124, tier P2; area play-tab; kind feature.
- Action: While the log places the player in a campaign town or the hideout and a build is loaded, the first line of the guide card shows the top search string by a plain name with a Copy button; the Build tab list stays.
- Impact / effort / risk: M / S / Play height; one row, hidden outside towns.
- ToS check: Clipboard written only on the player's click (decisions 0014, 0030); player pastes, no input.
- Sources: 0054-R4
- Depends on: F-025
- Acceptance: Replayed log entering a town shows the row and leaving hides it; no build, no row; Copy writes the exact string, within the game's 250-character limit.
- ZERO-CLICK: Shows and leaves with the zone; Copy is the one click the clipboard rule requires.
- Disposition: plan
- Notes: Clipboard written only on the player's click. Supersedes the search-string hotkey (0039-R13, not adopted).

### F-125 - WATCH-HEALTH: a broken watcher is itself a finding

- Rank 125, tier P2; area observability; kind feature.
- Action: Every source records last_ok; 3 failures in a row add one tick line; 7 days of failure file WATCH-BROKEN-<NAME>; a halted tick writes pending findings into its checklist; the dev-host Checks view notes a last tick older than 2 h.
- Impact / effort / risk: M / S / None.
- ToS check: Note reads AshLight's own status file, never a process list (0029).
- Sources: 0058-R10
- Depends on: F-030
- Acceptance: Source failing since 8 days yields one row, once.
- ZERO-CLICK: Unattended.
- Disposition: plan

### F-126 - A four-page player guide

- Rank 126, tier P2; area go-public; kind docs.
- Action: Download, Quick start, Common issues and FAQ pages built from the footer promise list and the Checks fix lines; the FAQ answers 'Is it allowed? Can I be banned?' first and honestly; README and About name the one download place.
- Impact / effort / risk: M / S / Wording that sounds like an endorsement.
- ToS check: Branding rules: every page carries the non-affiliation line, no GGG art, never says GGG approves or authorises AshLight.
- Sources: 0054-R7
- Depends on: F-020, F-050
- Acceptance: Four pages pass ASCII and leak tests, each has the disclaimer, one test finds the same download place in README, FAQ and About.
- ZERO-CLICK: Reading optional; nothing in play depends on it.
- Disposition: plan
- Notes: Every page carries the non-affiliation line; no GGG art.

### F-127 - SECOND-LINE: nothing stays down

- Rank 127, tier P2; area reliability; kind fix.
- Action: run.ps1 starts the supervisor before waiting for health and hands it the core pid (--adopt-pid, 60 s grace); the core starts a missing supervisor (at most once per 5 min, never against stop.request); the client checks /api/health every 30 s and after 4 failures runs run.ps1 once, at most once per 15 min.
- Impact / effort / risk: H / M / Restart loops; every layer keeps its cap and stop.request wins.
- ToS check: Only AshLight's own python processes, proven by pid and creation time (decision 0010); game never listed (0029); 0041 stands: supervisor never starts Electron.
- Sources: 0050-R3
- Depends on: nothing
- Acceptance: C16-C18.
- ZERO-CLICK: Automatic; 'Keepalive was not running; AshLight started it again.' on Checks card.
- Disposition: plan
- Notes: Recorded as a decision 0005 amendment at landing (adds neighbours, reverses nothing). No new watchdog process.

### F-128 - OVL-CHECK: the in-map overlay check as one normally played map

- Rank 128, tier P2; area overlay; kind test.
- Action: Developer-only tools/ovl_check.py armed by a session: starts 20 s into an open map, cycles the overlay through nine 30 s blocks (hidden, shown, updating) with own-window calls only, records AshLight's own processes and system-wide totals each second, and asks the operator once at the end whether the game's own FPS display stayed the same or dropped; JSON and a 15-line summary in <sidecar>\Logs.
- Impact / effort / risk: H / M / The HUD blinks for 4.5 min of one map; the result is a proxy, blind at a saturated GPU or an FPS cap; the display mode is not detected.
- ToS check: No input sent (own window calls only); no screen read; decision 0006 methods 1-3 only, no counter keyed to game pid, system-wide sampler never started by shipped app.
- Sources: 0048-R5, P01-OVL-FPS
- Depends on: F-032, F-062
- Acceptance: On a demo core with a synthetic map session the tool runs the nine blocks on a fake clock, writes the report and clears its flag; a test finds no measurement-only code under app/ or server/; the operator's same / dropped answer is recorded on the 'Tried in game' card.
- ZERO-CLICK: Play one map; one optional click at end.
- Disposition: needs-ruling: Q-18; then operator: play one map with the check armed
- Notes: Inside decision 0006 (methods 1-4): no present tracing, no game process or window check, no input, no screen capture. The phase switch is driven from tools/ through the overlay's existing own-window and layout calls, not by measurement code in the shipped product (decision 0006 item 4); if that cannot produce the 'updating' load, part (c) of the question decides.

### F-129 - OBS-EXPLAIN: five cause rows in Checks

- Rank 129, tier P2; area observability; kind feature.
- Action: Extend Checks with: overlay on screen (shown / hidden by you / hidden because the game looks closed / starting); item check key (last press, age, outcome); calc at run time; log lines understood (fail when 500 lines gave 0 events); restarts. One player-facing health surface, no second status page.
- Impact / effort / risk: H / M / A long Checks list; stays folded, opens on failure.
- ToS check: Overlay state from AshLight's own window object, never a screen read or a look at the game window; exclusive-fullscreen cause only a fixed hint.
- Sources: 0051-R5
- Depends on: F-026, F-032, F-105
- Acceptance: One test per new row and state; seeded overlay-state file drives each overlay sentence; design-reviewer pass.
- ZERO-CLICK: Computed every 5 s; opens by itself on a new failure.
- Disposition: plan
- Notes: Overlay state comes from AshLight's own window object, never a screen read or a window query. Restarts row shows to players only after 3 restarts in a day (design reviewer confirms).

### F-130 - ELECTRON-WATCH and a written upgrade policy

- Rank 130, tier P2; area electron; kind infra.
- Action: A decision: newest stable major; patch / minor weekly to the newest release at least 3 days old, within 24 h on an npm audit advisory; adopt major N+1 14-42 days after its .0.0, one at a time; never past EOL (a Checks note on the dev host). A watcher source reads the npm dist-tags and the Electron release schedule daily and files the bump row.
- Impact / effort / risk: H / M / Bad upstream release (waiting period, gates); feature switch renamed at a major (smoke process count catches it).
- ToS check: Two documented public npm/Electron endpoints, no GGG or trade endpoint, AshLight User-Agent, by the dev loop never the shipped app (decision 0013 untouched); smoke waits for log-staleness idle, no process check, no input.
- Sources: 0046-R1
- Depends on: F-030, F-037, F-044
- Acceptance: Fixture with line head 4 days old yields one bump item, 2 days none; schedule fixture inside the 30-day window yields the note; setup with a live client exits before npm runs.
- ZERO-CLICK: Unattended for operator; other users get one Checks note naming setup.ps1, computed offline from the EOL date in R4's config/electron_pin.json.
- Disposition: needs-ruling: Q-13
- Notes: The pin is 45.3.3 while 45.3.4 is out and the 45 line ends about 2027-04-27. The app itself never checks versions; the dev loop does.

### F-131 - One status vocabulary

- Rank 131, tier P2; area play-tab; kind refactor.
- Action: One table (state, dashboard words, overlay word of at most 15 chars, Checks detail, next step) in one module used by the pill, the overlay, Checks and the zone-tile sub line; 'fix' only for faults; while the log is missing tiles read '-' and the zone sub line carries the next step.
- Impact / effort / risk: M / M / Exact-output tests on both sides must move together.
- ToS check: Wording only; idle still from Client.txt staleness.
- Sources: 0042-R7
- Depends on: nothing
- Acceptance: One table-driven test feeds each state to all four surfaces and compares with the table.
- ZERO-CLICK: Status only.
- Disposition: plan

### F-132 - Calc opt-in in one act

- Rank 132, tier P2; area setup; kind feature.
- Action: Now: 'setup.ps1 -TcCalc' writes "tc_calc": true after a verified install, and the import and Checks texts name one step. Later: a 'Set up the Path of Building calc' button in the client runs the same script hidden and reports in Checks.
- Impact / effort / risk: M / M / A hash refusal must leave the flag untouched. Effort S then M.
- ToS check: Optional tools stay hash-pinned, unmodified, fetched only on the player's opt-in (decision 0018); the click is that opt-in.
- Sources: 0039-R5
- Depends on: nothing
- Acceptance: In a sandbox the switch leaves the flag set and the calc row passing with no edit; a forced mismatch leaves the flag as it was.
- ZERO-CLICK: One opt-in instead of two.
- Disposition: plan
- Notes: The button needs a second preload action: part of Q-08.

### F-133 - No dead ends: a copy pass over eleven sentences and four errors

- Rank 133, tier P2; area settings; kind fix.
- Action: Every sentence that sends the player away gets its control or names the exact place, never a script for a player task; the export file is called 'settings backup'; fix the six wording defects of 0042 F20.
- Impact / effort / risk: H / M / A file path in a main line bends design rule P2 for a while; the controls remove it. Effort S to M.
- ToS check: Wording only; no new read or request.
- Sources: 0042-R4
- Depends on: F-018, F-026, F-098, F-132
- Acceptance: A test greps player-facing strings for "settings file", "scripts" and ".ps1" and allows none outside a developer note.
- ZERO-CLICK: Fewer wrong acts; nothing added.
- Disposition: plan

### F-134 - WEIGHTS-DELTA: keep only the player's weight changes

- Rank 134, tier P2; area theorycraft; kind refactor.
- Action: Store weights.json as overrides over the defaults (only differing rows), merged at load; the panel marks changed rows with the default beside, per-row Reset, Reset All and an 'N changed' count; the existing full file migrates; settings export schema 2 carries the delta form and the sidegrade band.
- Impact / effort / risk: H / M / Migration may drop a deliberate value equal to old default; no behaviour change at migration time; keep a one-time backup under ops/runtime.
- ToS check: Local settings only; no game read, no web, no input (decision 0003 untouched).
- Sources: 0056-R1, 0039-R11
- Depends on: nothing
- Acceptance: Test changes one default in a patched module: untouched row picks it up, changed row keeps player value; reset row and reset all return to defaults; schema-1 full file migrates with no score change.
- ZERO-CLICK: Migration and merge run at load; reset buttons only for a player who tunes.
- Disposition: plan

### F-135 - FS-WEB-SHELL: shared format helpers, then a panel registry

- Rank 135, tier P2; area structure; kind refactor.
- Action: (a) one helper each side for dashboard source paths; (b) web/fmt.js with pad, duration and clock forms, aliased by the five files that copy them; (c) window.ALApp.register({name, order, paint, tick, wire}) so a new card edits no shared file.
- Impact / effort / risk: H / L / (a) S-M 27 test files; (b) S; (c) M-L about 950 lines in eight commits. Paint order and live-region announcements; keep order via explicit `order`; index.html still gains one tag per panel until R8.
- ToS check: Dashboard only shows core data; Copy-code clipboard write stays on player's click (0014) and moves verbatim; no clipboard read, timer or request added; CSP script-src 'self' and no CDN hold.
- Sources: 0047-R4
- Depends on: F-017, F-102
- Acceptance: pad, duration, clock each defined once under web/; web/app.js under 300 lines and names no feature module; npm test --prefix app and pytest files reading web/ green (plus new fmt test, registry test, test_dash_console, test_a11y, design-reviewer on diff).
- ZERO-CLICK: Developer-side only; player does nothing.
- Disposition: plan
- Notes: Parts (a) and (b) are small and go first; (c) is sequenced by plan 07 against the Play redesign so nothing is rewritten twice. The overlay's format.js stays apart.

### F-136 - SUPERVISOR-CLOCK: a liveness verdict that cannot misfire

- Rank 136, tier P2; area reliability; kind fix.
- Action: time.monotonic for every interval in keepalive.py; a stale kill needs 2 failed health checks 5 s apart; a poll gap opens a 60 s no-kill grace; /api/health gains loop_age_s (over 60 counts as failed); keepalive.json records the last restart and its reason.
- Impact / effort / risk: M / M / Worst-case hang recovery 97 s -> 102 s, inside 120 s budget at tests/test_keepalive.py:87, which must be extended by the second health check.
- ToS check: Only AshLight's own core probed (loopback, token) and terminated (python image, creation time).
- Sources: 0050-R5
- Depends on: nothing
- Acceptance: C19-C21; supervisor suites green.
- ZERO-CLICK: Automatic; 'AshLight restarted its core at 21:14 (it had stopped answering).'
- Disposition: plan

### F-137 - Clients verify the core before they send anything

- Rank 137, tier P2; area security; kind security.
- Action: Token-gated GET /api/hello: the client sends a fresh 128-bit nonce plus HMAC-SHA256(token, client, nonce); the core answers HMAC(server, nonce, bound port); Electron main, keepalive and run.ps1 check it once per token value and after any request error, before sending the token, posting item text or loading the page.
- Impact / effort / risk: M / M / Foreign listener learns one MAC over a nonce it cannot choose twice; port binding stops relay from a wrong port.
- ToS check: Clipboard still read once per manual press (decision 0003); only narrows where that text may go.
- Sources: 0045-R6
- Depends on: F-003, F-091
- Acceptance: A fake server answering 200 to everything receives neither token nor item text; a wrong-port config leaves the client on its starting page; --port 9000 exits non-zero.
- ZERO-CLICK: Code change.
- Disposition: plan
- Notes: Proves the listener with the token and looks at no process (clear of decision 0029).

### F-138 - Confine the calc child

- Rank 138, tier P2; area theorycraft; kind security.
- Action: Start luajit with a short environment; a job object (kill on close, one active process, memory limit above the 384 MB Lua heap ceiling); after PoB loads, bridge.lua drops os.execute, io.popen, os.remove, os.rename, package.loadlib and ffi if unused, and makes io.open read-only.
- Impact / effort / risk: M / M / PoB may need something (c) removes; live bridge tests decide. Job objects nest since Windows 8.
- ToS check: PoB stays an unmodified hash-pinned subprocess (decisions 0004, 0018, 0022); only AshLight's bridge files change.
- Sources: 0045-R9
- Depends on: nothing
- Acceptance: 17 reference outputs agree within 0.1 percent; a test command trying os.execute or write-mode io.open fails inside the bridge; child environment holds only allowed names; a second process started by the child is refused.
- ZERO-CLICK: Code change.
- Disposition: plan
- Notes: Whether PoB's headless path needs ffi or native modules is settled by the live bridge tests first. PoB itself stays unmodified.

### F-139 - Verify the calc component at use; pin contents, not bytes

- Rank 139, tier P2; area theorycraft; kind security.
- Action: tc_pins.json gains a content digest per component and a digest of PoB's runnable Lua files; the bridge compares the Lua digest before each start ('calc component changed, re-run setup' on mismatch); run_setup re-hashes the LuaJIT source before a build; an archive hash mismatch is accepted only when the content digest matches.
- Impact / effort / risk: M / M / Start time (0.07 s); (d) amends decision 0018 (its Reverses-if not met today).
- ToS check: No floor rule touched; component only gets pasted build text and hotkey-read item text.
- Sources: 0046-R7
- Depends on: nothing
- Acceptance: Editing one Lua file makes Bridge.from_component raise BridgeUnavailable; re-zipped archive with identical contents installs; a native require fails inside the bridge; 17 stored GUI outputs still match.
- ZERO-CLICK: Automatic; the one manual act stays the -TcCalc opt-in.
- Disposition: plan
- Notes: Prepares for generated archives losing byte stability (the Reverses-if of decision 0018); amendment lines to 0018 and 0022 at landing.

### F-140 - PRICE-SHAPE-WATCH: three layers of poe.ninja drift detection

- Rank 140, tier P2; area observability; kind feature.
- Action: Layer 1 in the core with no extra request: per route family record status, content type, ETag, key sets, kept / named counts and invariants; layer 2 as a watcher source: one GET a day of the poe.ninja docs page from the dev loop; layer 3: league identity checks on the cached list.
- Impact / effort / risk: M / M / Cosmetic docs-page edits make noise; tag changed lines by topic as the GGG docs watch does.
- ToS check: Public-web-data rule; docs page is public, 1 GET/day with truthful UA; in-core part adds no request.
- Sources: 0036-R6
- Depends on: F-030, F-085
- Acceptance: A fixture docs page gaining a PoE2 type writes a dated note naming it and raises a flag; a body with an extra unknown key raises nothing; a body missing a read key raises the flag.
- ZERO-CLICK: Automatic, in the loop tick and in the core.
- Disposition: plan
- Notes: Layer 2 runs on the dev loop, never in CI.

### F-141 - League picker, with the solo-league mapping

- Rank 141, tier P2; area prices; kind feature.
- Action: A league dropdown in the web-data card fed by the cached league list that writes the existing 'league' key; when the league is a solo league use the matching trade league for poe.ninja and the trade link and say 'prices from <league>' on the card.
- Impact / effort / risk: M / M / Low; the dropdown writes the existing league key.
- ToS check: The cached league list only (decision 0026); no request added; the trade link stays a URL the player opens.
- Sources: 0036-R8, 0056-R10
- Depends on: F-018, F-031
- Acceptance: The dropdown lists the cached leagues and writes the 'league' key; a solo league prices from its trade league and the card says so; no request is added.
- ZERO-CLICK: The league follows the auto league as today; the dropdown is an optional override.
- Disposition: plan
- Notes: Split: the auto-switch on two trade whispers (0036-R8) is deferred: it changes the league rule of decision 0026 and waits for evidence after 1.0. Solo league naming is read from the league list.

### F-142 - DATA-TREE-HOLD: keep the previous tree, resolve each build against the best match (before 2026-12-08)

- Rank 142, tier P2; area data-sources; kind feature.
- Action: Keep the previous tree file when a new one arrives and resolve each build against the cached tree with the highest id_match share.
- Impact / effort / risk: M / M / Low; two 5 MB files.
- ToS check: GGG's own Data Exports source, fetch-only, nothing bundled (decision 0009 item 3).
- Sources: 0037-R6
- Depends on: nothing
- Acceptance: With a foreign-version tree as the newest file, a build still gets names and .build ids from the older file.
- ZERO-CLICK: The choice is made per build with no setting.
- Disposition: plan
- Notes: No tree is cached on the dev host until the contact is set (operator act g in F-040).

### F-143 - TC-SNAP-PROBE and SNAP-DRIFT-REPORT: probe each fetched file before it replaces the cached one

- Rank 143, tier P2; area data-sources; kind fix.
- Action: Probe top-level type, minimum entry count and the fields each reader uses (for stat_translations the default-weight coverage); keep the old file on failure; write per source the record count and used-key set against the previous file to a Logs file; one Checks row per source; keep the current and one previous copy.
- Impact / effort / risk: M / M / A too-strict probe blocks a good file; keep to fields readers need.
- ToS check: None touched; local validation of public files already allowed by decision 0009.
- Sources: 0037-R8, 0056-R5
- Depends on: nothing
- Acceptance: A wrong-shape body leaves the cache untouched and the row names the source.
- ZERO-CLICK: At each build.
- Disposition: plan

### F-144 - Fix the contrast gate so it measures what the eye sees

- Rank 144, tier P2; area tests; kind test.
- Action: The overlay contrast test composites correctly (or uses opaque text after F-094); add a rendered-pixel check (glyph core against the far plate) to the overlay CDP smoke for the secondary role over white and a 2 px checker.
- Impact / effort / risk: M / M / Pixel thresholds depend on antialiasing; 5 percent tolerance, dpr 1.0 and 1.25. Effort stated S-M.
- ToS check: Test tooling only, synthetic backdrops, no game capture.
- Sources: 0041-R7
- Depends on: F-094
- Acceptance: New check fails on today's CSS (secondary core 4.56 < 5.5) and passes after R1.
- ZERO-CLICK: Runs in the suite.
- Disposition: plan
- Notes: Synthetic backdrops only; no capture of the real desktop or the game (strict reading; 0041-Q2 is settled this way).

### F-145 - Probe and restore zoom in the desktop client

- Rank 145, tier P2; area electron; kind fix.
- Action: In the Electron test path open the client window hidden, send Ctrl+= and a Ctrl+wheel event to its own webContents and read the zoom factor; if the key leaves 1.0, add a before-input-event handler for Ctrl plus / minus / 0 and persist the zoom.
- Impact / effort / risk: M / M / Low; menu stays hidden (autoHideMenuBar), no reload or devtools accelerator added (devTools stays gated). Effort S to M.
- ToS check: Synthetic key and wheel events only to AshLight's own hidden test window via its own webContents, never the OS input queue or the game; shipped fix only listens to keys pressed in AshLight's window; overlay keeps its fixed zoom, click-through, non-focusable.
- Sources: 0044-R4
- Depends on: nothing
- Acceptance: Electron test shows zoom 1.1 after one Ctrl+= and 2.0 reachable; factor survives a window restart.
- ZERO-CLICK: Zoom is the player's own key; nothing new to set up.
- Disposition: plan
- Notes: Synthetic events go only to AshLight's own hidden test window.

### F-146 - DOCS-FRESH: facts in docs are checked against the tree

- Rank 146, tier P2; area docs; kind test.
- Action: tools/docs_fresh.py: a table of facts computed from the tree and matched in named docs (Electron pin, version, Python / Node floors, port block, hotkeys, budgets, settings keys, kit version, every decision and research file indexed); 'check' runs as a test; CLAUDE.md names the file holding a pin instead of quoting the value.
- Impact / effort / risk: M / M / Brittle pattern blocks a merge; each fact has a fixture test.
- ToS check: None touched; keeps README required statement and descriptive wording under test.
- Sources: 0058-R6
- Depends on: F-023
- Acceptance: Changing the pin in app/package.json alone fails the test and names each stale file.
- ZERO-CLICK: Unattended.
- Disposition: plan
- Notes: The CLAUDE.md edit is session work.

### F-147 - SHOTS: screenshots from the demo core

- Rank 147, tier P2; area observability; kind feature.
- Action: tools/shots.py renders the dashboard states from a demo core in a headless browser for README, release notes and the design pack.
- Impact / effort / risk: M / M / Running timers make pixels differ; staleness judged on input hash.
- ToS check: Capture of AshLight's own page inside headless browser, never screen, game or game image; fixture invented names; floor scan gains protocol screenshot call as banned word with one allow entry.
- Sources: 0058-R8
- Depends on: F-034
- Acceptance: Demo start with missing fixture log exits non-zero, opens no file outside fixture folder (planted Steam root with decoy Client.txt); two renders same manifest; planted second capture call fails floor scan; no window appears.
- ZERO-CLICK: Unattended, hidden, below-normal priority.
- Disposition: plan
- Notes: Split: part (a) DEMO-MODE is F-034. Captures AshLight's own page only: never the screen, never game art.

### F-148 - Free release provenance, and a plain account of 'unsigned'

- Rank 148, tier P2; area go-public; kind infra.
- Action: At each tag CI writes SHA256SUMS and an SBOM and attests both; README gains 'verify your download' and 'Windows may warn' sections; after the first public release the operator may apply to a free open-source signing program.
- Impact / effort / risk: M / M / Attestation proves where built, not that it is safe.
- ToS check: No floor rule touched; no revenue; no game data in archive (decision 0009); README keeps non-affiliation line.
- Sources: 0046-R10, 0053-R9
- Depends on: F-076
- Acceptance: tools/sbom.py lists 13 npm components, 1 Electron binary and 3 calc pins each with a hash; release dry run on a fork verifies with gh; README section names each prompt.
- ZERO-CLICK: Runs on tag push; tester run is a one-time act.
- Disposition: needs-ruling: Q-22
- Notes: The pasted install line downloads without the mark of the web, so SmartScreen does not prompt; Smart App Control behaviour needs a Windows 11 tester. No signing paid from donations or ads tied to GGG-derived features.

### F-149 - TC-OAUTH-REG: send the application when registration reopens

- Rank 149, tier P2; area data-sources; kind operator.
- Action: The docs watch already raises ops/runtime/ggg_docs/REG_OPEN; the loop tick echoes it in its checklist; the operator then sends the prepared application.
- Impact / effort / risk: H / S / Low.
- ToS check: OAuth is GGG's documented path; never require or store a POESESSID.
- Sources: P01-TC-OAUTH-REG, P01-REG-OPEN-CHECK
- Depends on: F-083
- Acceptance: REG_OPEN shows as a checklist line of the loop tick; the session-start check line is retired once it does; the application is sent within one session of the flag.
- ZERO-CLICK: No reminder: the watch raises the flag; one operator act when it does.
- Disposition: blocked: GGG registration is closed (closed since 2026-07; reopening inferred for about 2027-01); when REG_OPEN appears the operator sends the application

### F-150 - CI-WATCH: upstream checks that need no dev host

- Rank 150, tier P2; area automation; kind infra.
- Action: A scheduled workflow runs 'upstream_watch.py ci' daily on a standard runner (contents read, issues write), compares upstream with the tracked pins, opens one labelled issue per finding (key line only) and closes it when gone; it never commits; the tick reads the labelled issues every 6 h.
- Impact / effort / risk: M / M / Scheduled runs late/dropped and stop after 60 days without activity; failover covers both.
- ToS check: Reads GitHub and public registries only, never a GGG host; UA names AshLight, version, repo address from runner. FLEET item 17: no bot commit, no bot PR.
- Sources: 0058-R7
- Depends on: F-021, F-030
- Acceptance: Recorded issue list with one valid key and one forged issue files exactly one row; workflow state disabled_inactivity switches tick to failover.
- ZERO-CLICK: Unattended; standard runners free on public repo.
- Disposition: blocked: the remote exists (F-021)
- Notes: CI reads GitHub metadata and public registries only: no poe.ninja, no GGG host, no download of repoe-fork or tree files (stricter reading of decision 0009).

## Tier P3 - worthwhile

### F-151 - Free a live-region slot; correct two texts; MERGE-SEAMS residue

- Rank 151, tier P3; area play-tab; kind fix.
- Action: Make #link a plain pill and lower the live-region cap test to 11 with one slot reserved; write the per-press announcement budget into design 0001 N6; correct the item-check empty text (dashboard card stays, overlay card leaves after 20 s); clear #restart-overlay-said on the next state push; rename hint-reset to tool-row.
- Impact / effort / risk: M / S / Low; tests/test_a11y.py:148.
- ToS check: Copy and markup only.
- Sources: 0044-R6, 0044-R8, P01-MERGE-SEAMS-FOLLOWUP
- Depends on: nothing
- Acceptance: Live-region cap test passes at 11; the exact-copy test holds the new empty text; #restart-overlay-said is empty after the next state push.
- ZERO-CLICK: Announcements stay automatic and polite.
- Disposition: plan
- Notes: Carries MERGE-SEAMS-FOLLOWUP F2, F5 and F7; F1 is F-025, F4 is F-096.

### F-152 - STOP-RACE: stop only what was running when stop was asked

- Rank 152, tier P3; area reliability; kind fix.
- Action: procs.stop terminates only overlay pids created before stop.request was written and ignores younger ones in its final check; guard the two unguarded int(pid) calls (procs.py:172, 178).
- Impact / effort / risk: M / S / Low.
- ToS check: Own processes only, proven by image path and creation time.
- Sources: 0050-R9
- Depends on: nothing
- Acceptance: C25.
- ZERO-CLICK: Automatic.
- Disposition: plan

### F-153 - OBS-OPLOG: one JSON line per own event

- Rank 153, tier P3; area observability; kind feature.
- Action: server/al/oplog.py writes typed events (start with build and pid, stop reason, reader start / reset / death, consent and web data switches, fetch result per host, calc start / time-out / exit, press outcome and ms, reload) to <sidecar>\Logs\events.jsonl, bounded; no log text, no item text.
- Impact / effort / risk: M / S / Growth; rotated with R7.
- ToS check: AshLight's own events only; no log text, by type.
- Sources: 0051-R9
- Depends on: F-090
- Acceptance: A free-text value passed to any kind is dropped and counted; a replayed session writes the expected kinds in order.
- ZERO-CLICK: Written by itself; read by probe and report.
- Disposition: plan

### F-154 - CALC-IDLE: luajit leaves when it is not needed

- Rank 154, tier P3; area theorycraft; kind feature.
- Action: Stop the calc process after 20 min without a press and when the game goes idle; restart on the next press or build load, hidden behind the first staged card; cache the luajit hash check.
- Impact / effort / risk: M / S / S for stop, S-M for collect. Slower first probe set after a stop; stop rule must not fire mid-press.
- ToS check: No floor rule touched; own optional child process getting only pasted build text and hotkey-read item text.
- Sources: 0048-R9
- Depends on: F-059
- Acceptance: B17; with a fake clock the provider stops the process after idle time and a later press answers.
- ZERO-CLICK: Automatic.
- Disposition: plan
- Notes: A full collect after every probe load is measured first; decision 0028 changes only if the measurement meets its reverse clause.

### F-155 - MATH-TRADESTAT-LOCAL: count the coverage before retiring the fallback

- Rank 155, tier P3; area data-sources; kind feature.
- Action: Keep the PoB TradeSiteStats fallback; add a coverage line counting the 39 default keys and their 8 '(Local)' twins per source; file an upstream-data note when repoe-fork starts to carry the twins.
- Impact / effort / risk: M / S / Low; a diagnostic only.
- ToS check: Local counts over cached public files; no trade endpoint call (decision 0017, trade2 floor rule).
- Sources: 0037-R4
- Depends on: nothing
- Acceptance: With the 2026-11-18 cache and pinned PoB file the line reads keys 39/39, local twins 0/8 repoe-fork and 8/8 merged.
- ZERO-CLICK: Computed at each index load, shown on the Checks page.
- Disposition: plan
- Notes: Retiring the fallback stays rejected for now (0037-X9): the current export has 0 of 8 Local twin ids.

### F-156 - PRICE-FALLBACK-RUNBOOK: the fallback order, written down

- Rank 156, tier P3; area prices; kind docs.
- Action: Write the fallback order (poe.ninja, a project mirror, a second community source, GGG Currency Exchange for stackables once an OAuth client exists, link only) with docs URL, date its terms were read and the field map per source; add no code and call no second source until decision 0026's Reverses-if fires.
- Impact / effort / risk: M / S / None now.
- ToS check: Public-web-data rule; nothing called; each future source needs its own check (documented API, truthful UA, no cookie).
- Sources: 0036-R11
- Depends on: nothing
- Acceptance: The note names the 4 fallbacks with their terms dates.
- ZERO-CLICK: Not applicable (session work).
- Disposition: plan

### F-157 - Trim the documented settings surface

- Rank 157, tier P3; area settings; kind docs.
- Action: Drop poll_ms, underlevel_gap, price_watch_pct and boots_speed_level from README and the example file (they keep working); replace the character key with a 'this is my character' pin in the picker; apply poll_ms and character without a restart.
- Impact / effort / risk: M / S / none
- ToS check: Settings and docs only; no data source or game contact.
- Sources: 0039-R7
- Depends on: F-020
- Acceptance: README names no setting without a control; an edit of the two keys takes effect within one tick.
- ZERO-CLICK: Fewer things asked.
- Disposition: plan

### F-158 - One filter control, stamped

- Rank 158, tier P3; area items; kind feature.
- Action: Merge becomes the one primary control and the plain download a small secondary link; the section header carries date and league; no further filter work before the in-game check.
- Impact / effort / risk: M / S / none new
- ToS check: Never modify any game file: still a download the player places (decisions 0031, 0033); cached prices only.
- Sources: 0039-R8
- Depends on: F-100
- Acceptance: One primary control; date and league in the merged section; byte-identity tests green.
- ZERO-CLICK: Content regenerates itself; the move stays the player's.
- Disposition: plan

### F-159 - Colour only for exceptions

- Rank 159, tier P3; area play-tab; kind design.
- Action: Running and done pills become neutral (glyph and word stay); blocked and failed keep colour; the bare button is quiet and .primary is used for the consent button only; one amber cue per item.
- Impact / effort / risk: M / S / A neutral "live" pill is less reassurance; glyph [+] and word remain.
- ToS check: Visible reading indicator: pill stays with glyph and words in the same place. Disclaimer sentence not touched (same place, same --fk-text).
- Sources: 0040-R4
- Depends on: F-131
- Acceptance: In PACK state f computed colour of #reading and #link is the muted token; footer first p still computes to --fk-text; exactly one element matches button.primary; pixel count of a Settings capture finds no filled accent block wider than 100 px.
- ZERO-CLICK: Nothing to press.
- Disposition: plan

### F-160 - Quiet control edges and an honest checkbox

- Rank 160, tier P3; area items; kind design.
- Action: Introduce --al-control-edge for input, select, textarea, secondary button and checkbox boundaries (back to the text colour under prefers-contrast: more); the unchecked checkbox is an empty box, the checked one filled with the accent.
- Impact / effort / risk: M / S / 3.61:1 is close to the 3:1 floor; the contrast test must own the number.
- ToS check: No floor rule touched (styling only).
- Sources: 0040-R5
- Depends on: nothing
- Acceptance: Four new rows in the DS 5.2 block (edge on page and card, light and dark, min 3.0) pass in tests/test_design_contrast.py; no rule outside the token block uses --fk-text-muted as a border.
- ZERO-CLICK: Nothing to press.
- Disposition: plan

### F-161 - Small type fixes: tabular numerals, stable tab widths, one stack

- Rank 161, tier P3; area play-tab; kind fix.
- Action: font-variant-numeric: tabular-nums on body and right-aligned price values; selected tab weight 600 with the bold width reserved; mono stack without the dead ui-monospace, one uppercase tracking value, line height 1.5 on multi-line prose.
- Impact / effort / risk: M / S / Tabular "1" looks a little loose at 600 in running text; prose is 400, already tabular.
- ToS check: Dashboard and overlay CSS only.
- Sources: 0041-R4, 0041-R5, 0041-R8
- Depends on: F-053
- Acceptance: CSS test asserts body declares tabular-nums; CDP probe measures advance of "1" and "8" inside .rate-value and .tab-mark equal within 0.05 px.
- ZERO-CLICK: Automatic.
- Disposition: plan

### F-162 - Overlay physical size: normalise autoScale to 1200 DIP

- Rank 162, tier P3; area overlay; kind design.
- Action: AUTO_REF_HEIGHT 1440 to 1200 (1440 DIP gets zoom 1.2, 2160 DIP 1.8, cap 2.0; 1080p unchanged).
- Impact / effort / risk: M / S / Larger window covers more of the game corner (click-through, transparent outside plates); user scale slider still multiplies, MAX_ZOOM 2.5 caps.
- ToS check: Overlay rule and FPS budget (decision 0002): window size only, same repaint gate; research 0048 owns the budget check.
- Sources: 0041-R6
- Depends on: F-094, F-108
- Acceptance: Updated test asserts by DIP height: 1080 -> 1, 1440 -> 1.2, 1728 -> 1.45, 2160 -> 1.8, 4320 -> 2; overlay budget test stays green.
- ZERO-CLICK: Follows the monitor; no click.
- Disposition: plan
- Notes: Measured against the overlay budgets after the size change.

### F-163 - On the overlay, a name beats 'Trade link ready'

- Rank 163, tier P3; area overlay; kind fix.
- Action: Line 2 of the item card shows the price only when there is a poe.ninja value; otherwise the item name stays.
- Impact / effort / risk: M / S / Drops 0017 item 2's overlay short notice when no value exists; needs a recorded amendment of 0017 item 2 (decision, alternatives, why); settled part of 0017 and 0016 merged-card rule untouched.
- ToS check: Cached poe.ninja value only; trade link stays a dashboard link the player opens.
- Sources: 0042-R11
- Depends on: nothing
- Acceptance: A link card without a value keeps line2 = name.
- ZERO-CLICK: Unchanged.
- Disposition: needs-ruling: Q-06
- Notes: Display text of decision 0017 item 2 only; the trade rule itself is untouched.

### F-164 - One accessibility CSS package

- Rank 164, tier P3; area play-tab; kind fix.
- Action: A forced-colours cue for the selected tab; a visible disabled state with the reason beside the button; 24 px checkboxes.
- Impact / effort / risk: M / S / Low; system colour keywords only (design 0001 C3 allows, as overlay.css does); forced colours keep author system colours (S9).
- ToS check: CSS only; touches no floor rule.
- Sources: 0044-R3, 0044-R7, 0044-R9
- Depends on: nothing
- Acceptance: Under forced-colors emulation the selected tab's bottom border colour differs from every other tab's (R1), dark and light.
- ZERO-CLICK: Follows the OS setting; no click.
- Disposition: plan

### F-165 - Lock the colour-never-alone rule with a test

- Rank 165, tier P3; area tests; kind test.
- Action: A static test that every CSS rule setting a status colour targets an element whose markup or JS also writes a word or glyph, with an explicit allow-list.
- Impact / effort / risk: M / S / False positives handled by the allow-list.
- ToS check: Test only; touches no floor rule.
- Sources: 0044-R10
- Depends on: nothing
- Acceptance: Planting .foo { color: var(--fk-status-ok) } on a wordless node fails the test.
- ZERO-CLICK: A test.
- Disposition: plan

### F-166 - Teach the item-check key in the empty card slot, then retire it

- Rank 166, tier P3; area overlay; kind feature.
- Action: While the card slot is empty and the item-check hotkey was never pressed on this install, the overlay shows one muted line with the real bound chord; it leaves for good after the first press or 3 game sessions.
- Impact / effort / risk: M / S / L: one more string in the slot; never competes with a trade or item card.
- ToS check: No input; hint only names a key the player presses; no clipboard read caused (decision 0003).
- Sources: 0055-R4
- Depends on: F-026, F-119
- Acceptance: Render-gate test: empty slot plus never-pressed shows hint; any card hides it; after a recorded press it never returns; hint uses the bound chord string.
- ZERO-CLICK: Appears and retires by itself; the press it teaches is the manual press the floor requires.
- Disposition: plan

### F-167 - Bring the companion back when the game wakes, only on another display

- Rank 167, tier P3; area electron; kind feature.
- Action: When the log goes from idle to a fresh line and the companion is in the tray or minimised, show it with showInactive only if its saved bounds lie wholly on a display other than the overlay's; a tray item turns this off.
- Impact / effort / risk: M / S / M: a window shown without focus can sit above other windows on that display; never touches the game display. Ship after R1.
- ToS check: No input, no focus steal, no process or window query of the game; trigger is Client.txt freshness only (decision 0029).
- Sources: 0055-R8
- Depends on: F-099
- Acceptance: Unit test of decision function: idle-to-fresh plus hidden plus bounds on display 2 with overlay on display 1 returns showInactive; same display returns stay; off switch returns stay.
- ZERO-CLICK: Automatic; one tray toggle to opt out.
- Disposition: plan
- Notes: Default ON with the tray toggle (0055-Q3); no focus is taken and the trigger is the log, never a window query.

### F-168 - Slow-test budget and hang guard in conftest

- Rank 168, tier P3; area tests; kind test.
- Action: Fail a test whose call exceeds its ceiling (unmarked 1.5 s, slow 15 s, scaled by load); on a full run fail the session past a suite ceiling (260 s, ratcheting down); faulthandler_timeout = 120.
- Impact / effort / risk: M / S / False reds under load (hence scaling); exit option needs pytest 9.0+ (README names no minimum).
- ToS check: No floor rule touched; complements the overlay budget rule in tests/test_budgets.py.
- Sources: 0049-R5
- Depends on: F-104
- Acceptance: Planted 2 s unmarked test fails with budget message; planted 130 s sleep ends the run near 120 s with a traceback.
- ZERO-CLICK: Enforced in every run.
- Disposition: plan

### F-169 - Housekeeping: stale decision entries and filed rows

- Rank 169, tier P3; area docs; kind docs.
- Action: One amendment line per stale 'Open (UNVERIFIED)' entry in decisions 0013 and 0015 (moot / resolved / still open for the link); reopen WT-SIDECAR as WT-SIDECAR-WIRE; remove the duplicate 'Pin log' section of decision 0004.
- Impact / effort / risk: M / S / none
- ToS check: No floor rule touched; docs only.
- Sources: P01-R8, P01-DOC-DECISION-TIDY, P01-L9
- Depends on: nothing
- Acceptance: Decisions 0013 and 0015 carry one dated amendment line per stale entry; ROADMAP has a WT-SIDECAR-WIRE row; decision 0004 has one 'Pin log' section.
- ZERO-CLICK: No operator act.
- Disposition: plan
- Notes: Split: the desktop-tool strike is F-007, the kit note F-203, the operator items F-040.

### F-170 - A launcher without VBScript

- Rank 170, tier P3; area setup; kind infra.
- Action: Replace scripts/autostart_launch.vbs with a pythonw entry point (Windows is retiring VBScript).
- Impact / effort / risk: M / S / Low.
- ToS check: Dev-tool reads of GitHub documented API with truthful UA; autostart stays opt-in (0011), no game contact.
- Sources: 0053-R10
- Depends on: nothing
- Acceptance: Fixture release newer than pin produces one loop line; registered task action runs no wscript.
- ZERO-CLICK: Watch runs on loop tick; pin move is a gated commit.
- Disposition: plan
- Notes: Split: the pin-watch half of 0053-R10 is carried by F-030 and F-130.

### F-171 - DIVE-ON-DEMAND: research dives when a source asks

- Rank 171, tier P3; area loop; kind feature.
- Action: A source may write ops/loop/control/dive_request.json (topic key, validated URLs); the tick dispatches the deep dive even when not idle, at most one a day; the daily idle dive becomes weekly.
- Impact / effort / risk: M / S / More dives after launch; one-a-day cap holds 2 runs a day.
- ToS check: Anonymous robots-respecting reads the dive prompt already orders; no forum URL added; whether research lane may read patch-notes forum is open (Q8).
- Sources: 0058-R11
- Depends on: F-030
- Acceptance: A request with open rows present still dispatches one dive.
- ZERO-CLICK: Unattended.
- Disposition: needs-ruling: Q-07
- Notes: The request file carries only GitHub, the poe.ninja docs page and the six GGG developer-docs pages; whether a dive may read the patch-notes forum is the ruling.

### F-172 - A read-only stream key

- Rank 172, tier P3; area security; kind security.
- Action: Derive a second credential from the token (HMAC over a fixed label), accept it on GET /events only and use it in both EventSource URLs, so the overlay page holds no token.
- Impact / effort / risk: M / M / Amends decision 0002 API token section (?token= on /events) and CLAUDE.md stack line 'every API / SSE call needs the per-start token'; needs that wording changed by operator or adjudicator first.
- ToS check: Floor untouched.
- Sources: 0045-R10
- Depends on: F-003
- Acceptance: Stream key opens /events and gets 401 on every /api route; ?token= on /events gets 401; overlay page config object has no token field.
- ZERO-CLICK: Code change.
- Disposition: needs-ruling: Q-11
- Notes: Changes the wording of decision 0002 and the CLAUDE.md token line; worth it mainly as the base of any phone view.

### F-173 - Ceilings on threads, deadlines and body sizes

- Rank 173, tier P3; area security; kind security.
- Action: Cap handler threads at 64; a total deadline per request for webfetch and snapshot; stream snapshot bodies to disk under a per-source cap; make snapshot's URL check equal to webfetch's.
- Impact / effort / risk: L / S / Low.
- ToS check: Floor untouched; opt-in, User-Agent and host lists unchanged.
- Sources: 0045-R11
- Depends on: nothing
- Acceptance: Connection 65 refused while 64 idle ones open and dashboard loads again once they time out; a fake transport sending one byte a second is dropped at the deadline.
- ZERO-CLICK: Code change.
- Disposition: plan

### F-174 - Move the two local pages off file://

- Rank 174, tier P3; area electron; kind security.
- Action: Serve the overlay and starting pages through one protocol.handle scheme (fixed file list, header CSP naming the exact core port); the core accepts that origin instead of null and file://.
- Impact / effort / risk: M / M / Transparent overlay must still paint (re-run UX-REAL-OVERLAY check).
- ToS check: Overlay stays a separate click-through window; decision 0002 budgets re-measured.
- Sources: 0046-R11
- Depends on: F-003, F-110
- Acceptance: Feed request carries the new scheme's origin; a request with Origin null gets 403; smoke budgets hold.
- ZERO-CLICK: Nothing for the player.
- Disposition: plan

### F-175 - FEED-TRUTH: the page says what really happened to the feed

- Rank 175, tier P3; area reliability; kind fix.
- Action: When the EventSource closes, web/app.js asks /api/health: a 401 shows 'AshLight restarted. Open it again from the tray.', else reconnect every 3 s; the SSE keep-alive becomes a named event so the overlay marks the feed stale after 45 s.
- Impact / effort / risk: L / S / Low.
- ToS check: Loopback API only; per-start token rule unchanged.
- Sources: 0050-R10
- Depends on: nothing
- Acceptance: A page test with a 401 after a live feed shows the line.
- ZERO-CLICK: Client window already reloads; browser tab cannot get the new token by design, one honest line is the minimum.
- Disposition: plan

### F-176 - OBS-DEV-LEDGERS: dev ledger hygiene

- Rank 176, tier P3; area automation; kind infra.
- Action: Add subagent_first to the rotation list; the probe flags a docs-watch last good read older than 3 days; move one-off suite logs to Logs\dev\.
- Impact / effort / risk: L / S / None; rows moved, never deleted (FLEET item 9).
- ToS check: Development files only.
- Sources: 0051-R10
- Depends on: F-032
- Acceptance: Seeded 40-day ledger keeps 30 days; a state.json with an old read prints a STALE line.
- ZERO-CLICK: The daily rotation pass does it.
- Disposition: plan

### F-177 - OVERLAY-FEED: a small feed for the overlay

- Rank 177, tier P3; area perf; kind feature.
- Action: /events?view=overlay sends only the fields the HUD reads and only when one changes; the server shares one serialised frame per view among its streams.
- Impact / effort / risk: M / M / A field the HUD needs left out; one list in one place with a test walking render_gate.js.
- ToS check: No floor rule touched; same token, same loopback feed.
- Sources: 0048-R8
- Depends on: F-093
- Acceptance: B7, B13; overlay tests pass on the small view.
- ZERO-CLICK: Automatic.
- Disposition: plan

### F-178 - Small perf trims: parse once, rest when unseen, idle backoff

- Rank 178, tier P3; area perf; kind fix.
- Action: The watched-file check hands its parsed document to the loader and base_items / world_areas are parsed once; the dashboard writes a clock only when its text changed, skips painters while hidden and stops the 1 Hz ticker while the game is idle; the supervisor imports the HTTP client only inside the probe and the core ticks once a second while idle.
- Impact / effort / risk: L / S / Decision 0042 last-good-copy rule must hold per table.
- ToS check: No floor rule touched; cached snapshot files, read only.
- Sources: 0048-R10, 0048-R11, 0048-R12
- Depends on: nothing
- Acceptance: B6.
- ZERO-CLICK: Automatic.
- Disposition: plan

### F-179 - TC-SNAP-TRIM: drop mods and stats from the snapshot until a reader exists

- Rank 179, tier P3; area data-sources; kind refactor.
- Action: Remove the two unread files (about 27 MB) from the snapshot fetch list.
- Impact / effort / risk: L / S / None; decision 0009 item 2 permits the files, does not require them.
- ToS check: Fewer requests to a community host.
- Sources: 0037-R11
- Depends on: nothing
- Acceptance: A fresh snapshot holds four files and the manifest lists four.
- ZERO-CLICK: Unchanged.
- Disposition: plan

### F-180 - TC-PIN-POLICY: write the pin policy into decision 0018

- Rank 180, tier P3; area setup; kind decision.
- Action: At most one PoB pin move per game patch cycle unless a release changes a reference output; LuaJIT moves only with a PoB move; the toolchain tree and archive are removed after a verified build; the update flow re-runs calc setup when the pin digest changed.
- Impact / effort / risk: L / S / A later rebuild fetches 276 MB again.
- ToS check: None touched.
- Sources: 0037-R12
- Depends on: F-064
- Acceptance: After a ready setup the toolchain folder is gone and a re-run is still a no-op.
- ZERO-CLICK: Setup cleans up by itself.
- Disposition: plan

### F-181 - PRICE-NINJA-LINK: a category link beside the trade link

- Rank 181, tier P3; area prices; kind feature.
- Action: Next to the trade link offer a link the player opens in their own browser to the poe.ninja category page of the checked item.
- Impact / effort / risk: L / S / Page URL form undocumented and uses a slug; link only to forms read from the public site.
- ToS check: Public-web-data rule; app requests nothing, the player's browser does (as decision 0017 for trade).
- Sources: 0036-R12
- Depends on: F-031
- Acceptance: The card carries an https poe.ninja URL for a unique and none for an unknown category.
- ZERO-CLICK: An optional click; nothing is needed.
- Disposition: plan

### F-182 - Loot tally from presses

- Rank 182, tier P3; area prices; kind feature.
- Action: Sum cached value times stack size of every priced press per map and per session, shown in the map block and the session card, labelled 'from the items you checked'.
- Impact / effort / risk: M / M / Partial by nature; stack-size text unverified (research 0003 line 51); repeat presses must not count twice.
- ToS check: Per-press item text and cached poe.ninja prices (web data on); no new read; decision 0036 holds (re-reads only cached book, only while web_data on, stored tally a bounded file under ops/runtime).
- Sources: 0038-R8
- Depends on: F-018, F-068, F-082
- Acceptance: 3 presses in one map, one repeated, count 2 items and their sum; web data off shows no tally.
- ZERO-CLICK: Counted on presses the player already makes.
- Disposition: plan

### F-183 - Affix line on the item card

- Rank 183, tier P3; area items; kind feature.
- Action: When the pressed text is the advanced copy, add one line with prefix and suffix counts and the best tier found.
- Impact / effort / risk: L / S / 'Open slots' needs per-rarity limits (small own table); print counts only until 1.0 confirms limits.
- ToS check: Text of the same press; nothing new read.
- Sources: 0038-R9
- Depends on: F-082
- Acceptance: Advanced fixture gives the line; plain copy gives none.
- ZERO-CLICK: Same press.
- Disposition: plan

### F-184 - A waystone card the player can tune

- Rank 184, tier P3; area items; kind feature.
- Action: List every risky mod above the reward line and give each rule a three-way switch (auto, always warn, never warn) saved in settings; thresholds become tunable constants with defaults and bounds.
- Impact / effort / risk: M / M / 'Never' hides a real danger; the card shows the count of silenced rules.
- ToS check: Same press and text (clipboard once per manual press); switches are local settings.
- Sources: 0054-R5
- Depends on: F-082
- Acceptance: Text with 5 risky mods lists 5; a rule set to never drops out and card says '1 rule silenced'; a rule set to always warns at capped resistance; overlay card keeps 3 lines of 34 characters.
- ZERO-CLICK: Defaults unchanged; tuning optional and saved on change.
- Disposition: plan

### F-185 - UNKNOWN-ITEM-TEXT: keep per-press 'Not counted' lines for a session

- Rank 185, tier P3; area observability; kind feature.
- Action: Collect the unweighted mod lines each press computes into an in-memory deduplicated session list (max 200); show the count on Checks and include the lines in the redacted report copied on a click.
- Impact / effort / risk: L / S / Memory growth (capped); list stays out of any file to keep decision 0045 'item text in memory only'.
- ToS check: No new read; reuses per-press clipboard text (0003); report leaves only on the player's click (0040).
- Sources: 0056-R3
- Depends on: F-109
- Acceptance: Pressing a fixture with one invented mod line twice yields one entry and Checks count 1; copied report contains the line and no path; restart clears it.
- ZERO-CLICK: Collected silently; report copy stays a click (decision 0040).
- Disposition: plan

### F-186 - PLAYER-NOTES: a player-written note per zone

- Rank 186, tier P3; area play-tab; kind feature.
- Action: A bounded file under ops/runtime (300 zones, 200 chars each) keyed by area id and character, edited on the dashboard zone guide, shown after the AshLight note as 'your note'; exported only when picked.
- Impact / effort / risk: M / M / Dashboard edit surface needs token and size checks (0045); plain text, no markup.
- ToS check: Player's own text, local file, Client.txt area id as key; nothing game-side.
- Sources: 0056-R8
- Depends on: F-088, F-092, F-122
- Acceptance: Note saved for an area id shows on next zone entry for that character only; malformed file keeps last good copy with a Checks note; file never exceeds its caps.
- ZERO-CLICK: Shown automatically on zone entry; writing is the player's choice.
- Disposition: plan
- Notes: A new bounded local store: its decision record rides the landing (pattern of decision 0036).

### F-187 - .build: fix the texts, name the upload route, plan the exit

- Rank 187, tier P3; area theorycraft; kind fix.
- Action: Correct the passives note; add GGG's second route (upload on the game's website) to the copy; the PoB release source raises a note when a release exports .build itself, and the download is then retired by an amendment of decision 0034.
- Impact / effort / risk: L / S / Players who paste a share link and have no PoB lose a route; guide sites cover them.
- ToS check: Download only (decision 0034); upload is the player's own browser act; no endpoint called; release check reuses decision 0025's one read-only releases read per 24 h.
- Sources: 0039-R9
- Depends on: nothing
- Acceptance: Note text test; a fake release body naming the export raises the note.
- ZERO-CLICK: The exit trigger needs no reminder.
- Disposition: plan

### F-188 - Small leftovers: one graphics sentence, the dead stub, two switches

- Rank 188, tier P3; area settings; kind fix.
- Action: Show 'play in Windowed Fullscreen' on the first-run card and as a Checks note; delete the 501 clipboard-read stub and its test line; remember the overlay shown / hidden choice in a runtime file; drop the no-op run.ps1 -Overlay.
- Impact / effort / risk: L / S / Tests that name the stub or the switch.
- ToS check: Advice only, no game file read or written; the one clipboard read stays the client's per-press one.
- Sources: 0039-R12
- Depends on: nothing
- Acceptance: Note shows in Checks; the route answers 404; a hidden overlay stays hidden after a client restart.
- ZERO-CLICK: The sentence shows itself; one toggle fewer per session.
- Disposition: plan
- Notes: The graphics advisor is removed only if 1.0 renames an option label (retire-on-trigger, with a decision 0014 amendment then).

### F-189 - One spacing scale, one badge, one row, held by a lint

- Rank 189, tier P3; area structure; kind refactor.
- Action: Declare --al-space-0..4 and three radius tokens and use only them; replace .pill, .verdict, .tab-mark and .tag by one .badge; one list-row rule with two densities; merge the three overlay plate blocks into one class.
- Impact / effort / risk: M / M / Many small visual diffs in one change; do it after R2 so it is not done twice.
- ToS check: No floor rule touched; overlay: no new repaint, no animation, plate CSS same after merge.
- Sources: 0040-R7
- Depends on: F-025, F-053
- Acceptance: New test passes; M1 re-run reports 100 percent spacing values in the set and 3 radii; PACK overlay window captures pixel-identical before and after.
- ZERO-CLICK: Nothing to press.
- Disposition: plan

### F-190 - The mark beside the name

- Rank 190, tier P3; area play-tab; kind design.
- Action: Show the existing small mark at 20 px left of 'AshLight' in the header, as an image from the dashboard's own files.
- Impact / effort / risk: L / S / None; dashboard CSP already allows its own images (server/al/http.py:39).
- ToS check: Branding rule: mark is AshLight's own flame and ash drawing (docs/design/0005-brand-mark.md), no GGG art, logo or name.
- Sources: 0040-R8
- Depends on: nothing
- Acceptance: Header holds one image with empty alt text and a 20 px box; CSP test stays green.
- ZERO-CLICK: Nothing to press.
- Disposition: plan

### F-191 - Undo for Clear run history

- Rank 191, tier P3; area reliability; kind feature.
- Action: The click hides the data and shows 'Cleared. Undo' in place for 10 s; files are rewritten only after that.
- Impact / effort / risk: L / S / A core exit inside the 10 s must leave the data intact.
- ToS check: Local files of decision 0036 only; no modal (design N2).
- Sources: 0042-R9
- Depends on: nothing
- Acceptance: Clear then undo inside 10 s leaves the file byte-identical; clear and wait empties it.
- ZERO-CLICK: Nothing in play.
- Disposition: plan

### F-192 - FS-STATE-SEAMS: publish() and per-concern parts of SessionState

- Rank 192, tier P3; area structure; kind refactor.
- Action: SessionState.publish(key, view) for views the core only stores; split the class by concern into mixin modules, each with its own init and view.
- Impact / effort / risk: M / M / (1) S about 40 lines; (2) M about 640 lines. Lock discipline and operation order; R3's tool proves equality; loop already uses mixins.
- ToS check: State built only from opted-in Client.txt tail and per-press item text; no new input, read or request.
- Sources: 0047-R5
- Depends on: F-103
- Acceptance: Equivalence identical after every commit; SessionState keeps its public methods; a test publishes a new key and reads it from snapshot() with no edit to state.py; listed state tests and whole suite green.
- ZERO-CLICK: Developer-side only; player does nothing.
- Disposition: plan

### F-193 - FS-CORE-SEAMS: tick list, route table, one import per line

- Rank 193, tier P3; area structure; kind refactor.
- Action: The core keeps a list of (name, callable) ticks; do_GET / do_POST / do_PUT dispatch through per-verb dicts after the guard; grouped imports become one name per line.
- Impact / effort / risk: M / M / Ticks S, imports S, routes M. Tick order and the guard: keep __main__.py order and call _guard before any lookup.
- ToS check: Client.txt-only-after-opt-in: consent gate in ensure_tailing unchanged; token, Host/Origin checks, CSP and 127.0.0.1 bind untouched.
- Sources: 0047-R7
- Depends on: F-103
- Acceptance: A test registers a tick and a GET route without editing __main__.py or do_GET; unknown path and missing token answer as before; listed http/core tests green.
- ZERO-CLICK: Developer-side only; player does nothing.
- Disposition: plan
- Notes: The route table is what F-010 pins.

### F-194 - FS-WEB-ASSEMBLE: generate the dashboard's script and style tags

- Rank 194, tier P3; area structure; kind refactor.
- Action: At serve time the core inserts one script tag per web/panels/*.js and one stylesheet link per web/panels/*.css at a marker in index.html.
- Impact / effort / risk: M / M / Tags M (about 60 lines plus tests); fragments L. The 13 test files reading index.html must read the assembled page via R4's helper; duplicate ids across fragments need a test.
- ToS check: No inline script, no remote origin; served only on 127.0.0.1 with same CSP.
- Sources: 0047-R8
- Depends on: F-135
- Acceptance: Adding web/panels/x.js makes GET / contain its tag with no index.html edit; served page has unique ids; CSP header unchanged; CDP console test and test_a11y on assembled page.
- ZERO-CLICK: Developer-side only; player does nothing.
- Disposition: plan
- Notes: The per-panel HTML fragment half waits for plan 03 (one block per card or not).

### F-195 - FS-DOCS: docs layout and structure guards

- Rank 195, tier P3; area structure; kind docs.
- Action: docs/plan/ holds the ultraplan and briefs/; design 0001 section 9 rule 2 splits into docs/design/copy/<family>.md; docs/decisions/README.md lists every decision; a structure test guards the layout.
- Impact / effort / risk: M / M / S-M. Reviewer must be told to read the copy sheets (design-reviewer.md:24).
- ToS check: No floor rule touched; (d) adds a check, never a read of game data.
- Sources: 0047-R10
- Depends on: F-017, F-103
- Acceptance: A planted cycle between two server modules and a new module with 5 sentences outside the gate both fail the test.
- ZERO-CLICK: Developer-side only; player does nothing.
- Disposition: plan

### F-196 - Split and stub the loop tests

- Rank 196, tier P3; area tests; kind test.
- Action: Split tests/test_al_loop.py (2783 lines, 53.8 s) into three files by theme; give the 77 tick tests that do not test git a stub git runner; build git_world from a session-scoped template copy.
- Impact / effort / risk: M / M / A stub hides a real-git regression (keep the 25 git_world tests on real git).
- ToS check: No floor rule touched (dev loop tooling only).
- Sources: 0049-R8
- Depends on: F-024
- Acceptance: Same test count; PROBE shows under 700 git spawns for the three files; each new file under 20 s.
- ZERO-CLICK: Test-only.
- Disposition: plan

### F-197 - AUDIT-P8-LOW residue: P8-6 and P8-8

- Rank 197, tier P3; area reliability; kind fix.
- Action: P8-6: the console / CSP test paints Checks rows, the hint and ladder_all; P8-8: the 'This session' ladder and the Maps card no longer mix characters after a switch; one test each.
- Impact / effort / risk: M / M / Low; design-reviewer PASS for UI.
- ToS check: No floor rule touched.
- Sources: P01-AUDIT-P8-LOW, P01-R7
- Depends on: nothing
- Acceptance: Each row's own ACCEPT line plus pytest / npm green.
- ZERO-CLICK: No player interaction.
- Disposition: plan
- Notes: Split: P8-3 and P8-4 are in F-091, P8-5 in F-084, P8-7 in F-109. P01-R7's other rows are carried by F-103, F-151 and F-122.

### F-198 - The final progress write names the outcome

- Rank 198, tier P3; area automation; kind infra.
- Action: Plan 08's agent contract: the last progress write of a task carries the outcome in its step text (not the last working step).
- Impact / effort / risk: L / S / Low.
- ToS check: No floor rule touched.
- Sources: P01-L12
- Depends on: nothing
- Acceptance: The orchestration outline states the rule; a finished task's progress file reads done with an outcome step.
- ZERO-CLICK: No operator act.
- Disposition: plan

### F-199 - Run the opt-in overlay smoke in one scheduled run

- Rank 199, tier P3; area tests; kind test.
- Action: The loop tick runs the live overlay smoke (AL_OVERLAY_SMOKE=1) at most once a day and only while the game is idle by the log-staleness state; the other skips are by design.
- Impact / effort / risk: L / S / Low.
- ToS check: The smoke shows AshLight's own overlay window; gated by game_idle from the log, never a process check; never inside waves while the operator plays (0049-X3).
- Sources: P01-L7
- Depends on: F-078
- Acceptance: A tick with game_idle true runs the smoke once and records its verdict; a tick with a fresh log line skips it.
- ZERO-CLICK: No operator act.
- Disposition: plan

### F-200 - GP-TIDY: three small public-surface cleanups

- Rank 200, tier P3; area go-public; kind refactor.
- Action: Replace the copied ORDER note fixture with a synthetic one; untrack the two channel .gitkeep files only if the kit tolerates a missing folder (read fleet_inbox first); the operator drops the stale tools/ash_lane.py permission from .claude/settings.json.
- Impact / effort / risk: L / S / L.
- ToS check: None touched.
- Sources: 0057-R12
- Depends on: nothing
- Acceptance: Inbox tests pass with synthetic fixture; git ls-files moon_sync_* empty if moved.
- ZERO-CLICK: Agent step.
- Disposition: operator: one settings edit (batched with F-057); the rest is plan work after the flip

### F-201 - PRICE-TYPE-PROOF: prove each price type after the first real round

- Rank 201, tier P3; area prices; kind data.
- Action: Move the two type lists into a hot-reloaded data file; after the first real round report per type the entry count and whether any press can match it; drop or fix what cannot (first candidate PrecursorTablets); put value.py's 11 currency ids under the shape watch.
- Impact / effort / risk: M / S / A fixture with real names would bundle third-party data; keep fixtures synthetic, record counts and key names only.
- ToS check: Public-web-data rule; same documented routes, fewer requests.
- Sources: 0036-R9
- Depends on: F-018
- Acceptance: Every requested type has entries and a matching path or is removed; every alias id exists in rates.json or is removed.
- ZERO-CLICK: Automatic; the report runs in the loop tick.
- Disposition: blocked: one real poe.ninja round on the dev host (contact set, web data on)

### F-202 - Official tree viewer link (version 7 URL)

- Rank 202, tier P3; area theorycraft; kind feature.
- Action: Encode the loaded build as a version 7 tree URL and show it as a link the player opens in their own browser.
- Impact / effort / risk: M / S / Class and ascendancy byte values undocumented; check against the tree export before shipping.
- ToS check: Documented format; app only builds a URL, player opens it (decision 0017 pattern); no request by the app.
- Sources: 0035-R7
- Depends on: nothing
- Acceptance: Decoding D-REF's PoE2 example gives version 7, class 10, 5 nodes, no bytes left; encode(decode(x)) equals x.
- ZERO-CLICK: The link is always ready; one click opens the browser.
- Disposition: blocked: a cached tree export on the dev host (operator act g: set the contact) for the fixture and the test

### F-203 - Report the kit gate defects to the fleet owner

- Rank 203, tier P3; area automation; kind operator.
- Action: Draft now one note: fleet_suite_gate.py:672 reads each ticket file twice (a ticket removed between reads raises AttributeError; a single read bound to a name fixes it) and the one-suite-per-tree leak through the lane slot, with line numbers and evidence; add the peer gaps found by note 0057 and the wish for a kit 3:1 edge token; send it once an outbound path exists.
- Impact / effort / risk: M / S / None.
- ToS check: No floor rule touched; note carries no path, id or email.
- Sources: 0049-R10, P01-FLEET-KIT-GATE-REPORT, P01-L17
- Depends on: nothing
- Acceptance: MAIN acknowledges; a later kit reads the ticket once at that line.
- ZERO-CLICK: Sent by the loop's inbox path, under the 12 per day cap.
- Disposition: blocked: no outbound note path (loop.dest_inboxes has no entry for the fleet owner); the note text is drafted now
- Notes: Kit files are never edited locally (FLEET item 11). The note carries no path, id or email.

### F-204 - One real screen-reader pass

- Rank 204, tier P3; area tests; kind test.
- Action: After the accessibility fixes land, an agent runs a screen reader over the dashboard on a fixture core and records what is heard for page load, an item check, a trade request, a tab switch and the Settings form.
- Impact / effort / risk: M / M / Needs a visible window and audio on the operator's machine, so must run when the operator is not playing.
- ToS check: Reads AshLight's own page with an OS reader; nothing touches the game.
- Sources: 0044-R12
- Depends on: F-096, F-121, F-151
- Acceptance: A dated transcript of what was heard per step, no unnamed or doubled announcements.
- ZERO-CLICK: A dev task; no player step.
- Disposition: blocked: a time the operator confirms they are not playing (speech output and a visible browser on this machine)

## Tier P4 - defer

### F-205 - Phone view / LAN

- Rank 205, tier P4; area security; kind decision.
- Action: No AshLight change by default: the phone as a wireless second display (design A) needs none; any data-sending design needs the read-only stream key, phone-only GET routes and a recorded lift of the bind rule.
- Impact / effort / risk: L / M / Low.
- ToS check: No floor rule; the CLAUDE.md bind rule (127.0.0.1 only, LAN access off) stands until the operator rules.
- Sources: P01-OP-PHONE-LAN
- Depends on: nothing
- Acceptance: The operator's pick is recorded in a decision; with P0 or design A nothing changes in the tree.
- ZERO-CLICK: One pick in the batched ask; default none.
- Disposition: needs-ruling: Q-11

### F-206 - TC-CURX: currency exchange history

- Rank 206, tier P4; area prices; kind feature.
- Action: After a yes from GGG or an own OAuth client: one request per completed hour while the app runs, immutable-hour cache, 8 MiB cap, names from the cached base_items snapshot; groundwork only against a hand-written fixture.
- Impact / effort / risk: L / S / Large hour files; history may be trimmed. Effort S to M.
- ToS check: Documented in the API Reference; no call until a registered client or written exemption exists (ruling in research 0018).
- Sources: 0035-R6, P01-TC-CURX
- Depends on: F-116
- Acceptance: Parser tests on a synthetic digest; an hour is never requested twice; no request at all while unregistered.
- ZERO-CLICK: Background fetch on the hour boundary under web_data.
- Disposition: defer: blocked on an AshLight OAuth client or GGG's written answer; cut if poe.ninja's exchange data stays sufficient

### F-207 - PRICE-VARIANT: a range when several variants match

- Rank 207, tier P4; area prices; kind feature.
- Action: Keep variant in the compact entry; when several variants match, show the low-high range and that it depends on the roll.
- Impact / effort / risk: L / S / Card density; it stays one line.
- ToS check: One read per press rule; same press, a cache lookup only.
- Sources: 0036-R10
- Depends on: F-201
- Acceptance: 3 variant lines give the range text; one variant is unchanged.
- ZERO-CLICK: Same press.
- Disposition: defer: needs a real item-overview body to confirm lines carry variant

### F-208 - Peek key for one-screen players

- Rank 208, tier P4; area electron; kind feature.
- Action: An optional third AshLight key shows the companion window at a compact size on the game's monitor and hides it on the next press.
- Impact / effort / risk: L / S / Focus leaves the game while the window is up (player's own press); the game may apply a background frame cap (UNVERIFIED for PoE2, Q3); a third global key.
- ToS check: Overlay stays click-through and non-focusable; companion is AshLight's own window (decision 0041); press reads and sends nothing; hiding acts on AshLight's window only, never queries or activates the game window (decision 0029 amendment).
- Sources: 0054-R8
- Depends on: F-026
- Acceptance: Node test: one press shows, next hides, held key does not repeat; handler makes no clipboard or screen call; unset by default.
- ZERO-CLICK: Off by default; one press when the player wants detail.
- Disposition: defer: needs a live focus test with the operator and an operator taste call; no demand evidence

### F-209 - PRICE-OVERRIDE: player price overrides

- Rank 209, tier P4; area prices; kind feature.
- Action: A small local name-to-value table that wins over the cached book on the price card, flagged 'your price'.
- Impact / effort / risk: L / S / Stale overrides mislead; show the override date.
- ToS check: Local only; poe.ninja reads unchanged; no trade call.
- Sources: 0056-R11
- Depends on: nothing
- Acceptance: Override replaces book value on the card and is marked; removing it restores the book value.
- ZERO-CLICK: Applies on presses the player already makes.
- Disposition: defer: no demand evidence; revisit with F-207

### F-210 - Scoop manifest by the release tool; winget later

- Rank 210, tier P4; area deploy; kind feature.
- Action: release.py writes a scoop bucket manifest; README shows two scoop commands; winget waits for a signed exe or installer.
- Impact / effort / risk: L / S / Low.
- ToS check: Manifest descriptive, no GGG mark, links disclaimer; free.
- Sources: 0053-R11
- Depends on: F-076
- Acceptance: Clean VM: scoop install from bucket starts client, scoop update keeps config/state, scoop uninstall removes shortcuts.
- ZERO-CLICK: scoop update is the user's one command; manifest refreshes each release.
- Disposition: defer: not checked against the per-user home layout; plan 05 revisits after the first public release

### F-211 - S5 (b): persist the BUILD-LIVE upgrade list

- Rank 211, tier P4; area theorycraft; kind decision.
- Action: Keep the checked-item upgrade list memory-only; if the operator rules otherwise, persist it through the durable store of F-014 in a bounded file.
- Impact / effort / risk: L / S / Low.
- ToS check: Item text stays in memory only (decision 0045).
- Sources: P01-L16
- Depends on: nothing
- Acceptance: No change unless ruled; if ruled, a restart keeps the list and Clear run history removes it.
- ZERO-CLICK: No operator act by default.
- Disposition: defer: decision 0045 keeps it memory-only and no Reverses-if is met; reopens only by Q-26

### F-212 - Spike: one press per item by a screen read

- Rank 212, tier P4; area items; kind decision.
- Action: Time-boxed test: one capture of the tooltip area on the AshLight press, read by an optional external OCR tool or the OS engine, compared against the clipboard text of the same 30 items.
- Impact / effort / risk: M / L / Misread numbers give wrong verdicts; new optional dependency (core stays stdlib-only, 0002); OS engine languages depend on device install (English recognizer presence UNVERIFIED).
- ToS check: One screen read per manual AshLight key press is what floor and GGG allow; no continuous capture, timer, or input; capture by AshLight's own window process, not a hook in game graphics.
- Sources: 0043-R7
- Depends on: F-054
- Acceptance: 30 of 30 items parse to the same stats as their clipboard text, or spike closed as rejected.
- ZERO-CLICK: 1 press, floor minimum for any item read.
- Disposition: defer: after the changed item key the saving is one key press per item; no wave before 1.0; a pick-one-of-N recommender (0056-Q2) waits with it

### F-213 - CLOCK-STEP: timers survive a clock change

- Rank 213, tier P4; area reliability; kind fix.
- Action: The core loop compares wall and monotonic deltas each pass; a difference over 5 s shifts the stored stamps by the step under the state lock.
- Impact / effort / risk: L / M / Many stamps; one SessionState method, property test.
- ToS check: No floor rule touched.
- Sources: 0050-R12
- Depends on: nothing
- Acceptance: Fixed-clock test: a +3600 s step leaves zone time, act splits and idle state unchanged.
- ZERO-CLICK: Automatic.
- Disposition: defer: low impact; last reliability wave

### F-214 - Shared server fixture

- Rank 214, tier P4; area tests; kind test.
- Action: One al_server factory in conftest replacing the serve_forever copies in 28 test files.
- Impact / effort / risk: L / M / A behaviour difference in one copy.
- ToS check: Binds 127.0.0.1 with the per-start token as today.
- Sources: 0049-R12
- Depends on: nothing
- Acceptance: Same test ids pass; serve_forever appears in at most 3 test files.
- ZERO-CLICK: Test-only.
- Disposition: defer: duplication only; fold in when a test file is touched

## Cut or merge

Every cut, merge, demote, promote, hide and retire-on-trigger candidate of the sources, with the finding it belongs to (none = recorded only, no work of its own).

- 0035 cut: account:profile in the scope request - Adds nothing; token answer names the account (F5). (F-083)
- 0035 merge: TC-OAUTH-REG and R2 - One row with one operator act. (F-083)
- 0035 merge: TC-CURX into the GGG client work (R4) - Late, low-value follow-on; cut it if poe.ninja's exchange data stays sufficient. (F-116)
- 0035 retire-on-trigger: BUILD-LIVE stale-build alert - Keep for paste users; mute it while a grant is live. (none)
- 0035 cut: Shrinking the docs watch to the changelog after registration (allowed by decision 0044) - Keep all six pages: shape and lifetime changes matter more once a client is live (the shrink is cut, not the pages). (none)
- 0036 merge: Currency into the price book (ninja.parse_overview and pricebook.parse_exchange_overview) - Same name resolution and gate; one parser and cache halves the code R4 and R5 must touch. (F-085)
- 0036 cut: PrecursorTablets type - Unless R9 finds a matching path (F9). (F-201)
- 0036 demote: Hourly cadence for the 22 non-currency types - To every 3 h when the repo goes public (R7); saves 352 of 552 daily requests. (F-046)
- 0036 cut: Dead price-card states searching, waiting, done, off and 'contact not set' words - Not produced since decision 0017 (status only link or error), yet the view maps them; for features review 0038. (F-018)
- 0036 demote: Movers - Keep (no request of its own) but word as a trend, not a fact: 20-listing floor rests on a sampled count (F8). (F-056)
- 0037 cut: mods and stats snapshot files - No reader (R11). (F-179)
- 0037 retire-on-trigger: PoB TradeSiteStats fallback and its pob2_files pin (NOT cut) - Stay until repoe-fork carries the Local twins (F11, R4). (F-155)
- 0037 cut: Toolchain tree after the one build it serves - About 1.2 GB used once (R12). (F-180)
- 0037 merge: PoB release check, docs watch and W2-W8 - One upstream watcher, one state file, one tick section (R5). (F-030)
- 0037 merge: Duplicate 'Pin log' sections of decision 0004 - Small defect (F17). (F-169)
- 0038 merge: M1 Zone tip into the zone guide - Part of R5; one file, one block (F7). (F-122)
- 0038 merge: M2 Boss table into the guide file - Part of R5; grow it from 2 zones to every act boss AshLight can state in own words (F7). (F-122)
- 0038 merge: M3 One level-gap rule: zoneguide.advice reads underlevel_gap; Level tile line goes, guide line and overlay word stay; RUSH_TEXT drops the XP claim - Two copies disagree when the setting changes; XP claim unbacked (F8). Test: gap setting 5 is silent at 4. (F-122)
- 0038 merge: M4 One notice slot on Play for build alert, upgrades and tip - Part of R6 (F3). (F-068)
- 0038 merge: M5 Price watch and movers in one card: 'your checked items that moved' first, then the market - Same cache, same tab (also 0039 R10). (F-056)
- 0038 cut: X1 recent_whispers from the snapshot (state.py:1832) - Unused, and carries chat text (F11). (F-106)
- 0038 cut: X2 POST /api/clipboard-read (http.py:311-317) and its test line - A stub with no caller (F11). (F-188)
- 0038 cut: X3 Movers line in the session card (summary.py:96-98) - Market movers appended to a play summary (F11). (F-056)
- 0038 retire-on-trigger: X4 D3 Price and points - Cut unless R4 shows a note price on a real copied item; trigger is a guess today (0038-Q2). (F-082)
- 0038 demote: Rename A9 'Death recap' to 'Deaths' - Promise no more than it shows if the game ships its own recap [EE] (rename). (F-067)
- 0038 demote: Freeze C1 trade whisper cards (no history, no reply helpers) - Freeze: keep, spend nothing (F6). (none)
- 0038 demote: Freeze G1 graphics advisor; one label re-check after 1.0 notes - Freeze: keep, spend nothing. (none)
- 0038 demote: Freeze A13 tips; re-check the two death-penalty tips at 1.0 - Freeze: keep, spend nothing. (none)
- 0038 demote: Freeze P3 price watch beyond M5 - Freeze: keep, spend nothing. (none)
- 0038 promote: B2 zone guide to the overlay - R2. (F-119)
- 0038 promote: A10 map runs to Play in maps - R6. (F-068)
- 0038 promote: D4 upgrade search link to the Build tab - R7. (F-123)
- 0038 promote: Act split results to the overlay - R2. (F-119)
- 0038 demote: A12 Last session to the Run tab - R6. (F-068)
- 0038 demote: E6 weights editor and the web-data switch to Settings, leaving Items and prices tab for prices only - Tab for prices only. (F-067)
- 0038 demote: Character picker to the Run tab - Per note 0039. (F-067)
- 0039 cut: Clipboard-read stub and the no-op run.ps1 -Overlay switch - Cut now (R12; F14). (F-188)
- 0039 cut: Four keys (poll_ms, underlevel_gap, price_watch_pct, boots_speed_level) from player docs - Cut now (R7). (F-157)
- 0039 retire-on-trigger: .build download - When the pinned PoB release exports it (R9). (F-187)
- 0039 retire-on-trigger: Graphics advisor - At the first option-label drift (R12). (F-188)
- 0039 retire-on-trigger: autostart.ps1 as a typed command - Once the checkbox exists; script stays as the mechanism (R4). (F-073)
- 0039 merge: Filter download into the merge control - R8. (F-158)
- 0039 merge: Price watch into price movers - R10. (F-056)
- 0039 merge: Contact and league into the web-data card - R2. (F-018)
- 0039 hide: Settings transfer and graphics stay folded; port, hot_reload and drift key stay out of player docs - Hide list. (none)
- 0039 demote: Automate away: snapshot fetch (R1 step 2, after a ruling), hotkey conflicts (R3), league (R2), calc flag (R5), logon start (R4), overlay choice (R12), non-Steam log discovery (R6) - Automate instead of asking (no enum value for automate). (F-072)
- 0039 demote: Keep as is: run history with ladder and visits, character keying, language notice, hot reload, copy helpers, Checks structure - Keep list (no change; recorded for completeness). (none)
- 0056 merge: Repo A schema-version gate and declarative export allow-list - Merged into 0037 R8 / R11; only drift counts new (R5). (F-186)
- 0056 merge: Repo D warn on missing or zero entries; prefer direct base-currency rate - Merged into 0036 R4; rate preference only if PoE2 overview carries both shapes (ninja.py:113 reads primaryValue only). (F-092)
- 0056 merge: Repo D tunable model constants with defaults and bounds - Merged into 0054 R5 (waystone thresholds, sidegrade band, price tiers). (F-143)
- 0056 merge: Repo F 'pattern not found means layout changed, degrade' for Client.txt parsers - Merged into 0050 R11 / 0051 R1. (F-209)
- 0056 cut: Repo D price cache warm start - Not needed; gate timestamps already persisted (ninja.py:162-168, 264). (none)
- 0056 cut: Repo F single in-flight guard for presses - Not needed; bridge lock serialises (bridge.py:125, 267); dropping a newer press would hide the item just copied. (none)
- 0056 demote: Repo B two-sided pacing word ('over-levelled, move on') - Deferred: adds a word most players do not need, risks noise vs 2-line HUD; revisit only if a player asks. (none)
- 0056 demote: Repo G time-budgeted background search publishing best-so-far - Deferred: useful only if 0048 shows PoB probes past budget (decision 0024 R7). (F-088)
- 0056 demote: Repo A worker-thread parsing in the dashboard - Deferred: no measured main-thread stall today (0048). (none)
- 0040 cut: Trades card outline, the 4 px radius, the .tag look, the start page's light palette - Via R4, R7, R6. (F-159)
- 0040 merge: Three overlay plate blocks into one class - R7; identical blocks. (F-189)
- 0040 merge: Short-window tier into the shell tier - If R2 lands (R6). (F-025)
- 0040 cut: --fk-surface and --fk-status-bad in overlay.css (used by no rule) - Remove only together with the matching DS 5.2 row that tests/test_design_contrast.py reads; otherwise leave them. (none)
- 0040 promote: --al-edge (equals muted grey) - Keep: exists so high-contrast mode does not whiten the card edge (overlay.css:18-20). (none)
- 0040 merge: The two header pills could become one - Wording side is 0042 R7. (F-189)
- 0040 merge: Empty item card repeats "Nothing checked yet." twice - One sentence is enough; wording is 0042's; visual gain one paragraph less. (F-133)
- 0041 merge: 13 / 13.6 / 14.4 px into meta 14 px; 13 px only for footer disclaimer - R3. (F-053)
- 0041 merge: Zone 24/28.16/36 into glance 28; level 32/33.28/44 into hero 40 (32 short windows); zone timer 20.8/25.6 into title 20 - R3. (F-053)
- 0041 cut: Overlay 15 px and 13 px steps - R2. (F-094)
- 0041 cut: Weight 700 from labels, kind tags and selected tab (700 only for glance and hero numbers) - R3, R5. (F-053)
- 0041 cut: Second letter-spacing value and dead ui-monospace - R8. (F-161)
- 0041 cut: Design 0001's unimplemented 7-token table and its 0.93 scale note - Replace with the R3 / R2 tables. (F-053)
- 0042 cut: build.ps1 and the three run.ps1 variants from the README quick start - R5. (F-020)
- 0042 cut: "character JSON" from the Build empty sentence (paste path stays) - R3. (F-041)
- 0042 cut: Price-card words for searching, waiting, listed, "Web data is off", "Contact not set" (state.py:554-562, 674-699; prices.js:202-209) - After a coverage check: price.py now publishes only a link or an error so they look unreachable; design 0001 section 9 still lists them. (F-018)
- 0042 merge: The "not an item" sentence shown twice - F20 d. (F-133)
- 0042 merge: The two under-level lines on Play - F22; 0043 picks. (F-025)
- 0042 merge: Five idle wordings and three log-missing wordings into one pair each - R7. (F-131)
- 0042 merge: Tips button into the Settings fold - R10. (F-067)
- 0043 merge: Items and prices tab - Into Build and items plus Settings (R6). (F-067)
- 0043 merge: Under-level line - Into the guide while a guide shows (R1); settles note 0042 F22. (F-025)
- 0043 cut: Pace line, when-line, calc line, trade expiry sentence, tip heading, Upgrade search / Price / Price and points headings and sentences - Cut from Play's first view (R1); all kept in Details or Run. (F-025)
- 0043 cut: Dead /api/clipboard-read stub (server/al/http.py:311-317) and its one consumer tests/test_http_security.py:152-154 - Returns 501 since the hotkey reads in the client (decision 0014 F1); one route less to explain. (F-188)
- 0044 merge: R2 and R6 - Into MERGE-SEAMS-FOLLOWUP (its F4 and F2) rather than new rows; that row already owns them. (F-096)
- 0044 merge: R7 and R9 with R3 - One CSS package: one small change to web/app.css plus its tests. (F-164)
- 0044 retire-on-trigger: axe-core as a dev-only checker - Deferred: adds an npm devDependency and a licence decision (MPL-2.0, not barred); R1 uses Chrome's own protocol; revisit only if R1 misses a class of defect in two reviews. (F-121)
- 0045 cut: Two unused null-origin paths (/api/state, /api/health) - No caller; done in R3. (F-003)
- 0045 cut: localhost in the Host and Origin lists - Every AshLight URL uses 127.0.0.1; or answer it with a redirect to 127.0.0.1. (F-003)
- 0045 cut: Authorization: Bearer header form - No caller in repo unless an operator script uses it (Q6); would amend decision 0002 API token section. (none)
- 0045 cut: 501 stub POST /api/clipboard-read - No caller; tests/test_floor_static.py source scan is the better pin; low priority. (F-188)
- 0045 merge: AUDIT-P8-LOW P8-3 and P8-4 - Into R6's package. (F-137)
- 0045 merge: token.reuse hardening - Into R4. (F-011)
- 0045 merge: All new security cases - Into R8's one test file. (F-010)
- 0046 cut: Lockfile-less install branch (setup.ps1:233-235) - Refuse instead (in R2). (F-037)
- 0046 cut: Plain-http external links - In R8. (F-112)
- 0046 merge: Two static Electron guards (tests/test_overlay_smoke.py:70-110, app/test/audit_electron.test.js) - One contract test with a single ban list (in R5). (F-110)
- 0046 merge: Python and JavaScript 'no bare program name' rules - Into one test (in R5). (F-110)
- 0046 merge: TC-DRIFT, GGG-DOCS-WATCH and ELECTRON-WATCH - One daily watcher frame (state file, 24 h gate, User-Agent); with research 0058. (F-030)
- 0050 merge: CODE-HEALTH-FOLLOWUP item 3 (CRLF) - Into R4: same lines of code. (F-014)
- 0050 merge: S5-FOLLOWUP item b (checked-item list lost on a restart) - Into R4: if persisted, uses the same store helper and backup. (F-014)
- 0050 merge: AUDIT-P8-LOW P8-3 and P8-4 (port checks) - Into R8 (note 0045 merges the same into its R6). (F-091)
- 0050 demote: Tray 'Restart overlay' - Keep as the manual fallback (0 uses so far). (none)
- 0050 cut: A new watchdog process - Add none: R3 gives each existing part a neighbour. (F-127)
- 0051 merge: R7 and R9 - Touch the same files: one work package. (F-090)
- 0051 merge: R3 reader restart and reliability note 0050 fix for the same root cause (logfile.py:245-251) - One change; note 0051 owns the Checks side only. (F-105)
- 0051 cut: events_seen in the snapshot, the report text, the 'events' SSE frame - events_seen once /api/debug exists (no page reads it); report text per R6; events frame per R8. (F-106)
- 0051 cut: A second status page - Keep one player-facing health surface: extend Checks (R5); /api/debug stays a dev surface. (F-129)
- 0051 merge: LIVE-1 single row for 11 remaining items (ROADMAP.md:13-18) - Split it so each item closes when the ledger shows its first live hit (inverse of merge: split). (F-061)
- 0047 cut: Regrouping server/al into more sub-packages - Graph has no cycle; about 200 test imports would change for no collision gain. (none)
- 0047 cut: Packaging tools/ or moving the loop files - Scheduled task, pre-commit, permission list and 34 tests name today's paths; tools/ had only 48 touches in 206 commits. (none)
- 0047 cut: Restructuring app/ or scripts/ - Low churn; 13 tests and floor allow-list name app/main.js; 10 tests name scripts/run.ps1. (none)
- 0047 cut: Converting web/ to ES modules now - Registry already removes the seam; conversion rewrites 21 scripts and 34 tests. (none)
- 0047 cut: Custom git merge driver for ROADMAP.md - Drivers live in .git/config, not tracked; every clone/worktree would need an install step. (none)
- 0047 merge: pad/duration/clock into web/fmt.js (R4); overlay format.js stays apart - Duplicated helpers; overlay is a file-system page with own budget (0002). (F-135)
- 0047 merge: docs/plans/ into docs/plan/briefs/ (R6) - Loop reads a non-existent docs/plans/ path. (F-029)
- 0047 merge: Identical setters into publish() (R5) - Four setters share one body. (F-192)
- 0047 merge: Done ROADMAP rows into the archive (R2) - 87 percent of ROADMAP is finished work. (F-028)
- 0047 merge: CODE-HEALTH-FOLLOWUP split into three rows: text split (R3, session), web helpers (R4 b), CRLF writers with corrected list (F13) - Split: the row bundles three independent pieces; its CRLF list is wrong. (F-103)
- 0048 merge: 0048-R4 and research 0051 R4 - One work package: counters from 0051, states/file/budget check from 0048. (F-032)
- 0048 merge: OVL-BUDGET into R4, OVL-FPS into R5; drop the hand measurement from the operator's list - Both close from the log / the one-map check. (F-032)
- 0048 merge: Audit P8-5 into R1; F8 into R9; F13 into deployment notes - Same work. (F-084)
- 0048 retire-on-trigger: test_tailer_idle_cpu_under_2_percent - Superseded by R6's loop test. (F-108)
- 0048 cut: Destroying the overlay window while the game is closed - 58 MB freed when RAM does not matter, for a new rebuild path. (none)
- 0048 cut: A Tauri or native overlay now - Decision 0002 reverses only on a missed budget; 169 MB is inside it. (none)
- 0049 merge: PowerShell 5.1 ParseFile check repeats at test_procs.py:81-84, test_autostart.py:134-136, test_run_detach.py:52-54 - test_supervisor.py:224-227 covers every script; -6 tests, -0.5 s, -6 PowerShell starts. (F-104)
- 0049 merge: Copied test helpers (gen 11 files, scene 9, _build 8, _core 7, srv 6, _wait 6, _isolated_git 5) into conftest or one helper module - Duplication left by the code-health audit; see R12. (F-214)
- 0049 demote: The 17 test_audit_* files - Do not merge for speed (4.9 s total, no duplicated coverage); re-homing is a structure question. (none)
- 0049 cut: 21 slow markers on tests under 1.5 s; the stale hand-off NOTE (AL-NEXT-SESSION.txt:91-93); gated npm test runs - Markers drift; NOTE stale since cbd54d6; npm test costs 0.45 s but waited 3,193 s in the gate. (F-104)
- 0052 cut: build.ps1 in README first-time path - F5: players should not run the test suite; cut at once. (F-019)
- 0052 cut: Three-way merge, pristine copy, patch export, typed-phrase reinstall, PATH entry, auto-update task, separate-repo export (M13, M17, M24, M26, M27, M29) - Do not port; N/A for AshLight. (none)
- 0052 merge: autostart.ps1 task code + setup.ps1 shortcut writer into one shell-integration module; tc_pin.py fetch/hash/extract helpers + installer's into one stdlib module - Installer and uninstaller both call them; 0011 stays off by default. (F-050)
- 0052 hide: \AshLightOps\LaneLoop out of every install - It is the dev loop's task, not the app's. (F-050)
- 0053 cut: build.ps1 from the stranger's quick start - F3; stays the dev gate and gains -Package (R4). (F-019)
- 0053 merge: Six Python lookups and three Electron paths into one helper and one resolver - F6, R3. (F-047)
- 0053 cut: npm from the end-user path - Pinned fetcher downloads same Electron zip; Node stays a dev dependency. (F-047)
- 0053 merge: First run into setup+run behind AshLight.cmd; drop a separate installer - Original: extract-and-run plus uninstall covers all. SUPERSEDED by Fit point 6: 0052 install.ps1 is the installer; re-run repairs. (F-050)
- 0057 merge: 0046 R9 (go-public wiring) into 0057 R3 + R8 - Same files; 0046 keeps lane tool, 0057 keeps order and settings. (F-079)
- 0057 merge: 0052 R7 one Windows CI workflow into 0057 R3 - One ci.yml, not two; release workflow (0053 R6) stays separate, later. (F-021)
- 0057 merge: 0051 issue template at go-public into R11 - Same deliverable. (F-075)
- 0058 merge: Watcher tools of N36 R6, N37 R5, N46 R1 into R2's frame - F13: one frame instead of three state files/hooks/failure modes; keep tc_drift.py for trial/apply, ggg_docs_watch.py for parsing. (F-146)
- 0058 merge: Policy wording watch (0029) into docs watch (R4) - Same pages. (F-051)
- 0058 cut: Hand-off file as a loop work source - R1 a: ROADMAP.md is the one ledger; hand-off stays session continuity. (F-024)
- 0058 demote: Daily idle dive - To weekly plus on demand (R11); sources report real changes. (F-171)
- 0058 cut: A Steam news reader - New host for a signal W4 and W5 already give. (none)
- 0058 retire-on-trigger: UTIL-1.0-POST split into three rows and a gate (R3) - Old row stays only as history; dotted id invisible to parser (F1). (F-052)
- 0054 merge: 0054 R3 into note 0039 R3 - Same key-handling area; merge when both run. (F-026)
- 0054 merge: 0054 R4 and note 0039 R13 - Share one search-string list. (F-124)
- 0054 merge: 0054 R1 hosts the contact field of notes 0038 R3 / 0039 R2 - One setup surface. (F-069)
- 0054 merge: 0054 R6 is the display half of note 0052 R6 - Update path designed in 0052. (F-055)
- 0054 cut: Growing the trade cards - Agrees with note 0038: every trade manager rests on reply buttons AshLight may never have (C1-C3). (none)
- 0054 cut: A second filter tool - Both editors sync to the account or save where AshLight will not write (H1, H2; note 0039 F15). (none)
- 0055 merge: 0055 R7 into 0038 R6 - Third state of 'Play follows the context'; not its own package. (F-068)
- 0055 merge: 0055 R4 with 0054 R2 (sample card) and 0042 R6 (chords in view) - One 'teach the overlay' package if plan 07 prefers fewer packages. (F-166)
- 0055 merge: 0055 R5 and R6 - Both design-rule plus test packages; one agent, one package. (F-095)
- 0055 cut: Overlay text shadow change (F9) - Redundant on a 92 percent plate but costs nothing and is cited by design 0001; not worth a package. (none)
- 0055 cut: Game Bar widget size change (GB-MODES 240-600 epx) - Confirms AshLight's 280 DIP base width (app/shared/layout.js:35); no change. (none)
- P01 merge: Draft's LOOP-ITEMS-TIDY into LOOP-PARSER-FIX - L4 fix rides R1 (c); not a row of its own. (F-024)
- P01 merge: TEST-LIVE-CLICKS into LIVE-1 ledger package - Closes on first passive read-back. (F-061)
- P01 merge: OVL-BUDGET into wave-1 observability package with the ledger (N51 R4) - Same package; row closes from the log. (F-032)
- P01 merge: TC-CURX groundwork with TC-IMPORT - Both wait on TC-OAUTH-REG. (F-206)
- P01 merge: CODE-HEALTH (1) into N47 file-structure package - Module layout decided once. (F-103)
- P01 merge: MERGE-SEAMS into plan 03 and with N44 accessibility (F2, F4) - One wave for Play-tab design. (F-151)
- P01 merge: S5-FOLLOWUP split: (a) into plan 03 with L18, (b) code row after ruling, (c)+(f) one data row, (d) loop row after ledger, (e) into plan 05 - Each part has a different unblock. (F-122)
- P01 retire-on-trigger: REG-OPEN start check into TC-OAUTH-REG - Keep session-start line until the loop tick surfaces REG_OPEN. (F-149)
- P01 cut: OP-ACTS (b) LIVE-1 play session and login - Replaced by normal play once the ledger lands; drop from the ask. (F-040)
- P01 cut: OP-ACTS (a) RAM part - Closes by BUDGET-LOG with no act; FPS part stays. (F-040)
- P01 cut: NOTE session-5 reap - Obsolete; drop at the next /done. (none)
- P01 merge: NOTE live lane trips fleet_test_guard into LOOP-PARSER-FIX or N49 - Keep the note until fixed. (F-024)
- P01 merge: UTIL-1.0-POST rename and split (UTIL-10-... gate plus three rows) - Loop cannot see the dotted id (L1); N58 R3 LAUNCH-GATE. (F-052)
- P01 merge: L10 zone notes into S5 (f) data row and parse ledger - No own live check row. (F-122)
- P01 merge: S5 (a), UX-ZONE-NOTES overlay word, UTIL-OVERLAY-MAP (L18) - One decision in plan 03 settles all three. (F-119)

## Conflicts

1. Reading Path of Building's own files: 0043 recommends following the builds folder behind an opt-in; 0042 rejects it as outside the floor's read list; 0054 and 0035 ask.
   - Ids: 0043-R3, 0042-X4, 0054-Q2, 0035-Q5
   - Resolution: needs-ruling: Q-01. Until ruled the strict reading applies (outside); F-042 and F-058 carry the build pain.
2. Parse ledger consent: plan 01 says the ledger closes LIVE-1 with zero operator acts; 0051 asks whether the existing Client.txt consent covers a persisted ledger.
   - Ids: 0051-R1, P01-R3, 0051-Q1
   - Resolution: Stricter reading: both persisted ledger parts wait for a new consent line; in-memory counters need none; revoking consent deletes the file. One tick by the operator (F-061).
3. Install shape: one pasted install line into a per-user home with app\<version>\ folders, a marker swap and an Apps & features entry (0052) against a portable extract-and-run zip with state inside the folder (0053 original).
   - Ids: 0052-R1, 0052-R4, 0052-R5, 0052-R6, 0053-R1, 0053-R3, 0053-R5
   - Resolution: The 0053 'Fit with 0052 and brief F' section adopts the 0052 design: home %LOCALAPPDATA%\Programs\AshLight with state in data\, version folders plus marker, runtimes one folder per pin, one per-user uninstall key, the pasted line as primary route (F-049, F-050, F-063).
4. Update consent and mechanism: automatic at the next start with a marker switch (0052) against one click per update, never silent, with an in-place swap (0053 original).
   - Ids: 0052-R6, 0053-R8, 0053-X1
   - Resolution: Mechanism: marker switch between version folders. Consent: needs-ruling: Q-21; recommended automatic staged apply with a 24 h hold and a click-only switch.
5. Who cuts a release and who writes the changelog: local stage then publish from the dev host (0052); tag-triggered CI builds, attests and publishes with tools/changelog.py (0053); release.py notes from merge subjects curated by a lane (0058).
   - Ids: 0052-R7, 0053-R6, 0058-R9
   - Resolution: Local 'release.py stage' is the gate; pushing the v* tag after PASS lets CI rebuild, compare, attest and publish (F-074, F-076). One changelog generator: 'release.py notes' with the commit-type grouping; tools/changelog.py is not built (F-101).
6. In-app version check: 0046 rejects any updater or version check by the running app; 0053 and 0052 recommend a daily releases check by the core inside the web-data opt-in.
   - Ids: 0046-X3, 0046-R1, 0053-R7, 0052-R6
   - Resolution: Allowed only inside the web-data opt-in and with the decision 0018 item 6 wording ruled (Q-21); what stays rejected is a check outside the opt-in or by default. Electron and pin watching stays on the dev loop (F-130).
7. Electron fuses: 0046 leaves flipping runAsNode / nodeOptions / nodeCliInspect and asar integrity to the packaging note; 0053 ships the unmodified prebuilt exe and never mentions fuses.
   - Ids: 0046-X1, 0053-R3
   - Resolution: No fuse flip while the shipped exe is the unmodified hash-pinned upstream binary (a flip changes the pinned hash and every install would undo it). The launcher drops the two environment variables and guards.js quits on inspect switches (F-110); fuses are revisited with a signed packaged exe (decision 0041 item 9). Plan 05 records this as rejected for now.
8. Operator act for the remote: 0057 found gh authenticated and wrote 'no operator act'; the other files and CLAUDE.md treat creating the remote as an operator act.
   - Ids: 0057-R7, P01-OPERATOR-REMOTE, 0052-R7, 0053-R6, 0058-R7, 0046-R9
   - Resolution: No sign-in or credential act is needed, but creating the remote and the visibility flip each wait for the operator's recorded go (Q-23); the hook and rule rewrite merges only after it (F-016).
9. CI reading poe.ninja: 0057 rejects any CI job calling poe.ninja or GGG docs; 0058 homes the poe.ninja docs-page watcher (W6) in CI; 0036 runs it from the loop tick on the dev host.
   - Ids: 0057-X5, 0058-R7, 0036-R6
   - Resolution: Stricter reading: no CI job calls poe.ninja or a GGG host, and CI downloads no repoe-fork or tree files; W6 runs on the dev loop (F-030, F-140, F-150).
10. Loop parser fix before HALT: widen the row id grammar and skip hand-off bullets that name an open row (0047) against rename the dotted ids, lint against dots and accept a hand-off bullet only with a LOOP: prefix (0058, plan 01).
   - Ids: 0047-R2, 0058-R1, P01-R1
   - Resolution: Rename plus lint plus the LOOP: prefix (F-024): the grammar stays simple and the hand-off is loop work only by explicit opt-in. 0047-R2 keeps the prune and the shape test (F-028).
11. How ROADMAP rows are added and linked: one file per new row and done marker with a loader, dependencies in briefs (0047); watchers append rows to ROADMAP.md and flip gates in a tick commit, dependencies as DEPENDS: (0058); 0036 says unattended commits stay off.
   - Ids: 0047-R6, 0058-R2, 0058-R12, 0036-R6
   - Resolution: File-per-row is the mechanism behind the watcher's two primitives, so an unattended commit only adds a file; DEPENDS: in the row is the one machine-read form and long text lives in docs/plan/briefs/ (F-029). The commit path itself: needs-ruling: Q-12.
12. When HALT comes off: after the parser fix lands (plan 01) against only after six listed checks (0058).
   - Ids: P01-R9, 0058-R5
   - Resolution: The six checks (F-078); they include the parser fix.
13. Minimum text size: labels 14 px and overlay 16 / 14 px by x-height at 65 / 90 cm (0041) against Play labels at least 19.2 px and overlay status 15 px by cap height at 80 / 60 cm (0055); 0043 budget B7 allows 13 px on Play.
   - Ids: 0041-R2, 0041-R3, 0055-R2, 0043-R1
   - Resolution: The 0041 six-step scale is the token set; Play text read in play uses its 20 px step, which meets the 0055 floor; the overlay status word sits at HUD size (16 px). Both cases fit without scroll (0043 fit table, at least 48 px spare). B7 becomes 'no Play text under 14 px, in-play text 20 px' (F-053, F-094).
14. Overlay legibility recipe: no overlay token changes (0040); plate alpha down to 0.86 with opaque text, new secondary and warn colours and a halo (0041); plate up to 0.96 or a lighter muted token (0044).
   - Ids: 0040-R7, 0041-R1, 0044-R11
   - Resolution: The 0041 recipe (the note that owns typography): opaque text removes the blend that the other two work around; 0044-R11 is merged into it (F-094); the gate is fixed to measure rendered pixels (F-144).
15. Play layout numbers: one glance band of five cells up to 120 px tested at 1264x821 (0040) against a strip of four tiles with the guide as a card tested at 1280x760 and 1920x950 (0043).
   - Ids: 0040-R2, 0043-R1
   - Resolution: 0043 owns the layout and the tests (all three sizes); 0040 owns the look; the measured strip (88-108 px) is inside 0040's 120 px band (F-025, F-066).
16. Tab set: four tabs with Build and items merged (0043); an Items and prices tab kept for prices only, five tabs (0038 cut-or-merge); Settings as the index (0042).
   - Ids: 0043-R6, 0042-R10, 0038-R6
   - Resolution: Four tabs: Play, Build and items, Run, Settings. Settings owns the switches it holds (web data, hotkeys, overlay parts, theme) and indexes the ones that stay elsewhere (F-067).
17. Where first-run setup lives: a setup card on Play (0054) against setup controls on Settings (0042, 0039); 0043 caps Play at 8 controls.
   - Ids: 0054-R1, 0042-R10, 0039-R2, 0043-R1
   - Resolution: The setup card replaces the consent card on Play only until consent is given, then folds to one line in the notice slot that jumps to the controls on Settings (F-069).
18. Closing LIVE-1: one scripted 30-minute operator capture session (0038) against a passive parse ledger with zero operator acts (0051, plan 01).
   - Ids: 0038-R4, 0051-R1, P01-R3
   - Resolution: Log shapes close passively through the ledger (F-061); 0038-R4 narrows to item-press samples during normal play (F-082).
19. A 'third global hotkey' is claimed four times: wear key (0038), search-string key (0039), peek key (0054), and a changed default item key (0043).
   - Ids: 0038-R1, 0039-R13, 0054-R8, 0043-R5
   - Resolution: Hotkey budget: at most two global keys registered by default (item check, show / hide). The wear action is a card button with an optional unset key (F-070); the search-string key is not adopted (town row instead, F-124); the peek key is deferred (F-208); the item key changes only after the operator's two checks (F-054).
20. The overlay's one card slot: a hotkey hint when empty (0055), nothing when no part has content (0056), zone and act cards (0038), a sample card (0054); plan 01 lists three more asks for the capped HUD.
   - Ids: 0055-R4, 0056-R6, 0038-R2, 0054-R2, P01-L18
   - Resolution: One slot, one order: open trade card, item / price / waystone card, zone or act card, first-run key hint, nothing (the HUD card hides). The sample card shows only on the Settings button. No second card, no third HUD line (F-119, F-118, F-166).
21. core.log rotation: RotatingFileHandler, 2 MB, 2 backups (0050) against rotate at start over 1 MB, one kept, 2 MB in-run backstop (0051).
   - Ids: 0050-R6, 0051-R7
   - Resolution: The 0051 scheme (0050 itself says 0051 owns the format) (F-090).
22. Decision 0006 item 4 says nothing from the FPS measurement ships in the product; 0048 adds own-process counters to the product and an armed phase-switch mode to the overlay code.
   - Ids: 0048-R4, 0048-R5, 0048-Q3
   - Resolution: Own-process counters are a Checks-class self-diagnostic (decision 0006 method 3 data, decision 0040 class), not the on / off measurement: they ship (F-032), with a one-line note in 0006. The phase switch stays in tools/ and drives the overlay through its own-window calls (F-128).
23. League re-read cadence: 0036-R2 part (b) wants an hourly re-read; decision 0026 item 4 settles 6 h or after a 404.
   - Ids: 0036-R2, 0036-Q6
   - Resolution: Decision 0026 stands (Reverses-if not met): part (b) is not adopted; part (a) ships and a core start re-reads anyway (F-031).
24. Snapshot refresh without a terminal: 0039 step 2 and 0058 ask for a start-time fetch by the launcher; three files reject a run-time fetch by the core (decision 0009 item 2).
   - Ids: 0039-R1, 0037-X1, 0039-X8, 0058-X8, 0058-Q6
   - Resolution: The core never fetches. A start-time fetch by the launcher as its own process: needs-ruling: Q-04.
25. AUDIT-P8-LOW P8-3 and P8-4 (port checks) are claimed by both 0045-R6 and 0050-R8.
   - Ids: 0045-R6, 0050-R8, P01-AUDIT-P8-LOW
   - Resolution: They land with F-091 (the smaller change); F-137 depends on it.

## Open decisions

Each question carries the consolidator's recommendation; the full records (options, sources) are in docs/plan/findings.json under open_decisions.

### Build input paths

- Q-01 (touches the floor): May AshLight read files Path of Building writes on the player's disk: the builds folder (opt-in, path shown, newest fitting file per loop tick) or PoB's local API answer file? The floor's READ ONLY list names only Client.txt, the per-press clipboard / screen read and public web data.
  - Options: no: the list is exhaustive; the hotkey load and the file pick carry the build pain | yes for the builds folder: opt-in under a new decision and one added line in the CLAUDE.md read list | yes for the folder and the API answer file
  - Recommendation: No until the operator rules in their own words. They are not game files and GGG's rules do not speak of them, but the list as written is exhaustive and no adjudicator can widen the floor; the strict reading wins. The plan builds the hotkey load and the file pick first; a yes later adds the folder source on top with no rework.
  - Touches: 0003, 0004, 0045; CLAUDE.md floor read list. Blocks: F-071. Sources: 0043-Q1, 0042-Q7, 0054-Q2, 0035-Q5.
- Q-02: Decision 0004 speaks of user-pasted build text. Does a build loaded by the item-check hotkey press (the same single clipboard read) or from a save file the player picks in the browser count as build text supplied by the player?
  - Options: yes for both: one-line amendment of decision 0004 item 4 and the CLAUDE.md Stack sentence | yes for the hotkey press only | no: paste box only
  - Recommendation: Yes for both. Each load is the player's own act, the bytes are the same as a paste, the clipboard rule (one read per manual AshLight hotkey press) is kept, and the file pick follows decision 0033 (the core gets bytes, never a path). It removes most of the paste pain inside the floor.
  - Touches: 0004 item 4; CLAUDE.md Stack sentence. Blocks: F-042, F-058. Sources: 0043-Q1, 0042-Q7.

### Data sources and web requests

- Q-03 (touches the floor): Once the repository is public, may the User-Agent contact of every install, of the CI watcher and of the OAuth application be one project address (the repository's public issues page) so no player types a contact?
  - Options: yes: project address by default, a typed per-install contact stays as an optional override | no: per-install contact only (decision 0015 as written)
  - Recommendation: Yes. It is truthful and reachable, it serves the source's purpose (reach the tool's maintainers) better than a player's personal address, it keeps personal contacts out of tracked files, and it removes the only typed step between ticking 'Use web data' and seeing prices.
  - Touches: 0015 item 1, 0016. Blocks: F-018, F-083, F-150. Sources: 0036-Q2, 0039-Q3, 0035-Q3, 0058-Q5.
- Q-04: May the launcher (run.ps1, later the installed start) run the existing snapshot tool as its own hidden low-priority process when web data is on and the cache is missing or older than 24 h? Decision 0009 item 2 and the 0013 amendment tie the fetch to build time and build.ps1.
  - Options: yes: amend 0009 item 2 to 'build time or start time, by the snapshot tool as its own process, never by the core' | no: build-time only (setup.ps1 runs the step when web data is already on)
  - Recommendation: Yes. A player of an installed copy has no build step, so 'users miss the data and the switch' (the amendment's own Reverses-if) holds by construction; the fetch keeps the same opt-in, sources, User-Agent and contact, and the core still never fetches.
  - Touches: 0009 item 2, 0004 item 7, 0013 amendment. Blocks: F-072. Sources: 0039-Q1, 0037-Q2, 0058-Q6.
- Q-05: Before the flip: does the operator send one message to poe.ninja asking whether per-install polling at the tiered cadence is acceptable or a project mirror is wanted?
  - Options: send the message | explicit skip: ship the tiered cadence without asking
  - Recommendation: Send it. poe.ninja asks desktop apps to proxy through their own backend, and a public release multiplies requests by the install count; one message costs a minute and an objection after release costs the price feature. The tiered cadence (552 down to 200 overview GETs a day) ships either way.
  - Touches: 0026. Blocks: F-046. Sources: 0036-Q1, 0057-Q7.
- Q-06 (touches the floor): Operator act (k): review decision 0017 (the app calls no trade endpoint; it only builds a search URL the player opens). And: may the overlay item card keep the item name instead of 'Trade link ready' when no poe.ninja value exists (wording of item 2)?
  - Options: keep 0017 and allow the wording change | keep 0017 unchanged | operator rules otherwise
  - Recommendation: Keep decision 0017: the trade2 endpoints are undocumented and the floor itself bars them, so nothing short of GGG documenting them changes the answer. Allow the wording change: it is display text only and a name is more useful than a status line.
  - Touches: 0017. Blocks: F-163. Sources: P01-Q4, 0042-Q3.
- Q-07 (touches the floor): Does the floor's GGG clause (endpoints only if in the API Reference or Data Exports) bind dev research reads of GGG's public patch-notes forum, which the dive prompt and runbook step 1 order today?
  - Options: binds: no agent or tool reads the forum; patch notes come from the documented developer-docs changelog, public repositories and text the operator pastes | does not bind: robots-respecting, low-frequency research reads by a session are allowed
  - Recommendation: Treat it as binding until the operator rules: the clause is written for web data in general and the forum is a GGG host outside the two named sets. Amend the dive prompt and runbook step 1 to the documented pages; at 1.0 the operator pastes the patch notes once if a session needs their text.
  - Touches: 0003; research 0029. Blocks: F-171. Sources: 0058-Q8.

### Settings, hotkeys and autostart

- Q-08: May the opt-in logon task start the desktop client in a tray-only mode (no companion window; overlay hidden until the log wakes) instead of the core alone, and may the client's page offer a small fixed set of preload actions (restart overlay, set autostart, run calc setup) instead of one?
  - Options: yes to both | tray item only: no Settings checkbox, no second preload action | keep as is: core at logon, the player starts the client
  - Recommendation: Yes to both. Starting AshLight is the one click left in a normal session; the task stays opt-in and OFF by default (decision 0011), the overlay still shows only once the log wakes (decision 0029 amendment), and the preload actions are named and argument-free. Decide with the idle memory number from the budget log.
  - Touches: 0041 points 2 and 5, 0011. Blocks: F-073, F-132. Sources: 0039-Q2, 0050-Q2.
- Q-09: Two one-minute operator checks: (1) with two keyboard layouts installed, do Alt+Shift+E or Alt+Shift+A switch the layout? (2) which Ctrl+letter next to C is free in the game's default binds?
  - Options: report both: the default item key becomes Ctrl+<free letter>, Alt+Shift+E stays a listed alternative | skip: keep Alt+Shift+E and Alt+Shift+A
  - Recommendation: Do both checks. At most two global keys are registered by default; the item key moves under Ctrl only once a free letter is confirmed by the operator's look (AshLight never reads the game's bindings), and the Alt+Shift pair is replaced only if it flips the layout.
  - Touches: 0014 (default key). Blocks: F-054. Sources: 0042-Q2, 0043-Q2.
- Q-10: Should the optional calc be on (tc_calc) on the dev host, where it is installed but unset today?
  - Options: turn it on | leave it off
  - Recommendation: Turn it on: the pin is then exercised by play as well as tests before 1.0, and the staged item check and the calc budgets get real numbers.
  - Touches: no settled decision. Blocks: F-059. Sources: 0037-Q4.

### Security and phone view

- Q-11: Phone view: which option, if any? P0 none; P1 a narrow companion window on the same PC; P2 / design A the phone as an extra display through third-party software (no AshLight change); design B an operator-run private tunnel; P3 / P4 / design C an opt-in read-only LAN listener. With any data-sending design: also allow the token-derived read-only stream key?
  - Options: P0 / design A: no network path | P1 | design B | P3 / P4 / design C (lifts the bind rule as an opt-in)
  - Recommendation: P0 / design A. The bind rule (127.0.0.1 only, LAN access off) stands, residual risk rises A < B < C, and a wireless second display gives the glance view with no new surface. The stream key is built only if a data-sending design is picked.
  - Touches: CLAUDE.md bind rule; 0002 (token wording). Blocks: F-172, F-205. Sources: 0042-Q1, 0045-Q1, P01-Q2.

### Loop, HALT and watchers

- Q-12: May the loop tick commit on main, unattended, a change that only adds row files (docs/roadmap/new/<ID>.md, docs/roadmap/done/<ID>.md) built from validated tokens?
  - Options: yes: add-only row files, at most 3 filed rows a day, operator identity, through fleet_gitlock | no: watchers only report in the tick checklist
  - Recommendation: Yes, limited to add-only row files. It is the narrowest auto-commit there is (no existing file changes, text comes from templates, never from upstream prose), it is what makes the watchers no-reminder, and decision 0025's pin move stays a session commit.
  - Touches: 0025. Blocks: F-029, F-030, F-052. Sources: 0058-Q1.
- Q-13: Should the upstream watchers (PoB release check with its static trial, Electron release watch) read while HALT is set, as the GGG docs watch does?
  - Options: read yes; no bump, no trial of candidate Lua, no commit while HALTed | respect HALT fully
  - Recommendation: Read yes, act no: same reasoning as decision 0044 item 6. HALT stays through the weeks before 1.0 and must not blind the drift check; findings wait in the halted tick's checklist. Recorded as a dated amendment of decision 0025.
  - Touches: 0025, 0044. Blocks: F-030, F-130. Sources: 0046-Q4.

### Design tokens, layout and theme

- Q-14: Optional: the operator's real monitor size, resolution and viewing distance (and one look at body text contrast in a dark room) to replace the reference setup of the type-scale rule (24 inch 1080p, 80 cm dashboard, 60 cm overlay).
  - Options: supply the measurement | ship with the stated default
  - Recommendation: Ship with the default; a measurement can replace it any time without rework because sizes are tokens and the distance rule is a test.
  - Touches: no settled decision. Blocks: F-053. Sources: 0055-Q1, 0040-Q2.
- Q-15: Operator act (h): confirm that 'NLM' at the top of design 0001 means natural-language messaging.
  - Options: yes | other meaning
  - Recommendation: Yes (one word); the doc then spells it out.
  - Touches: no settled decision. Blocks: nothing. Sources: P01-Q5.

### Tests and tooling

- Q-16: May the session gate, done.md and build.ps1 use pytest-xdist when it is importable (serial otherwise), or must parallel runs use a stdlib shard tool?
  - Options: xdist when importable (optional dev extra in requirements-dev.txt) | stdlib shard tool only
  - Recommendation: xdist when importable, once the three diagnosed runs show the earlier red loop-gate runs were not caused by it. It is a dev-only test runner plugin beside pytest, never imported by AshLight code, and the loop gate already uses it; the serial path always works.
  - Touches: 0002. Blocks: F-089. Sources: 0049-Q1.
- Q-17: Is a file-named run of a package's selected tests outside the suite gate within FLEET item 16c, with one whole suite per merge batch before main moves? The tree's Gates text changes.
  - Options: yes | yes with a cap: no timing tests, at most 90 s per subset | no: whole suite per package
  - Recommendation: Yes with the cap. The kit hook allows file-named runs, the loop prompt already does it, and a whole suite per package would cost about 200 s times the package count per wave; main still only moves after a whole green suite through the gate. Recorded as a decision and one tree Gates sentence.
  - Touches: CLAUDE.md Gates; FLEET item 16c. Blocks: F-065. Sources: 0049-Q2.
- Q-18 (touches the floor): OVL-FPS: (a) restate the acceptance as budget B19 (no change visible on the game's own FPS display with the HUD on; AshLight's own CPU under 1 percent; system-wide totals inside their own noise) because the 1 percent figure cannot be resolved by the methods decision 0006 clears? (b) may the dev check save one screen capture per manual hotkey press, cropped to the FPS readout? (c) may a flag-gated phase switch for the check ship in the overlay code, although decision 0006 item 4 says nothing from the measurement ships?
  - Options: (a) yes, (b) no, (c) no: the tool drives the overlay through its existing calls | (a) yes, (b) yes, (c) yes | keep the 1 percent acceptance (the row stays open)
  - Recommendation: (a) yes: it is the strongest claim the cleared methods can support and every write-up says it is a proxy. (b) no: decision 0006's cleared list does not name it and the operator's same / dropped answer is enough. (c) no: keep the switch in tools/ and ask again with evidence only if the existing calls cannot produce the load.
  - Touches: 0002, 0006. Blocks: F-128. Sources: 0048-Q1, P01-Q3, 0048-Q2.

### Packaging and release

- Q-19: Install home: %LOCALAPPDATA%\Programs\AshLight with player state in data\ for everyone, the operator's own installed copy under <sidecar>\Install by -InstallDir? And does the operator's live copy become an installed release, with the checkout on a spare port for dev?
  - Options: yes to both | pattern default for players; the operator keeps running the checkout | sidecar path as the default for everyone
  - Recommendation: Yes to both. Players get the reference-app pattern, this machine keeps the Sidecar order with no rule change, and running the installed release for play means every release is exercised before a stranger gets it.
  - Touches: CLAUDE.md Sidecar rule. Blocks: F-049, F-050. Sources: 0052-Q1, 0052-Q5, 0053-D2.
- Q-20: Runtimes for installed copies: Electron from a hash-pinned zip (no Node on the player's machine) and a private embeddable CPython 3.14.x, both fetched at install from their publishers and never bundled? This adds one sentence to the Stack rule (npm ci stays for the checkout) and a licence record.
  - Options: yes to both, after the spike passes | pinned Electron zip, but the player's own Python 3.13+ | npm ci and the player's Python (today's source install)
  - Recommendation: Yes to both once the spike passes. It removes the two heaviest prerequisites, both runtimes are hash-checked like the calc pins, nothing third-party is redistributed, and the embeddable zip is the smallest officially published form.
  - Touches: 0002 (stack), 0010, 0041 point 8; CLAUDE.md Stack and third-party rules. Blocks: F-047, F-050. Sources: 0052-Q2, 0052-Q3, 0053-Q6, 0053-D3.
- Q-21: Updates: (a) may the core read the project's GitHub releases once a day while web data is on (wording of decision 0018 item 6)? (b) is a verified, staged update applied by itself at the next start after a 24 h hold (Settings switch to click-only), or only on a click?
  - Options: (a) yes, (b) automatic staged apply by default | (a) yes, (b) click only | (a) no: the notice comes from the release page only
  - Recommendation: (a) yes: one documented endpoint inside the existing opt-in, nothing while web data is off. (b) automatic by default: it is the operator's minimal-interaction order and the reference pattern; the 24 h hold, hash and attestation checks and the kept previous version bound the risk of a bad release, and one switch gives click-only.
  - Touches: 0013, 0018 item 6. Blocks: F-055, F-077. Sources: 0052-Q4, 0053-Q5, 0053-D4, 0053-D9.
- Q-22: Code signing: none at first, or an identity and budget now?
  - Options: none at first; apply to a free open-source signing program after the first public release | paid signing now (individual identity, about 10 USD a month)
  - Recommendation: None at first. The pasted install line avoids the SmartScreen prompt, the README says plainly what 'unsigned' means and how to verify, there is no revenue to pay from, and signing must never be funded by anything tied to GGG-derived features.
  - Touches: 0041 point 9. Blocks: F-148. Sources: 0046-Q3, 0053-Q2, 0053-D8.

### Go-public

- Q-23: Go-public: the operator's go for step 1 (create the private repository and push main) and for step 4 (flip to public); and immutable releases on before the first v* tag?
  - Options: go for both; the flip happens by itself once the P0 list is green | go for step 1 only | not yet
  - Recommendation: Go for both in one answer, the flip conditional on the P0 findings green at the flip commit and a clean needle scan. Step 1 is private and proves the fresh clone and CI; no sign-in is needed. Immutable releases: on.
  - Touches: CLAUDE.md Public-repo hygiene (operator order 2026-11-16). Blocks: F-016, F-021. Sources: 0057-Q6, 0057-Q8.
- Q-24: May the project's own public repository address (owner and name) appear in tracked files: README install line, one constant for the update check, release metadata?
  - Options: yes: one hygiene exception for the project's own address, added to the leak-sweep allow-list at go-public | no: the address lives only in release assets and local config
  - Recommendation: Yes, for the project's own address only. A public project cannot tell players where to download without it; every other account id, path and sibling name stays barred.
  - Touches: CLAUDE.md Public-repo hygiene. Blocks: F-020, F-055. Sources: 0053-Q3, 0053-D5.
- Q-25: Only if the needle scan finds the reviewed third-party set's names in history: publish with the affected history rewritten (needs an ORDER from the fleet owner) or from a fresh root commit?
  - Options: rewrite the affected commits on the fleet owner's ORDER | fresh root commit for the public repository | not applicable: scan clean
  - Recommendation: Run the scan first; most likely it is clean and nothing is asked. If not: a rewrite on ORDER, because the history is the project's safety record and a fresh root throws it away.
  - Touches: FLEET item 17 (rewrite only on ORDER). Blocks: F-004, F-021. Sources: CRITIC-GAP-08.

### Storage of player data

- Q-26: Local stores derived from item text: (a) the worn-gear baseline as parsed stats in a bounded per-character file, on by default? (b) persist the BUILD-LIVE upgrade list across a restart?
  - Options: (a) bounded file on by default, (b) stays memory-only | (a) off by default, (b) memory-only | (a) memory only, (b) memory-only | (a) and (b) both persisted
  - Recommendation: (a) yes: parsed mod lines only, per character, bounded, under ops/runtime, cleared by 'Clear run history'; without it the baseline dies at every restart. A new decision beside 0045, not a reversal. (b) stays memory-only: decision 0045 settles it and no Reverses-if is met.
  - Touches: 0045, 0036. Blocks: F-070, F-211. Sources: 0038-Q4, P01-Q1.
- Q-27: May an off-by-default dev switch save the sanitized item text of a press as a fixture candidate in the sidecar (bounded, never tracked before review)? It answers the open facts about merchant-sale lines and note prices on copied items.
  - Options: yes: dev host only (a local.json key, not a player setting), 50 samples, names masked | no: masked property-block shapes in the parse ledger only
  - Recommendation: Yes, dev host only. Real item text is what closes the item-parser gaps before 1.0; it is the operator's own text from the permitted per-press read, and decision 0045's memory-only rule for players is untouched.
  - Touches: 0045. Blocks: F-082. Sources: 0038-Q1, 0038-Q2.
- Q-28: How does the first 1.0 play session open the UTIL-10-LOG row without a reminder: may the dev loop read AshLight's own run-history file for an Act 5 split?
  - Options: yes; fall back to the parse ledger's first Act 5 hit when run history is off | no: a session opens the row by hand
  - Recommendation: Yes. It reads AshLight's own bounded local file on the dev host, nothing from the game, and removes one reminder.
  - Touches: 0036. Blocks: F-052. Sources: 0058-Q7.

### Source questions that are not open decisions

- 0035-Q1: goes into the application text (F-083)
- 0035-Q2: measured after registration (F-080)
- 0035-Q4: no amendment of decision 0015 item 2; operator act (g) sets the contact on the dev host; moot once Q-03 is ruled
- 0035-Q6: observed at the first API call; the optional operator paste is dropped (F-035)
- 0036-Q3: observed on the first real round (F-201)
- 0036-Q4: observed on launch day (F-031, F-052)
- 0036-Q5: asked only if the fallback runbook is triggered (F-156)
- 0036-Q6: not adopted: decision 0026 item 4 stands (Reverses-if not met); part (b) of 0036-R2 is dropped (F-031)
- 0037-Q1: same as 0035-Q4: operator act (g); no tree on the dev host until then (F-142, F-113)
- 0037-Q3: no: decisions 0018 and 0027 stand (the DLL inside the PoB archive is not a LuaJIT-published hashed release); revisit after 1.0
- 0038-Q3: re-checked when the 1.0 notes are published (F-052)
- 0038-Q5: on by default, with a switch in the parts chooser (F-119)
- 0038-Q6: deferred: decide after a 1.0 endgame log; no finding
- 0038-Q7: LANG-GUARD (decision 0040) stands; language packs wait for samples
- 0039-Q4: closed: 0039-R13 is not adopted
- 0039-Q5: first part answered by the in-game check (F-100); the share is unknown
- 0039-Q6: watched by the PoB release source (F-187)
- 0039-Q7: unverified; the default folder is added only when confirmed (F-098)
- 0056-Q1: read from the league list (F-141)
- 0056-Q2: deferred with the screen-read spike (F-212)
- 0056-Q3: own table first (F-060)
- 0040-Q1: both paths start dark by the static attribute (F-086)
- 0040-Q3: moot: the new threshold does not depend on it (F-086)
- 0040-Q4: Light stays a choice, so the a11y job covers light in every tab (F-121)
- 0041-Q1: no change; needs a Windows 11 measurement first
- 0041-Q2: strict reading: no capture of the real desktop; rendered-pixel CDP check on synthetic backdrops (F-144)
- 0041-Q3: label 'Background' (F-094); design reviewer confirms
- 0042-Q4: resolved in Conflicts: Settings owns the switches it holds and indexes the rest (F-067)
- 0042-Q5: only relevant to phone option P2 (Q-11)
- 0042-Q6: unknown; no telemetry by design
- 0043-Q3: no wave before 1.0 (F-212)
- 0043-Q4: confirmed on the first run of F-066
- 0043-Q5: state g is part of F-066
- 0043-Q6: each addition re-runs F-066 when built
- 0044-Q1: settled by the hidden Electron probe (F-145)
- 0044-Q2: resolved in Conflicts: the 0041 recipe (F-094)
- 0044-Q3: closed by F-121
- 0045-Q2: no change: hot reload is on only in a source checkout (decision 0042); installed copies have no .git
- 0045-Q3: answered by the live bridge tests (F-138)
- 0045-Q4: probed in F-012
- 0045-Q5: moot after F-002
- 0045-Q6: kept: the Bearer form is not cut without evidence that nothing uses it
- 0045-Q7: low stakes (the token dies with the core); no work
- 0046-Q1: one logged client run while the game is idle (F-110)
- 0046-Q2: needs a Windows 11 tester (F-148)
- 0046-Q5: observed at the 46.x adoption window (F-130)
- 0050-Q1: no: decision 0041 point 2 stands; the client relaunches itself (F-105)
- 0050-Q3: measured by the budget log at the next cold start (F-032)
- 0050-Q4: observed by the tailer counters (F-032); the scan-cap note is in F-061
- 0050-Q5: only say so; never move ports by itself (F-091)
- 0050-Q6: only offer; never switch by itself (F-001)
- 0050-Q7: closed by its file: no faster retry
- 0051-Q1: resolved by the stricter reading: a new consent line; revoking deletes the file (F-061)
- 0051-Q2: unverified; the design treats them as chat either way
- 0051-Q3: a BUILD file written by the release tool (F-027, F-048)
- 0051-Q4: design reviewer; default: players see the row only after 3 restarts in a day (F-129)
- 0051-Q5: yes, for English clients (F-075)
- 0047-Q1: keep as is; F-017 removes the collision without a rules change
- 0047-Q2: unverified for bare mode; no rule text leaves CLAUDE.md
- 0047-Q3: an operator settings edit (F-200)
- 0047-Q4: published as a tracked archive file (F-028) after F-004
- 0047-Q5: plan 03 decides; the fragment half of F-194 waits
- 0048-Q3: resolved in Conflicts: own-process counters are a Checks-class self-diagnostic; the phase switch stays in tools/ (F-032, F-128)
- 0048-Q4: decided by the first budget log (F-032)
- 0048-Q5: one glance by the operator, part of F-128
- 0048-Q6: not knowable inside the floor; no work
- 0049-Q3: measured per batch in wave 1 (F-065)
- 0049-Q4: the three diagnosed runs before F-089
- 0052-Q6: verified by the sandbox phases (F-074)
- 0053-Q1: needs a clean Windows 11 run (F-148)
- 0053-Q4: deferred (F-210)
- 0053-Q7: settled by the release tool's two-builds test (F-048)
- 0053-D1: decided by the Fit section: app zip, offline full zip, install.ps1, no framework (F-048)
- 0053-D6: SemVer 0.y.z, tag v + VERSION (F-023)
- 0053-D7: -Purge (F-063)
- 0057-Q1: default 'The AshLight authors' (F-009)
- 0057-Q2: moot: the ruleset comes after the flip (F-021)
- 0057-Q3: goes into the next note to the fleet owner (F-203)
- 0057-Q4: read fleet_inbox first (F-200)
- 0057-Q5: the inputs sit in docs/plan/09 (F-040)
- 0058-Q2: no (stricter reading of decision 0009): shape probes run on the dev loop host (F-150)
- 0058-Q3: gh is authenticated on the dev host; the lane closes the PR (F-081)
- 0058-Q4: observed once the remote exists (F-150)
- 0054-Q1: not asked: the decision 0029 amendment stands (no window check); three files reject the foreground-window hide
- 0054-Q3: deferred with F-208
- 0054-Q4: unknown; no telemetry by design
- 0054-Q5: low decision weight; left unverified
- 0055-Q2: no: no demand evidence
- 0055-Q3: default ON with the tray toggle (F-167)

## Not adopted

- 0039-R13 Search-string hotkey for one-screen players - against a settled decision: decisions 0014 and 0030 copy search strings only on the player's click and no Reverses-if is met; it would also be a third global hotkey; superseded by F-124
- P01-NOTE-S5-REAP NOTE: session-5 reap - cut: obsolete (the reap is recorded done in session 6); /done drops the note
- P01-NOTE-TREE-BY-MAIN NOTE: tree created by MAIN - cut: informational, no action; the note stays verbatim in the hand-off
- P01-L8 No TODO / FIXME markers - cut: no action; open work lives in ROADMAP only, the intended pattern
- P01-L11 Decision 0035 unused, next free 0046 - cut: no action; consistent
- 0035-X1 Another application's client id (PoB's) - rejected by its file; against a settled decision: Untruthful User-Agent, barred by decision 0004 item 4.
- 0035-X2 character-window, profile scraping, POESESSID, or any route to PoE2 backpack/stash (trade site, memory, packets) - rejected by its file; outside the floor: The floor and ToU 7i.
- 0035-X3 Calling the Currency Exchange endpoint now with a plain or invented OAuth User-Agent - rejected by its file: Against the ruling in research 0018.
- 0035-X4 Confidential client behind a hosted backend for service scopes and longer tokens - rejected by its file: D-IDX wants a public client for an executable, there is no backend, LAN access stays off.
- 0035-X5 Embedded web view for sign-in, or an automated consent click - rejected by its file: RFC8252 8.12 (password would pass through the app); ToU 7c (approval must be the player's own act).
- 0035-X6 A timer polling the character every few seconds - rejected by its file: Shared limits and the invalid-request rule; events are enough.
- 0035-X7 Tokens in config/local.json, a log or the settings export - rejected by its file: Listed as rejected (token store is Credential Manager, R4).
- 0035-X8 Applying through the old mail channel or support - rejected by its file: D-IDX says closed and names no channel.
- 0035-X9 Bundling the tree export - rejected by its file; against a settled decision: No licence; decision 0009.
- 0036-X1 poe.ninja builds, profiles, character or PoB endpoints - rejected by its file: Closed to third parties by the source (ND); would carry other players' data.
- 0036-X2 Reading poe.ninja HTML pages or undocumented routes (history, details, 2025 currencyexchange/overview) - rejected by its file: Outside ND, not permitted.
- 0036-X3 Polling faster than hourly, cache-busting params, or a request per item-check press - rejected by its file; against a settled decision: Against ND and decision 0026 item 2.
- 0036-X4 The trade site as a price fallback - rejected by its file; outside the floor: Floor rule (trade site never called) and decision 0017.
- 0036-X5 GGG Currency Exchange endpoint today - rejected by its file: The 0018 ruling stands until an AshLight OAuth client exists; its Reverses if not met.
- 0036-X6 Paid third-party price APIs wrapping the trade site - rejected by its file: Trade data by proxy, and money changing hands over GGG-derived data.
- 0036-X7 Another tool's User-Agent or a nameless one to get past a block - rejected by its file: Breaks the truthful-User-Agent rule.
- 0036-X8 A shared default contact in a tracked file while the repo is private - rejected by its file: Public-repo hygiene rule (see 0036-Q2).
- 0037-X1 Core run-time fetch of repoe-fork or tree files - rejected by its file; against a settled decision: Against decision 0009 item 2; reversal conditions not met.
- 0037-X2 Bundled tree, zone or ascendancy snapshot for offline first run - rejected by its file; against a settled decision: Against decision 0009 item 1.
- 0037-X3 Reading the game's own data files to export data ourselves - rejected by its file; outside the floor: Outside the floor: only Client.txt, clipboard/screen per press, public web data.
- 0037-X4 Checking or filling trade stat ids from the trade site - rejected by its file; outside the floor: Outside the floor (trade endpoints never called) and decision 0017.
- 0037-X5 Committing the pin from the detached trial, or running candidate Lua unattended by default - rejected by its file; against a settled decision: Against decision 0025 and its amendment; neither reversal condition met.
- 0037-X6 Pinning PoB's dev or beta branch for players - rejected by its file; against a settled decision: Decision 0018 pins a release; unreleased code would reach players.
- 0037-X7 A stored GitHub token for a higher quota - rejected by its file: Not needed (F8: ref advertisement has no quota); a stored secret for a read-only check is cost without gain.
- 0037-X8 poe2db or wiki text for Acts 5-6 on launch day - rejected by its file; against a settled decision: Against decision 0009 item 4.
- 0037-X9 Retiring the PoB TradeSiteStats fallback now (draft R4) - rejected by its file; against a settled decision: Correctness: 2026-11-18 repoe-fork export has 0 of 8 Local twin ids; decision 0037 amendment's full-coverage reversal not met (F11).
- 0038-X1 One-press item check that sends the copy key - rejected by its file; outside the floor: Floor forbids any input to the game (research 0006; decision 0003).
- 0038-X2 Listing-based or model-based prices for rares - rejected by its file; against a settled decision: App never calls the trade site (decision 0017); no permitted source exists.
- 0038-X3 Stash value or loot from the account APIs - rejected by its file: Needs an OAuth client; registration closed; stays BLOCKED on TC-OAUTH-REG.
- 0038-X4 Clone frames, stash price overlays, atlas overlays - rejected by its file; outside the floor: Need repeated screen reads; floor allows one per manual press.
- 0038-X5 Trade reply helpers (invites, messages from a panel) - rejected by its file; outside the floor: Input to the game.
- 0038-X6 An XP multiplier or penalty number - rejected by its file: A formula AshLight cannot verify for PoE2; research 0028 ruling B stands.
- 0038-X7 Meta or build data from poe.ninja; own DPS or EHP numbers without PoB - rejected by its file; against a settled decision: Excluded for third parties (research 0019); own numbers barred by decision 0004.
- 0038-X8 Reading the reported in-game death recap from the screen on a press - rejected by its file; against a settled decision: Inside the floor, but OCR is a new dependency (stdlib-only core, decision 0002) for something the game already shows.
- 0038-X9 A 'sold while away' feed for merchant-tab sales - rejected by its file: Players ask for it but no permitted source is known (no log line seen).
- 0038-X10 Gem swap planner - rejected by its file; against a settled decision: Needs per-build guide prose (decision 0009); research 0031 item 8 stands.
- 0038-X11 Hiding the overlay by a foreground-window check - rejected by its file; against a settled decision: Close to the process check decision 0029 ruled out; passed to note 0042 as a question, not recommended.
- 0039-X1 Writing the filter or the .build into the game's folders, even by a Save dialog - rejected by its file; outside the floor: Floor 'never modify any game file'; reversal conditions of decisions 0031 and 0034 not met.
- 0039-X2 Reading the game's own config or registry keys (display mode, language, league, install path) - rejected by its file: Outside the Client.txt allowance (research 0032).
- 0039-X3 Finding the game process or window to start or place the overlay - rejected by its file; against a settled decision: Decision 0029, no process-list check.
- 0039-X4 Typing or pasting a search string into the game, or sending Ctrl+C - rejected by its file; outside the floor: Synthesized input, floor.
- 0039-X5 A clipboard watcher that checks items by itself - rejected by its file; outside the floor: Floor: one read per manual press (a PoE1 overlay switched off continuous screen reads 2026-11-12 after GGG's policy update).
- 0039-X6 A filter upload or build subscription through GGG's account API - rejected by its file: OAuth only, registration closed (TC-OAUTH-REG); never a cookie.
- 0039-X7 Sending the Checks report anywhere by itself - rejected by its file: Ruling J (research 0032).
- 0039-X8 A snapshot fetch by the core on demand - rejected by its file; against a settled decision: Decision 0009 item 2; R1 keeps the fetch in a separate process.
- 0039-X9 A paid updater or tier; bundled filters or game data - rejected by its file; outside the floor: Floor: no revenue from GGG IP; bundling barred by decision 0009.
- 0056-X1 Reading game process memory through a HUD host (repos B-G) - rejected by its file; outside the floor: Outside the floor (no memory reads). Not detailed.
- 0056-X2 Drawing inside the game through a host renderer (repos B, C, D, E, G) - rejected by its file; outside the floor: Outside the floor; AshLight's overlay is a separate click-through window.
- 0056-X3 Synthesized input, including an automated logout (repo F) - rejected by its file; outside the floor: Outside the floor (no input of any kind).
- 0056-X4 Reading installed game archives or the undocumented patch CDN, type inference over undocumented tables (repo A) - rejected by its file; outside the floor: Outside the floor (game files not permitted; GGG endpoints only if documented).
- 0056-X5 World-anchored markers and minimap routes (repos D, G) - rejected by its file: Need entity positions from memory; floor-safe remainder (ordered text list) already in ZONE-GUIDE.
- 0056-X6 Hovered-tooltip dimming (repo E) - rejected by its file: Needs tooltip position from memory; safe remainder is a player-chosen card anchor away from screen centre (0054 R2).
- 0056-X7 A donation request on the README (repo G) - rejected by its file; outside the floor: Bars nothing alone, but a donation gate on GGG-derived features is outside the floor; AshLight adds none.
- 0056-X8 Any code copy from the set - rejected by its file: 5 repos state no licence (all rights reserved, L1); 2 MIT repos would need notice kept (L2), a licence check in docs/decisions and a THIRD-PARTY entry, and nothing fits a stdlib Python core. Ideas only.
- 0040-X1 Game-styled chrome (rarity colours, item frames, fonts or textures imitating the game) - rejected by its file; outside the floor: Floor: no GGG art, logos or trademarks in branding; never present AshLight as official.
- 0040-X2 Blurred / frosted overlay plate or scene-adaptive plate - rejected by its file; outside the floor: Needs the game's pixels continuously; floor: screen read only once per manual hotkey press.
- 0040-X3 Dim dashboard or switch theme when the game is in front or running - rejected by its file; against a settled decision: Needs a process or window check, against decision 0029.
- 0040-X4 Pulse, flash or slide for a new trade or verdict - rejected by its file: DS 2 principle 3 and DS 10 forbid motion; overlay must not cost FPS.
- 0040-X5 Second overlay card or third HUD line - rejected by its file; against a settled decision: Decision 0014 (one card slot) and DS 7.2 stand; no reversal condition met.
- 0040-X6 Red for a downgrade verdict or falling price - rejected by its file: DS 6 reserves red for failures and deaths.
- 0040-X7 Brand orange as the interface accent - rejected by its file: Sits beside warn amber and would blur "needs you soon".
- 0040-X8 Editing kit token values in this tree - rejected by its file: FLEET item 11; a wish for a kit 3:1 edge token goes to the kit owner as a note.
- 0040-X9 Icon or web fonts from a CDN - rejected by its file: Stack rule: no CDN at runtime.
- 0041-X1 Bundling a web font (Inter, Selawik or similar) - rejected by its file: Segoe UI on every supported Windows; bundling needs licence record, adds bytes, overlay CSP has no font-src; Segoe UI itself may not be shipped (MS-FAQ). Revisit only for a non-Windows target.
- 0041-X2 A game-style display face - rejected by its file: Reads as GGG branding / imitates the game; ToS floor on GGG branding; licence unknown.
- 0041-X3 Plate that adapts to scene brightness by sampling the screen - rejected by its file; outside the floor: Needs a continuous screen read, forbidden by the floor.
- 0041-X4 Outline-only text with no plate (P-REC r6) - rejected by its file: 1.22-1.28 far-field over white, warm and fire, 1.00 over checker; fails at any size.
- 0041-X5 -webkit-text-stroke outlines (P-REC r4 / r5) - rejected by its file: Thicken and blur 13-14 px glyphs; only work with a weaker plate, costing more than they add.
- 0041-X6 Flashing, pulsing or colour cycling for salience - rejected by its file: Design 0001 section 10 and WCAG 2.3.1; costs repaints against the FPS budget.
- 0041-X7 Overlay text 16 px everywhere - rejected by its file: 3-line card would not fit 258 px for typical trade lines (~258 px vs 238 px room); window would need to grow; 14 px with R6 reaches the same physical size on 1440p / 4K.
- 0042-X1 One-press item check with AshLight sending Ctrl+C - rejected by its file; outside the floor: Synthesized input, floor. Two chords is the minimum.
- 0042-X2 Checking an item as soon as it is copied - rejected by its file; outside the floor: A clipboard watcher, floor.
- 0042-X3 Invite or reply buttons that type into the game chat - rejected by its file; outside the floor: Input, floor (research 0038 same).
- 0042-X4 Reading Path of Building's own build folder to skip the paste - rejected by its file; against a settled decision: Not on the floor's read list; decision 0004 gives only user-pasted build text; no reverse condition met. Conflicts with 0043 R3; plan needs one ruling (0042-Q7).
- 0042-X5 Finding the game window or process for certain game-closed or in-place hotkeys - rejected by its file; against a settled decision: Decision 0029.
- 0042-X6 Reading the game's key bindings or config to avoid chord clashes - rejected by its file: A game file, outside the Client.txt allowance.
- 0042-X7 Turning web data on by itself when a link is pasted - rejected by its file; against a settled decision: Decision 0013; R8 keeps the click.
- 0042-X8 First-run wizard, confirm dialog, toast or sound - rejected by its file: Design 0001 N2 and principle 3; R3 and R9 do the same work in place.
- 0042-X9 LAN bind by default or a cloud relay for the phone - rejected by its file: The bind rule and the local-only promise (research 0045).
- 0043-X1 AshLight sending Ctrl+C on its own press - rejected by its file; outside the floor: Synthesized input (floor).
- 0043-X2 Check an item or load a build as soon as it is copied - rejected by its file; outside the floor: A clipboard watcher (floor).
- 0043-X3 Pass-through key listener treating the player's Ctrl+C as the AshLight press - rejected by its file; against a settled decision: Needs a system-wide keyboard hook seeing every key; decision 0003 keeps copy and press apart; hotkeys.py bars Ctrl+C. Reverses only if decision 0003 does.
- 0043-X4 Load build from clipboard button on the dashboard - rejected by its file; outside the floor: Clipboard read on a click, not on a manual AshLight hotkey press (floor); R4 gives the same result inside it.
- 0043-X5 Public profile sources (poe.ninja character/build endpoints, website character-window endpoints) - rejected by its file: poe.ninja endpoints internal, not for third parties; website endpoints undocumented and need POESESSID (research 0033 s3; floor).
- 0043-X6 Reusing PoB's OAuth client id or saved tokens - rejected by its file: Misrepresents the client (research 0033) and reads another program's credentials.
- 0043-X7 Reading the game's planner or filter folder for a build - rejected by its file: Game folders outside the Client.txt-only read rule (research 0033 s4); they hold a plan, not the character.
- 0043-X8 Repeated or timed screen reads for inventory or stash - rejected by its file; outside the floor: Continuous capture (floor).
- 0043-X9 A three-tab set (Play, Review, Setup) - rejected by its file: Puts two unrelated things in one panel and brings scroll back (tab audit).
- 0044-X1 Screen reader reading the overlay or an accessible overlay focus mode - rejected by its file: Overlay must stay non-focusable and click-through (floor overlay rule); the dashboard is its equivalent.
- 0044-X2 Announcing the item verdict by speech synthesis or sound on the hotkey press - rejected by its file: Not an accessibility need the dashboard leaves open; design 0001 N2 rules out alerts; rejected on scope, no floor issue.
- 0044-X3 Reading the game's colour-blind or UI-scale settings to match them - rejected by its file; outside the floor: Would read game files or settings outside Client.txt (floor).
- 0044-X4 Timer re-showing the overlay card longer than 20 s by default for 2.2.1 - rejected by its file; against a settled decision: Not needed (S2 alternative rule, F10) and takes the one card slot from the next press (decision 0014).
- 0045-X1 Binding the LAN by default, or all interfaces ever - rejected by its file: Against the bind rule; only the operator can change it, and then only as an opt-in.
- 0045-X2 A cloud relay for the phone view - rejected by its file; against a settled decision: Sends log-derived data off the PC and adds an account, against the local-only promise and decision 0013's public-web-data scope.
- 0045-X3 Cookie login for the dashboard - rejected by its file: Ambient credential re-opens CSRF; the header token is stronger.
- 0045-X4 TLS on loopback - rejected by its file: No gain against T1 or T5; certificate warnings break zero-click.
- 0045-X5 Dropping token reuse (decision 0042) - rejected by its file: Its reverse condition (reuse ruled unsafe) is not met once R4 makes the runtime dir private.
- 0045-X6 Finding and stopping whatever holds the port - rejected by its file; against a settled decision: AshLight stops only its own processes (decision 0010).
- 0045-X7 Proving the listener by a process or handle lookup - rejected by its file; against a settled decision: R6 proves it with the token and looks at no process (clear of decision 0029).
- 0045-X8 Pre-granting the browsers' local-network permission by policy - rejected by its file: Weakens a protection the browser gives; the same-origin dashboard never needs it.
- 0046-X1 Flipping fuses on the stock binary now - rejected by its file: Every npm ci undoes it, it changes the hash R4 pins, and with no signature nothing stops bits being flipped back; R5 covers it in code.
- 0046-X2 Merging Dependabot pull requests on GitHub - rejected by its file: Against FLEET item 17.
- 0046-X3 An in-app updater or version check by the running app - rejected by its file; against a settled decision: Network call outside the web-data opt-in (decision 0013); the dev loop watches.
- 0046-X4 Process-list check for the game before the live smoke, or running the smoke during play - rejected by its file; against a settled decision: Decision 0029 forbids the first; the log-staleness idle state gates both.
- 0046-X5 Paying for signing out of donations or ads tied to GGG-derived features - rejected by its file; outside the floor: The floor bars revenue from GGG intellectual property.
- 0046-X6 Vendoring Electron, PoB or LuaJIT, or a hash pin for the locally built luajit.exe - rejected by its file; against a settled decision: Decisions 0009 and 0018 (never vendored; no hash exists before a local build).
- 0046-X7 Packaging now - rejected by its file; against a settled decision: Decision 0041 point 9 stands; its reverse condition (a release channel) not met while no remote exists. Left to 0053.
- 0046-X8 EV or self-signed certificate - rejected by its file: On merit: no SmartScreen gain.
- 0046-X9 --no-sandbox to save RAM - rejected by its file: On merit: removes the renderer sandbox.
- 0046-X10 Staying one major behind - rejected by its file: On merit: older lines sit on Chromium milestones with no upstream channel left.
- 0050-X1 Check the process list for the game to tell game closed from log unreadable - rejected by its file; against a settled decision: Against decision 0029; reversal conditions not met.
- 0050-X2 Persist session state on every event - rejected by its file; against a settled decision: Rejected by decision 0008; no evidence for its reversal.
- 0050-X3 Let the supervisor start Electron - rejected by its file; against a settled decision: Against decision 0041 point 2.
- 0050-X4 Keep the token across a crash restart so browser tabs reconnect - rejected by its file; against a settled decision: Widens decision 0042's narrow reuse and weakens the per-start token; client window already heals, gain is a browser tab only.
- 0050-X5 A scheduled task polling the supervisor every minute - rejected by its file; against a settled decision: Decision 0005 alternative B; the log shows no supervisor failure.
- 0050-X6 A Windows service for the core - rejected by its file; against a settled decision: Needs admin rights, against the no-admin stance of decisions 0011 and 0041.
- 0050-X7 Write a marker into the game's log folder, or hold Client.txt open, to detect rotation - rejected by its file; outside the floor: Floor forbids modifying any game file; tailer holds no handle between polls on purpose.
- 0050-X8 Send a key to the game so it writes a log line as a liveness probe - rejected by its file; outside the floor: Any synthesized input is outside the floor.
- 0050-X9 Retry a failed poe.ninja fetch after 5 minutes (draft R7 part) - rejected by its file: Research 0036 reads overuse as a block risk and rejects polling faster than hourly; public web data allowance does not cover hammering.
- 0050-X10 Let a demo or test core keep discovery but hide its indicator - rejected by its file; outside the floor: Floor ties tailing to the player's opt-in and a visible indicator; R0 removes discovery instead.
- 0051-X1 Automatic upload of a report, shapes, metrics or crash dumps - rejected by its file; against a settled decision: Network call outside the web-data opt-in (ruling J, decision 0013); no first-party server exists.
- 0051-X2 Storing raw unknown lines for debugging, even locally - rejected by its file: Puts chat, names and addresses on disk; consent text says what is derived, not that the log is copied.
- 0051-X3 Mining repeated tokens as shape constants (DRAIN style) for localised lines - rejected by its file: The player's own character name repeats most.
- 0051-X4 Screen capture, look at the game window or process, or game config read to explain a hidden overlay or display mode; frame tracing for an FPS gauge - rejected by its file; outside the floor: Outside the read floor (decisions 0003, 0029); frame tracing barred by decision 0006.
- 0051-X5 Logging a press's clipboard or item text - rejected by its file; against a settled decision: Memory only (decision 0045).
- 0051-X6 A health or metrics page on the LAN or a phone - rejected by its file: 127.0.0.1 only.
- 0051-X7 A third-party logging, metrics or crash library, or an exporter - rejected by its file; against a settled decision: Core is stdlib only (decision 0002).
- 0051-X8 Machine-wide crash dump settings in the registry - rejected by its file: Needs admin; a full dump holds the token, chat and item text.
- 0051-X9 The build id in the User-Agent - rejected by its file; against a settled decision: Changes a settled contract for no gain (decisions 0013, 0015).
- 0047-X1 A bundler or transpile step (esbuild, Rollup, TypeScript) to divide app.js - rejected by its file; against a settled decision: Decision 0002 keeps the dashboard static HTML/CSS/vanilla JS; its reversal condition not met; adds supply chain for no player value.
- 0047-X2 Loading a helper or module loader from a CDN - rejected by its file: CLAUDE.md no CDN at runtime; CSP script-src 'self'.
- 0047-X3 Moving the clipboard-read wiring out of app/main.js as tidying - rejected by its file; outside the floor: Floor: clipboard read only once per manual hotkey press; the one read is pinned to app/main.js at its reviewed anchor; a structure package must not widen where a read may live.
- 0047-X4 Moving theorycraft/datacredit.py up a level - rejected by its file; against a settled decision: Settled decision 0020 names that file as the only home of credit text; reversal conditions not met.
- 0047-X5 Moving the Settled list into path-scoped rules to reach 200 lines - rejected by its file: paths rules load only on matching files, so an agent could propose reversing a settled floor-adjacent call (0017) without seeing it.
- 0048-X1 PresentMon, CapFrameX, RTSS or any ETW present trace of the game, also for development; GPU/CPU counters keyed to the game's pid - rejected by its file; against a settled decision: Decision 0006 and the floor's READ ONLY what GGG permits.
- 0048-X2 Finding the game's window, display mode, focus or process to pause work or time the check - rejected by its file; outside the floor: Floor 'never touches the game process' and decision 0029 (log staleness only).
- 0048-X3 A timed or repeated screen capture of the FPS readout, or an OCR loop - rejected by its file; outside the floor: Floor allows the screen once per manual press, never a timer.
- 0048-X4 Synthesising the overlay toggle key to switch phases - rejected by its file; outside the floor: Any synthesised input is outside the floor.
- 0048-X5 Drawing inside the game to keep its direct present path - rejected by its file; outside the floor: Injection and graphics hooks are outside the floor.
- 0048-X6 Turning hardware acceleration back on for the overlay - rejected by its file; against a settled decision: Decision 0002 keeps it off so the overlay never queues GPU work beside the game; reverse condition not met.
- 0048-X7 Raising any AshLight process above normal priority - rejected by its file: Opposite of R2.
- 0049-X1 Throttling or pausing test runs by probing the game process, FPS or frame times - rejected by its file; outside the floor: Outside the floor (decisions 0029, 0006); inside it: below-normal priority and a fixed worker cap.
- 0049-X2 Dropping the floor scan, overlay smoke static checks or budget tests from package checks - rejected by its file: They are the floor's guards (CLAUDE.md names test_budgets.py and the overlay smoke).
- 0049-X3 Running the live overlay smoke (AL_OVERLAY_SMOKE=1) inside waves - rejected by its file: Opens the overlay window while the operator plays.
- 0049-X4 Hiding a whole-suite pytest from the claims hook in a script, raising the machine slot count from this tree, or patching the kit gate at :672 locally - rejected by its file: Against FLEET items 16 and 11; slots are MAIN's ruling.
- 0049-X5 pytest-testmon or any coverage-based selector - rejected by its file; against a settled decision: Two more dependencies against decision 0002; the stdlib F6 map is enough with a batch suite.
- 0049-X6 pytest-rerunfailures - rejected by its file: Hides flakes; tree practice is a named root cause (FLAKY-EVAL-API).
- 0049-X7 Deleting the loop tooling tests (69.5 s) because the loop is paused - rejected by its file: Loop is ARMED and HALT is temporary; tier them (R1).
- 0049-X8 Fewer reloads in the calc memory test (11.2 s) - rejected by its file; against a settled decision: Its numbers are settled in decision 0028 and its reverses-if is not met.
- 0052-X1 Packaged .exe or installer framework now - rejected by its file; against a settled decision: Against decision 0041 point 9; its Reverses-if not met: the pattern delivers the channel without one. Options stay with 0053.
- 0052-X2 Update check or download while web data off - rejected by its file; against a settled decision: Against decision 0013.
- 0052-X3 Timing update restart by looking for game in process list - rejected by its file; against a settled decision: Against decision 0029; game_idle from the log is the signal.
- 0052-X4 Installing/removing anything in a game folder; game data in release zip - rejected by its file; outside the floor: Floor (no game file change); decisions 0031, 0034; game data in zip against 0009.
- 0052-X5 Windows service or machine-wide install - rejected by its file; against a settled decision: Against decisions 0005 and 0011 (detached per-user supervisor; logon start opt-in task).
- 0052-X6 Telemetry, crash upload or update ping with an identifier - rejected by its file; against a settled decision: Against README privacy promise (README.md:119), decision 0013 and decision 0040 (report leaves only by click, redacted).
- 0053-X1 Silent automatic updates by default - rejected by its file: New code without player's act; hijacked release reaches every install in a day (consent, supply chain); opt-in at most. Amended by Fit point 4: still rejected is an update with no notice; automatic staged apply with named line, 24 h hold and rollback is chosen.
- 0053-X2 Install/update/uninstall step writing into a game folder - rejected by its file; outside the floor: Floor never modify any game file; decisions 0031, 0033, 0034.
- 0053-X3 Checking whether the game runs before update/uninstall - rejected by its file; against a settled decision: Decision 0029 rules out process-presence checks; updater needs none.
- 0053-X4 Update check through a GGG host, or bundling snapshot, PoB source or LuaJIT - rejected by its file; outside the floor: Floor (documented endpoints only); decisions 0009, 0018, 0027.
- 0053-X5 Paid/donation-gated downloads, supporter builds, ads; GGG art/name in artifact, shortcut, publisher or listing - rejected by its file; outside the floor: Floor: no commercial revenue from GGG IP; trademarks and branding.
- 0053-X6 Self-signed certificate, or telling users to switch SmartScreen/SAC off - rejected by its file: Same SmartScreen result as unsigned; unsafe advice.
- 0053-X7 Machine-wide installs needing admin (HKLM, services, Program Files) - rejected by its file: Against per-user no-admin design (0011, 0041 item 8).
- 0053-X8 One-line download-and-run web command in README - rejected by its file: Runs unreviewed remote code. SUPERSEDED by Fit point 6: pasted line is primary route; download, verify, -Zip is second.
- 0053-X9 electron-updater or update-electron-app as shipped - rejected by its file: Poll on own schedule regardless of web-data opt-in (against 0013) and need a packaged app.
- 0057-X1 History rewrite or fresh root commit - rejected by its file: No finding needs one (F1, F2); rewrite would need a MAIN order via fleet_rewrite.py.
- 0057-X2 Pull-request-required ruleset on main - rejected by its file: Blocks loop's direct push and local-merge workflow; force-push/deletion blocks plus required checks suffice.
- 0057-X3 Game screenshots in README or social preview - rejected by its file: GGG art (floor no GGG trademarks, art or logos).
- 0057-X4 Sponsors / FUNDING.yml link - rejected by its file; outside the floor: Floor no ads or donation gate on GGG-derived features; reads as revenue from GGG IP.
- 0057-X5 CI with web_data on, or CI job calling poe.ninja or GGG docs - rejected by its file: Needless traffic and contact header in CI; public web data is for user's opt-in.
- 0057-X6 Moving CLAUDE.md, kit or hand-off out of the tree - rejected by its file: 6 of 7 peers publish them; FLEET block byte-pinned and tested; explanation (R10) cheaper.
- 0058-X1 Plain-Python daily read of official patch-notes board - rejected by its file: robots allows, but GGG page outside API Reference/Data Exports, no feed; floor GGG clause not clearly met; W4/W5 detect patches without it. Existing dive/runbook practice not extended (Q8).
- 0058-X2 CI job that commits state, moves a pin or merges Dependabot PR - rejected by its file: FLEET item 17 (no bot author, no merge on GitHub).
- 0058-X3 Row text from issue body, release note or commit title - rejected by its file: A public stranger could steer a lane (F14).
- 0058-X4 Screenshots of real desktop or overlay above the game - rejected by its file; outside the floor: Floor allows screen read only per manual hotkey press; game art may not appear in branding.
- 0058-X5 Toast, message box or chat line on change - rejected by its file: Focus-taking, rejected in 0044 item 5; FLEET item 2 keeps chat quiet.
- 0058-X6 Dev watchers inside the shipped core - rejected by its file; against a settled decision: Rejected in decision 0044 (Fetch in the core); 0013 covers only player's requests.
- 0058-X7 Unattended pin move or unattended run of candidate Lua - rejected by its file; against a settled decision: Decision 0025 and amendment.
- 0058-X8 Runtime snapshot fetch by the core - rejected by its file; against a settled decision: Decision 0009 (build-time only).
- 0058-X9 Process-list check whether game closed before a heavy job - rejected by its file; against a settled decision: Decision 0029; jobs run hidden at below-normal priority.
- 0058-X10 A model run per tick to look for changes - rejected by its file: 96 ticks a day against a cap of 120 (FLEET items 10, 14).
- 0058-X11 Trade site or session cookie as league or patch signal - rejected by its file; outside the floor: Floor.
- 0054-X1 A copy key the tool presses; reply / invite / trade-request / hideout buttons; pasting a search string into the game's box (A1, A3, A5, C1-C3, D1) - rejected by its file; outside the floor: Floor, no input; AshLight copies on a click and the player pastes.
- 0054-X2 Trade-site listings and model estimates trained on them (A1-A3, B1) - rejected by its file; outside the floor: Floor and decision 0017.
- 0054-X3 Self-running screen reads, screen-region mirrors, per-feature screen calibration (D1, C2) - rejected by its file; outside the floor: Floor (one read per press); D1 itself switched three off; calibration is upkeep every patch.
- 0054-X4 Price tags drawn over stash tabs (I3) - rejected by its file: Clutter, hand-tuned offsets (upkeep), content cap of design 0001 section 10.
- 0054-X5 Overlay layer that takes clicks after a key (A1, A5, D3, D5) - rejected by its file; outside the floor: Floor wording (click-through, non-focusable); R8 is the answer inside it.
- 0054-X6 Hide overlay unless the game is the foreground window (D4, SNIP-POL2) - rejected by its file; against a settled decision: Settled, decision 0029 amendment (Open question 1).
- 0054-X7 Platform overlay infrastructure, ads and paid tiers (B1-B3) - rejected by its file; outside the floor: Floor: no injection; no revenue from GGG-derived features.
- 0054-X8 Account sign-in features: stash tracking, inventory snapshots, character import (B1, A5, E3, G3, G4) - rejected by its file; against a settled decision: Registration closed and two such tools are dark (F3); decision 0045 keeps the stub.
- 0054-X9 Sounds and desktop toasts (C1, E2, E3) - rejected by its file: Clutter; design 0001 principle 3.
- 0054-X10 Patch-notes window at launch (C1, C2) - rejected by its file: Clutter; R6 uses a fold.
- 0054-X11 Saving a filter into the game's folder or by account sync (H2, H1) - rejected by its file; against a settled decision: Settled decisions 0031 and 0033.
- 0054-X12 Commands typed into local chat and read back from the log (E2, D5) - rejected by its file: Clutter (other players see the line) and upkeep.
- 0054-X13 XP multiplier number (A1) - rejected by its file: D1 calls the PoE2 formula unknown; rejected in note 0038 (research 0028 ruling B).
- 0054-X14 Data-only releases (A3) - rejected by its file; against a settled decision: Upkeep; AshLight fetches at run time under the one opt-in (decision 0026).
- 0054-X15 Themes by the dozen (C1) - rejected by its file: Upkeep against the measured contrast pins of design 0001.
- 0054-X16 Free dragging of every widget (D3) - rejected by its file: Windows lost off-screen; clutter; corners only (design 0001 section 10).
- 0054-X17 Hook libraries and resizing the game window (C3, D1) - rejected by its file; outside the floor: Floor.
- 0054-X18 Web mode with no login on a published port (A3) - rejected by its file: CLAUDE.md keeps 127.0.0.1 and the per-start token.
- 0055-X1 Run on an overlay platform (Overwolf or similar) for in-game windows - rejected by its file; outside the floor: Injected overlay forbidden by the floor; platform model is ad-funded and from 2026-11-01 Overwolf approves only monetized apps (revenue on GGG-derived features); against decision 0002.
- 0055-X2 Hide the overlay while the game is alt-tabbed - rejected by its file; against a settled decision: Needs a foreground-window or process query; decision 0029 settles on Client.txt staleness; overlay is click-through so staying visible costs little; pattern UNVERIFIED in OW-BP / OP-SETUP.
- 0055-X3 Exclusive or interactive overlay mode (OW-OVL) - rejected by its file: Takes keyboard and mouse and needs focus; against non-focusable click-through rule and design 0001 principle 3.
- 0055-X4 Auto-import of builds or settings into the game (BLITZ) - rejected by its file; outside the floor: Writing game files or sending input is outside the floor; decisions 0031 and 0034 keep downloads.
- 0055-X5 Parser-style combat meters - rejected by its file; outside the floor: PoE2 has no add-on API; ACT-class parsers read network or memory (floor); Client.txt carries no combat numbers.
- 0055-X6 User-scripted triggers in the WeakAuras style - rejected by its file: Runs pasted code, widens local attack surface (notes 0045, 0046), adds settings; fixed context table (design 0001 s7.2) covers the need.
- 0055-X7 Shift-light style urgency (flashing or animated colour) - rejected by its file: Against WCAG 2.3.1 and design 0001 section 10.
- 0055-X8 Sound cues for trades or deaths - rejected by its file: Design 0001 principle 3 'no sound' (a principle, not a settled decision; operator could reopen; no evidence here).
- 0055-X9 Screen or clipboard watcher to show cards without a press - rejected by its file; outside the floor: Floor allows one read per manual press only (decision 0003).
- 0055-X10 Notification Center or Windows toast history as the long look (MS-NOTIF) - rejected by its file: Dashboard is the long look; a toast in play breaks R6 and design 0001 s7.1.
- P01-X1 R-1 Desktop-control tool grant to a lane to click Login / character select (ROADMAP.md:54) - rejected by its file; outside the floor: Synthesizes input to the game client; floor 'NEVER send input to the game'. TEST-LIVE-CLICKS closes from normal play.
- P01-X2 R-2 Reading the game's FPS from outside (PresentMon, ETW, frame hook, screen capture of the counter) - rejected by its file; against a settled decision: Decision 0006 and the floor bar them; OVL-FPS stays a player reading.
- P01-X3 R-3 Persisting raw unknown Client.txt lines for LIVE-1 - rejected by its file: N51 rejects it too; only masked shapes, no chat text or names kept.
- P01-X4 R-4 Timer or watcher reading the clipboard for LIVE-WAYSTONE - rejected by its file; against a settled decision: Per-press only (decision 0003).

## Research gaps

- 0057 (high): Full history was scanned with 24 local needles that do not hold the names of the third-party set reviewed in note 0056; history holds the 0056 draft. Action: F-004 runs the scan with the set's names as local-only needles before any push; Q-25 applies only on a hit.
- 0053 (medium): The embeddable CPython runtime is proven only on --check and module imports; no core, supervisor or calc bridge has run under it. Action: F-038 runs them in a scratch folder on a fixture log before F-047 is built.
- 0053 / 0046 (medium): Electron fuses end with no recommendation in either note. Action: Resolved in Conflicts (no flip on the unmodified pinned exe; environment and switch guards instead); plan 05 records it.
- 0041 (medium): 0041, 0055, 0044 and 0040 use different size metrics and overlay recipes and do not cite each other. Action: Resolved in Conflicts; plan 03 states the one metric and reference setup, and F-066 plus F-144 hold the result. The two-column check at 900x560 that 0055 asked of 0041 is added to F-066.
- 0043 (medium): No-scroll is shown for states c and d only; state g (web data on, item card) and the four Play additions are fitted by arithmetic. Action: F-066 covers state g and is re-run by each addition when built.
- 0047 / 0058 (medium): Two incompatible ROADMAP mechanics (id grammar, hand-off, new rows, dependencies). Action: Resolved in Conflicts (F-024, F-029).
- 0056 (medium): Only 7 of 39 repositories were deep-reviewed; the other 32 have no triage breakdown and the set size and idea count are unverified. Action: One bounded research row after wave 1: a neutral triage table from the review data in the sidecar scratch (class, count, data path class, why skipped) and a deep review of any floor-safe, relevant repository skipped only by the cap; results as an addendum to note 0056. Does not block the plan.
- 0055 (medium): No 'Adopted patterns' register (pattern, where it goes, source, access date) as the brief requires. Action: Add the register to note 0055 when it is next touched (docs-only row); sources are already cited per recommendation.
- 0044 (medium): The WCAG verdict rests on a focus walk and contrast probe of Play only; other tabs, light theme, open folds and client zoom are unverified. Action: F-121 extends the probe to every tab in both themes; F-145 runs the hidden Electron probe.
- 0052 (medium): 0052 R6 / R7 conflict with 0053, 0057 and 0058 on update consent, who builds the published artifact and the changelog generator. Action: Resolved in Conflicts (F-077, F-074, F-076, F-101); consent is Q-21.
- 0049 (low): 24 of 37 recorded xdist loop-gate runs were red and the cause is unknown. Action: First step of F-089: three diagnosed parallel runs through the suite gate with full output kept; the result decides Q-16.
- 0047 (low): Whether merge=union applies during rebase is unverified. Action: First step of F-017: a scratch-repository check with rebase and cherry-pick.
- 0050 (low): The X1 experiment numbers (24 MB replay, dead listener, unretried history write) were not re-run by the verifier. Action: They become the regression tests of F-015 and F-014 on fixture logs.
- 0045 (low): The overlay's Sec-Fetch-Site value in Electron 45 and Windows PowerShell 5.1 proxy behaviour for 127.0.0.1 are unverified. Action: One probe each as the first step of F-003 and F-012.
- 0053 (low): The per-user uninstall key is undocumented by the vendor; scoop was not checked against the home layout. Action: The sandbox phases of F-074 verify the key on Windows 10 and 11; F-210 is deferred.
- 0039 (low): Four notes each add a hotkey with no total. Action: Resolved in Conflicts (hotkey budget of two default keys).

## Coverage

Per source: recommendations, how many became findings, how many were not adopted; and the source's own rejected ideas (all not adopted).

- 0035: 7 recs = 7 in findings + 0 not adopted; 9 rejected ideas not adopted
- 0036: 12 recs = 12 in findings + 0 not adopted; 8 rejected ideas not adopted
- 0037: 12 recs = 12 in findings + 0 not adopted; 9 rejected ideas not adopted
- 0038: 9 recs = 9 in findings + 0 not adopted; 11 rejected ideas not adopted
- 0039: 13 recs = 12 in findings + 1 not adopted; 9 rejected ideas not adopted
- 0040: 8 recs = 8 in findings + 0 not adopted; 9 rejected ideas not adopted
- 0041: 9 recs = 9 in findings + 0 not adopted; 7 rejected ideas not adopted
- 0042: 12 recs = 12 in findings + 0 not adopted; 9 rejected ideas not adopted
- 0043: 7 recs = 7 in findings + 0 not adopted; 9 rejected ideas not adopted
- 0044: 12 recs = 12 in findings + 0 not adopted; 4 rejected ideas not adopted
- 0045: 11 recs = 11 in findings + 0 not adopted; 8 rejected ideas not adopted
- 0046: 11 recs = 11 in findings + 0 not adopted; 10 rejected ideas not adopted
- 0047: 10 recs = 10 in findings + 0 not adopted; 5 rejected ideas not adopted
- 0048: 12 recs = 12 in findings + 0 not adopted; 7 rejected ideas not adopted
- 0049: 12 recs = 12 in findings + 0 not adopted; 8 rejected ideas not adopted
- 0050: 13 recs = 13 in findings + 0 not adopted; 10 rejected ideas not adopted
- 0051: 10 recs = 10 in findings + 0 not adopted; 9 rejected ideas not adopted
- 0052: 7 recs = 7 in findings + 0 not adopted; 6 rejected ideas not adopted
- 0053: 11 recs = 11 in findings + 0 not adopted; 9 rejected ideas not adopted
- 0054: 8 recs = 8 in findings + 0 not adopted; 18 rejected ideas not adopted
- 0055: 8 recs = 8 in findings + 0 not adopted; 10 rejected ideas not adopted
- 0056: 12 recs = 12 in findings + 0 not adopted; 8 rejected ideas not adopted
- 0057: 13 recs = 13 in findings + 0 not adopted; 6 rejected ideas not adopted
- 0058: 12 recs = 12 in findings + 0 not adopted; 11 rejected ideas not adopted
- P01: 63 recs = 59 in findings + 4 not adopted; 4 rejected ideas not adopted

- Totals: 314 recs = 309 in findings + 5 not adopted; 213 rejected ideas; 527 ids in all; 214 findings; 218 not-adopted entries.
- Sources that are not recommendation ids (a finding without a recommendation, a critic gap): 0054-F2, CRITIC-GAP-08, CRITIC-GAP-09.
- Questions: 146 in the sources = 57 cited by the 28 open decisions + 89 folded.
- Coverage check: PASS (an independent script over the eight extraction files and findings.json: each of the 527 ids appears exactly once; no rejected idea sits in a finding; fids unique, ranks 1 to 214, every depends-on id exists; each of the 146 source questions is either cited by an open decision or folded, never both).
