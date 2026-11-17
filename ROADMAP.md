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
  accepted, hideout scene names, cruel `C_G<n>_` / interlude `P<n>_` area
  id prefixes (acts.act_of, decision 0020). ACCEPT: every event type seen live has a
  fixture and a passing test. Needs the operator to play past the whisper
  level, die once, and receive one trade whisper. BLOCKED: operator act
  (in-game play, hand-off OPERATOR act (b)); the loop skips it until then.
  LIVE CHECK 2026-11-17 (AREA-TEST batch 3, game 0.5.5g launched from Steam
  while the core ran, login screen only): consent + tailing VERIFIED live,
  new lines picked up, "(unknown)" scene kept as transient VERIFIED, opening
  marker shape VERIFIED with no prefix. WRONG: the live marker was ignored,
  so the old run's zone / area / zone timer stayed (fixed: TEST-LIVE-RESTART).
  NOT REACHED: login, character select, zone / level / act in a fresh run
  (TEST-LIVE-CLICKS); game exit / idle state (TEST-LIVE-EXIT). Overlay
  drew nothing on the desktop capture (known setOpacity bug, UX-REAL-OVERLAY
  merge pending).
- [x] TEST-LIVE-RESTART (build) A game start while the core runs must void
  the previous run's zone. ACCEPT: the opening marker parses to
  `log_opened`; it clears zone, area, zone timer, hideout, AFK / DND, keeps
  character / level / counts and pauses an open map clock; sanitized
  fixture tests/fixtures/client_live_restart.txt. ZERO-CLICK: automatic on
  the next log line.
- [x] TEST-LIVE-EXIT (build) Killing the game (by PID, 2026-11-17) wrote no
  log line; the dashboard kept the old zone and its timer running. ACCEPT: a
  verified clean-quit log line (operator quits normally once) mapped to an
  idle state with a fixture test, or an adjudicator ruling on whether a
  game-process presence check (no memory read) fits decision 0003.
  ZERO-CLICK: idle shows by itself when the game ends. DONE 2026-11-17
  (decision 0029, adjudicator: log staleness only, no process check): 20
  min with no line (mtime-seeded at start) sets `tailer.idle`; zone kept
  and tagged "frozen - log quiet", zone / act / map clocks frozen at the last line,
  the session summary card closes (reason idle); the next line clears it.
  tests/test_live_exit.py, app dashboard / shared tests. A verified quit
  line (firm "closed") stays a refinement once the operator quits once.
- [ ] TEST-LIVE-CLICKS (build) The live check lane had no desktop-control
  tool, so Login and character select were not clicked (no input synthesized
  from PowerShell). ACCEPT: one live run reaching the hideout / town with
  zone, character, level, act and session timer read back from /api/state.
  BLOCKED: operator act (log in once while the core runs) or a desktop-tool
  grant to the lane. ZERO-CLICK: the read-back is scripted.
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
- [x] HUD-ACT-RESUME (build) Act splits survive a core restart: LIVE-RESUME
  (decision 0008) also returns the current run's area-generation ids with
  their line timestamps, so the splits rebuild from Client.txt instead of
  starting empty and partial. ACCEPT: restart mid-act keeps earlier act
  times; exact tests. ZERO-CLICK: rebuilt at core start. DONE 2026-11-17
  (area-util): lane WIP 19d548d redone on main, decision renumbered 0023,
  tests/test_hud_act_resume.py (9). The cruel `C_G<n>_` / interlude `P<n>_`
  prefix check moved into LIVE-1: the live Client.txt holds Act 1 ids only.
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
- [ ] FLOOR-STATIC-SCAN (review) Test-backed ToS floor scan beyond the overlay smoke test: tests/test_floor_static.py greps server/, tools/, scripts/ and app/ for input / memory / screen-capture APIs (SendInput, SendKeys, keybd_event, mouse_event, ReadProcessMemory, WriteProcessMemory, CopyFromScreen, ImageGrab, DXGI hooks) and for clipboard reads outside the hotkey handler. ACCEPT: the test fails when such a call is planted in a temp copy, passes on the tree, allow-list entries name a reason (research 0026).
- [ ] POLICY-WORDING-WATCH (review) After the 1.0 notes (2026-12-11) and each developer-docs changelog entry, re-read the overlay / macro wording and diff it against the quotes in research 0001. ACCEPT: research 0001 or a new 0027 records the diff or "unchanged" with source URL and date; CLAUDE.md floor proposals go to MAIN, never self-edited.

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
  AUDIT pass 2: ACCEPT not met (live tests skip); see AUDIT-TC-BRIDGE-LIVE.
  TC-LIVE 2026-11-17: ACCEPT met (bridge = pinned GUI within 0.1 percent).
- [x] TC-DELTA (build) PoB-backed evaluation: DPS and EHP delta of the -- done 2026-11-17 (loop; refute 0/3 PASS)
  clipboard item vs the equipped one, and per-mod weights from PoB deltas
  (offence and EHP) feeding TC-UPGRADE in place of hand weights. After
  TC-BRIDGE, TC-EVAL. ACCEPT: delta tests on fixtures; falls back to stat
  weights with a visible notice when the component is off.
  ZERO-CLICK: deltas recompute on item or build change, no Calculate button.
  AUDIT pass 2: not wired (core.tc_calc stays None); wired since by
  AUDIT-TC-WIRE (AREA-MATH b2, calcwire.py).
- [x] TC-DRIFT (review) On each PoB-PoE2 release: run the bridge tests
  against the new tag, then move the pin in one commit, or hold it and
  record why. ACCEPT: pin moved or a dated hold note in decision 0004.
  ZERO-CLICK: a loop check spots the new tag and runs the tests unattended.
  DONE 2026-11-17 (area-math): HOLD, pin current; latest release v0.23.1
  (7d6f530c) and LuaJIT v2.1 head 63c8f1a9 both equal config/tc_pins.json,
  read back from the GitHub API; dated note in decision 0004 "Pin log".
  Re-open on the next PoB-PoE2 v0.* release.
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

### Math (non-engine; area-math lane, 2026-11-17)

Legitimate math around PoB interop, never an own damage / EHP calc engine
(decision 0004): parsing, normalisation, value and codec robustness. Stat
weights derived from PoB outputs stay with TC-DELTA.

- [x] MATH-ITEM (build) Item-mod parsing and stat-key normalisation
  robustness: fixtures over many item classes (weapon, normal / magic /
  rare / unique, flask, charm, shield, focus, quiver, gem, waystone,
  socketable, unidentified, corrupted, quality, rune sockets, CRLF + BOM),
  signed roll ranges "(-20--10)", PoB bare ranges "+(40-60)" read at
  {range:r} (default midpoint, half away from zero to the endpoints'
  places), flask / charm property lines kept out of mods, flavour / help
  text (full stop) never a mod, hybrid-line sign from the first governing
  word. ACCEPT: tests/test_math_item.py incl. stdlib property tests (random
  text, fixture mutations, idempotent keys) green.
  ZERO-CLICK: parsing runs on the existing hotkey press; tests unattended.
  DONE 2026-11-17: server/al/theorycraft/item.py (strip_rolls,
  resolve_range), weights.stat_key; magic bases: MATH-MAGIC-BASE.
- [x] MATH-CODEC-FUZZ (build) Property / fuzz tests for the PoB2 share-code
  codec: random XML round trips byte-exact under every framing, URL-safe
  and padded / unpadded / whitespace-wrapped codes, truncation and bit
  flips raise CodeError only (never another exception), deflate-bomb cap.
  ACCEPT: stdlib-only tests with fixed seeds; any defect found fixed.
  ZERO-CLICK: tests run unattended in the suite.
  DONE 2026-11-17: tests/test_math_codec_fuzz.py (19 tests, ~4k cases);
  no codec defect found, codec.py unchanged.
- [x] MATH-VALUE (build) Price-per-stat value math on poe.ninja rates:
  parse the item's own Note price ("~price 5 exalted", "~b/o 1/2 divine"),
  convert any currency to the primary via the cached rates (cross rates,
  missing / zero rate -> no value, never a guess; stale rates carry the
  snapshot's stale flag), and score per primary
  unit for the evaluated item. ACCEPT: pure-function tests on synthetic
  rates; no network; decision 0013 (web data off -> cached or nothing).
  ZERO-CLICK: computed on the same hotkey press from cached rates.
  DONE 2026-11-17: server/al/theorycraft/value.py (parse_note_price,
  to_primary, convert, per_unit, value_of; 6 significant figures); the item
  check card (LastEval) carries `value` from core's cached rates snapshot,
  no request; tests/test_math_value.py incl. cross-rate round-trip and
  transitivity properties. Dashboard display is MATH-VALUE-UI.
- [x] MATH-MAGIC-BASE (build) A magic item's true base type: the name
  line "Hale Iron Ring of the Bear" keeps its affix words as the base, so
  the trade / upgrade links searched a type that does not exist. Resolve
  from the build-time snapshot base list when cached (decision 0009), else
  the advanced headers' affix names, else a shape strip (" of ..." suffix,
  a leading prefix word when the explicit mod count says there is one).
  ACCEPT: tests over many item classes, with and without the snapshot.
  ZERO-CLICK: runs on the same hotkey press; the core reads the cached
  list, no fetch.
  DONE 2026-11-17: server/al/theorycraft/basetypes.py (magic_base,
  NamesCache over <cache>/gamedata/base_items.json), item.parse sets
  name = the magic line, base = the true base, base_source; core registers
  the cache; tests/test_math_magic_base.py.
