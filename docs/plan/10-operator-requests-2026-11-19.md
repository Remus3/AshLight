# 10 - Operator requests 2026-11-19: drafted rows and packages

Date: 2026-11-19. Status: DRAFT for a later wave. Nothing here is in
ROADMAP.md or docs/plan/packages.json yet: the wave integrator lands it
(it is the only writer of those files, decision 0077). Research: 0060.
Rulings: decisions 0081 (Kindler), 0082 (UI), 0083 (item info data).

## 1. Requests and rulings, one line each

- R1 item info tooltip: one shared click popover (web/iteminfo.js) over a
  cache-only GET /api/iteminfo; shows only sourced fields (item class,
  price / trend / volume from poe.ninja, stack and shard rule,
  description, release state, PoB "where found" for about 51 uniques);
  drop rates, monster drop lists, NPC prices and disenchant yields are
  CUT (no permitted source; GGG publishes no rates; poe2db / wiki are
  CC BY-NC-SA and refused, decision 0050), replaced by a "More on
  poe2db" link the player opens. Decisions 0082 part 1, 0083.
- R2 build generator: "Kindler" = AshLight-authored archetype templates
  scored only by Path of Building over at most 12 candidates in 60 s, on
  the Generate click; unscored template when the calc component is off;
  up to 6 tabs in ops/runtime/gen_builds.json; 6 tri-state toggles.
  Decision 0081 (amends 0004).
- R3 header and version: visible "AshLight" text removed (sr-only h1
  kept); "Version 0.1.0, build <12 hex>" in the footer and Settings >
  About and data, by widening RUN-BUILD-STAMP-UI. Decision 0082 part 2.
- R4 collapse: Build and items and Run cards collapse to their title
  row; open cards in the column share the height (grid fr tracks), the
  pager shows more rows; per viewer in localStorage; Play never
  collapses. Decision 0082 part 3.

## 2. Existing rows that already cover part of this

- RUN-BUILD-STAMP-UI (wave 13): build id in the footer, overlay About and
  tray tooltip. R3's version part is an amendment of this package (see
  section 4), not a new package.
- PLAY-TD-09C-BAR (wave 6, landed): the header mark; UI-HEADER-TEXT
  edits the same bar and its tests.
- TD-21 Settings rail (design A, docs/plan/03 section 4 item 6): Settings
  > About and data holds the version; RUN-BUILD-STAMP-UI writes into it
  once TD-21 has landed, else into the Settings tab's About fold.
- No row covers an item popover, a build generator or card collapse.

## 3. ROADMAP rows (draft; wave numbers are placeholders after wave 37)

### Wave 38: operator requests 2026-11-19, cores

- [ ] ITEM-INFO-CORE (build) Item info lookup: token-gated GET /api/iteminfo over local caches
  (decision 0083). ACCEPT: python -m pytest -q tests/test_iteminfo.py passes: exact-name match
  over base_items, the uniques snapshot and the price book; unknown fields absent; no network
  call (fetch patched to raise); 200 with empty fields for an unknown name; name length cap;
  token, Host and Origin checks apply. ZERO-CLICK: Answers from what is already cached; no
  setting. BLOCKED: session wave 38.
- [ ] UI-HEADER-TEXT (build) Drop the visible AshLight text left of the tabs; sr-only h1 kept
  (decision 0082 part 2). ACCEPT: python -m pytest -q tests/test_brand_assets.py
  tests/test_a11y.py passes: the bar has the mark img (alt "" and aria-hidden), an h1 whose
  text is AshLight inside .sr-only, no visible brand text; document.title is AshLight.
  ZERO-CLICK: Automatic. BLOCKED: session wave 38.
- [ ] UI-CARD-COLLAPSE (build) Collapsible cards on Build and items and Run; open cards take
  the freed height (decision 0082 part 3). ACCEPT: python -m pytest -q
  tests/test_card_collapse.py tests/test_a11y.py passes and npm test --prefix app passes:
  every card on those tabs has one title button with aria-expanded; Play regions and
  Settings have none; state survives a reload (localStorage) and a storage failure means
  all open; an alert expands its card. ZERO-CLICK: Remembered per viewer; nothing to set.
  BLOCKED: session wave 38.
