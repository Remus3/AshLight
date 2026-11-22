# AshLight ROADMAP

Open work only, as lane rows the loop (`tools/al_loop.py`) can dispatch.
Format: `- [ ] ID (lane) title. ACCEPT: ...`; `(priority)` jumps the queue.
Rows are filed as `docs/roadmap/new/<ID>.md` and closed as
`docs/roadmap/done/<ID>.md`, and folded in at /done.

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
- [ ] CORE-REGOPEN-ROOT (build) A test core's Checks stat of the docs-watch flag (core.py, REG_OPEN under paths.runtime_dir()) reads the real ops/runtime folder; it must use the core's own runtime root so a test or demo core never touches live runtime (found by PLAY-TD-01A-PLAY-STATES). ACCEPT: python -m pytest -q tests/test_play_states.py passes with a test that a core on a tmp runtime root never stats the live ops/runtime path. ZERO-CLICK: No click: a code fix the loop lands by itself. BLOCKED: session wave 7.
- [ ] TC-CARD-PARTS-DOC (build) Item card words in design 0001 section 9 (TCP-8 of the TC-CARD-PARTS
  review): one line naming the mark words (Upgrade, Sidegrade, Downgrade, Not checked, Risky, No risky
  mods), the tones of cardparts.TONES and the rule that a part changes only WORD_KEYS, plus a doc
  test that the section 9 list matches the module. ACCEPT: python -m pytest -q
  tests/test_tc_cardparts.py passes with that doc test. ZERO-CLICK: No click: a doc and test edit
  the loop lands by itself. DEPENDS: TC-CARD-PARTS. BLOCKED: session wave 7.
- [ ] TC-EVAL-NOTES-STYLE (build) Card notes list style (TCPW-1 of the TC-CARD-PARTS-WEB review): web/app.css gets a rule for #eval-notes (no bullets, the card's own spacing) so the notes read as part of the card. ACCEPT: python -m pytest -q tests/test_ux_review.py passes and npm test --prefix app passes. ZERO-CLICK: No click: a style edit the loop lands by itself. DEPENDS: TC-CARD-PARTS-WEB. BLOCKED: session wave 7.
- [ ] TC-OVL-CARD-TONE (build) Overlay card honours the core tone (TCP-3 of the TC-CARD-PARTS review): app/shared/format.js takes the card's tone from the core snapshot instead of its own edge rule, as the dashboard does. ACCEPT: npm test --prefix app passes with a test that a core tone overrides the edge colour. ZERO-CLICK: No click: the overlay follows the core's tone by itself. DEPENDS: TC-CARD-PARTS-WEB. BLOCKED: session wave 7.
- [ ] RUN-UNREADABLE-WORD (build): give the "Client.txt can't be read" state one status word: add an unreadable state to server/al/data/status_words.json with copies in web/status.js and app/shared/render_gate.js (kit blocked, bar "can't read Client.txt", overlay at most 15 characters), make diag.check_reading use _state_check, and add the new log-state sentences (five reset sentences, restarted / unreadable / readable lines, the two Reading-row strings) to docs/design/0001-design-system.md section 9 (review SRW-1, SRW-2). ACCEPT: bar, overlay and Checks name the same state; status-word tests green. ZERO-CLICK: the word follows the reader state by itself; no click. DEPENDS: TEST-STATE-TEXT-PINS, RUN-REPORT-FIELDS, OVL-KEY-HINT, REL-UPDATE-CHECKS, TEST-COPY-SHEETS. BLOCKED: session wave 24 (UNREADABLE-RETAG, session 18: package RUN-UNREADABLE-WORD; wave 22 owns render_gate.js and diag.py, wave 23 render_gate.js, design 0001 and diag.py; wave 24 owns none; the earlier wave 20 tag had no package).
- [ ] PLAY-PAGER-SCALE-24 (build) Confirm the pager buttons (.al-pager-btn, 1.5rem) and the compact weight inputs stay at least 24 px when the UI scale --al-s is below 1; clamp with max(24px, 1.5rem) if not; make the disabled dashed edge 2px if it reads faint (D-2). The D-1 #prices-title tabindex part is split out to PRICES-TITLE-TABINDEX (ruling Q2 amended, 2026-11-21). ACCEPT: python -m pytest -q tests/test_play_fit.py tests/test_ux_review.py passes and npm test --prefix app passes with the scale below 1 measured at 24 px or more. ZERO-CLICK: Nothing for players; a layout floor that holds by itself. DEPENDS: PLAY-TD-19D-ITEMS-GRID, PLAY-TD-20A-RUN-GRID. BLOCKED: session wave 24.
- [ ] BUILD-GEAR-EMPTY-COPY (build) PLAY-TD-19E-ITEM-TEXT review D-3 (nit): the Build card's empty-gear row text "No gear in this build." (web/panels/build.js) should say what to do next in the voice of design 0001 section 9 (for example how gear appears once the build is pasted with items). ACCEPT: npm test --prefix app passes and python -m pytest -q tests/test_build_item_text.py tests/test_ux_review.py passes with the new sentence. ZERO-CLICK: Shown by itself when a build has no gear; no click. DEPENDS: PLAY-TD-19E-ITEM-TEXT. BLOCKED: session wave 22.
- [ ] CARD-LINE-LIMIT (build) OVL-CONTRAST-PIXELS finding (strict xfail): a 34-character capitals-and-digits card line renders at about 292 px against the 236 px inside width; lower the card character limit (app/shared/format.js maxLen defaults and CARD_LINE in server/al/text/common.py), never the font size, and turn the xfail into a pass. ACCEPT: python -m pytest -q tests/test_overlay_pixels.py tests/test_glance_rules.py passes with the xfail removed and npm test --prefix app passes. ZERO-CLICK: Nothing for players; card lines fit by themselves. DEPENDS: OVL-CONTRAST-PIXELS. BLOCKED: session wave 22.
- [ ] DEP14-UNINSTALL-LINE (build) DEP-14 left the stale Quick start sentence 'There is no uninstall script yet' in README.md (uninstall.ps1 exists, decision 0066) and its pin in tests/test_public_docs.py; replace it with the uninstall step and update the test; also finish DEP-14 review D11 (item 1 line still a fragment). ACCEPT: python -m pytest -q tests/test_public_docs.py tests/test_readme.py tests/test_docs_fresh.py passes. ZERO-CLICK: Document edit; no click. DEPENDS: DEP-14. BLOCKED: session wave 22.
- [ ] HOME-REFUSAL-COPY (build) REL-HOME-REFUSAL-UI review: S3 the shared refused-home sentence (server/al/paths.py home_refusal and app/client/home.js) is lowercase with no full stop, make it a sentence in both; S4 design 0001 section 7 should allow a blocking OS error box only for a start-up refusal. ACCEPT: npm test --prefix app and python -m pytest -q tests/test_install_paths.py pass and section 7 carries the start-up refusal exception. ZERO-CLICK: Shown once at a refused start; no click. DEPENDS: REL-HOME-REFUSAL-UI, OVL-CONTRAST-PIXELS, OVL-LINE2-RULE, PLAY-TD-20A-RUN-GRID. BLOCKED: session wave 22 (W22-FOLD: also carries the folded RUN-GRID-DESIGN-WORDS, HUD-PLATE-WIDTH-DOC and PLAN03-LINE2-WORDING; one wave-22 owner of design 0001).
- [ ] PRICES-TITLE-TABINDEX (build) D-1 split from PLAY-PAGER-SCALE-24 (ruling Q2 amended 2026-11-21): add tabindex=-1 to the #prices-title markup in web/index.html so focus can land on it; fold into DATA-CONTACT-UI, the wave 24 owner of web/index.html. ACCEPT: python -m pytest -q tests/test_a11y.py passes and npm test --prefix app passes. ZERO-CLICK: Nothing for players; focus lands by itself. BLOCKED: session wave 24.
- [ ] REPORT-DOC-QUIET (build) server/al/plug/report.py docstring still describes the snapshot report text and minute stamp that RUN-QUIET-FEED removed; restate it for the quiet feed (report text built only on the click, ages stepped at 5 minutes). ACCEPT: python -m pytest -q tests/test_quiet_feed.py tests/test_diag_self.py passes. ZERO-CLICK: Docstring edit; no click. DEPENDS: RUN-QUIET-FEED. BLOCKED: session wave 22 (W22-FOLD: folded into RUN-REPORT-FIELDS, the wave 22 owner of report.py).
- [ ] ZONE-CARD-ITEM-GATE (build) OVL-ZONE-CARD review D-1: app/shared/render_gate.js shows every card only while parts.item is on, so the zone moment card (kind zone) is hidden when the player turns the item part off; gate the zone card on its own part (or on the card slot) instead of parts.item; fold into OVL-LINE2-GUIDE, the wave 22 owner of render_gate.js. ACCEPT: npm test --prefix app passes with a test that a kind zone card renders with parts.item off and an item card does not. ZERO-CLICK: The zone card shows and leaves by itself from the opted-in log tail. DEPENDS: OVL-ZONE-CARD. BLOCKED: session wave 22 (W22-FOLD: folded into OVL-LINE2-GUIDE).

## Lane: data

- [ ] LIVE-1-ACCEPTED (data) Live-verify the trade accepted / cancelled log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the trade accepted / cancelled item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-AFK (data) Live-verify the AFK log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the AFK item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-CRUEL (data) Live-verify the Cruel area id log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the Cruel area id item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-DEATH (data) Live-verify the death log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the death item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-GUILD (data) Live-verify the guild log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the guild item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-HIDEOUT (data) Live-verify the hideout log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the hideout item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-JOINED (data) Live-verify the area joined log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the area joined item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-MAP (data) Live-verify the endgame Map area id log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the endgame Map area id item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-PARTY (data) Live-verify the party join / leave log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the party join / leave item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-TRADE (data) Live-verify the trade request log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the trade request item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-1-WHISPER (data) Live-verify the whisper log shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live for the whisper item. ZERO-CLICK: The operator only plays; the ledger counts the first live hit by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] LIVE-WAYSTONE (data) Live-verify the waystone item text shape from the parse ledger's masked waystone block. ACCEPT: python tools/live1_report.py prints VERIFIED live for the waystone item. ZERO-CLICK: The operator only presses the item key on a waystone in normal play; the ledger keeps the masked shape by itself. DEPENDS: RUN-LEDGER-WIRE. BLOCKED: first live hit in the parse ledger (normal play after the ledger consent tick).
- [ ] DOCS-FRESH-20261121 (data) 1 dated markers in docs are older than 30 days: resolve or re-date each with a source. ACCEPT: docs_fresh.py stale prints 0. ZERO-CLICK: the loop works it. SOURCE: watch refresh docs, filed 2026-11-21.