- [x] MATH-VALUE-UI (build) Show the item check card's `value` on the
  dashboard Item check card: "Listed 4 Exalted Orb = 0.008 Divine Orb,
  2,500 score per Divine Orb", the rates' stale state and the poe.ninja
  credit; nothing when `value` is null. After MATH-VALUE. ACCEPT: web test
  on a synthetic card; design-reviewer pass.
  ZERO-CLICK: appears with the item check of the same hotkey press.
  DONE 2026-11-17: web/prices.js valueView + "Price and points" box in the
  Item check card (web/index.html #valuebox, web/app.js); honest no-rate
  sentences; app/test/prices.test.js; design-reviewer PASS WITH FINDINGS
  S3=1 S4=2, all fixed (docs/design/reviews.log, section 9 templates).
- [x] MATH-WEIGHTS (build) Stat weights from PoB outputs kept per build:
  TC-DELTA probes every stat key through the PoB calc on each check (one
  PoB run per key, up to 24 per slot); keep PoB's per-mod weights per
  build / slot / carrier / blend so a re-check probes only new keys, and
  when the optional calc is off or fails score with the weights PoB
  measured earlier for the same build (never another build's), with the
  off / failed notice. ACCEPT: fake-calc tests (probe counts, keying,
  outage fallback, thread safety); weights stay PoB's own numbers.
  ZERO-CLICK: automatic on every check and re-score.
  DONE 2026-11-17: server/al/theorycraft/pobweights.py (PobWeightCache,
  in memory, LRU 64); evaluate(cache=) and LastEval; calc.source
  "pob_cached" with state.CALC_CACHED_TEXT; upgrade weights source passes
  it through; tests/test_math_weights.py. Known limit: memory only, so a
  restart with the calc off falls back to the hand weights.
- [x] MATH-POTENTIAL (build) Ranged-roll potential of a checked item:
  keep each value's roll range from advanced / PoB item text, where each
  roll sits in its range, and the item score now vs at the worst / best
  rolls under the weights that scored it (a "reduced" mod is best at its
  small end for a positive weight). Display math on stated numbers, no
  game mechanic (decision 0004). ACCEPT: stdlib tests incl. random ranged
  lines (worst <= score <= best, JSON-safe).
  ZERO-CLICK: computed on the same hotkey press.
  DONE 2026-11-17: item.Mod.ranges + item.roll_ranges;
  server/al/theorycraft/potential.py (roll_pct, mod_potential,
  item_potential); evaluate() `potential`, live.compact carries score /
  worst / best / pct; tests/test_math_potential.py. Equipped-vs-checked
  compare with PoB deltas was already TC-DELTA's per-slot comparisons
  (dps / ehp on each compared slot), so no separate MATH-COMPARE row.
- [x] MATH-POTENTIAL-UI (build) Show the item check card's `potential` on
  the dashboard: "Rolls: 51% of the way from the worst to the best rolls
  (score 58, best 84)" or similar; nothing when null. After
  MATH-POTENTIAL. ACCEPT: web test on a synthetic card; design-reviewer
  pass. ZERO-CLICK: appears with the item check of the same press.
  DONE 2026-11-17 (area-util batch 3): web/tc.js rollsText (evalView
  `rolls`), #eval-rolls on the item check card; hidden for a failed check,
  junk numbers or no spread; app/test/tc_view.test.js.
- [x] MATH-NUM (build) Numeric edge cases of scoring: score / delta /
  verdict-band properties (antisymmetry of the delta, band monotone in the
  old score, rounding stable at 4 places, NaN / inf / huge values from a
  weights file or item never crash or flip a verdict), ring best-slot pick
  ties deterministic. ACCEPT: stdlib property tests; defects fixed.
  ZERO-CLICK: tests run unattended in the suite.
  DONE 2026-11-17: defect fixed - a huge roll ("+999...9 to maximum Life")
  made the score inf and the eval JSON invalid (Infinity); now a value past
  1e9 or non-finite is no value (weights.MAX_VALUE, item._number), score
  skips non-finite terms, verdict on non-finite input is sidegrade, _clean
  maps non-finite to 0. tests/test_math_num.py.
- [x] MATH-E2E-LIVE (build) Prove the theorycraft path on real data: test
  core (port 8961-8979, temp config "tc_calc": true), the real reference
  build via POST /api/build-code, PoE2 copy-format items via POST
  /api/eval; card deltas from PoB, sane, in budget, graceful when the calc
  is killed. ZERO-CLICK: live tests run in the suite wherever the
  component and reference exist, skip elsewhere.
  DONE 2026-11-17 (AREA-MATH b3, decision 0028): tests/test_math_e2e_live.py
  + tests/math_live_items.py. Base DPS / EHP on the card = PoB GUI (39265 /
  32072); ring upgrade +2.7 % DPS +3.2 % EHP, amulet sidegrade, bow
  downgrade -53 % DPS, body upgrade +10.3 % EHP; presses 12.4 s cold, 3.6
  to 5.5 s warm, 1.3 s repeat; killed calc -> 200 + "failed" notice in
  0.5 s, next press PoB again.
- [x] MATH-PERF (build) Bridge latency (cold start, warm item check,
  reload) and LuaJIT memory; budget in decision 0024 and a ceiling test.
  ZERO-CLICK: the budget test runs unattended in the suite.
  DONE 2026-11-17 (decision 0028, 0024 R7): cold 1.2 s, load 0.4 s,
  reload 0.3 s, set_item+outputs 0.1 s; luajit.exe working set reached
  ~900 MB over repeated reloads (heap garbage, not a leak), now a full GC
  past a 384 MB Lua heap in bridge.lua load_build: peak 511 MB, no median
  cost. tests/test_math_perf.py (budgets tests/tc_live_util.py).
- [x] MATH-POB-DRIFT-GUARD (build) Fail loudly when the pinned PoB
  checkout's API shape that bridge.lua relies on changes (launch object,
  HeadlessWrapper, output keys), so TC-DRIFT pin moves are safe.
  ZERO-CLICK: runs in the suite and in every TC-DRIFT trial.
  DONE 2026-11-17 (decision 0028): tests/test_tc_pob_drift_guard.py - 23
  static shape rows read from the checkout, a meta-test that every PoB
  method bridge.lua calls is guarded, a live launch + output-key check;
  each failure names file, shape and the fix.
- [x] MATH-COMPARE (build) Equipped vs checked item on the card: which
  equipped item the swap replaces and PoB's DPS / EHP delta of it; for
  rings and a one-hand weapon of a dual wielder the better slot is the
  headline and the other slot keeps its own PoB line. ZERO-CLICK: same
  hotkey press. DONE 2026-11-17 (AREA-MATH b4, decision 0032):
  evaluate.slots_for_build (Weapon 2 when it holds a weapon, not a
  shield / buckler / focus / quiver), state.eval_card_text names the
  replaced item and adds comparisons[].calc, web/app.js shows it;
  tests/test_math_compare.py; design-reviewer pass.
- [x] MATH-DPS-SANITY (build) PoB outputs that make no sense for the card
  (NaN, negative DPS / EHP, zero EHP, an attack build at 0 DPS after a
  swap) never show as a number: "Path of Building's numbers for this
  item don't add up", scored with the weights. ZERO-CLICK: automatic on the
  press. DONE 2026-11-17 (AREA-MATH b4, decision 0032):
  delta.CalcImplausible, calc notice "implausible";
  tests/test_math_dps_sanity.py.
- [x] MATH-WEAPON-TYPE (build) A weapon the main skill cannot use (PoB's
  own disableReason, read through the bridge) reads "Your main skill
  can't use this weapon type" as a downgrade, not -100 % and not the
  "don't add up" fallback. ZERO-CLICK: automatic on the press. DONE
  2026-11-17 (AREA-MATH b5, decision 0032 amendment): bridge "main_skill",
  calcwire.WEAPON_REASONS, delta.CalcWeaponUnusable, calc notice
  "weapon_type"; tests/test_math_weapon_type.py (live leg skips without
  the calc component); design-reviewer pass.

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
- [x] PRICE-UNIQUE (build) Unique prices on the item-check press from
  poe.ninja `/poe2/api/economy/stash/current/item/overview` (Unique*
  types, research 0019): match name + baseType (+ corrupted), show value,
  listing count ("few listings" when low) and 7-day trend; one request
  per type per hour with If-None-Match, only with web_data on (0013).
  ACCEPT: parser tests on a trimmed real body; no request when off.
  ZERO-CLICK: the same hotkey press; overviews refresh on the hourly gate.
  DONE 2026-11-17: server/al/pricebook.py PriceBook (driven by
  RatesClient.refresh: same opt-in, contact, UA, league; per-type hourly
  gate + ETag, cache book.json), RatesClient.lookup on the press (cache
  only), card `ninja` part + state.ninja_text; tests/test_price_book.py.
- [x] PRICE-STACKABLES (build) Price stackables on the item-check press via
  more exchange overview types (Ritual/Omens, Essences, Runes, SoulCores,
  Breach, Delirium, Fragments, UncutGems, LineageSupportGems; research
  0019), names from the top-level `items` array (0013). After
  PRICE-UNIQUE (both edit ninja.py). ACCEPT: per-type parser tests; one
  request per type per hour. ZERO-CLICK: same press, hourly refresh.
  DONE 2026-11-17: 13 exchange types (research 0019 list) in the price
  book; Currency itself from rates.json by name; one failing type never
  stops the rest; tests/test_price_book.py.
- [x] UTIL-1.0-READY (build) PoE2 1.0 (2026-12-11, research 0018): add
  Acts 5-6 id prefixes to acts.py, Duelist / Shadow class names, league
  rollover check in ninja.py and the price card league label, refresh the
  repoe-fork snapshot; after launch review the debug sink of the first 1.0
  log for new system lines. ACCEPT: tests with 1.0-shaped fixture lines;
  rollover test. ZERO-CLICK: data and parser only, nothing for the user.
  DONE 2026-11-17 (pre-launch part): G5_/G6_ read as Act 5/6, unknown ids
  and class names change nothing (tests/test_util_10_ready.py, 1.0-shaped
  lines); charjson.BASE_CLASSES adds Duelist / Shadow; ninja league re-
  read every 6 h and within the hour after a 404 / empty overview; trade
  links and the price card label follow the cached poe.ninja league while
  web data is on (Core.trade_league, decision 0026). OPEN after launch:
  refresh the repoe-fork snapshot for Act 5/6 zone levels and review the
  first 1.0 log's debug sink (filed as UTIL-1.0-POST).
- [ ] UTIL-1.0-POST (build) After PoE2 1.0 launches (2026-12-11): refresh
  the repoe-fork world_areas snapshot (build step) so Acts 5-6 get zone
  levels, add the 1.0 ascendancy names to charjson.ASCENDANCY_CLASS, and
  review the first 1.0 Client.txt debug sink for new system lines.
  Checklist (research 0021 section 3): (1) read the 1.0 patch notes for
  act / area / ascendancy names, chat, log and filter syntax changes;
  (2) fixture every new system line in the first 1.0 log's debug sink
  (Conquerors of Wraeclast battles / stronghold, Acts 5-6 scenes, any
  death summary); (3) confirm the Act 5 / 6 and return-to-Oriath area-id
  prefixes live, fix acts.act_of if not G5_ / G6_; (4) refresh the
  repoe-fork world_areas snapshot; (5) add the 1.0 ascendancies
  (reported Assassin / Infiltrator / Knight, UNVERIFIED) to
  charjson.ASCENDANCY_CLASS; (6) refresh the GGG tree export snapshot and
  re-run the id_match guard (passive tree overhaul); (7) confirm
  poe.ninja lists the new league first and the price label follows
  within 1 h; (8) on a PoB-PoE2 1.0 release run TC-DRIFT and bump
  config/tc_pins.json. BLOCKED: PoE2 1.0 not released yet (2026-12-11).
  ACCEPT: fixture lines from the real 1.0 log; zone table has G5 / G6
  rows; checklist items 1-7 ticked with read-back evidence. ZERO-CLICK:
  data and parser only.
- [x] TC-BUILDFILE (build) Export the loaded PoB build as a GGG Build
  Planner `*.build` JSON (Version 1, research 0018 section 3) offered as a
  dashboard "Save .build" download on the player's click; NEVER written
  into the game's BuildPlanner folder (adjudicator ruling 2026-11-17).
  First research the passive id mapping (GGG string ids like
  `strength89` vs PoB / GGG export numeric ids). ACCEPT: schema test
  against the documented fields; mapping source recorded; no write path
  to the BuildPlanner folder (test). ZERO-CLICK: the file is ready as soon
  as a build is loaded; one click to save is the user's placement act.
  DONE 2026-11-17 (AREA-MATH b6, decision 0034, research 0027): mapping
  source = the cached GGG tree export `id` (all 6 passive ids of GGG's
  example found in it), ascendancy = export ascendancy id, gems = PoB
  `gemId`; `server/al/theorycraft/buildfile.py` (export + validate), GET
  /api/buildfile attachment, `build_file` summary/notes in GET /api/build,
  dashboard "Save .build file" (web/app.js, web/tc.js buildFileView);
  unmapped parts dropped with a visible note; tests/test_tc_buildfile.py,
  app/test/tc_view.test.js; design-reviewer PASS WITH FINDINGS, all fixed.
  Follow-up TC-BUILDFILE-LIVE.
- [ ] TC-BUILDFILE-LIVE (build) Load an AshLight-made `.build` in game once
  and record whether it loads, which passives / gems show, and whether
  class-start or placeholder ids or meta gems are refused (research 0027
  UNVERIFIED). BLOCKED: needs the player to place the file and open the
  game. ACCEPT: read-back note in research 0027; mapping fixed if refused.
  ZERO-CLICK: one-time check.
- [x] AUDIT-BUILDFILE (review) Record the `.build` ruling (user-saved
  only, never written into the game folder; reverses if GGG explicitly
  permits tool writes there or the operator rules a click write
  acceptable) as a decision when TC-BUILDFILE lands, and add a test-backed
  check that no code path writes under the BuildPlanner folder. ACCEPT:
  decision file + test. ZERO-CLICK: review row.
  PARTIAL 2026-11-17 (AREA-AUDIT b2): the no-write check landed
  (tests/test_audit_buildfile.py: no source names the BuildPlanner or My
  Games folder). DONE 2026-11-17 (AREA-MATH b6): decision 0034 with both
  reversal clauses + CLAUDE.md Settled line; tests/test_tc_buildfile.py
  adds the generator / endpoint no-write checks.
- [x] UTIL-MOVERS (build) Dashboard "price movers" panel from the cached
  poe.ninja overviews (`sparkline.totalChange`), no extra requests. After
  PRICE-STACKABLES. ACCEPT: panel test, design-reviewer pass.
  ZERO-CLICK: refreshes with the hourly gate. DONE 2026-11-17:
  PriceBook.movers (5 risers / 5 fallers, thin markets out), `movers` in
  /api/rates (empty while web data is off), dashboard Price movers card
  (web/prices.js moversView); tests/test_price_book.py,
  app/test/prices.test.js.
- [x] UTIL-SESSION-SUMMARY (build) End-of-session summary card: time
  played, levels and hourly pace, maps, deaths, top price movers.
  ACCEPT: replay tests, design-reviewer pass. ZERO-CLICK: a play stretch
  closes by itself after 20 minutes with no game activity or when
  Client.txt starts a new game run (the previous game closed; no exit line
  is known). DONE 2026-11-17 (area-util batch 3): server/al/summary.py
  (Tracker, build, save / load_last), SessionState stretch +
  check_session_end, parser `log_opened` for the run marker,
  Core.tick_summary from the main loop, last 20 cards in
  ops/runtime/session_summaries.json (reloaded at start), dashboard
  "Last session" card (web/summary.js); tests/test_util_session_summary.py,
  app/test/summary.test.js.
- [x] UTIL-OVERLAY-MAP (build) Compact overlay HUD line for the open map:
  time in it and its deaths, under the overlay budgets. ZERO-CLICK: would
  show by itself while a map is open. NOT DONE BY DESIGN (adjudicator
  ruling 2026-11-17, area-util batch 3): design 0001 sections 7.2 and 10
  forbid a third HUD line ("2 HUD lines + one 3-line card"); map time and
  deaths this map stay on the dashboard Maps card. Alternatives: a
  conditional muted third line "This map 12m, 1 death" with 7.2 / 10
  amended (fits the 280x176 window with ~34 px spare, budgets passed), or
  folding it into row 2 (clips at the 258 px plate). Reverses if: the
  operator or MAIN allows a conditional third HUD line; the prototype is
  kept as util-overlay-map.patch in the AL sidecar Scratch folder.
- [ ] TC-CURX (build) Hourly exchange history from GGG's documented public
  Currency Exchange API (`web.poecdn.com/api/currency-exchange/poe2/<hour>`,
  research 0018). BLOCKED: TC-OAUTH-REG (adjudicator ruling 2026-11-17:
  standalone executables must use a public OAuth client; reverses if GGG
  exempts scope-less endpoints in writing). ACCEPT: when unblocked, OAuth
  UA, immutable-hour cache, parser tests. ZERO-CLICK: background fetch on
  the hourly boundary once enabled.

## Research-filed features, batch 2 (AREA-RES 2026-11-17, research 0022-0023)

Ranked in research 0023; loot filter ruling (adjudicator) in 0022 section 3.

- [x] UTIL-WAYSTONE (build) Waystone mod check on the item-check press:
  parse waystone clipboard text (tier, area level, mods) and flag mods
  dangerous for the loaded build (reduced recovery, no regen, extra
  element vs the build's weakest resistance, monster crit, ...) from
  AshLight-authored rules on mod text; one card line "Risky for this
  build: ..." (research 0023 item 1). ACCEPT: parser + rule tests on
  real-shaped waystone text; card copy via design-reviewer; no new read
  (same press). ZERO-CLICK: the existing item-check hotkey press; no
  extra button. DONE 2026-11-17 (area-util b5): theorycraft/waystone.py
  rule table (12 rules on PoB resist / life / ES numbers), eval.waystone
  on the card, decision 0030; tests/test_waystone.py. Real waystone text
  not yet checked live. VERIFIED 2026-11-17 (area-util b6, research 0025
  section 3) against the repoe-fork waystone mod pool in the sidecar
  snapshot: 5 rules matched no waystone mod (no regen, ES recharge, curse,
  reflect, projectiles) and were removed, monster_crit no longer flags
  "Monsters take reduced Extra Damage from Critical Hits", added
  penetration / bleed / ailments / speed; 11 rules, each matching real
  mods, fixtures in real wording. LIVE-WAYSTONE: one real Ctrl+C waystone
  text through the press (properties block, rolled-value shape).
- [x] UTIL-SEARCHSTR (build) Search-string builder on the dashboard: a
  stash / vendor search string (<= 250 chars, limit to verify in game)
  from the loaded build (wanted bases, resistances, life / ES) and from
  the waystone "avoid" set; "Copy" on the player's click (decision 0014
  clipboard write); never typed into the game (research 0023 item 2).
  After UTIL-WAYSTONE. ACCEPT: builder tests (length cap, escaping, OR /
  NOT syntax); no clipboard write without a click. ZERO-CLICK: strings
  rebuild by themselves when the build loads; the copy click is the
  player's act. DONE 2026-11-17 (area-util b5): theorycraft/searchstr.py
  (resists, life / ES, movement, gear bases, waystone NOT string from the
  UTIL-WAYSTONE rules), `search_strings` in GET /api/build, web/search.js
  card with Copy on click only (no live region); decision 0030. The 250
  limit and the regex syntax are still to verify in game. VERIFIED
  2026-11-17 (area-util b6, research 0025 section 1): 250 is GGG's limit
  since 0.5.0 (patch notes); `"a|b"` / `"!a|b"` matches the community-
  documented regex syntax; worst-case waystone string (no build) 249
  chars, no term dropped (test). LIVE-SEARCHSTR: confirm in game that a
  leading `!` negates the whole OR group.
- [x] UX-ZONE-NOTES (build) Zone notes while levelling: on each campaign
  `[SCENE]` / area line show one short AshLight-authored note (objective,
  quest reward to take) in the overlay status slot and the dashboard act
  card; notes in a tracked data file written by us (no poe2db / wiki
  prose, decision 0009); Acts 5-6 after 1.0 (UTIL-1.0-POST) (research
  0023 item 3). ACCEPT: data-file schema test, every Act 1-4 zone id in
  the repoe-fork snapshot has a note or an explicit skip, design-reviewer
  pass. ZERO-CLICK: appears by itself on zone entry. DONE 2026-11-17
  (area-util b5), dashboard only: server/al/data/zone_notes.json (own
  notes for Acts 1-4 by zone name, act defaults for G1-G4, P1-P3 and
  Cruel), server/al/zonenotes.py, snapshot `zone_note`, "Zone note:" line
  in the Act times card; decision 0030. Not done: the overlay word (the
  2-line HUD rule, design 0001 7.2 / 10, has no free slot); notes not yet
  checked in play. VERIFIED 2026-11-17 (area-util b6, research 0025
  section 3): with the world_areas snapshot fetched, every Act 1-4 and
  Interlude id resolves (test runs, no longer skipped); 3 Act 2 names
  fixed ("The Ardura Caravan", "The Dreadnought's Wake", "Dreadnought");
  a new test ties every zone-keyed note to a snapshot area name. No Cruel
  ids in the snapshot (act default kept). LIVE-ZONE-NOTES: check that the
  [SCENE] names equal the snapshot names in play.
- [x] UTIL-FILTER (build) Loot filter snippet: generate an AshLight-original
  `ashlight.filter` (price tiers from the cached poe.ninja overviews,
  bases / gems of the loaded PoB build) offered as a dashboard download;
  the player saves it and adds `Import "ashlight.filter" Optional` to
  their own filter; optional merge into a filter the player hands over via
  the browser file input, returned as a download (upload body in memory
  only, path never stored). NEVER written into My Games (adjudicator
  ruling, research 0022 section 3; reverses if GGG permits a filter-folder
  write or forbids filter tools). After TC-BUILDFILE (same save pattern).
  ACCEPT: syntax tests against the documented filter grammar; test that
  no code path writes under My Games; decision file recording the ruling.
  ZERO-CLICK: regenerated by itself on the hourly price refresh and on
  build load; one save click is the player's placement act. DONE
  2026-11-17 (area-util b5), base highlight part: theorycraft/
  lootfilter.py, GET /api/filter (attachment, no file written), dashboard
  "Download ashlight.filter" button, decision 0031, grammar and no-write
  tests. Price tiers and the merge moved to UTIL-FILTER-2. VERIFIED
  2026-11-17 (area-util b6, research 0025 section 2): every keyword and
  range is in GGG's filter reference (PoE2 shares the grammar); no Class
  condition is used; with the snapshot base list cached, base names the
  game data does not know are left out (an unknown BaseType breaks the
  filter). LIVE-FILTER: load the downloaded file through the Import line
  in game once.
- [x] UTIL-FILTER-2 (build) Loot filter, part 2: price-tier blocks from
  the cached poe.ninja overviews in ashlight.filter, and the optional merge
  into a filter the player hands over via the browser file input (upload
  body in memory only, path never stored, merged copy returned as a
  download) (decision 0031). ACCEPT: grammar tests, no stored path, no
  game-folder write. ZERO-CLICK: tiers refresh with the hourly price
  refresh; the save is the player's click.
  PRICE TIERS DONE 2026-11-17 (AREA-MATH b4, decision 0032):
  ninja.RatesClient.filter_prices (cache only, web data on), lootfilter
  tiers (top >= 1 Divine Orb, worth picking >= 0.05; unique base by its
  cheapest well-listed unique; never Hide); GET /api/filter passes them;
  tests/test_lootfilter_tiers.py. Remaining: the optional merge.
  MERGE DONE 2026-11-17 (area-util b7, decision 0033, adjudicator: within
  the floor): lootfilter.merge / check_text / out_name, POST
  /api/filter-merge (raw bytes, 2 MB, UTF-8 text; marked AshLight section
  first, player's bytes identical, CRLF and BOM kept, an earlier section
  replaced), dashboard file input (web/filtermerge.js) saving
  <name>-ashlight.filter; tests/test_lootfilter_merge.py,
  app/test/filtermerge.test.js. LIVE-FILTER-MERGE: merge a real filter
  (e.g. a NeverSink file) and load it in game once.

## Research-filed features, batch 3 (AREA-RES 2026-11-17, research 0028)

Ranked in research 0028; floor rulings (adjudicator 2026-11-17) in its
section 6. Phone view over the LAN is an OPERATOR decision (CLAUDE.md:
LAN access stays off), not a row.

- [ ] MATH-BUILD-HEALTH (build) Build health card from the loaded build's
  PoB-exported PlayerStat values only: each element resist below the 75
  cap (chaos shown as a number), ReqStr / ReqDex / ReqInt above Str / Dex
  / Int (PoB's own warning condition), SpiritUnreserved below 0, weakest
  element by PoB's *MaximumHitTaken; Life / ES / armour / evasion / block
  shown as plain values (research 0028 sections 1-2). A missing stat
  shows nothing; labelled "from PoB". floor-ok: comparisons of PoB
  outputs to the 75 cap and 0, nothing recomputed (decision 0004; ruling
  A). ACCEPT: tests on real-shaped PlayerStat sets (capped, uncapped,
  missing stat, negative spirit); design-reviewer pass. ZERO-CLICK:
  rebuilds by itself whenever a build loads or the snapshot changes.
- [ ] MATH-NEXT-LOOK (build) "Look for next" per gear slot: order the
  MATH-BUILD-HEALTH gaps and the MATH-WEIGHTS stat ranking into one line
  per slot ("Ring: cold resistance, then life") and pass the top terms to
  the UTIL-SEARCHSTR builder. After MATH-BUILD-HEALTH. floor-ok: ordering
  of PoB-derived numbers, no formula; the Copy stays the player's click
  (decision 0014). ACCEPT: ordering tests (gap first, then weight), slot
  coverage from the build XML's equipped items, string length cap kept.
  ZERO-CLICK: lines rebuild by themselves when the build loads.
- [ ] UTIL-UNDERLEVEL (build) Under-level warning: area level from the
  `Generating level N area` line minus the player level from level-up
  lines; at or above a setting (default 3 levels under) show "N levels
  under this zone" in the act card and the overlay status word (research
  0028 section 3). No XP-penalty formula shown. floor-ok: subtraction of
  two values from the opted-in Client.txt tail (ruling B). ACCEPT: parser
  / state tests incl. unknown player level (no warning), towns and
  hideouts skipped; overlay 2-line rule kept (design-reviewer).
  ZERO-CLICK: appears and clears by itself on zone entry and level-up.
- [ ] UTIL-RUN-HISTORY (build) Personal-best act splits and deaths by zone
  across runs: on a finished campaign act / run, append a small summary
  (act splits, deaths per zone, character class) to a local history file
  resolved by server/al/paths.py (gitignored ops/runtime or the AL
  sidecar); act card shows best and delta to best, a deaths-by-zone list
  shows the top zones. floor-ok with condition (ruling C): Client.txt-
  derived only, LIVE-RESUME untouched (decision 0008 not reversed; record
  that in a new decision), visible "history on" indicator and a clear /
  off setting. ACCEPT: fold tests on synthetic runs, file bound (cap on
  runs kept), clear works, test_sidecar_paths green. ZERO-CLICK: recorded
  and shown by itself; only clearing is a click.
- [ ] UTIL-PRICE-WATCH (build) Price watch: the item-check press remembers
  the last 20 priced items (name, price, time) locally; each hourly price
  book refresh (decision 0026) flags those whose price moved past a
  threshold (default 25 percent) in a dashboard list. floor-ok with
  condition (ruling D): the press records only what it already read, the
  refresh reads no clipboard or screen, no trade call, no auto-opened URL,
  nothing fetched or flagged while web_data is off (decision 0013), list
  clearable. ACCEPT: tests with a fake price book (rise, fall, under
  threshold, item gone, web_data off). ZERO-CLICK: filled by the existing
  press and refreshed by itself.
- [ ] UX-SETTINGS-IO (build) Settings export / import: "Download settings"
  on the player's click saves AshLight's own settings as a JSON file
  (decision 0031 / 0034 download pattern); "Import" reads a file the
  player picks in a browser file input. floor-ok with condition (ruling
  E): no contact, token or session cookie in the file; allow-list schema,
  unknown keys rejected; web_data never switched on without the player's
  confirm. ACCEPT: round-trip test, secret-exclusion test, bad-file tests;
  design-reviewer pass. ZERO-CLICK: nothing to do in play; one click each
  way only when moving PCs.

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
- [x] UX-FIRSTRUN (review) Walk the first-run path cold (no consent, no
  config, web data off, no Path of Building calc) on the dashboard and the
  overlay. ACCEPT: every card's empty / explain state says what appears and
  what the player does, the opt-in indicator is visible, the path to a live
  feed is one click; friction found is fixed and test-guarded. ZERO-CLICK:
  after the one ToS-required opt-in click nothing else is needed; empty
  states clear themselves when data arrives.
  DONE 2026-11-17 (area-ux, glance review 0004 U10): overlay says
  `not reading - see dashboard`; deaths tile `-` before the opt-in; the
  build-step note only inside an act; consent card shows the real path
  spelling. Node and pytest guards.
- [x] UX-DPI (review) Overlay and dashboard at 100 / 125 / 150 / 200
  percent scaling and 1080p / 1440p / 4K (emulated device scale factor);
  overlay card positions against the PoE2 HUD regions; text legibility at
  glance distance. ACCEPT: screenshots per scale, defects fixed and
  test-guarded. ZERO-CLICK: the overlay follows the OS scale by itself; no
  per-monitor setting to touch.
  DONE 2026-11-17 (area-ux, 0004 U11): no clipping or scroll at any
  scale; layout.js autoScale grows the HUD on monitors taller than 1440
  DIPs (4K at 100 / 125 percent); top-right default kept by adjudicator
  ruling, design 0001 section 10 corrected (it covers the corner map).
- [x] UX-COPY (review) Sweep every user-facing string (web/, app/overlay/,
  event text in server/al/state.py) against design 0001 sections 8-9.
  ACCEPT: inconsistent or unclear strings fixed with exact-output tests.
  ZERO-CLICK: copy only, no user step.
  DONE 2026-11-17 (area-ux, 0004 U12): server connect line no longer
  listed in Recent; overlay `waiting for log` for a quiet file;
  three dashboard labels reworded.
- [x] UX-PERF (review) Dashboard paint / JS cost with a busy synthetic
  session (hundreds of events): long tasks, DOM growth, SSE handler cost.
  ACCEPT: measured numbers recorded, regressions fixed, overlay budgets
  (tests/test_budgets.py) green. ZERO-CLICK: no user step; the dashboard
  stays light by itself in a long session.
  DONE 2026-11-17 (area-ux, 0004 U13): 600 events in 13 s, handler
  max 1.1 ms, 0 long tasks, DOM and heap flat after GC; recent list
  skips unchanged rebuilds.
- [x] UX-REAL-OVERLAY (review) Run the real Electron overlay on this
  machine's physical display(s) against a test core fed by
  tools/synth_client.py; real desktop screenshots (OS screen capture of the
  desktop, never the game) to verify transparency, click-through and
  non-focusable window flags, corner position, scaling at the monitor's
  real DPI, and the About disclaimer; close it by the PID started.
  ACCEPT: screenshots and measured flags recorded in glance review 0004,
  defects fixed and test-guarded. ZERO-CLICK: the overlay places, scales
  and stays click-through by itself; no setting to touch.
  DONE 2026-11-17 (area-ux, 0004 U14): S1 found - the overlay drew
  nothing on the real desktop (BrowserWindow.setOpacity on the
  transparent software-composited window); opacity is page CSS now,
  node-guarded. Read back on both monitors: visible, transparent,
  click-through (hit test), never focused, 280 x 176 DIP at 125 percent,
  disclaimer read by UI Automation.
- [x] UX-NEW-CARDS (review) Polish the cards that landed today (Maps,
  Death recap, Pace line, act resume note) for glanceability, empty and
  loading states, 320 px, forced colours and consistent timers. ACCEPT:
  headless Chrome screenshots, defects fixed with node / pytest guards.
  ZERO-CLICK: the cards fill and clear themselves from the log.
  DONE 2026-11-17 (area-ux, 0004 U15): Maps deaths column a count with
  gaps at 320 px; recap names deaths from before reading; Session counts
  from the log opening (`--:--` until live); `(partial)` plus one note;
  shorter pace line. Node and pytest guards.
- [x] UX-A11Y (review) A stdlib / node check of the dashboard for
  landmarks, heading order, aria-live politeness for pushed updates (not
  chatty), focus order and contrast tokens; fix findings. ACCEPT: the
  check runs in the suite (no new npm dependency), findings fixed.
  ZERO-CLICK: a test, no user step; screen readers hear only meaningful
  changes by themselves.
  DONE 2026-11-17 (area-ux, 0004 U16): tests/test_a11y.py; pills written
  only on change (0 live mutations over 3 pushes), deaths dash hidden
  text instead of a forbidden aria-label.

- [x] UX-NEWEST (review) Glance pass over today's newest surfaces: the
  Last session card (silent, no live region: it must be noticed by its
  place), the idle "log quiet" state (dashboard pill, zone tag, overlay
  word), price movers, the item card "Price and points" and "Rolls"
  lines, and the Path of Building calc off / failed notices, at 320 /
  768 / 1440 px in dark, light and forced colours. ACCEPT: headless
  Chrome screenshots, defects fixed and test-guarded. ZERO-CLICK: every
  surface fills and clears itself from the log and the price cache; the
  card shows where the eye lands with no click and no announcement.
  DONE 2026-11-17 (area-ux b4, 0004 U17): Last session card moved from
  under Death recap (y 1964 at 1440 px, 2908 at 320) to right under the
  tiles (y 363 / 519, above the fold) with a steady accent edge; Price
  and points moved next to Price. Guards in tests/test_ux_review.py.
- [x] UX-DASH-LAYOUT (review) With about 12 cards, order the dashboard by
  what a player needs at a glance, fold rarely used settings, keep Tab
  order = visual order. No new deps. ACCEPT: order recorded with the
  reason, DOM order guarded by a test. ZERO-CLICK: the order is fixed in
  the page; folded settings need a click only when the player wants to
  change them.
  DONE 2026-11-17 (area-ux b4, 0004 U18): tiles, Last session, trades,
  item check, Act times, Maps, Death recap, Recent, Build, Prices,
  overlay settings (folded), graphics (folded). DOM order only, no CSS
  order, so Tab order follows. Guard in tests/test_ux_review.py.
- [x] UX-OVERLAY-REAL2 (review) Re-verify the real overlay on the desktop
  after today's merges (visible, click-through, non-focusable, position,
  idle word) and measure RAM / CPU against decision 0002. ACCEPT:
  numbers in 0004. ZERO-CLICK: nothing to set; the overlay places and
  stays click-through by itself.
  DONE 2026-11-17 (area-ux b4, 0004 U19): visible on the desktop (GDI
  screen copy), TOPMOST TRANSPARENT LAYERED NOACTIVATE, hit test passes
  through, foreground unchanged, top-left 16,16 280 x 176; idle word
  `log quiet 20m` fits; 3 processes, working set 248 MB summed (budget
  250, no margin, as in OVL-BUDGET), private 109 MB, CPU 0 ms in 60 s.
