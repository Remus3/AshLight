# 01 - Open items

Date: 2026-11-18. Ultraplan plan section (docs/plan/README.md), section D.
Status: final

Scope: every open item the plan must carry, drafted at HEAD a55fb3b and
re-checked at HEAD 1f2d537 (see Verification), plus the
untracked research drafts of this session. Sources: ROADMAP.md (2061
lines), AL-NEXT-SESSION.txt (141 lines), docs/decisions/, docs/audit/,
the loop code (tools/loop_base.py, tools/loop_roadmap.py, tools/al_loop.py),
the core (server/al/), tests/ and the runtime files under ops/loop/control/.
Sibling notes are cited as N<number> (N48 = docs/research/0048-...).
Web check: PoE2 1.0 launches 2026-12-11 (rpgsite.net news 21188 and the
Epic Games Store news post, both accessed 2026-11-18, re-found by the
verifier the same day); the 1.0 ascendancy names stay UNVERIFIED (the
coverage names a new Duelist class). GGG OAuth registration: closed (the
developer docs index page says it cannot process new applications, and
that standalone apps must use a public client; accessed 2026-11-18).

## Summary

- Open ROADMAP rows: 14 (13 IDs plus the OPERATOR GitHub-remote bullet).
- Hand-off carried items: 16 top-level (15 "Carried forward" bullets plus
  the session-start REG_OPEN check), 38 sub-items under them.
