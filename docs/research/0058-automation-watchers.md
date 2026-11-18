# 0058 - No-reminder automation and upstream watchers

Date: 2026-11-18. For the ultraplan (docs/plan/README.md), dimension G
no-reminder automation and upstream watchers. Scope: the exact contracts of
what already runs unattended (loop tick, lanes, docs watch, TC-DRIFT, price
refresh, scheduled task), then the missing set: upstream watchers, docs,
screenshot and changelog refresh, the PoE2 1.0 trigger, and how the loop and
the session-run waves share ROADMAP.md. Watcher inputs come from notes 0035,
0036, 0037, 0046 and 0052; this note owns the shared frame.
Status: draft

## Sources (all accessed 2026-11-18)

Web:
- GH-SCHED: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
  (the schedule event)
- GH-BILL: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- GH-PERM: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
  (permissions keys)
- GH-CL: https://github.blog/changelog/2026-09-03-github-actions-early-september-2026-updates
- GH-RATE: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- GH-COND: https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
- GH-WF: https://docs.github.com/en/rest/actions/workflows
- GH-DIS: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows
- GH-ISS: https://docs.github.com/en/rest/issues/issues
- GH-REL: https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes
- GH-DBS: https://docs.github.com/en/code-security/dependabot/dependabot-security-updates/about-dependabot-security-updates
- KAC: https://keepachangelog.com/en/1.1.0/
- GGG-ROB: https://www.pathofexile.com/robots.txt
- GGG-PN: https://www.pathofexile.com/forum/view-forum/2212 (one read of the
  public board index)
- STEAM: https://partner.steamgames.com/doc/webapi/ISteamNews