## Lane: review

- [ ] WT-SIDECAR-WIRE (review) Reopened WT-SIDECAR: agent worktrees must land under the AL sidecar through the decision 0012 hooks, not only by the hand-run hook. ACCEPT: python -m pytest -q tests/test_wt_sidecar_hook.py -rs reports no skip and git worktree list after one isolated agent spawn shows its path under the sidecar Worktree folder. ZERO-CLICK: One paste by the operator, once; every later wave spawn lands in the sidecar by itself. BLOCKED: operator act (paste the two hook entries of decision 0012 into .claude/settings.json); AUTO-26 flips it when its proof passes.
- [ ] HUD-PLATE-WIDTH-DOC (review) OVL-CONTRAST-PIXELS measured the HUD plate at 258 px inside and 280 px outside, while docs/plan/03-target-design.md section 5.1 says at most 258 px wide, 236 px inside; correct section 5.1 (and design 0001) to the measured plate or narrow the plate CSS to the planned width. ACCEPT: python -m pytest -q tests/test_ascii_lf.py tests/test_overlay_pixels.py passes and section 5.1 states the widths the pixel test measures. ZERO-CLICK: Document or layout fix; no click. DEPENDS: OVL-CONTRAST-PIXELS. BLOCKED: session wave 22 (W22-FOLD: folded into HOME-REFUSAL-COPY, doc option: section 5.1 follows the measured plate; docs/plan is session-owned).
- [ ] PLAN03-LINE2-WORDING (review) OVL-LINE2-RULE review L2-2 (nit): docs/plan/03-target-design.md section 5.1 wording of the 26-character HUD line 2 rule omits the deaths text that hudLine2 counts; reword it to match app/shared/format.js. ACCEPT: python -m pytest -q tests/test_ascii_lf.py passes and section 5.1 names the deaths text in the count. ZERO-CLICK: Document edit; no click. DEPENDS: OVL-LINE2-RULE. BLOCKED: session wave 22 (W22-FOLD: folded into HOME-REFUSAL-COPY; docs/plan is session-owned).
- [ ] RUN-GRID-DESIGN-WORDS (review) PLAY-TD-20A-RUN-GRID review D-3: design 0001 section 9 renames Act times card to Acts card and Death recap card to Deaths card, with the row forms '<act> (<notes>): <t>, total <t>, best <t>', '<map> (<note>): level <n>, <t>, <n> death(s)', 'Level <n>: <n> maps, <n> deaths, median <t>, <n> level-ups'. ACCEPT: python -m pytest -q tests/test_ascii_lf.py tests/test_design_contrast.py passes. ZERO-CLICK: Document edit; no click. DEPENDS: PLAY-TD-20A-RUN-GRID. BLOCKED: session wave 22 (W22-FOLD: folded into HOME-REFUSAL-COPY).


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


## Audit 2026-11-17 (docs/audit/2026-11-17-audit.md)

Low findings filed by AREA-AUDIT; the medium ones were fixed in the audit
merge. Each row names the finding ids it closes.






- FOLDED 2026-11-18: AUDIT-P8-LOW -> RUN-START-REASON-CORE, RUN-OBS-LOGS-SHELL, RUN-LADDER-TICK, RUN-REPORT-FIELDS, RUN-P8-8-CHARMIX, RUN-BUDGET-TESTS-DASH (docs/plan/07 Coverage; the old row text is in git history).


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

- [ ] DATA-SNAP-SETUP (build) setup.ps1 runs the game-data snapshot when web data is already on.
  ACCEPT: python -m pytest -q tests/test_setup_snapshot.py tests/test_tc_snap.py
  tests/test_audit_snapshot_optin.py passes. ZERO-CLICK: The dev step runs itself: one setup
  command, no second command for game data once 'Use web data' is ticked. DEPENDS:
  REL-RUNTIME-SCRIPTS.

### Wave 20: overlay and client, install and release, tests and code seams


### Wave 21: overlay and client, install and release, reliability and observability


### Wave 22: install and release, reliability and observability, overlay and client

- [ ] PLAY-TD-20B-RUN-CARDS (build) Run grid 2: Recent, Last session and Characters cards. ACCEPT:
  npm test --prefix app and python -m pytest -q tests/test_play_fit.py tests/test_a11y.py
  tests/test_dash_console.py pass with the tab-run marker deleted: Recent filters by the chips All,
  Deaths and Trades, Last session shows the summary with run history pages, Characters holds the
  picker, and G1 holds for the whole tab in states f and g. ZERO-CLICK: Everything fills from the
  log; chips, pages and the picker are optional review acts. DEPENDS: PLAY-TD-20A-RUN-GRID. BLOCKED:
  session wave 22.
- [ ] RUN-REPORT-FIELDS (build) The report from an allow-list of structured fields, with a hardened
  redactor (P8-7) + Keep per-press 'Not counted' lines for the session. ACCEPT: python -m pytest -q
  tests/test_report.py tests/test_diag_self.py tests/test_audit_pass8.py passes and npm test
  --prefix app passes. Also (folded RUN-UNKNOWN-ITEM-TEXT): python -m pytest -q
  tests/test_unknown_item_text.py tests/test_tc_eval.py tests/test_report.py passes. ZERO-CLICK: One
  click to copy (decision 0014 requires it); the preview costs no extra click. Also (folded
  RUN-UNKNOWN-ITEM-TEXT): Collected silently; the report copy stays a click (decision 0040).
  DEPENDS: RUN-QUIET-FEED, RUN-METRICS-CORE, RUN-LEDGER-WIRE, RUN-BUDGET-LOG-CORE, GP-06,
  OVL-OBS-CRASH, TC-PRESS-STAGED-LIVE. BLOCKED: session wave 22.
- [ ] OVL-LINE2-GUIDE (build) Overlay HUD line 2: the opt-in guide line and the fixed card anchor.
  ACCEPT: node --test app/test/hudline2.test.js app/test/overlay_gate.test.js
  app/test/layout.test.js app/test/overlay_parts.test.js app/test/shared.test.js and python -m
  pytest -q tests/test_overlay_smoke.py tests/test_ux_review.py pass. ZERO-CLICK: The line follows
  the snapshot by itself; the guide line is an opt-in setting (Always), the default keeps level and
  deaths. DEPENDS: OVL-LINE2-RULE, OVL-ZONE-CARD, OVL-TD05-LEGIBILITY. BLOCKED: session wave 22.
- [ ] OVL-ACT-CARD (build) Act moment card: 12 s when an act split closes, with the gap to the saved
  best. ACCEPT: python -m pytest -q tests/test_moment_cards.py tests/test_hud_act.py
  tests/test_util_run_history.py tests/test_glance_rules.py passes. ZERO-CLICK: Shows and leaves by
  itself when the log closes an act; nothing to press. DEPENDS: OVL-ZONE-CARD. BLOCKED: session wave
  22.
- [ ] RUN-BUDGET-TESTS-DET (build) Deterministic budget tests: tick cost, idle tick, snapshot size,
  real loop body. ACCEPT: python -m pytest -q tests/test_budgets.py tests/test_budget_tick.py
  tests/test_budget_snapshot.py passes. ZERO-CLICK: The suite runs them. DEPENDS: RUN-LADDER-TICK,
  RUN-QUIET-FEED. BLOCKED: session wave 22.
- [ ] OVL-TD06-AUTOSCALE (build) Overlay physical size: autoScale reference 1200 DIP, budgets re-run
  (TD-06). ACCEPT: node --test app/test/layout.test.js and python -m pytest -q
  tests/test_overlay_smoke.py tests/test_ux_review.py tests/test_budgets.py pass. ZERO-CLICK:
  Follows the monitor by itself; no click. DEPENDS: OVL-TD05-PLATE, OVL-LINE2-RULE. BLOCKED: session
  wave 22.
- [ ] DEP-15 (build) Tag-triggered release workflow (file half). ACCEPT: python -m pytest -q
  tests/test_workflows.py passes. ZERO-CLICK: Pushing the tag is the only act; CI does the rest.
  DEPENDS: REL-BUILD-ASSETS, REL-PUBLISH-GATES, DEP-04, GP-05. BLOCKED: session wave 22.
- [ ] REL-UPDATE-WIRE (build) Update check in the core: acknowledgement, tick and snapshot block.
  ACCEPT: python -m pytest -q tests/test_updates.py tests/test_ux_settings_io.py
  tests/test_http_security.py tests/test_bus_state.py passes. ZERO-CLICK: The check runs by itself
  on the core tick once a day inside the web-data opt-in; with web data off it makes zero requests;
  no toast, no window. DEPENDS: DEP-16, DEP-05. BLOCKED: session wave 22.
- [ ] REL-PUBLISH-READBACK (build) Publish read-back: release, tag, digests, attestation. ACCEPT:
  python -m pytest -q tests/test_release_readback.py tests/test_release_gates.py passes. ZERO-CLICK:
  Automatic after the one phrase; one hand-off line records what was read back. DEPENDS:
  REL-PUBLISH-GATES. BLOCKED: session wave 22.
- [ ] REL-STAGE-SANDBOX (build) Release stage: optional Windows Sandbox phases. ACCEPT: python -m
  pytest -q tests/test_release_stage.py passes and python tools/release.py stage --help lists
  --sandbox as off by default. ZERO-CLICK: Off by default; the scratch-home round trip is the gate
  without it. DEPENDS: REL-STAGE-ROUNDTRIP. BLOCKED: session wave 22.
- [ ] DEP-19 (build) CPython pin watch. ACCEPT: python -m pytest -q tests/test_upstream_watch.py
  passes. ZERO-CLICK: Runs on the loop tick by itself; a pin move is a gated commit and ships as a
  0.y.z release through a REL-PREP row. Never from the app. DEPENDS: REL-RUNTIME-PINS, AUTO-05,
  LOOP-WATCH-ROWS, AUTO-09. BLOCKED: session wave 22.
- [ ] RUN-SECOND-LINE-CLIENT (build) The client restarts a core that stays down. ACCEPT: npm test
  --prefix app passes and python -m pytest -q tests/test_desktop_client.py passes. ZERO-CLICK:
  Automatic. DEPENDS: RUN-OBS-LOGS-SHELL, RUN-SECOND-LINE-PY. BLOCKED: session wave 22.
- [ ] PUB-HOOK-RELEASE-CHECK (build) Guarded hook: refuse a v* tag without a PASS stage report.
  ACCEPT: `python -m pytest -q tests/test_pre_push_hook.py tests/test_fleet_kit_conformance.py
  tests/test_ascii_lf.py` is green and `git grep -n "release.py\" prepush-check" --
  .githooks/pre-push` prints one line. ZERO-CLICK: Runs by itself on every push; a release needs no
  extra step beyond plan 05's one operator phrase. DEPENDS: GP-02, REL-PUBLISH-GATES. BLOCKED:
  session wave 22.

