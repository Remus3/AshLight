# 0060 - Operator requests 2026-11-19: item info, build generator, header, collapse

Date: 2026-11-19. Input for decisions 0081 (Kindler build generator), 0082
(UI: item info popover, header and version, collapsible cards) and 0083
(item info data sources), and for the plan file
docs/plan/10-operator-requests-2026-11-19.md. Every web read below went
through `python tools/webfetch.py get <url>` (decision 0050 allow-list),
accessed 2026-11-19, web_data on. No poe2db, wiki, GGG forum or trade
site request was made. Sidecar cache files are the app's own build-time
snapshots (decision 0009), read locally.

## 1. The requests (operator intent)

1. Items and prices: the item name in a currency row ("Mirror of Kalandra
   5,808 Divine Orb") becomes a soft-select; a click opens a tooltip with
   item info (market price, rarity, where found, which monsters or bosses
   drop it and at what rate, NPC price, disenchant results and rate,
   anything else useful); a click anywhere else closes it.
2. Build tab: a pasted-build sub-tab (today's panel) plus one or more
   "generate a build" sub-tabs (+ / -), persisted, started from a class
   and league picker, tuned by tri-state toggles ("not sure" allowed);
   the engine picks the rest. Does the theory engine have a name?
3. Remove the visible "AshLight" text left of the Play tab; show the app
   version and build number.
4. Collapsible panels; open panels take the freed space.

## 2. What the code and plan already hold

- Header: web/index.html line 58, `<h1 class="brand">` with the mark
  (PLAY-TD-09C-BAR, wave 6, landed) and the text "AshLight".
- Version: server/al/buildinfo.py (RUN-BUILD-STAMP-CORE, wave 10, landed)
  gives `build_id()` = VERSION plus "+<12 hex>" (".dev" while hot reload
  is on); /api/version and /api/health carry it. Package
  RUN-BUILD-STAMP-UI (wave 13, open) already puts the build id in the
  dashboard footer, overlay About and tray tooltip. Target design A puts
  the version in Settings > About and data (docs/plan/03 section 4).
- Prices: web/prices.js ratesView (top rates rows, plain text names);
  movers and price watch rows likewise. No row has an info control.
- Build tab: one #buildbox card (web/tc.js; server/al/theorycraft/).
  The bridge (decision 0022) offers load_build (XML), set_item, outputs
  and main_skill: enough to score a composed PoB build, nothing more.
- Target design A (docs/plan/03 section 4, ruled): Build and items and
  Run are fixed 3 x 2 card grids, no tab scrolls, lists page, "no fold
  can grow a card"; Play is the fixed cockpit (decision 0075 reserved).
- No ROADMAP row or package covers an item info popover, a build
  generator, a header text removal or card collapse (grep of ROADMAP.md
  and docs/plan/packages.json for collaps, tooltip, popover, generat,
  archetype, brand: none besides RUN-BUILD-STAMP-UI and PLAY-TD-09C-BAR).
- No engine name exists anywhere in the repo.

## 3. Item info: sources and fields (request 1)

S1. Clipboard text on the player's own key press (decision 0003). Fills
    name, base, item class, rarity, stack size, item level,
    requirements, mods, corrupted, the item's own description text. Only
    for the item just checked; a price row has no clipboard text.
S2. repoe-fork PoE2 export, repository repoe-fork/poe2, data/,
    version.txt 0.5.5.10.
    https://api.github.com/repos/repoe-fork/poe2/contents/data and
    .../contents/version.txt; parser source
    https://api.github.com/repos/repoe-fork/repoe/contents/RePoE/parser/poe2
    (base_items.py, uniques.py, world_areas.py). Licence: code MIT, data
    owned by GGG (research 0011); build-time sidecar snapshot only,
    attributed, never bundled (decision 0009).
    - base_items.json: name, item_class, drop_level, tags,
      release_state (cached copy of 5,496 entries: released 5482,
      unique_only 9, unreleased 3, legacy 2), implicits, requirements,
      properties.stack_size, stack_size_currency_tab, description,
      directions, full_stack_turns_into. Examples from the cache: Mirror
      of Kalandra drop_level 35, stack 10, description "Creates a
      [Mirrored] copy of an item"; Divine Orb drop_level 35, stack 10;
      Exalted Orb drop_level 5, stack 20; shards stack 10 and turn into
      their orb.
    - uniques.json: name, item class, art. The repoe-fork parser says
      item drop rates cannot be found in the game files
      (RePoE/parser/poe2/uniques.py line 51).
    - world_areas.json: per area name, act, area_level, town, waypoint,
      connections, bosses and packs as monster ids with spawn weights;
      no monster display names, no loot.
    - Not present for PoE2: any drop pool, vendor recipe, item spawn by
      area, essence or currency exchange file.
S3. Path of Building PoE2, src/Data at dev
    (https://api.github.com/repos/PathOfBuildingCommunity/PathOfBuilding-PoE2/contents/src/Data?ref=dev).
    MIT (research 0011, 0037); data headers credit GGG. Useful text:
    CurrencyNames.lua (currency id to name), WorldAreas.lua (per zone
    monster and boss DISPLAY names), Uniques/*.lua (about 51 of about
    427 uniques in 19 sampled files carry a PoB-written "Source:" line
    naming a boss and area, or "No longer obtainable"), QuestRewards.lua.
    Decision 0037's amendment allows only TradeSiteStats.lua to be text
    parsed, so any other file needs a ruling (decision 0083).
S4. GGG Data Exports (https://www.pathofexile.com/developer/docs/data):
    GGG gives no in-game data outside its supported APIs except the
    passive trees. No item, drop, vendor or monster export.
S5. GGG API Reference
    (https://www.pathofexile.com/developer/docs/reference): the Currency
    Exchange endpoint (web.poecdn.com/api/currency-exchange/poe2) gives
    hourly history only (volume, stock, lowest / highest ratio per
    pair), never the current hour; it stays out until AshLight has a
    registered client (ruling of 2026-11-17, research 0018 and 0035
    F11). The Item type has no price, drop or vendor field.
S6. poe.ninja PoE2 economy (no new fetch; research 0019, 0036): price in
    divine, volume, 7-day sparkline, icon, category, detailsId for
    stackables; price, listing count, level required, variant, flavour
    text for uniques. Opt-in web_data, credit "Prices: poe.ninja"
    (decisions 0013, 0015 to 0017, 0026).
S7. poe2db.tw and poe2wiki.net: CC BY-NC-SA 3.0 (research 0005, 0011),
    no scraping permission, the wiki behind a bot wall, refused by the
    allow-list (decision 0050). They alone hold vendor values, salvage
    yields, wider drop sources and community rate estimates. Their text
    cannot be copied into Apache-2.0 AshLight (decision 0047); a link
    the player opens is the most AshLight can offer.

Honestly unknown from every permitted source:
- Drop rates or weights for any item: GGG publishes none; never shown.
- Which monsters or zones drop a currency or base: only drop_level (the
  lowest area level the base can drop in) exists; anything more is an
  inference and must say so.
- Boss loot tables: none exported; only PoB's Source lines name a boss,
  with no rate.
- NPC vendor prices: no field in any permitted source.
- Disenchant / salvage yields and rates: no export; only "10 shards make
  1 orb" (full_stack_turns_into) is data.
- Per-league "drop disabled": only release_state and PoB's "No longer
  obtainable".
- A current-hour exchange rate from GGG.

## 4. Build generator (request 2)

- Decision 0004 bars an own calc engine; PoB through the bridge is the
  only calculator. A generator is therefore authored archetype templates
  (skill, supports, tree route as node ids, item stat priorities) in an
  AshLight JSON table, scored by PoB over a bounded candidate set; with
  the calc component off it can only show a template, unscored.
- Budgets: decision 0028 (384 MB Lua heap ceiling) and 0024 R7 calc
  budgets; one worker; calc work must not cost game FPS (decision 0002).
- League list: the poe.ninja league cache (decision 0026) while web_data
  is on; nothing new on the network.
- Name: none existed. Proposed "Kindler" (decision 0081). Checked: no
  hit in the repo, the docs or the sidecar game-data caches (2026-11-19);
  not among the tools named in research 0054, 0055 and 0006 that the
  ruling listed (Path of Building, Craft of Exile, poe.ninja, poe2db,
  Awakened PoE Trade, Exiled Exchange 2, Sidekick, Exilence, Lailloken
  UI, Maxroll, Mobalytics, FilterBlade, NeverSink, PoE Lurker,
  Acquisition, Procurement, exile-leveling, PoE Planner, poe.re). Not
  checked on the open web: the allow-list has no search host. Runner-up
  "Emberwright" is a test character name in tests/test_parser.py, so
  "Hearthwright" is the usable runner-up.

## 5. Header, version, collapse (requests 3 and 4)

- The Electron window title already reads AshLight; a plain browser tab
  shows document.title. The page still needs a heading: a visually
  hidden h1 (web/app.css `.sr-only` exists, line 89).
- Collapse vs design A: a collapsed card shrinks to its title row inside
  the fixed grid; open cards in its column share the height by grid fr
  tracks and the pager shows more rows. Nothing grows past its cell.

## 6. Rows proposed

See docs/plan/10-operator-requests-2026-11-19.md (packages ITEM-INFO-*,
KINDLER-*, UI-HEADER-VERSION, UI-CARD-COLLAPSE).