- [ ] KINDLER-DATA (data) Kindler archetype table server/al/data/archetypes.json and its
  checked loader (decision 0081). ACCEPT: python -m pytest -q tests/test_kindler_data.py
  passes: every entry has src and checked, conditions are JSON only, every route node id
  exists in the cached tree export or is dropped with a note, the file hot reloads.
  ZERO-CLICK: Reloads by itself on change. BLOCKED: session wave 38.
- [ ] KINDLER-STORE (build) Kindler tabs store ops/runtime/gen_builds.json (decision 0081
  point 7). ACCEPT: python -m pytest -q tests/test_kindler_store.py tests/test_settingsio.py
  passes: schema 1, at most 6 tabs, one .bak, Saver retry, no item text, emptied by Clear run
  history, exported through the settings allow-list, an import never turns web_data on.
  ZERO-CLICK: Saved on every change. BLOCKED: session wave 38.

### Wave 39: operator requests 2026-11-19, engine and popover

- [ ] ITEM-INFO-POB-TEXT (data) Text-parse PoB CurrencyNames.lua, WorldAreas.lua and the
  Uniques Source lines under sha256 pins (decision 0083 point 3, amends 0037). ACCEPT: python
  -m pytest -q tests/test_tc_pobtext.py tests/test_tc_pob_drift_guard.py passes: a hash
  mismatch omits the field, nothing is run as Lua, repoe-fork wins conflicts, no checkout
  means no where-found rows. ZERO-CLICK: Read once per pin; no setting. DEPENDS:
  ITEM-INFO-CORE. BLOCKED: session wave 39.
- [ ] ITEM-INFO-UI (build) Item names as link-like buttons with the shared item info popover
  in Prices, movers and price watch (decision 0082 part 1). ACCEPT: python -m pytest -q
  tests/test_iteminfo_ui.py tests/test_a11y.py tests/test_ux_review.py passes: one popover
  element, Enter opens and focuses its heading, Escape closes and returns focus, an outside
  click closes it, one open at a time, it never changes a card's size, the credit line names
  only the sources shown, a "More on poe2db" link opens only on click. ZERO-CLICK: One click
  to look; it closes by itself on any other click. DEPENDS: ITEM-INFO-CORE. BLOCKED: session
  wave 39.
- [ ] KINDLER-ENGINE (build) Kindler candidates and PoB scoring through the bridge, on the
  Generate route (decision 0081 points 2 to 5). ACCEPT: python -m pytest -q
  tests/test_kindler_engine.py passes: at most 12 candidates, 60 s budget with a partial
  label, cached per toggle hash, calc off gives one unscored template, toggles only mark
  stale, no item text stored, the 0028 heap ceiling stands. ZERO-CLICK: One Generate click;
  results stay until the toggles change. DEPENDS: KINDLER-DATA, KINDLER-STORE. BLOCKED:
  session wave 39.

### Wave 40: operator requests 2026-11-19, Build tab

- [ ] KINDLER-UI (build) Build tab sub-tabs: Pasted build plus Kindler tabs with + and -,
  class and league picker, tri-state toggles, Generate, result card (decision 0081).
  ACCEPT: python -m pytest -q tests/test_kindler_ui.py tests/test_a11y.py
  tests/test_ux_review.py and npm test --prefix app pass: tabs survive a reload, a seventh
  tab is refused with a note, "not sure" is the default of every toggle, the result card
  credits Path of Building, items open the shared popover, nothing generates by itself.
  ZERO-CLICK: The tabs and last result come back by themselves; one Generate click per new
  idea. DEPENDS: KINDLER-ENGINE, ITEM-INFO-UI. BLOCKED: session wave 40.

## 4. Amendment to an existing package (integrator edit, not a new package)

- RUN-BUILD-STAMP-UI: goal gains "and Settings > About and data (the
  Settings About fold until TD-21 lands), format 'Version <x.y.z>, build
  <12 hex>' with ', dev' while hot reload is on (decision 0082 part 2)";
  tests gain "tests/test_ux_review.py (Settings About line carries the
  same string)". If wave 13 has already merged when this lands, the
  amendment becomes package RUN-BUILD-STAMP-ABOUT (S, 20 min, same
  files minus app/, wave 38).

