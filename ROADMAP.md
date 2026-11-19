# AshLight ROADMAP

Open work only, as lane rows the loop (`tools/al_loop.py`) can dispatch.
Format: `- [ ] ID (lane) title. ACCEPT: ...`; `(priority)` jumps the queue.
Rows are filed as `docs/roadmap/new/<ID>.md` and closed as
`docs/roadmap/done/<ID>.md`, and folded in at /done.

## Lane: build

- FOLDED 2026-11-18: LIVE-1 -> RUN-LEDGER-CORE, RUN-LEDGER-WIRE, RUN-LEDGER-REPORT, RUN-LIVE1-FIXTURES (docs/plan/07 Coverage; the old row text is in git history).
- FOLDED 2026-11-18: TEST-LIVE-CLICKS -> RUN-LIVE-CLICKS-STRIKE, RUN-LEDGER-WIRE, RUN-LEDGER-REPORT, RUN-LIVE-CLICKS-CLOSE (docs/plan/07 Coverage; the old row text is in git history).
- FOLDED 2026-11-18: OVL-BUDGET -> RUN-BUDGET-LOG-CORE, RUN-BUDGET-LOG-CLIENT, RUN-OVL-BUDGET-CLOSE (docs/plan/07 Coverage; the old row text is in git history).
- [ ] OVL-FPS (review) OVL-FPS: record the in-map overlay check result (budget B19) and close the
  row. ACCEPT: python -m pytest -q tests/test_ascii_lf.py tests/test_research_numbers.py
  tests/test_leak_sweep.py passes and git grep -n B19 --
  docs/decisions/0006-fps-measurement-method.md shows the dated result line with the report's
  figures and `git grep -n "B19" -- docs/decisions/0002-stack.md` prints exactly that one appended
  line. ZERO-CLICK: The operator plays one map they would play anyway; the schedule, the record and
  this write-up need no further act. DEPENDS: OVL-CHECK, RUN-BUDGET-LOG-CORE. BLOCKED: one normally
  played map with tools/ovl_check.py armed (Q-18, budget B19); unblocks when the sidecar Logs dir
  holds an ovl_check report JSON that includes the operator's same / dropped answer (operator).
- [ ] CORE-REGOPEN-ROOT (build) A test core's Checks stat of the docs-watch flag (core.py, REG_OPEN under paths.runtime_dir()) reads the real ops/runtime folder; it must use the core's own runtime root so a test or demo core never touches live runtime (found by PLAY-TD-01A-PLAY-STATES). ACCEPT: python -m pytest -q tests/test_play_states.py passes with a test that a core on a tmp runtime root never stats the live ops/runtime path. ZERO-CLICK: No click: a code fix the loop lands by itself.
- [ ] TC-CARD-PARTS-DOC (build) Item card words in design 0001 section 9 (TCP-8 of the TC-CARD-PARTS
  review): one line naming the mark words (Upgrade, Sidegrade, Downgrade, Not checked, Risky, No risky
  mods), the tones of cardparts.TONES and the rule that a part changes only WORD_KEYS, plus a doc
  test that the section 9 list matches the module. ACCEPT: python -m pytest -q
  tests/test_tc_cardparts.py passes with that doc test. ZERO-CLICK: No click: a doc and test edit
  the loop lands by itself. DEPENDS: TC-CARD-PARTS.
- [ ] TC-EVAL-NOTES-STYLE (build) Card notes list style (TCPW-1 of the TC-CARD-PARTS-WEB review): web/app.css gets a rule for #eval-notes (no bullets, the card's own spacing) so the notes read as part of the card. ACCEPT: python -m pytest -q tests/test_ux_review.py passes and npm test --prefix app passes. ZERO-CLICK: No click: a style edit the loop lands by itself. DEPENDS: TC-CARD-PARTS-WEB.
- [ ] TC-OVL-CARD-TONE (build) Overlay card honours the core tone (TCP-3 of the TC-CARD-PARTS review): app/shared/format.js takes the card's tone from the core snapshot instead of its own edge rule, as the dashboard does. ACCEPT: npm test --prefix app passes with a test that a core tone overrides the edge colour. ZERO-CLICK: No click: the overlay follows the core's tone by itself. DEPENDS: TC-CARD-PARTS-WEB.

## Lane: data


## Lane: review

- [ ] WT-SIDECAR-WIRE (review) Reopened WT-SIDECAR: agent worktrees must land under the AL sidecar through the decision 0012 hooks, not only by the hand-run hook. ACCEPT: python -m pytest -q tests/test_wt_sidecar_hook.py -rs reports no skip and git worktree list after one isolated agent spawn shows its path under the sidecar Worktree folder. ZERO-CLICK: One paste by the operator, once; every later wave spawn lands in the sidecar by itself. BLOCKED: operator act (paste the two hook entries of decision 0012 into .claude/settings.json); AUTO-26 flips it when its proof passes.


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


- FOLDED 2026-11-18: CODE-HEALTH-FOLLOWUP -> TEST-STATE-EQUIV, RUN-ZONE-RESET, TEST-STATE-TEXT-2, TEST-STATE-TEXT-3, TEST-STATE-TEXT-4, TEST-STATE-TEXT-PINS, TEST-WEB-FMT, RUN-DURABLE-CRLF (docs/plan/07 Coverage; the old row text is in git history).


- FOLDED 2026-11-18: MERGE-SEAMS-FOLLOWUP -> PLAY-TD-01B-FIT-HARNESS, PLAY-TD-09B-SKELETON, PLAY-TD-09C-BAR (docs/plan/07 Coverage; the old row text is in git history). F1 (Play fit with both slots full) delivered 2026-11-18 by PLAY-TD-01B-FIT-HARNESS (figures in docs/design/play-fit-figures.md); F4 (Play column focus) delivered 2026-11-18 by PLAY-TD-09B-SKELETON; still open: F2, F5, F7.

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

- [ ] PUB-LOCAL-ONLY-TEXT (build) Replace the local-only wording in loop tools and ritual files.
  ACCEPT: `python -m pytest -q tests/test_loop_split.py tests/test_p163_lane_tools.py
  tests/test_fleet_kit_conformance.py tests/test_al_loop_gate_cache.py tests/test_ascii_lf.py` is
  green and `git grep -n -i "AL is local only\|repo is local only\|never push, local only\|AL: local
  only\|AL_ALLOW_PUSH" -- tools .claude` prints nothing and `python -m pytest -q
  "tests/test_al_loop_gate_cache.py::test_push_is_skipped_while_the_loop_push_switch_is_off"
  "tests/test_al_loop_gate_cache.py::test_push_runs_with_a_fake_origin_and_the_switch_on"` is green
  and `git grep -c loop_push -- tools/al_loop.py` prints a count of at least 1. ZERO-CLICK: Text
  only: the loop prompt and the /done ritual then describe the guarded push, so sessions and lanes
  follow it with no reminder. REOPENED 2026-11-18 (ruling R2): the wording landed at 7fe4993; the
  loop_push switch was never built and is the remaining work. BLOCKED: session wave 4.
- [ ] LOOP-WAVE-HOLD (build) Wave folder hold and the shared merge lock. ACCEPT: `python -m pytest
  -q tests/test_loop_wave_hold.py tests/test_loop_flip.py tests/test_al_loop_gate_cache.py
  tests/test_al_loop.py` passes. ZERO-CLICK: The session that starts a wave writes the hold file and
  the session that ends it removes it; the loop parks and later merges by itself, with no operator
  step. DEPENDS: LOOP-ROWFILES-MERGE, LOOP-FAILED-PARK. BLOCKED: session wave 4.
- [ ] SEC-ACL-APPLY (build) Private runtime files: explicit ACL on the runtime dir and local config.
  ACCEPT: python -m pytest -q tests/test_acl.py tests/test_audit_exe_path.py
  tests/test_hot_reload.py passes: a tmp runtime dir made private and the token file written into it
  (and a pre-existing child folder) read back exactly the three SIDs (player, SYSTEM, the admins
  group (SID S-1-5-32-544)), a second make_private changes nothing, and a kept token in a dir with
  one more writer is not reused. ZERO-CLICK: Runs by itself at every core start; nothing for the
  player to do. DEPENDS: SEC-NO-DISCOVERY. BLOCKED: session wave 4.
- [ ] GP-05 (build) CI workflows and their lint test. ACCEPT: `python -m pytest -q
  tests/test_ci_workflow.py tests/test_ascii_lf.py tests/test_leak_sweep.py tests/test_al_loop.py`
  is green. ZERO-CLICK: Runs by itself on every push and pull request once the remote exists; CI
  never turns web data on and calls no GGG or poe.ninja host. DEPENDS: GP-04. BLOCKED: session wave
  4.
- [ ] DATA-PRICE-CARD-TEXT (build) Price card words: cache age, league after a change, contact copy
  + One card per trade request: a repeated whisper refreshes its card. ACCEPT: python -m pytest -q
  tests/test_price_card_age.py tests/test_price_text.py tests/test_price_book.py
  tests/test_price_check.py tests/test_design_gate.py passes. Also (folded
  PLAY-F-120-TRADE-REFRESH): python -m pytest -q tests/test_trade_refresh.py
  tests/test_trade_close.py tests/test_trade_expire.py passes: three identical whispers from one
  sender and one from another leave 2 trade_requests rows, the first with the newest at,
  recent_whispers holds all four lines, and a Trade accepted line still closes one card. ZERO-CLICK:
  Automatic on presses the player already makes. Also (folded PLAY-F-120-TRADE-REFRESH): Automatic
  from the Client.txt lines already tailed. DEPENDS: DATA-LEAGUE-IDENTITY. BLOCKED: session wave 4.
- [ ] PLAY-F-131-STATUS-TABLE (build) One status vocabulary table for the bar, the overlay, Checks
  and the strip. ACCEPT: node --test app/test/statuswords.test.js app/test/dashboard.test.js
  app/test/shared.test.js and python -m pytest -q tests/test_status_words.py tests/test_diag_self.py
  pass: each state of the table gives the table's words on all four surfaces (bar word, overlay
  word, Checks detail, strip next step), the overlay word is at most 15 characters beside the level
  text or marked alone at most 27, and the table copies in web/status.js and
  app/shared/render_gate.js equal the JSON source. ZERO-CLICK: Status only; it follows the feed by
  itself. BLOCKED: session wave 4.
- [ ] PLAY-TD-01B-FIT-HARNESS (build) Fit harness, red first (G1, G2, G4-G7, G9). ACCEPT: python -m
  pytest -q tests/test_play_fit.py passes on today's layout with every region and tab listed as
  pending (state c at 1280x760 measures more than 300 px over) and fails when a pending marker is
  deleted while its region still overflows. ZERO-CLICK: Dev step; runs in the gates on a demo core
  in windowless Chrome; skips cleanly without Chrome or node. DEPENDS: PLAY-TD-01A-PLAY-STATES,
  SEC-DEMO-ENTRY. BLOCKED: session wave 4.
- [ ] PLAY-TD-03-TOKENS (build) Type, spacing, scale and control-edge tokens. ACCEPT: python -m
  pytest -q tests/test_design_tokens.py tests/test_ux_review.py tests/test_design_contrast.py
  tests/test_a11y.py passes: six --al-fs-* rem tokens with fixed rem line boxes and no vw or clamp,
  body declares tabular-nums, the --al-control-edge and --al-text-body rows of the design 0001 5.2
  block meet 3.0 and 4.5, no rule outside the token block uses --fk-text-muted as a border, and the
  title step gives at least 16 arcmin at the Q-14 reference setup. ZERO-CLICK: Styling only; nothing
  to press. BLOCKED: session wave 4.
- [ ] TC-PRESS-STAGED-EVAL (build) evaluate() in all-or-nothing stages. ACCEPT: python -m pytest -q
  tests/test_tc_stages.py tests/test_tc_delta.py tests/test_math_weights.py
  tests/test_math_compare.py tests/test_tc_eval.py passes. ZERO-CLICK: Dev step: pure refactor
  proven by equality tests; nothing for the player yet. BLOCKED: session wave 4.
- [ ] TC-WORN-STORE (build) Worn-gear store and baseline. ACCEPT: python -m pytest -q
  tests/test_tc_worn_gear.py tests/test_sidecar_paths.py passes. ZERO-CLICK: Dev step: storage only;
  it is wired by TC-WORN-WIRE. BLOCKED: session wave 4.
- [ ] OVL-MAIN-PARTS (build) Main-process parts seam: app/parts/ files loaded by app/parts.js;
  hotkey registration moves into the first part. ACCEPT: node --test app/test/parts.test.js
  app/test/client.test.js app/test/hotkey.test.js app/test/eval.test.js and python -m pytest -q
  tests/test_overlay_smoke.py tests/test_floor_static.py tests/test_diag_self.py
  tests/test_desktop_client.py pass. ZERO-CLICK: Dev step: nothing for the player; the same two keys
  register at start with no click. The clipboard read stays the one read per manual press in
  app/main.js. BLOCKED: session wave 4.
- [ ] SEC-HELLO-CORE (build) Core hello handshake: GET /api/hello and the supervisor check. ACCEPT:
  python -m pytest -q tests/test_hello.py tests/test_keepalive.py tests/test_security_surface.py
  tests/test_http_security.py passes: a fake listener answering 200 to everything receives no
  X-AL-Token header from keepalive.health_check, and /api/hello answers 401 without a valid client
  proof. ZERO-CLICK: Code change; the supervisor verifies by itself once per token value and after
  any request error. DEPENDS: SEC-STATIC-MAP, SEC-NO-PROXY, SEC-SURFACE-PIN. BLOCKED: session wave
  4.
- [ ] TC-FILTER-ONE-CONTROL (build) One filter control, stamped. ACCEPT: python -m pytest -q
  tests/test_lootfilter.py tests/test_lootfilter_merge.py tests/test_lootfilter_tiers.py passes and
  npm test --prefix app passes. ZERO-CLICK: Content regenerates itself; moving the file stays the
  player's act (decisions 0031, 0033). DEPENDS: TC-CARD-PARTS-WEB. BLOCKED: session wave 4.

### Wave 5: Play tab and dashboard, reliability and observability, overlay and client

- [ ] AUTO-06 (build) WAVE-INTERPLAY: BLOCKED reason echo and the dispatch re-check from HEAD.
  ACCEPT: `python -m pytest -q tests/test_loop_wave.py tests/test_loop_rowfiles.py
  tests/test_loop_plandeps.py tests/test_al_loop.py` passes. ZERO-CLICK: The session that ends a
  wave flips its rows and removes the hold file; no operator step, and the loop needs no reminder.
  DEPENDS: LOOP-ROWFILES-WORK, LOOP-WAVE-HOLD, AUTO-01. BLOCKED: session wave 5.
- [ ] RUN-SEAMS (build) Plug-in folder: ticks, Checks rows and token-gated routes without
  shared-file edits. ACCEPT: python -m pytest -q tests/test_plug_seams.py
  tests/test_core_crash_log.py tests/test_http_security.py tests/test_diag_self.py passes, and a
  600-pass failing tick grows the log by under 50 KB. ZERO-CLICK: Dev seam: nothing for the player;
  later packages wire themselves by file name. DEPENDS: SEC-SURFACE-PIN, SEC-NO-DISCOVERY. BLOCKED:
  session wave 5.
- [ ] SEC-ACL-SETUP (build) setup.ps1 makes the sidecar private; the logon launcher starts
  PowerShell by its System32 path. ACCEPT: python -m pytest -q tests/test_launcher_paths.py
  tests/test_autostart.py passes: no .ps1 or .vbs under scripts/ starts powershell, cmd, wscript or
  icacls by a bare name, setup.ps1 calls the acl CLI for the sidecar, the runtime dir and
  config/local.json, the CLI leaves a tmp sidecar (and a child folder in it) with exactly the three
  SIDs and a second run changes nothing, and both scripts parse in powershell.exe 5.1. ZERO-CLICK:
  Runs inside setup.ps1 by itself (idempotent; a re-run changes nothing). DEPENDS: SEC-ACL-APPLY.
  BLOCKED: session wave 5.
- [ ] TEST-PORT-LEASE (build) Port lease for tests that bind a port (leases 8962-8969). ACCEPT:
  python -m pytest -q tests/test_port_lease.py tests/test_keepalive.py tests/test_procs.py
  tests/test_supervisor.py tests/test_sidecar_paths.py passes, test_port_lease.py proves two
  processes leasing at the same moment receive different ports in 8962-8969, and two pytest
  processes started together on tests/test_keepalive.py tests/test_procs.py tests/test_supervisor.py
  tests/test_dash_console.py are green in 5 rounds out of 5 (finding F-022 acceptance). ZERO-CLICK:
  Test-only: the lease is taken and released by the fixture; no flag, no prompt. Binds stay on
  127.0.0.1 inside the assigned block; server/al/ports.py is untouched. DEPENDS: SEC-DEMO-CORE.
  BLOCKED: session wave 5.
- [ ] PLAY-TD-07A-PLAY-VIEW (build) Play view: capped strings for strip, feed, notices and build
  line. ACCEPT: python -m pytest -q tests/test_play_view.py passes: snapshot()['play'] carries the
  strip, feed, notices and build blocks with exact rows on the pack states, and on the long-string
  fixture no composed row exceeds its cap (event sentence 38, notice word 12 / title 20 / action 12
  / rows 52, build row two 36). ZERO-CLICK: Composed on every state push from lines already tailed;
  no click. DEPENDS: PLAY-F-131-STATUS-TABLE, DATA-PRICE-CARD-TEXT, PLAY-TD-01A-PLAY-STATES.
  BLOCKED: session wave 5.
- [ ] PLAY-TD-09B-SKELETON (build) Play skeleton: 7 fixed regions on the cockpit grid. ACCEPT:
  python -m pytest -q tests/test_play_fit.py tests/test_a11y.py tests/test_ux_review.py
  tests/test_ux_b8.py tests/test_dash_console.py and npm test --prefix app pass: in the harness
  placeholder mode the 7 region boxes equal the track table at the 5 cockpit sizes (100 / 228 / 204
  / 96 / 68 / 360 / 100 full and 100 / 212 / 204 / 52 / 68 / 348 / 52 compact at s = 1, x 1.25 at
  1920 wide), #panel-play has no tabindex, and the .play-main / .play-side wrappers are gone.
  ZERO-CLICK: Layout only; every region keeps filling from the state push with no click. DEPENDS:
  PLAY-TD-09A-REGION-HOOK, PLAY-TD-03-TOKENS, PLAY-TD-01B-FIT-HARNESS. BLOCKED: session wave 5.
