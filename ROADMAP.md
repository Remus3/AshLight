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
  level, die once, and receive one trade whisper.
- [ ] OVL-BUDGET (build) PARTIAL 2026-11-16 (decision 0002 "Measured
  2026-11-16 (OVL-BUDGET, game running)"): idle with the game open at
  character select 3 processes, about 204 MB working set, 0.000 percent CPU,
  0 GPU - within budget, after the in-process-gpu start fix. REMAINS: the
  ACTIVE measurement (overlay updating during play, in a map). ACCEPT: within
  budget or a ruling on Tauri / native.
- [ ] OVL-FPS (build) PARTIAL 2026-11-16. Method per decision 0006 (no
  PresentMon / ETW of the game). Character-select proxy: system-wide GPU 3D
  utilisation off 52.5 vs on 53.3 percent, inside noise, GPU saturated.
  REMAINS: in-map run read from the game's own FPS display, overlay off vs
  idle vs updating, Windowed Fullscreen. ACCEPT: average FPS loss under 1
  percent, 1 percent lows unchanged within noise; numbers in decision 0002.
- [x] LIVE-RESUME (build) Found in LIVE-1 (2026-11-16): a core restart
  starts at the end of Client.txt, so zone, level and character stay empty
  until the next level-up or zone change. Done 2026-11-16 (decision 0008):
  bounded backward scan (server/al/resume.py, 1 MB chunks, 32 MB cap, stops
  at the newest LOG FILE OPENING once the character is known) restores
  zone, area, character, class, level, deaths, level-ups, AFK / DND into
  state only, nothing re-listed; tests/test_resume.py, 32 MB scan budget in
  tests/test_budgets.py. ACCEPT: after a restart mid-session /api/state
  shows the last zone, level and character from the log.
- [ ] OVL-TRADE-CANCEL (build) Decide whether ": Trade cancelled." (new
  event trade_cancelled) should clear or mark an open trade card (design
  review 2026-11-16). ACCEPT: behaviour decided and tested.
- [x] OVL-POS (build) Overlay layout editor on the dashboard (corner, scale,
  opacity), DPI-aware, multi-monitor; stored in config/local.json. ACCEPT:
  position survives restart; tests for the layout math.
- [ ] HUD-ACT (build) Leveling helpers: act / zone level table from an
  attributed build-time data snapshot (license checked first, research 0005);
  zone timer splits per act. ACCEPT: split table on the dashboard.
- [x] HUD-WHISPER (build) Trade whisper card on the overlay (item, price,
  stash position) with a quiet, non-flashing cue; dismissed from the
  dashboard. ACCEPT: fixture whisper renders; no input sent to the game.
- [x] PRICE-1 (build) Price check: AshLight hotkey reads the clipboard ONCE
  (decision 0003), parses the item (research 0003), queries the trade2 API
  through one rate-limited queue that parses X-Rate-Limit headers
  dynamically; opt-in setting. ACCEPT: parser tests on fixtures; limiter
  tests; no request without the opt-in.
  PARTIAL 2026-11-17 (data lane, decision 0013): server/al/trade.py - shared
  RateLimiter (X-Rate-Limit-Policy / -Rules / -<rule> / -State, Retry-After
  with 60 s fallback, headroom 1, kinds sharing a policy share state), one
  serial TradeClient queue behind the web_data opt-in (re-checked before
  send), search / fetch URL builders, build_query(ParsedItem, stat_ids).
  tests/test_trade_limiter.py (mocked). REMAINS: the per-press clipboard
  read + hotkey (decision 0003), the trade2 /data/stats stat-id table
  (cached) for build_query, search -> fetch flow and price summary, an API
  endpoint, league choice, "waiting N s" surfaced in state, live header
  values recorded in research 0004.
  ZERO-CLICK: once opted in, the one hotkey press queues the check; the
  limiter paces it with no click.
  DONE 2026-11-17 (build lane, decision 0015): server/al/price.py - the
  item hotkey's existing POST /api/eval (one clipboard read per press,
  app/eval_hotkey.js) queues at most ONE check: trade2 /data/stats table
  cached daily under <sidecar>\Cache\trade, league from config else
  /data/leagues (daily) else Standard, build_query -> search -> fetch of
  the first 10 -> summary (currency, min / median of the cheapest 5,
  listing count, total); same text within 30 s reuses the result; live
  "waiting N s" from the limiter; neutral state field `price` and
  token-gated GET /api/price (removed by PRICE-1-WIRE). Off (zero requests) without web_data or a
  contact (UA-CONTACT). tests/test_price_check.py (mocked). UI remains in
  PRICE-1-UI; live header values in research 0004 remain UNVERIFIED.
- [x] PRICE-1-UI (build) Price-check card on the dashboard and overlay (best
  prices, "waiting N s" from the limiter, poe.ninja rates for conversion).
  After PRICE-1. ACCEPT: fixture result renders at desktop and phone width;
  design-reviewer pass. ZERO-CLICK: appears after the hotkey press, no
  button.
  DONE 2026-11-17 (decision 0016), STUB-BUILT: no PRICE-1 result contract
  existed, so the adjudicator ruled one (0016 fork 1): the lane calls
  state.SessionState.set_price(card, at=<press time>) and adds no endpoint;
  snapshot `price` (status searching|waiting|done|off|error, wait_s, item,
  league, count, listings <= 10, error) with text from state.py
  price_card_text, and `card` from overlay_card (merged with the item check
  of the same press, or price-only). Nothing calls set_price in this branch
  yet; UI checked against fixture cards (tests/test_price_text.py,
  app/test/price.test.js, prices.test.js, stand-in server screenshots).
  Dashboard: Price section in the Item check card with "about N <primary>"
  per listing (web/prices.js). REMAINS for PRICE-1: call set_price.
