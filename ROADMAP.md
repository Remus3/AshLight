# AshLight ROADMAP

Open work only, as lane rows the loop (`tools/al_loop.py`) can dispatch.
Format: `- [ ] ID (lane) title. ACCEPT: ...`; `(priority)` jumps the queue.
Done rows are flipped to `[x]` by the merge and pruned at /done.

## Lane: build

- [ ] LIVE-1 (build) (priority) PARTIAL 2026-11-16: first live log verified
  (research 0002 section 7): prefix, SCENE, area generation, instance
  connect, level-up, global / trade chat VERIFIED; "(unknown)" and "Act <N>"
  scenes and the empty-character config were WRONG and are fixed; fixture
  tests/fixtures/client_live_shapes.txt. REMAINS: death, whispers and trade
  templates (then replace the HUD-WHISPER fixture whispers with anonymised
  real-shaped ones), party / guild chat, AFK / DND, joined / left, Trade
  accepted, hideout scene names. ACCEPT: every event type seen live has a
  fixture and a passing test. Needs the operator to play past the whisper
  level, die once, and receive one trade whisper. BLOCKED: operator act
  (in-game play, hand-off OPERATOR act (b)); the loop skips it until then.
- [ ] OVL-BUDGET (build) PARTIAL 2026-11-16 (decision 0002 "Measured
  2026-11-16 (OVL-BUDGET, game running)"): idle with the game open at
  character select 3 processes, about 204 MB working set, 0.000 percent CPU,
  0 GPU - within budget, after the in-process-gpu start fix. REMAINS: the
  ACTIVE measurement (overlay updating during play, in a map). ACCEPT: within
  budget or a ruling on Tauri / native. BLOCKED: operator act (in-map play,
  hand-off OPERATOR act (a)); the loop skips it until then.
- [ ] OVL-FPS (build) PARTIAL 2026-11-16. Method per decision 0006 (no
  PresentMon / ETW of the game). Character-select proxy: system-wide GPU 3D
  utilisation off 52.5 vs on 53.3 percent, inside noise, GPU saturated.
  REMAINS: in-map run read from the game's own FPS display, overlay off vs
  idle vs updating, Windowed Fullscreen. ACCEPT: average FPS loss under 1
  percent, 1 percent lows unchanged within noise; numbers in decision 0002.
  BLOCKED: operator act (in-map FPS test, hand-off OPERATOR act (a)); the
  loop skips it until then.
- [x] OVL-TRADE-CANCEL (build) Decide whether ": Trade cancelled." (new
  event trade_cancelled) should clear or mark an open trade card (design
  review 2026-11-16). ACCEPT: behaviour decided and tested. DONE
  2026-11-17: decision 0019 - accepted / cancelled drop one open card (by
  counterparty name if a line carries one, else the oldest); with
  UX-REVIEW F1 (HUD status slot says "1 trade" / "N trades" while a card
  holds the slot) and F6 (dashboard polite "New trade request from <name>."
  only when the set of ids grows). ZERO-CLICK: the card clears itself.
- [x] HUD-ACT (build) Leveling helpers: act / zone level table from an
  attributed build-time data snapshot (license checked first, research 0005);
  zone timer splits per act. ACCEPT: split table on the dashboard. DONE
  2026-11-17 (decision 0020): server/al/acts.py folds area-generation ids
  into per-act splits (snapshot `acts`; dashboard "Act times": act, time in
  act, total); zone levels for the current act from repoe-fork
  world_areas.json, fetched only by the build-time snapshot into the
  sidecar cache (decision 0009 conditions), attributed under the table, the
  core only reads the cache. Tests: tests/test_hud_act.py,
  app/test/acts.test.js. ZERO-CLICK: splits and the zone table update by
  themselves on every zone change.
- [ ] HUD-ACT-RESUME (build) Act splits survive a core restart: LIVE-RESUME
  (decision 0008) also returns the current run's area-generation ids with
  their line timestamps, so the splits rebuild from Client.txt instead of
  starting empty and partial. Also confirm the cruel `C_G<n>_` / interlude
  `P<n>_` id prefixes from a live log (LIVE-1) and fix acts.act_of if they
  differ. ACCEPT: restart mid-act keeps earlier act times; exact tests.
  ZERO-CLICK: rebuilt at core start.
- [x] PRICE-1-COPY (build) Design review of PRICE-1-WIRE (reviews.log
  2026-11-17, S3 x3) on price.card_of: F1 any error text containing
  "league" maps to "no league" (match only trade.search_url's exact
  "league required"; others -> free-text error); F2 `off` covers both web
  data off and contact not set but the card says "Web data is off" (carry
  the reason, add a state.py PRICE_TEXT entry for contact not set, design
  review); F3 every skipped doc maps to "not an item" incl. build_query's
  "item has no base type" (map only reason "not an item"). ACCEPT: tests
  per mapping; design-reviewer pass. ZERO-CLICK: code row.
- [x] PRICE-TRADE-LINK (build) Decision 0017: remove every reachable app
  HTTP path to trade2 (/data/stats, /data/leagues, /search, /fetch); keep
  build_query offline, producing
  https://www.pathofexile.com/trade2/search/poe2/<league>?q=<json>; price
  card status "link" with `url` (0016 Fork 1 amended); dashboard shows a
  click-through link, overlay "Trade link ready"; the core never opens it;
  league from config, else Standard, nothing fetched; prices from poe.ninja
  only. After PRICE-1-COPY merges (both edit price.py). ACCEPT: tests that
  no trade host is in the webfetch allowlist and no code path reaches a
  trade2 request; URL round-trip test; design-reviewer pass.
  ZERO-CLICK: the item-check press builds the link with the price card; the
  user clicks it only if they want the trade site.
  DONE 2026-11-17: trade network code deleted, webfetch refuses trade URLs,
  offline search_link (research 0016), card status "link" (0016 amendment).

## Lane: data

- [x] DATA-TREE-IDS (data) DONE 2026-11-17: PoB2 spec node ids and GGG
  export skill ids are the SAME id space (research 0015: PoB2 PassiveSpec /
  PassiveTree / passivetree_ggg source, plus all 4914 PoB2 0_5 tree ids
  found in the GGG export with matching names). resolve() stays 1:1;
  TreeData.id_match guards it (build view drops named_nodes when under
  half the spec ids exist, adds tree_match). Tests:
  tests/test_tc_tree_ids.py. ZERO-CLICK: code row, no user step.

## Lane: review

- [x] UX-REVIEW (review) Glanceability review of dashboard and overlay -- done 2026-11-17 (loop; refute 0/3 PASS)
  (contrast, type scale, motion, phone width) against research 0008.
  ACCEPT: findings fixed or filed.
- [x] RES-POLICY (review) Re-read GGG's developer docs and ToU each patch
  cycle; update research 0001 and the CLAUDE.md floor if anything changed.
  Done 2026-11-17: policy unchanged; 3 floor wording proposals in research
  0001 for MAIN / operator.

## Theorycraft and item optimization (decision 0004, research 0010)

Phase 1 is stdlib-only file interop with Path of Building PoE2; phase 2
adds the optional pinned LuaJIT + PoB calc subprocess. Rows run in order.
Every row carries the minimal-interaction constraint (CLAUDE.md, decision
0004): no click the app can safely make for the user, state updates itself,
and the row's own dev / test steps run unattended. ZERO-CLICK states how.

- [x] TC-CODE-REAL (review) Confirm the codec on a real PoB2 v0.23.1 export -- done 2026-11-17 (loop; refute 0/3 PASS)
  (framing, root element, PlayerStat names) once a PoB2 install or an
  operator-supplied code is available; add it as a fixture only if its
  owner allows. After TC-CODE. ACCEPT: decode + parse + byte-exact round
  trip of the real code. ZERO-CLICK: a test that skips when the fixture is
  absent.
- [x] TC-SNAP-UI (build) Show snapshot.ATTRIBUTION (decision 0009) in the
  dashboard footer / About and the overlay About wherever snapshot data is
  used; expose it via an API field. After TC-SNAP. ACCEPT: text visible,
  design-reviewer pass. ZERO-CLICK: shown automatically when the cache
  exists. DONE 2026-11-17: GET /api/version "data_credit" (null without
  the cache; theorycraft/datacredit.py holds ATTRIBUTION, no network);
  dashboard footer line read on every feed connect; overlay About panel and
  page About read at start and on each core restart (no polling).
- [x] TC-UPGRADE (build) Upgrade search as a link builder (decision
  0017): from the local weights build a trade2 search URL offline
  (https://www.pathofexile.com/trade2/search/poe2/<league>?q=<json>) that
  the user opens in their own browser; the app makes no trade2 request, no
  POESESSID; prices shown come from poe.ninja only. Until TC-UPGRADE-STATS
  lands the link carries name, base and rarity only; weighted mod filters
  are BLOCKED on TC-UPGRADE-STATS. After PRICE-TRADE-LINK, TC-EVAL.
  ACCEPT: URL-builder tests; shares PRICE-TRADE-LINK's builder, not
  duplicated; no trade host in the webfetch allowlist.
  ZERO-CLICK: the same hotkey press that evaluates the item builds the
  link; the user clicks it only to open the trade site.
  DONE 2026-11-17 (link builder): server/al/upgrade.py turns the item
  check's best slot into trade.upgrade_link (rare items of the base the
  build wears there, else the checked item's base; base and rarity only,
  complexity cap 200 checked) through trade.link_for, the price link's
  builder; the eval card carries `upgrade` and the dashboard Item check
  card shows an "Upgrade search" link; a build or weights change rebuilds
  it. Tests: tests/test_tc_upgrade.py, app/test/prices.test.js. Weighted
  mod filters stay with TC-UPGRADE-STATS.
- [ ] TC-UPGRADE-STATS (review) Find a permitted source for trade stat ids
  (mod filters for TC-UPGRADE links): GGG API Reference / Data Exports
  check first (decision 0017), then attributed build-time snapshots with a
  license check per decision 0009; never the trade2 /data/stats endpoint
  from the app. ACCEPT: source and license recorded in docs/research and a
  decision, or a dated "no permitted source" note.
  ZERO-CLICK: research row; if a source is found, the build-time fetch runs
  in setup.ps1 unattended.
- [x] TC-PIN (build) Phase 2 setup: tracked pin file (PoB-PoE2 tag, commit,
  archive sha256; LuaJIT version, sha256; no absolute paths); setup.ps1
  step fetches the PoB source archive to the sidecar Cache and builds or
  accepts LuaJIT into Build, hash-verified, off by default; THIRD-PARTY
  notices with PoB's MIT and component notices. ACCEPT: hash mismatch
  refuses; re-run is a no-op; test_sidecar_paths covers the new paths.
  ZERO-CLICK: one opt-in toggle; setup.ps1 does the rest unattended.
  DONE 2026-11-17 (decision 0018): config/tc_pins.json pins PoB-PoE2
  v0.23.1 (7d6f530c) and LuaJIT 2.1.1794386141 (63c8f1a9), both archive
  SHA-256 verified over two downloads; tools/tc_pin.py + setup.ps1 -TcCalc
  (or tc_calc: true); THIRD-PARTY.md; tests/test_tc_pin.py. LuaJIT is built
  only when MSVC / MinGW is on PATH, else "source-only" (this machine has
  neither: TC-BRIDGE needs a compiler or a later pinned binary).
- [x] TC-BRIDGE (build) Fresh stdio JSON bridge (our own Lua, no code from -- done 2026-11-17 (loop; refute 0/3 PASS)
  pob-mcp / pob2-mcp) driving the unmodified pinned PoB checkout via
  luajit.exe, plus a Python client in server/al: load build XML, set an item
  from item text, return outputs; timeout kill; core runs without it.
  After TC-PIN. ACCEPT: outputs on a fixture build match PoB GUI within 0.1
  percent; tests skip cleanly when the component is absent.
  ZERO-CLICK: the bridge starts on first need and restarts itself on a crash.
- [x] TC-DELTA (build) PoB-backed evaluation: DPS and EHP delta of the -- done 2026-11-17 (loop; refute 0/3 PASS)
  clipboard item vs the equipped one, and per-mod weights from PoB deltas
  (offence and EHP) feeding TC-UPGRADE in place of hand weights. After
  TC-BRIDGE, TC-EVAL. ACCEPT: delta tests on fixtures; falls back to stat
  weights with a visible notice when the component is off.
  ZERO-CLICK: deltas recompute on item or build change, no Calculate button.
- [ ] TC-DRIFT (review) On each PoB-PoE2 release: run the bridge tests
  against the new tag, then move the pin in one commit, or hold it and
  record why. ACCEPT: pin moved or a dated hold note in decision 0004.
  ZERO-CLICK: a loop check spots the new tag and runs the tests unattended.
  HOLD 2026-11-17 (AREA-RES, research 0017): no PoB-PoE2 release after
  v0.23.1 (2026-07-28); dev is 109 commits ahead (0.5.5 rune / runemastered
  data, trader fix for Forbidden Rites, HeadlessWrapper "Restore headless
  global cache cleanup" 2026-08-26, .build export PR #2432). Pin stays.
  For AREA-MATH: at the next tag (likely by PoE2 1.0, 2026-12-11) test the
  bridge for cache state leaking across build loads before moving the pin.
- [ ] TC-OAUTH-REG (review) OPERATOR act: apply to GGG for an AshLight
  public OAuth client (PKCE, loopback redirect in port block 8960-8979,
  scopes account:profile and account:characters) once GGG reopens
  registration. BLOCKED: registration closed ("currently unable to process
  new applications", research 0010).
- [ ] TC-IMPORT (build) Live character import with AshLight's own public
  client: PKCE sign-in, GET /character/poe2[/name], tokens in the OS
  credential store, refresh handled, into the build model. BLOCKED on
  TC-OAUTH-REG. ACCEPT: mocked-flow tests; no POESESSID; no undocumented
  endpoint. ZERO-CLICK: one sign-in ever; silent refresh after that.

## Research-filed features (AREA-RES 2026-11-17, research 0020)

Ranked in research 0020; floor checks there. Rulings by adjudicator
recorded in research 0018 section 3.

- [ ] UTIL-MAPRUN (build) Map run tracker from Client.txt only: a new
  instance from `Generating level <N> area "<id>" with seed <N>` with an
  endgame area id starts a map, hideout / town `[SCENE]` pauses it, a new
  seed ends it; dashboard shows maps run, time per map, maps per hour,
  area level, deaths per map, session totals; overlay status slot one
  line. First verify the endgame area-id prefix on a live map (fixture,
  like LIVE-1). ACCEPT: fixture tests for enter / portal back / new map /
  death; numbers on the dashboard; design-reviewer pass. ZERO-CLICK: runs
  from the log tail, no start / stop button.
- [ ] PRICE-UNIQUE (build) Unique prices on the item-check press from
  poe.ninja `/poe2/api/economy/stash/current/item/overview` (Unique*
  types, research 0019): match name + baseType (+ corrupted), show value,
  listing count ("few listings" when low) and 7-day trend; one request
  per type per hour with If-None-Match, only with web_data on (0013).
  ACCEPT: parser tests on a trimmed real body; no request when off.
  ZERO-CLICK: the same hotkey press; overviews refresh on the hourly gate.
- [ ] PRICE-STACKABLES (build) Price stackables on the item-check press via
  more exchange overview types (Ritual/Omens, Essences, Runes, SoulCores,
  Breach, Delirium, Fragments, UncutGems, LineageSupportGems; research
  0019), names from the top-level `items` array (0013). After
  PRICE-UNIQUE (both edit ninja.py). ACCEPT: per-type parser tests; one
  request per type per hour. ZERO-CLICK: same press, hourly refresh.
- [ ] UTIL-1.0-READY (build) PoE2 1.0 (2026-12-11, research 0018): add
  Acts 5-6 id prefixes to acts.py, Duelist / Shadow class names, league
  rollover check in ninja.py and the price card league label, refresh the
  repoe-fork snapshot; after launch review the debug sink of the first 1.0
  log for new system lines. ACCEPT: tests with 1.0-shaped fixture lines;
  rollover test. ZERO-CLICK: data and parser only, nothing for the user.
- [ ] TC-BUILDFILE (build) Export the loaded PoB build as a GGG Build
  Planner `*.build` JSON (Version 1, research 0018 section 3) offered as a
  dashboard "Save .build" download on the player's click; NEVER written
  into the game's BuildPlanner folder (adjudicator ruling 2026-11-17).
  First research the passive id mapping (GGG string ids like
  `strength89` vs PoB / GGG export numeric ids). ACCEPT: schema test
  against the documented fields; mapping source recorded; no write path
  to the BuildPlanner folder (test). ZERO-CLICK: the file is ready as soon
  as a build is loaded; one click to save is the user's placement act.
- [ ] AUDIT-BUILDFILE (review) Record the `.build` ruling (user-saved
  only, never written into the game folder; reverses if GGG explicitly
  permits tool writes there or the operator rules a click write
  acceptable) as a decision when TC-BUILDFILE lands, and add a test-backed
  check that no code path writes under the BuildPlanner folder. ACCEPT:
  decision file + test. ZERO-CLICK: review row.
- [ ] UTIL-MOVERS (build) Dashboard "price movers" panel from the cached
  poe.ninja overviews (`sparkline.totalChange`), no extra requests. After
  PRICE-STACKABLES. ACCEPT: panel test, design-reviewer pass.
  ZERO-CLICK: refreshes with the hourly gate.
- [ ] TC-CURX (build) Hourly exchange history from GGG's documented public
  Currency Exchange API (`web.poecdn.com/api/currency-exchange/poe2/<hour>`,
  research 0018). BLOCKED: TC-OAUTH-REG (adjudicator ruling 2026-11-17:
  standalone executables must use a public OAuth client; reverses if GGG
  exempts scope-less endpoints in writing). ACCEPT: when unblocked, OAuth
  UA, immutable-hour cache, parser tests. ZERO-CLICK: background fetch on
  the hourly boundary once enabled.

## Game settings advisor (operator order 2026-11-16)

## Design and UX audit (operator order 2026-11-16)

Uses the design-reviewer agent (.claude/agents/design-reviewer.md) and the
design docs in docs/design/, both made by a separate agent.

- [x] DESIGN-GATE (review) Make the design-reviewer pass a standing step for
  every row that touches web/ or app/ (review lane after build). After
  DESIGN-AUDIT. ACCEPT: lane prompt or loop rule names the step; one row
  reviewed through it. ZERO-CLICK: runs in the loop, no manual trigger.
  Partly done: the lane prompt names the step (DS-REVIEW-HOOK); "one row
  reviewed through it" waits for the next web/ or app/ row the armed loop
  runs (LOOP-ARM done 2026-11-17). DONE 2026-11-17 (area-ux): UX-U7, UX-U8
  and UX-U9 each went through the design-reviewer before commit (PASS;
  PASS WITH FINDINGS S3=2 S4=1, fixed; PASS WITH FINDINGS S4=2, fixed).

- [x] UX-U7 (review) Real-browser check of the cards added after audit 0003
  (Act times, item check, price / upgrade link, build view) at 320 / 768 /
  1440 px, dark, light and forced colours (glance review 0004 U7). ACCEPT:
  screenshots taken against a replayed-fixture core, what fails fixed and
  test-guarded. DONE 2026-11-17 (area-ux): no horizontal scroll at any
  width; one defect - an unbroken character name under the level ran into
  the deaths tile at 320 px; fixed (`.stat .sub` wraps), guarded by
  tests/test_ux_review.py. Forced colours: every badge keeps its text
  label, so nothing is lost. ZERO-CLICK: layout only, no user step.
- [x] UX-U8 (review) Windows forced-colours / high-contrast on the
  transparent overlay window (glance review 0004 U8). ACCEPT: overlay page
  rendered with forced-colors active; the window background stays
  transparent, the plates and text stay legible, fixes test-guarded.
  DONE 2026-11-17 (area-ux): Electron 45 transparent window probe
  (capturePage with alpha) under forced-colors emulation, dark and
  light: window stays transparent (alpha 0 outside the plates). Found:
  the trade card's warn edge and the upgrade card's green edge both fell
  to plain CanvasText, and the 0.92 plate became 0.92 Canvas. Fixed in
  overlay.css: root opts out of forcing (never an opaque block over the
  game), plates opt back in, plate opaque Canvas, trade / upgrade edges
  Highlight; tests in tests/test_ux_review.py. Not exercised: a real OS
  high-contrast theme switch (emulation only). ZERO-CLICK: follows the OS
  setting, no toggle.
- [x] UX-U9 (review) Session tile empty state (design 0001 rule 9, seen in
  the UX-U7 pass): before the Client.txt opt-in the Session tile showed
  "--:--" over a blank line. ACCEPT: the line says when the timer starts;
  AFK / DND still win; node test. DONE 2026-11-17 (area-ux): web/status.js
  sessionSub() - "Starts when you allow reading Client.txt" until the
  opt-in; app/test/dashboard.test.js. ZERO-CLICK: the line clears itself
  once reading starts.

Rows filed by the first audit (docs/design/0002-first-audit.md; S1 = worst).
Run after DESIGN-AUDIT, ahead of DESIGN-GATE.

## Testing and hardening (AREA-TEST, session 4)

- [x] TEST-FLAKE (build) A live lane / loop tick writing
  ops/loop/control/loop_items/*.json mid-suite tripped fleet_test_guard with
  a false error at a random teardown. ACCEPT: root cause named; the tick's
  own state files ignored via the kit's extra_ignore (no kit edit), stop
  sentinels still watched; regression test. DONE 2026-11-17: the kit IGNORE
  list has no AL loop-state paths; tests/conftest.py LOOP_TICK_STATE passes
  loop_items/*, loop_inbox_watch, loop_orders, backoff, gate_verdicts,
  push_worker, push_last, ledger_rotate as extra_ignore;
  tests/test_guard_loop_state.py pins it to tools/loop_base.py. ZERO-CLICK:
  test-only, no user step.
- [x] TEST-E2E (build) Synthetic end-to-end harness: replay a generated
  Client.txt session (zones, level-ups, deaths, whispers, trades, rotation /
  truncation, partial lines, non-ASCII names, a file near the 32 MB resume
  cap) into a running core and assert snapshot / SSE output; fix what it
  breaks. ACCEPT: stdlib harness test green, defects fixed with tests.
  DONE 2026-11-17: tools/synth_client.py (generator + CLI) and
  tests/test_e2e_replay.py (7 tests: HTTP consent, SSE events, odd-chunk
  UTF-8 splits, BOM-only log, truncate / replace / delete-recreate, partial
  line, 34 MB file resume). Defects fixed: (1) an unterminated line grew the
  tailer buffer without bound (NUL padding after a crash) - capped at
  logfile.MAX_PARTIAL, dropped to its next newline; (2) a consented core
  that found no Client.txt at start never tailed until a re-consent, and a
  discovered log whose Steam library moved was never followed -
  Core.ensure_tailing() from the core loop, every 5 s. ZERO-CLICK: runs
  inside pytest; the fixes need no user step.
- [x] TEST-HTTP (build) HTTP / SSE surface robustness: token, Host / Origin,
  oversized and malformed requests, many and slow SSE clients, core restart
  under the keepalive supervisor. ACCEPT: tests green, defects fixed.
  DONE 2026-11-17: tests/test_http_robust.py (22 tests). Defects fixed in
  server/al/http.py: (1) no socket timeout - an idle client, a body shorter
  than its Content-Length or a stalled SSE reader pinned a thread forever
  (Handler.timeout = REQUEST_TIMEOUT_S 10 s); (2) a garbage request line or
  a 64 KB+ URI crashed log_message (no self.path yet) so the client got no
  400 / 414; (3) deeply nested JSON raised RecursionError and the client got
  no reply (now 400); (4) unbounded SSE streams - capped at MAX_SSE_CLIENTS
  16, a refused stream gets a closed 200 with retry 30 s (an EventSource
  gives up for good on 503) ; handler errors go to the core log. Core
  restart under the supervisor stays covered by tests/test_keepalive.py
  end-to-end. ZERO-CLICK: runs inside pytest, no user step.
- [x] TEST-OVL (build) Overlay smoke and budgets: tests/test_budgets.py and
  the overlay smoke test assert something real and pass. ACCEPT: each
  budget test fails when its budget is broken. DONE 2026-11-17: the
  "overlay smoke test" CLAUDE.md names did not exist as a test (only the
  manual AL_OVERLAY_SMOKE_S quit timer). tests/test_overlay_smoke.py: static
  checks of the window flags, no input / no timers / no animation, always
  on; a live run (opt-in AL_OVERLAY_SMOKE=1, isolated profile) asserting
  summed working set < 250 MB, idle CPU < 1 percent, rc 0 - measured
  2026-11-17: 2 processes, 142.6 MB, 0.000 percent. test_budgets.py adds the
  whole-core idle budget (tailer + HTTP + 2 SSE streams < 1 percent; the old
  test covered only the tailer at 2 percent). ZERO-CLICK: static part runs
  in every suite; the live part is one env var.

## Ops

- [x] LOOP-ARM (build) Arm the lane loop as a scheduled task (every 15 min,
  IgnoreNew, hidden) after one supervised dry-run tick and one real tick on a
  trivial row. ACCEPT: task read back; first tick's progress file done.
  DONE 2026-11-17. Preconditions read back: route valid (kit read_route, 4
  accounts), base URL var present (check_url ok), lanes.json readable, no
  HALT. Dry-run tick: loop.json status done. Real tick on FLAKY-EVAL-API
  (work list narrowed to that row by a driver over the stock Tick; the CLI
  has no row filter): lane-0 status done, lane + review usage lines in
  headless_usage.jsonl, merged 9181d6f (verifier PASS, refute 0/3), closing
  tick loop.json status done. Task read back (schtasks /Query /V):
  \AshLightOps\LaneLoop, Ready, Enabled; trigger one-time 2026-11-17 8:18
  AM repeating every 15 min, no end; action pythonw.exe
  "<repo>\tools\al_loop.py" tick, start in the repo root; Interactive only
  (no stored password); IgnoreNew. Hidden = pythonw + CREATE_NO_WINDOW (no
  console); the XML Hidden flag stays false so the task shows in Task
  Scheduler.
- [x] FLAKY-EVAL-API (build) tests/test_tc_eval_api.py:: -- done 2026-11-17 (loop; refute 0/3 PASS)
  test_endpoints_need_token_host_origin failed once with a connection error
  under the full suite on 2026-11-17 and passed when rerun; find and fix the
  race (suspects: the server answers 401 / 400 / 403 / 413 before reading
  the request body and closes, so the client sees a reset; or the
  serve_forever thread is not yet polling). ACCEPT: root cause named in the
  commit; the test passes 50 runs in a loop and under the full suite; no
  sleep-based fix. ZERO-CLICK: test-only / server fix, no user step.
- [ ] WT-SIDECAR (build) Harness Agent-tool worktree isolation creates
  worktrees under the repo's .claude/worktrees/, but the Sidecar rule puts
  them under the AL sidecar Worktree folder. Finding: .claude/worktrees/ IS
  gitignored (.gitignore line 37), so nothing leaks into commits; the
  violation is placement only. Fix: a WorktreeCreate hook in
  .claude/settings.json that creates the worktree at
  server/al/paths.py's Worktree path (kit fleet_lanes.worktree_path), or
  harness config pointing worktrees at the sidecar; whichever the harness
  supports. Also note: the isolation hook blocks a worktree agent from
  merging into main, so the main checkout merges its branches (ff-only via
  fleet_gitlock). ACCEPT: a fresh isolated agent's worktree resolves under
  the sidecar Worktree dir; tests/test_sidecar_paths.py still green.
  ZERO-CLICK: the hook fires on every isolated spawn; no manual move.
  PARTIAL 2026-11-17: hook ready; activation = operator act. Decision
  0012: tools/wt_sidecar_hook.py (WorktreeCreate + WorktreeRemove) makes
  the worktree at server/al/paths.py worktree_dir()/<name>, tested on a
  tmp repo (tests/test_wt_sidecar_hook.py). Operator adds to
  .claude/settings.json "hooks": "WorktreeCreate" and "WorktreeRemove",
  each [{"hooks": [{"type": "command", "command": "python
  \"$CLAUDE_PROJECT_DIR/tools/wt_sidecar_hook.py\""}]}], then checks one
  isolated spawn lands under the sidecar Worktree dir.
- [x] LEAK-WT (build) The commit hook's leak sweep reports DEGRADED in agent
  worktrees: config/local.json and config/leak_needles.json are gitignored
  and absent there. Fix: tools/leak_sweep.py resolves the main checkout via
  `git rev-parse --git-common-dir` and reads its needle config when the
  worktree has none, so the sweep runs ARMED in worktrees. ACCEPT: a commit
  in a linked worktree prints ARMED with the main checkout's needle count; a
  test on a tmp repo + linked worktree covers it. ZERO-CLICK: the hook finds
  the config itself on every worktree commit; no copy step.
  Done 2026-11-17: resolve_config() in tools/leak_sweep.py (worktree
  config wins, else main checkout); run line names config=<source>;
  tests/test_leak_sweep.py tmp repo + linked worktree.
- [x] PUB-NAME (review) Manual poe2wiki check that "Ashlight" is not a GGG
  proper noun (decision 0001). Done 2026-11-17: 0 hits on both wikis
  (research 0009).
## Audit 2026-11-17 (docs/audit/2026-11-17-audit.md)

Low findings filed by AREA-AUDIT; the medium ones were fixed in the audit
merge. Each row names the finding ids it closes.

- [ ] AUDIT-TC-CODE-REAL (review) Re-open the real-code check (finding C1):
  TC-CODE-REAL was flipped done with only a skip-when-absent harness
  (tests/test_tc_code_real.py skips; tests/fixtures/pob2_real holds a README
  only). ACCEPT: one real PoB2 export decodes, parses and round-trips
  through the harness (no skip), owner consent recorded if kept as a
  fixture. BLOCKED: operator act (supply one real PoB2 code).
  ZERO-CLICK: the harness runs by itself once the file exists.
- [ ] AUDIT-HTTP-HARDEN (build) Findings S1-S4: HEAD /events streams a body
  forever (http.py do_HEAD -> do_GET -> _sse); Handler has no socket
  timeout (an idle connection holds a thread); ?token= is accepted on every
  /api route (restrict it to /events, the only EventSource route);
  POST /api/consent "path" accepts any file or UNC path (refuse UNC and
  names other than Client.txt / a folder holding it). ACCEPT: one test per
  item. ZERO-CLICK: code row.
- [ ] AUDIT-EXE-PATH (build) Finding S5: gfx.py runs bare "powershell.exe"
  and tc_pin.py bare "cmd.exe" / "mingw32-make" (Windows CreateProcess also
  searches the current directory); use the System32 absolute path for the
  Windows tools, and TC-BRIDGE must hash-check luajit.exe before every
  exec (tc_pin.ensure_luajit trusts any existing luajit.exe). ACCEPT:
  tests on the argv. ZERO-CLICK: code row.
- [ ] AUDIT-ELECTRON (build) Findings S6-S7: devTools follow
  !app.isPackaged, and the overlay is never packaged, so they are always
  on (gate on an AL_DEV env instead); add
  session.setPermissionCheckHandler(() => false) next to the request
  handler. ACCEPT: a main.js source test for both. ZERO-CLICK: code row.
- [ ] AUDIT-SNAPSHOT-OPTIN (review) Finding T1: scripts/build.ps1 runs the
  game-data snapshot by default (opt-out, decision 0009) while CLAUDE.md
  Settled says nothing hits the network while web_data is off (decision
  0013). Adjudicate one rule (build step honours web_data, or 0013 states
  the build-time exception) and record it. ACCEPT: decision amended and
  build.ps1 / README match. ZERO-CLICK: ruling row.
- [ ] AUDIT-TREE-URL (build) Finding S8: web/tc.js safeUrl lets a pasted
  build's tree URL be any https host as an "Open the tree" link. Allow
  only known tree hosts (pathofexile.com, poe2db.tw, poeplanner-style
  hosts after a check) or show the host name in the link text. ACCEPT:
  app test with an off-list host. ZERO-CLICK: code row.
- [ ] AUDIT-HYGIENE (build) Findings H2-H6: tests/test_ascii_lf.py checks
  a suffix list (skips .log, .vbs, .sh, .xml, .svg, LICENSE) - check every
  non-binary tracked file; server/al/paths.py SIDECAR_SUBDIRS lacks
  Scratch and ClaudeHistory and all_runtime_paths() omits worktree_dir()
  and the overlay profile; tests/test_sidecar_paths.py SCANNED skips
  tools/; AL-NEXT-SESSION.txt spells the sidecar with a drive letter (use
  <sidecar>); decision 0002 should name pytest as the one allowed test
  dependency. ACCEPT: tests for the first three. ZERO-CLICK: code row.
- [ ] AUDIT-LOOP-COMMIT-MSG (build) Finding C2: loop merge commits carry the
  row text cut mid-sentence plus refute / verifier lines, so an ACCEPT that
  says "root cause named in the commit" (FLAKY-EVAL-API, 5e7b30e) is not
  met by the commit. Carry the lane's result line (root cause / what was
  done) in the commit body. ACCEPT: tools/loop_merge.py test on the
  message. ZERO-CLICK: code row.

- [ ] OPERATOR: create the GitHub remote when the operator wants to publish
  (then lift the pre-push refusal in the same change, CI workflow with the
  kit's fleet_identity_guard.yml as a required check).