Local evidence:
- EVID: the evidence-pack README and capture scripts under
  `<sidecar>\Scratch\up-evidence\` (README.txt lines 7-56: the live-log
  incident, the in-process isolated Core, the windowless DevTools capture)

Sibling notes of this ultraplan (drafts at HEAD, cited as N<number>):
- N35 docs/research/0035-data-sources-ggg-api.md (R3 docs watch topic)
- N36 docs/research/0036-data-sources-poe-ninja.md (R4, R6, shape watch)
- N37 docs/research/0037-data-sources-pob-repoe-tree.md (F2, F10, F14, R2,
  R5 with W1-W8, R8 to R10)
- N46 docs/research/0046-security-electron-supply-chain.md (F1, R1, R9)
- N52 docs/research/0052-deployment-reference-pattern.md (R2, R3, R7)

Local reads, read-only, 2026-11-18 00:01 to 00:20 local:
- L-GATE: `python tools/usage_ledger.py gate` and `spend`
- L-TASK: `python tools/loop_task.py status`
- L-DRIFT: `python tools/tc_drift.py status`; L-DOCS:
  `python tools/ggg_docs_watch.py status`
- L-USE: ops/loop/control/headless_usage.jsonl (87 rows) and the 22 records
  under ops/loop/control/loop_items/, summarised by throwaway scripts
- L-PARSE: ROADMAP.md, AL-NEXT-SESSION.txt and candidate row texts run
  through the loop's own `roadmap_rows`, `handoff_items`, `ROW_RX`,
  `BLOCKED_RX`, `flip_roadmap` and `plan_depends` (scripts under
  `<sidecar>\Scratch\up-0058\`, nothing written to the repo)

Repo files read: tools/al_loop.py, loop_base.py, loop_roadmap.py,
loop_merge.py, loop_prompts.py, loop_inbox.py, al_lane.py, loop_task.py,
ggg_docs_watch.py, tc_drift.py, usage_ledger.py, make_icons.py;
server/al/ninja.py, webfetch.py, diag.py, theorycraft/snapshot.py;
scripts/brand_render.js; tests/test_floor_static.py, test_dash_console.py,
test_audit_batch4.py; ops/loop/gates.txt; .githooks/; decisions 0009, 0013,
0025, 0026, 0044; research 0029; docs/ops/1.0-launch-runbook.md.

## Summary

- The loop is a sound base: one scheduled task, one tick, plain-Python
  watchers that cost 0 headless runs. Two watchers exist (GGG docs, PoB
  release); nothing watches Electron, repoe-fork, the tree export, poe.ninja
  shapes, the docs or the calendar.
- Three defects would waste runs or hide work the moment HALT is removed:
  9 of 15 hand-off bullets become lane work (4 duplicate open rows), a row
  id with a dot is invisible (UTIL-1.0-POST is one), and an item whose
  gates fail drops out of the checklist. Fix these first (R1).
- Nothing unblocks a row. Every BLOCKED row waits for a human edit, and
  the 1.0 launch (2026-12-11) has no trigger at all.
- Design: one stdlib watcher frame with typed findings (R2); two
  ROADMAP-only primitives, append a row and flip a gate row, committed by
  the tick itself under the merge lock (needs a decision); row text built
  only from tracked templates and validated tokens.
- Homes: player needs stay in the app under the web-data opt-in; GGG-host
  reads stay on the dev loop (decision 0044); everything hosted on GitHub
  or a public registry moves to one scheduled CI job once the repository is
  public, with the dev loop as failover.
- Screenshots need a supported demo mode first: the entry point always
  reads the per-host config and a missing log falls back to the live one
  (F17, R8 a).
- Cost: watchers 0 runs; a filed row 2 runs when clean, 8 at worst; a cap
  of 3 filed rows per day bounds watcher-caused work at 24 of 120 runs.
- Interplay: session-owned rows carry `BLOCKED: session wave <n>`; HALT
  comes off only after six listed checks (R5).

## Current state

### What runs unattended today

- U1 Scheduled task `\AshLightOps\LaneLoop`: `tools/al_loop.py tick` every
  15 minutes, a new start ignored while one runs, 6 h limit, interactive
  token, no wake, missed starts run when possible, priority 7
  (tools/loop_task.py:26-28, :75-95). Read back: exists, Ready, last result
  0 [L-TASK]. It runs only while the operator is logged on.
- U2 The tick (tools/al_loop.py:1543-1559, :1457-1505), in order: GGG docs
  watch; HALT check; tick lock; hooks-path check; usage backfill; reap lost
  dispatches; daily ledger rotation; TC-DRIFT; stall flags; inbox (free
  classify, then at most one triage run); review workers for finished
  lanes; conflict upkeep; work list; dispatch; idle deep-dive; push worker;
  checklist and status files. Target under 60 s (tools/loop_base.py:37).
- U3 GGG docs watch (decision 0044): six developer-docs pages once per 24 h,
  3 h after a network error, a 429 or 503 obeyed; main-text hash, diff to
  the sidecar Logs, flag `ops/runtime/ggg_docs/REG_OPEN`
  (tools/ggg_docs_watch.py:45-56, :335-344). It runs before the HALT return
  (tools/al_loop.py:1547-1551). Read back: 6 of 6 pages, registration
  closed, newest changelog entry 3.30.0 [L-DOCS].
- U4 TC-DRIFT (decision 0025): one releases read per 24 h, a detached
  static trial per new tag, the pin moves only by `apply` after a
  live-green trial (tools/tc_drift.py:57-61, :273-297, :459-479). It sits
  inside the tick body (tools/al_loop.py:1471). Read back: v0.23.1 current,
  last checked 2026-11-17 10:03 [L-DRIFT].
- U5 Idle deep-dive: one research lane per day when nothing is open or in
  flight, weekly after 3 dives that proposed no row; at most 2 new rows a
  day (tools/al_loop.py:1264-1279, :1489-1498; tools/loop_roadmap.py:334-348;
  tools/loop_base.py:62). The only item kind with web tools
  (tools/al_loop.py:1600; tools/loop_base.py:133-134).
- U6 In the shipped app, under the web-data opt-in (decisions 0013, 0026):
  poe.ninja prices at most hourly with ETag, league re-read every 6 h or
  after a 404 (server/al/ninja.py:56-58). A refresh starts only from
  `GET /api/rates` or the opt-in switch (server/al/http.py:287-290;
  server/al/core.py:593-595). The game-data snapshot refreshes only in
  scripts/build.ps1, 24 h gate (server/al/theorycraft/snapshot.py:6-7, :57).
- U7 Policy wording watch: not automated. It is a hand-run record with a
  shape test; its 2026-12-11 line reads PENDING and its one lane run had no
  web access (docs/research/0029-policy-wording-watch.md:59, :68-70).
- U8 Push: a no-op, there is no remote (tools/al_loop.py:1282-1297;
  .githooks/pre-push:22-24). There is no `.github` folder and no CI.

### Contract: how a row is selected

- Work sources, in this order (tools/al_loop.py:1081-1148): kept commits
  that need a resolve run; inbox ORDER / FIX / RULING notes; open ROADMAP
  rows, `(priority)` rows first, then file order (:1091-1093); bullets
  under "Carried forward" in the hand-off file (:1142-1147).
- Row syntax (tools/loop_base.py:104-112):
  `- [ ] ID (lane) title. ACCEPT: ...`, continuation lines indented two or
  more spaces. ID is three digits, or upper-case letters and digits joined
  by `-`, first character a letter. The first row of an id wins
  (tools/loop_roadmap.py:41-43).
- Lane field: `(build)`, `(data)` or `(review)` right after the ID. It is a
  preference: the row takes that lane when free, else the first free one
  (tools/al_loop.py:1225). `(data)` routes to sonnet, the rest to opus
  (tools/loop_base.py:70-80, :266-273).
- BLOCKED: a row whose text holds the upper-case word BLOCKED is listed and
  never dispatched (tools/loop_base.py:125; tools/al_loop.py:1125-1128).
- Depends: the first `Depends on:` line of `docs/plans/<ID>-*.md` names row
  ids; the row waits while any of them is an open row; an id with no row is
  ignored (tools/loop_roadmap.py:72-89; tools/al_loop.py:907-920,
  :1129-1134). No such file exists today.
- A record is dispatchable when new, paused, refused or lost under 2
  attempts, blocked with its needs closed, or in conflict with a kept
  commit under 2 resolve runs (tools/loop_roadmap.py:318-330).
- Lanes: 3 names, the machine lane cap, each run in its own worktree; a
  dirty or held worktree stops the claim (tools/al_lane.py:46, :85-89;
  tools/al_loop.py:1160-1188).

### Contract: how a row is marked done

- A lane never commits and never edits ROADMAP.md, CLAUDE.md or the
  hand-off (tools/loop_prompts.py:36-37, :50-51).
- A detached review worker runs the gates of ops/loop/gates.txt (whole
  suite through the suite gate, npm test, leak sweep), then a verifier, with
  up to 3 fix rounds (tools/loop_base.py:60; tools/al_loop.py:749-826).
- On PASS: commit in the lane worktree, `merge --no-ff` into main under
  merge.lock; inside that merge commit the row flips to `[x]` and
  ` -- done <date> (loop; refute r/3 PASS)` is appended to its first line
  (tools/loop_merge.py:104-129; tools/loop_roadmap.py:60-69). Only plan
  rows flip (tools/loop_merge.py:108). The merge needs main checked out and
  clean (tools/loop_merge.py:92-95).
- Gates still red after 3 rounds: state `failed`, work kept as an unmerged
  commit; no verifier PASS: state `adjudicate`, parked for a session
  (tools/al_loop.py:1007-1011). Done rows are pruned at /done
  (ROADMAP.md:5).

### Contract: runs cap, HALT

- Cap: 120 headless runs per rolling 24 h per tree; the machine config may
  set 1 to 500 (ops/fleet_kit/fleet_headless.py:422-424, :3044-3052). The
  loop counts the larger of the budget file and the usage log and stops
  spawning at cap minus 3 (tools/usage_ledger.py:107-156;
  tools/al_loop.py:490-501; tools/loop_base.py:57). Read back: used 85, cap
  120 [L-GATE].
- HALT: while `ops/loop/control/HALT` exists the tick writes status
  `halted` and returns before the lock (tools/al_loop.py:1549-1551), a lane
  worker pauses (:1592-1594) and the kit refuses a spawn. Present since
  2026-11-17 17:43 (operator wind-down).

## Findings

- F1 A row id with a dot is invisible. `ROW_RX` wants whitespace after the
  id, so `UTIL-1.0-POST` matches nothing (ROADMAP.md:530). 5 of 156
  row-like bullets fail to parse, 2 of them open; one id is used twice
  (AUDIT-TC-WIRE, ROADMAP.md:1797 and :1836) [L-PARSE]. The loop will never
  list, dispatch or flip the 1.0 row, whatever its text says.
- F2 The hand-off file is a second work list with no BLOCKED check. 9 of
  its 15 bullets are dispatchable today: 4 restate open rows the loop will
  also take (two lanes on one task), 3 restate blocked work, among them
  "UTIL-1.0-POST: BLOCKED until PoE2 1.0 launch", 1 is a kit note for MAIN,
  1 says the loop is paused [L-PARSE]. Only 3 tag patterns skip a bullet
  (tools/loop_base.py:119-122). Each costs at least one opus run.
- F3 A failed item disappears. `failed` counts as done for the checklist
  (tools/loop_base.py:85; tools/al_loop.py:1386-1391) and the parked list
  holds only `adjudicate` (tools/loop_inbox.py:388-392). 12 of 22 items of
  the armed day ended there [L-USE]. Their rows stayed open with no line
  anywhere, and their commits have no keep ref.
- F4 Fix rounds were spent on failures no lane can fix. On the armed day
  (87 runs in 15.8 h) 39 were fix runs and 36 of those went to the 12
  failed items. 7 items name a test tied to live processes on the host
  (tests/test_procs.py); 4 name the test that wants every decision listed
  in CLAUDE.md, a file a lane may not edit (tests/test_audit_batch4.py:33-42;
  tools/loop_prompts.py:36-37) [L-USE]. So a filed row that adds a decision
  cannot merge unattended.
- F5 HALT blinds TC-DRIFT but not the docs watch
  (tools/al_loop.py:1471 against :1547; N37 F2). HALT stays for the
  ultraplan, through the weeks before 1.0.
- F6 Nothing unblocks a row. 8 of 12 open rows carry BLOCKED [L-PARSE]; the
  only way out is a human edit. The registration alert depends on a
  paragraph each /done must carry forward (AL-NEXT-SESSION.txt:13-15); the
  1.0 work and the policy re-read depend on someone remembering a date.
- F7 A ROADMAP row cannot be given web access. Only the deep-dive kind has
  it, and that kind runs only when the loop is idle (U5). A row that says
  "read the patch notes" runs blind.
- F8 CI cannot help yet: no remote, no workflow, and the fallback gate
  source the loop names does not exist (tools/al_loop.py:202-206; U8).
  Every watcher needs a dev-loop driver first.
- F9 One address, one quota. Anonymous API reads are capped at 60 per hour
  per address [GH-RATE]; the dev host shares that with every other tool on
  it (N37 F8). In CI the automatic token gets 1,000 per hour per repository
  and a 304 is free only with authentication [GH-RATE, GH-COND].
- F10 Docs drift is unguarded. The Electron pin is quoted in 6 tracked
  files, CLAUDE.md:300 among them, and no test binds them; the decisions
  index lists 8 of 44 files; the version lives in two unlinked strings
  (N52 F4). A lane may not edit CLAUDE.md, so the first unattended bump
  leaves it wrong.
- F11 A screenshot pipeline is nine tenths present. tests/test_dash_console.py
  already starts a real core on a test port with a synthetic session, a mock
  price source, a loaded build and three item checks, and drives a headless
  browser at three widths (:1-12, :61-128). scripts/brand_render.js captures
  an own offscreen page (:35-44) under an allow-list entry
  (tests/test_floor_static.py:94-98). The README shows a drawn hero and no
  screenshot of the product (README.md:3-6).
- F12 No changelog, no tag. GitHub's generated notes list merged pull
  requests [GH-REL]; this repository merges locally, so they would be
  empty. On main's first-parent line 80 of 169 subjects are `merge:` with
  the row id in the scope and 58 follow no convention. A changelog should
  not be a commit dump anyway [KAC].
- F13 Three notes each propose a new watcher tool (N36 R6, N37 R5, N46 R1).
  Three tools mean three state files, three tick hooks and three ways to
  fail silently.
- F14 Row text is a prompt. A row's text is pasted into the lane prompt
  (tools/loop_prompts.py:54-62). Text taken from an upstream commit title,
  a release note or a public issue would let a stranger steer a lane that
  can edit files.
- F15 Traps for whoever writes rows: `docs/plans/` (row briefs) is one
  letter from `docs/plan/` (this plan); the brief glob lets row `A-B` read
  `A-B-C-x.md` (tools/loop_roadmap.py:86); an unknown dependency id is
  ignored, so a typo runs the row early.
- F16 What a row costs. Clean: 2 runs (lane, verifier). Each fix round
  adds 2, up to 8. Measured: lane median 280 s and 1.79 USD, verifier and
  fix 0.14 to 0.15 USD, 67.78 USD in the first two days [L-USE, L-GATE].
- F17 The product cannot start as an isolated demo. `python -m server.al`
  reads config/local.json for its port (server/al/__main__.py:152-153;
  server/al/paths.py:165-170) and builds its Core with no runtime or config
  override (server/al/__main__.py:157), so it inherits the operator's web
  data setting, log path and consent. Worse, a missing log path falls back
  to the Steam scan (server/al/core.py:608-609; server/al/logfile.py:144-152):
  this session's evidence capture once tailed the live Client.txt for about
  20 s that way [EVID]. The working approach builds the Core in-process the
  tests' way (runtime, config path and fetcher inside a scratch folder),
  pins log discovery, and drives headless Chrome over the DevTools protocol
  with no npm package [EVID]. A supported demo mode is therefore a
  prerequisite of any unattended screenshot job; a throwaway script that
  monkey-patches discovery is not something the loop may run.

## Recommendations

Ranked, best first. Row names are proposals. A watcher is always plain
Python; a model run happens only when a filed row is dispatched.

- R1 LOOP-PREFLIGHT. Action: before HALT is removed, (a) a hand-off bullet
  is loop work only when it starts with `LOOP:`; (b) a test fails on any
  row-like ROADMAP bullet that does not parse or repeats an id, and the 1.0
  rows are renamed (`UTIL-10-...`); (c) `failed` leaves the done states,
  shows in the checklist and the parked list, and its commit gets a keep
  ref; (d) a gate failure that names only tests outside the lane's diff
  ends the fix rounds at once; (e) `al_loop.py preflight` runs the gates
  once in a lane worktree on unchanged main. Impact: H; today's defects
  would spend about 9 opus runs on duplicates and repeat the 36 wasted fix
  runs. Effort: M. Risk: low; (d) could end a round early on a real
  cross-file break, so the item is parked visibly, not dropped. ToS check:
  no floor rule touched; dev tooling only. Depends on: nothing. Files
  likely touched: tools/loop_base.py, loop_roadmap.py, al_loop.py,
  loop_inbox.py, tests/test_al_loop.py, ROADMAP.md, AL-NEXT-SESSION.txt.
  Acceptance test: `handoff_items` on the live hand-off yields 0 work
  items; the lint test fails on a dotted id; a failed fixture item prints a
  checklist line; preflight exits 0 with the client running. ZERO-CLICK:
  nothing for the player; the operator never has to notice a stall.
- R2 WATCH-CORE. Action: one stdlib tool `tools/upstream_watch.py` with a
  registry of sources (catalogue below), state in
  `ops/runtime/watch/state.json`, at most one due source per tick, called
  before the HALT return; TC-DRIFT's check and the docs watch become
  sources of it. Each source returns typed findings (name, key, validated
  tokens). The tick turns a finding into a ROADMAP change with two
  primitives, append a row from a tracked template and flip a gate row
  with `flip_roadmap`, committed as a ROADMAP-only commit under merge.lock
  and the kit git lock, only when ROADMAP.md is unmodified and HALT is
  absent; at most 3 filed rows per local day. Impact: H; every later
  watcher is a 30-line source. Effort: M. Risk: an unattended commit on
  main; bounded by the diff check (added lines parse as rows, one flipped
  gate, nothing removed), the hooks and the daily cap. ToS check: touches
  "public web data" and "truthful User-Agent": every read is a public page,
  file or documented API through server/al/webfetch.py with the AshLight
  User-Agent, no cookie; dev tooling, never the player's core (decisions
  0025, 0044 item 7). Depends on: R1; a decision for the commit path (open
  question 1). Files likely touched: tools/upstream_watch.py (new),
  tools/al_loop.py, tc_drift.py, ggg_docs_watch.py, a tracked template
  table, tests. Acceptance test: fake fetches drive each source; a finding
  with a token that fails its pattern files nothing; a fourth row in one
  day waits; a HALTed tick records the finding and commits nothing.
  ZERO-CLICK: fully unattended.
- R3 LAUNCH-GATE (before 2026-12-10). Action: the plan lands three parseable
  rows and one gate row (templates below). The launch source flips
  `GATE-POE2-10` when the local date is 2026-12-11 or later and the
  repoe-fork data repository or the GGG tree export shows a version of 1.0
  or higher that is not a preview (N37 W6, W7, F14). Dependents then run:
  `UTIL-10-DATA` (runbook steps 4, 6, 7, 8), `UTIL-10-NOTES` (step 1 and
  the policy re-read, as a requested dive, R11). `UTIL-10-LOG` (steps 2, 3,
  5) stays an operator act until the first 1.0 session exists. Three days
  past the date with no signal files `LAUNCH-CHECK-<date>`. Cadence: daily,
  every 12 h from 2026-12-05 to 2026-12-24. Impact: H; the launch is the
  one dated event in the plan. Effort: S after R2. Risk: a slipped launch
  (the two-signal rule) or a preview tree read as live (the preview
  filter). ToS check: "GGG endpoints only if in the API Reference or Data
  Exports": the tree export is GGG's listed data export, read from its
  public repository; repoe-fork is public repository metadata; no game
  system, no trade site. Depends on: R1, R2; N37 R6 for the preview hazard.
  Files likely touched: tools/upstream_watch.py, ROADMAP.md, docs/plans/,
  docs/ops/1.0-launch-runbook.md, tests. Acceptance test: a clock at
  2026-12-10 flips nothing; 2026-12-11 with a fixture version 1.0.0 flips
  the gate once and the dependents turn dispatchable; a "Preview" title
  flips nothing. ZERO-CLICK: unattended, bar the operator's own play
  session, which the floor requires of a log read.
- R4 POLICY-QUOTES. Action: add the 12 baseline quotes of research 0029 as
  a check inside the docs watch: each must appear in the index page text.
  A missing quote writes the flag `ops/runtime/ggg_docs/POLICY_CHANGED`, a
  Checks note on the dev host and a `(review)` row carrying
  `BLOCKED: session`; a new changelog entry or the launch gate asks for a
  re-read. The 0029 log gets its line from the tool. Impact: H; the floor
  itself rests on this wording. Effort: S. Risk: a reflow of the page reads
  as a change; compare on whitespace-normalised text. ToS check: the same
  six pages, cadence and identity as decision 0044; no new request. The
  floor is never edited by the tool (research 0029 floor rule). Depends on:
  nothing. Files likely touched: tools/ggg_docs_watch.py, server/al/diag.py,
  tests/test_ggg_docs_watch.py, tests/test_policy_wording_watch.py.
  Acceptance test: a fixture page missing quote O3 raises the flag and
  names O3; the real cached page raises nothing. ZERO-CLICK: unattended.
- R5 WAVE-INTERPLAY. Action: adopt the contract in "Loop and waves" below:
  BLOCKED becomes "not for the loop" with a reason the checklist echoes;
  the plan tags every session row; HALT is removed only when the six
  checks pass. Impact: H; it is what stops two workers on one row.
  Effort: S. Risk: a wave that ends early leaves rows tagged; they stay
  listed as blocked on every tick, so nothing is lost. ToS check: no floor
  rule touched. Depends on: R1. Files likely touched: tools/al_loop.py (one
  reason string), ROADMAP.md, docs/plan/07-execution-plan.md,
  docs/plan/08-orchestration.md. Acceptance test: a dry-run tick on the
  landed ROADMAP lists only loop rows as "would dispatch". ZERO-CLICK: no
  operator step; the session that ends a wave flips its rows.
- R6 DOCS-FRESH. Action: `tools/docs_fresh.py` holds a table of facts, each
  computed from the tree and matched in named docs: Electron pin, version,
  Python and Node floors, port block, hotkeys, budget numbers, settings
  keys, kit version, and "every decision and research file has an index
  line". `check` runs as a test, so drift cannot merge. CLAUDE.md stops
  quoting values (it names the file that holds the pin). A second mode
  lists dated markers (PENDING, UNVERIFIED with a date) older than 30 days;
  the tick runs it daily and files at most one `DOCS-FRESH-<date>` row a
  week. Impact: M-H. Effort: M. Risk: a brittle pattern blocks a merge; each
  fact has a fixture test. ToS check: none touched; it keeps the README's
  required statement and descriptive wording under test (branding rules).
  Depends on: N52 R2 for the version. Files likely touched:
  tools/docs_fresh.py, tests/test_docs_fresh.py, README.md, CLAUDE.md (a
  session), docs/decisions/README.md. Acceptance test: changing the pin in
  app/package.json alone fails the test and names each stale file.
  ZERO-CLICK: unattended.
- R7 CI-WATCH (when the remote exists). Action: one scheduled workflow runs
  `upstream_watch.py ci` daily, off the hour, on a standard runner with
  `contents: read`, `issues: write`, `vulnerability-alerts: read`. It
  compares upstream with the tracked pins and a tracked baseline file,
  opens one labelled issue per finding (a key line, never row text) and
  closes it when the finding is gone. It never commits. The tick reads the
  labelled issues once per 6 h, accepts a key only from the workflow's
  account and its strict pattern, and files the row from its own template.
  Dependabot alerts enter the same way. The tick also reads the workflow
  state daily and runs the CI sources itself when it is not active or 48 h
  silent. Impact: M-H; watching continues with the dev host off and uses
  the larger quota. Effort: M. Risk: scheduled runs can be late or dropped
  and stop after 60 days without repository activity [GH-SCHED, GH-DIS];
  the failover covers both. ToS check: "public web data", "truthful
  User-Agent": the job reads GitHub and public registries only, never a GGG
  host, and names AshLight, its version and the repository address taken
  from the runner. FLEET item 17: no bot commit, no bot pull request.
  Depends on: R2; the remote (operator act, ROADMAP.md:2059-2061); N46 R9.
  Files likely touched: a workflow file, tools/upstream_watch.py,
  tools/al_loop.py, tests. Acceptance test: a recorded issue list with one
  valid key and one forged issue files exactly one row; a workflow state of
  `disabled_inactivity` switches the tick to failover. ZERO-CLICK:
  unattended; standard runners cost nothing on a public repository
  [GH-BILL].
- R8 SHOTS. Action: first (a) DEMO-MODE: `python -m server.al --demo
  <fixture dir>` builds the Core with runtime, config and fetcher inside a
  scratch folder, ignores config/local.json, disables the Steam scan
  outright (a missing demo log is an error, never a discovery), forces web
  data off or onto a loopback mock, and exits 97 if any open log lies
  outside the fixture folder (F17); then (b) `tools/shots.py render` starts
  that demo core on a test port, loads the fixture session, and
  saves PNGs of each tab (dark and light, 1440 and 360 wide) and of the
  overlay page on a plain ground, through the headless browser; a manifest
  records the hash of the UI sources and the fixture. `check` compares
  that hash. The tool refuses any core it did not start. Rows:
  `SHOTS-<date>` when the hash is stale at a release-prep. Impact: M; the
  README finally shows the product. Effort: M. Risk: running timers make
  pixels differ; staleness is judged on the input hash. ToS check: "screen
  only once per manual press" and "no GGG art": the capture is of
  AshLight's own page inside a headless browser, never the screen, the
  game or a game image; the fixture holds invented names only. The floor
  scan gains the protocol's screenshot call as a banned word with one
  allow entry. Depends on: (a) before (b); the lane tool list gains the
  script; the scratch capture scripts [EVID] are the reference, not code to
  copy blind. Files likely touched: server/al/__main__.py, core.py,
  logfile.py, tools/shots.py, app/test/cdp/ (new script), docs/shots/,
  README.md, tests/test_floor_static.py, tests/test_demo_mode.py,
  tools/al_lane.py. Acceptance test: a demo start with a missing fixture
  log exits non-zero and opens no file outside the fixture folder (checked
  with a planted Steam root holding a decoy Client.txt); two renders give
  the same manifest; a planted second capture call fails the floor scan;
  no window appears. ZERO-CLICK:
  unattended, hidden, below-normal priority.
- R9 REL-NOTES. Action: `tools/release.py notes` (N52 R2, R3) drafts a
  version's notes from the first-parent `merge:` subjects since the last
  tag, joined to their row titles, grouped Added / Changed / Fixed [KAC],
  `(data)` rows under Changed. Each wave ends with a pre-filed
  `REL-PREP-<n>` row that depends on the wave's rows: its lane curates the
  draft, runs R6 and R8. A session commit-msg check holds subjects to the
  same types. The tag and the publish stay the operator's one phrase (N52
  R7). Impact: M. Effort: S. Risk: a noisy draft; the lane edits it. ToS
  check: branding rules: notes carry the not-affiliated statement and no
  GGG art. Depends on: R1, R6, R8, N52 R2. Files likely touched:
  tools/release.py, .githooks/commit-msg, tests. Acceptance test: a fixture
  history of 3 merges yields 3 grouped lines; a subject without a type is
  refused. ZERO-CLICK: prepared unattended; one operator phrase per release
  by the operator's own order (AL-NEXT-SESSION.txt:104).
- R10 WATCH-HEALTH. Action: every source records `last_ok`; 3 failures in
  a row add one tick line; 7 days of failure file `WATCH-BROKEN-<NAME>`.
  The halted tick writes pending findings into its checklist instead of an
  empty list. On the dev host the Checks view gains one note when the last
  tick is older than 2 h. Impact: M. Effort: S. Risk: none. ToS check: none
  touched; the note reads AshLight's own status file, never a process list
  (decision 0029). Depends on: R2. Files likely touched:
  tools/upstream_watch.py, tools/al_loop.py, server/al/diag.py, tests.
  Acceptance test: a source failing since 8 days yields one row, once.
  ZERO-CLICK: unattended.
- R11 DIVE-ON-DEMAND. Action: a source may write
  `ops/loop/control/dive_request.json` (topic key and validated URLs); the
  tick then dispatches the deep-dive kind even when not idle, at most one
  a day, and the daily idle dive becomes weekly. Used by a new game patch
  (first three version parts changed) and by R3, R4. Impact: M; patch notes
  get read with web tools. Effort: S. Risk: more dives after launch; the
  one-a-day cap holds it at 2 runs a day. ToS check: "public web data": the
  lane's reads are the anonymous, robots-respecting reads the dive prompt
  already orders (tools/loop_prompts.py:72-92). Depends on: R2. Files
  likely touched: tools/al_loop.py, loop_prompts.py, tests. Acceptance
  test: a request with open rows present still dispatches one dive.
  ZERO-CLICK: unattended.
- R12 ROW-GRAMMAR. Action: accept `DEPENDS: <ids>` inside the row text
  beside the plan-doc line, make an unknown dependency id a visible wait,
  not a silent pass, match the brief file on the exact id, and put the row
  id in the lane run's usage label. Impact: L-M. Effort: S. Risk: an old
  typo starts to block; it shows in the checklist. ToS check: none.
  Depends on: R1. Files likely touched: tools/loop_roadmap.py, al_loop.py,
  al_lane.py, tests. Acceptance test: a row depending on an unknown id
  reads "waits on <id> (no such row)". ZERO-CLICK: unattended.

### Watcher catalogue

Each line: home; cadence and gate; what it reads; on change; failure.
Runs cost is 0 for all; "row" means 2 to 8 runs when dispatched. Identity
everywhere: `AshLight/<version>` with a purpose text; the web-data opt-in
applies only to W0 and W7 (the app); the rest is dev tooling.

- W0 Price refresh (exists, decision 0026). App. Hourly, ETag, opt-in and
  contact required. poe.ninja documented routes. Acts inside 0026; N36 R3
  moves the trigger into the core loop. Failure: cache kept, age shown.
- W1 GGG developer docs (exists, decision 0044) plus R4 and a data-exports
  topic (N35 R3, N37 W8). Dev loop, also under HALT. 24 h. Six docs pages,
  anonymous. Flags and notes; registration open files `TC-OAUTH-REG-OPEN`
  for the batched operator ask. Failure: 3 h retry, Retry-After obeyed.
- W2 PoB-PoE2 release (exists, decision 0025). CI after go-public, dev loop
  until then, in front of HALT (N37 R2). 24 h, 12 h in the launch window.
  Releases API. The 0025 trial, then `POB-<TAG>` with `BLOCKED: session`
  (the live trial is a manual trigger). Failure: rate-limit reset obeyed.
- W3 PoB next release (N37 W2). CI. Weekly. Nine guarded source files at
  the beta head, as text. Red guard files `TC-BRIDGE-NEXT-<date>`.
- W4 repoe-fork (N37 W6). CI. 24 h. The data repository's newest version
  title; after a refresh the shape probes of N37 R8. A probe failure keeps
  the last good file and files `SNAP-<FILE>-<date>`; a new version feeds R3
  and R11. Open question 2 covers downloading the files in CI.
- W5 GGG tree export (N37 W7). CI. 24 h, 12 h from 2026-12-05. The `main`
  head and tags. A release title refreshes and runs id_match; a preview
  title is noted and never treated as live.
- W6 poe.ninja API docs page (N36 layer 2). CI. 24 h. One public docs page,
  normalised text hash. A types or routes change files `NINJA-DOCS-<date>`;
  a policy line goes to a session with decisions 0013 / 0026 as the
  question.
- W7 poe.ninja response shapes (N36 layer 1, R4). App, no extra request,
  opt-in applies. Every hourly body. A break keeps the last good cache and
  shows a Checks line; on the dev host the flag
  `ops/runtime/ninja/SHAPE_DRIFT` files `NINJA-SHAPE-<date>`.
- W8 Electron (N46 R1). CI. 24 h. npm dist-tags and the release schedule,
  `npm audit`. Policy of N46 R1: patch after 3 days once per 7 days files
  `ELECTRON-<version>`; 30 days before end of life files `REL-DUE-<date>`
  (N52 R7).
- W9 Dependabot (after go-public). CI reads alerts with the read-only key
  that exists since 2026-09 [GH-PERM, GH-CL]. A new alert files
  `DEP-<PACKAGE>-<ADVISORY>` with `(priority)`; a lane re-applies the bump
  locally (FLEET item 17; tools/al_lane.py:54-60). Open question 3.
- W10 Pin canaries (N37 W3, W4, W5). CI. Weekly. The pinned LuaJIT archive
  hash, the WinLibs asset digest. A mismatch files `PIN-<NAME>-<date>` with
  `BLOCKED: session`; setup keeps refusing meanwhile.
- W11 Calendar and launch (R3). Dev loop. Reads W4 and W5 results and the
  clock only.
- W12 Docs, screenshots, notes (R6, R8, R9). Gate test plus one tick check
  a day; reads the tree only.
- W13 Watch health (R7, R10). Dev loop. Daily read of the workflow state
  [GH-WF]; own state file.

### Row templates the parser accepts

Checked with the loop's own parser [L-PARSE]. Tokens in angle brackets
are filled only from values that match a fixed pattern (a version, a tag,
a date, a 40-character hash); no upstream sentence is ever copied (F14).

    - [ ] <ID> (<lane>) <what changed, inside 70 characters>: <task>.
      ACCEPT: <checkable outcome>. ZERO-CLICK: <how>. SOURCE: watch
      <name> <key>, filed <YYYY-MM-DD>.

    - [ ] ELECTRON-45-3-4 (data) Electron 45.3.4 is 3 days old (pin
      45.3.3): bump the exact pin and the lockfile. ACCEPT: both files
      name 45.3.4; npm test, the overlay smoke and the docs freshness
      test pass. ZERO-CLICK: the loop works it. SOURCE: watch electron
      45.3.4, filed 2026-11-21.

    - [ ] GATE-POE2-10 (data) Gate: PoE2 1.0 is live. BLOCKED: gate,
      flipped by the launch watcher (date and two upstream signals).

    - [ ] UTIL-10-DATA (data) (priority) PoE2 1.0 data refresh: runbook
      steps 4, 6, 7 and 8. ACCEPT: the zone table has G5 and G6 rows;
      id_match passes; read-back per step. ZERO-CLICK: the loop works it.

    - [ ] DEP-ELECTRON-GHSA-XXXX-XXXX-XXXX (data) (priority) Advisory on
      electron: re-apply the fixed version locally. ACCEPT: npm audit
      reports 0 for the package. SOURCE: watch dependabot, filed <date>.

Rules the parser enforces today:
- ID: upper-case letters, digits, hyphens; no dot, no colon, no lower
  case; unique for all time, so it carries the version or the date.
- Lane: `build`, `data` or `review` right after the ID; any other word in
  brackets becomes title text. `(priority)` on the first line.
- Continuation lines start with two or more spaces; a line at column 0
  ends the row.
- The upper-case word BLOCKED anywhere parks the row; a template never
  uses the word in passing.
- A dependency needs `docs/plans/<ID>-<name>.md` with a first line
  `Depends on: <ids>` until R12; the gate row must exist first. No row id
  may be a hyphen-prefix of another.
- The loop appends ` -- done <date> (...)` to the first line; a gate flip
  uses the same form with `(watch: <evidence>)`.

### Loop and waves

- Marker. Every row a session wave owns carries
  `BLOCKED: session wave <n>`. The loop lists it and never dispatches it;
  the session flips it when done. A row without the word is the loop's.
- Rows the loop may take while waves run: watcher rows with lane `data`
  (pins, snapshots, baseline, docs freshness, advisories); requested
  dives; rows a wave leaves untagged on purpose. Never a row that touches
  web/, app/overlay/, app/shared/ or the event text while a wave owns
  those folders.
- A session touches an untagged row only after reading
  `ops/loop/control/loop_items/<ID>.json`: dispatched, ran or committed
  means the loop has it.
- Shared ground. Both sides commit under the kit git lock; the loop
  merges only into a clean main (tools/loop_merge.py:92-95), and its
  suite run waits while a live agent holds uncommitted edits (FLEET item
  16 c). So wave agents work in worktrees and main stays clean between
  merges; with a dirty main the loop holds at most 3 finished items and
  starts nothing new.
- HALT is removed when all six hold: (1) the plan's rows are in ROADMAP.md
  and the R1 lint passes; (2) every session row is tagged; (3) the hand-off
  yields 0 loop items; (4) `al_loop.py preflight` is green with the client
  running; (5) the gate reads under half the cap; (6) a dry-run tick lists
  only intended rows. Until then the sources of R2 run in front of the
  HALT return, so HALT never blinds a watcher again.
- Budget against the cap of 120 (117 usable): watchers 0; filed rows at
  most 3 a day, 6 to 24 runs; one dive, 2 runs; total at most 26 a day,
  22 percent. Launch week is the peak: about 12 rows, 24 to 96 runs over
  7 days. Inbox cost is unchanged: a watcher sends no note; a policy
  change sends at most one note to MAIN per changelog entry, inside the
  12-a-day cap (FLEET item 14).
- What the operator sees: the filed row itself, as one line of the next
  checklist; nothing in chat, no toast (decision 0044 item 5). Operator
  acts collect in the hand-off's one batched ask.

## Cut or merge

- Merge the watcher tools of N36 R6, N37 R5 and N46 R1 into R2's frame;
  keep `tc_drift.py` for trial and apply, `ggg_docs_watch.py` for parsing.
- Merge the policy wording watch (research 0029) into the docs watch (R4).
- Cut the hand-off file as a loop work source (R1 a): ROADMAP.md is the
  one ledger; the hand-off stays the session's continuity.
- Cut the daily idle dive to weekly plus on demand (R11): with sources
  reporting real changes, a daily dive mostly finds nothing.
- Cut a Steam news reader [STEAM]: a new host for a signal W4 and W5
  already give.
- Split UTIL-1.0-POST into three rows and a gate (R3); the old row stays
  only as history.

## Rejected

- A plain-Python daily read of the official patch-notes board [GGG-PN].
  robots.txt allows the path [GGG-ROB], but it is a GGG page outside the
  API Reference and Data Exports and the page has no feed; the floor's GGG
  clause is not clearly met and W4 / W5 detect a patch without it.
- A CI job that commits a state file, moves a pin or merges a Dependabot
  pull request: FLEET item 17 (no bot author, no merge on GitHub).
- Row text taken from an issue body, a release note or a commit title:
  a public stranger could steer a lane (F14).
- Screenshots of the real desktop, or of the overlay above the game: the
  floor allows a screen read only per manual hotkey press, and game art may
  not appear in AshLight's branding.
- A toast, message box or chat line on change: focus-taking, rejected in
  decision 0044 item 5; FLEET item 2 keeps chat quiet.
- Dev watchers inside the shipped core: rejected in decision 0044
  ("Fetch in the core"); decision 0013 covers only the player's requests.
- An unattended pin move or an unattended run of candidate Lua: decision
  0025 and its amendment.
- A runtime snapshot fetch by the core: decision 0009 (build-time only).
- A process-list check to see whether the game is closed before a heavy
  job: decision 0029; jobs run hidden at below-normal priority instead.
- A model run per tick to look for changes: 96 ticks a day against a cap
  of 120 (FLEET items 10 and 14).
- The trade site or a session cookie as a league or patch signal: floor.

## Open questions

1. May the tick commit ROADMAP-only changes (append a row, flip a gate)
   on main? Decision 0025 rejected an unattended commit for the pin and
   names "a safe auto-commit path" as its reversal. Needs an adjudicator;
   without it R2 files nothing and only reports.
2. May a CI job download the repoe-fork and tree files to probe their
   shape, discarding them after the run? Decision 0009 speaks of a
   build-time fetch into the sidecar cache. Needs an adjudicator.
3. FLEET item 17 asks a lane to close a Dependabot pull request with a
   comment. That needs a GitHub credential on the dev host (operator act),
   or a MAIN ruling that Dependabot's own close is enough. Whether
   Dependabot closes it once main is fixed is UNVERIFIED [GH-DBS].
4. Does a list read of public issues work without a token at the stated
   60 per hour? The pages read do not say so in words [GH-ISS, GH-RATE];
   UNVERIFIED until the remote exists.
5. Which address goes into the CI User-Agent as contact: the repository
   address from the runner is proposed; decide with note 0057.
6. May scripts/run.ps1 refresh the snapshot for players when web data is
   on and the cache is over 24 h old (N37 F13)? It is outside the core but
   not a build step; decision 0009 needs a reading. Adjudicator.
7. How does the first 1.0 play session unblock `UTIL-10-LOG` without a
   reminder: a read of AshLight's own run-history file for an Act 5 split
   is proposed; it needs the run-history box ticked. Operator decision.