- [x] PRICE-1-WIRE (build) (next build lane, first) Reconcile the PRICE-1
  server (decision 0015) with the PRICE-1-UI contract (decision 0016).
  Same hotkey (Alt+Shift+E, the one /api/eval read), but the method and
  endpoint differ: price.PriceChecker publishes its own doc (id, status
  incl. queued / skipped, reason, wait_s, league, summary {count, total,
  min, median, currency}, error) through set_price(doc) with no press time,
  while the card reads item {name, base, rarity}, count, listings
  [{amount, currency}] and error, and is stamped with at=<press time>; the
  lane also added GET /api/price, which 0016 does not use. Until wired a
  real check shows "Unnamed item" (only with web_data and a contact on;
  both are off by default). Fix: a thin adapter (price doc -> card: item
  from the parsed item, listings from the fetched results, reason -> off /
  error, queued -> searching, skipped -> "not an item") and call
  set_price(card, at=<press time>, keep_time=True for status updates);
  decide whether GET /api/price stays (amend 0015 / 0016). The supervisor's
  merge of 544c614 kept the 0016 set_price signature (the 0015 one was a
  duplicate). ACCEPT: an end-to-end mocked check renders the card text
  with name and prices; tests. ZERO-CLICK: no operator step.
  DONE 2026-11-17 (amendments in decisions 0015 / 0016): price.card_of()
  maps the 0015 doc to the 0016 card; PriceChecker(card=state.set_price)
  publishes the first update of a press with at=<press>, later ones
  keep_time=True; Core.eval_press stamps the item check and the price
  check with one server-clock time (a reused result is re-stamped with the
  new press). GET /api/price removed (no caller, SSE-only overlay); the
  0015 doc stays in PriceChecker.latest(). tests/test_price_check.py:
  status mapping, press time, end-to-end with the contact set at run time
  (card text and overlay card carry the name and prices), opt-in off / no
  contact still zero requests.

## Lane: data

- [x] DATA-NINJA (data) poe.ninja PoE2 currency rates with ETag caching under
  the AL sidecar Cache, refresh at most hourly, attribution in the UI.
  ACCEPT: offline-cached rates shown; one request per hour max.
  DONE (core) 2026-11-17 (decision 0013): server/al/ninja.py RatesClient,
  documented endpoints only (research 0005), If-None-Match, last attempt
  persisted in <sidecar>\Cache\ninja\rates.json (one request per hour per
  endpoint, leagues once a day or skipped via "league" in local config),
  offline -> cached rates with age_s / stale; ATTRIBUTION exposed. Web
  opt-in "web_data" (default off) in the local config, GET / POST
  /api/web-data; GET /api/rates (token, Host, Origin) never blocks, starts a
  due refresh in the background. tests/test_data_ninja.py (mocked).
  ZERO-CLICK: rates refresh themselves hourly once opted in.