- [x] UX-OVL-RAM (build) Give the overlay RAM headroom under the 250 MB
  budget (248 MB measured, 3 processes). ACCEPT: >= 20 percent headroom
  without losing transparency, click-through, non-focus, always-on-top
  or the U14 opacity fix; numbers in decision 0002; smoke budget
  tightened with margin. ZERO-CLICK: nothing to set; the switch ships
  in app/main.js.
  DONE 2026-11-17 (area-ux b5, 0004 U20): network service in the
  browser process; 2 processes, 179 to 186 MB summed (was 245 to 252),
  private 96 to 102 MB; desktop read-back passes; smoke asserts <= 2
  processes and < 215 MB. 20 percent met against the 250 MB ceiling;
  the smoke gate is 215 MB to absorb run-to-run noise.
- [x] UX-OVL-FORCED (review) Re-test forced colours in the real
  transparent overlay window. ACCEPT: the area outside the plates stays
  transparent, or a fix. ZERO-CLICK: nothing to set.
  DONE 2026-11-17 (area-ux b5, 0004 U21): `--force-high-contrast` on
  the real window: plates repaint to Canvas, outside stays transparent;
  no fix needed.
- [x] UX-B5-CARDS (review) Glance pass over the util batch 5 / 6
  surfaces: waystone verdict on the item card and overlay, Search
  strings card (Copy feedback without live-region spam, keyboard
  reachable, long strings wrap at 320 px), Zone tip in Act times, the
  ashlight.filter download (what it does; AshLight writes nothing into
  game folders). ACCEPT: 320 / 768 / 1440 px, dark / light / forced
  colours, defects fixed. ZERO-CLICK: nothing to set; every surface
  fills itself from the log, the pasted build and the hotkey press.
  DONE 2026-11-17 (area-ux b6, 0004 U22): search strings wrap (were
  clipped one-line inputs), Copy / filter feedback on the button's own
  name (no 13th live region), filter words say download-then-move and
  that nothing is written to game folders.