### Wave 23: install and release, overlay and client, tests and code seams

- [ ] PLAY-TD-21A-SETTINGS-RAIL (build) Settings rail 1: Checks, Reading and web data, Overlay.
  ACCEPT: npm test --prefix app and python -m pytest -q tests/test_play_fit.py tests/test_a11y.py
  tests/test_ux_review.py tests/test_ux_b8.py tests/test_dash_console.py pass: the rail lists 6
  sections with one visible, sections 1 to 3 hold at most 448 px of rows each, the reading status
  word is visible on all 4 tabs and pressing it shows Settings, Reading and web data with focus on
  Stop reading Client.txt, and Checks shows by itself while a check fails. ZERO-CLICK: Checks opens
  by itself on a failure; every switch is optional and lives in one place. DEPENDS:
  PLAY-TD-20B-RUN-CARDS. BLOCKED: session wave 23.
- [ ] OVL-APP-SCHEME (build) Move the overlay page and the starting page off file:// onto one app
  scheme. ACCEPT: node --test app/test/pages.test.js app/test/egress.test.js app/test/guards.test.js
  app/test/overlay_gate.test.js app/test/hotreload.test.js and python -m pytest -q
  tests/test_http_security.py tests/test_overlay_smoke.py tests/test_sse_idle_push.py pass.
  ZERO-CLICK: Nothing for the player; the overlay stays a separate click-through window. DEPENDS:
  OVL-SHELL-GUARDS, OVL-EGRESS-LOCK, OVL-WAKE-COMPANION, OVL-LINE2-GUIDE, OVL-KEYS-CORE,
  SEC-STATIC-MAP. BLOCKED: session wave 23.
- [ ] OVL-KEY-HINT (build) Teach the item-check key in the empty card slot, then retire it. ACCEPT:
  python -m pytest -q tests/test_overlay_view.py tests/test_moment_cards.py
  tests/test_glance_rules.py and node --test app/test/keyhint.test.js app/test/hudline2.test.js
  app/test/overlay_parts.test.js pass. ZERO-CLICK: Appears and retires by itself; the press it
  teaches is the manual press the floor requires. The hint causes no clipboard read. DEPENDS:
  OVL-KEYS-CORE, OVL-ACT-CARD, OVL-LINE2-GUIDE. BLOCKED: session wave 23.
- [ ] DEP-17 (build) Update, network half: download, verify and stage from a release. ACCEPT: python
  -m pytest -q tests/test_updater.py tests/test_update_switch.py passes. ZERO-CLICK: None with web
  data on and the wording acknowledged; with web data off 0 calls. DEPENDS: DEP-11, DEP-16, DEP-15,
  REL-UPDATE-SWITCH. BLOCKED: session wave 23.
- [ ] RUN-BUDGET-TESTS-DASH (build) Dashboard and overlay paint budgets under test (B13, B14) +
  P8-6: the console / CSP test paints Checks rows, a hint and ladder_all. ACCEPT: python -m pytest
  -q tests/test_dash_perf.py tests/test_dash_console.py passes and npm test --prefix app passes.
  Also (folded RUN-P8-6-CONSOLE): python -m pytest -q tests/test_dash_console.py passes. ZERO-CLICK:
  The suite runs them. Also (folded RUN-P8-6-CONSOLE): No player interaction. DEPENDS:
  RUN-VERDICTS-UI, PLAY-TD-01B-FIT-HARNESS, RUN-QUIET-FEED. BLOCKED: session wave 23.
- [ ] REL-UPDATE-CHECKS (build) Checks row and report lines for the install. ACCEPT: python -m
  pytest -q tests/test_update_checks.py tests/test_diag_self.py tests/test_ux_review.py
  tests/test_install_home.py passes. ZERO-CLICK: The line appears by itself in Checks; no toast, no
  window. DEPENDS: REL-UPDATE-SWITCH, PLAY-F-131-STATUS-TABLE. BLOCKED: session wave 23.
- [ ] SEC-HELLO-PS (build) run.ps1 verifies the core before it sends the token or opens the page.
  ACCEPT: python -m pytest -q tests/test_run_health_ps.py passes: the Test-AlHealth function text
  run in powershell.exe 5.1 against a fake listener that answers 200 to everything returns false and
  that listener sees no X-AL-Token header, and against a test core it returns true. ZERO-CLICK: Code
  change; run.ps1 checks by itself on every start. DEPENDS: SEC-HELLO-CORE, SEC-NO-PROXY. BLOCKED:
  session wave 23.
- [ ] TEST-SHOTS-RENDER (data) First screenshot render and the README image block. ACCEPT: python
  tools/shots.py check exits 0, and python -m pytest -q tests/test_shots.py
  tests/test_brand_assets.py tests/test_ascii_lf.py tests/test_leak_sweep.py passes. ZERO-CLICK: The
  agent runs 'python tools/shots.py render' itself (headless, no window); later refreshes are filed
  and worked by the watcher with no reminder. DEPENDS: AUTO-15, PUB-README-PLAYERS. BLOCKED: session
  wave 23.
- [ ] AUTO-16 (build) REL-NOTES: notes --count and the REL-PREP row text. ACCEPT: python -m pytest
  -q tests/test_release_notes.py tests/test_commit_subject.py passes and python tools/release.py
  notes --count prints one line '<n> <date>'. ZERO-CLICK: Read by the loop's refresh source; no
  operator step. DEPENDS: DEP-04, AUTO-01. BLOCKED: session wave 23.
- [ ] AUTO-13 (build) DIVE-ON-DEMAND: a source may request one dive a day; the idle dive is weekly.
  ACCEPT: `python -m pytest -q tests/test_loop_dive_request.py tests/test_loop_dive.py` passes.
  ZERO-CLICK: Unattended: an upstream version change asks for its own research; nobody has to
  remember to look. DEPENDS: AUTO-01, AUTO-04, AUTO-05, LOOP-ROWFILES-WORK, LOOP-TESTS-CARVE.
  BLOCKED: session wave 23.
- [ ] TEST-COPY-SHEETS (build) Split design 0001 section 9 rule 2 into docs/design/copy/<family>.md.
  ACCEPT: python -m pytest -q tests/test_structure.py tests/test_a11y.py
  tests/test_design_contrast.py tests/test_ascii_lf.py tests/test_leak_sweep.py passes and grep -c
  'docs/design/copy/' .claude/agents/design-reviewer.md prints at least 1. ZERO-CLICK:
  Developer-side only; the player does nothing. The reviewer agent reads the sheets by itself from
  its own method step. DEPENDS: TEST-STRUCTURE-GUARD. BLOCKED: session wave 23.
- [ ] AUTO-22 (build) OVL-SMOKE-DAILY: the tick runs the live overlay smoke once a day while the
  game is idle. ACCEPT: `python -m pytest -q tests/test_loop_overlay_smoke_step.py` passes.
  ZERO-CLICK: Unattended: the smoke runs by itself on an idle day; it never runs while the operator
  plays. DEPENDS: AUTO-01, SEC-NO-PROXY. BLOCKED: session wave 23.

### Wave 24: reliability and observability, web data, theorycraft

- [ ] DATA-CONTACT-UI (build) Contact field in the web-data card and honest blocked wording + League
  dropdown in the web-data card. ACCEPT: npm test --prefix app passes, including a new
  app/test/prices.test.js case that asserts no 'arrive within a minute' text in webDataView,
  savedText, ratesPill or moversView while doc.blocked is 'contact not set'. Also (folded
  DATA-LEAGUE-PICKER-UI): npm test --prefix app passes. ZERO-CLICK: One typed value and one Save
  click, once per install and outside play, until DATA-CONTACT-DEFAULT makes the field optional; the
  field shows only until a contact is set and nothing is clicked in play. Also (folded
  DATA-LEAGUE-PICKER-UI): Optional override only; with no pick the league follows poe.ninja's
  current one. DEPENDS: DATA-CONTACT-FIELD, DATA-DIAG-SEAM. BLOCKED: session wave 24.
- [ ] RUN-EXPLAIN-ROWS (build) Five cause rows in Checks. ACCEPT: python -m pytest -q
  tests/test_diag_explain.py tests/test_diag_self.py passes and npm test --prefix app passes.
  ZERO-CLICK: Computed every 5 s; Checks opens by itself on a new failure. DEPENDS:
  RUN-OBS-LOGS-SHELL, RUN-METRICS-SITES, RUN-SUPERVISOR-CLOCK, RUN-LEDGER-WIRE, RUN-REPORT-FIELDS,
  OVL-OBS-CRASH. BLOCKED: session wave 24.
- [ ] OVL-APP-SCHEME-STRICT (build) Core refuses Origin null and file:// once both local pages load
  from the app scheme. ACCEPT: python -m pytest -q tests/test_http_security.py
  tests/test_audit_http_harden.py tests/test_sse_idle_push.py passes and git grep -n -F '"file://"'
  -- server/al/http.py prints nothing. ZERO-CLICK: Nothing for the player; the overlay already loads
  from the app scheme. DEPENDS: OVL-APP-SCHEME. BLOCKED: session wave 24.
- [ ] TC-WEIGHTS-DELTA-EXPORT (build) Settings export schema 2 carries the weight changes. ACCEPT:
  python -m pytest -q tests/test_ux_settings_io.py tests/test_tc_weights_delta.py passes and npm
  test --prefix app passes. ZERO-CLICK: No click beyond the existing export and import buttons.
  DEPENDS: TC-WEIGHTS-DELTA-STORE, TC-WORN-WIRE, TC-CALC-OPTIN. BLOCKED: session wave 24.
- [ ] RUN-BUDGET-TESTS-LIVE (build) Opt-in live budgets: client process counts, calc ceilings,
  budget-log bounds. ACCEPT: python -m pytest -q tests/test_overlay_smoke.py
  tests/test_budget_log.py tests/test_math_perf.py passes (live parts skip unless opted in).
  ZERO-CLICK: The suite runs them; the live smoke stays opt-in. DEPENDS: RUN-BUDGET-LOG-CORE,
  RUN-BUDGET-TESTS-DET, TC-PRESS-STAGED-LIVE. BLOCKED: session wave 24.
