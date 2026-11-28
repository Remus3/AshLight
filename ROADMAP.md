# AshLight ROADMAP

Open work only, as lane rows the loop (`tools/al_loop.py`) can dispatch.
Format: `- [ ] ID (lane) title. ACCEPT: ...`; `(priority)` jumps the queue.
Rows are filed as `docs/roadmap/new/<ID>.md` and closed as
`docs/roadmap/done/<ID>.md`, and folded in at /done.

REL-PREP row template, filed at each wave end (AUTO-16): `- [ ] REL-PREP-<n>
(build) Prepare release X.Y.Z: docs_fresh.py index --write, docs_fresh.py check,
shots.py check; release.py bump X.Y.Z; release.py notes X.Y.Z --write; curate the
notes (remove the STUB mark); release.py notes --changelog; commit; release.py
stage. Never tags or pushes. On stage PASS set this row to BLOCKED: operator
phrase "release X.Y.Z" (stage PASS). DEPENDS: <the wave's row ids>. ACCEPT:
stage.json verdict PASS for X.Y.Z at HEAD. ZERO-CLICK: unattended up to the one
operator phrase.`

## Lane: build

- FOLDED 2026-11-18: LIVE-1 -> RUN-LEDGER-CORE, RUN-LEDGER-WIRE, RUN-LEDGER-REPORT, RUN-LIVE1-FIXTURES (docs/plan/07 Coverage; the old row text is in git history).
- FOLDED 2026-11-18: TEST-LIVE-CLICKS -> RUN-LIVE-CLICKS-STRIKE, RUN-LEDGER-WIRE, RUN-LEDGER-REPORT, RUN-LIVE-CLICKS-CLOSE (docs/plan/07 Coverage; the old row text is in git history).
- FOLDED 2026-11-18: OVL-BUDGET -> RUN-BUDGET-LOG-CORE, RUN-BUDGET-LOG-CLIENT, RUN-OVL-BUDGET-CLOSE (docs/plan/07 Coverage; the old row text is in git history).
- [ ] OVL-FPS (review) OVL-FPS: record the in-map overlay check result (budget B19, ruling Q-18) and close the
  row. ACCEPT: budget B19, documented as a proxy: no change on the game's own FPS display with the
  HUD on (the operator's same / dropped answer), AshLight CPU under 1 percent, system totals within
  noise; method: tools/ovl_check.py; the numbers go in decision 0006 (not 0002, ruling Q-18):
  python -m pytest -q tests/test_ascii_lf.py tests/test_research_numbers.py tests/test_leak_sweep.py
  passes and git grep -n B19 -- docs/decisions/0006-fps-measurement-method.md shows the dated result
  line with the report's figures. ZERO-CLICK: The operator plays one map they would play anyway; the
  schedule, the record and this write-up need no further act. DEPENDS: OVL-CHECK, RUN-BUDGET-LOG-CORE.
  BLOCKED: operator plays one map with tools/ovl_check.py armed (Q-18, B19); the loop skips it until
  then (operator).
- [ ] TC-TREE-URL-ASC-CHECK (build) Verify the ruled ascendancy byte of the version 7 tree link (server/al/theorycraft/treeurl.py: 1 + the 0-based position in the class ascendancies list of the cached tree export, placeholders kept) against a real GGG passive tree link that includes an ascendancy; decode it, compare, add it as a fixture and fix the mapping if it differs. ACCEPT: python -m pytest -q tests/test_tc_treeurl.py passes with the real link as a fixture. ZERO-CLICK: the operator pastes one tree link from the game once; the check is automatic. DEPENDS: TC-TREE-URL. BLOCKED: operator act (paste one real GGG tree link with an ascendancy chosen).
- [ ] LIVE-FILTER-FIX (build) Fix what the game refused: The downloaded AshLight filter snippet imported in game (verdict refused 2026-11-22, research 0022 section 5; the clicks landed within 19 s with no note, so no cause is known yet). Once the retry note says what the game showed, find the cause and fix it, or record a worked verdict if the retry works. ACCEPT: python tools/live_verdicts.py lists a worked verdict for LIVE-FILTER. ZERO-CLICK: One more try by the player ends in one click plus a short note; the fix is automatic from there. DEPENDS: RUN-VERDICTS-CLOSE. BLOCKED: operator act (one more try in game, with a note saying what the game showed).
- [ ] LIVE-FILTER-MERGE-FIX (build) Fix what the game refused: A merged filter (your filter plus AshLight's blocks) loaded in game (verdict refused 2026-11-22, research 0022 section 5; the clicks landed within 19 s with no note, so no cause is known yet). Once the retry note says what the game showed, find the cause and fix it, or record a worked verdict if the retry works. ACCEPT: python tools/live_verdicts.py lists a worked verdict for LIVE-FILTER-MERGE. ZERO-CLICK: One more try by the player ends in one click plus a short note; the fix is automatic from there. DEPENDS: RUN-VERDICTS-CLOSE. BLOCKED: operator act (one more try in game, with a note saying what the game showed).
- [ ] LIVE-SEARCHSTR-FIX (build) Fix what the game refused: A copied search string pasted into a game search box (verdict refused 2026-11-22, research 0025 section 4; the clicks landed within 19 s with no note, so no cause is known yet). Once the retry note says what the game showed, find the cause and fix it, or record a worked verdict if the retry works. ACCEPT: python tools/live_verdicts.py lists a worked verdict for LIVE-SEARCHSTR. ZERO-CLICK: One more try by the player ends in one click plus a short note; the fix is automatic from there. DEPENDS: RUN-VERDICTS-CLOSE. BLOCKED: operator act (one more try in game, with a note saying what the game showed).
- [ ] TC-BUILDFILE-LIVE-FIX (build) Fix what the game refused: An AshLight-made .build file loaded in game (verdict refused 2026-11-22, research 0027 section 5; the clicks landed within 19 s with no note, so no cause is known yet). Once the retry note says what the game showed, find the cause and fix it, or record a worked verdict if the retry works. ACCEPT: python tools/live_verdicts.py lists a worked verdict for TC-BUILDFILE-LIVE. ZERO-CLICK: One more try by the player ends in one click plus a short note; the fix is automatic from there. DEPENDS: RUN-BUILDFILE-LIVE-CLOSE. BLOCKED: operator act (one more try in game, with a note saying what the game showed).
- [ ] AUDIT-46-P3 (build) Audit P3s: installer_stream deadline (P3-2), low-integrity luajit token spike (P3-1), dormant OAuth modules note in decision 0048 (P3-3), wire or delete four test-only functions (P3-4), payload safe_path / _plan_members tests (P3-5), egress originOf / LOG_CAP tests (P3-6), kit ASCII / LF report (P3-7), HEAD on /events and /api/ (P3-8). Why: docs/reviews/audit/2026-11-28.md. ACCEPT: each fixed with its test or split into its own row. ZERO-CLICK: see the audit. BLOCKED: session (decision 0022 / 0048 records).
- [ ] AUDIT-CALC-UILIMITS (build) Give the calc job object JOBOBJECT_BASIC_UI_RESTRICTIONS (clipboard read / write, handles, global atoms, desktop, display, system parameters, exit windows); a failed set refuses the start; Job.limits() and the bridge tests assert the mask. Why: docs/reviews/audit/2026-11-28.md P2-1. ACCEPT: python -m pytest -q tests/test_tc_bridge.py passes with the mask asserted. ZERO-CLICK: set at every bridge start. BLOCKED: session (amends the TC-CALC-CONFINE-PROC entry, decision 0022).
- [ ] AUDIT-IPC-GATE-FRAME (build) al:gate in app/main.js checks Guards.frameIsOverlayPage(e.senderFrame, ...) like al:config, with a guards test that a non-main frame sender is ignored. Why: docs/reviews/audit/2026-11-28.md P2-3. ACCEPT: npm test --prefix app passes with the new case. ZERO-CLICK: main-process check only.
- [ ] LOOP-LANE-WT-CLEAN (build) Lane worktree cleanup: the kit refuses a lane worktree with untracked files and two runs of one lane name at once (session 46 removed three merged findings files by hand). Add tools/al_lane.py clean: byte-compare each untracked file with main's copy, Recycle Bin the identical ones, keep and name the rest, read back an empty git status. ACCEPT: a test over a scratch worktree (identical removed, different kept). ZERO-CLICK: the tick runs clean before a lane dispatch. BLOCKED: session (the loop does not edit its own lane driver).
- [ ] REL-46-P2 (build) Research 0066 P2 rows, before 0.2.1: REL-UPDATE-E2E-RC (F15), REL-REPLACE-RETRY (F3), REL-RUNTIME-FOLDER-HASH (F14), REL-CLOCK-SKEW (F8), REL-APPLYNOW-EDGES (F13), REL-CI-RUNTIME-LEG (G1), REL-CI-DRY-GATE (G6), REL-RELEASE-DRAFT-IDEMPOTENT (F10); split into own rows when taken. ACCEPT: each item fixed with its test or filed as its own row. ZERO-CLICK: see research 0066 section 3. BLOCKED: session (CI dry gate is a publish gate; workflow permissions).
- [ ] REL-BUILD-TOOLCHAIN-GATE (build) release.py stage records sys.version and zlib.ZLIB_RUNTIME_VERSION in stage.json; a new publish gate refuses unless they equal tracked config/release_toolchain.json, which a test pins to release.yml python-version, so a CI rebuild mismatch never burns a pushed tag. Why: research 0066 G2 (P1, before 0.2.0). ACCEPT: python -m pytest -q tests/test_release_publish.py passes with a mismatch refused. ZERO-CLICK: the gate runs inside publish and rehearse. BLOCKED: session (publish gates).
- [ ] REL-CONFIRM-CLIENT (build) Confirm needs the core health answer and a client heartbeat (data/client.alive after parts load); apply-staged --if-due runs from outside the new client (supervisor or a stable home stub) so a client that dies before startCore is counted and rolled back. Why: research 0066 F11b / G5 (P1, before 0.2.0). ACCEPT: python -m pytest -q tests/test_update_switch.py passes with an early-crash client rolled back on the next start. ZERO-CLICK: the next start rolls back by itself. BLOCKED: session (amends decisions 0005 / 0065).
- [ ] REL-UPDATE-WITHDRAW (build) apply-staged drops a staged version that a newer cached releases/latest answer no longer names ("the release was withdrawn"); the runbook pulls a bad release by marking it pre-release. Why: research 0066 F7 / G4 (P1, before 0.2.0). ACCEPT: python -m pytest -q tests/test_update_switch.py passes with staged 0.2.1, cache naming 0.2.0, apply NOT_DUE and the staged file removed. ZERO-CLICK: the daily read and the launcher apply-staged do it. BLOCKED: session (amends decision 0065).
- [ ] UX-INSTALLER-NEXT-STEP (build) Installer success and failure lines end with the next step (Start Menu shortcut; nothing installed, paste again; repairs in place) and print the real report folder, not the literal home placeholder. Why: docs/reviews/ux/2026-11-28.md P2-8. ACCEPT: python -m pytest -q tests/test_install_ps1.py passes with the new lines. ZERO-CLICK: printed by the installer.
- [ ] UX-SETUP-STEP-PLACES (build) Each setup-card step names its place within CAP_ROW 52: build with the bound item key, prices place (installed: trade links only), overlay from the tray; strings on a copy sheet with a test. Why: docs/reviews/ux/2026-11-28.md P1-3. ACCEPT: python -m pytest -q tests/test_playcards.py passes with the exact rows. ZERO-CLICK: rows composed by playcards from hotkeys and copy kind.

## Lane: data

- [ ] LIVE-1-AFK (data) Live-verify the AFK log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the AFK item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-CRUEL (data) Live-verify the Cruel area id log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the Cruel area id item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-GUILD (data) Live-verify the guild log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the guild item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-HIDEOUT (data) Live-verify the hideout log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the hideout item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-MAP (data) Live-verify the endgame Map area id log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the endgame Map area id item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-TRADE (data) Live-verify the trade request log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the trade request item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-WHISPER (data) Live-verify the whisper log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the whisper item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-WAYSTONE (data) Live-verify the waystone item text shape from the parse ledger's masked waystone block. ACCEPT: python tools/live1_report.py prints VERIFIED live for the waystone item. ZERO-CLICK: The operator only presses the item key on a waystone in normal play; the ledger keeps the masked shape by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] ITEM-INFO-POB-CURRENCY (data) When a PoB-PoE2 pin move brings src/Data/CurrencyNames.lua, add its sha256 to config/tc_pins.json pob2_files and a text parser for its real shape in server/al/theorycraft/pobtext.py (never run as Lua, repoe-fork wins), so currency where_found rows show (ITEM-INFO-POB-TEXT follow-up; the file is absent from the current pin). ACCEPT: python -m pytest -q tests/test_tc_pobtext.py tests/test_tc_pob_drift_guard.py tests/test_iteminfo.py passes. ZERO-CLICK: read with the pinned calc component; no setting. DEPENDS: ITEM-INFO-POB-TEXT. BLOCKED: gate, until a PoB pin carries src/Data/CurrencyNames.lua.
- [ ] DATA-PRICE-ALT-ASK (data) Ask a second PoE2 price source (poe2scout.com first) for written app-use permission and its contact and rate terms, then record the answer in a decision; a yes still needs the operator's floor amendment before any provider row (research 0064 G7; decision 0072 silence is not consent). ACCEPT: a decision file records the request, the answer or its absence, and the operator's ruling. ZERO-CLICK: one message sent by the operator; the rest is desk work. BLOCKED: operator act (draft ready at docs/ops/price-alt-ask-draft.md; operator sends).
- [ ] RES-MAP-CONTENT-LINES (data) List the PoE2 Client.txt lines that name a map mechanic or a named boss encounter, from AshLight's own masked shape ledger (decision 0071) and operator-pasted log only, each anchored and with a sighting count; propose map content tags for the map ladder (research 0064 G6). ACCEPT: a research note lists each line with its source and count, indexed in docs/research/README.md. ZERO-CLICK: the ledger fills while the operator plays; the read is the loop's. BLOCKED: gate (ledger span 2026-11-21T22 to 2026-11-23T04, about 30 h, under 7 days, no map shapes, ledger not written since 2026-11-22; re-check 2026-11-29).


## Lane: review

- [ ] TEST-SPLIT-B1-WATCH (review) B1 test_real_loop_body red once at 0.920 percent (3 clock steps, 46.9 ms) in the wave 59 batch 3 whole suite while the concurrent timing-calc stream of TEST-SERIAL-PHASE-CUT ran; 3 isolated gated reruns passed (0.616, 0.000, 0.000) and the next whole suite was green. If it reds again under the split phase 2, apply decision 0060's split reverses-if (SPLIT_TIMING False, or run B1 after both streams), never move the budget. ACCEPT: 5 later gated whole suites green on B1, or the split change landed with a soak. ZERO-CLICK: test-side only. DEPENDS: TEST-SERIAL-PHASE-CUT. BLOCKED: session (watch).
- [ ] TEST-DEMO-PORT-FLAKE (review) The session 30 first gated whole suite red on 3 tests in tests/test_port_lease.py and tests/test_play_states.py (29/29 pass alone, next whole suite green); suspected contention for the demo port block 8970-8975 in the parallel phase 1. Find the shared port or lease, then pin those tests to one xdist group or give them distinct ports; never widen a timeout. ACCEPT: the cause is named and 5 later gated whole suites are green on both files. ZERO-CLICK: test-side only. BLOCKED: session (watch).
- [ ] CI-WATCH-ELECTRON-45-5-0 (review) The CI watch workflow holds an open al-watch key for electron (key 45.5.0): run that source's check on the dev host, act on the finding, then move its pin or its tools/watch_ci.py baseline. ACCEPT: the key issue closes on the next watch workflow run. ZERO-CLICK: the daily workflow watches while the dev host is off. BLOCKED: session (decision 0076: a session acts on the finding and moves the pin or the baseline). SOURCE: watch ci electron 45.5.0, filed 2026-11-28.


## Theorycraft and item optimization (decision 0004, research 0010)

Phase 1 is stdlib-only file interop with Path of Building PoE2; phase 2
adds the optional pinned LuaJIT + PoB calc subprocess. Rows run in order.
Every row carries the minimal-interaction constraint (CLAUDE.md, decision
0004): no click the app can safely make for the user, state updates itself,
and the row's own dev / test steps run unattended. ZERO-CLICK states how.

- [ ] TC-OAUTH-REG (review) Send the GGG application when registration reopens, record the answer.
  The application is ready: docs/ops/ggg-oauth-application.md (decision 0048); scopes:
  account:characters only.
  ACCEPT: python -m pytest -q tests/test_ascii_lf.py tests/test_research_numbers.py
  tests/test_leak_sweep.py tests/test_audit_pass2.py passes; the decision holds a dated line for the
  send and, when it comes, GGG's reply to each of the three questions. ZERO-CLICK: No reminder: the
  watch raises the flag and the loop files the row; one operator act when it does. DEPENDS:
  DATA-GGG-APPLICATION. BLOCKED: GGG reopens OAuth application registration; unblocks when
  ops/runtime/ggg_docs/REG_OPEN exists (the settled decision 0044 watch; its index-page read is
  under operator decision A-01), or the hand-off holds the operator's own line 'REG OPEN (operator)'
  (GGG).
- [ ] TC-IMPORT (build) Character import through GGG's OAuth, one browser approval per 7 days at
  most (decision 0048). ACCEPT: python -m pytest -q
  tests/test_tc_import.py tests/test_gggapi.py tests/test_floor_static.py passes. ZERO-CLICK: One
  Connect click per session and one Refresh click per re-read until GGG's written yes; after it no
  click between approvals. A lapse shows the last import with its age on the dashboard, never the
  overlay. DEPENDS: TC-CHARJSON-SHAPES, TC-GGG-CLIENT-CORE, TC-OAUTH-REG, DATA-GGG-APPLICATION.
  BLOCKED: GGG reopens OAuth registration (the docs watch raises ops/runtime/ggg_docs/REG_OPEN) and
  grants AshLight a public client; event fetches and stored refresh also wait for GGG's written
  answers to F-083 questions 1 and 2; unblocks when a client id granted to AshLight is recorded in
  gitignored config/local.json after the operator sends the prepared application (F-149) (GGG).

### Math (non-engine; area-math lane, 2026-11-17)

Legitimate math around PoB interop, never an own damage / EHP calc engine
(decision 0004): parsing, normalisation, value and codec robustness. Stat
weights derived from PoB outputs stay with TC-DELTA.


## Research-filed features (AREA-RES 2026-11-17, research 0020)

Ranked in research 0020; floor checks there. Rulings by adjudicator
recorded in research 0018 section 3.

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
- FOLDED 2026-11-18: TC-BUILDFILE-LIVE -> RUN-BUILDFILE-LIVE-CLOSE (docs/plan/07 Coverage; the old row text is in git history).
- [ ] TC-CURX (build) Hourly exchange history from GGG's documented public Currency Exchange API
  (`web.poecdn.com/api/currency-exchange/poe2/<hour>`, research 0018). Deferred (F-206): opens on
  GGG's written answer to question 3 or an own client. BLOCKED: no AshLight OAuth
  client (adjudicator ruling 2026-11-17: standalone executables must use a public OAuth client);
  unblocks when GGG grants AshLight a public OAuth client (TC-OAUTH-REG done) or exempts scope-less
  endpoints in writing (question 3 of DATA-GGG-APPLICATION) (GGG; a session records it). No package
  in docs/plan/07 (Coverage: not adopted, F-206 disposition); cut if poe.ninja's exchange data stays
  sufficient. ACCEPT: when unblocked, OAuth UA, immutable-hour cache, parser tests. ZERO-CLICK:
  background fetch on the hourly boundary once enabled.

## Research-filed features, batch 2 (AREA-RES 2026-11-17, research 0022-0023)

Ranked in research 0023; loot filter ruling (adjudicator) in 0022 section 3.


## Research-filed features, batch 3 (AREA-RES 2026-11-17, research 0028)

Ranked in research 0028; floor rulings (adjudicator 2026-11-17) in its
section 6. Phone view over the LAN is an OPERATOR decision (CLAUDE.md:
LAN access stays off), not a row.


## Research-filed features, batch 4 (AREA-RES 2026-11-17, research 0031)

Ranked in research 0031; floor rulings G / H / I (adjudicator 2026-11-17)
in its section 5. UTIL-CRAFT-SLOTS and UTIL-ATLAS-PROGRESS are listed
there only; Acts 5-6 boss / zone data rides UTIL-1.0-POST.


## Research-filed features, batch 5 (AREA-RES 2026-11-17, research 0032)

Ranked in research 0032; floor rulings J / K / L (adjudicator 2026-11-17)
in its section 6. UTIL-ATLAS-PROGRESS and LANG-PACKS are listed there
only (blocked on live 1.0 / localised logs).


## Game settings advisor (operator order 2026-11-16)

## Design and UX audit (operator order 2026-11-16)

Uses the design-reviewer agent (.claude/agents/design-reviewer.md) and the
design docs in docs/design/, both made by a separate agent.




Rows filed by the first audit (docs/design/0002-first-audit.md; S1 = worst).
Run after DESIGN-AUDIT, ahead of DESIGN-GATE.

## Testing and hardening (AREA-TEST, session 4)



## Utility (lane area-util, 2026-11-17)


## Ops

Operator answers 2026-11-26 (session 29): OA-8 done (web_data on, contact = the project's issues
page, web_data_ack 1; read back by GET /api/web-data: web_data true, contact_set true, acked true,
blocked null). OA-5 answered: default kept (the gh account as holder, name AshLight). OA-9
answered: decision 0017 kept (trade link only). Every other operator act keeps its default.


## Audit 2026-11-17 (docs/audit/2026-11-17-audit.md)

Low findings filed by AREA-AUDIT; the medium ones were fixed in the audit
merge. Each row names the finding ids it closes.






- FOLDED 2026-11-18: AUDIT-P8-LOW -> RUN-START-REASON-CORE, RUN-OBS-LOGS-SHELL, RUN-LADDER-TICK, RUN-REPORT-FIELDS, RUN-P8-8-CHARMIX, RUN-BUDGET-TESTS-DASH (docs/plan/07 Coverage; the old row text is in git history); P8-3 to P8-8 all landed, the last RUN-P8-8-CHARMIX in wave 34, 2026-11-23).


- FOLDED 2026-11-18: CODE-HEALTH-FOLLOWUP -> TEST-STATE-EQUIV, RUN-ZONE-RESET, TEST-STATE-TEXT-2, TEST-STATE-TEXT-3, TEST-STATE-TEXT-4, TEST-STATE-TEXT-PINS, TEST-WEB-FMT, RUN-DURABLE-CRLF (docs/plan/07 Coverage; the old row text is in git history). Item (1) state.py text split delivered 2026-11-21 by TEST-STATE-TEXT-PINS (server/al/text/, design gate and reviewer moved); item (2) web/ pad / duration / clock dedup delivered 2026-11-19 by TEST-WEB-FMT; item (3) CRLF runtime writers (F-014) delivered 2026-11-18 by RUN-DURABLE-CRLF. All three done; closed.


- FOLDED 2026-11-18: MERGE-SEAMS-FOLLOWUP -> PLAY-TD-01B-FIT-HARNESS, PLAY-TD-09B-SKELETON, PLAY-TD-09C-BAR (docs/plan/07 Coverage; the old row text is in git history). F1 (Play fit with both slots full) delivered 2026-11-18 by PLAY-TD-01B-FIT-HARNESS (figures in docs/design/play-fit-figures.md); F4 (Play column focus) delivered 2026-11-18 by PLAY-TD-09B-SKELETON; F2 (one bar status word, live-region cap 11) delivered 2026-11-18 by PLAY-TD-09C-BAR; F5 and F7 delivered 2026-11-18 by PLAY-MERGE-SEAMS-F5-F7, folded into PLAY-TD-09C-BAR. All of F1, F2, F4, F5, F7 done; closed.

- FOLDED 2026-11-18: S5-FOLLOWUP -> DATA-GUIDE-FACTS, DATA-GUIDE-GAP-TUNE, OVL-ZONE-CARD, OVL-LINE2-GUIDE (docs/plan/07 Coverage; the old row text is in git history).


## Execution plan (docs/plan/07-execution-plan.md)

One row per package of docs/plan/packages.json (396 rows, landed 2026-11-18 from
`python tools/plan_check.py rows`), grouped by wave in merge order. docs/plan/07 is the
plan; docs/plan/08 says how a session runs a wave and how it flips a row.
Session rows carry `BLOCKED: session wave <n>`: the loop lists them and never dispatches
them (08 section 8). Parked rows (wave 99) carry `BLOCKED: <on>; unblocks when <condition>
(<who>)`. The 16 loop-owned rows carry no BLOCKED and name their deps in `DEPENDS:`; the
current parser does not read `DEPENDS:` (LOOP-ROWFILES-WORK, wave 3, teaches it), so until
then ops/loop/control/HALT alone holds them; HALT stays until AUTO-21 (wave 6), which
depends on LOOP-ROWFILES-WORK (07, HALT removal and the headless loop).
Rows whose id was already an open row were replaced in place (pointer lines below); open
rows that packages cover under other ids keep a FOLDED pointer line where they were.

### Wave 0: plan landing


### Wave 1: loop and watchers, local security, reliability and observability


### Wave 2: loop and watchers, local security, reliability and observability


### Wave 3: loop and watchers, tests and code seams, theorycraft


### Wave 4: go-public, Play tab and dashboard, theorycraft


### Wave 5: Play tab and dashboard, reliability and observability, overlay and client


### Wave 6: Play tab and dashboard, local security, reliability and observability


### Wave 7: Play tab and dashboard, tests and code seams, reliability and observability


### Wave 8: tests and code seams, install and release, reliability and observability


### Wave 9: install and release, tests and code seams, overlay and client


### Wave 10: install and release, overlay and client, tests and code seams


### Wave 11: install and release, theorycraft, tests and code seams


### Wave 12: install and release, overlay and client, theorycraft


### Wave 13: loop and watchers, reliability and observability, theorycraft


### Wave 14: reliability and observability, install and release, theorycraft


### Wave 15: loop and watchers, reliability and observability, theorycraft


### Wave 16: theorycraft, loop and watchers, reliability and observability


### Wave 17: go-public, theorycraft, tests and code seams


### Wave 18: go-public, web data, reliability and observability


### Wave 19: reliability and observability, web data, install and release


### Wave 20: overlay and client, install and release, tests and code seams


### Wave 21: overlay and client, install and release, reliability and observability


### Wave 22: install and release, reliability and observability, overlay and client


### Wave 23: install and release, overlay and client, tests and code seams


### Wave 24: reliability and observability, web data, theorycraft

- [ ] REL-CUTOVER-LIVE (build) Cut-over: the operator's live copy becomes an installed release.
  ACCEPT: GET /api/health on 127.0.0.1:8960 answers mode 'installed' with version 0.2.0-rc.0 from
  <sidecar>\Install, the checkout answers on 127.0.0.1:8961 with mode 'checkout', and a re-run of
  the checkout's setup.ps1 -NoShortcut leaves the installed copy's shortcuts and logon task alone
  (read back with the scripts/al_shell.ps1 readers). ZERO-CLICK: Waits for game_idle by itself; no
  operator step. DEPENDS: DEP-13, DEP-09, REL-UNINSTALL-SHELL, REL-UPDATE-LAUNCH, REL-UPDATE-CHECKS,
  REL-RUNTIME-SCRIPTS, REL-BUILD-ASSETS. BLOCKED: operator act (prep done session 19: 0.2.0-rc.0 built in the sidecar Build release folder; install not run because install.ps1 always writes shortcuts; the operator runs the prepared switch-over script in the sidecar Scratch cutover folder, cutover.ps1, which waits for game_idle; adjudicator ruling 2026-11-21: agents never start or stop the app).

### Wave 25: local security, overlay and client, theorycraft


### Wave 26: Play tab and dashboard, install and release


### Wave 27: tests and code seams, reliability and observability, Play tab and dashboard


### Wave 28: Play tab and dashboard, reliability and observability


### Wave 29: Play tab and dashboard, overlay and client


### Wave 30: overlay and client, tests and code seams, loop and watchers


### Wave 31: Play tab and dashboard, reliability and observability


### Wave 32: reliability and observability, install and release


### Wave 33: Play tab and dashboard, tests and code seams, reliability and observability


### Wave 34: install and release, tests and code seams, Play tab and dashboard


### Wave 35: theorycraft, tests and code seams


### Wave 36: web data


### Wave 37: reliability and observability


### Wave 38: operator requests 2026-11-19, cores


### Wave 39: operator requests 2026-11-19, popover and templates


### Wave 40: operator requests 2026-11-19, engine and tabs


### Wave 41: operator requests 2026-11-19, Kindler plan and card collapse


### Wave 42: operator requests 2026-11-19, Kindler result card


### Parked

- (TC-IMPORT: its row is replaced in place under '## Theorycraft and item optimization (decision 0004, research 0010)'.)
- [ ] DATA-LOOT-TALLY (build) Loot tally from the items the player checked. ACCEPT: python -m pytest
  -q tests/test_loot_tally.py tests/test_util_price_watch.py tests/test_util_maprun.py passes and
  npm test --prefix app passes. ZERO-CLICK: Counted on presses the player already makes. DEPENDS:
  DATA-CONTACT-FIELD, DATA-DIAG-SEAM, DATA-GUIDE-MERGE, DATA-GUIDE-ONE-BLOCK, DATA-GUIDE-BOSS,
  TC-PRESS-FIXTURES. BLOCKED: a real stackable item text sample confirming the stack-size line;
  unblocks when TC-PRESS-FIXTURES (TC cluster, F-082) is merged: the F-082 sample presses were made
  with the dev-host sample switch on (Q-27) and the stackable fixture with its parsed stack size is
  in the tree (operator).
- [ ] TC-WAYSTONE-TUNE (build) A waystone card the player can tune (core). ACCEPT: python -m pytest
  -q tests/test_waystone.py tests/test_waystone_reward.py tests/test_ux_settings_io.py
  tests/test_overlay_layout.py passes. ZERO-CLICK: Defaults unchanged; tuning is optional and saved
  on change. DEPENDS: TC-PRESS-FIXTURES, TC-WEIGHTS-DELTA-EXPORT, TC-CALC-IDLE. BLOCKED: a real
  waystone sample as a fixture; unblocks when tests/fixtures/press holds a reviewed waystone fixture
  (package TC-PRESS-FIXTURES).
- [ ] DEP-18 (build) First public release 0.2.0. ACCEPT: gh release view v0.2.0 shows a published
  immutable release with digests equal to the staged SHA256SUMS.txt, and GET /api/health on the
  operator's installed copy answers version 0.2.0 after its own staged update (no manual step).
  ZERO-CLICK: One operator phrase for the tag; the live copy updates itself. DEPENDS: REL-RC-LIVE,
  REL-AUTOSTART-SETTINGS, REL-UPDATE-TRIGGER, DEP-19, REL-CUTOVER-LIVE, REL-STAGE-SANDBOX, DEP-02,
  DEP-14, DEP-04, GP-12, GP-15, DATA-PRICE-CADENCE. BLOCKED: the public flip, the project's address
  in tracked files, the release build's poe.ninja switch settled (off by default) and the operator's
  release phrase; unblocks when the repository is public (go-public flip package done, all P0
  packages green at the flip commit), the address package has put the real owner/name into the
  tracked config and the README install line, the release build's poe.ninja switch is settled (off,
  or a decision records poe.ninja's yes), and the operator types 'release 0.2.0' in an interactive
  session (operator).
- [ ] REL-RC-LIVE (build) First release candidate on the private repository. ACCEPT: gh release view
  v0.2.0-rc.1 shows a published immutable pre-release whose asset digests equal the staged
  SHA256SUMS.txt, gh attestation verify and gh release verify-asset pass on the app zip, a plain
  commit pushed after it triggered no release run, and after 'installer update --zip
  AshLight-0.2.0-rc.1-app.zip' on the live installed home GET /api/health on 127.0.0.1:8960 answers
  0.2.0-rc.1. ZERO-CLICK: One operator phrase for the tag; bump, notes, stage, CI and read-back run
  themselves. DEPENDS: REL-PUBLISH-READBACK, DEP-15, REL-STAGE-ROUNDTRIP, DEP-14, AUTO-16,
  REL-CUTOVER-LIVE, DEP-04, DEP-02, GP-09, GP-02, PUB-HOOK-RELEASE-CHECK. BLOCKED: the private
  remote, the immutable-releases setting and the operator's release phrase; unblocks when the
  private repository exists with main pushed and CI green (go-public remote package), the guarded
  pre-push hook with the prepush-check call is merged, immutable releases are on before the first v*
  tag, and the operator types 'release 0.2.0-rc.1' in an interactive session (operator).
- [ ] TC-BUILD-FILEPICK (build) Load a build from a save file the player picks. ACCEPT: python -m
  pytest -q tests/test_tc_build_filepick.py tests/test_http_security.py passes and npm test --prefix
  app passes. ZERO-CLICK: One pick per build change, the player's own act; no folder read, no
  watcher. DEPENDS: TC-CARD-PARTS-WEB. BLOCKED: operator decision Q-02 file half: one line in the
  CLAUDE.md read list allowing a file the player picks in AshLight's own page (bytes only, never a
  path or a stored copy); unblocks when the operator adds that read-list line to CLAUDE.md in their
  own words; until then nothing of F-058 is built (operator).
