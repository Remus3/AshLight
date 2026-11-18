# 06 - Automation
Date: 2026-11-18. Ultraplan plan section (docs/plan/README.md).
Status: final

Dimension G: the operator never has to remind anyone. Inputs: research
0058 (primary), the watcher inputs of 0036, 0037, 0046 and 0051,
docs/plan/01-open-items.md (L1 to L4, L12, L15, R1, R9) and the findings and
rulings of docs/plan/findings.json (status final). Finding ids are F-..,
ruling ids Q-.. and A-... Where a ruling changed what research 0058
proposed, the ruling wins and the change is named.

## Goal

Done means every statement below can be shown by a test or a read-back.

- G1 No work depends on a remembered date or a carried-forward paragraph:
  every dated or upstream-triggered task is a ROADMAP row that opens by a
  watcher (a filed row or a flipped gate), or an operator act listed once
  in docs/plan/09.
- G2 One tool, `tools/upstream_watch.py`, runs every source. A watcher is
  plain Python and costs 0 headless runs; a model run happens only when a
  filed row is dispatched.
- G3 Each of the seven upstreams the operator named has a source with a
  cadence gate, a truthful User-Agent and a defined act: GGG developer
  docs, PoB-PoE2 releases, poe.ninja response shapes, the repoe-fork
  snapshot, the GGG passive tree export, Electron security releases,
  Dependabot.
- G4 An unattended commit on main only ever adds one file under
  `docs/roadmap/new/` or `docs/roadmap/done/`, built from a tracked
  template and validated tokens, at most 3 new-row files a local day
  (Q-12) and at most 3 done files a local day (gate flips first), never
  while HALT exists (Q-12, Q-13). A test refuses any other path.
- G5 Watcher-caused work stays inside 32 of the 117 usable runs a day and
  sends 0 fleet notes.
- G6 README facts, doc indexes, screenshots and release notes cannot drift
  silently: a test blocks a merge that leaves a fact stale, and a daily
  local check files at most one refresh row a week per kind.
- G7 The loop and a session never work the same row: session rows carry
  `BLOCKED: session wave <n>`, and the HALT file is removed only at the
  point named under "Loop and wave interplay".
- G8 A broken watcher is itself reported: 3 misses give a tick line, 7
  days give a row.
- G9 The 1.0 launch (2026-12-11) opens its rows by itself; the launch gate
  is landed and proven with a fake clock before 2026-12-05.

## Design

### What exists and stays

- One scheduled task, `\AshLightOps\LaneLoop`, runs `tools/al_loop.py
  tick` every 15 minutes while the operator is logged on (research 0058
  U1). It stays the only scheduled task on the dev host; this plan adds no
  second task. After go-public one scheduled CI workflow is added (F-150).
- The GGG docs watch (decision 0044) and the PoB release check (decision
  0025) keep their settled reads, cadence and identity (F-030).
- The shipped app keeps its own refreshes under the web-data opt-in
  (decisions 0013, 0026). No dev watcher moves into the core (0058-X6).

### Changes the rulings made to research 0058

- Row writes are files, never an edit of ROADMAP.md (F-029, Q-12). A new
  row is `docs/roadmap/new/<ID>.md`; a finished or flipped row is
  `docs/roadmap/done/<ID>.md`. A loader composes them with ROADMAP.md;
  one writer folds them in at /done. Research 0058 R2 (append to
  ROADMAP.md, flip in place) is superseded.
- New sources read only while the dev host's `web_data` is on and read
  repository metadata only (commit id, tag, release title, date through
  the documented GitHub API), never a data file; the poe.ninja docs page
  is their one page read (F-030, floor audit L3). The docs watch and the
  PoB release check are the only settled exceptions. This plan applies
  the same gate to the Electron source (strict reading; F-130 does not
  record an exemption).
- Sources read while HALT exists and act on nothing: no row file, no
  bump, no candidate-Lua trial, no commit. Findings wait in the halted
  tick's checklist (Q-13).
- No CI job reads poe.ninja or a GGG host, and CI downloads no repoe-fork
  or tree file (conflict resolution on 0057-X5; F-150). The poe.ninja
  docs-page source runs on the dev loop.
- The policy-quotes check (0058 R4) is blocked on operator decision A-01
  (F-051). The shape topic runs on the API Reference and Data Exports
  pages only (F-115). Dives lose free web tools and read GGG only at
  those two pages (F-171, Q-07).
- Dependencies are `DEPENDS: <ids>` in the row text; long text lives in
  `docs/plan/briefs/<ID>.md`; the `docs/plans/` path is dropped (F-029).
- The User-Agent contact of the CI watcher is the project's issues page
  once the repository is public (Q-03).

### The watcher frame (F-030)

- `tools/upstream_watch.py`, stdlib only, every request through
  `server/al/webfetch.py` (`webfetch.request` with a per-source host
  allow-list, `webfetch.user_agent(<purpose>)`, no cookie, no redirect off
  the host).
- A source is a registry entry: `name`, `home` (loop, ci or both),
  `cadence_s`, an optional dated window with a shorter cadence,
  `needs_web_data` (false only for the two settled sources and for local
  sources that make no request), `hosts`, `check(state, now, fetch)`.
  `check` returns typed findings: `{source, kind, key, tokens}`.
- State: `ops/runtime/watch/state.json` (per source: `last_run`,
  `last_ok`, `fails`, `etag`, `seen` keys). Pending findings:
  `ops/runtime/watch/pending.json`. Both gitignored, written through the
  hardened write path (F-014) once it exists.
- Scheduling: the tick calls `upstream_watch.run_due(root, now)` in front
  of the HALT return (tools/al_loop.py:1547, next to the docs watch). At
  most one due network source per tick, oldest due first, at most 2
  requests and 10 s per request, so the tick stays under its 60 s target.
  Local sources (no request) all run each tick. A dry-run tick calls no
  source (it already skips the docs watch).
- With `web_data` off a gated source raises `webfetch.WebDataOff` before
  any request and its state reads `idle: web data off`; watch health
  shows it as one checklist line, never as a failure.
- Every tracked template lives in one file, `ops/loop/watch_rows.json`:
  per finding kind the act (`note`, `row`, `gate`, `dive`), the id
  pattern, lane, priority flag, the BLOCKED tag if any, the text template
  and one regular expression per token. No upstream sentence, issue body,
  release note or commit title ever enters a row (0058-X3, F-030).

### The two primitives and the commit path (Q-12)

`upstream_watch.py file` runs inside the tick, after the work list, only
when all hold: HALT absent; not a dry run; fewer than 3 files of the
same kind committed this local day (new-row files are the "3 filed rows"
of Q-12; done files have their own cap of 3 so a burst of LIVE-1 done
files on launch day cannot hold a gate flip, and a gate flip is written
before any other done file); the usage gate under 60 percent of the cap
(rows with `(priority)` and done files skip this one test); the id is
unused in
ROADMAP.md, `docs/roadmap/new/`, `docs/roadmap/done/` and
`docs/roadmap/archive/`; no flag `ops/runtime/watch/COMMIT_FAULT`.

1. Render the template; every token must match its pattern, else the
   finding is dropped with one tick line.
2. Parse the rendered text with the loader: exactly one row, the expected
   id, a valid lane, ASCII, LF, at most 700 characters.
3. Write `docs/roadmap/new/<ID>.md` (a new row) or
   `docs/roadmap/done/<ID>.md` (a gate flip: one line
   ` -- done <YYYY-MM-DD> (watch: <source> <key>)`). The path must match
   `^docs/roadmap/(new|done)/[A-Z][A-Z0-9-]*\.md$` and must not exist at
   HEAD (add-only).
4. `git add -N -- <path>`, then
   `python ops/fleet_kit/fleet_gitlock.py run --owner <loop owner id> --
   git commit -m "chore(roadmap): file <ID> (watch <source>)" -- <path>`.
   The identity is the operator's from the local git config; no trailer
   (FLEET item 17). The pre-commit leak sweep runs as for any commit.
5. Read back: `git show --stat --format=%H HEAD` names exactly that one
   path and `git status --short -- <path>` is empty. Any other result
   writes `ops/runtime/watch/COMMIT_FAULT`, which stops all filing until a
   session removes it (the Q-12 "Reverses if" tripwire). The tick never
   reverts, resets or amends.
6. On a failed step 4 the untracked file is removed, the finding stays
   pending and the tick prints one line.

### Row cost rules

- A template never asks for a new decision and never names CLAUDE.md,
  ROADMAP.md, `web/`, `app/overlay/`, `app/shared/` or event text: a lane
  cannot merge those unattended (research 0058 F4, F-033). Work of that
  kind is filed with `BLOCKED: session`.
- Lane `data` (sonnet route) for pin, snapshot and docs rows; `review`
  for rows that end in a written verdict; `build` only for pre-landed
  plan rows.
- A row is filed once per key: `seen` holds the key for all time, so a
  re-read of the same upstream state files nothing.

### Contract line for docs/plan/08 (F-198)

The last progress write of a task carries the outcome in its step text
(`done: <result>` or `failed: <cause>`), not the last working step.

## Watcher catalogue

Fields per block: home; gate; source and User-Agent; on change; row
template; cost. "Row" cost means 2 runs when clean (lane, verifier), 8 at
worst (research 0058 F16); with AUTO-01 part (d) a gate failure outside
the lane's diff ends at 1 run. User-Agent everywhere is
`AshLight/<version> (<purpose>)` from `webfetch.user_agent`; on the dev
host the contact part comes from the gitignored config when set. All
templates below were shaped against the loop's row grammar (research 0058
"Row templates the parser accepts"); `<YYYYMMDD>` keeps an id unique for
all time. Check done 2026-11-18 (re-run by the verifier after the
corrections): all 24 templates of this section, with sample tokens
filled in, parse through `tools/loop_roadmap.py` `roadmap_rows` as
exactly one row each, carry a valid lane, are ASCII and stay under 700
characters; BLOCKED appears only as a tag. No two template ids are
hyphen-prefixes of each other. Two ids extend an existing ROADMAP id by
a hyphen: `TC-OAUTH-REG-OPEN` (of TC-OAUTH-REG) and the F-061
`LIVE-1-<ITEM>` rows (of LIVE-1); both are safe only after AUTO-03
matches briefs and done files on the exact id, which AUTO-05 already
depends on.

### W0 Price refresh (exists)

- Home: shipped app. Gate: hourly per type, ETag, web-data opt-in and
  contact (decision 0026; cadence tiers per F-046). Release builds make
  no poe.ninja request until poe.ninja's yes is recorded (F-046, operator
  decision Q-05); source checkouts, the dev host included, poll as today.
- Source: poe.ninja documented routes; purpose `price check`.
- On change: acts inside decision 0026; nothing is filed.
- Row template: none. Cost: 0 runs.

### W1 GGG developer docs (exists, decision 0044) plus the shape topic

- Home: dev loop, in front of the HALT return, not gated by `web_data`
  (settled). Gate: 24 h, 3 h after a network error, Retry-After obeyed.
- Source: the six developer-docs pages, anonymous; purpose as today.
  New work reads nothing beyond them and tags only the reference and
  data pages (F-115, A-01 pending).
- On change: hash, diff to the sidecar Logs, Checks note; the flag
  `ops/runtime/ggg_docs/REG_OPEN` files the first row below; a diff of
  the reference or data page that touches a field name the readers use
  files the second.