- [ ] TEST-SLOW-BUDGET (build) Slow-test budget and hang guard. ACCEPT: python -m pytest -q
  tests/test_slow_budget.py tests/test_pytest_config.py passes and grep -c faulthandler_timeout
  pytest.ini prints 1. ZERO-CLICK: Enforced in every run by the hook; nobody has to look at
  durations. DEPENDS: TEST-FLOOR-MEMO, TEST-TIMER-FIXES, TEST-PLUGIN-PIN, TEST-MARKS,
  TEST-SUITE-RUNNER, TEST-DOCS-FACTS-UI, PUB-README-PLAYERS, DEP-02. BLOCKED: session wave 24.
- [ ] DATA-PRICE-TYPES-FILE (build) Price type lists in a hot-reloaded data file. ACCEPT: python -m
  pytest -q tests/test_price_types_file.py tests/test_price_book.py tests/test_price_cadence.py
  tests/test_hot_reload.py passes. ZERO-CLICK: Automatic; the file reloads by itself (decision
  0042). DEPENDS: DATA-NINJA-SHAPE-WATCH. BLOCKED: session wave 24.
- [ ] TC-PIN-POLICY (build) Pin policy written into decision 0018; toolchain cleaned up. ACCEPT:
  python -m pytest -q tests/test_tc_pin.py passes. ZERO-CLICK: Setup cleans up by itself. DEPENDS:
  TC-CALC-VERIFY-PIN, AUTO-12. BLOCKED: session wave 24.
- [ ] RUN-HISTORY-UNDO (build) Undo for Clear run history. ACCEPT: npm test --prefix app passes and
  python -m pytest -q tests/test_util_run_history.py tests/test_a11y.py passes. ZERO-CLICK: Nothing
  in play. DEPENDS: RUN-DURABLE-STORES. BLOCKED: session wave 24.
- [ ] RUN-OVERLAY-REMEMBER (build) Remember the overlay shown / hidden choice across restarts.
  ACCEPT: npm test --prefix app passes and python -m pytest -q tests/test_overlay_layout.py
  tests/test_floor_static.py passes. ZERO-CLICK: One toggle fewer per session. DEPENDS:
  RUN-OBS-LOGS-SHELL. BLOCKED: session wave 24.
- [ ] DATA-SNAP-TRIM (build) Drop the two unread files from the snapshot fetch list. ACCEPT: python
  -m pytest -q tests/test_tc_snap.py tests/test_tc_snap_ui.py tests/test_snap_probe.py
  tests/test_audit_snapshot_optin.py passes and snapshot.SOURCES has exactly base_items,
  stat_translations, skilltree and world_areas. ZERO-CLICK: Unchanged for the player; fewer requests
  to a community host. DEPENDS: DATA-SNAP-PROBE. BLOCKED: session wave 24.
- [ ] REL-CUTOVER-LIVE (build) Cut-over: the operator's live copy becomes an installed release.
  ACCEPT: GET /api/health on 127.0.0.1:8960 answers mode 'installed' with version 0.2.0-rc.0 from
  <sidecar>\Install, the checkout answers on 127.0.0.1:8961 with mode 'checkout', and a re-run of
  the checkout's setup.ps1 -NoShortcut leaves the installed copy's shortcuts and logon task alone
  (read back with the scripts/al_shell.ps1 readers). ZERO-CLICK: Waits for game_idle by itself; no
  operator step. DEPENDS: DEP-13, DEP-09, REL-UNINSTALL-SHELL, REL-UPDATE-LAUNCH, REL-UPDATE-CHECKS,
  REL-RUNTIME-SCRIPTS, REL-BUILD-ASSETS. BLOCKED: session wave 24.

### Wave 25: local security, overlay and client, theorycraft

- [ ] SEC-LOG-PATH-FIELD (build) Find Client.txt outside Steam: a typed path on the consent card.
  ACCEPT: npm test --prefix app and python -m pytest -q tests/test_log_path_field.py
  tests/test_a11y.py tests/test_http_security.py pass: a posted Client.txt path starts the tailer, a
  bad one returns the existing 400 text, and spies show the request adds no winreg,
  libraryfolders.vdf or directory-listing call. ZERO-CLICK: Today's discovery first; the field
  appears by itself only when nothing is found. Then the player types the path and presses Enter or
  the Use button: that one act is also the Client.txt opt-in, which the floor requires to be the
  player's own, and it replaces hand-editing config/local.json. Only Client.txt, only at the path
  the player typed. DEPENDS: SEC-NO-DISCOVERY, PLAY-TD-12-CONTEXT-SETUP. BLOCKED: session wave 25.
- [ ] OVL-OVERLAY-FEED (build) OVERLAY-FEED: /events?view=overlay sends only the fields the HUD
  reads, only when one changes. ACCEPT: python -m pytest -q tests/test_overlay_feed.py
  tests/test_overlay_view.py tests/test_sse_idle_push.py tests/test_http_security.py
  tests/test_budgets.py and node --test app/test/shared.test.js app/test/overlay_gate.test.js
  app/test/hudline2.test.js pass. ZERO-CLICK: Automatic; same token, same loopback feed. DEPENDS:
  OVL-KEY-HINT, OVL-APP-SCHEME-STRICT, RUN-QUIET-FEED, RUN-BUDGET-TESTS-DET. BLOCKED: session wave
  25.
- [ ] TC-CALC-IDLE (build) luajit leaves when it is not needed. ACCEPT: python -m pytest -q
  tests/test_tc_wire.py tests/test_audit_exe_path.py tests/test_tc_press_staged.py passes.
  ZERO-CLICK: Automatic; no click. DEPENDS: TC-PRESS-STAGED-LIVE, TC-CALC-CONFINE-PROC,
  TC-CALC-VERIFY-USE, TC-WEIGHTS-DELTA-EXPORT, TC-UPGRADE-PER-SLOT. BLOCKED: session wave 25.
- [ ] SEC-CEIL-SNAPSHOT (build) Snapshot fetch: deadline, per-source cap on disk, one URL check.
  ACCEPT: python -m pytest -q tests/test_tc_snap.py tests/test_audit_snapshot_optin.py
  tests/test_tc_snap_ui.py passes: a URL with user info or a port is refused, a body over its source
  cap is refused with no partial file left, and a dripping reply ends at the deadline. ZERO-CLICK:
  Code change; the snapshot still runs only with the web_data opt-in or -Snapshot. DEPENDS:
  SEC-CEIL-WEBFETCH, DATA-SNAP-TRIM.

### Wave 26: Play tab and dashboard, install and release

- [ ] PLAY-TD-21B-SETTINGS-ABOUT (build) Settings rail 2: Keys, Appearance and tools, About and
  data; footer. ACCEPT: npm test --prefix app and python -m pytest -q tests/test_play_fit.py
  tests/test_a11y.py tests/test_ux_b6.py tests/test_ux_b8.py tests/test_ux_review.py
  tests/test_audit_pass7.py tests/test_dash_console.py pass with the tab-settings marker deleted:
  every index entry jumps to and focuses its control, the disclaimer sentence is still in the
  footer, the full credits and the does / never does text are in About and data, and the page has at
  most 6 live regions. ZERO-CLICK: Set-once switches only; nothing here is needed in play. DEPENDS:
  PLAY-TD-21A-SETTINGS-RAIL, PLAY-TD-09C-BAR. BLOCKED: session wave 26.
- [ ] REL-UPDATE-TRIGGER (build) Core: start the updater by itself, 'Update now' and click-only.
  ACCEPT: python -m pytest -q tests/test_updates.py tests/test_http_security.py
  tests/test_ux_settings_io.py passes. ZERO-CLICK: No click with web data on; click-only waits for
  one 'Update now'. DEPENDS: DEP-17, REL-UPDATE-WIRE, DEP-05, DEP-16, SEC-SURFACE-PIN. BLOCKED:
  session wave 26.

### Wave 27: tests and code seams, reliability and observability, Play tab and dashboard

- [ ] RUN-NO-DEAD-ENDS (build) Copy pass: eleven sentences and four errors never send the player to
  a script. ACCEPT: python -m pytest -q tests/test_copy_dead_ends.py tests/test_diag_self.py
  tests/test_ux_review.py tests/test_design_gate.py passes and npm test --prefix app passes.
  ZERO-CLICK: Fewer wrong acts; nothing added. DEPENDS: RUN-REPORT-FIELDS, RUN-OBS-LOGS-SHELL,
  RUN-ZONE-RESET, RUN-DIAG-DATA-AGE, RUN-EXPLAIN-ROWS, DATA-CONTACT-UI, OVL-KEYS-WEB,
  SEC-LOG-PATH-FIELD, TC-CALC-OPTIN-BUTTON. BLOCKED: session wave 27.