- [x] DATA-NINJA-UI (build) Rates panel on the dashboard from GET /api/rates
  (top currencies in the primary unit, age, stale marker) with the
  ATTRIBUTION / "Prices: poe.ninja" credit, and the one web-data toggle
  backed by GET / POST /api/web-data (off by default, says what it enables).
  After DATA-NINJA. ACCEPT: fixture rates render at desktop and phone
  width; credit visible; design-reviewer pass. ZERO-CLICK: the panel polls
  /api/rates on its own; no refresh button.
  DONE 2026-11-17 (decision 0016 fork 3): "Prices and web data" card -
  web-data checkbox (never pre-ticked, saves on change, says what it
  fetches), top 8 currencies by volume in the primary unit, kit-state pill
  (updated / old / not updating - web data is off / can't reach), league,
  "Prices: poe.ninja" credit + attribution; local poll every 5 min while
  visible; trade rows show "about N <primary>" (rate age as tooltip). The
  build-link 422 text now points at this card. web/prices.js,
  app/test/prices.test.js.
- [x] DATA-NINJA-VERIFY (review) With web access, confirm poe.ninja's PoE2
  overview response fields (lines[].id / primaryValue, core.items names,
  core.primary) against server/al/ninja.parse_overview and record them in
  research 0005; add a dated, anonymised fixture. ACCEPT: parser test on
  the real shape. ZERO-CLICK: doc + fixture row, run by a lane.
  DONE 2026-11-17 (research 0013, not 0005): paths, ETag 304, ids and values
  verified; item names are in a top-level `items`, not core.items (row
  DATA-NINJA-NAMES). The trimmed real shape is in research 0013.
- [x] DATA-NINJA-NAMES (data) server/al/ninja.parse_overview reads names
  from core.items, which holds only the 3 reference currencies; the real
  response (research 0013, 2026-11-17) has every line's name in the
  top-level `items` array (id, name, category, detailsId). Read names from
  top-level `items` first, core.items as fallback; update tests/test_data_ninja.py
  OVERVIEW to the real shape (top-level items, primary "divine"). ACCEPT:
  a test on the trimmed shape in research 0013 names every line.
  ZERO-CLICK: next /api/rates refresh.
  DONE 2026-11-17: names from top-level `items` first, `core.items` fills
  gaps (first wins); tests/test_data_ninja.py OVERVIEW is the research 0013
  trimmed shape (primary "divine", top-level items, core.rates,
  sparkline) and every line is named; a parse test covers precedence and
  the older core-only shape. Cached rates.json from before keep their old
  names until the next hourly refresh.
- [x] DATA-LICENSE (data) License check for RePoE / repoe-fork PoE2 exports
  and poe2db / poe2wiki (CC BY-NC-SA) before any snapshot is bundled; record
  in docs/decisions. ACCEPT: decision file with the ruling.
  DONE 2026-11-16 (decision 0009): bundle nothing; repoe-fork PoE2 mods /
  base_items / stats / stat_translations may be fetched at build time into
  the user's sidecar Cache only; GGG tree export disabled until confirmed;
  poe2db / wiki link-out only. Web fetch was refused this session, so the
  ruling is conservative and rests on research 0005 (DATA-LICENSE-VERIFY).
- [x] DATA-LICENSE-VERIFY (data) With web access, read the repoe-fork
  LICENSE.md, the repoe-fork.github.io/poe2 page and file names, poe2db's
  disclaimer and the wiki copyright page; cite URL + date in decision 0009.
  ACCEPT: every UNVERIFIED line in 0009 resolved or the source removed.
  ZERO-CLICK: doc-only row, run by the data lane.
  DONE 2026-11-17 (decision 0009, research 0011): repoe-fork MIT confirmed;
  bundle-nothing stands; two fetch URLs found dead (see DATA-SRC-URLS); GGG
  PoE2 tree export exists (see DATA-TREE-SRC).
- [x] DATA-SRC-URLS (data) Fix SOURCES in server/al/theorycraft/snapshot.py:
  `stats` -> repoe-fork poe2 `stats_by_file.json`, `stat_translations` ->
  `stat_translations/stat_descriptions.json` (old URLs return 404;
  decision 0009 item 4). Update tests and consumers. ACCEPT: mocked-fetch
  test uses the real file names. ZERO-CLICK: next build.ps1 run.
  DONE 2026-11-17: SOURCES fixed (cache names stay stats.json /
  stat_translations.json); no other consumer of the old names;
  tests/test_tc_snap.py test_sources_policy + test_real_source_names_mocked_fetch.
- [x] DATA-TREE-SRC (data) Confirm whether GGG publishes a PoE2 passive
  tree export (repo, data-file URL, terms); if so enable
  `SOURCES["skilltree"]` in server/al/theorycraft/snapshot.py and add its
  host to ALLOWED_HOSTS. Repo exists (grindinggear/poe2-skilltree-export,
  data.json, no license file; decision 0009 item 3 amended: fetch-only). ACCEPT: source enabled
  with a mocked-fetch test, or recorded as absent. ZERO-CLICK: the next
  build.ps1 run fetches it.
  DONE 2026-11-17: SOURCES["skilltree"] = raw.githubusercontent.com
  grindinggear/poe2-skilltree-export main/data.json -> Cache\gamedata\
  skilltree.json (fetch-only); ALLOWED_HOSTS + raw host limited to that
  repo path (HOST_PATH_PREFIX); ATTRIBUTION names the tree export.
  Reader server/al/theorycraft/treedata.py (node id -> name / stats /
  ascendancy / notable / keystone, class starts; unknown fields ignored;
  shape UNVERIFIED, see DATA-TREE-SHAPE). Build view: tree.named_nodes in
  the build snapshot when the cache exists (BuildStore tree=TreeCache,
  mtime-checked), absent otherwise. tests/test_tc_tree.py on the synthetic
  fixture tests/fixtures/skilltree_synthetic.json. Decision 0009 item 3
  "Decision" text still says DISABLED (file locked this round; the
  "What changes" amendment governs) - fold in at the next 0009 edit.
- [x] DATA-TREE-SHAPE (review) With web access, read the real
  grindinggear/poe2-skilltree-export data.json top-level keys and one
  main / notable / keystone / ascendancy / class-start node; confirm or
  fix the UNVERIFIED shape in server/al/theorycraft/treedata.py (nodes
  keyed by id, skill, name, stats, ascendancyName, isNotable, isKeystone,
  isJewelSocket, classStartIndex or classesStart, classes[].name) and
  whether PoB2 spec node ids equal the export's skill ids. ACCEPT: reader
  test on a dated, anonymised shape fixture. ZERO-CLICK: doc + fixture
  row, run by a lane.
  DONE 2026-11-17 (research 0014): real file read; id keys, skill, name,
  stats, isNotable/isKeystone/isJewelSocket, classes match; ascendancyName
  and int classStartIndex do NOT (see DATA-TREE-FIX). No shape fixture
  committed (GGG data, no license).
- [x] DATA-TREE-FIX (data) Fix server/al/theorycraft/treedata.py parse()
  per research 0014: (1) node ascendancy comes from `ascendancyId` (string
  like Warrior3), not `ascendancyName`; map id -> name via
  classes[].ascendancies[].id / name and keep ascendancy = the name (None
  when unmapped; keep id as fallback); (2) `classStartIndex` is a LIST of
  ints (real class-start nodes hold 2 entries), accept int or list; (3)
  optionally strip [Key|Shown] bracket markup from stats at display time;
  (4) update tests/fixtures/skilltree_synthetic.json and tests/test_tc_tree.py
  to the real shapes (synthetic values only); (5) check PoB2 spec node ids
  against skill ids when PoB2 data is read. ACCEPT: tests cover list
  classStartIndex and ascendancyId mapping. ZERO-CLICK: code row, build lane.
  DONE 2026-11-17: ascendancyId -> name (id fallback, legacy
  ascendancyName kept), classStartIndex int or list (legacy classesStart
  kept), display_stat strips [Key|Shown] in Node.to_dict (raw stats kept),
  fixture and tests on the real shapes, UNVERIFIED wording removed. (5):
  PoB2 spec node ids (model.py tree nodes -> TreeData.resolve) are looked
  up as export skill ids WITHOUT a check that they match; still open until
  PoB2 data is read.
- [x] UA-CONTACT (data) GGG's API and poe.ninja ask for a contact in the
  User-Agent (DATA-LICENSE-VERIFY, decision 0009 / research 0011). Add an
  optional contact value read only from gitignored config/local.json (never
  a tracked file; no email in any tracked file, leak sweep), appended to
  the webfetch / ninja / trade / snapshot User-Agent; with no contact
  configured, poe.ninja, trade2 and GGG fetches stay off even when
  web_data is on (state says why). Queued by the lane supervisor
  2026-11-17 from the coordinator's review of the round-3 data lane.
  ACCEPT: tests with and without a contact (mocked fetch); leak sweep
  clean. ZERO-CLICK: setting the contact once enables the fetches.
  DONE 2026-11-17 (build lane, decision 0015): "contact" read only from
  gitignored config/local.json (example file: empty value);
  webfetch.user_agent appends "(contact: <value>)" (cleaned: printable
  ASCII, no parentheses / backslash, max 120); ninja, trade and the
  snapshot (snapshot.user_agent, GGG sources via needs_contact) send
  nothing without it; "blocked": "contact not set" in /api/rates,
  /api/web-data, /api/price and the state price field; the value is never
  echoed. pobb.in / pastebin share links unchanged. Tests:
  test_price_check.py, test_data_ninja.py, test_trade_limiter.py.

## Lane: review

- [ ] UX-REVIEW (review) Glanceability review of dashboard and overlay
  (contrast, type scale, motion, phone width) against research 0008.
  ACCEPT: findings fixed or filed.
- [x] TEST-413-FLAKE (review) tests/test_tc_code_api.py::test_bad_inputs
  intermittently fails with WinError 10053 on the oversized-body (413)
  request: the server answers and closes before the client finishes
  sending, so the client sees a reset instead of the 413. Seen 2026-11-16
  by the data lane (passes on re-run). ACCEPT: the server drains or the
  test tolerates a reset after a 413; 50 consecutive green runs.
  ZERO-CLICK: fix lands with the suite, no manual step.
  DONE 2026-11-16: server/al/http.py _discard_body reads and drops a
  rejected body (413 / 415) before the reply, capped at DRAIN_MAX 1 MiB and
  DRAIN_TIMEOUT_S 2 s, then closes; test_rejected_body_drain_is_bounded.
  50/50 consecutive green runs.
- [ ] RES-POLICY (review) Re-read GGG's developer docs and ToU each patch
  cycle; update research 0001 and the CLAUDE.md floor if anything changed.

## Theorycraft and item optimization (decision 0004, research 0010)

Phase 1 is stdlib-only file interop with Path of Building PoE2; phase 2
adds the optional pinned LuaJIT + PoB calc subprocess. Rows run in order.
Every row carries the minimal-interaction constraint (CLAUDE.md, decision
0004): no click the app can safely make for the user, state updates itself,
and the row's own dev / test steps run unattended. ZERO-CLICK states how.

- [x] TC-CODE (build) PoB2 share-code codec in server/al: URL-safe base64 +
  zlib decode / encode (stdlib) to build XML, plus a typed build model
  (class, ascendancy, level, tree nodes, gear, skills, PoB's saved stats);
  paste-a-code API behind the token. ACCEPT: round-trip tests on fixture
  codes exported from PoB2 v0.23.1 (deflate framing confirmed); no network.
  ZERO-CLICK: a copied PoB code or share URL is taken on the AshLight
  hotkey press; the last build reloads on start.
  DONE 2026-11-16 (decision 0007): server/al/theorycraft/ codec, model,
  store; POST /api/build-code, GET /api/build; reload on start. Synthetic
  fixtures (adjudicator F1); share URLs recognized, not fetched (TC-URL);
  hotkey hook is codec.looks_like_build_code for the PRICE-1 clipboard read.
- [ ] TC-CODE-REAL (review) Confirm the codec on a real PoB2 v0.23.1 export
  (framing, root element, PlayerStat names) once a PoB2 install or an
  operator-supplied code is available; add it as a fixture only if its
  owner allows. After TC-CODE. ACCEPT: decode + parse + byte-exact round
  trip of the real code. ZERO-CLICK: a test that skips when the fixture is
  absent.
- [x] TC-URL (build) Fetch a user-pasted share URL (pobb.in, pastebin) once
  per paste: host allowlist, truthful User-Agent, size cap, no redirects off
  the allowlist (SSRF guard). After TC-CODE. ACCEPT: mocked-fetch tests; no
  other host reachable. ZERO-CLICK: the pasted URL loads like a code.
  DONE 2026-11-17 (decision 0013): server/al/theorycraft/shareurl.py takes
  only the paste id and rebuilds pobb.in/pob/<id> or pastebin.com/raw/<id>;
  server/al/webfetch.py (https, exact allowlist, no userinfo / port / IP
  literal, manual redirects re-checked, max 3, 2 MB cap, 10 s timeout,
  User-Agent required, cookies refused); POST /api/build-code fetches a
  detected URL once when web_data is on (422 off / not allowed, 502 fetch
  failure), the text goes through paste detection into the build store.
  tests/test_tc_url.py (SSRF cases, mocked).
- [x] TC-URL-VERIFY (review) With web access, confirm the raw-download
  paths pobb.in/pob/<id> and pastebin.com/raw/<id> (and whether pobb.in
  redirects) and record them in research 0010. ACCEPT: paths cited with an
  access date or shareurl.RAW_TEMPLATES fixed. ZERO-CLICK: doc row.
  DONE 2026-11-17 (research 0013): pobb.in /pob/<id> and /<id>/raw both 200
  text/plain, no redirect; pastebin /raw/<id> route exists (404 page for a
  missing id), 200 body untested. Row TC-URL-POBBIN-RAW filed.
- [x] TC-URL-POBBIN-RAW (theorycraft) shareurl.RAW_TEMPLATES uses
  pobb.in/pob/<id>, the PoB import route; pobb.in's README documents
  /<id>/raw and /u/<name>/<id>/raw as the public third-party routes
  (research 0013, 2026-11-17). Switch the pobb.in template to
  https://pobb.in/{id}/raw and accept https://pobb.in/u/<name>/<id> links
  (rebuilt as /u/<name>/<id>/raw, name charset [A-Za-z0-9_-]); update the
  module docstring and decision 0013 item 4. ACCEPT: tests/test_tc_url.py
  covers both forms and the SSRF cases. ZERO-CLICK: pasting a pobb.in link.
  DONE 2026-11-17: RAW_TEMPLATES pobb.in -> https://pobb.in/{id}/raw,
  POBB_USER_TEMPLATE https://pobb.in/u/{name}/{id}/raw; pasted /<id>,
  /<id>/raw, /pob/<id>, /u/<name>/<id>[/raw] accepted, name and id
  [A-Za-z0-9_-]{1,64} and not raw / pob / u; docstring and decision 0013
  item 4 updated. tests/test_tc_url.py: both forms, 17 new refusal cases
  (bad names, extra segments, encoded slash / traversal, userinfo, port),
  a user link through POST /api/build-code. /u/ raw route not fetched live.
- [x] TC-VIEW (build) Build view on the dashboard: gear by slot, skills,
  key stats from the XML, tree summary; "copy code for PoB" export; link out
  to poe2db / wiki pages, no copied text. After TC-CODE. ACCEPT: fixture
  build renders at desktop and phone width; no GGG art bundled.
  ZERO-CLICK: the view follows the loaded build and the live character's
  level / zone from Client.txt with no refresh button.
  DONE 2026-11-17 (decision 0014): dashboard Build card (web/tc.js
  buildView); the state carries a build rev, so the view refetches by
  itself; paste box loads on paste; copy button plus a selectable code box
  (ruling F4); poe2db / wiki links for gems and uniques.
  app/test/tc_view.test.js; screenshots in the sidecar Scratch ui-features.
- [x] TC-JSON (build) Character JSON paste import (GGG reference Character
  / Item types, PoE2 fields skills, passives.specialisations, runeMods) into
  the build model. After TC-CODE. ACCEPT: fixture JSON maps to the same
  model as its PoB code; unknown fields ignored, not fatal.
  ZERO-CLICK: format (code, URL, JSON) auto-detected; no import dialog.
  DONE 2026-11-16: server/al/theorycraft/charjson.py turns character JSON
  into PoB build XML read by model.parse (same model, persists as a share
  code); paste.py detects json / url / code; POST /api/build-code takes
  {"code": text} of any format or {"character": {...}}, token checks
  unchanged. Jewel socket placement needs tree data (not mapped).
  tests/test_tc_json.py (synthetic CHAR_JSON vs JSON_TWIN_XML).
- [x] TC-SNAP (data) Build-time snapshot tool: GGG poe2-skilltree-export
  plus the RePoE fork PoE2 mods / base_items / stats / stat_translations
  into the AL sidecar Cache with a manifest (URL, fetch date, sha256);
  attribution line in the UI. After DATA-LICENSE. ACCEPT: manifest written;
  no runtime fetch; tool idempotent.
  ZERO-CLICK: runs inside scripts/build.ps1, no manual step.
  DONE 2026-11-16 (decision 0009): server/al/theorycraft/snapshot.py into
  Cache\gamedata\ with manifest.json, AshLight/<version> User-Agent, 24 h
  skip + ETag / sha256 no-op, https + host allowlist, offline never fatal;
  build.ps1 step (opt-out -NoSnapshot / AL_NO_SNAPSHOT). Skilltree source
  disabled (DATA-TREE-SRC); repoe-fork file names unverified until
  DATA-LICENSE-VERIFY. ATTRIBUTION exposed; UI line is TC-SNAP-UI.
  Mocked-fetch tests only (tests/test_tc_snap.py).
- [ ] TC-SNAP-UI (build) Show snapshot.ATTRIBUTION (decision 0009) in the
  dashboard footer / About and the overlay About wherever snapshot data is
  used; expose it via an API field. After TC-SNAP. ACCEPT: text visible,
  design-reviewer pass. ZERO-CLICK: shown automatically when the cache
  exists.
- [x] TC-EVAL (build) Item evaluation phase 1: the clipboard item from the
  existing hotkey read (decision 0003, one read per press) scored by
  editable stat weights against the build's item in that slot; result on the
  dashboard and a compact overlay card. After TC-CODE, TC-SNAP. ACCEPT:
  fixture items scored; no second clipboard read; no input to the game.
  ZERO-CLICK: the one hotkey press shows price and upgrade verdict together.
  DONE 2026-11-16 core: server/al/theorycraft/item.py (PoE2 Ctrl+C /
  Ctrl+Alt+C and PoB item text parser, never fatal, English only),
  weights.py (mod text -> stat key, defaults written to
  <runtime>/theorycraft/weights.json, validated PUT), evaluate.py (pure
  evaluate(item_text, build, weights): class -> slot, score = sum(w * v),
  upgrade / sidegrade / downgrade with per-stat delta, both rings / charms
  compared, best swap headlined); model.SLOTS + Build.equipped; API POST
  /api/eval {"item", "slot"?}, GET / PUT /api/weights (token, Host,
  Origin as /api/build-code). Never reads the clipboard; TC-SNAP data not
  needed. Base defences / weapon DPS not compared (TC-DELTA). Synthetic
  fixtures only (tests/test_tc_eval.py, tests/test_tc_eval_api.py). UI
  part moved to TC-EVAL-UI.
- [x] TC-EVAL-UI (build) Dashboard view + compact overlay card for the
  TC-EVAL result (verdict, score delta, top per-stat deltas, both rings),
  plus a weights editor on the dashboard backed by GET / PUT /api/weights;
  design-reviewer pass. After TC-EVAL, PRICE-1 (the hotkey read). ACCEPT:
  fixture result renders at desktop and phone width; overlay card in the
  RAM / FPS budget; no second clipboard read. ZERO-CLICK: the hotkey press
  posts the read text to /api/eval and the card appears; no evaluate button.
  DONE 2026-11-17 (decision 0014): Alt+Shift+E (config eval_hotkey) in
  app/eval_hotkey.js, one clipboard read per press (ruling F1, ahead of
  PRICE-1, which reuses the press); live.py publishes the card in the state
  and re-scores on a weights or build change; words in state.py
  eval_card_text; dashboard Item check + Stat weights editor (saves on
  change); overlay card 20 s in the one card slot (ruling F2, design 0001
  section 10 amended). Tests: test_eval_text.py, app/test/eval.test.js.
- [ ] TC-UPGRADE (build) Upgrade search: weighted trade2 query ("type":
  "weight" stat group) from the local weights, complexity under 200, one
  search per user action, through the PRICE-1 limiter (X-Rate-Limit-*,
  Retry-After), opt-in, no POESESSID; prices shown with poe.ninja rates.
  After PRICE-1, TC-EVAL, DATA-NINJA. ACCEPT: query-builder tests; limiter
  shared, not duplicated; no request without the opt-in.
  ZERO-CLICK: once opted in, the same hotkey press that evaluates the item
  queues the search; results appear when the limiter allows, no extra click.
- [ ] TC-PIN (build) Phase 2 setup: tracked pin file (PoB-PoE2 tag, commit,
  archive sha256; LuaJIT version, sha256; no absolute paths); setup.ps1
  step fetches the PoB source archive to the sidecar Cache and builds or
  accepts LuaJIT into Build, hash-verified, off by default; THIRD-PARTY
  notices with PoB's MIT and component notices. ACCEPT: hash mismatch
  refuses; re-run is a no-op; test_sidecar_paths covers the new paths.
  ZERO-CLICK: one opt-in toggle; setup.ps1 does the rest unattended.
- [ ] TC-BRIDGE (build) Fresh stdio JSON bridge (our own Lua, no code from
  pob-mcp / pob2-mcp) driving the unmodified pinned PoB checkout via
  luajit.exe, plus a Python client in server/al: load build XML, set an item
  from item text, return outputs; timeout kill; core runs without it.
  After TC-PIN. ACCEPT: outputs on a fixture build match PoB GUI within 0.1
  percent; tests skip cleanly when the component is absent.
  ZERO-CLICK: the bridge starts on first need and restarts itself on a crash.
- [ ] TC-DELTA (build) PoB-backed evaluation: DPS and EHP delta of the
  clipboard item vs the equipped one, and per-mod weights from PoB deltas
  (offence and EHP) feeding TC-UPGRADE in place of hand weights. After
  TC-BRIDGE, TC-EVAL. ACCEPT: delta tests on fixtures; falls back to stat
  weights with a visible notice when the component is off.
  ZERO-CLICK: deltas recompute on item or build change, no Calculate button.
- [ ] TC-DRIFT (review) On each PoB-PoE2 release: run the bridge tests
  against the new tag, then move the pin in one commit, or hold it and
  record why. ACCEPT: pin moved or a dated hold note in decision 0004.
  ZERO-CLICK: a loop check spots the new tag and runs the tests unattended.
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

## Game settings advisor (operator order 2026-11-16)

- [x] GFX-ADVISOR (build) Optional dashboard panel: read this machine's
  hardware (CPU, GPU and VRAM, RAM, displays with resolution and refresh)
  through stdlib calls or Windows' own CIM query, and recommend PoE2
  graphics settings for it, Windowed Fullscreen required (decision 0002).
  RECOMMEND ONLY: the user applies them in game; AshLight never reads or
  writes the game's config files (ToS floor: no game file modification).
  ACCEPT: recommendation tests on fixture hardware profiles; no file under
  the game's folders opened; the panel says "apply in game".
  ZERO-CLICK: hardware read on first start and on change, panel ready with
  no button; nothing runs while the game is focused.
  DONE 2026-11-17 (decision 0014, research 0012): server/al/gfx.py, one
  hidden powershell.exe CIM query + the display-adapter registry key
  (VRAM), pure parse / recommend; GET /api/gfx; collapsed dashboard panel
  read on its first open (ruling F3: a dashboard click, so the game is not
  focused; deviation from "read on first start" recorded), kept for the
  core's life. Opens no file (AST test). tests/test_gfx.py.

## Design and UX audit (operator order 2026-11-16)

Uses the design-reviewer agent (.claude/agents/design-reviewer.md) and the
design docs in docs/design/, both made by a separate agent.

- [x] DESIGN-AUDIT (review) Design / UX audit pass of the dashboard, overlay
  and the new theorycraft and advisor panels with the design-reviewer agent
  against docs/design/. ACCEPT: findings fixed or filed as ROADMAP rows;
  report in docs/design/. ZERO-CLICK: count the clicks each play-session
  flow needs and file a row for every one that can go. First pass done
  (ref e909dc8, docs/design/0002-first-audit.md): findings filed as the DS-*
  rows below; later passes (theorycraft and advisor panels) stay open.
- [ ] DESIGN-GATE (review) Make the design-reviewer pass a standing step for
  every row that touches web/ or app/ (review lane after build). After
  DESIGN-AUDIT. ACCEPT: lane prompt or loop rule names the step; one row
  reviewed through it. ZERO-CLICK: runs in the loop, no manual trigger.
  Partly done: the lane prompt names the step (DS-REVIEW-HOOK); "one row
  reviewed through it" waits for LOOP-ARM (the loop is not armed).

Rows filed by the first audit (docs/design/0002-first-audit.md; S1 = worst).
Run after DESIGN-AUDIT, ahead of DESIGN-GATE.

- [x] DS-OPACITY (build, S1) Raise the overlay opacity floor to 0.9 in
  server/al/layout.py, app/shared/layout.js and the dashboard slider; clamp
  older saved layouts; update layout tests. ACCEPT: no overlay text pair
  under 4.5:1 over a white scene at the floor (design 0001 5.2).
  ZERO-CLICK: saved layouts clamp themselves on load; no user action.
- [x] DS-SCALE (build, S2) Raise the overlay scale floor to 0.95 in the same
  three places so 13px text never renders under 12px. ACCEPT: layout tests
  and a design 0001 O3 check. ZERO-CLICK: old layouts clamp on load.
- [x] DS-NLM (build, S2) Rewrite summarize to the design 0001 section 9
  templates with honest defaults and no internal ids; add
  tests/test_summarize.py with one exact-output assert per template.
  ACCEPT: tests green. ZERO-CLICK: text is generated from events; nothing
  to configure.
- [x] DS-TRADE-EXPIRE (build, S2) Trade requests expire 10 minutes after
  arrival; the dashboard states the rule; Dismiss stays. ACCEPT: expiry
  test with a fake clock. ZERO-CLICK: stale requests drop off by themselves.
- [x] DS-HUD-AFK (build, S2) Show AFK / DND in the overlay status slot; add
  the field to the render gate and a test. ACCEPT: test green.
  ZERO-CLICK: follows the log's AFK / DND lines automatically.
- [x] DS-HUD-EMPTY (build, S3) A sensible HUD before the first snapshot (no
  lone separator). ACCEPT: render test for the empty state.
  ZERO-CLICK: fills in by itself when the first snapshot arrives.
- [x] DS-HUD-CLIP (build, S3) Clip the zone before adding "(HO)"; glanceable
  stash position text. ACCEPT: render test with a long zone name.
  ZERO-CLICK: purely display; no input.
- [x] DS-REVIEW-HOOK (process) Run the design-reviewer agent on every change
  to web/, app/overlay/, app/shared/ or summarize before commit (lane prompt
  or pre-commit reminder). Folds into DESIGN-GATE. ACCEPT: rule named in the
  lane prompt or loop. ZERO-CLICK: runs in the loop, no manual trigger.
  Done (UI-REVIEW-2, adjudicator ruling in docs/design/0003-second-audit.md):
  DESIGN_RULE in tools/loop_prompts.py GATES + verify_prompt, warn-only
  tools/design_gate.py in .githooks/pre-commit, ledger
  docs/design/reviews.log; tests/test_design_gate.py.
- [x] UI-REVIEW-2 (review) Second UI/UX audit: live dashboard (desktop and
  phone, light and dark, offline, first run) and the overlay rendered with
  synthetic state, merged with the design-reviewer agent into
  docs/design/0003-second-audit.md. ACCEPT: every S1 / S2 fixed, reviewer
  re-run reports S1=0 S2=0. Done: before S2=4 S3=8 S4=7, after 0 open.
  ZERO-CLICK: no click added; the hotkey is now named on the dashboard.
## Ops

- [ ] LOOP-ARM (build) Arm the lane loop as a scheduled task (every 15 min,
  IgnoreNew, hidden) after one supervised dry-run tick and one real tick on a
  trivial row. ACCEPT: task read back; first tick's progress file done.
- [x] CORE-DETACH (build) run.ps1 starts the core and overlay via WMI
  Win32_Process.Create (scripts/al_detach.ps1), outside the caller's tree and
  job; core.log records unhandled exceptions and native faults;
  ops/runtime/core.alive heartbeat (30 s, removed on clean exit) bounds the
  time of a silent kill. Cause of the 2026-11-16 21:57-22:12 death not
  proven: no crash event, no log line, Start-Process children survived probe
  sub-agent exits.
- [x] CORE-KEEPALIVE (build) run.ps1 starts a detached stdlib supervisor
  (server/al/keepalive.py, single-instance) that relaunches the core when its
  pid is gone with core.alive left behind, or when it hangs (heartbeat 90 s
  stale and /api/health failing); backoff 2/10/30/60/120 s, cap 5 per 15 min
  with a logged give-up. scripts/stop.ps1 writes ops/runtime/stop.request:
  the core exits cleanly and is not restarted (decision 0005). End-to-end
  test kills a real core on a tmp runtime and sees it back. Takes effect on
  the next run.ps1.
- [x] OPS-STOP (build) scripts/stop.ps1 leaves the keepalive supervisor
  and the Electron overlay running; it must stop every AshLight process
  (core via stop.request, then supervisor and overlay by their recorded
  pids / single-instance locks), never the game client. ACCEPT: after
  stop.ps1 no AshLight python / pythonw / electron process remains (test on
  a tmp runtime). ZERO-CLICK: one stop.ps1 call, no manual kill.
  DONE 2026-11-16 (decision 0010): server/al/procs.py proves pids ours (pid
  + creation time; electron.exe only under app/node_modules/electron/dist);
  stop.ps1 then stops supervisor and overlay; supervisor honours
  stop.request during a restart backoff. tests/test_procs.py runs the real
  stop.ps1 on a tmp runtime (core, supervisor, overlay + child gone; an
  unrelated electron.exe left alone).
- [x] OPS-RUN-IDEMP (build) run.ps1 -NoBrowser does not start the overlay,
  and re-running run.ps1 -Overlay spawns a second supervisor that only exits
  on its own. Make run.ps1 idempotent per component: core, supervisor and
  overlay each started only when not already live. ACCEPT: two run.ps1 calls
  in a row leave exactly one core, one supervisor, one overlay. ZERO-CLICK:
  any run.ps1 call converges to the full running set.
  DONE 2026-11-16 (decision 0010): run.ps1 follows `procs plan`; overlay
  starts by default when installed (-NoOverlay opts out, -Overlay kept),
  pid recorded in ops/runtime/overlay.pid. Convergence and "re-run starts
  nothing" tested in tests/test_procs.py (decision logic + live tmp set).
- [x] API-TOKEN-HDR (review) The API token is accepted only as the ?token=
  query parameter, not as an Authorization Bearer header. Confirm intended
  (SSE / EventSource cannot set headers) and document it in decision 0002 or
  the API notes, or accept both. ACCEPT: documented and covered by a test.
  ZERO-CLICK: no operator step.
  DONE 2026-11-16: X-AL-Token was already accepted; Authorization: Bearer
  added, ?token= kept for EventSource; Host / Origin unchanged and checked
  first. Decision 0002 "API token"; tests/test_api_token_hdr.py.
- [x] OPS-OVL-PID (build) run.ps1's overlay no-op line prints a child
  electron pid (e.g. the NetworkService utility process) instead of the
  recorded main pid in ops/runtime/overlay.pid; procs status should report
  the main process. Seen 2026-11-16 by the lane supervisor after the
  restart (overlay.pid and the process tree were correct; message only).
  ACCEPT: the no-op line and procs status name the overlay.pid process;
  test. ZERO-CLICK: no operator step.
  DONE 2026-11-16: procs.overlay_main_pid(); status "pid" is the recorded
  main process when live (children stay in "pids"; no record = lowest
  scanned pid). run.ps1 already prints status.overlay.pid, so unchanged.
  tests/test_procs.py.
- [x] LANE-CHECKLIST (build) tools/al_lane.py run_lane wrote
  progress/lane-<i>.json without the FLEET item-13 d "checklist" and with an
  unrealistic ETA (eta_s 416 vs 400-450 s runs plus overhead, pct stuck at
  20), so the file read STALE at 2x ETA. ACCEPT: checklist on every write,
  realistic ETA, file kept fresh while the run lasts. ZERO-CLICK: lanes and
  the loop carry it with no operator step.
  DONE 2026-11-16: run_lane(checklist=) normalises rows and passes them on
  every write (done = [], failed keeps them); lane_eta = history median
  floored at 900 s (code) / 300 s (read); a Heartbeat thread rewrites the
  row every 90 s, pct = elapsed / eta in 5..95, eta_s = remaining (min
  300 s). CLI `al_lane.py run --item "ID: task"` / --checklist-file;
  al_loop lane_worker passes lane_checklist(rec). The kit spawn only closes
  the row (close_progress keeps the checklist), so no kit change.
  tests/test_al_lane.py, tests/test_al_loop.py.
- [x] CORE-AUTOSTART (build) Optional logon autostart of run.ps1 (scheduled
  task, hidden, opt-in recorded), filed by decision 0005 option C.
  ACCEPT: after a logon the core answers with no input. ZERO-CLICK.
  DONE 2026-11-17 (opt-in, operator enables with `scripts\autostart.ps1
  -Enable`; decision 0011): current-user task "AshLight Autostart" at
  logon +30 s, Limited, wscript + scripts/autostart_launch.vbs runs
  run.ps1 -NoBrowser -Autostart hidden; opt-in in gitignored
  ops/runtime/autostart.json, run.ps1 -Autostart is a no-op without it;
  -Disable / -Status / -DryRun; tests/test_autostart.py (dry-run only).
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
- [ ] PUB-NAME (review) Manual poe2wiki check that "Ashlight" is not a GGG
  proper noun (decision 0001).
- [ ] OPERATOR: create the GitHub remote when the operator wants to publish
  (then lift the pre-push refusal in the same change, CI workflow with the
  kit's fleet_identity_guard.yml as a required check).