- [x] UX-ONBOARD-COPY (build) One short "What AshLight does / never
  does" explainer reachable from the dashboard footer: reads Client.txt
  after opt-in, clipboard only on your hotkey press, never sends input to
  the game, never touches the game process; the GGG disclaimer intact.
  ACCEPT: in the footer at every width, under the 12 live-region cap,
  tested. ZERO-CLICK: always on the page, folded; nothing to set.
  DONE 2026-11-17 (area-ux b6, 0004 U23): footer fold, disclaimer first,
  no live region; tests/test_ux_b6.py.
- [x] UX-OVERLAY-WAYSTONE (review) The real overlay shows the waystone
  verdict legibly in its 3-line card (34 characters a line, no wrap) on
  the desktop, budget kept (2 processes, smoke <= 215 MB). ACCEPT:
  desktop screenshot read back, numbers recorded. ZERO-CLICK: the card
  shows by itself on the item-check press and leaves after 20 s.
  DONE 2026-11-17 (area-ux b6, 0004 U24): card read back on the desktop
  in 3 lines; risky waystone now takes the warn edge, and keeps the card
  over the price card with no build loaded; 2 processes, 179.9 MB peak.

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

- [x] TEST-FUZZ (build) Stdlib seeded property / fuzz tests (bounded time)
  for the Client.txt line parser, the item-text parser, the PoB2 share-code
  codec, the build / character JSON / poe.ninja parsers and the price /
  snapshot builders: random bytes in mixed encodings, truncations,
  mutations, extreme numbers, wrong-typed card fields. ACCEPT: fuzz tests
  green; every crash fixed with a regression test. DONE 2026-11-17:
  tests/test_fuzz.py (AL_FUZZ_S / AL_FUZZ_SEED for a longer hunt; per-call
  time bound catches regex blow-ups). Defects fixed: (1) FUZZ-1 the trade
  whisper regexes backtracked cubically (10 KB whisper 4 s on the tailer
  thread, a 64 KB line hours) and guild / chat / level-up quadratically -
  parser.MAX_LINE_CHARS 8192 (longer lines ignored), MAX_TRADE_TEXT 1024
  (longer whispers stay plain whispers); (2) FUZZ-2 item._TAG_RE's leading
  \s* made re.search quadratic (60 000 spaces 7 s on a hotkey press);
  (3) FUZZ-3 wrong-typed card fields (number for item, dict for error,
  non-list listings, huge ints) raised in eval / price / trade card text,
  price_until and set_price, so one bad card broke every /api/state;
  (4) FUZZ-4 ninja._num raised OverflowError on a huge JSON int.
  ZERO-CLICK: runs inside pytest; the fixes need no user step.