- [ ] PLAY-TD-22A-A11Y-CSS (build) Accessibility CSS: inset focus ring, 24 px targets, forced
  colours, text spacing. ACCEPT: python -m pytest -q tests/test_a11y.py tests/test_design_tokens.py
  tests/test_ux_review.py tests/test_play_fit.py and node --test app/test/textspacing.test.js pass:
  every focusable kind has a 3 px accent ring with outline-offset -3px (an outside ring only on
  button.primary), checkboxes are 24 px, the selected tab has its own border under forced-colors, a
  disabled button has a visible disabled style, every font-size in web/*.css is a var(--al-fs-*)
  token, and the probe sets data-text-spacing=user when its reference box differs from the tokens.
  ZERO-CLICK: Follows the OS and browser settings; no click. DEPENDS: PLAY-TD-21B-SETTINGS-ABOUT,
  PLAY-TD-03-TOKENS. BLOCKED: session wave 27.
- [ ] TEST-WEB-PANELS-B (build) Panel move B: layout, weights, web data and graphics panels. ACCEPT:
  npm test --prefix app passes and python -m pytest -q tests/test_dash_console.py tests/test_a11y.py
  tests/test_floor_static.py tests/test_ux_review.py tests/test_webpage.py passes. ZERO-CLICK:
  Developer-side only; the player does nothing. The page assembles the panel tags by itself; paint
  order is kept by explicit order values. DEPENDS: TEST-WEB-PANELS-A, PLAY-TD-21B-SETTINGS-ABOUT.
  BLOCKED: session wave 27.
- [ ] TEST-CORE-TICKS (build) Core tick list and one import per line. ACCEPT: python
  tools/state_equiv.py --ref <package base> prints 'state_equiv: identical' and python -m pytest -q
  tests/test_core_ticks.py tests/test_core_crash_log.py tests/test_fullstack.py
  tests/test_hot_reload.py tests/test_no_discovery.py passes. ZERO-CLICK: Developer-side only; the
  player does nothing. The core runs the same ticks in the same order with no click, as today.
  DEPENDS: TEST-STATE-EQUIV, SEC-DEMO-ENTRY. BLOCKED: session wave 27.

### Wave 28: Play tab and dashboard, reliability and observability

- [ ] PLAY-TD-04B-THEME-CHOICE (build) Theme choice: Dark, Follow Windows, Light. ACCEPT: python -m
  pytest -q tests/test_theme_setting.py tests/test_ux_settings_io.py tests/test_play_fit.py
  tests/test_http_security.py and node --test app/test/webtheme.test.js pass: with
  prefers-color-scheme light emulated and no setting the page background computes to rgb(15, 18,
  22), with Theme Light it computes to rgb(255, 255, 255), the setting survives export and import,
  and a capture through the shared capture helper has a mean relative luminance under 0.05.
  ZERO-CLICK: Dark with no action; the choice is one optional click in Settings. DEPENDS:
  PLAY-TD-21B-SETTINGS-ABOUT, PLAY-TD-04A-DARK-CLIENT, SEC-SURFACE-PIN, TEST-CAPTURE-HELPER.
  BLOCKED: session wave 28.
- [ ] PLAY-TD-22C-A11Y-CDP (build) In-browser accessibility pass in the CDP harness. ACCEPT: python
  -m pytest -q tests/test_a11y_render.py passes in about 10 s and fails on a planted clipped ring, a
  planted unnamed button and a planted 3:1 text pair: it checks the AX tree (no unnamed focusable,
  no skipped heading level, the landmark set), a real Tab walk on the 4 tabs with the ring box per
  stop, the forced-colours tab cue, targets of at least 24 px, at most 4 live regions on Play and 6
  in the page, 320 px reflow with no horizontal scroll, and the four text-spacing overrides on both
  axes at 1024x700 and 1280x760. ZERO-CLICK: Dev step; runs in the gates in windowless Chrome on a
  demo core; skips cleanly without Chrome. DEPENDS: PLAY-TD-22A-A11Y-CSS, PLAY-TD-22B-TAB-FOCUS,
  PLAY-TD-01A-PLAY-STATES, SEC-DEMO-ENTRY. BLOCKED: session wave 28.
- [ ] RUN-PERF-PARSE-ONCE (build) Parse each data file once. ACCEPT: python -m pytest -q
  tests/test_budget_start.py tests/test_hot_reload.py tests/test_hud_act.py tests/test_zone_guide.py
  tests/test_util_campaign.py passes. ZERO-CLICK: Automatic. DEPENDS: RUN-HOTRELOAD-RETRY,
  RUN-DIAG-DATA-AGE, RUN-NO-DEAD-ENDS, RUN-DURABLE-STORES. BLOCKED: session wave 28.
- [ ] PLAY-F-165-COLOUR-WORD-TEST (build) Test: colour never works alone. ACCEPT: python -m pytest
  -q tests/test_colour_never_alone.py passes on the tree and fails when .foo { color:
  var(--fk-status-ok) } is planted on a wordless node. ZERO-CLICK: Runs in the test gates by itself;
  no player step. DEPENDS: PLAY-TD-22A-A11Y-CSS.

### Wave 29: Play tab and dashboard, overlay and client

- [ ] OVL-PARTS-WEB (build) Settings group 'Overlay shows': part switches, presets Full / Cards
  only, zone-guide choice, 'Show a sample card for 10 s'. ACCEPT: node --test
  app/test/overlayparts.test.js app/test/tabs.test.js and python -m pytest -q tests/test_a11y.py
  tests/test_ux_review.py tests/test_dash_console.py pass. ZERO-CLICK: Set once, saved on change,
  the overlay follows within a second; nothing to press in play. DEPENDS: OVL-OVERLAY-KEYS,
  OVL-CARD-SLOT, OVL-TD05-PLATE. BLOCKED: session wave 29.
- [ ] PLAY-F-186A-PLAYER-NOTES-STORE (build) Player notes: bounded store, token route and the
  your-note row. ACCEPT: python -m pytest -q tests/test_player_notes.py tests/test_play_cards.py
  tests/test_sidecar_paths.py tests/test_floor_static.py tests/test_http_security.py passes: a note
  saved for an area id shows as your note on the next entry of that zone for that character only, a
  malformed file keeps the last good copy with a Checks note, the file never exceeds 300 zones of
  200 characters, and the POST needs the token and accepts plain text only. ZERO-CLICK: Shown by
  itself on zone entry; writing a note is the player's choice. DEPENDS: PLAY-TD-07B-PLAY-CARDS,
  PLAY-TD-04B-THEME-CHOICE, RUN-ZONE-RESET, RUN-HOTRELOAD-RETRY, DATA-GUIDE-MERGE. BLOCKED: session
  wave 29.
- [ ] PLAY-F-204A-SR-TOOL (build) Screen-reader pass tool and its refusals. ACCEPT: python -m pytest
  -q tests/test_sr_pass.py tests/test_floor_static.py passes: tools/sr_pass.py exits non-zero
  without the operator flag and while the running core reports game_idle false, holds no OS input,
  screen, audio or clipboard call, and on a fixture speech log writes a transcript with one section
  per step (page load, item check, trade request, tab switch, Settings form); the transcript check
  of docs/design/screen-reader-pass.md skips while that file is absent. ZERO-CLICK: Dev step; the
  tool and its refusals run in the test gates on a fixture speech log; no player step. DEPENDS:
  PLAY-TD-22C-A11Y-CDP, SEC-DEMO-ENTRY. BLOCKED: session wave 29.

### Wave 30: overlay and client, tests and code seams, loop and watchers

- [ ] OVL-TD18-CARD-TIME (build) Card time setting: 20 / 60 / 200 s (TD-18, optional). ACCEPT:
  python -m pytest -q tests/test_overlay_layout.py tests/test_overlay_view.py
  tests/test_price_text.py tests/test_eval_text.py tests/test_ux_settings_io.py and node --test
  app/test/layout.test.js app/test/overlayparts.test.js pass. ZERO-CLICK: Set once in Settings; the
  card still shows and leaves by itself. DEPENDS: OVL-LINE2-GUIDE, OVL-PARTS-WEB,
  OVL-TD06-AUTOSCALE, OVL-COPY-FIRST, OVL-KEYS-WEB, OVL-OVERLAY-FEED. BLOCKED: session wave 30.
- [ ] TEST-WEB-PANELS-C (build) Panel move C: remaining Play blocks (events and trades, item check,
  rates and price) + Panel move D: view modules register themselves; app.js is a shell. ACCEPT: npm
  test --prefix app passes and python -m pytest -q tests/test_dash_console.py tests/test_a11y.py
  tests/test_floor_static.py tests/test_ux_review.py tests/test_webpage.py passes. Also (folded
  TEST-WEB-PANELS-SHELL): npm test --prefix app passes, python -m pytest -q
  tests/test_dash_console.py tests/test_a11y.py tests/test_floor_static.py tests/test_ux_review.py
  tests/test_webpage.py passes, wc -l web/app.js prints under 300, and grep -c 'window.AL[A-Z]'
  web/app.js prints 0. ZERO-CLICK: Developer-side only; the player does nothing. The page assembles
  the panel tags by itself; paint order is kept by explicit order values. Also (folded
  TEST-WEB-PANELS-SHELL): Developer-side only; the player does nothing. The page assembles the panel
  tags by itself; paint order is kept by explicit order values. DEPENDS: TEST-WEB-PANELS-B,
  PLAY-LEGACY-OUT-2, PLAY-TD-16A-ITEMCARD. BLOCKED: session wave 30.
- [ ] LOOP-DEV-CHECKS (build) Two Checks notes: a stale loop tick (dev host) and the Electron end of
  life. ACCEPT: `python -m pytest -q tests/test_diag_dev_notes.py tests/test_diag_self.py` passes.
  ZERO-CLICK: Passive: the notes appear in the Checks view by themselves; the app makes no request
  and checks no version online (decision 0013). BLOCKED: session wave 30.

### Wave 31: Play tab and dashboard, reliability and observability

- [ ] PLAY-F-186B-PLAYER-NOTES-UI (build) Player notes: edit box on Run and the export option.
  ACCEPT: node --test app/test/playernote.test.js and python -m pytest -q
  tests/test_ux_settings_io.py tests/test_a11y.py tests/test_dash_console.py pass: Save posts the
  note for the shown zone and character, the box is capped at 200 characters, and a settings export
  holds notes only when the option is ticked. ZERO-CLICK: Optional review act on the Run tab;
  nothing to press in play. DEPENDS: PLAY-F-186A-PLAYER-NOTES-STORE, PLAY-TD-04B-THEME-CHOICE,
  PLAY-TD-20A-RUN-GRID. BLOCKED: session wave 31.
- [ ] RUN-CHARACTER-PIN (build) 'This is my character' pin in the picker; poll_ms and character
  apply without a restart. ACCEPT: python -m pytest -q tests/test_util_multichar.py
  tests/test_a11y.py passes and npm test --prefix app passes. ZERO-CLICK: One click once; nothing in
  play. DEPENDS: RUN-QUIET-FEED, RUN-NO-DEAD-ENDS, RUN-START-REASON-CORE. BLOCKED: session wave 31.
- [ ] PLAY-TD-23-RECORDS (build) Records: design 0001 rewritten, the cockpit decision, decision 0014
  amended. ACCEPT: python -m pytest -q tests/test_ascii_lf.py tests/test_research_numbers.py
  tests/test_leak_sweep.py tests/test_design_contrast.py tests/test_design_gate.py passes and
  docs/design/0001-design-system.md holds no heading that starts with Amendment 2026-11-18.
  ZERO-CLICK: Docs only; the dev step is one commit after the last TD step lands. DEPENDS:
  PLAY-TD-02-SLOTS, PLAY-TD-03-TOKENS, PLAY-TD-01B-FIT-HARNESS, DATA-PRICE-CARD-TEXT,
  PLAY-F-131-STATUS-TABLE, PLAY-TD-07B-PLAY-CARDS, PLAY-TD-08B-GUIDE-SHORT-TEXT,
  PLAY-TD-09B-SKELETON, PLAY-LEGACY-OUT-2, PLAY-TD-19D-ITEMS-GRID, PLAY-TD-20B-RUN-CARDS,
  PLAY-TD-21B-SETTINGS-ABOUT, PLAY-TD-04B-THEME-CHOICE, PLAY-TD-22A-A11Y-CSS, PLAY-TD-22B-TAB-FOCUS,
  PLAY-TD-22C-A11Y-CDP, OVL-TD05-LEGIBILITY, OVL-TD05-PLATE, OVL-TD06-AUTOSCALE, OVL-LINE2-GUIDE,
  OVL-ACT-CARD, OVL-COPY-FIRST, OVL-KEY-HINT, OVL-GLANCE-RULES, OVL-TD18-CARD-TIME. BLOCKED: session
  wave 31.

### Wave 32: reliability and observability, install and release

- [ ] REL-UPDATE-NOTICE-UI (build) Settings: version lines, update line, opt-in wording. ACCEPT: npm
  test --prefix app passes and python -m pytest -q tests/test_ux_review.py tests/test_a11y.py
  tests/test_dash_console.py passes. ZERO-CLICK: The line appears by itself; no toast, no prompt; an
  earlier opt-in needs one acknowledgement click, once. DEPENDS: REL-UPDATE-WIRE,
  PLAY-TD-21A-SETTINGS-RAIL. BLOCKED: session wave 32.
- [ ] RUN-P8-8-CHARMIX (build) P8-8: the session ladder and the Maps card no longer mix characters +
  SessionState.publish(key, view) for views the core only stores. ACCEPT: python -m pytest -q
  tests/test_util_map_ladder.py tests/test_util_multichar.py tests/test_util_maps_resume.py
  tests/test_util_maprun.py passes. Also (folded TEST-STATE-PUBLISH): python tools/state_equiv.py
  --ref <package base> prints 'state_equiv: identical' and python -m pytest -q
  tests/test_state_publish.py tests/test_bus_state.py tests/test_fuzz.py tests/test_e2e_replay.py
  passes. ZERO-CLICK: No player interaction. Also (folded TEST-STATE-PUBLISH): Developer-side only;
  the player does nothing. Published views reach the dashboard and overlay in the snapshot by
  themselves. DEPENDS: RUN-LADDER-TICK, RUN-CHARACTER-PIN, TEST-STATE-TEXT-4, PLAY-TD-07A-PLAY-VIEW.
  BLOCKED: session wave 32.
- [ ] RUN-PERF-IDLE-BACKOFF (build) Supervisor diet and idle backoff. ACCEPT: python -m pytest -q
  tests/test_keepalive.py tests/test_tailer.py tests/test_budget_tick.py tests/test_live_exit.py
  passes. ZERO-CLICK: Automatic. DEPENDS: RUN-STOP-RACE, RUN-CHARACTER-PIN, RUN-START-REASON-CORE,
  RUN-TAIL-HEAL-READER, RUN-BUDGET-TESTS-DET. BLOCKED: session wave 32.

### Wave 33: Play tab and dashboard, tests and code seams, reliability and observability

- [ ] PLAY-F-189A-SPACING-BADGE (build) One spacing scale, one badge, one list row, held by a lint.
  ACCEPT: python -m pytest -q tests/test_spacing_scale.py tests/test_play_fit.py tests/test_a11y.py
  tests/test_design_tokens.py and npm test --prefix app pass: every margin, padding and gap in
  web/*.css is one of --al-space-0..4, exactly 3 radius values are used, and no rule or script names
  .pill, .verdict, .tab-mark or .tag. ZERO-CLICK: Styling only; nothing to press. DEPENDS:
  PLAY-TD-23-RECORDS, PLAY-TD-22A-A11Y-CSS, PLAY-F-186B-PLAYER-NOTES-UI, TEST-CAPTURE-HELPER.
  BLOCKED: session wave 33.
- [ ] TEST-STATE-MIXIN-A (build) SessionState mixins: cards and trades. ACCEPT: python
  tools/state_equiv.py --ref <package base> prints 'state_equiv: identical' and python -m pytest -q
  tests/test_bus_state.py tests/test_fuzz.py tests/test_e2e_replay.py tests/test_util_multichar.py
  tests/test_live_exit.py tests/test_resume.py tests/test_state_publish.py passes. ZERO-CLICK:
  Developer-side only; the player does nothing. Behaviour is byte-identical; a running core reloads
  itself after the merge. DEPENDS: RUN-P8-8-CHARMIX. BLOCKED: session wave 33.
- [ ] RUN-FEED-TRUTH (build) The page says what really happened to the feed + The dashboard rests
  when unseen or frozen. ACCEPT: npm test --prefix app passes and python -m pytest -q
  tests/test_sse_idle_push.py tests/test_fullstack.py tests/test_budgets.py passes. Also (folded
  RUN-PERF-DASH-IDLE): npm test --prefix app passes and python -m pytest -q tests/test_dash_perf.py
  passes. ZERO-CLICK: Automatic; the client window already reloads itself. Also (folded
  RUN-PERF-DASH-IDLE): Automatic. DEPENDS: RUN-SUPERVISOR-CLOCK, RUN-CHARACTER-PIN,
  RUN-NO-DEAD-ENDS, RUN-BUDGET-TESTS-DASH, SEC-SSE-TAP. BLOCKED: session wave 33.

### Wave 34: install and release, tests and code seams, Play tab and dashboard

- [ ] REL-AUTOSTART-SETTINGS (build) 'Start with Windows' row on Settings + Settings: 'Update now',
  the click-only switch and the staged line. ACCEPT: npm test --prefix app passes and python -m
  pytest -q tests/test_ux_review.py tests/test_a11y.py tests/test_dash_console.py passes. Also
  (folded REL-UPDATE-UI): npm test --prefix app passes and python -m pytest -q
  tests/test_ux_review.py tests/test_a11y.py tests/test_dash_console.py passes. ZERO-CLICK: One tick
  once; the row reflects the recorded state by itself. Also (folded REL-UPDATE-UI): Nothing to press
  by default; the button and switch are for players who want control. DEPENDS: REL-AUTOSTART-SWITCH,
  REL-UPDATE-NOTICE-UI, REL-UPDATE-TRIGGER, PLAY-TD-21A-SETTINGS-RAIL. BLOCKED: session wave 34.
- [ ] TEST-STATE-MIXIN-B (build) SessionState mixins: characters. ACCEPT: python
  tools/state_equiv.py --ref <package base> prints 'state_equiv: identical' and python -m pytest -q
  tests/test_bus_state.py tests/test_fuzz.py tests/test_e2e_replay.py tests/test_util_multichar.py
  tests/test_live_exit.py tests/test_resume.py tests/test_state_publish.py passes. ZERO-CLICK:
  Developer-side only; the player does nothing. Behaviour is byte-identical; a running core reloads
  itself after the merge. DEPENDS: TEST-STATE-MIXIN-A. BLOCKED: session wave 34.
- [ ] PLAY-F-189B-OVERLAY-PLATE (build) Overlay: one plate class. ACCEPT: python -m pytest -q
  tests/test_overlay_plate_class.py tests/test_overlay_layout.py tests/test_budgets.py
  tests/test_ux_review.py passes: overlay.css has one plate rule, and the overlay page rendered
  headless over a synthetic backdrop through the shared capture helper is pixel-identical before and
  after. ZERO-CLICK: No repaint, no animation and no new content on the overlay. DEPENDS:
  PLAY-F-189A-SPACING-BADGE. BLOCKED: session wave 34.

### Wave 35: theorycraft, tests and code seams

- [ ] TC-WEIGHTS-DELTA-UI (build) Weights panel marks changes and resets + .build texts: correct the
  passives note, name the upload route. ACCEPT: npm test --prefix app passes and python -m pytest -q
  tests/test_ux_review.py tests/test_a11y.py passes. Also (folded TC-BUILDFILE-TEXTS): python -m
  pytest -q tests/test_tc_buildfile.py tests/test_audit_buildfile.py tests/test_ux_review.py passes.
  ZERO-CLICK: Reset buttons only for a player who tunes; saving stays on change. Also (folded
  TC-BUILDFILE-TEXTS): Texts only; the download stays the player's click (decision 0034). DEPENDS:
  TC-WEIGHTS-DELTA-STORE, TC-CARD-PARTS-WEB. BLOCKED: session wave 35.
- [ ] TEST-STATE-MIXIN-C (build) SessionState mixins: idle and summary, published views. ACCEPT:
  python tools/state_equiv.py --ref <package base> prints 'state_equiv: identical' and python -m
  pytest -q tests/test_bus_state.py tests/test_fuzz.py tests/test_e2e_replay.py
  tests/test_util_multichar.py tests/test_live_exit.py tests/test_resume.py
  tests/test_state_publish.py passes. ZERO-CLICK: Developer-side only; the player does nothing.
  Behaviour is byte-identical; a running core reloads itself after the merge. DEPENDS:
  TEST-STATE-MIXIN-B. BLOCKED: session wave 35.

### Wave 36: web data

- [ ] DATA-GUIDE-ONE-BLOCK (build) Dashboard: one guide block, no separate Zone tip + A poe.ninja
  category link beside the trade link. ACCEPT: npm test --prefix app passes
  (app/test/zoneguide.test.js unchanged) and no file under web/ contains 'zone-note'. Also (folded
  DATA-PRICE-NINJA-LINK): python -m pytest -q tests/test_price_ninja_link.py
  tests/test_price_check.py tests/test_price_card_age.py passes and npm test --prefix app passes.
  ZERO-CLICK: Layout only; nothing for the player to do. Also (folded DATA-PRICE-NINJA-LINK): An
  optional click; nothing is needed and nothing is fetched by the app. DEPENDS: DATA-GUIDE-MERGE,
  DATA-CONTACT-UI, DATA-PRICE-CARD-TEXT, DATA-LEAGUE-IDENTITY. BLOCKED: session wave 36.

### Wave 37: reliability and observability

- [ ] RUN-LEFTOVERS-CORE (build) Small leftovers: Windowed Fullscreen sentence, the dead 501 stub,
  the no-op switch. ACCEPT: python -m pytest -q tests/test_leftovers.py tests/test_http_security.py
  tests/test_floor_static.py tests/test_run_detach.py tests/test_ascii_lf.py passes. ZERO-CLICK: The
  sentence shows itself. DEPENDS: RUN-FEED-TRUTH, RUN-STOP-RACE. BLOCKED: session wave 37.

### Wave 38: operator requests 2026-11-19, cores

- [ ] ITEM-INFO-CORE (build) Item info lookup: token-gated GET /api/iteminfo over local caches.
  ACCEPT: python -m pytest -q tests/test_iteminfo.py passes. ZERO-CLICK: Answers from what is
  already cached; no setting. BLOCKED: session wave 38.
- [ ] UI-HEADER-TEXT (build) Drop the visible AshLight text left of the tabs; sr-only h1 kept.
  ACCEPT: python -m pytest -q tests/test_brand_assets.py tests/test_a11y.py passes. ZERO-CLICK:
  Automatic. BLOCKED: session wave 38.
- [ ] KINDLER-DATA (data) Kindler template schema and checked loader. ACCEPT: python -m pytest -q
  tests/test_kindler_data.py passes. ZERO-CLICK: Reloads by itself on change. BLOCKED: session wave
  38.
- [ ] KINDLER-STORE (build) Kindler tabs store ops/runtime/gen_builds.json. ACCEPT: python -m pytest
  -q tests/test_kindler_store.py tests/test_settingsio.py passes. ZERO-CLICK: Saved on every change.
  BLOCKED: session wave 38.

### Wave 39: operator requests 2026-11-19, popover and templates

- [ ] ITEM-INFO-POB-TEXT (data) Text-parse PoB CurrencyNames, WorldAreas and Uniques Source lines
  under sha256 pins. ACCEPT: python -m pytest -q tests/test_tc_pobtext.py
  tests/test_tc_pob_drift_guard.py passes. ZERO-CLICK: Read once per pin; no setting. DEPENDS:
  ITEM-INFO-CORE. BLOCKED: session wave 39.
- [ ] ITEM-INFO-UI (build) Item names as link-like buttons with the shared item info popover.
  ACCEPT: python -m pytest -q tests/test_iteminfo_ui.py tests/test_a11y.py tests/test_ux_review.py
  passes. ZERO-CLICK: One click to look; it closes by itself on any other click. DEPENDS:
  ITEM-INFO-CORE. BLOCKED: session wave 39.
- [ ] KINDLER-TEMPLATES (data) First authored Kindler templates, act 1 to maps. ACCEPT: python -m
  pytest -q tests/test_kindler_templates.py passes. ZERO-CLICK: Reloads by itself on change.
  DEPENDS: KINDLER-DATA. BLOCKED: session wave 39.

### Wave 40: operator requests 2026-11-19, engine and tabs

- [ ] KINDLER-ENGINE (build) Kindler candidates, PoB scoring and deterministic ranking on the
  Generate route. ACCEPT: python -m pytest -q tests/test_kindler_engine.py
  tests/test_kindler_live.py passes. ZERO-CLICK: One Generate click; results stay until the toggles
  change. DEPENDS: KINDLER-DATA, KINDLER-TEMPLATES, KINDLER-STORE. BLOCKED: session wave 40.
- [ ] KINDLER-UI-TABS (build) Build tab sub-tabs: Pasted build plus Kindler tabs with move, rename
  and close. ACCEPT: python -m pytest -q tests/test_kindler_tabs_ui.py tests/test_a11y.py
  tests/test_ux_review.py and npm test --prefix app pass. ZERO-CLICK: The tabs come back by
  themselves; one Generate click per new idea. DEPENDS: KINDLER-STORE. BLOCKED: session wave 40.

### Wave 41: operator requests 2026-11-19, Kindler plan and card collapse

- [ ] UI-CARD-COLLAPSE (build) Collapsible cards on Build and items and Run in the desktop client;
  state in the core. ACCEPT: python -m pytest -q tests/test_card_collapse.py tests/test_ui_layout.py
  tests/test_a11y.py passes and npm test --prefix app passes. ZERO-CLICK: Remembered by the app;
  nothing to set. BLOCKED: session wave 41.
- [ ] KINDLER-PLAN (build) Kindler result plan: stages, links, gem timing, passives, ascendancy,
  item focus. ACCEPT: python -m pytest -q tests/test_kindler_plan.py passes. ZERO-CLICK: Follows the
  Play guidance by itself while the tab toggle is on. DEPENDS: KINDLER-ENGINE. BLOCKED: session wave
  41.

### Wave 42: operator requests 2026-11-19, Kindler result card

- [ ] KINDLER-UI-RESULT (build) Kindler result card with stages and follow Play guidance. ACCEPT:
  python -m pytest -q tests/test_kindler_result_ui.py tests/test_a11y.py tests/test_ux_review.py and
  npm test --prefix app pass. ZERO-CLICK: The current step moves with the Play guidance by itself.
  DEPENDS: KINDLER-PLAN, KINDLER-UI-TABS, ITEM-INFO-UI. BLOCKED: session wave 42.

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
- [ ] RUN-LIVE1-FIXTURES (build) Turn each live-verified log shape into a fixture line and a test.
  ACCEPT: python tools/live1_report.py prints no NOT SEEN line for the items this run closes and
  python -m pytest -q tests/test_parser.py tests/test_fuzz.py passes. ZERO-CLICK: The operator only
  plays; the loop files one LIVE-1-<ITEM> row per first live hit. DEPENDS: RUN-LEDGER-WIRE,
  RUN-LEDGER-REPORT. BLOCKED: live sightings of the 11 remaining shapes in normal play; unblocks
  when the ledger consent line is ticked and python tools/live1_report.py prints VERIFIED live for
  at least one LIVE-1 item (operator).
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
- [ ] DATA-CONTACT-DEFAULT (build) Default contact: the project's issues page once the repository is
  public. ACCEPT: python -m pytest -q tests/test_contact_default.py tests/test_contact_field.py
  tests/test_data_ninja.py tests/test_leak_sweep.py passes and npm test --prefix app passes.
  ZERO-CLICK: After this no player types anything for prices: the web-data tick is enough. DEPENDS:
  DATA-CONTACT-UI, DATA-WEBFETCH-GZIP, DATA-DIAG-SEAM, DATA-SNAP-TRIM, DATA-GUIDE-ONE-BLOCK, GP-10.
  BLOCKED: the project's public repository address exists as one tracked constant (Q-24); unblocks
  when GP-10 is merged to main, so the address constant and its leak-sweep allow-list entry are in
  the tree (package GP-10 (PUB cluster), itself behind the repository and first push (GP-09)).
- [ ] OVL-ITEM-KEY-CTRL (build) Item-check default chord moves under Ctrl once the operator names a
  free letter. ACCEPT: node --test app/test/hotkey.test.js app/test/eval.test.js and python -m
  pytest -q tests/test_audit_pass5_low.py tests/test_floor_static.py pass with the new default in
  the case table. ZERO-CLICK: Two presses under one hold (the player's own Ctrl+C, then the AshLight
  key); the floor forbids fewer with the clipboard. Nothing is sent to the game. DEPENDS:
  OVL-KEYS-WEB, OVL-COPY-FIRST. BLOCKED: operator decision Q-09 (two one-minute key checks);
  unblocks when the operator reports whether Alt+Shift+E / Alt+Shift+A flip the keyboard layout with
  two layouts installed and names one unbound Ctrl+letter next to C from the game's key binds
  (operator).
- [ ] AUTO-26 (review) WT-SIDECAR-WIRE: prove agent worktrees land under the sidecar. ACCEPT:
  `python -m pytest -q tests/test_wt_sidecar_hook.py -rs` reports no skip, and `git worktree list`
  after one isolated agent spawn shows its path under the sidecar Worktree folder. ZERO-CLICK: One
  paste by the operator, once; every later wave spawn lands in the sidecar by itself. DEPENDS:
  LOOP-DECISION-TIDY. BLOCKED: the WorktreeCreate and WorktreeRemove hook entries of decision 0012
  are not in .claude/settings.json (an agent may not edit settings); unblocks when
  .claude/settings.json names tools/wt_sidecar_hook.py under both WorktreeCreate and WorktreeRemove
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
  on the dev host (batched ask act g), or an operator-run build.ps1 -Snapshot (GGG).
- [ ] TC-PRESS-FIXTURES (review) Real item-press fixtures for six shapes. ACCEPT: python -m pytest
  -q tests/test_press_fixtures.py tests/test_math_item.py tests/test_leak_sweep.py passes with six
  fixture shapes present. ZERO-CLICK: A one-time check: six presses during normal play, then the
  tests run themselves. DEPENDS: TC-PRESS-SAMPLES. BLOCKED: six item presses in normal play with
  dev_press_samples on (rare gear, a unique, a currency stack, a waystone, a tablet, a gem; plain
  and advanced copy); unblocks when at least six sanitized candidate files, one per shape, exist
  under the sidecar Scratch press-samples folder (operator).
- [ ] AUTO-20 (build) DEPBOT-WATCH: Dependabot alerts and pull requests become rows. ACCEPT: `python
  -m pytest -q tests/test_watch_dependabot.py tests/test_watch_rows.py` passes. ZERO-CLICK: The lane
  runs from the tick and re-applies the bump locally as an operator commit; nothing is merged on
  GitHub (FLEET item 17). DEPENDS: AUTO-19, LOOP-CI-ISSUES, GP-12, GP-08, GP-14. BLOCKED: Dependabot
  alerts and pull requests exist only after the public flip; unblocks when the repository is public
  (GP-12 done) and .github/dependabot.yml and tools/dependabot_reapply.py are on main (package
  GP-12).
- [ ] LOOP-CI-ISSUES (build) CI-WATCH (tick half): read the key issues, fail over when CI is silent.
  ACCEPT: `python -m pytest -q tests/test_watch_ci_issues.py tests/test_watch_rows.py` passes.
  ZERO-CLICK: Unattended: the watch survives a dev host that is off, and the dev loop takes over by
  itself when CI goes quiet. DEPENDS: AUTO-19, LOOP-WATCH-ROWS, LOOP-WATCH-FILE, AUTO-08. BLOCKED:
  session wave 22.
- [ ] PUB-GUIDE-DOWNLOAD-PLACE (build) One download place in README, FAQ and About. ACCEPT: `python
  -m pytest -q tests/test_download_place.py tests/test_player_guide.py tests/test_leak_sweep.py
  tests/test_ascii_lf.py` and `npm test --prefix app` are green. ZERO-CLICK: No click: About shows
  the line by itself; the player opens the place in their own browser if they want it. DEPENDS:
  PUB-GUIDE-PAGES, GP-10. BLOCKED: the project's address is in tracked config/public_repo.json;
  unblocks when `python -c "import json;print(json.load(open('config/public_repo.json'))['repo'])"`
  prints the repository address (package GP-10).
- [ ] DATA-GUIDE-GAP-TUNE (build) Tune the clear-or-push threshold from play data. ACCEPT: python -m
  pytest -q tests/test_zone_guide.py tests/test_util_underlevel.py passes and the commit message
  cites the sample size. ZERO-CLICK: Automatic for the player; the data comes from normal play.
  DEPENDS: DATA-GUIDE-MERGE, DATA-GUIDE-BOSS, RUN-LEDGER-WIRE. BLOCKED: two weeks of
  level-minus-zone-level data per campaign zone exit; unblocks when the parse ledger packages
  (RUN-LEDGER-CORE, RUN-LEDGER-CONSENT (folded into RUN-METRICS-SITES), RUN-LEDGER-WIRE; F-061) are
  merged with the per-exit gap bucket, the operator has ticked the ledger consent, and the dev
  host's ledger spans 14 days of campaign play (operator).
- [ ] TC-TREE-URL (build) Official tree viewer link (version 7 URL). ACCEPT: python -m pytest -q
  tests/test_tc_treeurl.py passes and npm test --prefix app passes. ZERO-CLICK: The link is always
  ready; one click opens the browser. DEPENDS: TC-PRESS-BUILD, TC-UPGRADE-PER-SLOT,
  TC-WEIGHTS-DELTA-UI. BLOCKED: a cached GGG tree export on the dev host for the fixture and the
  byte-value check (needs web data on with the contact set: operator act g); unblocks when the file
  Cache/gamedata/skilltree.json exists under the AL sidecar root (treedata.FILE_NAME) after the
  operator sets the contact and the snapshot runs (operator).
- [ ] DATA-PRICE-TYPE-PROOF (build) Prove each price type after the first real round. ACCEPT: python
  -m pytest -q tests/test_price_type_report.py tests/test_ninja_shape.py tests/test_math_value.py
  passes and python tools/price_type_report.py exits 0 on the dev host's cache (every requested type
  has entries and a matching path or was removed). ZERO-CLICK: Automatic afterwards: the report runs
  in the loop tick. DEPENDS: DATA-PRICE-TYPES-FILE, DATA-NINJA-SHAPE-WATCH. BLOCKED: one real
  poe.ninja round on the dev host; unblocks when the operator sets the contact and turns web data on
  on the dev host (batched ask act g) and the sidecar Cache ninja book.json holds a fetched round
  (operator).
- [ ] TC-AFFIX-LINE (build) Affix line on the item card. ACCEPT: python -m pytest -q
  tests/test_tc_affix_line.py tests/test_eval_text.py passes. ZERO-CLICK: Same press; no click.
  DEPENDS: TC-CARD-PARTS, TC-PRESS-FIXTURES. BLOCKED: a real advanced-copy item sample as a fixture;
  unblocks when tests/fixtures/press holds a reviewed advanced-copy gear fixture (package
  TC-PRESS-FIXTURES).
- [ ] GP-16 (build) Public-surface tidy. ACCEPT: `python -m pytest -q tests/test_loop_inbox_p164.py
  tests/test_al_loop.py tests/test_ascii_lf.py tests/test_leak_sweep.py` is green. ZERO-CLICK: Agent
  step; nothing for the operator beyond the one batched settings edit. DEPENDS: GP-12. BLOCKED:
  ordered after the public flip (plan 04 order, step 7); unblocks when `gh repo view "$R" --json
  visibility --jq .visibility` prints PUBLIC (package GP-12).
- [ ] PLAY-F-204B-SR-RUN (build) One real screen-reader pass: the run and its transcript. ACCEPT:
  python -m pytest -q tests/test_sr_pass.py tests/test_ascii_lf.py tests/test_leak_sweep.py passes
  with docs/design/screen-reader-pass.md present: it is dated, lists the five steps, and has no
  unnamed or doubled announcement. ZERO-CLICK: A dev task run once with the operator's go-ahead; no
  player step. DEPENDS: PLAY-F-204A-SR-TOOL. BLOCKED: The operator confirms the game is closed (not
  only that they are not playing) and game_idle is true; speech output and a visible browser on this
  machine; unblocks when The operator says in their own words that the game is closed and allows one
  run with speech output and a visible browser; the agent then runs python tools/sr_pass.py with the
  operator flag once, game_idle true, and commits the transcript (operator).
- [ ] GP-12 (review) Flip the repository to public. ACCEPT: `gh repo view "$R" --json visibility
  --jq .visibility` prints PUBLIC and an anonymous `git ls-remote --heads --tags
  "https://github.com/$R"` lists refs/heads/main and otherwise only refs/heads/dependabot/*.
  ZERO-CLICK: The flip is an agent step that runs once the gates read green and the operator's own
  words for the flip are in the hand-off (ruling Q-23, step 4; recorded 2026-11-18). OA-2 is skipped
  in writing (the hand-off line 'OA-2 SKIPPED IN WRITING'), so no operator act is left. DEPENDS:
  GP-06, PUB-README-PLAYERS, GP-09, GP-10, GP-11, GP-01, SEC-NO-DISCOVERY, SEC-STATIC-MAP,
  SEC-XML-NUL, DATA-PRICE-CADENCE. BLOCKED: every P0 unit of the plan on origin/main, and flip gates
  0 to 6 green; unblocks when `grep -c "^OPERATOR GO Q-23 step 4" AL-NEXT-SESSION.txt` prints 1 and
  the line quotes the operator's own words with their date, `grep -c "^OA-2 SKIPPED IN WRITING"
  AL-NEXT-SESSION.txt` prints 1, and `python -m pytest -q tests/test_http_security.py
  tests/test_tc_code.py tests/test_no_discovery.py` is green on the commit at origin/main
  (packages).
- [ ] RUN-LIVE-CLICKS-CLOSE (review) Close TEST-LIVE-CLICKS from the passive read-back. ACCEPT:
  python tools/live1_report.py prints all five read-back fields as seen and python -m pytest -q
  tests/test_ascii_lf.py tests/test_research_numbers.py tests/test_leak_sweep.py passes. ZERO-CLICK:
  The operator only logs in as usual with the client running. DEPENDS: RUN-LIVE-CLICKS-STRIKE,
  RUN-LEDGER-WIRE, RUN-LEDGER-REPORT. BLOCKED: one normal login to town or hideout while the core
  runs; unblocks when python tools/live1_report.py prints the five TEST-LIVE-CLICKS fields as seen
  (operator).
- [ ] GP-13 (review) Apply protection and security settings, read back. ACCEPT: `gh api
  "repos/$R/rules/branches/main" --jq '[.[].type] | sort | join(",")'` prints
  deletion,non_fast_forward,required_status_checks and, after one ordinary push of a fresh commit
  through fleet_gitlock, `git rev-parse main` equals `git rev-parse origin/main`, and `git ls-remote
  --heads --tags origin` lists only refs/heads/main, refs/heads/dependabot/* and refs/tags/v* refs.
  ZERO-CLICK: Agent step with gh; later pushes need nothing. DEPENDS: GP-12, PUB-SETTINGS-FILES,
  GP-05. BLOCKED: the public flip (rulesets and free secret scanning need a public repository on a
  personal account); unblocks when `gh repo view "$R" --json visibility --jq .visibility` prints
  PUBLIC (package GP-12).
- [ ] RUN-OVL-BUDGET-CLOSE (review) Close OVL-BUDGET from the budget log. ACCEPT: python -m
  server.al.budgetlog check exits 0 and prints at least 10 rows tagged in map with the overlay
  shown, and python -m pytest -q tests/test_ascii_lf.py tests/test_research_numbers.py
  tests/test_leak_sweep.py passes. ZERO-CLICK: The operator only plays one map with the client
  running. DEPENDS: RUN-BUDGET-LOG-CORE, RUN-BUDGET-LOG-CLIENT, RUN-BUDGET-TESTS-LIVE. BLOCKED:
  normal play with the budget log on (no operator act); closes from the log.
- (TC-OAUTH-REG: its row is replaced in place under '## Theorycraft and item optimization (decision 0004, research 0010)'.)
- (OVL-FPS: its row is replaced in place under '## Lane: build'.)
- [ ] PUB-DEPBOT-FIRST-RUN (data) First live run of the Dependabot re-apply tool. ACCEPT: After
  `python tools/dependabot_reapply.py run`, `gh pr list --repo "$R" --author "app/dependabot"
  --state open --json number,title` lists only pull requests the tool reported as waiting (npm age
  rule or electron signal), and `gh pr list --repo "$R" --state merged --json number` is empty.
  ZERO-CLICK: One command, run by the session that handles go-public while the loop is HALTed; the
  tick runs it by itself after F-078 (PUB-DEPBOT-TICK). DEPENDS: GP-09, PUB-DEPBOT-ACTIONS, GP-08.
  BLOCKED: the repository exists and .github/dependabot.yml is on main; unblocks when `gh api
  "repos/$R/contents/.github/dependabot.yml" --jq .path` prints the config path (package GP-09).
- [ ] RUN-BUILDFILE-LIVE-CLOSE (review) Record the in-game result of an AshLight-made .build.
  ACCEPT: python tools/live_verdicts.py lists a verdict for TC-BUILDFILE-LIVE and python -m pytest
  -q tests/test_ascii_lf.py tests/test_research_numbers.py tests/test_leak_sweep.py passes.
  ZERO-CLICK: One download click, one file move by the player, one verdict click. DEPENDS:
  RUN-VERDICTS-CORE, RUN-VERDICTS-UI. BLOCKED: the operator loads one AshLight-made .build in game
  and clicks Worked or Refused; unblocks when ops/runtime/verdicts.json holds a TC-BUILDFILE-LIVE
  verdict (operator).
- [ ] GP-15 (review) Release settings: immutable releases and the tag ruleset. ACCEPT: `gh api
  "repos/$R/immutable-releases" --jq .enabled` prints true, `gh api "repos/$R/rulesets" --jq
  '.[].name'` lists release-tags, and `gh release list --repo "$R"` is empty. ZERO-CLICK: Agent step
  with gh; tags are pushed only by the release procedure of plan 05. DEPENDS: GP-12,
  PUB-SETTINGS-FILES. BLOCKED: the public flip; unblocks when `gh repo view "$R" --json visibility
  --jq .visibility` prints PUBLIC (package GP-12).
- [ ] RUN-VERDICTS-CLOSE (review) Record the three remaining in-game tries (search string, filter,
  merged filter). ACCEPT: python tools/live_verdicts.py lists verdicts for LIVE-SEARCHSTR,
  LIVE-FILTER and LIVE-FILTER-MERGE and python -m pytest -q tests/test_ascii_lf.py
  tests/test_research_numbers.py tests/test_leak_sweep.py passes. ZERO-CLICK: Each try ends in one
  click; no typed report. DEPENDS: RUN-VERDICTS-CORE, RUN-VERDICTS-UI. BLOCKED: three in-game tries
  by the operator, one verdict click each; unblocks when ops/runtime/verdicts.json holds verdicts
  for LIVE-SEARCHSTR, LIVE-FILTER and LIVE-FILTER-MERGE (operator).
- [ ] LOOP-KIT-REPORT-SEND (review) KIT-REPORT: send the drafted note once a destination inbox
  exists. ACCEPT: The last line for the note in ops/loop/control/delivery.jsonl reads `"reached":
  true` with `"count": "1/1"`. ZERO-CLICK: Sent by the tick's own note path (InboxMixin.deliver_note
  / redeliver) under the 12-a-day cap; no operator step after the destination is configured.
  DEPENDS: AUTO-25. BLOCKED: no outbound note path: loop.dest_inboxes in the gitignored
  config/local.json has no entry for the fleet owner and no fleet roster is configured; unblocks
  when loop_base.load_config(root)['dest_inboxes'] holds a MAIN entry (set on the host by the
  operator, or supplied by the fleet owner) (operator).
