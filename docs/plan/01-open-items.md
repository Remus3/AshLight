# 01 - Open items

Date: 2026-11-18. Ultraplan plan section (docs/plan/README.md), section D.
Status: draft

Scope: every open item the plan must carry, read at HEAD a55fb3b plus the
untracked research drafts of this session. Sources: ROADMAP.md (2061
lines), AL-NEXT-SESSION.txt (141 lines), docs/decisions/, docs/audit/,
the loop code (tools/loop_base.py, tools/loop_roadmap.py, tools/al_loop.py),
the core (server/al/), tests/ and the runtime files under ops/loop/control/.
Sibling notes are cited as N<number> (N48 = docs/research/0048-...).
Web check: PoE2 1.0 launches 2026-12-11 (rpgsite.net news 21188 and the
Epic Games Store news post, both accessed 2026-11-18); the 1.0 ascendancy
names stay UNVERIFIED (the coverage names a new Duelist class).

## Summary

- Open ROADMAP rows: 14 (13 IDs plus the OPERATOR GitHub-remote bullet).
- Hand-off carried items: 16 top-level (15 "Carried forward" bullets plus
  the session-start REG_OPEN check), 38 sub-items under them.
- Items with no ROADMAP row: 14 (each gets a proposed row below).
- Loose ends found in code and docs: 17 (L1 to L17).

By type (the 14 rows plus the 14 no-row items, 28 in all; an item counted
once under its main type):
- code: 9 (AUDIT-P8-LOW, CODE-HEALTH-FOLLOWUP, MERGE-SEAMS-FOLLOWUP,
  S5-FOLLOWUP, LOOP-PARSER-FIX, CORE-LOG-NO-FALLBACK, CORE-DEMO-MODE,
  LOOP-ITEMS-TIDY, DOC-DECISION-TIDY)
- live-game check: 8 (LIVE-1, TEST-LIVE-CLICKS, OVL-BUDGET, OVL-FPS,
  TC-BUILDFILE-LIVE, LIVE-WAYSTONE, LIVE-SEARCHSTR, LIVE-FILTER /
  LIVE-FILTER-MERGE as one)
- external wait: 4 (TC-OAUTH-REG, TC-IMPORT, TC-CURX, UTIL-1.0-POST)
- operator act or decision: 5 (OPERATOR GitHub remote, OP-ACTS batch,
  OP-PHONE-LAN, WT-SIDECAR-WIRE, LOOP-RESUME)
- fleet: 1 (FLEET-KIT-GATE-REPORT)
- informational, no work: 1 (NOTE tree created)

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
- Next step that needs no operator: parser and cache against a recorded
  public fixture, off by default.
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
  hint-reset class to tool-row. F3 and F6 are not carried (the review
  line records the waypoint row folded as FIXED).
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
  bounded ops/runtime file; decision 0045 reverses-if "item text must not
  stay in memory" only covers the opposite direction, so persisting needs
  a 0045 amendment); (c) "+2 point books" wording unverified (passive vs
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
- Next step that needs no operator: (c) and (f) research now; (b) decide
  in 03 / a 0045 amendment; (d) log level-minus-zone-level per zone exit
  in run history and tune from 2 weeks of the operator's play.
- Proposed disposition: split: (a) into 03; (b) one code row; (c) and (f)
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
  - Letters f, i and j are absent. ROADMAP.md:1819 records act i replaced
    by decision 0027 (WinLibs toolchain); no source left for f and j in
    the tracked files, so nothing is lost by their absence.
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
10. LOOP-PARSER-FIX (build): L1, L2, L3 below (N58 R1 LOOP-PREFLIGHT
    covers L1 and L3; L2 is new).
11. CORE-LOG-NO-FALLBACK (build): L13 below.
12. CORE-DEMO-MODE (build): L14 below (N58 R8 a DEMO-MODE is the same
    design).
13. LOOP-ITEMS-TIDY (build): L4 below.
14. DOC-DECISION-TIDY (review): L9 below.

## Loose ends found in code and docs

- L1 Loop row parser drops ids with a dot or a colon. tools/loop_base.py:
  109-111 `ROW_ID = (?:\d{3}|[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)` followed by
  whitespace. Run on ROADMAP.md today: 150 rows parsed, 12 open seen;
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
  ROADMAP rows. Run on the live hand-off: 15 items, 9 untagged (the five
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
  exist (decision 0034 superseded it). Fix: mark them superseded so a
  resumed loop does not re-adjudicate (N58 R1 c covers the failed state).
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
- L9 Stale "Open (UNVERIFIED)" sections: docs/decisions/0013-web-data.md:
  69-79 (trade2 filter names and limits) and
  docs/decisions/0015-price-check-and-contact.md:50-53 (trade2 /data and
  /fetch shapes) ask about endpoints the app no longer calls (decision
  0017). Fix: an amendment line "moot since 0017" so no session
  researches them again.
- L10 decision 0030:38 "Notes are general guidance and not yet checked in
  play": the zone notes have no live check row; fold into S5 (f) data row
  and the parse ledger (zone visits).
- L11 docs/decisions/README.md:21 records 0035 as intentionally unused;
  docs/plan/README.md says the next free number is 0046. Consistent; no
  action.
- L12 Progress files: up-0051-v and up-0056-r1 read failed ("died at the
  model usage limit; re-queued", 2026-11-18T00:46); 14 more ultraplan rows
  were running at 00:47. No stale old rows outside this session. Action
  for the plan's orchestration (docs/plan/08): a re-queued task writes a
  new row and the failed one is cleared, so the status line does not show
  a dead failure next to its live retry.
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
  paths.load_local_config() for the port, and Core(runtime=None)
  (core.py:72-75) reads config/local.json (paths.py:119-121, no env
  override) and the shared runtime dir unless AL_RUNTIME_DIR is set
  (documented "tests only", paths.py:22). There is no --config or --demo
  flag. Fix: N58 R8 a DEMO-MODE: `python -m server.al --demo <fixture
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
  a kit file, so a report, never a local edit.

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
- Items with no ROADMAP row = 14; each has a proposed row ID above.