## 5. packages.json-shaped entries (draft)

```json
[
 {"id": "ITEM-INFO-CORE", "title": "Item info lookup: token-gated GET /api/iteminfo over local caches",
  "goal": "One cache-only lookup returns the sourced fields of decision 0083 for an exact item name; unknown fields are absent; no network call.",
  "units": ["OPREQ-1119-1"],
  "files": ["server/al/theorycraft/snapshot.py", "server/al/pricebook.py"],
  "new_files": ["server/al/iteminfo.py", "server/al/plug/iteminfo.py", "tests/test_iteminfo.py"],
  "integrator_edits": [],
  "tests": ["tests/test_iteminfo.py"],
  "accept": "python -m pytest -q tests/test_iteminfo.py passes.",
  "zero_click": "Answers from what is already cached; no setting.",
  "size": "M", "est_min": 45, "deps": [], "serial_group": "data-caches",
  "agent": "general-purpose", "isolation": "worktree", "lane": "build",
  "design_review": false, "blocked": "session wave 38", "operator_act": "",
  "notes": "snapshot.py gains the repoe-fork uniques.json source (same licence and opt-in as base_items, decision 0009). Price fields only while web_data is on.",
  "wave": 38, "owner": "session", "tier": "P2", "cluster": "DATA"},
 {"id": "UI-HEADER-TEXT", "title": "Drop the visible AshLight text left of the tabs; sr-only h1 kept",
  "goal": "The bar shows the mark and the tabs; the h1 AshLight is visually hidden; document.title unchanged.",
  "units": ["OPREQ-1119-3"],
  "files": ["web/index.html", "web/app.css", "tests/test_brand_assets.py", "tests/test_a11y.py"],
  "new_files": [],
  "integrator_edits": [{"file": "docs/design/reviews.log", "change": "Append the design-reviewer line this package returns."}],
  "tests": ["tests/test_brand_assets.py (header: mark, sr-only h1)", "tests/test_a11y.py"],
  "accept": "python -m pytest -q tests/test_brand_assets.py tests/test_a11y.py passes.",
  "zero_click": "Automatic.",
  "size": "S", "est_min": 20, "deps": [], "serial_group": "web-shell",
  "agent": "general-purpose", "isolation": "worktree", "lane": "build",
  "design_review": true, "blocked": "session wave 38", "operator_act": "",
  "notes": "Decision 0082 part 2. The version line belongs to RUN-BUILD-STAMP-UI.",
  "wave": 38, "owner": "session", "tier": "P2", "cluster": "UI"},
 {"id": "UI-CARD-COLLAPSE", "title": "Collapsible cards on Build and items and Run; open cards take the freed height",
  "goal": "A title button collapses a card to its title row; open cards in the column share the height; the pager shows the rows that fit; state per viewer.",
  "units": ["OPREQ-1119-4"],
  "files": ["web/index.html", "web/app.css", "web/pager.js"],
  "new_files": ["web/collapse.js", "tests/test_card_collapse.py"],
  "integrator_edits": [{"file": "docs/design/reviews.log", "change": "Append the design-reviewer line this package returns."}],
  "tests": ["tests/test_card_collapse.py", "tests/test_a11y.py"],
  "accept": "python -m pytest -q tests/test_card_collapse.py tests/test_a11y.py passes and npm test --prefix app passes.",
  "zero_click": "Remembered per viewer; nothing to set.",
  "size": "M", "est_min": 50, "deps": [], "serial_group": "web-shell",
  "agent": "general-purpose", "isolation": "worktree", "lane": "build",
  "design_review": true, "blocked": "session wave 38", "operator_act": "",
  "notes": "Decision 0082 part 3. Play regions and Settings never collapse; alerts expand their card.",
  "wave": 38, "owner": "session", "tier": "P2", "cluster": "UI"},
 {"id": "KINDLER-DATA", "title": "Kindler archetype table and its checked loader",
  "goal": "server/al/data/archetypes.json in AshLight's own words with src and checked per entry, loaded and validated against the cached tree export, hot reloaded.",
  "units": ["OPREQ-1119-2"],
  "files": [],
  "new_files": ["server/al/data/archetypes.json", "server/al/theorycraft/archetypes.py", "tests/test_kindler_data.py"],
  "integrator_edits": [],
  "tests": ["tests/test_kindler_data.py"],
  "accept": "python -m pytest -q tests/test_kindler_data.py passes.",
  "zero_click": "Reloads by itself on change.",
  "size": "L", "est_min": 90, "deps": [], "serial_group": "tc-data",
  "agent": "general-purpose", "isolation": "worktree", "lane": "data",
  "design_review": false, "blocked": "session wave 38", "operator_act": "",
  "notes": "Decision 0081 points 2 and 6. Skill names checked against repoe-fork skill_gems.json if cached, else kept with checked=false. Nothing copied from another tool.",
  "wave": 38, "owner": "session", "tier": "P2", "cluster": "TC"},
 {"id": "KINDLER-STORE", "title": "Kindler tabs store ops/runtime/gen_builds.json",
  "goal": "A bounded player-data file of up to 6 generator tabs, durable like the other stores, cleared and exported per decision 0036.",
  "units": ["OPREQ-1119-2"],
  "files": ["server/al/settingsio.py", "server/al/runhistory.py", "server/al/plug/stores.py", "tests/test_settingsio.py"],
  "new_files": ["server/al/theorycraft/genstore.py", "tests/test_kindler_store.py"],
  "integrator_edits": [],
  "tests": ["tests/test_kindler_store.py", "tests/test_settingsio.py"],
  "accept": "python -m pytest -q tests/test_kindler_store.py tests/test_settingsio.py passes.",
  "zero_click": "Saved on every change.",
  "size": "M", "est_min": 45, "deps": [], "serial_group": "stores",
  "agent": "general-purpose", "isolation": "worktree", "lane": "build",
  "design_review": false, "blocked": "session wave 38", "operator_act": "",
  "notes": "Decision 0081 point 7. runhistory.py: Clear run history also empties this file; stores.py: one Checks row while unsaved.",
  "wave": 38, "owner": "session", "tier": "P2", "cluster": "TC"},
 {"id": "ITEM-INFO-POB-TEXT", "title": "Text-parse PoB CurrencyNames, WorldAreas and Uniques Source lines under sha256 pins",
  "goal": "Where-found rows for the popover from pinned PoB text, never run as Lua, only with the calc component installed.",
  "units": ["OPREQ-1119-1"],
  "files": ["config/tc_pins.json", "server/al/iteminfo.py", "tests/test_tc_pob_drift_guard.py"],
  "new_files": ["server/al/theorycraft/pobtext.py", "tests/test_tc_pobtext.py"],
  "integrator_edits": [],
  "tests": ["tests/test_tc_pobtext.py", "tests/test_tc_pob_drift_guard.py"],
  "accept": "python -m pytest -q tests/test_tc_pobtext.py tests/test_tc_pob_drift_guard.py passes.",
  "zero_click": "Read once per pin; no setting.",
  "size": "M", "est_min": 60, "deps": ["ITEM-INFO-CORE"], "serial_group": "tc-pins",
  "agent": "general-purpose", "isolation": "worktree", "lane": "data",
  "design_review": false, "blocked": "session wave 39", "operator_act": "",
  "notes": "Decision 0083 point 3 (amends 0037). pob2_files gains one sha256 per parsed file; tc_drift moves them with the pin.",
  "wave": 39, "owner": "session", "tier": "P3", "cluster": "TC"},
 {"id": "ITEM-INFO-UI", "title": "Item names as link-like buttons with the shared item info popover",
  "goal": "web/iteminfo.js and one popover element serve Prices, movers and price watch; ItemInfo.attach is ready for the item card and Kindler.",
  "units": ["OPREQ-1119-1"],
  "files": ["web/index.html", "web/prices.js", "web/pricewatch.js", "web/app.js"],
  "new_files": ["web/iteminfo.js", "web/iteminfo.css", "tests/test_iteminfo_ui.py"],
  "integrator_edits": [{"file": "docs/design/reviews.log", "change": "Append the design-reviewer line this package returns."}],
  "tests": ["tests/test_iteminfo_ui.py", "tests/test_a11y.py", "tests/test_ux_review.py"],
  "accept": "python -m pytest -q tests/test_iteminfo_ui.py tests/test_a11y.py tests/test_ux_review.py passes.",
  "zero_click": "One click to look; it closes by itself on any other click.",
  "size": "M", "est_min": 60, "deps": ["ITEM-INFO-CORE"], "serial_group": "web-shell",
  "agent": "general-purpose", "isolation": "worktree", "lane": "build",
  "design_review": true, "blocked": "session wave 39", "operator_act": "",
  "notes": "Decision 0082 part 1 and 0083 points 1, 5, 6. The poe2db link goes through the client's link guard (decision 0041).",
  "wave": 39, "owner": "session", "tier": "P2", "cluster": "UI"},
 {"id": "KINDLER-ENGINE", "title": "Kindler candidates and PoB scoring through the bridge, on the Generate route",
  "goal": "A bounded candidate set from the archetype table, composed as PoB XML, scored by the bridge one at a time inside the 0024 / 0028 budgets; calc-off gives one unscored template.",
  "units": ["OPREQ-1119-2"],
  "files": ["server/al/theorycraft/bridge.py"],
  "new_files": ["server/al/theorycraft/kindler.py", "server/al/plug/kindler.py", "tests/test_kindler_engine.py"],
  "integrator_edits": [],
  "tests": ["tests/test_kindler_engine.py"],
  "accept": "python -m pytest -q tests/test_kindler_engine.py passes.",
  "zero_click": "One Generate click; results stay until the toggles change.",
  "size": "L", "est_min": 120, "deps": ["KINDLER-DATA", "KINDLER-STORE"], "serial_group": "tc-calc",
  "agent": "general-purpose", "isolation": "worktree", "lane": "build",
  "design_review": false, "blocked": "session wave 39", "operator_act": "",
  "notes": "Decision 0081 points 2 to 5. bridge.py only if a load_build reset is needed between candidates; no new bridge.lua command.",
  "wave": 39, "owner": "session", "tier": "P2", "cluster": "TC"},
 {"id": "KINDLER-UI", "title": "Build tab sub-tabs: Pasted build plus Kindler tabs",
  "goal": "The Build tab holds the pasted-build sub-tab and up to 6 Kindler sub-tabs with + and -, a class and league picker, tri-state toggles, Generate and a result card whose items open the shared popover.",
  "units": ["OPREQ-1119-2"],
  "files": ["web/index.html", "web/tc.js", "web/app.css"],
  "new_files": ["web/kindler.js", "web/kindler.css", "tests/test_kindler_ui.py"],
  "integrator_edits": [{"file": "docs/design/reviews.log", "change": "Append the design-reviewer line this package returns."}],
  "tests": ["tests/test_kindler_ui.py", "tests/test_a11y.py", "tests/test_ux_review.py"],
  "accept": "python -m pytest -q tests/test_kindler_ui.py tests/test_a11y.py tests/test_ux_review.py and npm test --prefix app pass.",
  "zero_click": "The tabs and last result come back by themselves; one Generate click per new idea.",
  "size": "L", "est_min": 90, "deps": ["KINDLER-ENGINE", "ITEM-INFO-UI"], "serial_group": "web-shell",
  "agent": "general-purpose", "isolation": "worktree", "lane": "build",
  "design_review": true, "blocked": "session wave 40", "operator_act": "",
  "notes": "Decision 0081. Sub-tabs follow the tablist pattern of web/tabs.js; the card fits design A's 3 x 2 grid and pages.",
  "wave": 40, "owner": "session", "tier": "P2", "cluster": "TC"}
]
```

## 6. What cannot be done, said plainly

- Drop rates: GGG publishes none and repoe-fork says they are not in the
  game files; inventing or copying community estimates is out.
- Which monsters drop a currency or base, boss loot tables (beyond PoB's
  Source lines for about 51 uniques), NPC vendor prices, disenchant
  yields and rates: no permitted source. poe2db and the wiki have some
  of it, but their CC BY-NC-SA 3.0 text cannot enter Apache-2.0
  AshLight and the research allow-list refuses them (decision 0050); the
  popover links to poe2db instead.
- The official GGG exchange rate: blocked until AshLight has a
  registered GGG client.
- A free optimiser over the passive tree: decision 0004 bars an own calc
  engine; Kindler only ranks authored templates and lets Path of
  Building score them, and only on a click.
