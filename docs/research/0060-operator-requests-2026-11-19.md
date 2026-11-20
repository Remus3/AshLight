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

## 7. Follow-up 2026-11-19: licence of poe2wiki and poe2db

Question: "non-commercial licence - explain; if AshLight uses a different
licence, will that allow it?" No new fetch was possible:
`python tools/webfetch.py check` refuses poe2db.tw and www.poe2wiki.net
for every path tried (General_disclaimer, the Copyrights page,
robots.txt, api.php), reason "poe2db and wiki hosts are never read by a
dive (decision 0050)" (2026-11-19). Everything below is what is already
recorded, with its age.

- poe2db: "Wikis Content is available under CC BY-NC-SA 3.0 unless
  otherwise noted", (c) 2014-2026 PoE2DB, GGG holds the game copyright,
  some articles adapted from the Project PoE Wiki
  (https://poe2db.tw/General_disclaimer, read first-hand 2026-11-16,
  research 0005, 0011; decision 0009 line 9). The page has no scraping,
  crawling or API terms at all: an absence, not a prohibition. No public
  API exists. Licence version: CC BY-NC-SA 3.0 (unported not stated).
- poe2wiki: CC BY-NC-SA 3.0 Unported for content the wiki may lawfully
  license; game assets GGG copyright (search summary of
  https://www.poe2wiki.net/wiki/Path_of_Exile_2_Wiki:Copyrights,
  2026-11-16; the page itself, General_disclaimer and COPYING returned an
  Anubis bot wall, research 0011). UNVERIFIED first-hand. The PoE1 wiki
  data query API was also bot-walled (research 0005); poe2wiki api.php
  answered name searches on 2026-11-16 (research 0009), so its
  reachability is mixed. robots.txt and any API terms: UNREAD (refused
  by the allow-list).
- What the terms mean. BY: credit the source. NC: no use primarily
  intended for commercial advantage. SA: an adaptation of the material
  must carry the same licence (3.0 Unported section 4(b) also allows a
  later version with the same elements). SA binds adaptations of the
  licensed material, not separate code that reads it at run time.
  CC 3.0 does not license sui-generis database rights (CC 4.0 does).
  Creative Commons advises against its licences for software.
- Would relicensing AshLight help? No. Relicensing does not grant the
  missing permission to fetch (no poe2db API, a wiki bot wall). An NC
  licence would make AshLight not OSI open source and clash with the
  Apache-2.0 vendored kit (decision 0047), and the ToS floor already
  bars revenue, so NC gains nothing practical. SA would only matter if
  AshLight shipped an adaptation of the data, which decision 0009 already
  forbids.
- The other route (decision 0009 pattern): a build-time, opt-in,
  attributed fetch into the player's own sidecar cache, never in the repo
  or a release. Then NC / SA stay on the player's local copy and do not
  reach AshLight's Apache-2.0 code. It is closed today only because 0009
  item 4 refuses poe2db / wiki fetches until a source publishes an API
  or app-use terms.
- Is the data there? From research 0060 section 3 S7 and the recorded
  page summaries (not re-read): the wiki's Cargo item tables and poe2db
  item pages carry vendor values, salvage / disenchant results and wider
  drop sources; any drop "rate" there is a community estimate or a
  datamined weight, since GGG publishes none (research 0060 section 3).
  Reliability: community-written, unknown freshness per patch. If ever
  shown, every such field is labelled "community estimate" with source
  and snapshot date.

Ruling: decision 0083 amendment 2026-11-19 (keep Apache-2.0, link only,
the 0009 snapshot route only once a source permits app use).

## 8. Follow-up 2026-11-19: Kindler and collapse

- Kindler: tabs reorder, rename and close with a confirm; deterministic
  ranking by PoB numbers with a fixed tie order; stages from levelling to
  maps carrying gems, links, gem timing, passive order, ascendancy and
  per-slot item focus; a per-tab "follow Play guidance" toggle reading
  the zone, act and level the snapshot already publishes. Decision 0081
  amendment 2026-11-19.
- Collapse ("app not browser, app only"): state in the core
  (ops/runtime/ui_layout.json via GET / PUT /api/ui/layout), buttons only
  inside the desktop client's companion window. Decision 0082 amendment
  2026-11-19.