- [ ] TC-CAMPAIGN-KEEP (build) Keep-or-vendor verdict with no build loaded. ACCEPT: python -m pytest
  -q tests/test_tc_levelrules.py tests/test_hot_reload.py tests/test_eval_text.py passes.
  ZERO-CLICK: No new press: rides the existing item-check key; level and zone come from the opted-in
  Client.txt tail. DEPENDS: TC-CARD-PARTS. BLOCKED: session wave 5.
- [ ] RUN-LEDGER-CORE (build) Parse ledger module: hit counts and masked shapes (logshapes.py).
  ACCEPT: python -m pytest -q tests/test_logshapes.py tests/test_parser.py tests/test_fuzz.py
  passes. ZERO-CLICK: Fills by itself once wired and consented. DEPENDS: SEC-NO-DISCOVERY. BLOCKED:
  session wave 5.
- [ ] OVL-KEYS-CLIENT (build) Hotkeys in the client: re-register on a config change, fall back from
  a taken key, write ops/runtime/hotkeys.json. ACCEPT: node --test app/test/hotkeys_live.test.js
  app/test/hotkey.test.js app/test/parts.test.js and python -m pytest -q tests/test_floor_static.py
  tests/test_overlay_smoke.py pass. ZERO-CLICK: Conflicts heal by themselves at start and on a
  config change; rebinding stays optional. Nothing is sent to the game and the clipboard read stays
  one per manual press. DEPENDS: OVL-MAIN-PARTS. BLOCKED: session wave 5.
- [ ] PLAY-TD-19A-PAGER (build) Pager: list pages and the Full text page. ACCEPT: node --test
  app/test/pager.test.js passes: 23 rows page as 1-10 of 23 with Prev / Next (8 a page in the
  compact class), the Full text page holds 3 entries of up to 3 wrapped lines (2 x 4 compact), a
  page changes only on a press, and focus stays on the pressed button. ZERO-CLICK: Pages never
  advance by themselves; paging is an optional review act outside play. DEPENDS:
  PLAY-TD-09A-REGION-HOOK. BLOCKED: session wave 5.
- [ ] OVL-GLANCE-RULES (build) Glance budget and notification policy in design 0001, held by tests.
  ACCEPT: python -m pytest -q tests/test_glance_rules.py tests/test_design_gate.py
  tests/test_ascii_lf.py passes. ZERO-CLICK: Not player-facing; the tests run in the suite. BLOCKED:
  session wave 5.
- [ ] PLAY-TD-04A-DARK-CLIENT (build) Dark by default in the desktop client. ACCEPT: node --test
  app/test/theme.test.js passes: app/main.js sets nativeTheme.themeSource to dark before any
  BrowserWindow is created, app/client/window.js uses backgroundColor #0f1216, and
  app/client/starting.css has no prefers-color-scheme block and uses #0f1216, #e4e8ec and #99a1aa
  with the stack system-ui, Segoe UI, sans-serif. ZERO-CLICK: Dark with no action. BLOCKED: session
  wave 5.