- Items with no ROADMAP row: 13 (each gets a proposed row below; the
  draft's LOOP-ITEMS-TIDY is merged into LOOP-PARSER-FIX).
- Loose ends found in code and docs: 18 (L1 to L18).
- Ranked recommendations: 9 (R1 to R9, section "Recommendations").

By type (the 14 rows plus the 13 no-row items, 27 in all; each counted
once under its main type):
- live-game check: 9 (LIVE-1, TEST-LIVE-CLICKS, OVL-BUDGET, OVL-FPS,
  TC-BUILDFILE-LIVE, LIVE-WAYSTONE, LIVE-SEARCHSTR, LIVE-FILTER,
  LIVE-FILTER-MERGE)
- code or docs: 9 (AUDIT-P8-LOW, CODE-HEALTH-FOLLOWUP,
  MERGE-SEAMS-FOLLOWUP, S5-FOLLOWUP, LIVE-VERDICTS, LOOP-PARSER-FIX,
  CORE-LOG-NO-FALLBACK, CORE-DEMO-MODE, DOC-DECISION-TIDY)
- external wait: 4 (TC-OAUTH-REG, TC-IMPORT, TC-CURX, UTIL-1.0-POST)
- operator act or decision: 4 (OPERATOR GitHub remote, OP-PHONE-LAN,
  WT-SIDECAR-WIRE, LOOP-RESUME)
- fleet: 1 (FLEET-KIT-GATE-REPORT)
Outside the 27: the OP-ACTS batch (8 lettered acts, mapped onto rows or
kept optional) and 3 hand-off NOTEs (one obsolete, one test flake, one
informational).

By who or what unblocks:
- a normal session or wave, no operator: 9 code items plus the
  "next step" of every live check (ledger, verdict card, budget log).
- normal play by the operator while the core runs, no extra act once
  the passive capture lands: LIVE-1, TEST-LIVE-CLICKS, OVL-BUDGET.
- one explicit operator act in the batched ask (docs/plan/09): OVL-FPS
  (one map with the game's FPS display on), TC-BUILDFILE-LIVE,
  LIVE-FILTER / LIVE-FILTER-MERGE, LIVE-SEARCHSTR, GitHub remote,
  WT-SIDECAR-WIRE, autostart, UA contact / web_data, NLM wording, 0017
  review, phone / LAN decision.
- GGG: TC-OAUTH-REG (registration reopens), then TC-IMPORT and TC-CURX.
- the calendar: UTIL-1.0-POST (2026-12-11).
- MAIN / fleet: FLEET-KIT-GATE-REPORT (a delivery path to MAIN).
- the plan itself: LOOP-RESUME (07-execution-plan names the HALT removal).

## Items

### LIVE-1
- Source: ROADMAP.md:9-31; AL-NEXT-SESSION.txt:62-63.
- Remaining work: live sightings plus fixture and test for 11 shapes:
  death, whisper (in and out), trade templates (then swap the HUD-WHISPER
  fixture whispers for anonymised real-shaped ones), party chat, guild
  chat, AFK / DND, joined / left, Trade accepted, hideout scene names,
  cruel `C_G<n>_` and interlude `P<n>_` area-id prefixes (acts.act_of,
  decision 0020), endgame `Map` prefix on a real map (acts.is_endgame).
- Type: live-game check.
- Blocked by: no live sighting of those lines yet; today the only way to
  learn what was seen is a person reading Client.txt.
- Unblocked by: the operator's normal play (any session that dies once,
  enters a hideout, gets one whisper) once a passive parse ledger exists.
- Next step that needs no operator: build N51 R1 OBS-PARSE-LEDGER (hit
  counts per pattern id plus masked shapes of unparsed lines in a bounded
  ops/runtime/logshapes.json, hook at Core.feed_line) and
  tools/live1_report.py printing VERIFIED live / NOT SEEN / NEW SHAPE per
  LIVE-1 item. Split LIVE-1 into one row per shape (N51 "LIVE-1 is one row
  for 11 remaining items") so each closes on its first live hit.
- Proposed disposition: package in wave 1 (ledger + report), then a loop
  row per shape; the row's BLOCKED word goes once the ledger lands.
- Least-operator-effort way: zero extra acts. The operator plays as usual;
  the next session runs `python tools/live1_report.py` and turns each
  VERIFIED shape into a fixture from the masked shape (never a raw line).
- ToS check: "READ ONLY ... Client.txt (tailed only after the user's
  opt-in)": the ledger reads only lines the consented tailer already
  reads, stores masked shapes, no raw text, no network.

### TEST-LIVE-CLICKS
- Source: ROADMAP.md:50-55; AL-NEXT-SESSION.txt:63-64.
- Remaining work: one live run that reaches town or hideout, with zone,
  character, level, act and session timer read back from /api/state.
- Type: live-game check.
- Blocked by: nobody has logged in while the core ran since the first
  live check (ROADMAP.md:28-31).
- Unblocked by: the operator's next normal login with the client running.
- Next step that needs no operator: a read-back script
  (tools/live_readback.py, or a section of live1_report.py) that checks
  the ledger and a saved /api/state snapshot for the five fields; the
  loop tick runs it after the next game_idle -> active edge.
- Proposed disposition: fold into LIVE-1's ledger package; the row closes
  on the first passive read-back with all five fields set.
- Least-operator-effort way: zero extra acts (normal play).
- ToS check: the row's other unblock path, "a desktop-tool grant to the
  lane" (ROADMAP.md:54), means a tool clicking Login in the game client,
  which is synthesized input to the game ("NEVER send input to the game ...
  not even a synthesized Ctrl+C"). It is moved to Rejected below and must
  be struck from the row text.

### OVL-BUDGET
- Source: ROADMAP.md:56-62; AL-NEXT-SESSION.txt:64-65.
- Remaining work: the active figure (overlay updating in a map) against
  the decision 0002 RAM / CPU budget, or a Tauri / native ruling.
- Type: live-game check.
- Blocked by: no measurement while a map runs.
- Unblocked by: normal play once AshLight logs its own footprint.
- Next step that needs no operator: N48 R4 BUDGET-LOG: the client main
  process logs app.getAppMetrics() per process once a minute and the core
  its own working set / CPU, each row tagged game idle / active / in map /
  overlay shown, bounded file in <sidecar>\Logs (1 MB cap), one Checks
  row. N48 states R4 "closes OVL-BUDGET with no operator action".
- Proposed disposition: package in wave 1 with the ledger (same
  observability package as N51 R4); row closes from the log.
- Least-operator-effort way: zero extra acts.
- ToS check: "NEVER read or write game process memory" and decision 0029
  (no process-list check): only AshLight's own processes are measured.

### OVL-FPS
- Source: ROADMAP.md:63-70; AL-NEXT-SESSION.txt:64-65, 70-71 (act a).
- Remaining work: in-map FPS from the game's own FPS display, overlay off
  vs idle vs updating, Windowed Fullscreen; accept under 1 percent average
  loss, 1 percent lows unchanged within noise; numbers into decision 0002.
- Type: live-game check (needs the player's eyes on the game's counter).
- Blocked by: decision 0006 bars PresentMon / ETW of the game, so only
  the player can read the game's FPS display.
- Unblocked by: the operator, one normally played map (act a).
- Next step that needs no operator: N48 R5 OVL-CHECK
  (tools/ovl_check.py arm): a session arms it, it starts by itself 20 s
  into an open map and cycles the overlay hidden / shown / updating in
  nine 30 s blocks (showInactive, no focus move), logging the block
  schedule so the operator's FPS readings line up afterwards; N48 open
  question 1 asks an adjudicator whether the acceptance becomes a
  system-wide GPU proxy.
- Proposed disposition: wave 1 builds R5; the act joins the operator
  batch (09) as "play one map with the FPS display on; note avg and low
  per block" (or a dashboard form after the map, see LIVE-VERDICTS).
- Least-operator-effort way: one map the operator plays anyway; the
  schedule is automatic; the operator types 9 numbers or 2 (shown vs
  hidden) into the dashboard once.
- ToS check: no game hook, no present tracing (decision 0006), no input;
  hiding the overlay is AshLight's own window.

### TC-OAUTH-REG
- Source: ROADMAP.md:274-279; AL-NEXT-SESSION.txt:13-15, 33-37.
- Remaining work: apply to GGG for a public PKCE client (scopes
  account:profile, account:characters; loopback redirect in 8960-8979).
- Type: external wait, then operator act.
- Blocked by: GGG registration closed. Read back 2026-11-18: sidecar
  Cache\ggg_docs\state.json "reg": "closed", checked
  2026-11-18T02:06:44Z, 6 of 6 pages read; ops/runtime/ggg_docs/ does not
  exist (no change yet, so no REG_OPEN flag). N35 F1: it closed and
  reopened before.
- Unblocked by: GGG; GGG-DOCS-WATCH (decision 0044) raises REG_OPEN and a
  Checks note within 24 h.
- Next step that needs no operator: prepare the application text and the
  redirect / scope list as a ready file (N35 F2 lists what an application
  held); nothing to build.
- Proposed disposition: operator batch, conditional ("apply when REG_OPEN
  appears"); the session-start check stays automated.
- ToS check: "never require or store a POESESSID": OAuth is GGG's
  documented path.

### TC-IMPORT
- Source: ROADMAP.md:280-284; AL-NEXT-SESSION.txt:38-40.
- Remaining work: PKCE sign-in, GET /character/poe2[/name], tokens in the
  OS credential store, refresh, into the build model.
- Type: external wait (on TC-OAUTH-REG).
- Blocked by: TC-OAUTH-REG.
- Unblocked by: GGG reopening registration plus the operator's apply.
- Next step that needs no operator: N35 R1 (bring theorycraft charjson to
  the shapes GGG documents today) and a mocked PKCE flow behind the
  existing ggg_api provider stub (decision 0045), so the row is only the
  client id away.
- Proposed disposition: package the mocked groundwork in a later wave;
  keep the row BLOCKED.
- ToS check: documented API only, no POESESSID, truthful UA.

### UTIL-1.0-POST
- Source: ROADMAP.md:530-551; AL-NEXT-SESSION.txt:68-69; runbook
  docs/ops/1.0-launch-runbook.md.
- Remaining work: checklist items 1-8 (patch notes, fixture new lines,
  confirm G5_ / G6_ prefixes, refresh world_areas, 1.0 ascendancies,
  tree export plus id_match guard, poe.ninja league label, TC-DRIFT on a
  PoB 1.0 release).
- Type: external wait (calendar).
- Blocked by: PoE2 1.0 ships 2026-12-11 (confirmed, see header).
- Unblocked by: the date; no operator act except playing 1.0.
- Next step that needs no operator: the loop cannot see this row at all
  (L1: the dot in the id fails ROW_RX). N58 R3 LAUNCH-GATE replaces it
  with a gate row and three parseable rows (UTIL-10-...) before
  2026-12-10, and N58 R2 watches upstream versions so the gate flips
  itself. The parse ledger (LIVE-1) catches changed 1.0 line formats
  within minutes of the first 1.0 session (N51 R1).
- Proposed disposition: rename and split in wave 1 (with LOOP-PARSER-FIX);
  execution on 2026-12-11 as a loop row.
- ToS check: data refresh from repoe-fork / GGG exports at build time only
  (decision 0009); no game file read beyond Client.txt.

### TC-BUILDFILE-LIVE
- Source: ROADMAP.md:570-575.
- Remaining work: load one AshLight-made .build in game; record whether it
  loads, which passives / gems show, whether class-start, placeholder ids
  or meta gems are refused; fix the mapping if refused; note in research
  0027.
- Type: live-game check (operator act: the player places the file).
- Blocked by: decision 0034: the app never writes the planner folder; only
  the player can place the file and open it.
- Unblocked by: the operator, once (2 minutes).
- Next step that needs no operator: the LIVE-VERDICTS card (no-row item
  below) so the result is recorded by a click, not prose.
- Proposed disposition: operator batch, item "save .build, open it in
  game, press Worked / Refused on the Checks tab".
- Least-operator-effort way: one download click, one file move by the
  player, one verdict click.
- ToS check: "never ... modify any game file" and decision 0034: the
  player saves it; AshLight writes nothing into the game's folders.

### TC-CURX
- Source: ROADMAP.md:618-624; AL-NEXT-SESSION.txt:39-40.
- Remaining work: hourly exchange history from GGG's documented Currency
  Exchange API, OAuth UA, immutable-hour cache, parser tests.
- Type: external wait (on TC-OAUTH-REG).
- Blocked by: adjudicator ruling 2026-11-17: standalone executables must
  use a public OAuth client (N35 F11 confirms it stays blocked for us).
- Unblocked by: TC-OAUTH-REG, or GGG exempting scope-less endpoints in
  writing.
- Next step that needs no operator: parser and cache against a fixture
  written by hand from the response shape GGG's API Reference documents
  (never a recorded live call: that call needs the OAuth client), off by
  default.
- Proposed disposition: keep BLOCKED; package groundwork with TC-IMPORT.
- ToS check: API Reference endpoint only, headers obeyed dynamically.

### AUDIT-P8-LOW
- Source: ROADMAP.md:1981-1995; AL-NEXT-SESSION.txt:47-55;
  docs/audit/2026-11-17-audit.md "Pass 8" (lines 882-950).
- Remaining work: P8-3 app/main.js corePort without the 8960-8979 check;
  P8-4 core --port outside the block still binds (server/al/__main__.py:
  154-155 only warns; refuse, 0 for tests); P8-5 tick_ladder re-dedupe
  (about 10 ms per 0.5 s tick at 200 + 500 maps, N48 cites it); P8-6
  console / CSP test never paints Checks rows, a hint or ladder_all; P8-7
  diag.redact blanks words in fixed report text; P8-8 "This session"
  ladder and Maps card mix characters after a switch.
- Type: code.
- Blocked by: nothing.
- Unblocked by: any wave.
- Next step that needs no operator: the row itself (fix plus one test each).
- Proposed disposition: package in wave 1 (P8-3 / P8-4 with N45's local
  surface package; P8-5 with N48; P8-7 with N51 R6 report text).
- ToS check: no floor rule touched; P8-7 tightens redaction.

### CODE-HEALTH-FOLLOWUP
- Source: ROADMAP.md:2012-2024; AL-NEXT-SESSION.txt:56-61;
  docs/audit/code-health-2026-11-17.md:56, 97, 106.
- Remaining work: (1) state.py card / event text split plus the four
  places keyed on server/al/state.py (tools/design_gate.py, the
  design-reviewer agent, loop_prompts, design docs 0001 / 0002); (2) web/
  pad / duration / clock helper dedup; (3) runtime pid / state / heartbeat
  files written CRLF (core.write_private, procs.record_overlay,
  keepalive._write_state, __main__.write_heartbeat) to LF, re-test
  stop.ps1 / run.ps1.
- Type: code.
- Blocked by: nothing; (1) and (2) need a design-reviewer PASS.
- Unblocked by: any wave.
- Next step that needs no operator: the row.
- Proposed disposition: package; fold (1) into N47's file-structure
  package so the module layout is decided once.
- ToS check: none touched.

### MERGE-SEAMS-FOLLOWUP
- Source: ROADMAP.md:2037-2046; AL-NEXT-SESSION.txt:21-25;
  docs/design/reviews.log:59.
- Remaining work: F1 measure the Play tab at 1280x760 and 1920x950 with a
  zone guide, a build alert and 2 trades (figures into design 0001
  section 4); F2 live regions at 12 of 12 (free one, make #link a plain
  pill, update the N6 text); F4 each .col a labelled group, tabindex 0,
  drop tabindex from #panel-play; F5 clear #restart-overlay-said on the
  next state push, list it as a silent N6 exemption; F7 rename the
  hint-reset class to tool-row. F3 (build-alert group) and F6 (dead zone
  margins) are not carried: docs/design/reviews.log:59 records both FIXED
  (and the waypoint row fold inside F1 FIXED; only F1's measurement is
  open).
- Type: code (design).
- Blocked by: nothing. F1 needs only a headless browser on a fixture
  core, which needs CORE-DEMO-MODE first (L13, L14).
- Unblocked by: any wave after CORE-DEMO-MODE.
- Next step that needs no operator: F2, F4, F5, F7 now; F1 after the
  demo mode lands (N58 R8 SHOTS renders the same states).
- Proposed disposition: fold into docs/plan/03 target design (Play tab);
  package with N44 accessibility (F2, F4) in one wave.
- ToS check: none touched.

### S5-FOLLOWUP
- Source: ROADMAP.md:2048-2057; AL-NEXT-SESSION.txt:26-32.
- Remaining work: (a) overlay zone-guide line (view carries `line`, the
  overlay has no slot; design section 10 caps the HUD at 2 lines + one
  card); (b) BUILD-LIVE upgrade list memory-only, lost on restart (a
  bounded ops/runtime file would fix it, but decision 0045 settles
  "checked items kept in memory only" and none of its Reverses-if
  conditions is met: persisting needs an operator ruling or an
  adjudicated 0045 amendment; default stays memory-only); (c) "+2 point books" wording unverified (passive vs
  weapon-set points); (d) clear-or-push threshold is a rule of thumb; (e)
  no packaged .exe; (f) 4 blank zones (Root Hollow, Library of Kamasa,
  Isle of Decay, Brinerot Cove).
- Type: code (a, b), data / research (c, f), data from play (d),
  deployment (e).
- Blocked by: (a) the HUD line cap (design 0001 section 10, decision 0035
  number unused); (d) play data; (e) electron-builder not offline.
- Unblocked by: (a) docs/plan/03 overlay target design; (c), (f) a
  research pass on public sources; (d) the parse ledger plus run history
  (level vs zone level at each zone exit); (e) docs/plan/05 deployment
  and N53.
- Next step that needs no operator: (c) and (f) research now; (b) put
  the ruling in the operator batch (09) or to an adjudicator; (d) log level-minus-zone-level per zone exit
  in run history and tune from 2 weeks of the operator's play.
- Proposed disposition: split: (a) into 03 together with the other two
  overlay asks that compete for the same 2-line HUD (L18); (b) one code
  row only after the ruling; (c) and (f)
  one data row; (d) a loop row after the ledger; (e) into 05.
- ToS check: (c), (f) own words from public facts (decision 0043); (b)
  local file only, no new read.

### OPERATOR: GitHub remote
- Source: ROADMAP.md:2059-2061; AL-NEXT-SESSION.txt:73-74 (act d).
- Remaining work: create the remote; in the same change lift the
  .githooks/pre-push refusal and add CI with the kit's
  fleet_identity_guard.yml as a required check.
- Type: operator act.
- Blocked by: operator choice to publish; go-public readiness (N57,
  docs/plan/04).
- Unblocked by: the operator, after 04's checklist is green.
- Next step that needs no operator: everything in 04 (leak, licence,
  history checks); stage the pre-push flip and the CI file as a ready
  diff.
- Proposed disposition: operator batch (09), last item; the loop also
  cannot see this bullet (L1, the colon after OPERATOR), which is correct
  for an operator act but should be explicit (tag it, do not rely on a
  parse miss).
- ToS check: branding / trademark rules apply to the public README and
  repo name (no GGG marks).

## Hand-off items without their own block above

### REG-OPEN start check
- Source: AL-NEXT-SESSION.txt:13-15.
- Remaining work: none manual; the check is automated by GGG-DOCS-WATCH.
- Proposed disposition: fold into TC-OAUTH-REG; keep the session-start
  line until the loop tick also surfaces REG_OPEN in its checklist.

### KIT DEFECT for MAIN (FLEET-KIT-GATE-REPORT)
- Source: AL-NEXT-SESSION.txt:41-46; ops/fleet_kit/fleet_suite_gate.py:672.
- Remaining work: report to MAIN. Confirmed by reading line 672:
  `elif any(_rec(a) and _rec(a).get("exclusive") for a in ahead)` reads
  each ticket file twice; when a ticket is removed between the two reads,
  the second `_rec(a)` returns None and `.get` raises AttributeError (a
  check-then-use race; a single read bound to a name fixes it). Kit files
  are never edited locally (FLEET item 11).
- Type: fleet.
- Blocked by: no outbound path: FLEET_ROSTER is unset in this shell and
  no loop.dest_inboxes MAIN entry is configured (tools/loop_base.py:238
  reads it; tools/al_loop.py:448 reads FLEET_ROSTER).
- Unblocked by: a session that sets loop.dest_inboxes for MAIN in the
  gitignored per-host config (its value is MAIN's inbox, which MAIN's
  kit-join note or the machine roster supplies), or MAIN asking.
- Next step that needs no operator: draft the note text (defect, line,
  one-line fix, frequency 1) now, ready to send.
- Proposed disposition: fleet item in wave 1 housekeeping; one note under
  the 12/day cap.
- ToS check: none touched.

### OPERATOR ACTS (OP-ACTS)
- Source: AL-NEXT-SESSION.txt:70-79.
- Sub-items and disposition:
  - (a) in-map FPS / RAM test: RAM part closes by BUDGET-LOG with no act;
    FPS part stays (OVL-FPS).
  - (b) LIVE-1 play session and one login: replaced by normal play once
    the ledger lands (LIVE-1, TEST-LIVE-CLICKS); drop from the ask.
  - (c) TC-OAUTH-REG apply: conditional on REG_OPEN.
  - (d) GitHub remote: see its block.
  - (e) logon autostart (decision 0011, OFF by default): keep, optional.
  - (g) UA contact in config/local.json plus web_data on: keep, optional;
    it gates poe.ninja and share-URL features (decisions 0013, 0015).
  - (h) confirm "NLM" = natural-language messaging (docs/design/0001
    top): keep; one word answer.
  - (k) review decision 0017 (trade link only): keep; its reverses-if
    names "the operator rules otherwise".
  - Letters f, i and j are absent from today's hand-off. Verifier traced
    them in git history (hand-off before commit a3bf44c, session 4):
    (f) = wire the WT-SIDECAR WorktreeCreate / WorktreeRemove hook in
    .claude/settings.json; it was dropped at a3bf44c WITHOUT being acted
    on (no hook entry today), a FLEET item 5 carry-forward miss; it is
    carried here as WT-SIDECAR-WIRE. (i) = install a compiler or approve
    a prebuilt LuaJIT; replaced by decision 0027 (ROADMAP.md:1819).
    (j) = paste one real PoB2 export; done (TC-CODE-REAL [x] at
    ROADMAP.md:152, decision 0021). Nothing else is lost.
- Proposed disposition: one batched ask in docs/plan/09, ordered by
  value: (k), (g), (h), FPS map, TC-BUILDFILE-LIVE, filter checks, (e),
  (d), (c) when open.

### OPERATOR DECISION: phone view / LAN (OP-PHONE-LAN)
- Source: AL-NEXT-SESSION.txt:80; ROADMAP.md:734; N42 section "Phone
  view" (options P0 to P4, question 1); N45 phone designs A to C.
- Remaining work: the operator picks P0 (none) to P4 (opt-in read-only
  LAN listener). CLAUDE.md "Bind 127.0.0.1 only ... LAN access stays off"
  stands until the operator rules.
- Type: operator decision.
- Proposed disposition: operator batch with N42 and N45 options attached;
  default recommendation P0 / design A (no network path) keeps the bind
  rule untouched.
- ToS check: no floor rule touched; it is a CLAUDE.md tree rule, which
  only the operator lifts.

### Headless loop PAUSED (LOOP-RESUME)
- Source: AL-NEXT-SESSION.txt:81-84; ops/loop/control/HALT (present);
  progress loop.json step "HALT file present" (2026-11-18T00:48).
- Remaining work: remove HALT at the point docs/plan/07 names; the
  scheduled task \AshLightOps\LaneLoop stays enabled meanwhile.
- Blocked by: LOOP-PARSER-FIX must land first: with HALT gone the tick
  would dispatch 9 hand-off bullets as work today (L3).
- Proposed disposition: plan 07 step "after wave 1's loop fix".

### NOTE: session-5 reap
- Source: AL-NEXT-SESSION.txt:85-90.
- Remaining work: none; AL-NEXT-SESSION.txt:15-18 records the reap done
  in session 6 with read-back.
- Proposed disposition: drop at the next /done (obsolete, superseded by
  the session-start line).

### NOTE: live lane trips fleet_test_guard
- Source: AL-NEXT-SESSION.txt:91-93.
- Remaining work: a lane writing ops/loop/control/loop_items/*.json
  mid-suite gives a false teardown error.
- Proposed disposition: fold into LOOP-PARSER-FIX or N49 (test speed):
  the suite gate already refuses while another agent holds uncommitted
  edits; loop_items writes are not edits. Keep the note until fixed.

### NOTE: tree created by MAIN
- Source: AL-NEXT-SESSION.txt:94-95.
- Remaining work: none; informational. Keep verbatim.

## Items with no ROADMAP row

Each gets a proposed row (ID, lane, one line); docs/plan/07 assigns waves.

1. LIVE-WAYSTONE (build): source ROADMAP.md:647-648 (inside UTIL-WAYSTONE,
   a done row). One real waystone text through the item-check press.
   Least effort: the press already reads the text the player copied;
   record the masked property-block shape of a waystone press in the
   parse ledger and close on the first one. ToS check: per-press read
   only, no extra read, no watcher.
2. LIVE-SEARCHSTR (build): source ROADMAP.md:665 (inside UTIL-SEARCHSTR).
   Confirm in game that a leading `!` negates the whole OR group. Least
   effort: one paste by the player plus a verdict click (row 5). ToS
   check: the player pastes; AshLight copies only on the player's click.
3. LIVE-FILTER (build): source ROADMAP.md:708 (inside UTIL-FILTER). Load
   the downloaded snippet through the game's filter import once.
4. LIVE-FILTER-MERGE (build): source ROADMAP.md:728-729 and
   AL-NEXT-SESSION.txt:66. Merge a real filter (for example a NeverSink
   file) and load it in game once. Rows 3 and 4 run as one act. ToS
   check: decision 0031 / 0033: the player saves the file; AshLight never
   writes the game folder.
5. LIVE-VERDICTS (build): new. A Checks-tab card "Tried in game" listing
   the open player checks (TC-BUILDFILE-LIVE, LIVE-SEARCHSTR, LIVE-FILTER,
   LIVE-FILTER-MERGE, OVL-FPS numbers) with Worked / Refused buttons and
   an optional note; verdicts in a bounded ops/runtime file; a script
   reads them back and drafts the ROADMAP flips. ZERO-CLICK for the
   developer side; one click per check for the player. ToS check:
   dashboard clicks only, nothing sent to the game.
6. FLEET-KIT-GATE-REPORT (fleet): the kit defect above.
7. OP-PHONE-LAN (review): the operator decision above.
8. LOOP-RESUME (review): remove HALT after LOOP-PARSER-FIX (plan 07).
9. WT-SIDECAR-WIRE (review, operator act): the WT-SIDECAR row is flipped
   [x] (ROADMAP.md:1663 "done ... loop") though its own text says
   "PARTIAL ... activation = operator act" (ROADMAP.md:1676-1683);
   .claude/settings.json has no WorktreeCreate entry (grep, 2026-11-18)
   and tests/test_wt_sidecar_hook.py:136 skips "not wired yet". Act: the
   operator pastes the two hook entries, then a session checks one
   isolated spawn lands under the sidecar Worktree dir. Reopen as its own
   row so the act is not lost behind a done mark.
10. LOOP-PARSER-FIX (build): L1, L2, L3 and L4 below (N58 R1
    LOOP-PREFLIGHT covers L1, L3 and the failed-state change behind L4;
    L2 is new).
11. CORE-LOG-NO-FALLBACK (build): L13 below.
12. CORE-DEMO-MODE (build): L14 below (N58 R8 a DEMO-MODE is the same
    design).
13. DOC-DECISION-TIDY (review): L9 below (L10 rides the S5 (f) data
    row instead).

## Loose ends found in code and docs

- L1 Loop row parser drops ids with a dot or a colon. tools/loop_base.py:
  109-111 `ROW_ID = (?:\d{3}|[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)` followed by
  whitespace. Run on ROADMAP.md (verifier re-run at 1f2d537): 151 rows
  parsed, 12 open seen;
  the open UTIL-1.0-POST (ROADMAP.md:530) and the OPERATOR bullet
  (ROADMAP.md:2059) are invisible, as are the done UTIL-1.0-READY (516),
  DOC-1.0-RUNBOOK (1277) and UTIL-1.0-FIXTURES (1518). Fix: rename the
  ids (UTIL-10-...) and add a lint test that fails on any `- [` bullet
  ROW_RX does not match (N58 R1 b).
- L2 handoff_session() returns None for the live hand-off.
  tools/al_loop.py:1525-1528 matches `^SESSION:\s*(\d+)\s*$`; the hand-off
  line is `SESSION: 6   (FLEET item 13 counter; ...)`
  (AL-NEXT-SESSION.txt:3), so the trailing comment fails the `\s*$`.
  Read back 2026-11-18: `handoff_session(text)` -> None. Effect: the
  interactive checklist header at tools/al_loop.py:1747-1750 has no
  session number. Fix: `^SESSION:\s*(\d+)\b` plus a test on the real
  line shape. New (not in N58).
- L3 Hand-off bullets become loop work without the BLOCKED check or a
  row dedupe. tools/al_loop.py:1142-1147 appends every hand-off item
  whose skip tag is None; the BLOCKED test (al_loop.py:1125) runs only on
  ROADMAP rows; tools/loop_roadmap.py:269-292 tags a bullet only by
  SKIP_TAGS (tools/loop_base.py:119: operator / other-tree / info), and
  each dispatched bullet is an opus / medium run (tools/loop_base.py:73).
  Run on the live hand-off (verifier re-run): 15 items, 9 untagged (the five
  that repeat open rows: MERGE-SEAMS, S5, TC-IMPORT, AUDIT-P8, CODE-HEALTH;
  plus LIVE rows, UTIL-1.0-POST, KIT DEFECT, loop PAUSED). N58 R1 a
  (hand-off bullet is work only with a `LOOP:` prefix) fixes it; it must
  land before HALT is removed.
- L4 12 stale `failed` loop_items records with verdict "adjudicate" for
  rows that are done in ROADMAP: AUDIT-BUILDFILE, AUDIT-P6-LOW,
  HUD-ACT-RESUME, MATH-VALUE-UI, TC-BUILDFILE, TC-UPGRADE-STATS,
  UTIL-FILTER-2, UTIL-MAPRUN-OVL, UTIL-MAPRUN, UTIL-SEARCHSTR,
  UTIL-WAYSTONE, UX-ZONE-NOTES (ops/loop/control/loop_items/*.json,
  updated 2026-11-17). AUDIT-BUILDFILE's result names
  docs/plans/AUDIT-BUILDFILE-decision-draft.md; docs/plans/ does not
  exist (decision 0034 superseded it). Today they are inert: "failed" is a
  done state (tools/loop_base.py:85) and dispatchable() never re-sends it
  (tools/loop_roadmap.py:318-330), so a resumed loop does NOT
  re-adjudicate them (the draft's claim was wrong). They start to matter
  when N58 R1 (c) takes "failed" out of the done states: then all 12
  would show as parked work. Fix: in the same change as R1 (c), mark
  these 12 superseded (or skip failed records whose row is [x]); part of
  LOOP-PARSER-FIX, not a row of its own.
- L5 WT-SIDECAR flipped done while its activation is an operator act
  (see no-row item 9).
- L6 TEST-LIVE-CLICKS names a desktop-tool grant as an unblock path
  (ROADMAP.md:54); it breaks the input rule (Rejected R-1).
- L7 Skips in the suite (3 skipped at the session-5 gate): the
  opt-in live overlay smoke (tests/test_overlay_smoke.py:175, needs
  AL_OVERLAY_SMOKE=1), the hook wiring (tests/test_wt_sidecar_hook.py:136,
  operator act), and the PoB GUI reference values
  (tests/test_tc_bridge.py:290, "no PoB GUI reference values recorded").
  One xfail by design: tests/test_tc_code_real.py:124 (zlib bytes,
  decision 0021). About 20 more skips fire only without the optional calc
  component or snapshot cache (tests/tc_live_util.py:32-35,
  tests/conftest.py:56, tests/test_zone_guide.py:196); none hides a
  defect. Action: the overlay smoke should run in at least one
  scheduled run (N49 / N58), not only by hand.
- L8 No TODO, FIXME, XXX or HACK marker exists outside ops/fleet_kit/
  and docs/ (grep 2026-11-18): the code carries its open work in ROADMAP
  only, which is the intended pattern.
- L9 Stale "Open (UNVERIFIED)" entries. docs/decisions/0015-price-check-
  and-contact.md:52-53 (trade2 /data/stats, /data/leagues, /fetch shapes)
  is moot: the app calls no trade2 endpoint (decision 0017). In
  docs/decisions/0013-web-data.md the trade2 bullet (:77-78) is half moot:
  the limit values no longer matter, but filter names still feed the
  ?q= link (server/al/trade.py:55 writes type_filters), so that half
  stays open; the poe.ninja names bullet (:74-76) is already verified and
  only sits under the wrong heading. Fix: one amendment line per entry
  (moot since 0017 / resolved / still open for the link) so no session
  researches the moot ones again.
- L10 decision 0030:38 "Notes are general guidance and not yet checked in
  play": the zone notes have no live check row; fold into S5 (f) data row
  and the parse ledger (zone visits).
- L11 docs/decisions/README.md:21 records 0035 as intentionally unused;
  docs/plan/README.md says the next free number is 0046. Consistent; no
  action.
- L12 Progress files: up-0051-v and up-0056-r1 read failed ("died at the
  model usage limit; re-queued", 2026-11-18T00:46). Verifier read-back
  01:00: both rows now read done (the retry reuses the task name and
  overwrites the failed row), and no up-* row of 60 reads failed. One
  oddity remains: up-0056-r1 reads status done with step "reviewing repo
  1", so the step text was not updated on the last write. Action for
  docs/plan/08: the final progress write names the outcome in its step;
  no other action.
- L13 A configured but missing log path falls back to the live
  Client.txt. server/al/logfile.py:138-152: when the configured path is
  not a file, discover_client_log() continues to the Steam library scan
  and returns the real log. Core.locate_log (server/al/core.py:608-614)
  takes the scan's answer and keeps the configured path only when the
  scan finds nothing. Seen this session: a demo core given a
  missing fixture path tailed the live log for about 20 s. Consent did
  not stop it because the demo used the shared runtime dir, where the
  live consent record lives (core.py:66-67, paths.py:35-41). Fix: a
  configured path never falls back (return the configured path, missing
  or not, as locate_log already does for "may appear later"); the scan
  runs only when no path is configured. Test: a configured missing path
  with a fake Steam library holding a log returns the configured path.
  ToS check: "Client.txt (tailed only after the user's opt-in, with a
  visible indicator)": the fix keeps a non-live instance from reading the
  live log under someone else's consent.
- L14 No isolated instance is possible. server/al/__main__.py:153 reads
  paths.load_local_config() for the port, and __main__.py:157 always
  builds Core with runtime=None, which (core.py:72-75) reads config/local.json (paths.py:119-121, no env
  override) and the shared runtime dir unless AL_RUNTIME_DIR is set
  (documented "tests only", paths.py:22). There is no --config or --demo
  flag; the existing --no-tail and --replay flags (__main__.py:33-34) stop
  the tail but still share the real config, token and runtime dir, so
  they are not a safe demo either. Fix: N58 R8 a DEMO-MODE: `python -m server.al --demo <fixture
  dir>` with runtime, config and fetcher in a scratch folder, Steam scan
  off, web data off or a loopback mock, exit if any open log is outside
  the fixture folder. It unblocks MERGE-SEAMS F1, the screenshot work and
  safe demos while the operator plays.
- L15 The scheduled task \AshLightOps\LaneLoop is enabled while HALT is
  set (AL-NEXT-SESSION.txt:81-84): each 15-minute tick runs the docs
  watch (by design, decision 0044) and exits on HALT. No defect; noted
  so LOOP-RESUME does not reinstall the task.
- L16 S5 (b) persisting the upgrade list touches decision 0045's
  in-memory clause: it needs an amendment, not a silent change.
- L17 KIT DEFECT race at ops/fleet_kit/fleet_suite_gate.py:672 (above);
  a kit file, so a report, never a local edit. _rec (line 274 on) returns
  None on OSError / ValueError, which is the removed-ticket case.
- L18 Three overlay asks compete for the same capped HUD (design 0001
  sections 7.2 and 10: 2 HUD lines plus one card): S5 (a) zone-guide
  line, the UX-ZONE-NOTES "overlay word" left "Not done" inside a done
  row (ROADMAP.md:678-679), and UTIL-OVERLAY-MAP, closed "NOT DONE BY
  DESIGN" by an adjudicator (ROADMAP.md:607-612). Found by the verifier
  in done rows; the draft missed the first two links. Disposition: one
  decision in docs/plan/03 (overlay target design) settles all three.

## Recommendations

Ranked by what blocks other work first, then by operator effort saved.
Waves are docs/plan/07's call; "Depends on" names hard prerequisites.

### R1 LOOP-PARSER-FIX (before HALT is removed)
- Action: (a) a hand-off bullet is loop work only with a `LOOP:` prefix,
  and BLOCKED_RX applies to it (al_loop.py:1142-1147); (b) rename the five
  dot / colon ids (UTIL-10-..., `OPERATOR-REMOTE` tagged operator) and
  add a test that fails on any `- [` line ROW_RX misses or a repeated id;
  (c) handoff_session() matches `^SESSION:\s*(\d+)\b`; (d) when "failed"
  leaves the done states (N58 R1 c), skip failed records whose row is [x]
  (the 12 of L4).
- Impact: H. Stops 9 duplicate opus runs per resumed tick (L3), makes
  UTIL-1.0-POST visible before 2026-12-11, restores the checklist header.
- Effort: S-M (3 regex / filter changes, 4 tests). Risk: low; a bullet
  without `LOOP:` simply stops being work.
- ToS check: no floor rule touched (dev tooling, no game, no network).
- Depends on: nothing. Blocks: R9 LOOP-RESUME, the UTIL-1.0 split.
- Files: tools/loop_base.py, tools/loop_roadmap.py, tools/al_loop.py,
  ROADMAP.md (ids), tests/test_al_loop*.py.
- Acceptance test: on today's ROADMAP.md every `- [` line parses (14
  open seen, not 12); on today's hand-off the tick's work list holds 0
  hand-off items; handoff_session(real hand-off) == 6.
- ZERO-CLICK: the loop reads the fixed files by itself each tick.

### R2 CORE-LOG-NO-FALLBACK
- Action: discover_client_log returns the configured path when one is
  given, existing or not (logfile.py:138-143); the Steam scan runs only
  with no configured path.
- Impact: H. A demo or test core can no longer tail the live log under
  the operator's consent (L13, seen this session for about 20 s).
- Effort: S (one branch, one test with a fake Steam library). Risk: a
  user with a stale configured path sees "log not found" instead of an
  auto-found log; the first-run card already shows the path, so the fix
  is visible.
- ToS check: "Client.txt (tailed only after the user's opt-in, with a
  visible indicator)": tightens it; no new read.
- Depends on: nothing. Files: server/al/logfile.py, server/al/core.py
  (locate_log comment), tests/test_logfile*.py.
- Acceptance test: configured missing path plus a fake library holding a
  Client.txt returns the configured path; no path configured still finds
  the library log.
- ZERO-CLICK: no user step changes.

### R3 OBS-PARSE-LEDGER plus live read-back (closes LIVE-1 shapes,
TEST-LIVE-CLICKS, LIVE-WAYSTONE from normal play)
- Action: N51 R1 ledger at Core.feed_line (hit counts per pattern id,
  masked shapes of unparsed lines, bounded ops/runtime/logshapes.json);
  tools/live1_report.py prints VERIFIED live / NOT SEEN / NEW SHAPE per
  LIVE-1 shape plus the five TEST-LIVE-CLICKS fields from a saved
  /api/state snapshot; the item-check press records the masked property
  block shape of a waystone; split LIVE-1 into one row per shape.
- Impact: H. Turns operator acts (b) and the login ask into zero acts.
- Effort: M. Risk: a masking bug could keep a name; the test feeds real
  shaped lines with names and asserts none survive.
- ToS check: Client.txt read only after opt-in, same lines the tailer
  already reads; per-press item text only (decision 0003); no raw text
  stored (R-3), no network.
- Depends on: nothing. Files: server/al/core.py, new
  server/al/logshapes.py, tools/live1_report.py, tests.
- Acceptance test: replaying the UTIL-1.0 fixture log yields per-pattern
  counts and masked shapes with no character name; the report marks each
  LIVE-1 shape.
- ZERO-CLICK: the operator plays; a session or tick runs the report.

### R4 BUDGET-LOG (closes OVL-BUDGET from normal play)
- Action: N48 R4: client main process logs app.getAppMetrics() per
  process once a minute, the core its own working set / CPU, tagged by
  game idle / active / in map / overlay shown (from Client.txt state,
  never a process check), 1 MB cap in <sidecar>\Logs, one Checks row.
- Impact: H (N48: closes OVL-BUDGET with no operator action). Effort: M.
  Risk: log growth, capped.
- ToS check: own processes only; no game memory, no process-list check
  (decision 0029).
- Depends on: nothing. Files: app/main.js (or app/client/*),
  server/al/ (core metrics), web/checks.js, tests.
- Acceptance test: a fixture run writes tagged rows and stops at 1 MB.
- ZERO-CLICK: logs by itself.

### R5 CORE-DEMO-MODE
- Action: `python -m server.al --demo <fixture dir>`: runtime, config and
  fetcher in a scratch folder, Steam scan off, web data off, exit if any
  open log is outside the fixture folder (N58 R8 a).
- Impact: M-H. Unblocks MERGE-SEAMS F1 measurement and screenshots with
  no risk to the live client.
- Effort: M. Risk: low once R2 lands.
- ToS check: reads only a fixture copy; no live log, no network.
- Depends on: R2. Files: server/al/__main__.py, server/al/paths.py,
  server/al/core.py, tests.
- Acceptance test: a demo core given a missing fixture exits non-zero
  and opens no file outside the fixture dir; the live runtime dir is
  untouched (mtime check).
- ZERO-CLICK: scripted; no operator step.

### R6 LIVE-VERDICTS plus OVL-CHECK (one-click player checks)
- Action: a Checks-tab "Tried in game" card (TC-BUILDFILE-LIVE,
  LIVE-SEARCHSTR, LIVE-FILTER, LIVE-FILTER-MERGE, OVL-FPS numbers) with
  Worked / Refused and a note, stored in a bounded ops/runtime file and
  read back by a script that drafts the ROADMAP flips; N48 R5 OVL-CHECK
  cycles the overlay through timed blocks in a map so FPS readings line
  up.
- Impact: M. Each player check costs one click instead of prose.
- Effort: M. Risk: low; nothing sent anywhere.
- ToS check: dashboard clicks only; the player saves files and pastes
  strings (decisions 0031, 0033, 0034); overlay cycling is AshLight's own
  window; FPS read by the player (decision 0006, R-2).
- Depends on: nothing (R4 shares the Checks row). Files: web/checks.js,
  server/al/http.py, new ops/runtime file, tools/ovl_check.py, tests.
- Acceptance test: a verdict posted via the token API appears in the
  read-back script output; OVL-CHECK writes its block schedule.
- ZERO-CLICK: developer side automatic; one click per check for the
  player.

### R7 Code rows as filed
- Action: AUDIT-P8-LOW (P8-3 to P8-8), CODE-HEALTH-FOLLOWUP (3 items, (1)
  folded into the N47 layout), MERGE-SEAMS F2 / F4 / F5 / F7 now and F1
  after R5, S5 (c) / (f) research, (d) after R3.
- Impact: M. Effort: M in total. Risk: low; design-reviewer PASS for UI.
- ToS check: none touched; P8-7 tightens redaction.
- Depends on: R5 for F1. Files: per row (ROADMAP.md:1981-2057).
- Acceptance test: each row's own ACCEPT line plus pytest / npm green.
- ZERO-CLICK: no player step.

### R8 Housekeeping docs and fleet
- Action: DOC-DECISION-TIDY (L9 amendment lines); strike "or a
  desktop-tool grant to the lane" from TEST-LIVE-CLICKS (ROADMAP.md:54,
  R-1); reopen WT-SIDECAR as WT-SIDECAR-WIRE (operator act); draft the
  FLEET-KIT-GATE-REPORT note now and send it once loop.dest_inboxes has a
  MAIN entry; S5 (b) and OP-PHONE-LAN go to the operator batch.
- Impact: M (prevents re-research and a ToS-breaking unblock path).
  Effort: S. Risk: none.
- ToS check: R-1 removal enforces "NEVER send input to the game".
- Depends on: nothing. Files: docs/decisions/0013, 0015, ROADMAP.md,
  a draft note in the outbox only when a path exists.
- Acceptance test: grep finds no "desktop-tool grant" in ROADMAP.md;
  test_wt_sidecar_hook.py still skips until the operator wires the hook.
- ZERO-CLICK: no player step.

### R9 LOOP-RESUME and the operator batch
- Action: remove ops/loop/control/HALT after R1 lands; one batched ask
  (docs/plan/09): (k) 0017 review, (g) UA contact / web_data, (h) NLM,
  OVL-FPS map, TC-BUILDFILE-LIVE, filter checks, LIVE-SEARCHSTR paste,
  S5 (b) ruling, phone / LAN pick, WT-SIDECAR-WIRE paste, (e) autostart,
  (d) GitHub remote, (c) apply when REG_OPEN appears.
- Impact: H for throughput once R1 is in. Effort: S. Risk: a resumed
  loop without R1 burns runs (L3).
- ToS check: no floor rule touched; every act is the operator's own.
- Depends on: R1 (HALT); R6 for one-click verdicts.
- Files: ops/loop/control/HALT, docs/plan/09.
- Acceptance test: after removal, one tick's loop.json lists no
  hand-off item as work and no row marked BLOCKED.
- ZERO-CLICK: the tick resumes by itself every 15 minutes.

## Rejected

- R-1 A desktop-control tool grant to a lane to click Login / character
  select (ROADMAP.md:54). It synthesizes input to the game client; the
  floor says "NEVER send input to the game ... not even a synthesized
  Ctrl+C". TEST-LIVE-CLICKS closes from the operator's normal play
  instead.
- R-2 Reading the game's FPS from outside (PresentMon, ETW Present
  tracing, a frame hook or a screen capture of the FPS counter). Decision
  0006 and the floor ("hook DirectX / DXGI", "the screen ONLY once per
  manual press") bar them; OVL-FPS stays a player reading.
- R-3 Persisting raw unknown Client.txt lines to speed up LIVE-1 (N51
  rejects it too): only masked shapes, so no chat text or names are kept.
- R-4 A timer or watcher that reads the clipboard to catch waystone or
  item texts for LIVE-WAYSTONE: per-press only (decision 0003).

## Count check

- Open ROADMAP rows = 14 (grep `^- \[ \]` on ROADMAP.md: lines 9, 50, 56,
  63, 274, 280, 530, 570, 618, 1981, 2012, 2037, 2048, 2059); listed in
  "Items" = 14.
- Hand-off carried items, top level = 16 (15 bullets at
  AL-NEXT-SESSION.txt:21-95 plus the REG_OPEN start check at :13-15);
  listed = 16 (5 as row blocks: MERGE-SEAMS, S5, TC-OAUTH-REG, AUDIT-P8,
  CODE-HEALTH; TC-IMPORT / TC-CURX, LIVE rows and UTIL-1.0-POST map to
  their row blocks; 8 in "Hand-off items without their own block").
- Hand-off sub-items = 38: MERGE-SEAMS 5 (F1, F2, F4, F5, F7), S5 6 (a
  to f), P8 6 (P8-3 to P8-8), CODE-HEALTH 3, LIVE 9 (LIVE-1,
  TEST-LIVE-CLICKS, OVL-BUDGET, OVL-FPS, TC-BUILDFILE-LIVE,
  LIVE-FILTER-MERGE, waystone, search string, filter), operator acts 8
  (a, b, c, d, e, g, h, k), TC-CURX 1; listed = 38.
- Items with no ROADMAP row = 13; each has a proposed row ID above.
- Verifier re-derivation (1f2d537): `^\s*- \[ \]` on ROADMAP.md gives the
  same 14 lines; handoff_items() on AL-NEXT-SESSION.txt gives 15 bullets
  (9 untagged); every bullet and sub-item maps to a block above. The
  hand-off's 5 "Operator orders recorded session 5" are standing orders,
  not open items, and are not counted.

## Verification

Verifier pass 2026-11-18 (independent of the author), at HEAD 1f2d537.
- Checked: 14 of 14 open rows and 15 of 15 hand-off bullets re-derived
  (both match); 31 code citations opened (loop_base 73 / 85 / 109-111 /
  119 / 238, loop_roadmap 269-292 / 318-330, al_loop 448 / 1125 /
  1142-1147 / 1525-1528 / 1747-1750, logfile 135-153, core 66-75 /
  608-614, paths 22 / 35-41 / 119-121, __main__ 33-34 / 153-157,
  fleet_suite_gate 274 / 672, 6 test skip / xfail lines, reviews.log:59,
  decisions 0013 / 0015 / 0030, 12 loop_items records, ROADMAP lines 54,
  607-612, 647, 665, 678, 708, 728, 1663-1683, 1819); parsers re-run
  read-only on the live files; 2 web claims re-fetched (1.0 date, OAuth
  registration closed); docs-watch state read back ("reg": "closed").
  All 9 recommendations tested against the ToS floor and the Settled list.
- Corrected: L1 row count 150 -> 151; L4 claim that stale failed records
  get re-adjudicated (false: failed is a done state today); L9 scope
  (0013 trade2 filter names still feed the ?q= link); L12 (failed rows
  already overwritten; one stale step text); MERGE-SEAMS F3 / F6
  reason; S5 (b) now states no 0045 Reverses-if is met; TC-CURX fixture
  must not come from a live call; OP-ACTS f / i / j traced (f was
  dropped unacted); Summary type counts (LIVE-VERDICTS was missing,
  OP-ACTS is not a row-level item); LOOP-ITEMS-TIDY merged into
  LOOP-PARSER-FIX (14 -> 13 no-row items).
- Added: L18 (three overlay asks on one capped HUD); the Recommendations
  section R1 to R9 with all fields; L14 note on --no-tail / --replay.
- UNVERIFIED: the 1.0 ascendancy names; whether G5_ / G6_ prefixes hold
  in 1.0 (runbook item); N48's per-tick cost figure for P8-5 (about
  10 ms, quoted, not re-measured); the "about 20 s" live-tail duration
  (session report, not re-read from a log).