- [ ] SEC-STEAM-SCAN-A03 (build) Apply operator decision A-03 to the Steam library scan. ACCEPT:
  Strict branch: `git grep -n -i "libraryfolders\|winreg" -- server` prints nothing and `python -m
  pytest -q tests/test_no_discovery.py tests/test_e2e_replay.py tests/test_tailer.py
  tests/test_diag_self.py tests/test_floor_static.py` passes. Allowed branch: decision 0003 cites
  the operator's read-list line and the same test run passes unchanged. ZERO-CLICK: No player click
  on either branch. With the scan gone the first-run card shows the typed path field and one Checks
  line; consent and the visible indicator are unchanged. Narrows what is read; reads nothing new.
  DEPENDS: SEC-NO-DISCOVERY, SEC-LOG-PATH-FIELD. BLOCKED: operator decision A-03 (one floor line: is
  finding Client.txt through Steam's registry key and libraryfolders.vdf on the read list); with no
  answer the stricter reading applies once the typed path field exists; unblocks when the hand-off
  records the operator's A-03 answer, or the ROADMAP row of SEC-LOG-PATH-FIELD is flipped and no
  answer is recorded (then the strict branch is built) (operator).
- [ ] AUTO-24 (build) POLICY-QUOTES: the floor's 12 source quotes under watch. ACCEPT: `python -m
  pytest -q tests/test_policy_wording_watch.py tests/test_ggg_docs_watch.py
  tests/test_watch_rows.py` passes. ZERO-CLICK: Unattended once allowed: same six pages, cadence and
  identity as decision 0044, no new request. DEPENDS: AUTO-05, LOOP-WATCH-ROWS, LOOP-WATCH-WIRE,
  AUTO-11. BLOCKED: operator decision A-01: one floor line saying whether GGG's developer-docs pages
  outside the API Reference and Data Exports may be read (the 12 quotes live on the index page);
  unblocks when the operator writes that floor line in CLAUDE.md and it allows the index page
  (operator).
- [ ] TC-WAYSTONE-TUNE-UI (build) Waystone rule switches on the dashboard. ACCEPT: npm test --prefix
  app passes and python -m pytest -q tests/test_ux_review.py tests/test_a11y.py passes. ZERO-CLICK:
  Defaults unchanged; one change per rule the player wants different. DEPENDS: TC-WAYSTONE-TUNE,
  TC-WEIGHTS-DELTA-UI. BLOCKED: the core half; unblocks when TC-WAYSTONE-TUNE is merged (package
  TC-WAYSTONE-TUNE).
- [ ] TC-IMPORT-UI (build) Connect and Refresh controls on the Build tab. ACCEPT: npm test --prefix
  app passes and python -m pytest -q tests/test_ux_review.py tests/test_a11y.py passes. ZERO-CLICK:
  One Connect click per session and one Refresh click per re-read until GGG's written yes; none
  after it. DEPENDS: TC-IMPORT, TC-CARD-PARTS-WEB. BLOCKED: the core half of the import; unblocks
  when TC-IMPORT is merged (package TC-IMPORT).
- [ ] OVL-ITEM-KEY-CTRL (build) Item-check default chord moves under Ctrl once the operator names a
  free letter. ACCEPT: node --test app/test/hotkey.test.js app/test/eval.test.js and python -m
  pytest -q tests/test_audit_pass5_low.py tests/test_floor_static.py pass with the new default in
  the case table. ZERO-CLICK: Two presses under one hold (the player's own Ctrl+C, then the AshLight
  key); the floor forbids fewer with the clipboard. Nothing is sent to the game. DEPENDS:
  OVL-KEYS-WEB, OVL-COPY-FIRST. BLOCKED: operator decision Q-09 (two one-minute key checks);
  unblocks when the operator reports whether Alt+Shift+E / Alt+Shift+A flip the keyboard layout with
  two layouts installed and names one unbound Ctrl+letter next to C from the game's key binds
  (operator).
- [ ] DATA-NINJA-RELEASE-ON (build) Turn release-build poe.ninja polling on after poe.ninja's yes.
  ACCEPT: python -m pytest -q tests/test_price_cadence.py passes and the decision file quotes the
  answer with its date. ZERO-CLICK: Nothing for players. DEPENDS: DATA-PRICE-CADENCE. BLOCKED:
  poe.ninja's answer to the Q-05 message; unblocks when the operator pastes poe.ninja's written yes
  (or its mirror request, which opens a new decision instead); silence is not consent (poe.ninja).
- [ ] PLAY-MAP-MODE-ON (build) Switch map mode on in region C. ACCEPT: python -m pytest -q
  tests/test_play_view.py tests/test_play_fit.py passes with play.map_ok true: the map state shows
  mode map in region C within its track and a replayed session shows the map block in a map and the
  guide in a campaign zone. ZERO-CLICK: Follows the log; no click. DEPENDS: PLAY-TD-07B-PLAY-CARDS,
  PLAY-TD-11-CONTEXT, RUN-LEDGER-REPORT. BLOCKED: A live sighting of the endgame map area prefix in
  the parse ledger of F-061 (RUN cluster); unblocks when python tools/live1_report.py (built by
  RUN-LEDGER-REPORT) prints VERIFIED live for the endgame Map area-id prefix item of LIVE-1, after
  the operator has ticked the parse-ledger consent line once and played one map normally (operator).
- [ ] DATA-GUIDE-ACTS-5-6 (data) Guide entries for Acts 5-6 and the interlude decision after the 1.0
  launch. ACCEPT: python -m pytest -q tests/test_zone_guide.py tests/test_util_10_fixtures.py
  tests/test_provenance.py passes with a 1.0 world_areas snapshot in the cache. ZERO-CLICK: The
  launch gate opens the row by itself; the guide then follows the log. DEPENDS: DATA-GUIDE-FACTS,
  AUTO-07. BLOCKED: PoE2 1.0 is live and a 1.0 world_areas snapshot is cached on the dev host;
  unblocks when the launch gate GATE-POE2-10 (F-052 / AUTO-07) has flipped: local date 2026-12-11 or
  later and the snapshot metadata shows 1.0; the cache refresh needs web data on and the contact set
  on the dev host (act g, OA-8 done 2026-11-26), or an operator-run build.ps1 -Snapshot (GGG).
- [ ] TC-PRESS-FIXTURES (review) Real item-press fixtures for six shapes. ACCEPT: python -m pytest
  -q tests/test_press_fixtures.py tests/test_math_item.py tests/test_leak_sweep.py passes with six
  fixture shapes present. ZERO-CLICK: A one-time check: six presses during normal play, then the
  tests run themselves. DEPENDS: TC-PRESS-SAMPLES. BLOCKED: six item presses in normal play with
  dev_press_samples on (rare gear, a unique, a currency stack, a waystone, a tablet, a gem; plain
  and advanced copy); unblocks when at least six sanitized candidate files, one per shape, exist
  under the sidecar Scratch press-samples folder (operator).
- [ ] DATA-GUIDE-GAP-TUNE (build) Tune the clear-or-push threshold from play data. ACCEPT: python -m
  pytest -q tests/test_zone_guide.py tests/test_util_underlevel.py passes and the commit message
  cites the sample size. ZERO-CLICK: Automatic for the player; the data comes from normal play.
  DEPENDS: DATA-GUIDE-MERGE, DATA-GUIDE-BOSS, RUN-LEDGER-WIRE. BLOCKED: two weeks of
  level-minus-zone-level data per campaign zone exit; unblocks when the parse ledger packages
  (RUN-LEDGER-CORE, RUN-LEDGER-CONSENT (folded into RUN-METRICS-SITES), RUN-LEDGER-WIRE; F-061) are
  merged with the per-exit gap bucket, the operator has ticked the ledger consent, and the dev
  host's ledger spans 14 days of campaign play (operator).
- [ ] TC-AFFIX-LINE (build) Affix line on the item card. ACCEPT: python -m pytest -q
  tests/test_tc_affix_line.py tests/test_eval_text.py passes. ZERO-CLICK: Same press; no click.
  DEPENDS: TC-CARD-PARTS, TC-PRESS-FIXTURES. BLOCKED: a real advanced-copy item sample as a fixture;
  unblocks when tests/fixtures/press holds a reviewed advanced-copy gear fixture (package
  TC-PRESS-FIXTURES).
- [ ] PLAY-F-204B-SR-RUN (build) One real screen-reader pass: the run and its transcript. ACCEPT:
  python -m pytest -q tests/test_sr_pass.py tests/test_ascii_lf.py tests/test_leak_sweep.py passes
  with docs/design/screen-reader-pass.md present: it is dated, lists the five steps, and has no
  unnamed or doubled announcement. ZERO-CLICK: A dev task run once with the operator's go-ahead; no
  player step. DEPENDS: PLAY-F-204A-SR-TOOL. BLOCKED: The operator confirms the game is closed (not
  only that they are not playing) and game_idle is true; speech output and a visible browser on this
  machine; unblocks when The operator says in their own words that the game is closed and allows one
  run with speech output and a visible browser; the agent then runs python tools/sr_pass.py with the
  operator flag once, game_idle true, and commits the transcript (operator).
- [ ] RUN-LIVE-CLICKS-CLOSE (review) Close TEST-LIVE-CLICKS from the passive read-back. ACCEPT:
  python tools/live1_report.py prints all five read-back fields as seen and python -m pytest -q
  tests/test_ascii_lf.py tests/test_research_numbers.py tests/test_leak_sweep.py passes. ZERO-CLICK:
  The operator only logs in as usual with the client running. DEPENDS: RUN-LIVE-CLICKS-STRIKE,
  RUN-LEDGER-WIRE, RUN-LEDGER-REPORT. BLOCKED: one normal login to town or hideout while the core
  runs; unblocks when python tools/live1_report.py prints the five TEST-LIVE-CLICKS fields as seen
  (operator).
- [ ] RUN-OVL-BUDGET-CLOSE (review) Close OVL-BUDGET from the budget log. ACCEPT: python -m
  server.al.budgetlog check exits 0 and prints at least 10 rows tagged in map with the overlay
  shown, and python -m pytest -q tests/test_ascii_lf.py tests/test_research_numbers.py
  tests/test_leak_sweep.py passes. ZERO-CLICK: The operator only plays one map with the client
  running. DEPENDS: RUN-BUDGET-LOG-CORE, RUN-BUDGET-LOG-CLIENT, RUN-BUDGET-TESTS-LIVE. BLOCKED:
  normal play with the budget log on (no operator act); closes from the log.
- (TC-OAUTH-REG: its row is replaced in place under '## Theorycraft and item optimization (decision 0004, research 0010)'.)
- (OVL-FPS: its row is replaced in place under '## Lane: build'.)
- [ ] LOOP-KIT-REPORT-SEND (review) KIT-REPORT: send the drafted note once a destination inbox
  exists. ACCEPT: The last line for the note in ops/loop/control/delivery.jsonl reads `"reached":
  true` with `"count": "1/1"`. ZERO-CLICK: Sent by the tick's own note path (InboxMixin.deliver_note
  / redeliver) under the 12-a-day cap; no operator step after the destination is configured.
  DEPENDS: AUTO-25. BLOCKED: no outbound note path: loop.dest_inboxes in the gitignored
  config/local.json has no entry for the fleet owner and no fleet roster is configured; unblocks
  when loop_base.load_config(root)['dest_inboxes'] holds a MAIN entry (set on the host by the
  operator, or supplied by the fleet owner) (operator).