- Row templates:

      - [ ] TC-OAUTH-REG-OPEN (review) GGG OAuth registration reads open:
        put the application send into the batched operator ask. ACCEPT:
        the hand-off's operator ask names it. BLOCKED: operator act (send
        the application, row TC-OAUTH-REG). SOURCE: watch ggg-docs
        reg-open, filed <YYYY-MM-DD>.

      - [ ] GGG-SHAPE-<YYYYMMDD> (review) GGG docs page <page> changed near
        <n> field names the readers use: read the diff in the sidecar Logs
        and file one fix row per reader. ACCEPT: each named field has a
        row or a written "no change needed". BLOCKED: session. SOURCE:
        watch ggg-docs shape <page>, filed <YYYY-MM-DD>.

  Tokens: `<page>` is `reference` or `data`; `<n>` is 1 to 99.
- Cost: 0 runs; both rows wait for a session or the operator.

### W2 PoB-PoE2 release (exists, decision 0025)

- Home: dev loop, moved in front of the HALT return (Q-13), not gated by
  `web_data` (settled). After go-public CI repeats the tag read so the
  watch survives a dev host that is off.
- Gate: one releases read per 24 h (decision 0025; no launch-window
  speed-up, the settled cadence stands).
- Source: the GitHub releases API of the PoB-PoE2 repository; purpose as
  today.
- On change: the decision 0025 flow. A new tag starts the detached
  static trial at below-normal priority (static drift guard only, no
  candidate Lua). Under HALT the read, the record and that static trial
  happen, as Q-13 rules ("static trial only"); no row file, no live
  trial, no pin move, no commit. When the static verdict is known and
  HALT is absent the row below is filed.
- Row template:

      - [ ] POB-<VTAG> (review) PoB-PoE2 <tag> is out (pin <pin>), static
        trial <verdict>: run the live trial, then apply or record a HOLD.
        ACCEPT: tc_drift.py status shows the pin at <tag>, or a HOLD line
        names the failing rows. BLOCKED: session (decision 0025: the live
        trial and the pin move are session acts). SOURCE: watch
        pob-release <tag>, filed <YYYY-MM-DD>.

  Tokens: `<tag>` and `<pin>` match `v[0-9]+\.[0-9]+\.[0-9]+`; `<VTAG>` is
  the tag upper-cased with dots as hyphens (`V0-24-0`); `<verdict>` is
  `green` or `red`.
- Cost: 0 runs.

### W3 PoB-PoE2 next release

- Home: dev loop; CI after go-public. Gate: weekly; `web_data` on.
- Source: the `master` head commit id and date (GitHub API metadata).
- On change: one tick line (`PoB master moved <n> commits past the pin`).
  When the head moved and no release appeared for 28 days, the row below
  is filed, at most once per 28 days. The watcher itself reads no source
  file; the static rehearsal is `tc_drift.py trial --ref <sha>` (AUTO-12).
- Row template:

      - [ ] TC-NEXT-<YYYYMMDD> (review) PoB-PoE2 master is <n> commits past
        the pin with no release for 28 days: run the static rehearsal on
        <sha> and list failing guard rows. ACCEPT: a static verdict in
        tc_drift.py status for that ref. BLOCKED: session. SOURCE: watch
        pob-next <sha>, filed <YYYY-MM-DD>.

  Tokens: `<sha>` is 40 hex characters; `<n>` is 1 to 9999.
- Cost: 0 runs.

### W4 repoe-fork data

- Home: dev loop; CI after go-public (metadata only). Gate: 24 h, 12 h
  from 2026-12-05 to 2026-12-24; `web_data` on.
- Source: the newest version or export title of the repoe-fork data
  repository (GitHub API metadata). No data file is requested.
- On change: record the version; feed the launch gate (W11); when the
  first three version parts changed, write a dive request (AUTO-13). The
  snapshot itself refreshes at the next build or client start (decision
  0009 as amended by Q-04), never from the loop.
- Row template: none of its own. A shape break after the refresh is
  filed by W14 (`SNAP-<FILE>-<YYYYMMDD>`).
- Cost: 0 runs; a requested dive is 2 runs.

### W5 GGG passive tree export

- Home: dev loop; CI after go-public (metadata only). Gate: 24 h, 12 h
  from 2026-12-05 to 2026-12-24; `web_data` on.
- Source: the `main` head, tags and newest commit title of GGG's listed
  data-export repository (GitHub API metadata). No tree file is
  requested.
- On change: a title holding the word Preview is noted and never treated
  as live; a release title or tag records the version, feeds the launch
  gate and writes a dive request as W4 does.
- Row template: none of its own (launch rows via W11, breaks via W14).
- Cost: 0 runs.

### W6 poe.ninja API docs page (F-140 layer 2)

- Home: dev loop only (never CI). Gate: 24 h, 3 h after a network error,
  stop at 429 or 503; `web_data` on and a contact set on the dev host.
- Source: the one public API docs page; purpose `docs watch`. Hash of the
  normalised text from the "API Reference" heading to the footer line;
  baseline in the sidecar Cache, diff in the sidecar Logs.
- On change: changed lines are tagged types, routes or policy. Types or
  routes file the first row; a policy line files the second. Each kind
  files at most one row per 7 days; later diffs join the Logs file.
- Row templates:

      - [ ] NINJA-DOCS-<YYYYMMDD> (data) poe.ninja docs changed (<topic>,
        <n> lines): compare the diff in the sidecar Logs with the tracked
        read-key baseline and update the type lists or the parser.
        ACCEPT: the baseline test passes on the new shape; no route
        outside the documented page is added. ZERO-CLICK: the loop works
        it. SOURCE: watch ninja-docs <topic>, filed <YYYY-MM-DD>.

      - [ ] NINJA-POLICY-<YYYYMMDD> (review) poe.ninja docs changed a
        policy line (<n> lines): re-read decisions 0013 and 0026 against
        it. ACCEPT: a dated note in both decisions. BLOCKED: session.
        SOURCE: watch ninja-docs policy, filed <YYYY-MM-DD>.

  Tokens: `<topic>` is `types` or `routes`; `<n>` is 1 to 999.
- Cost: 0 runs; the first row 2 to 8 when dispatched.

### W7 poe.ninja response shapes (F-140 layer 1, F-085)

- Home: shipped app, no extra request, opt-in applies; the dev loop only
  reads the flag the dev host's own core wrote.
- Gate: every hourly body in the core; the flag is read each tick (local,
  no request).
- Source: the bodies the price refresh already fetched.
- On change: in the app a break keeps the last good cache and shows a
  Checks line (F-085). On the dev host the flag
  `ops/runtime/ninja/SHAPE_DRIFT` (family, type, missing key names from
  the tracked baseline, first seen) files the row below.
- Row template:

      - [ ] NINJA-SHAPE-<YYYYMMDD> (data) poe.ninja <family> bodies miss
        <n> read keys since <YYYY-MM-DD>: adapt the parser and the tracked
        baseline from the recorded key sets. ACCEPT: the shape tests pass
        on a fixture cut from the recorded key sets; prices show again.
        ZERO-CLICK: the loop works it. SOURCE: watch ninja-shape <family>,
        filed <YYYY-MM-DD>.

  Tokens: `<family>` is `league`, `exchange` or `item`; `<n>` is 1 to 99.
- Cost: 0 runs; the row 2 to 8.

### W8 Electron releases and advisories (F-130)

- Home: dev loop until go-public, then CI with the dev loop as failover.
  Gate: 24 h; `web_data` on (dev loop). Reads while HALT exists, files
  nothing then (Q-13).
- Source: the two public JSON files named in research 0046 R1 (npm
  dist-tags for the pinned package, the Electron release schedule);
  purpose `electron watch`; 2 requests. A second registry entry,
  `npm-audit` (24 h, `web_data` on, after F-037 lands), runs
  `npm audit --package-lock-only --json --prefix app` against the
  tracked lockfile; npm sends the AshLight User-Agent through the
  tracked `app/.npmrc` (F-037, strict reading of A-02). The same entry
  runs in CI after go-public. Without it the dev loop has no advisory
  signal before the remote exists (research 0046 R1 b: "within 24 h").
- On change, by the written upgrade policy (F-130): a patch or minor at
  least 3 days old, at most once per 7 days, files the first row; an
  advisory on a pinned package files it at once with `(priority)`. The
  second row is filed once per major, at the earlier of: the next
  major's .0.0 is 14 days old (policy c: adopt N+1 14 to 42 days after
  its .0.0, one major at a time), or 30 days before the pinned line's
  end of life (`config/electron_pin.json`, F-044; policy d).
- Row templates:

      - [ ] ELECTRON-<MAJ>-<MIN>-<PAT> (data) Electron <version> is 3 days
        old (pin <pin>): bump the exact pin, the lockfile and
        config/electron_pin.json. ACCEPT: all three name <version>; npm
        test, the static guards, npm audit signatures and the docs
        freshness test pass. ZERO-CLICK: the loop works it. SOURCE: watch
        electron <version>, filed <YYYY-MM-DD>.

      - [ ] ELECTRON-MAJOR-<MAJ> (review) Electron <MAJ> is due (line
        <PIN-MAJ> ends <YYYY-MM-DD>): move to the next major under the
        written upgrade policy and re-measure the decision 0002 budgets.
        ACCEPT: a pin on line <MAJ> or a dated plan. BLOCKED: session.
        SOURCE: watch electron major <MAJ>, filed <YYYY-MM-DD>.

  Tokens: `<version>` and `<pin>` match `[0-9]+\.[0-9]+\.[0-9]+`;
  `<MAJ>` and `<PIN-MAJ>` match `[0-9]{2,3}`.
- Cost: 0 runs; a bump row 2 to 8.

### W9 Dependabot (after the public flip; F-081)

- Home: CI reads the repository's alerts with the read-only
  `vulnerability-alerts` permission and lists the open Dependabot pull
  requests (`pull-requests: read`); the tick reads the labelled issues.
  Gate: daily in CI, issues read every 6 h by the tick.
- Source: GitHub only; purpose `upstream watch` with the issues page as
  contact (Q-03).
- On change: a new alert files the first row; an open Dependabot pull
  request (the weekly version updates of `.github/dependabot.yml`,
  section 04 GP-08) files the second, unless an open `DEPBOT-` advisory
  row names the same package (that lane closes the pull request too).
  Each lane runs `tools/dependabot_reapply.py apply <n>` (section 04
  GP-14): the bump is re-applied locally as an operator commit through
  the bump gates, the tool pushes main through the guarded pre-push hook
  (section 04 GP-02) and closes the pull request with a one-line
  comment. Nothing is merged on GitHub (FLEET item 17). An Electron bump
  pull request is only a signal: the lane follows the Electron bump
  procedure (F-130, F-044), as GP-14 does.