- [x] TEST-SOAK (build) Time-compressed soak harness: the core runs many
  simulated hours of synthetic Client.txt (tools/synth_client.py) with SSE
  clients reconnecting; assert bounded memory (tracemalloc), bounded event
  history, no thread / handle growth. Short variant in every suite, long
  variant opt-in (AL_SOAK=1). ACCEPT: both variants green; defects fixed.
  DONE 2026-11-17: synth_client.play() (five-minute rounds of game time);
  tests/test_soak.py: 48 simulated hours in every suite (~4 s), AL_SOAK=1
  500 hours (19 s, second half may not outgrow the first); heap growth
  measured ~0.7 MB flat (budget 2.5 MB), handles and threads back to the
  baseline, ring / recent lists / trade cards at their caps; a planted
  ~700 B/event leak fails it. Defect fixed: (1) SOAK-1 a closed SSE client
  kept its slot, bus subscription and thread until two writes failed (two
  15 s heartbeats on a quiet log), so reloading the dashboard filled
  MAX_SSE_CLIENTS and the overlay got "busy" for 30 s - http.py
  _client_gone() peeks the socket every loop wake (<= 1 s). ZERO-CLICK:
  runs inside pytest; the long run is one env var.
- [x] TEST-SUPERVISOR (build) Keepalive supervisor kill / hang / restart and
  stop.request paths (decision 0005), plus scripts/run.ps1 / stop.ps1
  idempotency checks; PowerShell validated with powershell.exe 5.1
  ParseFile. ACCEPT: tests green; defects fixed. DONE 2026-11-17:
  tests/test_supervisor.py (18 tests: pid reuse, stop during backoff,
  unterminable hung core never duplicated, start grace timeout, launch
  failure give-up, restart window expiry, clean exit, second supervisor,
  every scripts/*.ps1 through 5.1 ParseFile, run.ps1 gating, stop.ps1 run
  twice on a tmp runtime). Defects fixed: (1) SUP-1 a dead core's pid
  reused by another process read as a live hung core - the supervisor
  tried to terminate it (any python.exe died) and, refused, never
  relaunched the core; keepalive now compares the heartbeat's recorded
  creation time; (2) SUP-2 stop.ps1 force-stopped any python process
  holding a leftover core.alive pid; it now asks server.al.procs status
  (image + creation time) and leaves a reused pid alone (rc 0, the core is
  not running). ZERO-CLICK: runs inside pytest, no user step.
- [x] TEST-COVER (build) Line coverage with stdlib trace; the untested
  modules listed in a docs file; tests added for the worst gaps. ACCEPT:
  coverage file committed; worst gaps covered. DONE 2026-11-17:
  tools/cover.py (sys.settrace + threading.settrace limited to server/ and
  tools/, co_lines denominator, runs the whole suite through the suite
  gate) writes docs/audit/test-coverage.md. First run 87.5% (server/
  90.2%); tests/test_cover_gaps.py (21 tests: entry helpers, procs CLI and
  forced stop, keepalive launcher / logger / CLI give-up, real webfetch
  transport on loopback) and tests/test_cover_tool.py lift it to 89.1%
  (server/ 93.1%; procs 63 -> 91, keepalive 70 -> 88, webfetch 80 -> 92).
  Left low on purpose: modules run only in a child process (the report
  names them). The tighter fuzz contract found (5) FUZZ-5 a lone surrogate
  in pasted character JSON escaped model.parse as UnicodeEncodeError, not
  BuildError (/api/build-code got no 400) - fixed in model._root.
  ZERO-CLICK: one command (tools/cover.py) writes the report, no user
  step.
- [x] TEST-FLAKE-SSE (build) tests/test_http_robust.py::
  test_slow_sse_reader_is_dropped_and_does_not_stall_others failed once in
  a full gated suite. ACCEPT: root cause named (test or server), fixed,
  looped green alone and under load; other wall-clock tests at risk listed.
  DONE 2026-11-17: reproduced 1/25 under CPU load ("fast stream closed").
  Root cause in the TEST, not the server: the "fast" client never read while
  1.6 MB was published, so its server thread blocked on a full socket and
  the fixture's 0.5 s write timeout cut it; it survived only while Windows
  loopback buffering (probed: ~3 MB default, ~400 KB at SO_RCVBUF 4096)
  absorbed the burst. Server checked: publish is a bounded deque append per
  subscriber and a stalled writer blocks only its own thread, so no
  server/al/http.py change. The test now reads the fast stream on a thread,
  publishes until the slow subscription is gone (60 s deadline), asserts
  the worst single publish < 2 s and a marker reaches the fast stream (30 s
  deadline); the cap test's slot-release deadline 5 -> 20 s. Loops: new test 50/50 alone, 30/30 under 24 CPU
  burner processes, plus two full gated suites green.
  Other wall-clock thresholds at risk under load: test_fuzz _timed < 0.25 s
  and CALL_S 1.0 s, test_audit_pass2 flask regex < 0.5 s (fixed: now
  fleet_test_guard.budget(), 0.5 / 1.0 s base); left as is (bounds 4-10x
  the work): test_e2e_replay resume < 5 s, test_tc_bridge timeout kill
  < 5 s, test_tc_code_api drain < DRAIN_TIMEOUT_S + 3, test_audit_http_harden
  idle close < 4 s, test_http_robust thread count after 0.3 s sleep,
  test_budgets (already budget()-scaled). ZERO-CLICK: test-only, no user
  step.
- [x] TEST-FULLSTACK (build) One synthetic scenario through every feature
  over the real HTTP / SSE surface of a core on a free port 8961-8979:
  consent, log opened, acts 1-4 with level-ups / deaths / splits, maps with
  a same-seed portal re-entry, trades accepted / cancelled, item checks
  (gear, waystone, unique), price book from a local mock poe.ninja, build
  code, 20 min quiet (time-injected), idle + saved summary, core restart +
  resume. ACCEPT: snapshot and SSE asserted per stage; web data OFF sends
  nothing; under ~20 s; defects fixed with tests. DONE 2026-11-17:
  tests/test_fullstack.py (4 tests, ~1.5 s main scenario; the calc ON leg
  ~12 s, runs only where setup.ps1 -TcCalc installed the component). The
  mock is a stdlib 127.0.0.1 server behind the core's injected transport
  (webfetch still checks the real https://poe.ninja URL): asserted 24 GETs
  on opt-in with the truthful User-Agent + contact and no Cookie, none more
  within the hour, then 23 conditional GETs (If-None-Match, 304, no league
  re-read inside 6 h), none after a restart, none with web data off before
  or after. Defect fixed: (1) FULLSTACK-1 synth_client wrote the LOG FILE
  OPENING marker with a millisecond counter, a shape the live log never
  has, so no synthetic session (e2e, soak) ever produced log_opened or a
  resume run start - regression test_synth_marker_has_the_live_shape.
  No core defect found. ZERO-CLICK: runs inside pytest, no user step.
- [x] TEST-FULLSTACK-SSE-IDLE (build) A state change with no log event (the
  idle state and the session summary card from the core loop tick, a trade
  card expiring) reached SSE clients only on the next heartbeat
  (http.SSE_HEARTBEAT_S 15 s). DONE 2026-11-17 (area-test b5): a
  state-version wake, no new timer: SessionState.version is a property
  whose bumps outside apply() call on_change = bus.wake_all (sticky
  Subscription.wake, never lost); the SSE loop pushes a version-only state
  at once (4 Hz coalescing kept). Core.tick_sources in the existing 0.5 s
  loop tick expires trade cards and publishes snapshot `sources` (calc_on,
  calc_running, rates / price book checked_at), so calc on/off and a price
  book refresh are pushed too. tests/test_sse_idle_push.py (heartbeat 600 s
  and stream wait 30 s, so only the wake can deliver; fails with the wake
  unwired) and test_fullstack idle leg (heartbeat lengthened, push < 3 s).
  ZERO-CLICK: no user step.
- [x] TEST-FULLSTACK-CALC-WARM (build) The live calc tests each started their
  own PoB bridge. DONE 2026-11-17 (area-test b5): session fixture
  `warm_bridge` (tests/conftest.py, the core's bridge.shared()) used by
  test_math_e2e_live, the test_fullstack calc leg, the drift guard live
  test and two test_tc_bridge live tests; tc_live_util.keep_warm(core)
  records the core's stop instead of killing it (e2e asserts the stop was
  asked). test_math_perf (measures the cold start) and the reload / leak
  test keep their own processes. 5 luajit starts -> 3. Measured: the 5 live
  files 58.3 s -> 57.6 s. FINDING: the process cold start is only ~1.2 s
  (MATH-PERF cold_start_s 1.19); the ~11 s first press is the per-core,
  per-build probe work (base outputs + MATH-WEIGHTS mod weights), not the
  bridge. Further cuts would need a cross-core probe cache, which would make
  the tests depend on each other: not done. ZERO-CLICK: test-only.

## Utility (lane area-util, 2026-11-17)

- [x] UTIL-MAPS (build) Map run tracker from Client.txt (area generation +
  scene): maps run, the open map's time in map (hideout trips and loading
  paused), deaths per map, last 5 finished maps, average map time.
  server/al/runs.py MapRuns, snapshot `maps`, dashboard Maps card
  (web/runs.js). ACCEPT: exact tests on replayed lines
  (tests/test_util_runs.py, app/test/runs.test.js). ZERO-CLICK: maps open,
  time and close by themselves from the log; no button. DONE 2026-11-17.
- [x] UTIL-DEATHS (build) Death recap: each of the player's deaths with
  zone, area level, character level and time in the zone before it, newest
  first, plus the zone with the most deaths. server/al/runs.py DeathLog,
  snapshot `death_recap`, dashboard Death recap card. ACCEPT: exact
  sentence tests. ZERO-CLICK: filled by itself on every death line.
  DONE 2026-11-17.
- [x] UTIL-PACE (build) Level pace from level-up lines (Client.txt carries
  no XP): average time per level over the last 5 levels and levels per
  hour this session (after 10 minutes); one line on the Level stat tile,
  sentence built in the core (server/al/pace.py, snapshot `pace`). ACCEPT:
  exact tests on replayed level-up lines (tests/test_util_pace.py).
  ZERO-CLICK: updates on every level-up by itself. DONE 2026-11-17.
- [x] UTIL-MAPS-RESUME (build) Rebuild the map runs and death recap at core
  start from the current game run in Client.txt, as HUD-ACT-RESUME does for
  act splits (decision 0023 pattern, no persisted state). ACCEPT: restart
  mid-map keeps the map's time and the session's deaths; exact tests.
  ZERO-CLICK: rebuilt at core start. DONE 2026-11-17: resume.scan returns
  `run_events` (scenes, area generations, deaths, level-ups of the current
  run, at most 20000), runs.replay folds them like SessionState.apply;
  tests/test_util_maps_resume.py (core restart mid-map keeps 5:00 and the
  death).

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
- [x] WT-SIDECAR (build) Harness Agent-tool worktree isolation creates -- done 2026-11-17 (loop; refute 1/3 PASS)
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

- [x] AUDIT-TC-CODE-REAL (review) Re-open the real-code check (finding C1):
  TC-CODE-REAL was flipped done with only a skip-when-absent harness
  (tests/test_tc_code_real.py skips; tests/fixtures/pob2_real holds a README
  only). ACCEPT: one real PoB2 export decodes, parses and round-trips
  through the harness (no skip), owner consent recorded if kept as a
  fixture.
  ZERO-CLICK: the harness runs by itself once the file exists.
  DONE 2026-11-17 (AREA-AUDIT b2): two public PoB2 exports from pobb.in
  (a level 68 Ranger Pathfinder and a level 90 Mercenary Gemling Legionnaire,
  targetVersion 0_1, fetched once by hand into the gitignored sidecar
  Scratch, never tracked; owner consent not asked, so not a fixture) ran
  through tests/test_tc_code_real.py via AL_TC_REAL_CODE: zlib framing,
  root PathOfBuilding2, parse, stats and XML byte-exact round trip PASS
  (11 passed each); the code string differs from Python zlib (the accepted
  xfail of decision 0021 R2). Tree URLs: www.pathofexile.com.
- [x] AUDIT-HTTP-HARDEN (build) Findings S1-S4: HEAD /events streams a body
  forever (http.py do_HEAD -> do_GET -> _sse); Handler has no socket timeout
  (an idle connection holds a thread); ?token= is accepted on every /api
  route (restrict it to /events, the only EventSource route); POST
  /api/consent "path" accepts any file or UNC path (refuse UNC and names
  other than Client.txt / a folder holding it). ACCEPT: one test per item.
  ZERO-CLICK: code row. DONE 2026-11-17 (AREA-AUDIT b2): HEAD /events is a
  405 (Allow: GET); Handler.timeout (10 s, REQUEST_TIMEOUT_S after
  the TEST-HTTP merge; audit pass 2); ?token= only on /events; consent
  path checked lexically (logfile.consent_path_ok: local absolute, no UNC /
  device / stream / '..', Client.txt or a dot-free folder) before any file
  access. tests/test_audit_http_harden.py.
- [x] AUDIT-EXE-PATH (build) Finding S5: gfx.py runs bare "powershell.exe"
  and tc_pin.py bare "cmd.exe" / "mingw32-make" (Windows CreateProcess also
  searches the current directory); use the System32 absolute path for the
  Windows tools, and TC-BRIDGE must hash-check luajit.exe before every exec
  (tc_pin.ensure_luajit trusts any existing luajit.exe). ACCEPT: tests on
  the argv. ZERO-CLICK: code row. DONE 2026-11-17 (AREA-AUDIT b2):
  server/al/exepin.py - System32 absolute paths (gfx, tc_pin cmd.exe,
  lane_samples recycle), PATH tools from absolute entries only (which_abs),
  luajit.exe SHA-256 recorded at build and checked by tc_pin no-op,
  bridge.status and before every bridge exec. tests/test_audit_exe_path.py.
- [x] AUDIT-ELECTRON (build) Findings S6-S7: devTools follow
  !app.isPackaged, and the overlay is never packaged, so they are always on
  (gate on an AL_DEV env instead); add session.setPermissionCheckHandler(()
  => false) next to the request handler. ACCEPT: a main.js source test for
  both. ZERO-CLICK: code row. DONE 2026-11-17 (AREA-AUDIT b2): devTools only
  with AL_DEV=1; setPermissionCheckHandler(() => false).
  app/test/audit_electron.test.js.
- [x] AUDIT-SNAPSHOT-OPTIN (review) Finding T1: scripts/build.ps1 runs the
  game-data snapshot by default (opt-out, decision 0009) while CLAUDE.md
  Settled says nothing hits the network while web_data is off (decision
  0013). Adjudicate one rule (build step honours web_data, or 0013 states
  the build-time exception) and record it. ACCEPT: decision amended and
  build.ps1 / README match. ZERO-CLICK: ruling row. DONE 2026-11-17
  (AREA-AUDIT b2): adjudicator ruled option (a) - the build-time snapshot
  follows web_data (default off); -Snapshot / AL_SNAPSHOT=1 force it,
  -NoSnapshot / AL_NO_SNAPSHOT=1 win; snapshot.main checks it too.
  Amendments in decisions 0009 and 0013. tests/test_audit_snapshot_optin.py.
- [x] AUDIT-TREE-URL (build) Finding S8: web/tc.js safeUrl lets a pasted
  build's tree URL be any https host as an "Open the tree" link. Allow only
  known tree hosts (pathofexile.com, poe2db.tw, poeplanner-style hosts after
  a check) or show the host name in the link text. ACCEPT: app test with an
  off-list host. ZERO-CLICK: code row. DONE 2026-11-17 (AREA-AUDIT b2):
  web/tc.js safeTreeUrl allows pathofexile.com, pathofexile2.com, poe2db.tw,
  maxroll.gg (and subdomains), https, no port / user info; two real PoB2
  exports use www.pathofexile.com. app/test/audit_tree_url.test.js.
- [x] AUDIT-HYGIENE (build) Findings H2-H6: tests/test_ascii_lf.py checks a
  suffix list (skips .log, .vbs, .sh, .xml, .svg, LICENSE) - check every
  non-binary tracked file; server/al/paths.py SIDECAR_SUBDIRS lacks Scratch
  and ClaudeHistory and all_runtime_paths() omits worktree_dir() and the
  overlay profile; tests/test_sidecar_paths.py SCANNED skips tools/;
  AL-NEXT-SESSION.txt spells the sidecar with a drive letter (use
  <sidecar>); decision 0002 should name pytest as the one allowed test
  dependency. ACCEPT: tests for the first three. ZERO-CLICK: code row. DONE
  2026-11-17 (AREA-AUDIT b2): ASCII / LF check reads every non-binary file;
  SIDECAR_SUBDIRS adds Scratch, ClaudeHistory; all_runtime_paths adds
  worktree and overlay_profile; drive scan covers tools/; hand-off spells
  <sidecar>; decision 0002 names pytest. tests/test_audit_hygiene.py.
- [x] AUDIT-LOOP-COMMIT-MSG (build) Finding C2: loop merge commits carry the
  row text cut mid-sentence plus refute / verifier lines, so an ACCEPT that
  says "root cause named in the commit" (FLAKY-EVAL-API, 5e7b30e) is not met
  by the commit. Carry the lane's result line (root cause / what was done)
  in the commit body. ACCEPT: tools/loop_merge.py test on the message.
  ZERO-CLICK: code row. DONE 2026-11-17 (AREA-AUDIT b2): the lane's RESULT:
  line (else its last paragraph) is stored by lane_worker and written as a
  `result:` paragraph in the lane commit and the main merge commit; the
  build prompt asks for it. tests/test_audit_loop_commit_msg.py.
- [x] AUDIT-TC-WIRE (build) TC-DELTA was never wired into the core
  (Core.tc_calc stayed None), so every item check in play used the stat
  weights. Wire the TC-BRIDGE client as the delta calc: opt-in, off by
  default, graceful when the component is absent or fails. ACCEPT: tests
  over the stdio bridge double; core runs unchanged with it off.
  ZERO-CLICK: one opt-in key; the bridge starts on the first item check.
  DONE 2026-11-17 (AREA-MATH b2, with MATH-WEIGHTS):
  server/al/theorycraft/calcwire.py (map_outputs: FullDPS / CombinedDPS /
  TotalDPS / TotalDotDPS, TotalEHP else Life + EnergyShield; make_calc
  reloads the build around every swap; Provider returns None unless local
  config "tc_calc": true AND bridge.available(), rechecked at most every
  30 s, bridge imported lazily); Core.tc_provider + tc_calc_enabled,
  Core.close stops the shared bridge; tests/test_tc_wire.py. A failing
  bridge gives the "failed" notice (or cached PoB weights, MATH-WEIGHTS).

- [x] AUDIT-TC-BRIDGE-LIVE (review) Pass 2 finding P2-C1 (medium, claim -- done 2026-11-17 (TC-LIVE)
  re-opened): TC-BRIDGE was flipped done but its ACCEPT ("outputs on a
  fixture build match PoB GUI within 0.1 percent") never ran -
  tests/test_tc_bridge.py live tests skip (no luajit.exe: no compiler on
  this machine; no gui_expected.json). Only the fake-bridge protocol tests
  ran. ACCEPT: the live 0.1 percent test passes once (no skip).
  ZERO-CLICK: the live tests run by themselves once both exist.
  result: operator act i replaced by decision 0027 (hash-pinned WinLibs
  MinGW-w64 .zip in the sidecar Cache, used only when no system compiler).
  setup.ps1 -TcCalc built luajit.exe (static) and read back ready / no-op.
  The real component exposed two bridge.lua bugs, fixed: PoB's '#@' first
  line no longer loads under current LuaJIT, and the pinned HeadlessWrapper
  keeps mainObject local. Reference: public pobb.in build Nqt6FK5lIc6F
  opened in the pinned v0.23.1 GUI; 17 sidebar outputs (TotalDPS 27729.4,
  CombinedDPS 27739.3, FullDPS 39265.0, TotalEHP 32072, Life 1887, ES 1738,
  Evasion 19583, ...) match the bridge within 0.1 percent (largest gap
  0.024 percent, CritChance display rounding). The reference sits untracked
  in the sidecar Cache\tc_bridge (owner not asked); the live tests read it
  via paths.py and still skip on machines without it. Also: load_build now
  forces one BuildOutput (a sparse build after a full one kept the stale
  output); test_live_reload sets characterLevelAutoMode="false" so level 90
  really differs. Residual (PoB side, not filed as a defect): the sparse
  minimal fixture loaded after a full real build inherits its class (Life
  702 vs 65 fresh); full real builds reload exactly (x, y, x identical).
- [x] AUDIT-TC-WIRE (build) Pass 2 finding P2-C2 (medium): TC-DELTA is not
  wired - core.tc_calc is always None (core.py "TC-BRIDGE sets it", but no
  code does) and no adapter maps Bridge (load_build / set_item / outputs)
  to delta's calc(build, swaps) -> {"dps", "ehp"}, so every item check
  scores with stat weights and says "off". Add the adapter (PoB output
  names for DPS / EHP, swap then restore the slot), set tc_calc when
  bridge.available(), and bound one evaluation's total calc time (up to 25
  calls x 60 s timeout today) off the hotkey path. After AUDIT-TC-BRIDGE-LIVE
  for the output names. ACCEPT: fake-bridge test of the adapter and the
  core wiring; card says "pob" with the fake present.
  ZERO-CLICK: the calc switches on by itself when the component exists.
  CLOSED 2026-11-17: done by the AREA-MATH b2 AUDIT-TC-WIRE row above
  (calcwire.py, tests/test_tc_wire.py); this pass-2 copy is the same item.
- [x] AUDIT-MAP-SEED (build) Pass 2 findings P2-M1 (medium), P2-M2, P2-M3
  (low); server/al/runs.py was mid-change in UTIL-MAPS-RESUME, so not fixed
  in pass 2. M1: MapRuns.on_generated opens a new map on every Map*
  generation and ignores the seed, so a portal back into the same instance
  (same area id, same seed) counts a second map and splits its clock (PoE1
  logs "Generating level" on every instance load; PoE2 to be confirmed);
  keep the seed on the open map and treat same id + seed as a re-entry.
  M2: DeathLog.by_zone (Counter) is uncapped while rows cap at 500; derive
  "most deaths" from the capped rows. M3: after a core restart the deaths
  tile shows the restored count while the recap says "No deaths this
  session" (check after UTIL-MAPS-RESUME). ACCEPT: replay test gen(MapX,
  seed 7), hideout, gen(MapX, seed 7) gives count 1 and one clock; 10k
  distinct-zone deaths keep by_zone <= MAX_DEATHS.
  ZERO-CLICK: code row.
  DONE 2026-11-17 (area-util batch 3): MapRuns keeps the seed; same id +
  seed as the open map is a re-entry (no seed keeps the old rule); seed
  carried through resume run_events; DeathLog.by_zone() derives from the
  capped rows; the recap's empty line names restored deaths instead of
  "No deaths this session". tests/test_audit_map_seed.py.
- [x] AUDIT-BRIDGE-LOW (build) Pass 2 lows P2-B3..B5: exepin's .sha256 sits
  beside luajit.exe in the user-writable sidecar, so it guards against a
  stale or foreign exe, not tampering (say so in decision 0022 or keep the
  record in the repo runtime); Bridge._read calls proc.wait(5) after EOF
  without catching TimeoutExpired (escapes as a non-BridgeError); the
  reader thread reads unbounded stdout lines from PoB. ACCEPT: one test
  each. ZERO-CLICK: code row.
  DONE 2026-11-17 (area-audit batch 4): threat model in decision 0022
  amendment, EOF wait caught, reader lines capped at 1 MiB;
  tests/test_audit_batch4.py.
- [x] AUDIT-SETTLED-LIST (review) Pass 2 low P2-D2: CLAUDE.md "Settled"
  has no entries for decisions 0021-0024 (tc-code-real, tc-bridge,
  act-splits-resume, tc-delta); a lane draft "0022-trade-stat-ids-source"
  would collide again (tests/test_audit_pass2.py now fails on any duplicate
  number). ACCEPT: Settled lines with "Reverses if" for each.
  ZERO-CLICK: doc row.
  DONE 2026-11-17 (area-audit batch 4): Settled lines for 0021, 0022,
  0024, 0025 and the 0009 / 0013 amendment; 0023-tc-drift renumbered
  0025; test_audit_batch4 fails on any decision missing from Settled.

- [x] AUDIT-P4-LOW (build) AREA-AUDIT pass 4 lows P4-4..P4-6
  (docs/audit/2026-11-17-audit.md "Pass 4"): core.tick_sources reads
  local.json every 0.5 s loop tick (use an mtime check); delta._swap_sane's
  "base has no weapon_unusable" test can never be false (base outputs never
  ask main_skill; fix the code or the 0032 amendment wording); the
  UX-OVL-RAM 2-process / 215 MB budget is only in the opt-in live smoke.
  ACCEPT: a fix or a recorded ruling and one test each. ZERO-CLICK: code
  row, the loop works it. DONE 2026-11-17 (audit batch 8): Core._config
  stats the file and re-reads only on an mtime / size change
  (test_p4_4_*); _swap_sane counts only the swap's flag, 0032 amendment
  reworded (test_p4_5_*); always-on static RAM guard: one BrowserWindow,
  no worker / child / utility process / webview / iframe / popup, one
  enable-features switch, in-process switches before ready
  (test_p4_6_ram_budget_static_guard); live measurement stays opt-in.
- [x] AUDIT-P3-LOW (build) AREA-AUDIT pass 3 lows P3-4..P3-10
  (docs/audit/2026-11-17-audit.md "Pass 3"): map clock stays paused after
  idle clears on a non-scene line; ninja.py rollover docstring says "at
  once" (it is the next hourly refresh); calcwire keeps luajit running
  after tc_calc is turned off; PriceBook saves attempt_at only after the
  whole loop; AL_TC_PINS_FILE honoured outside the TC-DRIFT trial; the
  TC-DRIFT trial runs new upstream PoB Lua unattended; the extracted
  toolchain is trusted by its marker (no re-hash before the build).
  ACCEPT: a fix or a recorded ruling and one test each. ZERO-CLICK: code
  row, the loop works it.
  DONE 2026-11-17 (area-audit batch 6): P3-9 ruled (decision 0025
  amendment: unattended trial static only, live on --live or local.json
  opt-in, apply needs live-green); P3-8 env honoured only in pytest;
  P3-10 toolchain tree re-hashed before each build (0027 amendment); P3-6
  core loop stops luajit when tc_calc goes off; P3-4 map clock resumes
  when idle clears in the same map; P3-5 docstring fixed; P3-7 price book
  saved per request. Tests: test_tc_drift, test_tc_pin, test_tc_wire,
  test_audit_pass3 (test_p3_*).

- [ ] OPERATOR: create the GitHub remote when the operator wants to publish
  (then lift the pre-push refusal in the same change, CI workflow with the
  kit's fleet_identity_guard.yml as a required check).