- [ ] GP-09 (build) Create the private repository, first push, CI green. ACCEPT: `gh repo view "$R"
  --json visibility --jq .visibility` prints PRIVATE, `git rev-parse main` equals `git rev-parse
  origin/main`, `git ls-remote --heads --tags origin` lists refs/heads/main and otherwise only
  refs/heads/dependabot/*, and `gh run list --repo "$R" --branch main --limit 4 --json
  workflowName,conclusion` shows ci and fleet-identity-guard as success. ZERO-CLICK: Runs only on
  the operator's recorded go (ruling Q-23, step 1): the hand-off line 'OPERATOR GO Q-23 step 1' that
  quotes the operator's own words with their date. From there agent steps only: gh is already signed
  in; no click. A private repository publishes nothing. DEPENDS: GP-01, GP-02, PUB-GO-DECISION,
  PUB-LOCAL-ONLY-TEXT, GP-03, GP-04, GP-05. BLOCKED: session wave 5.

### Wave 6: Play tab and dashboard, local security, reliability and observability

- [ ] SEC-ACL-CHECK (build) Checks note when AshLight's folders let someone else write. ACCEPT:
  python -m pytest -q tests/test_acl_check.py tests/test_diag_self.py passes: a dir prepared with
  one more writer yields the Checks row with its fix line, three private dirs yield no row, and the
  copied report holds no path or user name. ZERO-CLICK: Runs by itself once per core start on a
  background thread; the note for a shared AshLight folder asks for one command, because rewriting
  the ACL of the player's own checkout unasked would be intrusive. DEPENDS: SEC-ACL-APPLY,
  SEC-NO-DISCOVERY. BLOCKED: session wave 6.
- [ ] RUN-DURABLE-CRLF (build) Move the five CRLF / hand-rolled writers onto the jsonfile helper.
  ACCEPT: python -m pytest -q tests/test_durable_lf.py tests/test_keepalive.py tests/test_procs.py
  tests/test_hot_reload.py passes. Also (review): the new case
  test_stop_and_run_scripts_read_lf_pid_and_state_files passes: scripts/stop.ps1 and scripts/run.ps1
  read the LF-written pid, state and heartbeat files (PowerShell 5.1, fixture files under tmp_path,
  no process started or stopped). ZERO-CLICK: Automatic. DEPENDS: RUN-DURABLE-JSONFILE, RUN-SEAMS.
  BLOCKED: session wave 6.
- [ ] PLAY-TD-07B-PLAY-CARDS (build) Play view: context modes, item card and kept checks. ACCEPT:
  python -m pytest -q tests/test_play_cards.py tests/test_play_view.py passes: play.context holds
  one block per available mode with a title of at most 38 characters and at most 7 rows of at most
  52, play.item holds the verdict word, a 2-row sentence of at most 36 a row, 5 compare rows, a
  price row and at most 2 links, play.kept at most 3 rows of at most 42, and a guide entry that
  needs more than 7 rows fails the data test. ZERO-CLICK: Follows the log: the mode blocks change
  with the zone, the build and the last check. DEPENDS: PLAY-TD-07A-PLAY-VIEW, TC-CARD-PARTS.
  BLOCKED: session wave 6.
- [ ] PLAY-TD-09C-BAR (build) Bar: the mark, the character slot and one status word + MERGE-SEAMS F5
  and F7: restart note clears, tool-row class. ACCEPT: python -m pytest -q tests/test_a11y.py
  tests/test_ux_b8.py tests/test_brand_assets.py tests/test_dash_console.py and npm test --prefix
  app pass: the header shows web/favicon.svg as an img in a 20 px box with empty alt left of the
  name, #bar-char exists, #link is gone, #reading is the one polite status word on every tab and is
  written through ALDash.barStatus, and both live-region cap tests assert at most 11. Also (folded
  PLAY-MERGE-SEAMS-F5-F7): node --test app/test/client_controls.test.js and python -m pytest -q
  tests/test_ux_b6.py tests/test_dash_console.py pass: render() clears #restart-overlay-said on the
  next state push after a restart (wireRestartOverlay region), and no file under web/ or app/test/
  names the class hint-reset (it is tool-row). ZERO-CLICK: The bar word follows the feed by itself;
  nothing to press. Also (folded PLAY-MERGE-SEAMS-F5-F7): The restart note clears itself on the next
  state push; nothing to press. DEPENDS: PLAY-TD-09B-SKELETON, PLAY-F-131-STATUS-TABLE. BLOCKED:
  session wave 6.
- [ ] PLAY-TD-13-FEED (build) Feed T: five one-line rows, trades first. ACCEPT: node --test
  app/test/feed.test.js and python -m pytest -q tests/test_play_fit.py pass with the t marker
  deleted: region T fits 204 px with 5 open trades at the 5 cockpit sizes, every open trade has a
  row with its own Dismiss, Dismiss all shows from 2 trades, a keyboard dismiss moves focus to the
  next row's Dismiss or the T heading, and the trade status region announces at most 12 words.
  ZERO-CLICK: Trades and events arrive from the log; Dismiss is optional. DEPENDS:
  PLAY-TD-09B-SKELETON, PLAY-TD-07A-PLAY-VIEW, PLAY-TD-02-SLOTS. BLOCKED: session wave 6.
- [ ] PLAY-TD-15-BUILDLINE (build) Build line B with the Paste a build button. ACCEPT: node --test
  app/test/buildline.test.js and python -m pytest -q tests/test_play_fit.py pass with the b marker
  deleted: a consented snapshot with no build shows [ ] No build and the button, the click shows the
  build tab with #build-paste focused, the four states print their words, and region B fits 68 px.
  ZERO-CLICK: The state shows and changes by itself; the paste is the one act the floor-safe build
  sources leave. DEPENDS: PLAY-TD-09B-SKELETON, PLAY-TD-07A-PLAY-VIEW, PLAY-TD-02-SLOTS. BLOCKED:
  session wave 6.
- [ ] PLAY-TD-14-NOTICE (build) Notice N: one notice at a time. ACCEPT: node --test
  app/test/notice.test.js and python -m pytest -q tests/test_play_fit.py pass with the n marker
  deleted: region N fits 96 px (52 compact, head row only, kinds 6-7 hidden), shows the first notice
  of ALSlots.noticePick with at most 1 action and a +N more count, and Setup: N steps left shows
  Settings. ZERO-CLICK: Notices show and leave by themselves; every action is optional. DEPENDS:
  PLAY-TD-09B-SKELETON, PLAY-TD-07A-PLAY-VIEW, PLAY-TD-02-SLOTS. BLOCKED: session wave 6.
- [ ] RUN-VERDICTS-CORE (build) Verdict store, token API and read-back script for the 'Tried in
  game' checks. ACCEPT: python -m pytest -q tests/test_live_verdicts.py tests/test_http_security.py
  passes. ZERO-CLICK: Developer side automatic; one click per check for the player. DEPENDS:
  RUN-SEAMS, RUN-DURABLE-JSONFILE. BLOCKED: session wave 6.
- [ ] OVL-OVERLAY-KEYS (build) Overlay settings schema: parts switches, quiet town, zone-guide
  choice in layout.py and layout.js. ACCEPT: python -m pytest -q tests/test_overlay_layout.py
  tests/test_ux_settings_io.py tests/test_bus_state.py and node --test app/test/layout.test.js pass.
  ZERO-CLICK: Defaults keep today's overlay (everything on, zone guide On entry); nothing to click.
  BLOCKED: session wave 6.
- [ ] TEST-STATE-EQUIV (build) tools/state_equiv.py and the design gate prefix server/al/text/.
  ACCEPT: python -m pytest -q tests/test_state_equiv.py tests/test_design_gate.py passes and python
  tools/state_equiv.py --ref HEAD prints 'state_equiv: identical' and exits 0. ZERO-CLICK:
  Developer-side only; the player does nothing. The tool is run by each later state.py package as
  its own check; no flag beyond the reference revision. DEPENDS: TEST-LAYOUT-GUARD, LOOP-LEDGERS.
  BLOCKED: session wave 6.
- [ ] DEP-02 (build) The source install works for a stranger. ACCEPT: python -m pytest -q
  tests/test_sidecar_paths.py tests/test_source_install.py passes, and a fresh git clone of HEAD
  under <sidecar>/Scratch/clean-clone with AL_SIDECAR_ROOT unset runs setup.ps1 -NoShortcut then
  run.ps1 -NoOverlay -NoBrowser -Port 8961 and answers /api/health with every created path inside
  the clone or the AL sidecar. ZERO-CLICK: Dev step: the same two script calls, no prompt; nothing
  changes for a player in play. DEPENDS: GP-05, SEC-ACL-APPLY, SEC-ACL-SETUP. BLOCKED: session wave
  6.
- [ ] SEC-SSE-TAP (build) OBS-SSE-EVENTS: stop sending chat-bearing frames by default. ACCEPT:
  python -m pytest -q tests/test_http_security.py tests/test_fullstack.py tests/test_e2e_replay.py
  tests/test_soak.py tests/test_bus_state.py tests/test_fuzz.py tests/test_resume.py
  tests/test_trade_expire.py passes: a default stream holds 0 'events' frames over a fixture replay
  while a state push still arrives within 250 ms, tap frames hold no string field but type, and the
  snapshot has no recent_whispers key. ZERO-CLICK: Nothing to do; the dashboard and overlay read
  state frames only (no consumer of the events frame exists in web/ or app/). DEPENDS:
  SEC-STATIC-MAP, SEC-NO-DISCOVERY. BLOCKED: session wave 6.
- [ ] AUTO-21 (review) LOOP-RESUME: remove HALT after the six checks (no later than 2026-12-04).
  ACCEPT: `python tools/al_loop.py tick --dry-run --ignore-halt` lists as 'would dispatch' only rows
  without BLOCKED that the plan leaves to the loop, HALT is absent afterwards, and
  ops/loop/control/progress/loop.json of the next tick does not read 'halted'. ZERO-CLICK: The tick
  resumes by itself every 15 minutes; the scheduled task stays installed and nothing is reinstalled.
  DEPENDS: AUTO-01, LOOP-HANDOFF-PREFIX, LOOP-PREFLIGHT-CMD, LOOP-FAILED-PARK, AUTO-02, AUTO-03,
  LOOP-ROWFILES-MERGE, LOOP-ROWFILES-WORK, LOOP-DONE-FOLD, AUTO-04, AUTO-06, LOOP-WAVE-HOLD,
  TEST-PLUGIN-PIN. BLOCKED: session wave 6.

### Wave 7: Play tab and dashboard, tests and code seams, reliability and observability

- [ ] TEST-WEB-SRCPATHS-NODE (build) app/test/_web.js: one helper that knows where dashboard sources
  live (node side). ACCEPT: npm test --prefix app passes and grep -l '\.\./\.\./web'
  app/test/*.test.js prints nothing. ZERO-CLICK: Developer-side only; the player does nothing. The
  helper is required by the tests; no flag. DEPENDS: TEST-LAYOUT-GUARD. BLOCKED: session wave 7.
- [ ] TEST-WEB-SRCPATHS-PY (build) tests/srcpaths.py: one helper that knows where dashboard sources
  live (Python side). ACCEPT: python -m pytest -q tests/test_srcpaths.py tests/test_a11y.py
  tests/test_brand_assets.py tests/test_http_security.py tests/test_lootfilter_merge.py
  tests/test_overlay_layout.py tests/test_price_text.py tests/test_tc_snap_ui.py
  tests/test_trade_close.py tests/test_trade_expire.py tests/test_ux_b6.py tests/test_ux_b8.py
  tests/test_ux_review.py tests/test_hot_reload.py tests/test_tc_code_real.py passes and grep -l
  '"web" / "index.html"' tests/test_*.py prints nothing. ZERO-CLICK: Developer-side only; the player
  does nothing. The helper is imported by the tests; no flag. DEPENDS: TEST-LAYOUT-GUARD. BLOCKED:
  session wave 7.
- [ ] RUN-DURABLE-STORES (build) Core saves retried from the tick with back-off; one Checks row
  while unsaved. ACCEPT: python -m pytest -q tests/test_durable_stores.py
  tests/test_ux_settings_io.py tests/test_util_run_history.py tests/test_zone_guide.py
  tests/test_util_map_ladder.py passes. ZERO-CLICK: Automatic; one Checks row while a store is
  unsaved; 'Settings were damaged and restored from the last good copy.'. DEPENDS:
  RUN-DURABLE-JSONFILE, RUN-SEAMS, RUN-DURABLE-STORE-FILES. BLOCKED: session wave 7.
- [ ] TEST-MARKS (build) Mark timing, calc and worker-group tests. ACCEPT: python -m pytest -q
  tests/test_marks.py passes and python -m pytest --collect-only -q -m calc lists tests from the
  eight live calc files only. ZERO-CLICK: Selection is automatic: the marks are read by
  tools/test_select.py and by the suite runner; nobody passes a flag. DEPENDS: TEST-PORT-LEASE,
  TEST-PLUGIN-PIN. BLOCKED: session wave 7.
- [ ] PLAY-TD-11-CONTEXT (build) Context C: guide, town, map and none modes. ACCEPT: node --test
  app/test/context.test.js and python -m pytest -q tests/test_play_fit.py pass with the c-zone
  marker deleted: region C fits 228 px (212 compact) in guide, town and none modes, a replayed log
  entering a town shows the search string row and leaving hides it, no build means no row, and Copy
  writes the exact string of at most 250 characters. ZERO-CLICK: Shows and leaves with the zone;
  Copy is the one optional click the clipboard rule requires. DEPENDS: PLAY-TD-09B-SKELETON,
  PLAY-TD-07B-PLAY-CARDS, PLAY-TD-02-SLOTS. BLOCKED: session wave 7.
- [ ] PLAY-TD-10-STRIP (build) Strip G, the bar words and the stale look. ACCEPT: node --test
  app/test/strip.test.js and python -m pytest -q tests/test_play_fit.py pass with the g marker
  deleted: region G fits its 100 px track in every state at the 5 cockpit sizes (G1, G4), zone 28
  px, numbers 32 px, sub lines 20 px (G9), the strip values compute to rgb(153, 161, 170) in state d
  and rgb(228, 232, 236) in state c, and the reading word is neutral while ok. ZERO-CLICK: Follows
  the feed by itself; timers tick once a second. DEPENDS: PLAY-TD-09B-SKELETON,
  PLAY-TD-07A-PLAY-VIEW, PLAY-F-131-STATUS-TABLE, PLAY-TD-02-SLOTS, PLAY-TD-09C-BAR. BLOCKED:
  session wave 7.
- [ ] PLAY-TD-16B-KEPT-CHECKS (build) Kept checks U: the 3 best checked items. ACCEPT: node --test
  app/test/keptchecks.test.js and python -m pytest -q tests/test_play_fit.py pass with the u marker
  deleted: region U fits 100 px with 3 rows (52 px with 1 row and 4 px padding in compact), rows are
  at most 42 characters at 14 px, and a build change re-orders the rows from the next state push.
  ZERO-CLICK: Re-ranks by itself on a build or weight change (decision 0045). DEPENDS:
  PLAY-TD-09B-SKELETON, PLAY-TD-07B-PLAY-CARDS, PLAY-TD-02-SLOTS. BLOCKED: session wave 7.
- [ ] PLAY-TD-16A-ITEMCARD (build) Item card I: verdict first, reserved rows. ACCEPT: node --test
  app/test/itemcard.test.js and python -m pytest -q tests/test_play_fit.py pass with the i marker
  deleted: region I fits 360 px (348 compact) with a full card, the verdict word is 28 px with its
  glyph, at most 2 links and 2 actions show, the empty state teaches the press with the keys from
  the snapshot, and its text says the dashboard card stays and the overlay card leaves after its
  card time. ZERO-CLICK: Fills from the press the player already makes (one clipboard read per
  manual press, unchanged); nothing else to press. DEPENDS: PLAY-TD-09B-SKELETON,
  PLAY-TD-07B-PLAY-CARDS, PLAY-TD-02-SLOTS. BLOCKED: session wave 7.
- [ ] OVL-PARTS-PAGE (build) Overlay page honours the parts switches: a part that is off drops out,
  an empty HUD plate is absent. ACCEPT: node --test app/test/overlay_parts.test.js
  app/test/layout.test.js app/test/overlay_gate.test.js app/test/shared.test.js
  app/test/eval.test.js and python -m pytest -q tests/test_overlay_smoke.py tests/test_budgets.py
  pass. ZERO-CLICK: Default stays Full; the choice is set once and saved; the page follows the
  snapshot with no click. DEPENDS: OVL-OVERLAY-KEYS. BLOCKED: session wave 7.
- [ ] PLAY-TD-08A-GUIDE-SHORT-FIELD (build) Zone guide short field: loader, cap and view key.
  ACCEPT: python -m pytest -q tests/test_zone_guide.py passes: every entry's short is ASCII of at
  most 34 characters or empty, the view carries the key short, and a 35-character short fails the
  load. ZERO-CLICK: Published in the snapshot on each zone change; nothing to press. BLOCKED:
  session wave 7.
- [ ] DEP-05 (build) Installed-mode paths (Python side). ACCEPT: python -m pytest -q
  tests/test_install_paths.py tests/test_sidecar_paths.py tests/test_port_resolve.py
  tests/test_procs.py passes. ZERO-CLICK: Resolved from the marker by itself; nothing to set. In a
  checkout nothing changes. DEPENDS: DEP-02, RUN-DURABLE-JSONFILE, SEC-DEMO-ENTRY. BLOCKED: session
  wave 7.
- [ ] TC-VERDICT-CAVEAT (build) Build caveat on the verdict; alerts name the item-key press. ACCEPT:
  python -m pytest -q tests/test_eval_text.py tests/test_build_live.py tests/test_overlay_layout.py
  passes. ZERO-CLICK: Appears and clears by itself with the alert; no click. DEPENDS: TC-CARD-PARTS,
  TC-PRESS-BUILD. BLOCKED: session wave 7.
- [ ] OVL-CLIENT-ZOOM (build) Probe and restore zoom in the desktop client. ACCEPT: node --test
  app/test/zoom.test.js app/test/parts.test.js and python -m pytest -q tests/test_client_zoom.py
  tests/test_overlay_smoke.py tests/test_floor_static.py pass (the probe test skips without Electron
  or its opt-in variable). ZERO-CLICK: Zoom is the player's own key in AshLight's own window;
  nothing new to set up. DEPENDS: OVL-MAIN-PARTS.
- [ ] AUTO-23 (build) DEV-LEDGERS: rotate the sub-agent ledger, flag a stale docs watch, tidy suite
  logs. ACCEPT: `python -m pytest -q tests/test_ledger_rotate.py tests/test_guard_loop_state.py`
  passes, with a seeded 40-day ledger keeping 30 days and a 4-day-old read printing one STALE line.
  ZERO-CLICK: The daily rotation pass of the tick does it; nothing to remember.

### Wave 8: tests and code seams, install and release, reliability and observability

- [ ] TEST-WEB-FMT (build) web/fmt.js: pad, duration and clock defined once. ACCEPT: npm test
  --prefix app passes, python -m pytest -q tests/test_dash_console.py tests/test_a11y.py
  tests/test_trade_close.py tests/test_floor_static.py passes, and grep -c 'function pad(' web/*.js
  prints 1 for web/fmt.js and 0 for every other file. ZERO-CLICK: Developer-side only; the player
  does nothing. The page loads fmt.js first by itself; a running dashboard in a source checkout
  reloads on the merge (decision 0042). DEPENDS: TEST-WEB-SRCPATHS-NODE, TEST-WEB-SRCPATHS-PY,
  LOOP-LEDGERS. BLOCKED: session wave 8.
- [ ] RUN-TAIL-HEAL-CORE (build) Core restarts a dead log reader and the Reading row tells the
  truth. ACCEPT: python -m pytest -q tests/test_tail_heal.py tests/test_e2e_replay.py
  tests/test_diag_self.py tests/test_resume.py passes. ZERO-CLICK: Automatic; one line ('AshLight
  restarted its log reader.'). DEPENDS: RUN-TAIL-HEAL-READER, RUN-SEAMS, RUN-DURABLE-STORES.
  BLOCKED: session wave 8.
- [ ] TEST-SELECT (build) tools/test_select.py: the test files for a diff. ACCEPT: python -m pytest
  -q tests/test_test_select.py passes and python tools/test_select.py --base HEAD~1 exits 0 printing
  an 'ungated:' line, a 'gated:' line and an 'env:' line. ZERO-CLICK: The tool reads the diff itself
  (git diff --name-only against the wave base); no flag beyond the base, no prompt. DEPENDS:
  TEST-MARKS. BLOCKED: session wave 8.
- [ ] TEST-XDIST-DIAG (review) Three diagnosed parallel suite runs: why the loop's xdist runs went
  red. ACCEPT: python -m pytest -q tests/test_ascii_lf.py tests/test_research_numbers.py
  tests/test_leak_sweep.py passes and the note's new dated addendum holds, for each of the three
  runs, the pass / fail counts, every failing test id, the gate hold seconds and one verdict line
  'XDIST: cleared' or 'XDIST: rejected'. ZERO-CLICK: The agent runs the three gated runs itself at
  below-normal priority and writes the verdict; no operator step. Nothing reads the game process to
  decide when to run. DEPENDS: TEST-PLUGIN-PIN, TEST-PORT-LEASE, TEST-MARKS. BLOCKED: session wave
  8.
- [ ] PLAY-TD-12-CONTEXT-SETUP (build) Context C: setup, error and idle modes. ACCEPT: node --test
  app/test/setupcard.test.js and python -m pytest -q tests/test_play_fit.py pass with the c-setup
  marker deleted: a cold profile shows the 4 setup rows and exactly one button.primary, after the
  opt-in the feed is live and the card leaves, idle shows Last session only while game_idle, and
  region C fits its track in setup, error and idle modes. ZERO-CLICK: One required click (the
  floor's Client.txt opt-in); the other rows are optional and clear themselves when their data
  arrives. DEPENDS: PLAY-TD-11-CONTEXT. BLOCKED: session wave 8.
- [ ] GP-06 (build) Community files. ACCEPT: `python -m pytest -q tests/test_community_files.py
  tests/test_ascii_lf.py tests/test_leak_sweep.py` is green. ZERO-CLICK: Documentation only; nothing
  in play depends on it. BLOCKED: session wave 8.
- [ ] DEP-03 (build) One version, enforced, and the release tool dispatcher. ACCEPT: python -m
  pytest -q tests/test_version.py passes and python tools/release.py bump --check exits 0 at HEAD.
  ZERO-CLICK: Nothing for the player; the loop never bumps by itself (bump runs only inside a
  REL-PREP row or an explicit version request). BLOCKED: session wave 8.
- [ ] DEP-01 (build) Spike: AshLight under the private runtimes. ACCEPT: The new file
  docs/ops/runtime-spike-record.md states PASS or FAIL per check (demo core /api/health on a port in
  8970-8975, one supervisor restart, one calc on the reference build when the calc is installed, the
  five named tests under the embeddable python, boot.py versus ._pth, Electron zip version without
  Node) and lists every re-spawn site that needed a change; python -m pytest -q
  tests/test_ascii_lf.py passes. ZERO-CLICK: Dev only: hidden, fixture log, spare port, scratch
  folder; no player step. DEPENDS: SEC-DEMO-ENTRY. BLOCKED: session wave 8.
- [ ] REL-SUBJECT-CHECK (build) Commit subject check in the commit-msg hook. ACCEPT: python -m
  pytest -q tests/test_commit_subject.py tests/test_fleet_kit_conformance.py
  tests/test_audit_loop_commit_msg.py passes. ZERO-CLICK: Dev step that runs itself in the hook; a
  refused subject names the fix in one line. BLOCKED: session wave 8.
- [ ] DATA-WEBFETCH-GZIP (build) webfetch: bounded gzip inflate, HTTPException mapping, Retry-After
  helper. ACCEPT: python -m pytest -q tests/test_webfetch_gzip.py tests/test_fuzz.py
  tests/test_data_ninja.py tests/test_http_security.py passes. ZERO-CLICK: Automatic: no setting;
  smaller bodies while the game runs. BLOCKED: session wave 8.
- [ ] OVL-ELECTRON-PIN (build) Electron pin: config/electron_pin.json and tools/electron_pin.py
  (hash-pinned fetch, verify, unpack). ACCEPT: python -m pytest -q tests/test_electron_pin.py
  tests/test_sidecar_paths.py tests/test_leak_sweep.py passes. ZERO-CLICK: Setup step: the tool runs
  inside setup with no prompt once OVL-ELECTRON-SETUP wires it; nothing for the player. BLOCKED:
  session wave 8.
- [ ] TEST-HTTP-ROUTES (build) HTTP route tables per verb. ACCEPT: python -m pytest -q
  tests/test_routes.py tests/test_http_security.py tests/test_http_robust.py
  tests/test_api_token_hdr.py tests/test_audit_http_harden.py tests/test_fullstack.py passes.
  ZERO-CLICK: Developer-side only; the player does nothing. Requests are answered as before; nothing
  changes for the player. DEPENDS: SEC-SURFACE-PIN. BLOCKED: session wave 8.

### Wave 9: install and release, tests and code seams, overlay and client

- [ ] TC-PRESS-STAGED-LIVE (build) Publish the item check in stages. ACCEPT: python -m pytest -q
  tests/test_tc_press_staged.py tests/test_eval_text.py tests/test_tc_eval_api.py
  tests/test_tc_wire.py passes (budget B15: first card under 0.5 s). ZERO-CLICK: Same one press; the
  card fills in by itself. DEPENDS: TC-PRESS-STAGED-EVAL, TC-PRESS-BUILD, TC-CARD-PARTS. BLOCKED:
  session wave 9.
- [ ] TEST-WAVE-GATE-POLICY (build) Record the wave gate policy (Q-17) in a decision, the lane
  prompt and /done. ACCEPT: python -m pytest -q tests/test_wave_gate_policy.py
  tests/test_design_gate.py tests/test_fleet_kit_conformance.py tests/test_al_loop_gate_cache.py
  passes. ZERO-CLICK: The prompt text reaches every lane by itself; a session agent reads the rule
  in CLAUDE.md Gates. Nothing for the player. DEPENDS: TEST-SELECT, LOOP-LEDGERS. BLOCKED: session
  wave 9.
- [ ] TEST-WEB-REGISTRY (build) web/registry.js: ALApp.register and per-panel isolation in render,
  tick and start. ACCEPT: npm test --prefix app passes and python -m pytest -q
  tests/test_dash_console.py tests/test_a11y.py tests/test_floor_static.py tests/test_ux_review.py
  passes. ZERO-CLICK: Developer-side only; the player does nothing. Paint order and live-region
  announcements stay as today through explicit order values; nothing for the player to do. DEPENDS:
  TEST-WEB-FMT. BLOCKED: session wave 9.
- [ ] TEST-SUITE-RUNNER (build) tools/suite_run.py: the one whole-suite command, parallel when
  cleared. ACCEPT: python -m pytest -q tests/test_suite_run.py passes and python tools/suite_run.py
  argv --owner x prints the single line 'python ops/fleet_kit/fleet_suite_gate.py run --owner x --
  python tools/suite_run.py'. ZERO-CLICK: The command picks its mode itself (xdist importable or
  not); callers pass no flag. Workers are bounded (4) and run at below-normal priority. DEPENDS:
  TEST-XDIST-DIAG, GP-05. BLOCKED: session wave 9.
- [ ] RUN-ZONE-RESET (build) One _enter_zone() clears per-zone state, with a zone generation counter
  + State text move 1: text/common.py and text/events.py. ACCEPT: python -m pytest -q
  tests/test_bus_state.py tests/test_resume.py tests/test_hud_act.py tests/test_hud_act_resume.py
  tests/test_live_exit.py passes. Also (folded TEST-STATE-TEXT-1): python tools/state_equiv.py --ref
  <package base> prints 'state_equiv: identical' and python -m pytest -q tests/test_summarize.py
  tests/test_eval_text.py tests/test_price_text.py tests/test_trade_text.py tests/test_waystone.py
  tests/test_waystone_reward.py tests/test_build_live.py tests/test_ux_b6.py
  tests/test_design_gate.py tests/test_audit_pass2.py tests/test_math_compare.py
  tests/test_math_dps_sanity.py tests/test_math_weights.py tests/test_tc_delta.py passes.
  ZERO-CLICK: Automatic. Also (folded TEST-STATE-TEXT-1): Developer-side only; the player does
  nothing. A running core in a source checkout reloads itself after the merge (decision 0042).
  DEPENDS: RUN-TAIL-HEAL-CORE, TEST-STATE-EQUIV, TC-CARD-PARTS. BLOCKED: session wave 9.
- [ ] REL-PINFETCH (build) Move the hash-pinned fetch, verify and extract helpers into one stdlib
  module. ACCEPT: python -m pytest -q tests/test_pinfetch.py tests/test_tc_pin.py
  tests/test_tc_drift.py passes. ZERO-CLICK: Dev refactor; nothing changes in play (the running core
  never imports the module). BLOCKED: session wave 9.
- [ ] OVL-LINKS-DOWNLOADS (build) Narrow external links and downloads in the companion window +
  Companion window opens on the second monitor on first run. ACCEPT: node --test
  app/test/client.test.js app/test/link_hosts.test.js app/test/tc_view.test.js
  app/test/audit_tree_url.test.js and python -m pytest -q tests/test_trade_link.py
  tests/test_leak_sweep.py pass. Also (folded OVL-SECOND-DISPLAY): node --test
  app/test/client.test.js app/test/client_controls.test.js passes. ZERO-CLICK: The link click is the
  player's own act; no new prompt. The app still only builds the trade-search URL; the player's
  browser opens it (decision 0017). Also (folded OVL-SECOND-DISPLAY): Fully automatic on the first
  start; the saved place wins from the second start. Electron's display list only: no window or
  process query of the game. DEPENDS: OVL-MAIN-PARTS. BLOCKED: session wave 9.
- [ ] OVL-SHELL-GUARDS (build) Electron shell guards: sandbox for every renderer, default-deny
  navigation / popups / webview, exact IPC senders, quit on debug switches. ACCEPT: node --test
  app/test/guards.test.js app/test/audit_electron.test.js app/test/client_controls.test.js
  app/test/parts.test.js and python -m pytest -q tests/test_overlay_smoke.py
  tests/test_floor_static.py tests/test_desktop_client.py pass. ZERO-CLICK: Nothing for the player;
  no new process, timer or window, so the overlay budgets hold. DEPENDS: OVL-MAIN-PARTS. BLOCKED:
  session wave 9.
- [ ] DEP-04 (build) Notes and changelog generator. ACCEPT: python -m pytest -q
  tests/test_release_notes.py tests/test_version.py passes and python tools/release.py notes
  --changelog --check exits 0. ZERO-CLICK: Prepared unattended by the REL-PREP lane; the player
  reads the result in the app and on the release page. DEPENDS: DEP-03, REL-SUBJECT-CHECK, AUTO-01,
  AUTO-03. BLOCKED: session wave 9.
- [ ] DEP-06 (build) Runtime resolvers and one command builder. ACCEPT: python -m pytest -q
  tests/test_runtime_layout.py tests/test_keepalive.py tests/test_procs.py
  tests/test_sidecar_paths.py tests/test_install_paths.py passes. ZERO-CLICK: Dev and install
  plumbing: the core and supervisor start through one command builder by themselves; a checkout
  keeps today's '-m' form; nothing for the player. DEPENDS: DEP-01, DEP-02, DEP-05. BLOCKED: session
  wave 9.
- [ ] DEP-07 (build) Shell integration helper: shortcuts and the uninstall entry in one place.
  ACCEPT: python -m pytest -q tests/test_shell_integration.py tests/test_desktop_client.py
  tests/test_supervisor.py passes (the last parses every scripts/*.ps1 under PowerShell 5.1).
  ZERO-CLICK: Unchanged for the player: setup writes the shortcuts with no prompt. DEPENDS: DEP-02,
  SEC-ACL-SETUP. BLOCKED: session wave 9.
- [ ] DATA-PRICE-POLITE (build) poe.ninja client: back off, daily retry of a failing type, spaced
  requests. ACCEPT: python -m pytest -q tests/test_data_ninja.py tests/test_price_book.py
  tests/test_util_10_ready.py tests/test_fuzz.py passes. ZERO-CLICK: Automatic; the item press never
  waits on a round (it reads the cache only). DEPENDS: DATA-WEBFETCH-GZIP. BLOCKED: session wave 9.

### Wave 10: install and release, overlay and client, tests and code seams

- [ ] TC-WORN-BASELINE (build) Item check compares against the worn item first. ACCEPT: python -m
  pytest -q tests/test_tc_worn_baseline.py tests/test_tc_eval.py tests/test_tc_delta.py
  tests/test_tc_stages.py tests/test_eval_text.py passes. ZERO-CLICK: Dev step: proven by its tests;
  filing a worn item is wired by TC-WORN-WIRE, after which verdicts follow by themselves. DEPENDS:
  TC-WORN-STORE, TC-PRESS-STAGED-LIVE, TC-PRESS-STAGED-EVAL, TC-CAMPAIGN-KEEP. BLOCKED: session wave
  10.
- [ ] PLAY-LEGACY-OUT-1 (build) Legacy out 1: old strip tiles, trade card and build alert slot.
  ACCEPT: npm test --prefix app and python -m pytest -q tests/test_play_fit.py tests/test_a11y.py
  tests/test_ux_review.py tests/test_trade_close.py tests/test_trade_expire.py
  tests/test_dash_console.py pass: web/index.html has no data-legacy group named g-tiles, t-trades
  or b-alert, web/trades.js and web/buildlive.js are gone, and the build-check upgrades still show
  in region U. ZERO-CLICK: Cleanup only; Play keeps updating from the state push. DEPENDS:
  PLAY-TD-10-STRIP, PLAY-TD-13-FEED, PLAY-TD-15-BUILDLINE, PLAY-TD-16B-KEPT-CHECKS. BLOCKED: session
  wave 10.
- [ ] TEST-GATE-CALLERS (build) One gate spelling in the loop, gates.txt, build.ps1 and /done; kit
  crash = retry. ACCEPT: python -m pytest -q tests/test_al_loop_kit_v13.py tests/test_loop_split.py
  tests/test_al_loop_gate_cache.py tests/test_supervisor.py tests/test_fleet_kit_conformance.py
  passes, python -m pytest -q tests/test_al_loop.py -k gate passes, and grep -c suite_run.py
  ops/loop/gates.txt scripts/build.ps1 .claude/commands/done.md prints at least 1 for each file.
  ZERO-CLICK: Automatic: the loop tick, build.ps1 and the done ritual call the one command; a kit
  crash is retried once by itself and logged. DEPENDS: TEST-SUITE-RUNNER, TEST-PLUGIN-PIN,
  TEST-WAVE-GATE-POLICY. BLOCKED: session wave 10.
- [ ] RUN-BUILD-STAMP-CORE (build) buildinfo.py: one build id for health, version and the report
  header. ACCEPT: python -m pytest -q tests/test_buildinfo.py tests/test_diag_self.py
  tests/test_http_security.py passes. ZERO-CLICK: Computed at start, shown everywhere, no setting.
  DEPENDS: RUN-SEAMS, RUN-TAIL-HEAL-CORE. BLOCKED: session wave 10.
- [ ] REL-RUNTIME-PINS (build) Runtime pin file and the hash-checked runtime fetch. ACCEPT: python
  -m pytest -q tests/test_runtime_pins.py tests/test_pinfetch.py tests/test_tc_pin.py passes.
  ZERO-CLICK: Fetched inside install by the installer's own process; nothing for the player to
  install; the running core never fetches a runtime. DEPENDS: DEP-01, REL-PINFETCH,
  OVL-ELECTRON-PIN. BLOCKED: session wave 10.
- [ ] OVL-WAKE-COMPANION (build) Bring the companion back when the game wakes, only on another
  display. ACCEPT: node --test app/test/client.test.js app/test/client_controls.test.js
  app/test/parts.test.js and python -m pytest -q tests/test_overlay_smoke.py pass. ZERO-CLICK:
  Automatic; one tray toggle opts out. No input, no focus steal, no process or window query of the
  game: the trigger is Client.txt freshness only (decision 0029). DEPENDS: OVL-MAIN-PARTS,
  OVL-LINKS-DOWNLOADS. BLOCKED: session wave 10.
- [ ] OVL-EGRESS-LOCK (build) Egress lock on both Electron sessions; no-network CSP for the icon
  render page. ACCEPT: node --test app/test/egress.test.js app/test/parts.test.js and python -m
  pytest -q tests/test_overlay_smoke.py tests/test_brand_assets.py tests/test_floor_static.py pass.
  ZERO-CLICK: Nothing for the player; one callback per request, no timer. DEPENDS: OVL-SHELL-GUARDS.
  BLOCKED: session wave 10.
- [ ] TEST-FLOOR-MEMO (build) Memoise the static floor scan. ACCEPT: python -m pytest -q
  tests/test_floor_static.py tests/test_floor_static_cache.py passes, test_floor_static.py still
  collects 35 ids, and its --durations=0 total is under 4 s on a quiet box. ZERO-CLICK: Runs in the
  suite and in every package subset (always-run list); no flag. BLOCKED: session wave 10.
- [ ] RUN-DIAG-DATA-AGE (build) Checks row when the game data is older than the game. ACCEPT: python
  -m pytest -q tests/test_diag_data_age.py tests/test_hud_act.py tests/test_diag_self.py passes.
  ZERO-CLICK: Shown by itself; the refresh is one build step. DEPENDS: RUN-SEAMS. BLOCKED: session
  wave 10.
- [ ] DEP-08 (build) Release build tool: the app zip, MANIFEST and BUILD. ACCEPT: python -m pytest
  -q tests/test_release_tool.py passes and python tools/release.py build --ref HEAD --out <tmp>
  twice gives the same SHA-256 for the zip. ZERO-CLICK: One command, no prompt, no upload. DEPENDS:
  DEP-03, DEP-04, DEP-06. BLOCKED: session wave 10.
- [ ] REL-INSTALL-HOME (build) Installer package: home, marker and the command table. ACCEPT: python
  -m pytest -q tests/test_install_home.py tests/test_install_paths.py passes and python -m
  server.al.install status exits 0 in a checkout with 'mode: checkout'. ZERO-CLICK: No player step:
  the marker is written and read by the installer and the launcher. DEPENDS: DEP-05,
  RUN-DURABLE-JSONFILE, SEC-ACL-APPLY. BLOCKED: session wave 10.
- [ ] OVL-COPY-FIRST (build) Empty clipboard at the item-check press shows a 'Copy the item first'
  card; one read per press stays under test + On the overlay card the item name stays on line 2
  unless a poe.ninja value exists. ACCEPT: python -m pytest -q tests/test_eval_text.py
  tests/test_tc_eval_api.py tests/test_price_text.py and node --test app/test/eval.test.js pass.
  Also (folded OVL-CARD-NAME): python -m pytest -q tests/test_price_text.py
  tests/test_price_check.py tests/test_trade_link.py tests/test_eval_text.py passes. ZERO-CLICK: The
  card shows by itself after the press; the player copies and presses again. No retry, no
  wait-for-change, no timer: one clipboard read per manual press. Also (folded OVL-CARD-NAME):
  Unchanged: the card shows and leaves by itself; the trade link stays a dashboard link the player
  opens. BLOCKED: session wave 10.

### Wave 11: install and release, theorycraft, tests and code seams

- [ ] TC-WORN-WIRE (build) 'I wear this' endpoint, worn-gear switch and clear. ACCEPT: python -m
  pytest -q tests/test_tc_worn_wire.py tests/test_ux_settings_io.py tests/test_floor_static.py
  tests/test_sidecar_paths.py tests/test_http_security.py passes. ZERO-CLICK: No new read: a worn
  item is filed by one press of the optional wear key (TC-WORN-KEY; the floor's one manual press per
  equipped item) or by the item-check press plus one 'I wear this' click (TD-16); after that every
  verdict follows by itself. DEPENDS: TC-WORN-BASELINE, SEC-SURFACE-PIN. BLOCKED: session wave 11.
- [ ] PLAY-LEGACY-OUT-2 (build) Legacy out 2: consent, guide, tip, language and item cards leave
  Play. ACCEPT: npm test --prefix app and python -m pytest -q tests/test_play_fit.py
  tests/test_a11y.py tests/test_ux_review.py tests/test_ux_b8.py tests/test_dash_console.py pass:
  web/index.html holds no data-legacy attribute, no pending marker is left for g, c-zone, c-setup,
  t, n, b, i or u, G1, G2, G4, G5, G6 and G9 hold in every state at the 5 cockpit sizes, and Play
  has at most 4 live regions. ZERO-CLICK: Cleanup only; nothing new to press. DEPENDS:
  PLAY-LEGACY-OUT-1, PLAY-TD-11-CONTEXT, PLAY-TD-12-CONTEXT-SETUP, PLAY-TD-14-NOTICE,
  PLAY-TD-16A-ITEMCARD, PLAY-TD-16B-KEPT-CHECKS. BLOCKED: session wave 11.
- [ ] TC-CALC-OPTIN (build) Calc opt-in in one act (setup switch). ACCEPT: python -m pytest -q
  tests/test_tc_pin.py tests/test_diag_self.py passes, npm test --prefix app passes, and
  powershell.exe 5.1 ParseFile accepts scripts/setup.ps1. ZERO-CLICK: One run of setup.ps1 -TcCalc
  (the decision 0018 opt-in) installs the calc and turns it on; no second edit of config/local.json.
  BLOCKED: session wave 11.
- [ ] REL-AUTOSTART-ENTRY (build) A logon launcher without VBScript. ACCEPT: python -m pytest -q
  tests/test_autostart.py tests/test_supervisor.py tests/test_floor_static.py passes and git
  ls-files scripts/autostart_launch.vbs prints nothing. ZERO-CLICK: Unchanged: autostart stays
  opt-in and OFF by default (decision 0011); when on, logon needs no click. DEPENDS: DEP-07,
  SEC-ACL-SETUP. BLOCKED: session wave 11.
- [ ] REL-SBOM (build) SBOM from the pins and the lockfile. ACCEPT: python -m pytest -q
  tests/test_sbom.py passes and python tools/sbom.py --commit HEAD --out <tmp>/sbom.json exits 0.
  ZERO-CLICK: Runs inside the release build and in CI on a tag; no player or operator step. DEPENDS:
  REL-RUNTIME-PINS, OVL-ELECTRON-PIN. BLOCKED: session wave 11.
- [ ] TEST-CAPTURE-HELPER (build) One capture helper under app/test/cdp/ and the wider floor-scan
  ban list. ACCEPT: python -m pytest -q tests/test_capture_helper.py tests/test_floor_static.py
  tests/test_dash_console.py tests/test_test_layout.py passes, including the plants that show a
  second capture call, desktopCapturer, capturePage or an OS screen grab anywhere outside the helper
  fails the floor scan. ZERO-CLICK: Unattended and hidden: headless browser, no window, below-normal
  priority; never the screen, never the game, never a game image. DEPENDS: TEST-FLOOR-MEMO,
  TEST-PORT-LEASE, TEST-LAYOUT-GUARD, SEC-DEMO-ENTRY. BLOCKED: session wave 11.
- [ ] REL-INSTALL-PAYLOAD (build) Installer package: verify and lay out the payload and the
  runtimes. ACCEPT: python -m pytest -q tests/test_install_payload.py tests/test_pinfetch.py passes.
  ZERO-CLICK: Runs inside the one pasted install line or an update; no extra step. DEPENDS:
  REL-INSTALL-HOME, DEP-06, DEP-08, REL-RUNTIME-PINS. BLOCKED: session wave 11.
- [ ] REL-INSTALL-SELFTEST (build) Installer package: self-test of a laid-out version. ACCEPT:
  python -m pytest -q tests/test_install_selftest.py passes. ZERO-CLICK: Runs by itself inside
  install and update; starts only while game_idle is true or on the player's click, so it never
  costs game FPS. DEPENDS: REL-INSTALL-HOME, DEP-06, SEC-DEMO-ENTRY. BLOCKED: session wave 11.
- [ ] DATA-PROVENANCE (data) A source and check date on every authored fact. ACCEPT: python -m
  pytest -q tests/test_provenance.py tests/test_zone_guide.py tests/test_zone_notes.py
  tests/test_waystone.py tests/test_util_campaign.py tests/test_hot_reload.py passes and python
  tools/provenance.py --before 2026-12-11 prints the re-verify list. ZERO-CLICK: The re-verify list
  is produced by a test or the loop; no player act. BLOCKED: session wave 11.
- [ ] RUN-HOTRELOAD-RETRY (build) Hot reload never pins a stale copy on a transient read error.
  ACCEPT: python -m pytest -q tests/test_hot_reload.py tests/test_diag_self.py passes. ZERO-CLICK:
  Fully automatic. DEPENDS: RUN-DURABLE-CRLF. BLOCKED: session wave 11.
- [ ] DEP-16 (build) In-app update notice: the release check client. ACCEPT: python -m pytest -q
  tests/test_updates.py passes. ZERO-CLICK: The check runs by itself once a day inside the web-data
  opt-in (wired in REL-UPDATE-WIRE); with web data off it makes zero requests. DEPENDS: DEP-03,
  DEP-04, DEP-05, RUN-BUILD-STAMP-CORE. BLOCKED: session wave 11.
- [ ] TEST-STATE-TEXT-2 (build) State text move 2: text/price.py and text/waystone.py. ACCEPT:
  python tools/state_equiv.py --ref <package base> prints 'state_equiv: identical' and python -m
  pytest -q tests/test_summarize.py tests/test_eval_text.py tests/test_price_text.py
  tests/test_trade_text.py tests/test_waystone.py tests/test_waystone_reward.py
  tests/test_build_live.py tests/test_ux_b6.py tests/test_design_gate.py tests/test_audit_pass2.py
  tests/test_math_compare.py tests/test_math_dps_sanity.py tests/test_math_weights.py
  tests/test_tc_delta.py passes. ZERO-CLICK: Developer-side only; the player does nothing. A running
  core in a source checkout reloads itself after the merge (decision 0042). DEPENDS: RUN-ZONE-RESET.
  BLOCKED: session wave 11.
- [ ] TEST-LOOP-SPLIT-MERGE (build) Loop tests split 1: merge, gates and dependency themes to
  tests/test_al_loop_merge.py. ACCEPT: python -m pytest -q tests/test_al_loop.py
  tests/test_al_loop_merge.py tests/test_test_layout.py passes and the two files together collect
  exactly the test ids tests/test_al_loop.py collected at the package base. ZERO-CLICK: Test-only;
  the suite picks the new file up by itself. DEPENDS: TEST-GATE-CALLERS, AUTO-01,
  LOOP-HANDOFF-PREFIX, LOOP-PREFLIGHT-CMD, LOOP-FAILED-PARK, LOOP-TESTS-CARVE, AUTO-21,
  TEST-LAYOUT-GUARD.

### Wave 12: install and release, overlay and client, theorycraft

- [ ] TEST-WEB-ASSEMBLE (build) Generate the dashboard's panel script and style tags at serve time.
  ACCEPT: python -m pytest -q tests/test_webpage.py tests/test_http_security.py tests/test_a11y.py
  tests/test_dash_console.py tests/test_hot_reload.py tests/test_floor_static.py passes. ZERO-CLICK:
  Developer-side only; the player does nothing. A new panel file is picked up by the core by itself,
  with no restart in a source checkout. DEPENDS: TEST-WEB-REGISTRY, TEST-WEB-SRCPATHS-PY. BLOCKED:
  session wave 12.
- [ ] PLAY-F-159-QUIET-BUTTON (build) Quiet base button, one filled button. ACCEPT: python -m pytest
  -q tests/test_ux_review.py tests/test_a11y.py tests/test_play_fit.py and npm test --prefix app
  pass: app.css has exactly one filled button rule (button.primary), the base button rule has a
  transparent background with a var(--al-control-edge) border, and the only button.primary in web/
  is the setup card's (web/setupcard.js). ZERO-CLICK: Styling only; nothing to press. DEPENDS:
  PLAY-LEGACY-OUT-2. BLOCKED: session wave 12.
- [ ] OVL-OBS-CRASH (build) OBS-CRASH: the core writes ops/runtime/last-exit.json on every exit
  path; Checks reads the core and client exit records. ACCEPT: python -m pytest -q
  tests/test_core_crash_log.py tests/test_diag_self.py tests/test_keepalive.py
  tests/test_supervisor.py tests/test_hot_reload.py passes. ZERO-CLICK: Automatic; the record is
  read by Checks with no click. BLOCKED: session wave 12.
- [ ] REL-INSTALL-SHELL (build) Installer package: shell entries and the first-run config. ACCEPT:
  python -m pytest -q tests/test_install_shell.py tests/test_shell_integration.py passes.
  ZERO-CLICK: No player step; the Client.txt opt-in and the web-data switch stay the player's own
  clicks on the first window (the floor's opt-in with its visible indicator). DEPENDS:
  REL-INSTALL-HOME, DEP-07, REL-AUTOSTART-ENTRY. BLOCKED: session wave 12.
- [ ] DATA-GUIDE-MERGE (data) One guide file: fold zone notes into zone_guide.json. ACCEPT: python
  -m pytest -q tests/test_zone_guide.py tests/test_util_campaign.py tests/test_util_10_fixtures.py
  tests/test_hot_reload.py tests/test_provenance.py tests/test_bus_state.py
  tests/test_floor_static.py passes and server/al/zonenotes.py and server/al/data/zone_notes.json no
  longer exist. ZERO-CLICK: Data only; the file hot-reloads (decision 0042) and the guide updates
  from the log. DEPENDS: DATA-PROVENANCE, DATA-PRICE-CARD-TEXT, DATA-LEAGUE-IDENTITY. BLOCKED:
  session wave 12.
- [ ] REL-AUTOSTART-TRAY (build) Autostart starts the client tray-only. ACCEPT: npm test --prefix
  app passes, python -m pytest -q tests/test_autostart.py tests/test_desktop_client.py passes, and a
  hidden tray-only run on a free port of the test lease range (ports.TEST_LEASE_PORTS, never
  AL_DEV_PORT 8961) with a fixture log writes its idle working set to <sidecar>/Logs/tray_idle.json
  at or under the 250 MB budget (else the fallback in notes is taken). ZERO-CLICK: One tick once
  (the opt-in); after that every logon starts AshLight with no click and no window. DEPENDS:
  REL-AUTOSTART-ENTRY, DEP-02. BLOCKED: session wave 12.
- [ ] OVL-NPM-LOCK (build) Lock npm down: tracked app/.npmrc, npm ci --ignore-scripts only, electron
  in dependencies. ACCEPT: python -m pytest -q tests/test_npm_lock.py tests/test_desktop_client.py
  tests/test_loop_inbox_p161.py tests/test_loop_inbox_p164.py passes and powershell.exe 5.1
  ParseFile accepts scripts/setup.ps1. ZERO-CLICK: No change for the player; setup stays one
  idempotent script. BLOCKED: session wave 12.
- [ ] PUB-README-PLAYERS (build) README quick start for players: shortcut, Stop, Update, Uninstall,
  Troubleshooting + README, SECURITY, CONTRIBUTING: how the repository is run. ACCEPT: `python -m
  pytest -q tests/test_public_docs.py tests/test_brand_assets.py tests/test_ascii_lf.py
  tests/test_leak_sweep.py` is green. Also (folded GP-07): `python -m pytest -q
  tests/test_public_docs.py tests/test_brand_assets.py tests/test_ascii_lf.py
  tests/test_leak_sweep.py` is green and `git grep -n "Once this repository is public" --
  SECURITY.md` prints nothing. ZERO-CLICK: Documentation only; nothing in play depends on it. The
  quick start it documents is two typed commands shorter: setup.ps1 writes the shortcut (starting
  from it is one click, said plainly), and the opt-in logon autostart of decision 0011 then starts
  AshLight with no click. Also (folded GP-07): Documentation only; nothing in play depends on it.
  DEPENDS: DEP-02. BLOCKED: session wave 12.
- [ ] TC-BRIDGE-NEXT (build) Bridge accepts the next PoB main-object shape. ACCEPT: python -m pytest
  -q tests/test_tc_pob_drift_guard.py tests/test_tc_bridge.py passes, and the new test proves both
  the local mainObject upvalue shape and the global __mainObject__ shape are accepted. ZERO-CLICK:
  Nothing for the player; the calc keeps working across the pin move. BLOCKED: session wave 12.
- [ ] TC-WEIGHTS-DELTA-STORE (build) Weights stored as the player's changes only. ACCEPT: python -m
  pytest -q tests/test_tc_weights_delta.py tests/test_tc_eval.py tests/test_tc_eval_api.py
  tests/test_eval_text.py passes. ZERO-CLICK: Migration and merge run at load; nothing to click.
  BLOCKED: session wave 12.
- [ ] LOOP-WATCH-GATE (build) Watcher web-data gate and URL check: tools/watch_gate.py. ACCEPT:
  `python -m pytest -q tests/test_watch_gate.py` passes, with 0 calls on the injected transport
  while web_data is off. ZERO-CLICK: Unattended: the gate is code in front of every watcher request;
  nobody switches it per run. BLOCKED: session wave 12.
- [ ] DEP-10 (build) Uninstall: stop, delete by fixed name, keep data unless -Purge. ACCEPT: python
  -m pytest -q tests/test_uninstall.py tests/test_supervisor.py tests/test_floor_static.py passes.
  ZERO-CLICK: One click in Apps and features; no question by default (data is kept). DEPENDS:
  DEP-05, DEP-07. BLOCKED: session wave 12.
- [ ] TEST-LOOP-SPLIT-LANES (build) Loop tests split 2: lane themes to tests/test_al_loop_lanes.py.
  ACCEPT: python -m pytest -q tests/test_al_loop.py tests/test_al_loop_merge.py
  tests/test_al_loop_lanes.py tests/test_test_layout.py passes and the three files together collect
  exactly the test ids the two files collected at the package base. ZERO-CLICK: Test-only; the suite
  picks the new file up by itself. DEPENDS: TEST-LOOP-SPLIT-MERGE.
- [ ] REL-INSTALL-CALC (build) Installer package: calc opt-in in an installed copy. ACCEPT: python
  -m pytest -q tests/test_install_calc.py tests/test_tc_pin.py passes. ZERO-CLICK: One command
  (later one button from the calc opt-in package); off by default (decision 0018). DEPENDS:
  REL-INSTALL-HOME, DEP-06, TC-CALC-OPTIN.

### Wave 13: loop and watchers, reliability and observability, theorycraft

- [ ] RUN-BUILD-STAMP-UI (build) Build id in the dashboard footer, overlay About and tray tooltip.
  ACCEPT: npm test --prefix app passes and python -m pytest -q tests/test_ux_review.py
  tests/test_a11y.py passes. ZERO-CLICK: Shown by itself; no setting. DEPENDS: RUN-BUILD-STAMP-CORE.
  BLOCKED: session wave 13.
- [ ] RUN-METRICS-CORE (build) Own counters: metrics.py and the token-gated GET /api/debug. ACCEPT:
  python -m pytest -q tests/test_metrics.py tests/test_http_security.py tests/test_budgets.py
  passes. ZERO-CLICK: Counted by the core by itself; nothing for the player. The probe command is
  RUN-METRICS-PROBE. DEPENDS: RUN-SEAMS, RUN-BUILD-STAMP-CORE, RUN-TAIL-HEAL-READER. BLOCKED:
  session wave 13.
- [ ] DATA-SNAP-AT-START (build) Game data arrives at start: the supervisor runs the snapshot tool
  hidden. ACCEPT: python -m pytest -q tests/test_snap_start.py tests/test_supervisor.py
  tests/test_keepalive.py tests/test_tc_snap.py tests/test_diag_self.py passes. ZERO-CLICK: Nothing
  beyond the one 'Use web data' tick: the data is there at the next start, and within one supervisor
  poll when the tick happens while AshLight runs. BLOCKED: session wave 13.
- [ ] PLAY-TD-08B-GUIDE-SHORT-TEXT (data) Zone guide short lines: author the 93 entries. ACCEPT:
  python -m pytest -q tests/test_zone_guide.py passes with every non-empty short at most 34 ASCII
  characters; the package result lists the filled and empty counts. ZERO-CLICK: Data only; the guide
  file hot-reloads on a new mtime (decision 0042). DEPENDS: PLAY-TD-08A-GUIDE-SHORT-FIELD,
  DATA-GUIDE-MERGE. BLOCKED: session wave 13.
- [ ] TEST-STATE-TEXT-3 (build) State text move 3: text/itemcheck.py. ACCEPT: python
  tools/state_equiv.py --ref <package base> prints 'state_equiv: identical' and python -m pytest -q
  tests/test_summarize.py tests/test_eval_text.py tests/test_price_text.py tests/test_trade_text.py
  tests/test_waystone.py tests/test_waystone_reward.py tests/test_build_live.py tests/test_ux_b6.py
  tests/test_design_gate.py tests/test_audit_pass2.py tests/test_math_compare.py
  tests/test_math_dps_sanity.py tests/test_math_weights.py tests/test_tc_delta.py passes.
  ZERO-CLICK: Developer-side only; the player does nothing. A running core in a source checkout
  reloads itself after the merge (decision 0042). DEPENDS: TEST-STATE-TEXT-2. BLOCKED: session wave
  13.
- [ ] OVL-ELECTRON-SETUP (build) Electron pin wired into setup and run: override variables cleared,
  install.js replaced, electron.exe verified. ACCEPT: python -m pytest -q tests/test_electron_pin.py
  tests/test_npm_lock.py tests/test_desktop_client.py tests/test_run_detach.py passes and
  powershell.exe 5.1 ParseFile accepts scripts/setup.ps1 and scripts/run.ps1. ZERO-CLICK: Runs
  inside setup and run with no prompt; a failed check names the fix (run setup again). DEPENDS:
  OVL-NPM-LOCK, OVL-ELECTRON-PIN. BLOCKED: session wave 13.
- [ ] AUTO-12 (build) TC-DRIFT-TRIAL-FIX (part 1): re-hash pob2_files from the candidate; prune old
  candidates. ACCEPT: `python -m pytest -q tests/test_tc_drift.py` passes with fakes proving both
  parts. ZERO-CLICK: The static tier is unattended; the live tier and the pin move stay session acts
  (decision 0025). DEPENDS: TC-BRIDGE-NEXT. BLOCKED: session wave 13.
- [ ] TC-CALC-CONFINE-PROC (build) Confine the calc child process. ACCEPT: python -m pytest -q
  tests/test_tc_bridge.py tests/test_tc_wire.py passes. ZERO-CLICK: Automatic: every calc start is
  confined; the player does nothing. DEPENDS: TC-BRIDGE-NEXT. BLOCKED: session wave 13.
- [ ] AUTO-05 (build) WATCH-CORE frame: tools/upstream_watch.py registry, state, cadence, web-data
  gate. ACCEPT: `python -m pytest -q tests/test_upstream_watch.py` passes, with a gated source
  making 0 requests on the injected transport while web_data is off. ZERO-CLICK: Fully unattended:
  the tick calls it every 15 minutes (LOOP-WATCH-WIRE); nothing is ever remembered by a person.
  DEPENDS: LOOP-WATCH-GATE. BLOCKED: session wave 13.
- [ ] LOOP-WATCH-ROWS (build) Watcher row templates: one validated table folder and a renderer.
  ACCEPT: `python -m pytest -q tests/test_watch_rows.py` passes. ZERO-CLICK: Unattended: templates
  are data; a new source adds a file and the tick reads it. BLOCKED: session wave 13.
- [ ] REL-UNINSTALL-SHELL (build) Uninstall: logon task, shortcuts and the uninstall key. ACCEPT:
  python -m pytest -q tests/test_uninstall.py tests/test_supervisor.py passes. ZERO-CLICK: Same
  single click; nothing asked. DEPENDS: DEP-10, REL-AUTOSTART-ENTRY. BLOCKED: session wave 13.
- [ ] TC-UPGRADE-PER-SLOT (build) Trade-search link on every 'Look for next' row. ACCEPT: python -m
  pytest -q tests/test_tc_upgrade.py tests/test_math_build_health.py tests/test_trade_link.py
  tests/test_floor_static.py passes and npm test --prefix app passes. ZERO-CLICK: Links rebuild with
  the build; opening one is the player's click (decision 0017). DEPENDS: TC-WORN-WIRE. BLOCKED:
  session wave 13.
- [ ] TEST-LOOP-GIT-TEMPLATE (build) git_world from a session-scoped template copy. ACCEPT: python
  -m pytest -q tests/test_al_loop.py tests/test_al_loop_merge.py tests/test_al_loop_lanes.py
  tests/test_al_loop_gate_cache.py tests/test_al_loop_routes.py passes with the same collected ids
  as the package base. ZERO-CLICK: Test-only. DEPENDS: TEST-LOOP-SPLIT-LANES.

### Wave 14: reliability and observability, install and release, theorycraft

- [ ] PLAY-TD-19B-FOUR-TABS (build) Four tabs: Play, Build and items, Run, Settings. ACCEPT: npm
  test --prefix app and python -m pytest -q tests/test_a11y.py tests/test_ux_review.py
  tests/test_ux_b8.py tests/test_dash_console.py pass: the page has exactly 4 role=tab elements
  named Play, Build and items, Run, Settings, a stored items tab maps once to build, and news still
  shows Play with no act. ZERO-CLICK: Play still shows by itself; nothing new to press. DEPENDS:
  PLAY-LEGACY-OUT-2, PLAY-F-159-QUIET-BUTTON. BLOCKED: session wave 14.
- [ ] OVL-KEYS-CORE (build) Hotkeys in the core: effective keys in the snapshot, POST /api/hotkeys,
  Checks rows for both chords. ACCEPT: python -m pytest -q tests/test_hotkeys_live.py
  tests/test_diag_self.py tests/test_audit_pass5_low.py tests/test_http_security.py
  tests/test_ux_settings_io.py passes. ZERO-CLICK: The core reads the client's runtime file by
  itself (stat-gated, inside tick_diag); changing a key is optional. DEPENDS: OVL-KEYS-CLIENT,
  SEC-SURFACE-PIN. BLOCKED: session wave 14.
- [ ] RUN-BUDGET-LOG-CORE (build) Budget log: the core records its own footprint once a minute.
  ACCEPT: python -m pytest -q tests/test_budget_log.py tests/test_floor_static.py
  tests/test_sidecar_paths.py passes. ZERO-CLICK: Automatic; the operator only plays. DEPENDS:
  RUN-METRICS-CORE. BLOCKED: session wave 14.
- [ ] RUN-BUDGET-LOG-CLIENT (build) Client samples its own Electron processes once a minute. ACCEPT:
  npm test --prefix app passes and python -m pytest -q tests/test_floor_static.py
  tests/test_overlay_layout.py passes. ZERO-CLICK: Automatic. DEPENDS: RUN-BUILD-STAMP-UI. BLOCKED:
  session wave 14.
- [ ] REL-INSTALL-CMD (build) Installer package: install and repair commands. ACCEPT: python -m
  pytest -q tests/test_installer.py tests/test_install_home.py tests/test_install_payload.py
  tests/test_install_selftest.py tests/test_install_shell.py passes. ZERO-CLICK: One pasted line,
  then the app opens; no elevation prompt, no second step; the floor's Client.txt opt-in (with its
  visible indicator) and the web-data switch stay the player's own clicks on the first window.
  DEPENDS: REL-INSTALL-PAYLOAD, REL-INSTALL-SELFTEST, REL-INSTALL-SHELL, DATA-SNAP-AT-START.
  BLOCKED: session wave 14.
- [ ] REL-AUTOSTART-SWITCH (build) 'Start with Windows' in the tray menu. ACCEPT: npm test --prefix
  app passes and python -m pytest -q tests/test_overlay_smoke.py tests/test_floor_static.py passes.
  ZERO-CLICK: One tick once in the tray menu; no terminal, no typed command. DEPENDS:
  REL-AUTOSTART-TRAY. BLOCKED: session wave 14.
- [ ] AUTO-14 (build) DOCS-FRESH: tools/docs_fresh.py check, with the code-pin facts. ACCEPT: python
  -m pytest -q tests/test_docs_fresh.py tests/test_brand_assets.py passes and python
  tools/docs_fresh.py check exits 0 on the tree and exits 1 naming app/main.js and
  docs/decisions/0002-stack.md when run with --root on a copy whose app/package.json Electron pin
  was changed. ZERO-CLICK: Unattended: the check runs as a test in every suite; a bump lane sees the
  stale file named and fixes it in the same change. DEPENDS: DEP-03, PUB-README-PLAYERS. BLOCKED:
  session wave 14.
- [ ] TC-CALC-VERIFY-PIN (build) Pin contents, not bytes. ACCEPT: python -m pytest -q
  tests/test_tc_pin.py tests/test_tc_drift.py passes. ZERO-CLICK: Automatic; the one manual act
  stays the -TcCalc opt-in. DEPENDS: TC-CALC-OPTIN, AUTO-12. BLOCKED: session wave 14.
- [ ] TC-CALC-CONFINE-LUA (build) Drop dangerous Lua entry points after PoB loads. ACCEPT: python -m
  pytest -q -rs tests/test_tc_bridge.py tests/test_tc_pob_drift_guard.py passes on the dev host
  (calc component installed) and its -rs summary lists no skipped live row. ZERO-CLICK: Automatic:
  every calc start runs the lockdown; the player does nothing. DEPENDS: TC-BRIDGE-NEXT,
  TC-CALC-CONFINE-PROC. BLOCKED: session wave 14.
- [ ] AUTO-11 (build) DOCS-SHAPE: a 'shape' topic in the GGG docs watch. ACCEPT: `python -m pytest
  -q tests/test_ggg_docs_watch.py` passes. ZERO-CLICK: Runs on the loop tick, also while HALTed; no
  new request. BLOCKED: session wave 14.
- [ ] DATA-TREE-HOLD (build) Keep the previous passive tree and resolve each build against the best
  match. ACCEPT: python -m pytest -q tests/test_tc_tree.py tests/test_tc_tree_ids.py
  tests/test_tc_snap.py tests/test_tc_buildfile.py tests/test_audit_buildfile.py passes. ZERO-CLICK:
  The choice is made per build with no setting. DEPENDS: DATA-SNAP-AT-START. BLOCKED: session wave
  14.
- [ ] LOOP-ELECTRON-POLICY (build) Electron upgrade policy decision; setup refuses the npm step
  while the client runs. ACCEPT: `python -m pytest -q tests/test_setup_client_guard.py
  tests/test_ascii_lf.py` passes. ZERO-CLICK: A dev step that guards itself: while AshLight's client
  is live, setup.ps1 ends with a one-line reason before npm runs; the bump row stays open and a
  later tick's lane run retries it; the player sees nothing. BLOCKED: session wave 14.
- [ ] REL-UNINSTALL-CHECKOUT (build) Uninstall: checkout mode. ACCEPT: python -m pytest -q
  tests/test_uninstall.py tests/test_sidecar_paths.py passes. ZERO-CLICK: One command; -Purge is the
  only consent asked. DEPENDS: REL-UNINSTALL-SHELL.
- [ ] RUN-METRICS-PROBE (build) python -m server.al.probe: one line per item, exit 0 live, 1
  stopped. ACCEPT: python -m pytest -q tests/test_probe.py tests/test_sidecar_paths.py passes.
  ZERO-CLICK: A session or a lane runs the one command; nothing for the player. Wiring it into
  session start and the lanes is the LOOP cluster's. DEPENDS: RUN-METRICS-CORE.
- [ ] TEST-LOOP-STUB-GIT (build) Stub git runner for the tick tests that do not test git. ACCEPT:
  python -m pytest -q --durations=0 tests/test_al_loop.py tests/test_al_loop_merge.py
  tests/test_al_loop_lanes.py passes with the same collected ids, each file's total under 20 s, and
  with AL_GIT_COUNT=1 the run prints a git spawn count under 700. ZERO-CLICK: Test-only. DEPENDS:
  TEST-LOOP-GIT-TEMPLATE.

### Wave 15: loop and watchers, reliability and observability, theorycraft

- [ ] RUN-METRICS-SITES (build) Counter call sites: fetches per host, calc starts and time-outs,
  press outcome + Own consent line for the parse ledger (consent key, route flag, dashboard line).
  ACCEPT: python -m pytest -q tests/test_metrics.py tests/test_data_ninja.py tests/test_tc_bridge.py
  tests/test_tc_eval_api.py passes. Also (folded RUN-LEDGER-CONSENT): python -m pytest -q
  tests/test_ledger_consent.py tests/test_http_security.py tests/test_a11y.py passes and npm test
  --prefix app passes. ZERO-CLICK: Automatic. Also (folded RUN-LEDGER-CONSENT): One Allow click on
  the new consent line, once, in the dashboard outside play; nothing in play. DEPENDS:
  RUN-METRICS-CORE, RUN-TAIL-HEAL-CORE, RUN-LEDGER-CORE, RUN-BUILD-STAMP-UI. BLOCKED: session wave
  15.
- [ ] TC-WORN-KEY (build) Optional wear key (unset by default). ACCEPT: npm test --prefix app passes
  and python -m pytest -q tests/test_floor_static.py tests/test_ux_settings_io.py passes.
  ZERO-CLICK: One manual press per equipped item, only for a player who sets the key; the floor
  minimum for a clipboard read. DEPENDS: TC-WORN-WIRE, TC-PRESS-BUILD, OVL-KEYS-CORE. BLOCKED:
  session wave 15.
- [ ] DEP-11 (build) Update from a local zip: verify, build beside, self-test, stage. ACCEPT: python
  -m pytest -q tests/test_updater.py tests/test_installer.py passes. ZERO-CLICK: With web data off:
  a re-run of the pasted line or 'install.ps1 -Zip' upgrades in place; no other step. DEPENDS:
  REL-INSTALL-CMD. BLOCKED: session wave 15.
- [ ] PLAY-TD-22B-TAB-FOCUS (build) Auto-return to Play keeps focus where the user is. ACCEPT: node
  --test app/test/tabs.test.js passes: the automatic return never fires within 10 s of a key press
  in the tab row, moves focus to the Play tab only when focus sat on the tab row, never moves a
  focus inside a panel, and writes Showing Play. <what>. once to the polite header line. ZERO-CLICK:
  News for Play still shows Play with no act; a card, trade or notice never moves focus. DEPENDS:
  PLAY-TD-19B-FOUR-TABS. BLOCKED: session wave 15.
- [ ] TEST-STATE-TEXT-4 (build) State text move 4: text/buildlive.py and text/overlaycard.py.
  ACCEPT: python tools/state_equiv.py --ref <package base> prints 'state_equiv: identical' and
  python -m pytest -q tests/test_summarize.py tests/test_eval_text.py tests/test_price_text.py
  tests/test_trade_text.py tests/test_waystone.py tests/test_waystone_reward.py
  tests/test_build_live.py tests/test_ux_b6.py tests/test_design_gate.py tests/test_audit_pass2.py
  tests/test_math_compare.py tests/test_math_dps_sanity.py tests/test_math_weights.py
  tests/test_tc_delta.py passes. ZERO-CLICK: Developer-side only; the player does nothing. A running
  core in a source checkout reloads itself after the merge (decision 0042). DEPENDS:
  TEST-STATE-TEXT-3. BLOCKED: session wave 15.
- [ ] OVL-LAUNCH-ENV (build) Launcher runs tools by absolute path; the client starts without
  ELECTRON_RUN_AS_NODE and NODE_OPTIONS. ACCEPT: node --test app/test/client.test.js and python -m
  pytest -q tests/test_audit_exe_path.py tests/test_run_detach.py tests/test_desktop_client.py pass,
  and powershell.exe 5.1 ParseFile accepts scripts/run.ps1 and scripts/al_detach.ps1. ZERO-CLICK:
  Nothing for the player; the launcher still starts only the repo's own scripts. DEPENDS:
  OVL-ELECTRON-SETUP. BLOCKED: session wave 15.
- [ ] TEST-DOCS-INDEX (build) docs_fresh.py: stale markers, index --write, every decision and
  research file indexed. ACCEPT: python -m pytest -q tests/test_docs_index.py
  tests/test_docs_fresh.py passes and python tools/docs_fresh.py index --check exits 0 on the tree.
  ZERO-CLICK: Unattended: the check is a test; the REL-PREP lane and the refresh watcher (AUTO-17)
  run index --write and stale by themselves. DEPENDS: AUTO-14, LOOP-LEDGERS. BLOCKED: session wave
  15.
- [ ] LOOP-WATCH-FILE (build) The two row primitives and the unattended add-only commit path (Q-12).
  ACCEPT: `python -m pytest -q tests/test_watch_file.py` passes in a scratch repository, with every
  commit made through the injected kit git lock and naming exactly one path under docs/roadmap/new/
  or docs/roadmap/done/. ZERO-CLICK: Fully unattended: a watcher finding becomes a row the loop
  works, with no reminder and no hand edit. DEPENDS: AUTO-03, AUTO-05, LOOP-WATCH-ROWS. BLOCKED:
  session wave 15.
- [ ] DEP-13 (build) Cut-over tooling: migrate player data from a checkout. ACCEPT: python -m pytest
  -q tests/test_migrate.py tests/test_install_home.py passes. ZERO-CLICK: One command inside the
  cut-over; no player step (players start fresh). DEPENDS: REL-INSTALL-CMD. BLOCKED: session wave
  15.
- [ ] LOOP-WATCH-META (build) Watch sources: repoe-fork data and the GGG passive tree export
  (metadata only). ACCEPT: `python -m pytest -q tests/test_watch_meta.py` passes. ZERO-CLICK:
  Unattended: the snapshot itself still refreshes only at build or client start (decision 0009 as
  amended), never from the loop. DEPENDS: AUTO-05. BLOCKED: session wave 15.
- [ ] LOOP-WATCH-SETTLED (build) The GGG docs watch and the PoB release check as registry sources.
  ACCEPT: `python -m pytest -q tests/test_watch_settled.py tests/test_watch_rows.py
  tests/test_tc_drift.py tests/test_ggg_docs_watch.py` passes. ZERO-CLICK: Unattended: the two
  settled reads keep running every tick with their own throttle; their findings become rows with no
  hand edit. DEPENDS: AUTO-05, LOOP-WATCH-ROWS, AUTO-11. BLOCKED: session wave 15.
- [ ] TC-GGG-RATELIMIT (build) Header-driven rate limiter. ACCEPT: python -m pytest -q
  tests/test_ratelimit.py passes. ZERO-CLICK: Dev step: a pure module proven by its unit tests; it
  makes no request and nothing runs in play until TC-GGG-CLIENT-CORE uses it. BLOCKED: session wave
  15.
- [ ] RUN-SETTINGS-TRIM-DOCS (review) Drop four tuning keys from the player docs. ACCEPT: grep -c -E
  'poll_ms|underlevel_gap|price_watch_pct|boots_speed_level' README.md config/local.example.json
  prints 0 for both and python -m pytest -q tests/test_ascii_lf.py tests/test_research_numbers.py
  tests/test_leak_sweep.py passes. ZERO-CLICK: Docs-only edit applied by the lane; the player reads
  four keys fewer; nothing to click. DEPENDS: PUB-README-PLAYERS. BLOCKED: session wave 15.

### Wave 16: theorycraft, loop and watchers, reliability and observability

- [ ] OVL-KEYS-WEB (build) Dashboard prints the real keys, one change-key field per chord, one Play
  line while the overlay is off. ACCEPT: node --test app/test/hotkeys_view.test.js
  app/test/prices.test.js and python -m pytest -q tests/test_ux_review.py tests/test_ux_b8.py
  tests/test_newbie_hints.py tests/test_a11y.py pass, and git grep -n -F "Alt+Shift+" -- web
  server/al/hints.py prints nothing. ZERO-CLICK: The keys shown follow the registration by
  themselves; rebinding is one optional field, saved on change. DEPENDS: OVL-KEYS-CORE. BLOCKED:
  session wave 16.
- [ ] RUN-LEDGER-WIRE (build) Wire the ledger: feed_line hook, write tick, drift note, read-back
  flags, waystone shape. ACCEPT: python -m pytest -q tests/test_ledger_wire.py
  tests/test_ledger_consent.py tests/test_budgets.py passes. ZERO-CLICK: After the one consent click
  (RUN-LEDGER-CONSENT (folded into RUN-METRICS-SITES)) the ledger fills in normal play by itself.
  DEPENDS: RUN-METRICS-SITES. BLOCKED: session wave 16.
- [ ] RUN-OBS-LOGS-PY (build) Python logs bounded, one format, a banner per start, faulthandler on
  its own file + Heavy child processes start below normal priority. ACCEPT: python -m pytest -q
  tests/test_logs.py tests/test_core_crash_log.py tests/test_keepalive.py tests/test_tc_bridge.py
  passes. Also (folded RUN-CALC-PRIORITY): python -m pytest -q tests/test_tc_bridge.py
  tests/test_keepalive.py tests/test_tc_drift.py tests/test_ascii_lf.py passes. ZERO-CLICK: At
  start, by itself. Also (folded RUN-CALC-PRIORITY): Automatic. DEPENDS: RUN-BUILD-STAMP-CORE,
  RUN-DURABLE-CRLF, RUN-METRICS-SITES. BLOCKED: session wave 16.
- [ ] TC-CALC-OPTIN-BUTTON (build) 'Set up the Path of Building calc' button in the client. ACCEPT:
  npm test --prefix app passes. ZERO-CLICK: One click, the decision 0018 opt-in; setup then runs and
  reports by itself. DEPENDS: TC-CALC-OPTIN, TC-WORN-KEY, OVL-KEYS-CLIENT. BLOCKED: session wave 16.
- [ ] REL-UPDATE-SWITCH (build) Update: apply-staged, confirm and rollback. ACCEPT: python -m pytest
  -q tests/test_update_switch.py tests/test_updater.py tests/test_install_shell.py passes.
  ZERO-CLICK: Applied at the next client start by itself; rollback needs no click. DEPENDS: DEP-11,
  REL-INSTALL-SHELL. BLOCKED: session wave 16.
- [ ] TC-GGG-LISTENER (build) One-shot loopback listener for the OAuth redirect. ACCEPT: python -m
  pytest -q tests/test_oauthlisten.py tests/test_port_resolve.py tests/test_floor_static.py passes.
  ZERO-CLICK: Dev step: offline module proven by its tests; nothing listens in play until TC-IMPORT
  wires it. BLOCKED: session wave 16.
- [ ] DATA-GUIDE-BOSS (data) Boss elements move from campaign.BOSS_ZONES into the guide file.
  ACCEPT: python -m pytest -q tests/test_util_campaign.py tests/test_zone_guide.py
  tests/test_provenance.py tests/test_bus_state.py tests/test_hot_reload.py passes and python -c
  "import server.al.campaign as c; assert not hasattr(c, 'BOSS_ZONES')" exits 0. ZERO-CLICK: Data
  only; the guide file hot-reloads (decision 0042) and the boss hint follows the log with no click.
  DEPENDS: DATA-GUIDE-MERGE. BLOCKED: session wave 16.
- [ ] LOOP-USAGE-LABEL (build) The row id reaches the lane's usage line. ACCEPT: `python -m pytest
  -q tests/test_lane_usage_label.py tests/test_al_lane.py tests/test_al_lane_sidecar.py
  tests/test_p163_lane_tools.py` passes. ZERO-CLICK: Unattended: every lane run labels its own usage
  line; nobody tags runs by hand. BLOCKED: session wave 16.
- [ ] TEST-DOCS-FACTS-UI (build) docs_fresh.py: hotkeys, budgets, settings keys and tab names.
  ACCEPT: python -m pytest -q tests/test_docs_fresh.py passes and python tools/docs_fresh.py check
  exits 0 on the tree. ZERO-CLICK: Unattended: runs as a test; a package that renames a tab or moves
  a hotkey sees README named as stale in its own subset. DEPENDS: TEST-DOCS-INDEX. BLOCKED: session
  wave 16.
- [ ] AUTO-09 (build) ELECTRON-WATCH sources: releases, schedule and npm audit. ACCEPT: `python -m
  pytest -q tests/test_watch_electron.py tests/test_watch_rows.py` passes. ZERO-CLICK: Unattended:
  the only exposure that grows by itself is watched daily and turns into a row the loop works.
  DEPENDS: AUTO-05, LOOP-WATCH-ROWS, LOOP-ELECTRON-POLICY. BLOCKED: session wave 16.
- [ ] TC-CHARJSON-SHAPES (build) charjson reads the item shapes GGG documents today. ACCEPT: python
  -m pytest -q tests/test_tc_json.py tests/test_tc_code_api.py passes with a new both-shapes fixture
  in tests/tc_fixtures.py. ZERO-CLICK: Same paste path, no new press. BLOCKED: session wave 16.
- [ ] AUTO-07 (build) LAUNCH-GATE: the 1.0 rows open by themselves (due 2026-12-04). ACCEPT: `python
  -m pytest -q tests/test_watch_launch.py tests/test_watch_rows.py` passes, driven end to end with a
  fake clock from a source record to a committed done file in a scratch repository. ZERO-CLICK:
  Unattended, bar the operator's own play session that the floor requires of a log read: the gate
  flips on a tick and the dependent rows are dispatched. DEPENDS: AUTO-03, AUTO-05, LOOP-WATCH-ROWS,
  LOOP-WATCH-FILE, LOOP-WATCH-META, AUTO-04. BLOCKED: session wave 16.
- [ ] SEC-CEIL-WEBFETCH (build) A total deadline per outbound request. ACCEPT: python -m pytest -q
  tests/test_webfetch_deadline.py tests/test_data_ninja.py tests/test_tc_url.py passes: a fake
  response object yielding one byte a second raises FetchError at the total deadline with an
  injected clock. ZERO-CLICK: Code change; opt-in, User-Agent and host lists do not change. DEPENDS:
  RUN-METRICS-SITES.

### Wave 17: go-public, theorycraft, tests and code seams

- [ ] PLAY-TD-19C-BUILD-GRID (build) Build and items grid 1: Build, Health and next, Search strings.
  ACCEPT: npm test --prefix app and python -m pytest -q tests/test_play_fit.py tests/test_a11y.py
  tests/test_ux_b6.py tests/test_ux_b8.py tests/test_dash_console.py pass: the Build, Health and
  next and Search strings cards are 3 cells of the 3 x 2 grid, each list pages at 10 rows (8
  compact), and no element inside the three cards has scrollHeight above clientHeight at the 5
  cockpit sizes. ZERO-CLICK: Cards fill when a build loads; paging is optional and outside play.
  DEPENDS: PLAY-TD-19B-FOUR-TABS, PLAY-TD-19A-PAGER. BLOCKED: session wave 17.
- [ ] OVL-TD05-LEGIBILITY (build) Overlay legibility recipe and two type sizes in the overlay CSS
  (TD-05, part 1). ACCEPT: python -m pytest -q tests/test_design_contrast.py tests/test_ux_review.py
  tests/test_overlay_smoke.py tests/test_design_gate.py and node --test
  app/test/overlay_gate.test.js pass, and git grep -n -E "html *[{] *opacity" --
  app/overlay/overlay.css prints nothing. ZERO-CLICK: Applies at the next overlay start; nothing
  reads the screen to adapt the plate. DEPENDS: OVL-KEYS-WEB, OVL-GLANCE-RULES, PLAY-TD-03-TOKENS,
  PLAY-TD-04A-DARK-CLIENT. BLOCKED: session wave 17.
- [ ] DATA-CONTACT-FIELD (build) Contact value: a write-only POST and its core setter + Prices
  refresh from the core loop, not the visible page. ACCEPT: python -m pytest -q
  tests/test_contact_field.py tests/test_diag_self.py tests/test_data_ninja.py
  tests/test_ux_settings_io.py tests/test_http_security.py passes. Also (folded
  DATA-PRICE-REFRESH-CORE): python -m pytest -q tests/test_price_refresh.py tests/test_data_ninja.py
  tests/test_price_book.py tests/test_sse_idle_push.py passes. ZERO-CLICK: One typed value, once per
  install (an identity cannot be guessed); after it the price refresh starts by itself (set_contact
  calls rates.refresh_async). Also (folded DATA-PRICE-REFRESH-CORE): Automatic: right prices in
  overlay-only play, no request while nobody plays. BLOCKED: session wave 17.
- [ ] REL-CLIENT-HOME (build) Installed-mode paths in the Electron client. ACCEPT: npm test --prefix
  app passes and python -m pytest -q tests/test_install_paths.py tests/test_overlay_smoke.py
  tests/test_port_resolve.py passes. ZERO-CLICK: Resolved by itself at client start; no setting, no
  click. DEPENDS: DEP-05. BLOCKED: session wave 17.
- [ ] TC-CALC-VERIFY-USE (build) Verify the calc component at each start. ACCEPT: python -m pytest
  -q tests/test_tc_bridge.py tests/test_tc_wire.py passes; tests/test_math_perf.py passes on a host
  with the component. ZERO-CLICK: Automatic; a changed component shows one Checks line naming the
  fix. DEPENDS: TC-CALC-VERIFY-PIN, TC-CALC-CONFINE-LUA, TC-CALC-CONFINE-PROC. BLOCKED: session wave
  17.
- [ ] AUTO-15 (build) SHOTS: tools/shots.py render and check, the manifest, the lane tool grant.
  ACCEPT: python -m pytest -q tests/test_shots.py tests/test_p163_lane_tools.py
  tests/test_sidecar_paths.py tests/test_floor_static.py passes and python tools/shots.py check
  exits 0 or 1 without starting a browser. ZERO-CLICK: Unattended, hidden, below-normal priority:
  the lane or the refresh source (AUTO-17) runs render and check; no window appears and the player
  does nothing. DEPENDS: TEST-CAPTURE-HELPER, SEC-DEMO-ENTRY. BLOCKED: session wave 17.
- [ ] TEST-TIMER-FIXES (build) Small timer fixes in five test files. ACCEPT: python -m pytest -q
  tests/test_keepalive.py tests/test_procs.py tests/test_audit_pass5.py tests/test_cover_gaps.py
  passes three times in a row, python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python
  -m pytest -q tests/test_budgets.py passes, and grep -c 13388 tests/test_keepalive.py prints 0.
  ZERO-CLICK: Test-only; runs in the suite. DEPENDS: TEST-PORT-LEASE, TEST-MARKS. BLOCKED: session
  wave 17.
- [ ] TC-GGG-CLIENT-CORE (build) Offline core of a GGG OAuth client. ACCEPT: python -m pytest -q
  tests/test_gggapi.py tests/test_floor_static.py passes. ZERO-CLICK: Dev step: offline module
  proven by its tests with an injected transport; nothing runs in play until TC-IMPORT wires it, and
  no request is possible without a client id. DEPENDS: TC-GGG-RATELIMIT, TC-GGG-LISTENER,
  DATA-GGG-APPLICATION. BLOCKED: session wave 17.
- [ ] LOOP-WATCH-WIRE (build) Wire the watcher into the tick in front of HALT; file pending findings
  after the work list. ACCEPT: `python -m pytest -q tests/test_watch_wire.py tests/test_al_loop.py
  tests/test_loop_steps.py tests/test_watch_settled.py` passes. ZERO-CLICK: Fully unattended: drift
  is seen while HALT stands and acted on the first tick after it goes. DEPENDS: AUTO-01, AUTO-05,
  LOOP-WATCH-FILE, LOOP-WATCH-SETTLED. BLOCKED: session wave 17.
- [ ] GP-14 (data) Dependabot re-apply tool: list, close and the run loop. ACCEPT: `python -m pytest
  -q tests/test_dependabot_reapply.py tests/test_p163_lane_tools.py tests/test_ascii_lf.py
  tests/test_leak_sweep.py` is green. ZERO-CLICK: `python tools/dependabot_reapply.py run` handles
  every open bump with no prompt; a session runs it until the loop resumes (F-078), then the tick
  does (PUB-DEPBOT-TICK). BLOCKED: session wave 17.
- [ ] PUB-SWEEP-OWN-ADDRESS (build) Leak sweep: allow exactly the project's own repository address.
  ACCEPT: `python -m pytest -q tests/test_leak_sweep.py` is green and `python tools/leak_sweep.py
  --tree` exits 0 with no config/public_repo.json in the tree. ZERO-CLICK: Runs by itself in
  pre-commit, commit-msg, pre-push and CI; no value is typed until GP-10 writes the address once.
  BLOCKED: session wave 17.
- [ ] PUB-SOCIAL-CARD (build) Own-art social preview card. ACCEPT: `python -m pytest -q
  tests/test_brand_assets.py tests/test_ascii_lf.py` is green and `python tools/make_icons.py check`
  exits 0 printing `make_icons: check ok`. ZERO-CLICK: A dev step that runs itself (the icon tool
  renders and checks); the card holds only AshLight's own drawn strokes, no font, no game art.
  BLOCKED: session wave 17.
- [ ] TC-ASC-FROM-TREE (build) Ascendancy names from the cached tree export. ACCEPT: python -m
  pytest -q tests/test_build_live.py tests/test_util_10_ready.py tests/test_tc_tree.py passes.
  ZERO-CLICK: Follows the tree file by itself. DEPENDS: TC-CHARJSON-SHAPES, TC-VERDICT-CAVEAT,
  DATA-TREE-HOLD, DATA-LEAGUE-IDENTITY.

### Wave 18: go-public, web data, reliability and observability

- [ ] PLAY-TD-19D-ITEMS-GRID (build) Build and items grid 2: Last item, Prices with checked items,
  Item scoring. ACCEPT: npm test --prefix app and python -m pytest -q tests/test_play_fit.py
  tests/test_ux_review.py tests/test_ux_b8.py tests/test_price_book.py tests/test_dash_console.py
  pass with the tab-build marker deleted: a moved checked item sets the tab mark and renders above
  the movers, the separate price watch card is gone, the poe.ninja credit line is visible on the
  Prices card while it shows prices, and G1 holds for every list and Full text page of the tab.
  ZERO-CLICK: Fills from the press the player already makes and from the cached price book; no new
  request. DEPENDS: PLAY-TD-19C-BUILD-GRID. BLOCKED: session wave 18.
- [ ] DATA-DIAG-SEAM (build) One hook for data checks: diag_data (attach, facts, rows) + League
  picker, server half: write the league key, solo-league mapping. ACCEPT: python -m pytest -q
  tests/test_diag_data.py tests/test_diag_self.py tests/test_floor_static.py passes. Also (folded
  DATA-LEAGUE-PICKER-API): python -m pytest -q tests/test_league_picker.py
  tests/test_contact_field.py tests/test_util_10_ready.py tests/test_ux_settings_io.py passes.
  ZERO-CLICK: The dev step that lets four later packages run in parallel with no shared edit. Also
  (folded DATA-LEAGUE-PICKER-API): The league follows the auto league as today; the picker is an
  optional override. DEPENDS: DATA-CONTACT-FIELD, DATA-LEAGUE-IDENTITY. BLOCKED: session wave 18.
- [ ] RUN-START-REASON-CORE (build) A bind failure names its cause; --port stays in the block (P8-4)
  + One JSON line per own event (events.jsonl). ACCEPT: python -m pytest -q
  tests/test_port_resolve.py tests/test_audit_pass8.py passes. Also (folded RUN-OPLOG): python -m
  pytest -q tests/test_oplog.py tests/test_sidecar_paths.py passes. ZERO-CLICK: The line names the
  one fix; AshLight never moves to another port by itself. Also (folded RUN-OPLOG): Written by
  itself; read by the probe and the report. DEPENDS: RUN-OBS-LOGS-PY, RUN-METRICS-SITES,
  RUN-LEDGER-WIRE. BLOCKED: session wave 18.
- [ ] DATA-PRICE-CADENCE (build) Tiered poe.ninja cadence and the release polling gate. ACCEPT:
  python -m pytest -q tests/test_price_cadence.py tests/test_price_book.py tests/test_data_ninja.py
  tests/test_audit_pass2.py passes. ZERO-CLICK: Nothing for players; the cadence is automatic. The
  Q-05 message is optional (OA-2, skipped in writing 2026-11-18). DEPENDS: DATA-PRICE-POLITE,
  DATA-CONTACT-FIELD. BLOCKED: session wave 18.
- [ ] REL-RUNTIME-SCRIPTS (build) One PowerShell helper for Python and paths; the client prefers the
  private runtimes. ACCEPT: python -m pytest -q tests/test_al_env.py tests/test_supervisor.py
  tests/test_run_detach.py tests/test_autostart.py tests/test_port_resolve.py
  tests/test_desktop_client.py passes and npm test --prefix app passes. ZERO-CLICK: Dev and install
  plumbing; a start needs no PATH Python and no Node on the player path. DEPENDS: DEP-06,
  REL-AUTOSTART-ENTRY, REL-CLIENT-HOME, REL-RUNTIME-PINS, DEP-02, OVL-ELECTRON-SETUP,
  OVL-LAUNCH-ENV, SEC-NO-PROXY. BLOCKED: session wave 18.
- [ ] LOOP-DRIFT-REF (build) TC-DRIFT-TRIAL-FIX (part 2): trial --ref rehearsal and the GUI
  reference keyed by tag. ACCEPT: `python -m pytest -q tests/test_tc_drift.py
  tests/test_tc_bridge.py` passes (the live bridge tests skip where the optional calc component is
  absent). ZERO-CLICK: The static tier is unattended; the live tier and the pin move stay session
  acts (decision 0025). DEPENDS: AUTO-12. BLOCKED: session wave 18.
- [ ] LOOP-WATCH-POBNEXT (build) Watch source: PoB-PoE2 next release (master head, weekly). ACCEPT:
  `python -m pytest -q tests/test_watch_pob_next.py tests/test_watch_rows.py` passes. ZERO-CLICK:
  Unattended; the static rehearsal itself stays a session act (`tc_drift.py trial --ref`, AUTO-12).
  DEPENDS: AUTO-05, LOOP-WATCH-ROWS. BLOCKED: session wave 18.
- [ ] RUN-LEDGER-REPORT (build) tools/live1_report.py: VERIFIED live / NOT SEEN / NEW SHAPE per
  LIVE-1 item. ACCEPT: python -m pytest -q tests/test_live1_report.py passes and python
  tools/live1_report.py --json on a fixture ledger exits 0. ZERO-CLICK: A session runs it as one
  command; the loop runs it once AUTO-18 wires it (cross); the operator only plays. DEPENDS:
  RUN-LEDGER-CORE, RUN-LEDGER-WIRE. BLOCKED: session wave 18.
- [ ] PUB-SETTINGS-FILES (build) Repository settings as tracked files with a lint test. ACCEPT:
  `python -m pytest -q tests/test_repo_settings_files.py tests/test_ascii_lf.py
  tests/test_leak_sweep.py` is green. ZERO-CLICK: Files only; GP-13 and GP-15 apply them with gh and
  read them back, with no click. DEPENDS: GP-05. BLOCKED: session wave 18.
- [ ] GP-08 (build) Dependabot config file. ACCEPT: `python -m pytest -q
  tests/test_dependabot_config.py tests/test_ascii_lf.py` is green. ZERO-CLICK: GitHub opens the
  bump pull requests by itself; GP-14's tool re-applies and closes them, nothing is merged on
  GitHub. BLOCKED: session wave 18.
- [ ] TEST-SUITE-SOAK (review) Prove the parallel gate: 10 green runs, one serial fallback run, one
  spelling. ACCEPT: python -m pytest -q tests/test_ascii_lf.py tests/test_research_numbers.py
  tests/test_leak_sweep.py passes and the note's second dated addendum lists 10 consecutive green
  runs of the one gate command with their hold seconds (median under 75 s), one green run with xdist
  hidden, and one command hash for all of them in the gate's duration log. ZERO-CLICK: The agent
  runs the eleven gated runs itself, one at a time, at below-normal priority; no operator step.
  DEPENDS: TEST-GATE-CALLERS. BLOCKED: session wave 18.
- [ ] DATA-GUIDE-FACTS (data) Guide facts from allowed sources: 4 blank zones, point-books wording,
  coverage. ACCEPT: python -m pytest -q tests/test_zone_guide.py tests/test_provenance.py
  tests/test_hot_reload.py passes (the snapshot coverage test runs where the world_areas cache
  exists, as test_every_guide_zone_names_a_snapshot_zone_of_its_act does). ZERO-CLICK: Data only;
  the file hot-reloads and the guide follows the log with no click. DEPENDS: DATA-GUIDE-MERGE,
  DATA-GUIDE-BOSS. BLOCKED: session wave 18.
- [ ] PUB-DEPBOT-ACTIONS (data) Dependabot re-apply tool: actions bumps and the commit, push and
  close path. ACCEPT: `python -m pytest -q tests/test_dependabot_reapply.py
  tests/test_p163_lane_tools.py tests/test_ascii_lf.py tests/test_leak_sweep.py` is green.
  ZERO-CLICK: Part of `python tools/dependabot_reapply.py run`: no prompt; a session runs it until
  the loop resumes (F-078), then the tick does (PUB-DEPBOT-TICK). DEPENDS: GP-14, GP-02, GP-05.
  BLOCKED: session wave 18.
- [ ] PUB-DEPBOT-TICK (build) Loop tick launches the Dependabot re-apply worker once a day. ACCEPT:
  `python -m pytest -q tests/test_loop_depbot.py tests/test_loop_split.py tests/test_al_loop.py
  tests/test_p163_lane_tools.py` is green. ZERO-CLICK: Fully unattended once F-078 resumes the loop;
  while HALT is present nothing is launched and a session runs the tool instead. DEPENDS: GP-14,
  PUB-LOCAL-ONLY-TEXT. BLOCKED: session wave 18.

### Wave 19: reliability and observability, web data, install and release

- [ ] RUN-VERDICTS-UI (build) 'Tried in game' card on the Checks tool + The report is built on the
  click by GET /api/report and shown in a preview first. ACCEPT: npm test --prefix app passes and
  python -m pytest -q tests/test_a11y.py tests/test_ux_review.py tests/test_dash_console.py passes.
  Also (folded RUN-REPORT-ROUTE): python -m pytest -q tests/test_report_route.py
  tests/test_diag_self.py tests/test_a11y.py tests/test_http_security.py passes and npm test
  --prefix app passes. ZERO-CLICK: Each in-game try ends in one click; no reminder, no typed report.
  Also (folded RUN-REPORT-ROUTE): The copy stays one click (decision 0014); the preview costs no
  extra click. DEPENDS: RUN-VERDICTS-CORE, RUN-LEDGER-WIRE, RUN-BUILD-STAMP-CORE. BLOCKED: session
  wave 19.
- [ ] RUN-LADDER-TICK (build) Map ladder tick is free when nothing changed (AUDIT-P8-LOW P8-5).
  ACCEPT: python -m pytest -q tests/test_util_map_ladder.py tests/test_budgets.py
  tests/test_audit_map_seed.py tests/test_util_maps_resume.py passes. ZERO-CLICK: Nothing to do; the
  ladder still fills by itself. DEPENDS: RUN-DURABLE-STORES, RUN-LEDGER-WIRE. BLOCKED: session wave
  19.
- [ ] RUN-OBS-LOGS-SHELL (build) overlay.log and run.log bounded, same stamp format + run.ps1 and
  the client's failed page print the start error; client port check (P8-3) + The client reports why
  the overlay is shown or hidden. ACCEPT: npm test --prefix app passes and python -m pytest -q
  tests/test_run_detach.py tests/test_desktop_client.py tests/test_logs.py tests/test_ascii_lf.py
  passes. Also (folded RUN-START-REASON-CLIENT): npm test --prefix app passes and python -m pytest
  -q tests/test_desktop_client.py tests/test_run_detach.py tests/test_ascii_lf.py passes. Also
  (folded RUN-EXPLAIN-OVERLAY-STATE): npm test --prefix app passes and python -m pytest -q
  tests/test_floor_static.py passes. ZERO-CLICK: At start, by itself. Also (folded
  RUN-START-REASON-CLIENT): The line shows by itself on a failed start. Also (folded
  RUN-EXPLAIN-OVERLAY-STATE): Automatic. DEPENDS: RUN-OBS-LOGS-PY, RUN-BUDGET-LOG-CLIENT,
  RUN-START-REASON-CORE. BLOCKED: session wave 19.
- [ ] RUN-SUPERVISOR-CLOCK (build) Supervisor liveness verdict that cannot misfire. ACCEPT: python
  -m pytest -q tests/test_keepalive.py tests/test_supervisor.py tests/test_http_security.py passes.
  ZERO-CLICK: Automatic; 'AshLight restarted its core at 21:14 (it had stopped answering).'.
  DEPENDS: RUN-OBS-LOGS-PY, RUN-METRICS-CORE, RUN-SEAMS, RUN-LEDGER-WIRE. BLOCKED: session wave 19.
- [ ] REL-BUILD-ASSETS (build) Release build: release.json, stamped installer, notes, SBOM,
  SHA256SUMS. ACCEPT: python -m pytest -q tests/test_release_assets.py tests/test_release_tool.py
  passes and two runs of python tools/release.py build --ref HEAD --out <tmp> give identical
  SHA256SUMS.txt. ZERO-CLICK: One command, no prompt, no upload. DEPENDS: DEP-08, REL-SBOM,
  DATA-PRICE-CADENCE. BLOCKED: session wave 19.
- [ ] DATA-PRICE-SHAPE-GUARD (build) A silent poe.ninja shape change keeps the last good prices.
  ACCEPT: python -m pytest -q tests/test_price_shape_guard.py tests/test_price_book.py
  tests/test_data_ninja.py tests/test_diag_data.py passes. ZERO-CLICK: Automatic; no request is
  added, the checks are local. DEPENDS: DATA-DIAG-SEAM, DATA-PRICE-CADENCE. BLOCKED: session wave
  19.
- [ ] TEST-STATE-TEXT-PINS (build) Point the design gate, the reviewer agent, the lane prompt and
  design 0001 at server/al/text/. ACCEPT: python -m pytest -q tests/test_design_gate.py
  tests/test_a11y.py tests/test_design_contrast.py tests/test_al_loop_gate_cache.py passes, npm test
  --prefix app passes, and grep -c 'server/al/state.py' tools/design_gate.py tools/loop_prompts.py
  .claude/agents/design-reviewer.md prints 0 for each. ZERO-CLICK: Developer-side only; the player
  does nothing. The gate and the lane prompt apply the new path by themselves from the next commit
  on. DEPENDS: TEST-STATE-TEXT-4, TEST-WAVE-GATE-POLICY. BLOCKED: session wave 19.
- [ ] REL-UPDATE-LAUNCH (build) Client launcher: apply a staged update before the core starts.
  ACCEPT: npm test --prefix app passes and python -m pytest -q tests/test_overlay_smoke.py
  tests/test_update_switch.py passes. ZERO-CLICK: The update applies at the next start with no
  click; one line names the version. DEPENDS: REL-UPDATE-SWITCH, REL-RUNTIME-SCRIPTS,
  REL-CLIENT-HOME. BLOCKED: session wave 19.
- [ ] DATA-SNAP-PROBE (build) Probe each fetched snapshot file before it replaces the cached one.
  ACCEPT: python -m pytest -q tests/test_snap_probe.py tests/test_tc_snap.py
  tests/test_tc_snap_ui.py tests/test_diag_data.py passes. ZERO-CLICK: At each snapshot run (build
  or start); nothing for the player. DEPENDS: DATA-TREE-HOLD, DATA-DIAG-SEAM. BLOCKED: session wave
  19.
- [ ] OVL-CLIENT-GUARD (build) CLIENT-GUARD: the client survives its own errors without a dialog and
  rebuilds a dead overlay or companion page. ACCEPT: node --test app/test/crashguard.test.js
  app/test/parts.test.js and python -m pytest -q tests/test_overlay_smoke.py
  tests/test_floor_static.py pass. ZERO-CLICK: Automatic; the tray tooltip changes only after the
  cap. Handlers run only on failure events in the main process; the page gets no timer. DEPENDS:
  OVL-MAIN-PARTS. BLOCKED: session wave 19.
- [ ] PUB-GUIDE-PAGES (build) Four-page player guide. ACCEPT: `python -m pytest -q
  tests/test_player_guide.py tests/test_ascii_lf.py tests/test_leak_sweep.py
  tests/test_research_numbers.py` is green. ZERO-CLICK: Reading is optional; nothing in play depends
  on it. DEPENDS: PUB-README-PLAYERS. BLOCKED: session wave 19.
- [ ] DATA-RESEARCH-GAPS (data) Research gaps: triage table for note 0056 and the adopted-patterns
  register of note 0055. ACCEPT: `python -m pytest -q tests/test_ascii_lf.py
  tests/test_research_numbers.py tests/test_leak_sweep.py` passes, `grep -c "^## Addendum"
  docs/research/0056-third-party-repo-review.md` prints 1 or more and `grep -c "^## Adopted
  patterns" docs/research/0055-competitive-companions-overlays.md` prints 1. ZERO-CLICK:
  Developer-side only: an agent works from the review data already in the sidecar and the notes' own
  source lists; nothing for the player to do and nothing is read from the game. DEPENDS: GP-01.
  BLOCKED: session wave 19.
- [ ] PUB-DEPBOT-NPM (data) Dependabot re-apply tool: the npm branch. ACCEPT: `python -m pytest -q
  tests/test_dependabot_reapply.py tests/test_ascii_lf.py` is green. ZERO-CLICK: Part of `run`: no
  prompt; an electron pin never moves without the Electron bump procedure. DEPENDS:
  PUB-DEPBOT-ACTIONS, OVL-NPM-LOCK. BLOCKED: session wave 19.
- [ ] DATA-SNAP-SETUP (build) setup.ps1 runs the game-data snapshot when web data is already on.
  ACCEPT: python -m pytest -q tests/test_setup_snapshot.py tests/test_tc_snap.py
  tests/test_audit_snapshot_optin.py passes. ZERO-CLICK: The dev step runs itself: one setup
  command, no second command for game data once 'Use web data' is ticked. DEPENDS:
  REL-RUNTIME-SCRIPTS.
- [ ] DATA-TRADESTAT-COVERAGE (build) Count trade stat id coverage per source before retiring the
  PoB fallback. ACCEPT: python -m pytest -q tests/test_math_tradestat_local.py
  tests/test_math_tradestat_pob.py tests/test_math_tradestat_cover.py tests/test_tc_upgrade_stats.py
  tests/test_diag_data.py passes. ZERO-CLICK: Computed at each index load, shown on the Checks page
  with no click. DEPENDS: DATA-DIAG-SEAM, TC-UPGRADE-PER-SLOT.
- [ ] TC-BUILDFILE-EXIT-WATCH (review) .build exit trigger from the PoB release check. ACCEPT:
  python -m pytest -q tests/test_tc_drift.py passes. ZERO-CLICK: The exit trigger needs no reminder:
  the loop tick's existing check raises it. DEPENDS: TC-CALC-VERIFY-PIN, AUTO-12, AUTO-05,
  LOOP-DRIFT-REF.

### Wave 20: overlay and client, install and release, tests and code seams

- [ ] OVL-TD05-PLATE (build) Overlay slider sets the plate alpha only: limits 0.80 to 1.0, default
  0.86, saved layouts migrate once (TD-05, part 2). ACCEPT: python -m pytest -q
  tests/test_overlay_layout.py tests/test_ux_settings_io.py tests/test_ux_review.py
  tests/test_overlay_smoke.py and node --test app/test/layout.test.js app/test/overlay_gate.test.js
  pass. ZERO-CLICK: Saved layouts migrate by themselves at the next read; the slider stays optional.
  DEPENDS: OVL-TD05-LEGIBILITY, OVL-OVERLAY-KEYS. BLOCKED: session wave 20.
- [ ] OVL-CARD-SLOT (build) Overlay view seam (server/al/overlayview.py) with the card-slot holder
  order and the 10 s sample card. ACCEPT: python -m pytest -q tests/test_overlay_view.py
  tests/test_price_text.py tests/test_eval_text.py tests/test_price_check.py
  tests/test_http_security.py tests/test_budgets.py passes. ZERO-CLICK: The sample shows only on its
  Settings button and leaves after 10 s by itself; in play the slot fills and empties with no click.
  DEPENDS: SEC-SURFACE-PIN. BLOCKED: session wave 20.
- [ ] DEP-12 (build) Release stage: the PASS / FAIL report (static gates). ACCEPT: python -m pytest
  -q tests/test_release_stage.py tests/test_release_assets.py passes. ZERO-CLICK: One command inside
  the REL-PREP row; no prompt, no upload, no tag. DEPENDS: REL-BUILD-ASSETS. BLOCKED: session wave
  20.
- [ ] TEST-WEB-PANELS-A (build) Panel move A: the loaded-build block to web/panels/build.js. ACCEPT:
  npm test --prefix app passes and python -m pytest -q tests/test_dash_console.py tests/test_a11y.py
  tests/test_floor_static.py tests/test_ux_review.py tests/test_webpage.py passes. ZERO-CLICK:
  Developer-side only; the player does nothing. The page assembles the panel tags by itself; paint
  order is kept by explicit order values. DEPENDS: TEST-WEB-ASSEMBLE, PLAY-TD-19D-ITEMS-GRID.
  BLOCKED: session wave 20.
- [ ] DEP-09 (build) Bootstrap install.ps1. ACCEPT: python -m pytest -q tests/test_install_ps1.py
  tests/test_supervisor.py tests/test_floor_static.py passes. ZERO-CLICK: One pasted line, then the
  app opens; a re-run upgrades or repairs in place; the floor's Client.txt opt-in (with its visible
  indicator) and the web-data switch stay the player's own clicks on the first window. DEPENDS:
  REL-INSTALL-CMD, REL-BUILD-ASSETS. BLOCKED: session wave 20.
- [ ] RUN-SECOND-LINE-PY (build) Nothing stays down: supervisor adopted at start, core restarts a
  missing supervisor. ACCEPT: python -m pytest -q tests/test_supervisor.py tests/test_procs.py
  tests/test_keepalive.py tests/test_run_detach.py tests/test_ascii_lf.py passes. ZERO-CLICK:
  Automatic; 'Keepalive was not running; AshLight started it again.' on the Checks card. DEPENDS:
  RUN-SUPERVISOR-CLOCK, RUN-OBS-LOGS-SHELL. BLOCKED: session wave 20.
- [ ] DATA-NINJA-SHAPE-WATCH (build) poe.ninja drift detection in the core: signatures, baseline,
  league checks. ACCEPT: python -m pytest -q tests/test_ninja_shape.py tests/test_price_book.py
  tests/test_data_ninja.py tests/test_hot_reload.py passes. ZERO-CLICK: Automatic in the core; the
  loop turns the flag into a row by itself (AUTO-10). DEPENDS: DATA-PRICE-SHAPE-GUARD,
  DATA-LEAGUE-IDENTITY, DATA-DIAG-SEAM. BLOCKED: session wave 20.
- [ ] TEST-STRUCTURE-GUARD (build) Structure test: acyclic server imports, player text under a gate
  path. ACCEPT: python -m pytest -q tests/test_structure.py passes, and its self-checks show a
  planted import cycle and a planted 5-sentence module outside the gate both fail. ZERO-CLICK: Runs
  in the suite; a new text module outside the gate fails at once with the rule. DEPENDS:
  TEST-STATE-TEXT-PINS. BLOCKED: session wave 20.
- [ ] SEC-HELLO-CLIENT (build) The Electron client verifies the core before it sends anything.
  ACCEPT: npm test --prefix app and python -m pytest -q tests/test_floor_static.py
  tests/test_desktop_client.py pass: a fake server answering 200 to everything receives neither the
  token nor item text, and with an unverified core the companion window stays on its starting page.
  ZERO-CLICK: Code change; the client verifies by itself once per token value and again after any
  request error. The clipboard is still read once per manual press (decision 0003); this only
  narrows where that text may go. DEPENDS: SEC-HELLO-CORE, RUN-OBS-LOGS-SHELL. BLOCKED: session wave
  20.
- [ ] AUTO-10 (build) NINJA-WATCH: the poe.ninja docs page and the shape-drift flag. ACCEPT: `python
  -m pytest -q tests/test_watch_ninja.py tests/test_watch_rows.py` passes. ZERO-CLICK: Automatic: a
  poe.ninja change becomes a row; the shipped app makes no extra request for it. DEPENDS: AUTO-05,
  LOOP-WATCH-ROWS. BLOCKED: session wave 20.
- [ ] TC-PRESS-SAMPLES (build) Dev-host capture of sanitized item-press samples. ACCEPT: python -m
  pytest -q tests/test_press_samples.py tests/test_sidecar_paths.py tests/test_ux_settings_io.py
  passes. ZERO-CLICK: No extra act in play: with the switch on, the normal item-check presses are
  the samples. DEPENDS: TC-CARD-PARTS. BLOCKED: session wave 20.
- [ ] AUTO-18 (build) LEDGER-SOURCE: live log shapes and snapshot probe results become rows. ACCEPT:
  `python -m pytest -q tests/test_watch_ledger.py tests/test_watch_rows.py tests/test_al_lane.py`
  passes. ZERO-CLICK: Unattended once the ledger consent is ticked: normal play closes the live
  shape rows. DEPENDS: AUTO-05, LOOP-WATCH-ROWS, LOOP-WATCH-FILE, LOOP-ROWFILES-WORK,
  LOOP-USAGE-LABEL. BLOCKED: session wave 20.

### Wave 21: overlay and client, install and release, reliability and observability

- [ ] PLAY-TD-20A-RUN-GRID (build) Run grid 1: Acts, Maps and Deaths cards. ACCEPT: npm test
  --prefix app and python -m pytest -q tests/test_play_fit.py tests/test_a11y.py
  tests/test_dash_console.py pass: the Acts, Maps and Deaths cards are 3 cells of the Run grid,
  their lists page at 10 rows, no element inside them scrolls in states f and g at the 5 cockpit
  sizes, and the game data credit line is visible on the Acts card while snapshot data shows.
  ZERO-CLICK: Fills from the log; paging is optional and outside play. DEPENDS:
  PLAY-TD-19D-ITEMS-GRID. BLOCKED: session wave 21.
- [ ] RUN-QUIET-FEED (build) Quiet feed: no minute stamp or report text in the snapshot, ages
  stepped at 5 minutes. ACCEPT: python -m pytest -q tests/test_quiet_feed.py tests/test_diag_self.py
  tests/test_sse_idle_push.py passes and npm test --prefix app passes. ZERO-CLICK: The feed is
  silent while nothing happens; nothing to click. DEPENDS: RUN-VERDICTS-UI, RUN-LADDER-TICK,
  RUN-ZONE-RESET. BLOCKED: session wave 21.
- [ ] OVL-ZONE-CARD (build) Zone moment card in the one card slot, and the guide-line fields for HUD
  line 2. ACCEPT: python -m pytest -q tests/test_moment_cards.py tests/test_overlay_view.py
  tests/test_zone_guide.py tests/test_budgets.py tests/test_glance_rules.py passes. ZERO-CLICK:
  Shows and leaves by itself from the opted-in Client.txt tail and AshLight's own guide file; no
  screen read, no input. DEPENDS: OVL-CARD-SLOT, OVL-OVERLAY-KEYS, OVL-GLANCE-RULES,
  PLAY-TD-08A-GUIDE-SHORT-FIELD, RUN-ZONE-RESET, PLAY-TD-07A-PLAY-VIEW. BLOCKED: session wave 21.
- [ ] OVL-LINE2-RULE (build) Overlay HUD line 2: one priority order with the 26-character rule
  (hudLine2). ACCEPT: node --test app/test/hudline2.test.js app/test/layout.test.js
  app/test/overlay_gate.test.js app/test/overlay_parts.test.js app/test/shared.test.js and python -m
  pytest -q tests/test_overlay_smoke.py pass. ZERO-CLICK: The line follows the snapshot by itself;
  nothing to set. DEPENDS: OVL-PARTS-PAGE, OVL-TD05-PLATE, PLAY-TD-02-SLOTS,
  PLAY-F-131-STATUS-TABLE. BLOCKED: session wave 21.
- [ ] REL-PUBLISH-GATES (build) Publish gates: the operator phrase, the refusals, rehearse and
  prepush-check. ACCEPT: python -m pytest -q tests/test_release_gates.py tests/test_release_stage.py
  passes and python tools/release.py publish --rehearse --version <VERSION> --go "release <VERSION>"
  exits non-zero and names 'no remote' among its refusals while the repository is local only.
  ZERO-CLICK: One operator phrase per release; everything before and after is automatic. DEPENDS:
  DEP-12. BLOCKED: session wave 21.
- [ ] REL-STAGE-ROUNDTRIP (build) Release stage: scratch-home install, update, rollback, uninstall.
  ACCEPT: python -m pytest -q tests/test_release_stage.py passes and, with the runtimes cached,
  python tools/release.py stage --version <VERSION> writes stage.json with step 6 PASS. ZERO-CLICK:
  Runs by itself inside the stage; hidden, self-test ports 8970-8975, web data off. DEPENDS: DEP-12,
  DEP-09, REL-UNINSTALL-SHELL, REL-UPDATE-SWITCH. BLOCKED: session wave 21.
- [ ] RUN-STOP-RACE (build) Stop only what was running when stop was asked. ACCEPT: python -m pytest
  -q tests/test_procs.py tests/test_ascii_lf.py passes. ZERO-CLICK: Automatic. DEPENDS:
  RUN-SECOND-LINE-PY, RUN-OBS-LOGS-SHELL. BLOCKED: session wave 21.
- [ ] OVL-CHECK (build) OVL-CHECK: developer tool that runs the in-map overlay check as one normally
  played map. ACCEPT: python -m pytest -q tests/test_ovl_check.py tests/test_floor_static.py
  tests/test_sidecar_paths.py passes. ZERO-CLICK: A session arms it; it starts by itself 20 s into
  an open map and ends by itself; the operator plays one map and answers same / dropped once.
  DEPENDS: OVL-CARD-SLOT, OVL-PARTS-PAGE, RUN-BUDGET-LOG-CORE, RUN-BUDGET-LOG-CLIENT,
  RUN-VERDICTS-UI. BLOCKED: session wave 21.
- [ ] OVL-CONTRAST-PIXELS (review) Contrast gate measures rendered pixels: glyph core against the
  plate over white and a 2 px checker; rendered widths of the worst-case lines. ACCEPT: python -m
  pytest -q tests/test_overlay_pixels.py passes on a machine with Chrome or Edge and node (it skips,
  with a reason, without them). ZERO-CLICK: Runs in the suite; synthetic backdrops only, no capture
  of the desktop or the game. DEPENDS: OVL-TD05-PLATE, TEST-CAPTURE-HELPER, SEC-DEMO-ENTRY. BLOCKED:
  session wave 21.
- [ ] DEP-14 (build) Player docs: install, update, uninstall, verify, 'Windows may warn'. ACCEPT:
  python -m pytest -q tests/test_readme.py tests/test_version.py tests/test_ascii_lf.py
  tests/test_leak_sweep.py passes. ZERO-CLICK: Nothing for the player to do; the docs name the one
  pasted line. DEPENDS: DEP-02, DEP-03, REL-RUNTIME-PINS, DEP-09, REL-UNINSTALL-SHELL,
  PUB-README-PLAYERS. BLOCKED: session wave 21.
- [ ] AUTO-08 (build) WATCH-HEALTH: a broken watcher is itself a finding. ACCEPT: `python -m pytest
  -q tests/test_watch_health.py tests/test_watch_rows.py` passes. ZERO-CLICK: Unattended: a silent
  watcher shows up in the checklist by itself. DEPENDS: AUTO-01, AUTO-05, LOOP-WATCH-ROWS. BLOCKED:
  session wave 21.
- [ ] AUTO-17 (build) REFRESH-SOURCE: stale docs, screenshots and an unplanned release become rows.
  ACCEPT: `python -m pytest -q tests/test_watch_refresh.py tests/test_watch_rows.py` passes.
  ZERO-CLICK: Unattended: docs, screenshots and release planning cannot drift silently. DEPENDS:
  AUTO-05, LOOP-WATCH-ROWS, LOOP-WAVE-HOLD. BLOCKED: session wave 21.

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

### Parked

- [ ] GP-10 (build) The project's own address in tracked files. ACCEPT: `python tools/leak_sweep.py
  --tree` exits 0 printing `ARMED` with the address in README.md, and `python -m pytest -q
  tests/test_leak_sweep.py tests/test_community_files.py tests/test_public_docs.py
  tests/test_ascii_lf.py` is green. ZERO-CLICK: One config value written by an agent from the
  existing remote; no player types an address. DEPENDS: GP-09, PUB-SWEEP-OWN-ADDRESS, GP-06,
  PUB-README-PLAYERS. BLOCKED: the repository exists (first push done); unblocks when `git remote
  get-url origin` prints the repository address and `gh repo view` succeeds for it (package GP-09).
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
- [ ] AUTO-19 (build) CI-WATCH (workflow half): a daily workflow that writes one key issue per
  finding. ACCEPT: `python -m pytest -q tests/test_watch_ci.py` passes, `git grep -c "not a web_data
  path" -- docs/decisions/0076-ci-issue-protocol.md` prints a count of 1 and, after the first push,
  the workflow's manual run ends green. ZERO-CLICK: Unattended: the watch survives a dev host that
  is off; standard runners are free on a public repository. DEPENDS: AUTO-05, LOOP-WATCH-GATE,
  GP-09, GP-05. BLOCKED: the remote does not exist yet (no git remote is configured; GP-09 creates
  the repository and makes the first push); unblocks when `git remote get-url origin` exits 0 and
  the first push is green (GP-09 done) (package GP-09).
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
  the remote does not exist yet (no git remote is configured; GP-09 creates the repository and makes
  the first push); unblocks when `git remote get-url origin` exits 0 and the first push is green
  (GP-09 done) (package GP-09).
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
- [ ] GP-11 (review) Description, topics and feature switches. ACCEPT: `gh repo view "$R" --json
  repositoryTopics --jq '[.repositoryTopics[].name] | sort | join(",")'` prints
  companion-app,dashboard,electron,loot-filter,overlay,path-of-building,path-of-exile-2,poe2,python,windows
  and `gh repo view "$R" --json
  description,hasIssuesEnabled,hasWikiEnabled,hasProjectsEnabled,hasDiscussionsEnabled` shows the 04
  description, issues on, wiki / projects / discussions off. ZERO-CLICK: Agent step with gh; no
  click. DEPENDS: GP-09. BLOCKED: the repository exists (first push done); unblocks when `gh repo
  view` succeeds for the repository (package GP-09).
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
  budget-log rows from normal in-map play; unblocks when python -m server.al.budgetlog check prints
  10 or more rows tagged in map with the overlay shown (operator).
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