- Row templates (prefix `DEPBOT-`, because section 05's package ids use
  `DEP-`):

      - [ ] DEPBOT-<PACKAGE>-<GHSA> (data) (priority) Advisory <GHSA> on
        <package>: re-apply the fixed version locally. ACCEPT: npm audit
        reports 0 for the package; the bump is an operator commit; the
        pull request is closed with one comment. ZERO-CLICK: the loop
        works it. SOURCE: watch dependabot <GHSA>, filed <YYYY-MM-DD>.

      - [ ] DEPBOT-PR-<n> (data) Dependabot pull request <n> is open:
        re-apply it locally with tools/dependabot_reapply.py. ACCEPT: one
        operator commit names the dependency and versions; the pull
        request is closed with one comment, never merged. ZERO-CLICK: the
        loop works it. SOURCE: watch dependabot pr <n>, filed
        <YYYY-MM-DD>.

  Tokens: `<GHSA>` is upper-cased and matches `GHSA(-[0-9A-Z]{4}){3}`;
  `<package>` must be a name in the tracked lockfile; `<PACKAGE>` is that
  name upper-cased with every character outside A-Z and 0-9 as a hyphen;
  `<n>` is 1 to 999999 and must be a pull request whose author is the
  Dependabot app (the CI key carries the number only).
- Cost: 0 runs; each row 2 to 8.

### W10 Pin canaries (marked option, not adopted)

- The WinLibs asset digest and the LuaJIT head are GitHub metadata and
  would fit the F-030 URL check; the LuaJIT archive re-download is a
  data-file request and does not. No finding adopts them. Setup already
  refuses a hash mismatch at fetch time (decisions 0018, 0027). Option:
  add the two metadata reads as sources after AUTO-05, row
  `PIN-<NAME>-<YYYYMMDD>` with `BLOCKED: session`. Not in the packages.

### W11 Calendar and launch gate (F-052)

- Home: dev loop. Gate: each tick (local; reads the W4 and W5 records,
  the clock, AshLight's own run-history file and the parse ledger).
- Source: no request of its own.
- On change: `GATE-POE2-10` flips when the local date is 2026-12-11 or
  later and W4 or W5 recorded a version of 1.0 or higher that is not a
  preview. `GATE-ACT5-SEEN` flips on the first Act 5 split in the
  run-history file, else on the parse ledger's first Act 5 hit (Q-28).
  Three days past the date with no upstream signal files the check row.
- Row templates (the two gate rows and their dependents are pre-landed
  by the plan; the watcher only writes the done files):

      - [ ] GATE-POE2-10 (data) Gate: PoE2 1.0 is live. BLOCKED: gate,
        flipped by the launch watcher (date and one upstream signal).

      - [ ] GATE-ACT5-SEEN (data) Gate: the operator's own log shows Act
        5. BLOCKED: gate, flipped by the launch watcher (run history or
        parse ledger).

      - [ ] UTIL-10-DATA (data) (priority) PoE2 1.0 data refresh: runbook
        steps 4, 6, 7 and 8. ACCEPT: the zone table has Act 5 and 6 rows;
        id_match passes; read-back per step. DEPENDS: GATE-POE2-10.
        ZERO-CLICK: the loop works it.

      - [ ] UTIL-10-NOTES (review) PoE2 1.0 notes: runbook step 1 from
        the allowed sources only (pasted text, public repositories, the
        API Reference and Data Exports pages). ACCEPT: a dated research
        note. DEPENDS: GATE-POE2-10. ZERO-CLICK: a requested dive.

      - [ ] UTIL-10-LOG (build) PoE2 1.0 log shapes: runbook steps 2, 3
        and 5 from tools/live1_report.py output. ACCEPT: every new shape
        has a fixture and a passing test. DEPENDS: GATE-POE2-10,
        GATE-ACT5-SEEN. ZERO-CLICK: opens after the first 1.0 session.

      - [ ] LAUNCH-CHECK-<YYYYMMDD> (review) The 1.0 date passed 3 days
        ago and no upstream shows 1.0: confirm the launch state from the
        allowed sources. ACCEPT: the gate is flipped by hand or a new
        date is recorded. BLOCKED: session. SOURCE: watch launch
        no-signal, filed <YYYY-MM-DD>.

- Cost: 0 runs for the gates; the three dependents 6 to 24 in total.

### W12 Docs, screenshots and notes freshness (F-146, F-147, F-101)

- Home: dev loop, local source `refresh`. Gate: once per local day;
  each kind files at most one row per 7 days.
- Source: the tree only (`docs_fresh.py stale`, `shots.py check`,
  `release.py notes --count`). No request.
- On change: see "Refresh pipeline".
- Row templates:

      - [ ] DOCS-FRESH-<YYYYMMDD> (data) <n> dated markers in docs are
        older than 30 days: resolve or re-date each with a source.
        ACCEPT: docs_fresh.py stale prints 0. ZERO-CLICK: the loop works
        it. SOURCE: watch refresh docs, filed <YYYY-MM-DD>.

      - [ ] SHOTS-<YYYYMMDD> (data) The screenshot manifest is stale since
        <YYYY-MM-DD>: run tools/shots.py render and commit docs/shots.
        ACCEPT: shots.py check exits 0; no window appeared. ZERO-CLICK:
        the loop works it. SOURCE: watch refresh shots, filed
        <YYYY-MM-DD>.

      - [ ] REL-DUE-<YYYYMMDD> (review) <n> rows merged in <d> days since
        the last tag with no release row open: decide whether they make
        a milestone and, if so, file a REL-PREP row that waits on them.
        ACCEPT: a REL-PREP row exists or a dated "no milestone" line.
        BLOCKED: session. SOURCE: watch refresh notes, filed
        <YYYY-MM-DD>.

  Tokens: `<n>` is 1 to 9999; `<d>` is 1 to 999. The notes themselves
  are generated at release time from merge subjects (section 05,
  "Changelog generation"), so they cannot go stale between releases;
  this row only keeps a release from never being planned. It never
  bumps, stages, tags or pushes (releases only at a milestone or on an
  explicit version request, section 05 "Release procedure").

- Cost: 0 runs; each row 2 to 8, at most 3 rows a week.

### W13 Watch health (F-125)

- Home: dev loop, local. Gate: each tick; the CI workflow state is read
  once a day after go-public.
- Source: `ops/runtime/watch/state.json`; after go-public the documented
  workflow endpoint of the project's own repository.
- On change: 3 failures in a row add one tick line; 7 days without
  `last_ok` file the row; a workflow that is not active or 48 h silent
  switches the tick to run the CI sources itself. On the dev host the
  Checks view notes a last tick older than 2 h (reads AshLight's own
  status file, never a process list; decision 0029).
- Row template:

      - [ ] WATCH-BROKEN-<NAME>-<YYYYMMDD> (review) Watch source <name>
        has had no good read for 7 days (<cause>): repair the source or
        retire it with a decision note. ACCEPT: last_ok is newer than the
        filing date. BLOCKED: session. SOURCE: watch health <name>, filed
        <YYYY-MM-DD>.

  Tokens: `<name>` is a registry name; `<cause>` is one of `network`,
  `status`, `shape`, `rate-limit`, `workflow`.
- Cost: 0 runs.

### W14 Local ledgers (F-061, F-143)

- Home: dev loop, local. Gate: each tick. No request.
- Source: the dev host's own `ops/runtime/logshapes.json` (masked shapes
  only, written by the core after the ledger consent, F-061) and the
  snapshot probe result (F-143; this plan asks that package for one
  machine-readable file, `ops/runtime/snapshot/probe.json`, with source
  name, verdict, missing-key count and time).
- On change: a pattern's first live hit writes the done file of its
  `LIVE-1-<ITEM>` row (F-061 splits LIVE-1 so each item closes alone); a
  new shape past the two-sighting rule files the first row; a failed
  probe files the second.
- Row templates:

      - [ ] LOG-SHAPE-<YYYYMMDD> (build) <n> new masked log shapes passed
        the two-sighting rule: add a fixture line and a parser pattern
        for each from tools/live1_report.py output. ACCEPT: the report
        prints no NEW SHAPE. ZERO-CLICK: the loop works it. SOURCE: watch
        ledger shapes, filed <YYYY-MM-DD>.

      - [ ] SNAP-<FILE>-<YYYYMMDD> (data) The <file> snapshot failed its
        shape probe (<n> missing keys); the last good file is kept: adapt
        the reader from the recorded key sets. ACCEPT: the probe passes
        on a fixture cut from the recorded key sets. ZERO-CLICK: the loop
        works it. SOURCE: watch ledger probe <file>, filed <YYYY-MM-DD>.

  Tokens: `<file>` is a name from the snapshot tool's own source list.
- Cost: 0 runs; each row 2 to 8.

### W15 Policy quotes (blocked, F-051)

- Not built until operator decision A-01. If allowed: the 12 baseline
  quotes of research 0029 checked in the docs watch's index page text
  (same six pages, cadence and identity as decision 0044; no new
  request); a missing quote writes `ops/runtime/ggg_docs/POLICY_CHANGED`
  and files:

      - [ ] POLICY-QUOTE-<YYYYMMDD> (review) Floor source quote <qid> is
        missing from the GGG docs index page: re-read the page and the
        floor. ACCEPT: research 0029 has a dated line with the verdict.
        BLOCKED: session. SOURCE: watch ggg-docs quote <qid>, filed
        <YYYY-MM-DD>.

- Cost: 0 runs.

## Runs budget

Cap: 120 headless runs per rolling 24 h for this tree; the loop stops
spawning at cap minus 3, so 117 are usable (tools/loop_base.py HEADROOM;
research 0058 "Contract: runs cap"). Interactive sessions and their
sub-agents are not headless runs.

- Watcher reads, all sources, dev loop and CI: 0 runs.
- Inbox: unchanged. Free classify each tick; at most one sonnet run at
  effort low per tick for what classify cannot place. Budget 4 a day.
- Watcher rows: at most 3 filed a local day. 6 runs when clean, 24 at
  worst.
- Dives: at most 1 a day on request, the idle dive weekly (AUTO-13). 2
  runs, 4 with a fix round.
- Automation total: at most 32 of 117 (27 percent). At least 85 a day
  stay for pre-landed plan rows the loop may take.
- Soft gate: at 72 used (60 percent) the tick files no row without
  `(priority)` and requests no dive; pending findings wait and show in
  the checklist. Advisory rows (`DEPBOT-<PACKAGE>-`, an Electron advisory) are never
  held by the soft gate, only by the hard stop at 117.
- Launch week peak (2026-12-11 to 2026-12-17): about 12 rows, 24 to 96
  runs over 7 days, inside the daily bound because of the 3-a-day cap.
- CI: 0 headless runs; one scheduled workflow run a day on a standard
  runner, free on a public repository.
- Requests a day on the dev host: about 10 (6 docs pages counted as one
  watch; 1 releases read; W3 to W6 and W8 about 6; 1 npm audit read to
  the npm registry), about 13 in the
  launch window; all anonymous GitHub reads stay far under the 60 per
  hour limit the address shares with other tools.
- Inbox cost rules (FLEET item 14): a watcher sends no note, answers no
  note and adds no responder; inbox handling stays folded into the tick.
  The one outbound note in this section is the kit report of AUTO-25,
  once, inside the 12-a-day cap. CI issues are not fleet notes.
- Usage lines: every dispatched watcher row logs through the kit with
  kind `build` and a label holding the row id (AUTO-03); dives and inbox
  triage keep the kinds they log today (FLEET item 14 e).

## Loop and wave interplay

### Who owns a row

- A row holding the upper-case word BLOCKED is listed every tick and
  never dispatched. The reason after the colon is echoed in the
  checklist (AUTO-06). Reasons in use: `session wave <n>` (a wave owns
  it), `session` (the next session start takes it), `operator act`,
  `gate` (a watcher flips it).
- A row without the word is the loop's.
- The hand-off file is not a work list: a hand-off bullet is loop work
  only when it starts with `LOOP:` (AUTO-01).

### Rows the loop may take while sessions run waves

- Every watcher row with lane `data`: `ELECTRON-<MAJ>-<MIN>-<PAT>`,
  `DEPBOT-`, `SNAP-`, `NINJA-DOCS-`, `NINJA-SHAPE-`, `DOCS-FRESH-`.
- `REL-PREP-<n>` once its `DEPENDS:` rows are done (section 05's lane;
  it never tags or pushes).
- `SHOTS-` only while no wave owns `web/` (it is filed only then).
- `LOG-SHAPE-`, `UTIL-10-DATA`, `UTIL-10-NOTES` and `UTIL-10-LOG` once
  their gates are closed.
- Requested dives.
- Plan packages that docs/plan/packages.json marks `owner: loop`. The
  test for that mark: size S, one area, none of the hotspot files
  (state.py, web/app.js, ROADMAP.md, CLAUDE.md), no new decision, no
  test tied to live processes, nothing under `web/`, `app/overlay/`,
  `app/shared/` or the event text while a wave owns those.

### How the loop and a session never take the same row

1. Tag: plan 07 lands every session row with `BLOCKED: session wave <n>`.
2. Claim order for an untagged row a session wants: commit the tag on
   that row first (one commit under the kit git lock), then read
   `ops/loop/control/loop_items/<ID>.json`. A record in state
   dispatched, ran or committed means the loop has it: the session
   commits the tag away again and leaves the row. The record wins.
3. The tick re-reads the row from HEAD immediately before a dispatch
   (inside the tick lock) and skips it when the word BLOCKED appeared
   since the work list was built (AUTO-06).
4. Folder hold: a session writes `ops/loop/control/wave_owned.json`
   (wave number, folder prefixes, time) at wave start and removes it at
   wave end. The review worker parks an item whose diff touches a held
   prefix as state `wave-hold` and merges it when the file is gone; a
   file older than 48 h is reported in the checklist, not obeyed
   silently.
5. Shared ground: both sides commit through the kit git lock; the loop
   merges only into a clean main under `ops/loop/control/merge.lock`,
   and a wave's merge agent takes the same lock (`tools/loop_merge.py
   hold`, AUTO-06). Wave agents work in worktrees, so main stays clean
   between merge batches; the loop's whole-suite run waits while a live
   agent holds uncommitted edits (FLEET item 16 c).
6. Row files cannot conflict: a filed row and a finished row are new
   files, and the fold into ROADMAP.md happens only at /done.

### The point at which HALT is removed

HALT (`ops/loop/control/HALT`) stays through the plan landing and wave
1. It is removed by package AUTO-21, run by the session that closes the
merge batch holding AUTO-01, AUTO-02, AUTO-03, AUTO-04 and AUTO-06,
before wave 2 starts, and no later than 2026-12-04 (the launch gate
cannot flip while HALT exists).

Landed first (all at HEAD on main, whole suite green once through the
suite gate):

- AUTO-01 (parser, hand-off prefix, failed state, fix-round stop,
  preflight, `tick --dry-run --ignore-halt`);
- AUTO-02 and AUTO-03 (pruned ROADMAP, row files, loader, `DEPENDS:`);
- AUTO-04 steps 1 and 2 (no dive may start with free web tools or a
  forum source);
- AUTO-06 (reason echo, dispatch re-check, folder hold, merge lock);
- the plan's rows in ROADMAP.md, every session row tagged.

Then the six checks of F-078, each with its read-back:

1. `python tools/roadmap.py lint` exits 0 and
   `python -m pytest -q tests/test_roadmap_shape.py
   tests/test_roadmap_rows.py` is green.
2. `python tools/roadmap.py rows --open --untagged` prints only ids that
   packages.json marks `owner: loop`.
3. `python tools/al_loop.py preflight --handoff` prints `hand-off loop
   items: 0`.
4. `python tools/al_loop.py preflight` exits 0 with the client running
   (the gates of ops/loop/gates.txt once, in a lane worktree on
   unchanged main, the suite through the suite gate).
5. `python tools/usage_ledger.py gate` reads under 60 used.
6. `python tools/al_loop.py tick --dry-run --ignore-halt` lists as
   "would dispatch" only ids from check 2. (Today a dry run under HALT
   returns before the work list, tools/al_loop.py:1549-1551; AUTO-01
   adds the flag, valid only together with `--dry-run`.)

Removal: delete the marker file directly (an empty marker, replaceable;
FLEET item 9 method stated), then read back that the file is absent and
that the next tick's `ops/loop/control/progress/loop.json` does not read
`halted` and dispatched at most the ids of check 6. The scheduled task
stays installed (01-open-items L15); nothing is reinstalled.

A red check leaves HALT in place; the sources keep reading in front of
the HALT return and findings queue in `pending.json`. If HALT is still
present on 2026-12-11, the session of that day flips `GATE-POE2-10` by
hand from the pending finding.

## Refresh pipeline

One rule for all four: a test blocks drift at merge time, a daily local
check (0 runs) finds what a test cannot, and a filed row or a pre-filed
wave row does the work. Nothing here needs the operator.

### README and docs (F-146, F-020)

- `tools/docs_fresh.py check` (run by `tests/test_docs_fresh.py`): a
  table of facts computed from the tree and matched in named docs:
  Electron pin, version, Python and Node floors, port block, hotkeys,
  budget numbers, settings keys, kit version, tab names, the setup / run
  commands, the not-affiliated statement verbatim in README, and one
  index line for every decision and research file. A stale fact fails
  the test and names each stale file, so the bump lane fixes README in
  the same change.
- CLAUDE.md stops quoting values a lane must change (it names
  `app/package.json` for the Electron pin); that one edit is session
  work.
- `docs_fresh.py index --write` regenerates the decision and research
  index lines; the REL-PREP lane runs it.
- `docs_fresh.py stale` lists dated markers (PENDING, UNVERIFIED with a
  date) older than 30 days; W12 files `DOCS-FRESH-<YYYYMMDD>`, at most
  one a week.
- Narrative README text changes with the feature: plan 07 puts README.md
  or the matching doc into the files of every package that changes what
  a player sees; the REL-PREP lane checks each Added line of the notes
  against README.

### Screenshots from a supported demo mode (F-034, F-147)

- Prerequisite: `python -m server.al --demo <fixture dir>` (F-034, with
  F-001): runtime, config and fetcher in a scratch folder, the per-host
  config ignored, the Steam scan off (a missing demo log is an error),
  web data off or a loopback mock, exit 97 if any open log lies outside
  the fixture folder.
- `tools/shots.py render`: starts that demo core on a spare port of the
  8960-8979 block (a constant in `server/al/ports.py`), loads the
  fixture session, and saves PNGs of each tab (dark and light, 1440 and
  360 wide) and of the overlay page on a plain ground into `docs/shots/`
  through the one capture helper under `app/test/cdp/`, in a headless
  browser, software rendering, below-normal priority, no window. It
  refuses any core it did not start and any target that is not a page of
  that core. `docs/shots/manifest.json` records the hash of the UI
  sources and of the fixture.
- `tools/shots.py check` compares that hash only (no browser). W12 files
  `SHOTS-<YYYYMMDD>` when the hash has been stale for 3 days, no
  `wave_owned.json` holds `web/`, and no SHOTS row was filed in 7 days.
- README shows the images between two marker comments; the lane
  replaces only that block.
- The floor scan bans the protocol screenshot call, desktopCapturer,
  capturePage on a live window and OS screen grabs everywhere outside
  the helper (one allow entry). The capture is AshLight's own page on a
  demo core: never the screen, never the game, never game art; the
  fixture holds invented names only.
- The lane tool list gains `Bash(python tools/shots.py:*)`.

### Changelog and release notes (F-101, F-023)

- The generator, its groups, the commit-msg subject check and its type
  list are section 05's ("Changelog generation", package DEP-04):
  `tools/release.py notes` from first-parent subjects joined to row
  titles; the Security group keys on the commit type and the row kind,
  never on an id prefix; `CHANGELOG.md` is regenerated and tested
  against `docs/releases/`. This section adds no second rule set. The
  watcher's own commit subjects (`chore(roadmap): file <ID> (watch
  <source>)`, `chore(roadmap): done <ID> (watch <source>)`) pass that
  check.
- This section adds only `release.py notes --count` (rows merged since
  the last tag, or since the root while no tag exists, with the date of
  the oldest), read by W12 (AUTO-16).
- Each wave ends with a pre-filed `REL-PREP-<n>` row carrying `DEPENDS:`
  on the wave's rows (plan 07; section 05 runs it). Between waves W12
  files `REL-DUE-<YYYYMMDD>` (a session decision, never a bump) when at
  least 10 rows merged and 30 days passed since the last tag and no
  REL-PREP row is open.
- The REL-PREP lane also runs `docs_fresh.py index --write`,
  `docs_fresh.py check` and `shots.py check` before section 05's `bump`.
  The tag and the publish stay with section 05 and the operator's one
  phrase.
- Notes carry the not-affiliated statement and no GGG art (section 05).

### Cadence summary

- Every merge: the freshness test, the version test.
- Every local day: `refresh` source (stale markers, shots hash, notes
  count), 0 runs.
- At most weekly per kind: one DOCS-FRESH, one SHOTS, one REL-DUE row.
- Every wave end: `REL-PREP-<n>`.

## Work packages

Sizes: S up to 2 h of agent time, M up to a day. "Hotspots" names the
shared files of the task brief (state.py, web/app.js, ROADMAP.md,
CLAUDE.md) and other shared files worth a warning.

How acceptance is run: every acceptance line is a test in the test
files the package names (new or extended), run by the package agent as
`python -m pytest -q <those files>` (Q-17: a named subset, no timing
tests, under 90 s); main moves only after one whole suite through the
suite gate per merge batch. All network behaviour is proven with an
injected transport and fixtures: no acceptance test makes a real
request. Packages with no test file (AUTO-21, AUTO-25, AUTO-26) name
their read-back commands. A package id names the section (prefix
`AUTO-`); `DEP-` ids are section 05's, `GP-` ids section 04's.

### AUTO-01 LOOP-PREFLIGHT (F-024)

- Goal: the loop wastes no run and hides no work when HALT goes.
  (a) hand-off bullets are loop work only with `LOOP:`, and the BLOCKED
  test applies to them; (b) rename the dot and colon ids (`UTIL-10-...`,
  `OPERATOR-REMOTE` with `BLOCKED: operator act`) and add a lint that
  fails on a row-like bullet that does not parse or repeats an id;
  (c) `handoff_session()` matches `^SESSION:\s*(\d+)\b`; (d) `failed`
  leaves the done states, shows in the checklist and the parked list and
  gets a keep ref, with the 12 stale records of 01-open-items L4 marked
  superseded first; (e) a gate failure naming only tests outside the
  lane's diff ends the fix rounds and parks the item; (f) `al_loop.py
  preflight` (gates once in a lane worktree on unchanged main; with
  `--handoff` only the hand-off count) and `tick --dry-run
  --ignore-halt`.
- Files: tools/loop_base.py, tools/loop_roadmap.py, tools/al_loop.py,
  tools/loop_inbox.py, tests/test_al_loop.py, a new
  tests/test_roadmap_shape.py, ROADMAP.md (ids only),
  AL-NEXT-SESSION.txt (a session), ops/loop/control/loop_items/.
- Acceptance: `handoff_items` on the live hand-off yields 0 work items;
  `handoff_session` on the real line returns the number; the lint fails
  on a fixture with a dotted id and a repeated id and passes on the
  tree; a failed fixture item prints a checklist line and has a keep
  ref; a fixture gate log naming only foreign tests ends at round 0;
  `--ignore-halt` without `--dry-run` exits non-zero.
- ZERO-CLICK: the operator never has to notice a stall or a duplicate.
- Size: M. Depends on: nothing. Findings: F-024 (01-open-items L1 to
  L4).
- Parallel with: AUTO-11, AUTO-12, AUTO-14, AUTO-15. Not with AUTO-02,
  AUTO-03, AUTO-04, AUTO-06 (same loop modules).
- Hotspots: ROADMAP.md (id renames).

### AUTO-02 ROADMAP-PRUNE (F-028)

- Goal: ROADMAP.md holds open rows only; done rows move to
  `docs/roadmap/archive/2026-11.md`; the prune joins /done; the shape
  test turns green.
- Files: ROADMAP.md, docs/roadmap/archive/, tools/loop_roadmap.py,
  tests/test_roadmap_shape.py, .claude/commands/done.md (a session).
- Acceptance: the loader lists the same open ids before and after; the
  archive holds every moved row byte for byte; the shape test is green.
- ZERO-CLICK: /done prunes by itself.
- Size: S. Depends on: AUTO-01, F-017 (one ledger writer). Findings:
  F-028.
- Parallel with: nothing that edits ROADMAP.md.
- Hotspots: ROADMAP.md.

### AUTO-03 ROW-FILES (F-029)

- Goal: unattended writers create files only. `tools/roadmap.py` with
  `rows`, `lint`, `new`, `done`, `fold`; the loop reads rows through it;
  the merge writes `docs/roadmap/done/<ID>.md` instead of editing
  ROADMAP.md; `DEPENDS: <ids>` in row text; an unknown dependency reads
  "waits on <id> (no such row)"; briefs match on the exact id under
  `docs/plan/briefs/`; the row id goes into the lane's usage label.
- Files: tools/roadmap.py (new), tools/loop_roadmap.py, tools/al_loop.py,
  tools/loop_merge.py, tools/loop_prompts.py, tools/al_lane.py,
  tests/test_roadmap_rows.py (new), tests/test_al_loop.py,
  .claude/commands/done.md (a session), ROADMAP.md (header text).
- Acceptance: in a scratch clone two branches each add a row file and a
  done marker and merge with no conflict; the work list shows both; a
  fold leaves no fragment and an unchanged row set; a row depending on
  an unknown id is listed as waiting, not dispatched.
- ZERO-CLICK: rows appear and close with no hand edit.
- Size: M. Depends on: AUTO-02. Findings: F-029, Q-12.
- Parallel with: AUTO-11, AUTO-12, AUTO-14, AUTO-15.
- Hotspots: ROADMAP.md (header), tools/al_loop.py.

### AUTO-04 DIVE-FLOOR (F-171 steps 1 and 2)

- Goal: no agent or tool reads GGG's patch-notes forum. Step 1: the dive
  prompt and runbook step 1 name only operator-pasted text, public
  non-GGG repositories and GGG's API Reference and Data Exports pages;
  research 0029 gets the dated amendment. Step 2: a dive is spawned
  without WebFetch or WebSearch; every fetch goes through a new
  `tools/webfetch.py` command (over `server/al/webfetch.py`, AshLight
  User-Agent) behind one host allow-list function that refuses the
  forum, the trade site, every other GGG path, poe2db and wiki hosts,
  and logs each fetched host.
- Files: tools/loop_prompts.py, tools/loop_base.py (DEEP_EXTRA),
  tools/webfetch.py (new), tools/al_lane.py,
  docs/ops/1.0-launch-runbook.md, docs/research/0029-*.md,
  tests/test_dive_fetch.py (new).
- Acceptance: the allow-list refuses a forum URL, a trade URL, a
  `/developer/docs/changelog` URL (A-01 constant off), a poe2db URL and
  a wiki URL and passes the reference and data pages; the dive spawn
  arguments hold no WebFetch or WebSearch; every fetch of a fixture dive
  is in the host log with the AshLight User-Agent; no forum host is in
  the dive prompt or the runbook.
- ZERO-CLICK: unattended.
- Size: S. Depends on: nothing (does not wait for AUTO-05). Findings:
  F-171, Q-07.
- Parallel with: AUTO-11, AUTO-12, AUTO-14. Run after AUTO-01 or by the
  same agent (tools/loop_base.py).
- Hotspots: docs/ops/1.0-launch-runbook.md (also AUTO-07 and F-031).

### AUTO-05 WATCH-CORE (F-030)

- Goal: the frame, the two primitives and the commit path of "Design";
  the docs watch and the PoB release check become sources and keep
  their reads; both run in front of the HALT return; new sources W3, W4,
  W5 as metadata reads gated on `web_data`.
- Files: tools/upstream_watch.py (new), ops/loop/watch_rows.json (new),
  tools/al_loop.py, tools/tc_drift.py, tools/ggg_docs_watch.py,
  tests/test_upstream_watch.py (new), tests/test_al_loop.py,
  docs/decisions/0025-*.md (dated amendment).
- Acceptance: fake fetches drive each source; a token failing its
  pattern files nothing; a fourth new row in one day waits; a fourth
  done file waits, and with a gate flip and three LIVE-1 done files due
  the gate flip is committed first; a HALTed tick
  records the finding and commits nothing; a commit touching any path
  outside `docs/roadmap/new/` or `docs/roadmap/done/` is refused and
  sets COMMIT_FAULT; commits go only through fleet_gitlock; with
  `web_data` off the new sources make 0 requests (injected transport)
  while the two settled sources still read; no new source requests a
  data-file URL; every template in watch_rows.json renders to text the
  loader parses as one row with the expected id.
- ZERO-CLICK: fully unattended.
- Size: M. Depends on: AUTO-01, AUTO-03. Findings: F-030, Q-12, Q-13.
- Parallel with: AUTO-14, AUTO-15, AUTO-16.
- Hotspots: tools/al_loop.py.

### AUTO-06 WAVE-INTERPLAY (F-033)

- Goal: the contract of "Loop and wave interplay" in code: the BLOCKED
  reason echoed in the checklist; the dispatch re-check from HEAD;
  `wave_owned.json` and the `wave-hold` state; `tools/loop_merge.py
  hold -- <command>` for a wave's merge agent; the contract text for
  docs/plan/07 and 08.
- Files: tools/al_loop.py, tools/loop_merge.py, tools/loop_base.py,
  tests/test_al_loop.py, docs/plan/07-execution-plan.md,
  docs/plan/08-orchestration.md.
- Acceptance: a dry-run tick on the landed ROADMAP lists only loop rows
  as "would dispatch"; a row tagged between work list and dispatch is
  skipped; an item whose diff touches a held prefix is parked and merges
  after the hold file is removed; two holders of the merge lock run one
  after the other.
- ZERO-CLICK: the session that ends a wave flips its rows; no operator
  step.
- Size: S. Depends on: AUTO-01, AUTO-03. Findings: F-033.
- Parallel with: AUTO-11, AUTO-12, AUTO-14.
- Hotspots: tools/al_loop.py.

### AUTO-07 LAUNCH-GATE (F-052) - due 2026-12-04

- Goal: W11. The plan landing puts the two gate rows and the three
  `UTIL-10-` rows into ROADMAP.md (templates above) and retires
  `UTIL-1.0-POST` as history; the launch source flips the gates; the
  runbook gains the steps of research 0037 (bridge fix before the first
  pin move, re-read pob2_files, a new GUI reference per pin move, a
  1.0-era export fixture, Acts 5 and 6 and interlude handling).
- Files: tools/upstream_watch.py, ops/loop/watch_rows.json, ROADMAP.md
  (at landing), docs/ops/1.0-launch-runbook.md,
  tests/test_upstream_watch.py.
- Acceptance: a clock at 2026-12-10 flips nothing; 2026-12-11 with a
  fixture metadata record tagged 1.0.0 flips `GATE-POE2-10` once and its
  dependents turn dispatchable; a Preview title flips nothing; the
  source requests no data-file URL and makes 0 requests with `web_data`
  off; a fixture run-history file with an Act 5 split flips
  `GATE-ACT5-SEEN`; with run history off a ledger Act 5 hit flips it; 3
  days past the date with no signal files `LAUNCH-CHECK-<YYYYMMDD>`
  once.
- ZERO-CLICK: unattended, bar the operator's own play session that the
  floor requires of a log read.
- Size: S. Depends on: AUTO-05 (and AUTO-21 for the flip to commit).
  Findings: F-052, Q-12, Q-28.
- Parallel with: AUTO-08, AUTO-09, AUTO-10.
- Hotspots: ROADMAP.md, docs/ops/1.0-launch-runbook.md.

### AUTO-08 WATCH-HEALTH (F-125)

- Goal: W13 without its CI half: `last_ok` per source, the 3-miss tick
  line, the 7-day row, pending findings in the halted tick's checklist,
  the dev-host Checks note on a tick older than 2 h.
- Files: tools/upstream_watch.py, tools/al_loop.py, server/al/diag.py,
  tests/test_upstream_watch.py, tests/test_diag_self.py.
- Acceptance: a source failing since 8 days yields one row, once; a
  source idle because `web_data` is off yields a checklist line and no
  row; a HALTed tick's checklist lists the pending findings.
- ZERO-CLICK: unattended.
- Size: S. Depends on: AUTO-05. Findings: F-125.
- Parallel with: AUTO-07, AUTO-09, AUTO-10.
- Hotspots: server/al/diag.py (shared by several Checks packages).

### AUTO-09 ELECTRON-WATCH source (F-130, watcher half)

- Goal: W8 on the dev loop. The written upgrade policy, the setup
  refusal while the client runs and the pin file are the Electron
  section's half of F-130 (with F-037, F-044); this package adds the
  `electron` and `npm-audit` sources, the two templates and the
  end-of-life Checks note input.
- Files: tools/upstream_watch.py, ops/loop/watch_rows.json,
  tests/test_upstream_watch.py.
- Acceptance: a fixture with the line head 4 days old yields one bump
  finding, 2 days none; a second bump inside 7 days waits; a recorded
  `npm audit --json` fixture naming electron yields a `(priority)` row
  at once; a schedule fixture with the next major's .0.0 15 days old
  yields `ELECTRON-MAJOR-<MAJ>` once, and one inside the 30-day
  end-of-life window with no new major yields it once; a HALTed tick
  reads and records but files nothing; with `web_data` off 0 requests
  and the npm subprocess is not started (injected runner).
- ZERO-CLICK: unattended.
- Size: S. Depends on: AUTO-05, F-037, F-044, the F-130 decision.
  Findings: F-130, Q-13.
- Parallel with: AUTO-07, AUTO-08, AUTO-10.
- Hotspots: none.

### AUTO-10 NINJA-WATCH (F-140 layer 2 and the flag bridge)

- Goal: W6 and the dev-loop half of W7. Layers 1 and 3 in the core
  belong to the prices packages (F-085, F-140); this package reads the
  docs page daily and turns the SHAPE_DRIFT flag into a row.
- Files: tools/upstream_watch.py, ops/loop/watch_rows.json,
  tests/test_upstream_watch.py.
- Acceptance: a fixture docs page gaining a PoE2 type writes a dated
  diff naming it and yields `NINJA-DOCS-`; a policy-line change yields
  `NINJA-POLICY-`; a whitespace-only change yields nothing; with no
  contact set or `web_data` off 0 requests; a fixture flag file yields
  one `NINJA-SHAPE-` row, once.
- ZERO-CLICK: automatic.
- Size: S. Depends on: AUTO-05; the flag half on F-085 and F-140
  layer 1. Findings: F-140.
- Parallel with: AUTO-07, AUTO-08, AUTO-09.
- Hotspots: none.

### AUTO-11 DOCS-SHAPE (F-115)

- Goal: a `shape` topic in the docs watch keyed on the field names the
  readers use, on the reference and data pages only; one constant, off,
  for the other pages (A-01).
- Files: tools/ggg_docs_watch.py, tests/test_ggg_docs_watch.py; a dated
  additive note in docs/decisions/0044-*.md.
- Acceptance: a synthetic reference diff that retypes `explicitMods`
  gets topic `shape` and a note naming the field; a synthetic changelog
  diff gets no `shape` tag while the constant is off.
- ZERO-CLICK: runs on the tick, also while HALTed.
- Size: S. Depends on: nothing (the row filing half needs AUTO-05).
  Findings: F-115.
- Parallel with: everything except AUTO-05 (same file).
- Hotspots: none.

### AUTO-12 TC-DRIFT-TRIAL-FIX (F-064)

- Goal: a trial that can end green: re-hash pob2_files from the
  extracted candidate and record old and new hash plus row count;
  `trial --ref <branch or commit>` (static by default, never accepted
  by `apply`); the GUI reference keyed by tag; prune candidates other
  than the pin and the newest.
- Files: tools/tc_drift.py, tests/test_tc_drift.py,
  tests/tc_live_util.py, tests/test_tc_bridge.py; amendment lines in
  decisions 0025 and 0028.
- Acceptance: fakes prove the four parts; a rehearsal against the next
  release branch reports static-green after F-039.
- ZERO-CLICK: the static tier is unattended; the live tier stays manual
  (decision 0025).
- Size: M. Depends on: F-039. Findings: F-064.
- Parallel with: every loop package (no shared file but AUTO-05's small
  tc_drift.py hook: land AUTO-12 first or rebase).
- Hotspots: none.

### AUTO-13 DIVE-ON-DEMAND (F-171 step 3)

- Goal: a source may write `ops/loop/control/dive_request.json` (topic
  key, URLs that pass the AUTO-04 allow-list); the tick dispatches one
  dive even when not idle, at most one a day; the idle dive becomes
  weekly. Used by W4, W5 and `UTIL-10-NOTES`.
- Files: tools/al_loop.py, tools/loop_prompts.py,
  tools/upstream_watch.py, tests/test_al_loop.py.
- Acceptance: a request with open rows present still dispatches one
  dive; a second request the same day waits; a request carrying a
  refused URL dispatches nothing; at 60 percent of the cap the request
  waits.
- ZERO-CLICK: unattended.
- Size: S. Depends on: AUTO-04, AUTO-05. Findings: F-171.
- Parallel with: AUTO-14, AUTO-15, AUTO-16.
- Hotspots: tools/al_loop.py.

### AUTO-14 DOCS-FRESH (F-146)

- Goal: `tools/docs_fresh.py` with `check`, `stale` and `index
  --write`, as under "Refresh pipeline".
- Files: tools/docs_fresh.py (new), tests/test_docs_fresh.py (new),
  README.md, docs/decisions/README.md, docs/research/README.md,
  CLAUDE.md (a session: name the file that holds the pin).
- Acceptance: changing the pin in app/package.json alone fails the test
  and names each stale file; removing the not-affiliated sentence from
  README fails it; a decision file with no index line fails it; `stale`
  on a fixture with a 31-day-old PENDING marker prints it; each fact has
  a fixture test.
- ZERO-CLICK: unattended.
- Size: M. Depends on: F-023 (one version). Findings: F-146.
- Parallel with: all loop packages.
- Hotspots: CLAUDE.md, README.md.

### AUTO-15 SHOTS (F-147)

- Goal: `tools/shots.py render` and `check`, the one capture helper, the
  manifest, the README image block, the wider floor-scan ban list.
- Files: tools/shots.py (new), app/test/cdp/ (new helper), docs/shots/,
  README.md, tests/test_floor_static.py, tests/test_shots.py (new),
  tools/al_lane.py, server/al/ports.py (spare port constant).
- Acceptance: a demo start with a missing fixture log exits non-zero
  and opens no file outside the fixture folder (a planted Steam root
  with a decoy log); two renders give the same manifest; a planted
  second capture call, desktopCapturer, capturePage or OS grab anywhere
  fails the floor scan; the helper refuses a target that is not a page
  of the demo core; no window appears; the live runtime folder's mtime
  is unchanged.
- ZERO-CLICK: unattended, hidden, below-normal priority.
- Size: M. Depends on: F-034 (CORE-DEMO-MODE), F-001. Findings: F-147.
- Parallel with: all loop packages. Every capture-based acceptance of
  other sections (F-086, F-094, F-144, F-159, F-189) waits for it.
- Hotspots: README.md, tests/test_floor_static.py.

### AUTO-16 REL-NOTES (F-101)

- Goal: the `--count` option on section 05's generator and the
  `REL-PREP-<n>` row text for plan 07 (section 05 Release procedure
  step 1). The generator, the groups and the commit-msg subject check
  are section 05's package DEP-04; this package builds none of them.
- Files: tools/release.py (one option on DEP-04's `notes`),
  tests/test_release_notes.py (extended).
- Acceptance: on a fixture history with a tag and 3 later merges,
  `notes --count` prints 3 and the date of the oldest; with no tag it
  counts from the root; the watcher's two `chore(roadmap): ...` subjects
  pass the DEP-04 subject check (test calls the check function).
- ZERO-CLICK: read by the `refresh` source; no operator step.
- Size: S. Depends on: DEP-04 (section 05), AUTO-01. Findings: F-101.
- Parallel with: all watcher packages.
- Hotspots: tools/release.py (section 05's file).

### AUTO-17 REFRESH-SOURCE (W12)

- Goal: the local `refresh` source and its three templates.
- Files: tools/upstream_watch.py, ops/loop/watch_rows.json,
  tests/test_upstream_watch.py.
- Acceptance: a stale manifest for 3 days files one SHOTS row and none
  while `wave_owned.json` holds `web/`; 10 merged rows and 30 days since
  the last tag file one REL-DUE row, 9 rows or 29 days file none, and
  none is filed while a REL-PREP row is open; a 31-day-old dated marker
  files one DOCS-FRESH row; each kind files at most one row per 7 days;
  the source makes no request.
- ZERO-CLICK: unattended.
- Size: S. Depends on: AUTO-05, AUTO-14, AUTO-15, AUTO-16. Findings:
  F-146, F-147, F-101.
- Parallel with: AUTO-18.
- Hotspots: none.

### AUTO-18 LEDGER-SOURCE (W14)

- Goal: the local `ledger` source: LIVE-1 sub-row done files on a first
  live hit, `LOG-SHAPE-` on a new shape, `SNAP-<FILE>-` on a failed
  probe; `tools/live1_report.py --json` output copied into the lane
  worktree at dispatch of a `LOG-SHAPE-` or `UTIL-10-LOG` row (masked
  shapes only, never a raw line).
- Files: tools/upstream_watch.py, ops/loop/watch_rows.json,
  tools/al_loop.py, tests/test_upstream_watch.py.
- Acceptance: a fixture ledger with a first hit for one pattern writes
  exactly that row's done file; a new shape seen once files nothing,
  seen twice files one row; a fixture probe failure files one row per
  source and day; with no ledger file the source is idle and files
  nothing.
- ZERO-CLICK: unattended once the ledger consent is ticked.
- Size: S. Depends on: AUTO-05, F-061, F-143. Findings: F-061, F-143,
  Q-28.
- Parallel with: AUTO-17.
- Hotspots: tools/al_loop.py.

### AUTO-19 CI-WATCH (F-150) - blocked: the remote exists (F-021)

- Goal: `.github/workflows/watch.yml`: schedule once a day off the hour
  plus manual dispatch, a standard runner, permissions `contents: read`
  and `issues: write`, actions pinned by full commit id, no secret. It
  runs `python tools/upstream_watch.py ci` for the sources with home ci
  or both (W2 tag, W3, W4, W5, W8, `npm-audit`), compares with the tracked pins and
  a tracked baseline, opens one issue per finding (label `al-watch`,
  body exactly one line `AL-WATCH key=<source>:<key> v=1`) and closes it
  when the finding is gone. It never commits and opens no pull request.
  The tick reads the open labelled issues once per 6 h (the address from
  the checkout's own remote, never a tracked constant), accepts a key
  only from the workflow's bot account and its strict pattern, and files
  the row from its own template. The tick reads the workflow state once
  a day; not active or 48 h silent switches the dev loop to run those
  sources itself and, after 7 days, files `WATCH-BROKEN-CI-<YYYYMMDD>`.
- Files: .github/workflows/watch.yml, tools/upstream_watch.py,
  tools/al_loop.py, tests/test_ci_workflow.py (created by section 04
  GP-05; extended here), tests/test_upstream_watch.py.
- Acceptance: a recorded issue list with one valid key and one forged
  issue files exactly one row; a body with extra text is ignored; a
  workflow state of `disabled_inactivity` switches the tick to
  failover; the workflow file holds no GGG host and no poe.ninja host
  (test); the CI User-Agent names AshLight, its version and the issues
  page built from the runner's own variables (Q-03).
- ZERO-CLICK: unattended.
- Size: M. Depends on: AUTO-05, AUTO-08, F-021, F-013. Findings: F-150,
  Q-03.
- Parallel with: AUTO-20.
- Hotspots: none. Prepared and tested with fixtures before the remote;
  merged with the first commit after the operator's go.

### AUTO-20 DEPBOT-WATCH (W9) - blocked: after the public flip (F-081)

- Goal: the Dependabot alert and pull-request source in the CI job
  (adds `vulnerability-alerts: read` and `pull-requests: read`), the two
  `DEPBOT-` templates, and the dispatch wiring to
  `tools/dependabot_reapply.py` (section 04 GP-14 owns that tool, GP-08
  `.github/dependabot.yml`).
- Files: .github/workflows/watch.yml, tools/upstream_watch.py,
  ops/loop/watch_rows.json, tests/test_upstream_watch.py,
  tests/test_ci_workflow.py.
- Acceptance: a recorded alert yields one `(priority)` row; a lower-case
  advisory id is upper-cased and validated; a package name not in the
  lockfile files nothing; the soft budget gate does not hold the row; a
  recorded open Dependabot pull request yields one `DEPBOT-PR-<n>` row,
  and none while a `DEPBOT-` advisory row names the same package; a
  pull request from any other author yields nothing; the workflow file
  grants no write permission but `issues: write` (test).
- ZERO-CLICK: the lane runs from the tick; nothing is merged on GitHub.
- Size: S. Depends on: AUTO-19, F-081, GP-02 and GP-14 (section 04).
  Findings: F-081, F-150.
- Parallel with: nothing in this section.
- Hotspots: none.

### AUTO-21 LOOP-RESUME (F-078) - blocked: the six checks pass

- Goal: remove HALT at the point and by the steps under "The point at
  which HALT is removed".
- Files: ops/loop/control/HALT (removed), docs/plan/09 (the act is
  recorded as done), AL-NEXT-SESSION.txt (the paused paragraph goes).
- Acceptance: the six read-backs are in the commit message of the
  hand-off change; HALT is absent; the next real tick dispatched at most
  the ids the dry run listed.
- ZERO-CLICK: the tick resumes by itself every 15 minutes.
- Size: S. Depends on: AUTO-01, AUTO-02, AUTO-03, AUTO-04, AUTO-06, the
  plan landing. Findings: F-078.
- Parallel with: nothing (it is a point in time).
- Hotspots: none.

### AUTO-22 OVL-SMOKE-DAILY (F-199)

- Goal: the tick runs the live overlay smoke (`AL_OVERLAY_SMOKE=1`) at
  most once a day and only while the game is idle by the log-staleness
  state AshLight itself publishes; no process check.
- Files: tools/al_loop.py, tests/test_overlay_smoke.py,
  tests/test_al_loop.py.
- Acceptance: a fixture status with game_idle false runs nothing; true
  runs it once per local day; a red smoke adds one checklist line and
  files nothing by itself.
- ZERO-CLICK: unattended.
- Size: S. Depends on: AUTO-21. Findings: F-199.
- Parallel with: all.
- Hotspots: tools/al_loop.py.

### AUTO-23 DEV-LEDGERS (F-176)

- Goal: `subagent_first` joins the rotation list; the probe flags a
  docs-watch last good read older than 3 days; one-off suite logs move
  to the sidecar `Logs\dev\`.
- Files: tools/ledger_rotate.py, tests/test_ledger_rotate.py,
  server/al/probe.py (created by F-032's probe command; it does not
  exist today). The probe reads the docs watch state and, once AUTO-05
  lands, `ops/runtime/watch/state.json`.
- Acceptance: a fixture ledger over its cap rotates; a 4-day-old read
  raises the probe flag.
- ZERO-CLICK: unattended.
- Size: S. Depends on: F-032. Findings: F-176.
- Parallel with: all.
- Hotspots: none.

### AUTO-24 POLICY-QUOTES (F-051) - blocked: operator decision A-01

- Goal: W15, built only after the operator's floor line.
- Files: tools/ggg_docs_watch.py, server/al/diag.py,
  tests/test_ggg_docs_watch.py, tests/test_policy_wording_watch.py,
  ops/loop/watch_rows.json.
- Acceptance: a fixture page missing quote O3 raises the flag and names
  O3; the real cached page raises nothing; whitespace reflow raises
  nothing.
- ZERO-CLICK: unattended.
- Size: S. Depends on: A-01, AUTO-05. Findings: F-051.
- Parallel with: all but AUTO-11 (same file).
- Hotspots: server/al/diag.py.

### AUTO-25 KIT-REPORT (F-203) - send blocked: no outbound path

- Goal: draft one note for the fleet owner now (the double ticket read
  in the kit suite gate, the one-suite-per-tree leak through the lane
  slot, the peer gaps of research 0057, the wish for a 3:1 edge token),
  with line numbers and evidence, no path, id or address; send it once
  `loop.dest_inboxes` names the fleet owner.
- Files: a draft under `ops/runtime/` (gitignored) until it is sent.
- Acceptance: the draft passes the leak sweep; after the send, the
  destination copy re-hashes equal and the reached count is reported
  (FLEET item 7).
- ZERO-CLICK: sent by the tick's note path once the entry exists.
- Size: S. Depends on: the operator act below. Findings: F-203.
- Parallel with: all. Hotspots: none.

### AUTO-26 WT-SIDECAR-WIRE (F-057) - operator act first

- Goal: after the operator pastes the two WorktreeCreate hook entries
  into `.claude/settings.json`, a session proves one isolated spawn
  lands under the sidecar Worktree folder and un-skips the test.
- Files: tests/test_wt_sidecar_hook.py; ROADMAP.md (the row reopens as
  WT-SIDECAR-WIRE at landing).
- Acceptance: the spawn's worktree path is under the sidecar; the
  un-skipped test passes.
- ZERO-CLICK: every later wave spawn lands in the sidecar by itself.
- Size: S. Depends on: the operator act. Findings: F-057.
- Parallel with: all. Must precede wave 1's first isolated spawn.
- Hotspots: ROADMAP.md.

## Order

Critical path to a running loop:
AUTO-01 -> AUTO-02 -> AUTO-03 -> AUTO-06 -> (AUTO-04 beside them) ->
plan rows landed and tagged -> AUTO-21 (HALT removed).

Critical path to the dated event (2026-12-11):
AUTO-03 -> AUTO-05 -> AUTO-07, proven with the fake clock and landed by
2026-12-04; AUTO-21 no later than the same day. F-039 (bridge shape) and
AUTO-12 before the first pin move of the 1.0 era.

Then, in any order after AUTO-05: AUTO-08, AUTO-09 (after F-037 and
F-044), AUTO-10, AUTO-13, AUTO-18 (after F-061 and F-143).

Refresh track, independent of the loop track until its last step:
F-023 (section 05 DEP-03) -> AUTO-14; DEP-04 -> AUTO-16; F-001 ->
F-034 -> AUTO-15; then AUTO-17.

After the operator's go for the remote: AUTO-19, then AUTO-20 after the
public flip.

What must come first, in one line each:
- AUTO-01 before anything else that touches the loop modules.
- AUTO-04 before HALT is removed (floor).
- AUTO-26's operator act before wave 1 spawns isolated agents.
- AUTO-11 and AUTO-12 can start in wave 1; they need nothing.

## Decisions

Rulings this section relies on: Q-03 (CI User-Agent contact), Q-04
(snapshot at start time, never from the loop or the core), Q-07 (GGG
clause binds research reads), Q-12 (add-only row files), Q-13 (read
while HALTed, act no), Q-17 (subset runs, one whole suite per merge
batch), Q-23 (the remote is the operator's go), Q-28 (run history opens
UTIL-10-LOG); operator decision A-01 (pending, default no).

Decisions to record at landing (numbers assigned later):

- Amendment to decision 0025 (dated 2026-11-18, cross-reference 0044).
  Decision: the tick may commit add-only row files
  (`docs/roadmap/new|done/<ID>.md`) built from tracked templates and
  validated tokens, at most 3 a local day, with the operator identity,
  only through the kit git lock, never while HALT exists; the release
  check reads in front of the HALT return and acts on nothing while
  HALTed; pin moves stay session commits. Alternatives: edit ROADMAP.md
  in place (merge conflicts with waves); report only (rows wait for a
  human). Why: an unattended commit that can only add a file cannot
  break a row or a wave merge. Reverses if: a tick commit ever touches a
  non-row path, a bad row lands, tokens fail validation, GitHub limits
  bar the daily read, or the operator rules unattended commits or
  HALT-time reads unwanted.
- Upstream watcher frame. Decision: one tool and one state file for
  every upstream source; new sources read repository metadata only and
  only while the dev host's `web_data` is on; the docs watch and the
  release check keep their settled reads; CI reads GitHub and public
  registries only, never a GGG host or poe.ninja, and never commits; row
  text comes only from tracked templates. Alternatives: one tool per
  source (three state files, three silent failure modes); watchers in
  the shipped core (decision 0044 rejected it); CI reading poe.ninja
  (needless traffic). Why: one frame makes each source about 30 lines
  and one health check covers all. Reverses if: a source's owner asks
  tools not to read it automatically, the metadata-only rule hides a
  break that only a data read shows, or the operator exempts a source
  from the web-data gate in writing.
- Loop and wave contract. Decision: BLOCKED means "not for the loop"
  with a reason the checklist echoes; the hand-off is loop work only by
  a `LOOP:` prefix; a session claims by tag-then-read and the loop's
  record wins; the folder hold and the shared merge lock; HALT is
  removed only after the six checks. Alternatives: HALT during every
  wave (the launch gate and advisory rows would stall); a lock file per
  row (more state than a tag). Why: one visible word in the row is the
  whole protocol. Reverses if: a row is worked twice in practice, or
  the tag traffic on ROADMAP.md causes merge conflicts.
- Research dive sources. Decision (Q-07, F-171): a dive has no free web
  tools; every fetch passes one host allow-list in code with the
  AshLight User-Agent; GGG is read only at the API Reference and Data
  Exports pages; research 0029 and runbook step 1 are amended.
  Alternatives: prompt wording only (not enforceable); forum reads under
  robots rules (outside the floor text). Why: the floor is enforced by
  code and spawn arguments. Reverses if: the operator amends the floor
  or GGG documents the forum as a permitted source.
- One capture path. Decision (F-147): screenshots are taken only of
  AshLight's own page on a demo core, through one helper, in a headless
  browser; the floor scan bans every other capture call. Alternatives:
  desktop captures (floor), hand-made screenshots (drift, reminders).
  Why: the README can show the product with no screen read and no game
  art. Reverses if: the helper cannot render a state a design check
  needs, or the floor's capture rule changes.
- Refresh pipeline. Decision (F-146, F-147, F-101): facts in docs are
  tested against the tree; screenshots are judged stale by an input
  hash; a daily local check files at most one row a week per kind; the
  changelog is section 05's one generator (its decision), run at each
  release, and between releases the watcher only asks a session whether
  a milestone is due (REL-DUE), never bumps. Alternatives: a periodic
  notes-draft row (it would trigger section 05's bump and break
  "releases only at a milestone"); a hand-kept changelog. Why: drift is
  blocked at merge time, and what a test cannot see costs 0 runs to
  find. Reverses if: the freshness test blocks good merges more than
  once a month, or section 05's release trigger changes.
- CI issue protocol. Decision (F-150, Q-03): one labelled issue per
  finding with a one-line key body from the workflow's bot account; the
  tick trusts only that account and the key pattern; failover to the dev
  loop when the workflow is not active or 48 h silent. Alternatives: a
  CI commit of a state file (FLEET item 17); a stored token on the dev
  host (0037-X7). Why: an issue is the only write a no-secret job needs.
  Reverses if: anonymous issue reads are refused (unverified until the
  remote exists) or issue spam makes the label unusable.
- Dated additive note to decision 0044: the `shape` topic on the
  reference and data pages (F-115). No change to the six-page read
  (A-01 is the operator's).
- Electron upgrade policy (F-130): recorded by the Electron section;
  this section only relies on it.

## Operator acts

Each goes into the one batched ask (docs/plan/09, F-040).

1. A-01: write one floor line saying whether GGG's developer-docs pages
   outside the API Reference and Data Exports may be read. Why no agent
   can: only the operator may word the floor. Blocks AUTO-24 and the
   changelog parts of AUTO-11 and AUTO-04. Default until then: no new
   work reads those four pages, and the settled decision 0044 watch is
   left as it is. An explicit "no" files a session row that narrows the
   0044 watch to the two pages; `TC-OAUTH-REG-OPEN` (it keys on the
   authorization page's REG_OPEN flag) then needs another signal and
   that row says so.
2. Q-23: create the private repository, approve the first push and
   later the public flip. Why: the operator's recorded go (order of
   2026-11-16). Blocks AUTO-19 and AUTO-20; until then every source
   runs on the dev loop only.
3. F-057: paste the two WorktreeCreate hook entries into
   `.claude/settings.json`. Why: an agent may not edit settings. Blocks
   AUTO-26.
4. F-061: tick the new ledger consent line once in Settings. Why:
   consent is the player's. Without it W14's log half stays idle and
   `GATE-ACT5-SEEN` relies on run history alone.
5. Turn `web_data` on and set the contact on the dev host (batched ask
   item g, F-040). Why: a per-host opt-in and a personal value in a
   gitignored file. Without `web_data` W3, W4, W5, W6, W8 and
   `npm-audit` stay idle (one checklist line) and `GATE-POE2-10` can
   only be flipped by hand after `LAUNCH-CHECK-`; without the contact
   W6 stays idle.
6. Play one session after the 1.0 launch with AshLight running. Why:
   the floor allows a log read only of the operator's own play. It
   opens `UTIL-10-LOG` by itself; no report is needed.
7. Give the fleet owner's inbox as a `loop.dest_inboxes` entry in the
   gitignored per-host config (or have the fleet owner supply it). Why:
   it is a location outside this tree. Blocks the send of AUTO-25.
8. Optional (Q-07): paste the 1.0 patch notes once into a text file
   under the sidecar Scratch folder for `UTIL-10-NOTES`. Default: the
   dive works from public repositories and the two docs pages.
9. Optional: say in writing that the Electron source may read while the
   dev host's `web_data` is off. Default: it waits for `web_data`.

Not operator acts: removing HALT (AUTO-21, a session), the tag and
publish phrase (section 05).

## Risks and fallbacks

- R1 The dev host's `web_data` goes off and the new sources go blind.
  Fallback: watch health prints `idle: web data off` in every checklist;
  after go-public CI covers W2 to W5 and W8; the two settled sources
  read regardless.
- R2 The dev host is off or the operator is logged out (the task runs
  only while logged on). Fallback: CI after go-public; before it,
  missed starts run when possible and each source catches up by its
  cadence gate.
- R3 A bad row is filed. Bounds: templates and token patterns, the
  3-a-day cap, the loader parse, add-only files. Fallback: a session
  writes the done file for it; COMMIT_FAULT stops filing on any
  unexpected commit shape.
- R4 A filed row burns runs on a gate failure no lane can fix. Bound:
  AUTO-01 (e) ends the fix rounds at once and parks the item visibly;
  templates never ask for a decision.
- R5 HALT is still present at the launch. Fallback: the gate finding
  waits in the halted checklist; the session of the day flips the gate
  by hand; the release check and the docs watch read throughout.
- R6 A preview tree or a slipped launch flips the gate early. Bound:
  date and a non-preview upstream version are both required; the
  Preview filter has a test; `LAUNCH-CHECK-` covers silence.
- R7 Scheduled workflows run late, are dropped, or stop after 60 days
  without repository activity. Fallback: the daily workflow-state read,
  failover to the dev loop, `WATCH-BROKEN-CI-` after 7 days.
- R8 Anonymous issue reads may not work as assumed (unverified until
  the remote exists). Fallback: the dev loop runs the CI sources itself;
  nothing depends on the issue read.
- R9 Headless rendering costs frame time during play. Bound: software
  rendering, below-normal priority, no window, at most one SHOTS row a
  week. Fallback: move the render behind the log-staleness idle state
  as AUTO-22 does.
- R10 A wave ends early and leaves rows tagged or `wave_owned.json` in
  place. Bound: tagged rows stay listed every tick; a hold file older
  than 48 h is reported. Nothing is lost, only delayed.
- R11 The ledger consent stays off, so `UTIL-10-LOG` opens with no
  shape report. Cost: one lane and one verifier, then the item parks
  for a session. Fallback: the session works it from a live read-back.
- R12 Docs freshness patterns are brittle and block a good merge.
  Bound: each fact has a fixture test and names the stale file.
- R13 The GitHub address quota (60 an hour, shared) is used up by other
  tools on the host. Bound: about 13 reads a day, ETag where given;
  a rate-limit reply sets the source's next run to the reset time.
- R14 Preflight is red because a test is tied to live processes on the
  host (research 0058 F4). Fallback: HALT stays; the fix is the tests
  section's (F-022); AUTO-01 (e) keeps such a failure from costing fix
  rounds once the loop runs.
- R15 The poe.ninja docs page reflows and files noise. Bound: the hash
  is of normalised text between two anchors; one NINJA-DOCS row a week
  at most.

## Verification

Independent verifier pass, 2026-11-18, against HEAD 30b6bbe and the
draft sections 04 and 05 present in the tree.

Checked:

- Yardstick G point by point: README, docs, screenshots and changelog
  refresh (W12, Refresh pipeline, AUTO-14 to AUTO-17); GGG developer
  docs (W1, settled 0044); PoB-PoE2 releases (W2, settled 0025) and the
  next release (W3); poe.ninja response shapes (W7) and docs page (W6);
  the repoe-fork snapshot (W4); the GGG passive tree export (W5);
  Electron security releases (W8); Dependabot (W9). Every watcher acts
  inside its decision or files a row; the runs cap (Runs budget, 32 of
  117) and FLEET item 14 (no watcher note, inbox folded into the tick)
  hold. What cannot be automated is listed once under Operator acts.
- Repo claims, opened: tools/al_loop.py:1543 `tick`, :1547 docs watch
  before HALT and skipped on a dry run, :1549-1551 HALT return, :1525-1528
  `handoff_session` with the `\s*$` defect, :1714 `--dry-run` only;
  tools/loop_base.py:57 HEADROOM = 3, :109-111 ROW_ID / ROW_RX, :112
  continuation rule, :133 DEEP_EXTRA, :238-240 `loop.dest_inboxes`;
  tools/loop_roadmap.py:29 `roadmap_rows`, :60 `flip_roadmap`, :269
  `handoff_items`; server/al/webfetch.py `request`, `user_agent`,
  `WebDataOff`; tools/tc_drift.py `check`, `trial --tag --live`,
  `apply`, `status`; tools/usage_ledger.py `gate`; the AL runs cap of
  120 in the machine lanes config; ROADMAP ids LIVE-1, TC-OAUTH-REG,
  UTIL-1.0-POST; every test and tool named as existing exists. Named as
  new and absent today, correctly: tools/upstream_watch.py,
  tools/roadmap.py, tools/webfetch.py, tools/docs_fresh.py,
  tools/shots.py, tools/live1_report.py (F-061), tools/release.py
  (section 05), config/electron_pin.json (F-044), server/al/probe.py
  (F-032), tests/test_ci_workflow.py (section 04 GP-05),
  tests/test_roadmap_shape.py, tests/test_upstream_watch.py.
- All 24 row templates re-run through the loop's own parser (see the
  catalogue note); no template id collides with an existing ROADMAP id
  except the two hyphen extensions named there.
- Findings: every F-id cited exists in docs/plan/findings.json; nothing
  relies on a not-adopted item; the blocked items (F-021, F-051, F-057,
  F-061 consent, F-078, F-081, F-150, F-203) appear only as blocked
  packages or operator acts; 0058-X1 to X11 stay rejected.
- Rulings Q-03, Q-04, Q-07, Q-12, Q-13, Q-17, Q-23, Q-28 and operator
  decisions A-01, A-02, Q-05 read against the text; the floor read
  strictly: no new GGG page beyond the two sets, no data-file download
  by the loop or CI, no trade site, no capture outside the one
  demo-core helper, no process-list check, no input, every request with
  the AshLight User-Agent (npm through F-037's `.npmrc`).
- Settled decisions 0009 (with Q-04), 0013, 0025, 0029, 0044 are not
  contradicted; FLEET items 9, 10, 13, 14, 16 and 17 hold (no bot
  author, no merge on GitHub, pushes only by section 04's guarded path,
  releases only at a milestone or on an explicit request).
- Order: the dependency graph of AUTO-01 to AUTO-26 has no cycle; the
  dated path AUTO-01 -> AUTO-02 -> AUTO-03 -> AUTO-05 -> AUTO-07 fits
  before 2026-12-04.
- Inputs 0058 (R1 to R12, catalogue, templates, loop and waves, cut,
  rejected, open questions), 0036 R6, 0037 R2 / R5 / R7, 0046 R1 and
  R9, 0051 R1 and R10, and 01-open-items L1 to L4, L12, L15, R1, R9.

Corrected (16):

1. W2: under HALT the static trial now runs, as Q-13 rules ("static
   trial only"); the draft stopped it.
2. G4, the two primitives and AUTO-05: done files get their own cap of
   3 a day and gate flips go first, so a burst of LIVE-1 done files on
   launch day cannot hold `GATE-POE2-10` or `GATE-ACT5-SEEN`; Q-12's
   "3 filed rows" stays the new-row cap.
3. W8 and AUTO-09: the dev loop had no advisory source before the
   remote exists; added the `npm-audit` source (after F-037).
4. W8: research 0046 R1 (c), adopt the next major 14 to 42 days after
   its .0.0, was dropped; `ELECTRON-MAJOR-<MAJ>` replaces the EOL-only
   row and covers both triggers.
5. W9: row prefix `DEP-` collided with section 05's `DEP-` package ids;
   now `DEPBOT-`.
6. W9 and AUTO-20: weekly Dependabot version-update pull requests had
   no trigger; added `DEPBOT-PR-<n>`.
7. W9 and AUTO-20: the push is done by section 04's GP-14 tool through
   GP-02's guarded hook, not an unnamed push worker; dependencies added.
8. Refresh pipeline and AUTO-16: the generator, groups and commit-msg
   type list now defer to section 05 (final), which keys Security on
   the commit type, never an id prefix; AUTO-16 shrinks to `--count`.
9. W12, AUTO-17 and Decisions: a between-wave `REL-PREP-<date>` row
   would have run section 05's bump outside a milestone; replaced by
   `REL-DUE-<date>`, a session decision that never bumps.
10. W0: release builds poll poe.ninja only after its yes (F-046, Q-05).
11. Operator act 1: what an explicit "no" on A-01 does to the 0044 watch
    and to `TC-OAUTH-REG-OPEN`.
12. Operator act 5: `web_data` on the dev host is needed by W3 to W6, W8
    and the launch gate's upstream signal, not only the contact.
13. AUTO-23: server/al/probe.py does not exist; F-032 creates it.
14. AUTO-19: tests/test_ci_workflow.py is created by section 04 GP-05.
15. Template check re-run on 24 templates; the LIVE-1 hyphen extension
    added; the word DEPENDS removed from a template body.
16. Work packages: how acceptance is run (Q-17 subsets, injected
    transport, read-backs) stated once; request counts updated.
