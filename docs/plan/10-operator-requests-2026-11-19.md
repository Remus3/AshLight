# 10 - Operator requests 2026-11-19: drafted rows and packages

Date: 2026-11-19. Status: DRAFT for a later wave, revised the same day
for the operator follow-ups (decision 0081, 0082 and 0083 amendments
2026-11-19; research 0060 sections 7 and 8). LANDED 2026-11-19 by the
wave 11 pre-batch integrator: the section 5 packages are in
docs/plan/packages.json (waves 38 to 42, session 11), their rows in
ROADMAP.md, and section 4 widened RUN-BUILD-STAMP-UI. One change from the
draft: UI-CARD-COLLAPSE runs in wave 41, not 38 (in wave 38 it shared
serial group web-shell, web/index.html and web/app.css with
UI-HEADER-TEXT and server/al/plug/stores.py with KINDLER-STORE, which
tools/plan_check.py refuses). Research: 0060.
Rulings: decisions 0081 (Kindler), 0082 (UI), 0083 (item info data).

## 1. Requests and rulings, one line each

- R1 item info tooltip: one shared click popover (web/iteminfo.js)
  over a cache-only GET /api/iteminfo; shows only sourced fields (item
  class, price / trend / volume from poe.ninja, stack and shard rule,
  description, release state, PoB "where found" for about 51 uniques);
  drop rates, monster drop lists, NPC prices and disenchant yields are
  CUT (no permitted source; GGG publishes no rates; poe2db / wiki are CC
  BY-NC-SA and refused, decision 0050), replaced by a "More on poe2db"
  link the player opens. Decisions 0082 part 1, 0083.
- R1 follow-up, licence: AshLight keeps Apache-2.0; relicensing would
  not help, because the blocker is access (no poe2db API or app-use
  terms, a wiki bot wall), not AshLight's licence; link only stays; the
  0009 opt-in sidecar snapshot route opens only if a source permits app
  use, and community figures would then be labelled "community
  estimate". Decision 0083 amendment 2026-11-19.
- R2 build generator: "Kindler" = AshLight-authored archetype
  templates scored only by Path of Building over at most 12 candidates
  in 60 s, on the Generate click; unscored template when the calc
  component is off; up to 6 tabs in ops/runtime/gen_builds.json; 6
  tri-state toggles. Decision 0081 (amends 0004).
- R2 follow-ups: tabs move left / right, rename and close with an
  inline confirm; deterministic (one result key, PoB-ranked, fixed tie
  order); output as stages from levelling to maps with skills, support
  links, gem pick-up / swap timing, ordered passives, ascendancy and
  per-slot item focus; per-tab "follow Play guidance" (on by default)
  highlights the current stage. Trimmed: own tree search, drop / vendor
  / crafting / quest-gem facts, numbers with the calc off, auto
  regeneration, drag reorder. Decision 0081 amendment 2026-11-19.
- R3 header and version: visible "AshLight" text removed (sr-only h1
  kept); "Version 0.1.0, build <12 hex>" in the footer and Settings >
  About and data, by widening RUN-BUILD-STAMP-UI. Decision 0082 part 2.
  Follow-up: accepted as drafted, no change.
- R4 collapse: Build and items and Run cards collapse to their title
  row; open cards in the column share the height (grid fr tracks), the
  pager shows more rows; Play never collapses. Follow-up "app not
  browser, app only": state in the core (ops/runtime/ui_layout.json, GET
  / PUT /api/ui/layout), buttons only in the desktop client companion
  window, no localStorage. Decision 0082 part 3 and its amendment
  2026-11-19.

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
- [ ] UI-CARD-COLLAPSE (build) Collapsible cards on Build and items and Run in the desktop
  client; open cards take the freed height; state in the core (decision 0082 part 3 and
  amendment 2026-11-19). ACCEPT: python -m pytest -q tests/test_card_collapse.py
  tests/test_ui_layout.py tests/test_a11y.py passes and npm test --prefix app passes: every card
  on those tabs has one title button with aria-expanded inside the client (window.alClient) and
  none in a plain browser; Play regions and Settings have none; ops/runtime/ui_layout.json
  schema 1 keeps only allow-listed card ids, one .bak, Saver retry; GET / PUT /api/ui/layout is
  token gated; no localStorage use; a missing file means all open; an alert expands its card;
  not in settings export, untouched by Clear run history. ZERO-CLICK: Remembered by the app;
  nothing to set. BLOCKED: session wave 38.
- [ ] KINDLER-DATA (data) Kindler template schema and checked loader for
  server/al/data/archetypes.json (decision 0081 points 2, 6 and 11 to 16). ACCEPT: python -m
  pytest -q tests/test_kindler_data.py passes on fixtures: every entry has src and checked,
  conditions are JSON only, stages carry trigger, skills with supports bounded by sockets, gem
  timing, ordered passive prefix and per-slot focus; every passive prefix is connected from the
  class start and inside the point budget (breadth-first check, validator only); node ids exist
  in the cached tree export or are dropped with a note; gem names exist in the gems snapshot or
  are checked=false; the file hot reloads. ZERO-CLICK: Reloads by itself on change. BLOCKED:
  session wave 38.
- [ ] KINDLER-STORE (build) Kindler tabs store ops/runtime/gen_builds.json and its tab route
  (decision 0081 points 7, 11 and 17). ACCEPT: python -m pytest -q tests/test_kindler_store.py
  tests/test_settingsio.py passes: schema 1, at most 6 tabs, list order kept, labels capped at
  32 characters with control characters stripped, follow flag on by default, one .bak, Saver
  retry, no item text, emptied by Clear run history, exported through the settings allow-list,
  an import never turns web_data on. ZERO-CLICK: Saved on every change. BLOCKED: session wave
  38.

### Wave 39: operator requests 2026-11-19, popover and templates

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
- [ ] KINDLER-TEMPLATES (data) First authored Kindler templates in
  server/al/data/archetypes.json: one or more per archetype toggle (melee, spell, minion, bow),
  each with stages from act 1 to maps (decision 0081 points 2, 15 and 16). ACCEPT: python -m
  pytest -q tests/test_kindler_templates.py passes: the real file passes the KINDLER-DATA
  validator, every fact carries src and checked, nothing copied from another tool, unsure facts
  left out. ZERO-CLICK: Reloads by itself on change. DEPENDS: KINDLER-DATA. BLOCKED: session
  wave 39.

### Wave 40: operator requests 2026-11-19, engine and tabs

- [ ] KINDLER-ENGINE (build) Kindler candidates, PoB scoring and deterministic ranking on the
  Generate route (decision 0081 points 2 to 5, 12 and 13). ACCEPT: python -m pytest -q
  tests/test_kindler_engine.py tests/test_kindler_live.py passes: at most 12 candidates, 60 s
  budget with a partial label and no final caching of a partial, result key from class, toggles,
  table hash, PoB pin, tree version and level band, two runs byte-identical, ties by template id
  then variant, calc off gives one unscored template by toggle-match then id, the reference
  build through Kindler XML within 0.1 percent of the bridge (live, skips with the calc off),
  the 0028 heap ceiling stands. ZERO-CLICK: One Generate click; results stay until the toggles
  change. DEPENDS: KINDLER-DATA, KINDLER-TEMPLATES, KINDLER-STORE. BLOCKED: session wave 40.
- [ ] KINDLER-UI-TABS (build) Build tab sub-tabs: fixed Pasted build plus up to 6 Kindler tabs
  with +, Move left / Move right, rename and close with an inline confirm, class and league
  picker, tri-state toggles, Generate (decision 0081 points 7 to 11). ACCEPT: python -m pytest
  -q tests/test_kindler_tabs_ui.py tests/test_a11y.py tests/test_ux_review.py and npm test
  --prefix app pass: tabs and their order survive a reload, a seventh tab is refused with a
  note, Pasted build cannot move, close or be renamed, close asks Close / Keep with focus on
  Keep and no window.confirm, "not sure" is every toggle default, nothing generates by itself.
  ZERO-CLICK: The tabs come back by themselves; one Generate click per new idea. DEPENDS:
  KINDLER-STORE. BLOCKED: session wave 40.

### Wave 41: operator requests 2026-11-19, Kindler plan

- [ ] KINDLER-PLAN (build) Kindler result plan: stages with skills, support links, gem pick-up
  / swap timing, ordered passives, ascendancy, per-slot item focus, and the current-stage
  resolver (decision 0081 points 14 to 17). ACCEPT: python -m pytest -q
  tests/test_kindler_plan.py passes: stage order follows triggers, gem levels from the gems
  snapshot else checked=false, a support PoB says does not apply fails the template (live, skips
  with the calc off), item focus ranked by PoB per-mod weights with the calc on and by authored
  priority with it off, the resolver picks the stage from the published zone, act and level
  only, no step is claimed done, no own calc. ZERO-CLICK: Follows the Play guidance by itself
  while the tab toggle is on. DEPENDS: KINDLER-ENGINE. BLOCKED: session wave 41.

### Wave 42: operator requests 2026-11-19, Kindler result card

- [ ] KINDLER-UI-RESULT (build) Kindler result card: stages, skills with their links, gem
  timing, passive order, ascendancy, item focus, the "follow Play guidance" toggle and the
  current-stage highlight (decision 0081 points 10 and 15 to 18). ACCEPT: python -m pytest -q
  tests/test_kindler_result_ui.py tests/test_a11y.py tests/test_ux_review.py and npm test
  --prefix app pass: the card credits Path of Building, shows no number with the calc off, items
  and mods open the shared popover, the follow toggle is on by default and highlights the
  matching stage, the .build stays a download on click, the card fits design A's grid and pages.
  ZERO-CLICK: The current step moves with the Play guidance by itself. DEPENDS: KINDLER-PLAN,
  KINDLER-UI-TABS, ITEM-INFO-UI. BLOCKED: session wave 42.

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
 {"id": "ITEM-INFO-CORE", "title": "Item info lookup: token-gated GET /api/iteminfo over local caches", "goal": "One cache-only lookup returns the sourced fields of decision 0083 for an exact item name; unknown fields are absent; no network call.", "units": ["OPREQ-1119-1"], "files": ["server/al/theorycraft/snapshot.py", "server/al/pricebook.py"], "new_files": ["server/al/iteminfo.py", "server/al/plug/iteminfo.py", "tests/test_iteminfo.py"], "integrator_edits": [], "tests": ["tests/test_iteminfo.py"], "accept": "python -m pytest -q tests/test_iteminfo.py passes.", "zero_click": "Answers from what is already cached; no setting.", "size": "M", "est_min": 45, "deps": [], "serial_group": "data-caches", "agent": "general-purpose", "isolation": "worktree", "lane": "build", "design_review": false, "blocked": "session wave 38", "operator_act": "", "notes": "snapshot.py gains the repoe-fork uniques.json source (same licence and opt-in as base_items, decision 0009). Price fields only while web_data is on.", "wave": 38, "owner": "session", "tier": "P2", "cluster": "DATA"},
 {"id": "UI-HEADER-TEXT", "title": "Drop the visible AshLight text left of the tabs; sr-only h1 kept", "goal": "The bar shows the mark and the tabs; the h1 AshLight is visually hidden; document.title unchanged.", "units": ["OPREQ-1119-3"], "files": ["web/index.html", "web/app.css", "tests/test_brand_assets.py", "tests/test_a11y.py"], "new_files": [], "integrator_edits": [{"file": "docs/design/reviews.log", "change": "Append the design-reviewer line this package returns."}], "tests": ["tests/test_brand_assets.py (header: mark, sr-only h1)", "tests/test_a11y.py"], "accept": "python -m pytest -q tests/test_brand_assets.py tests/test_a11y.py passes.", "zero_click": "Automatic.", "size": "S", "est_min": 20, "deps": [], "serial_group": "web-shell", "agent": "general-purpose", "isolation": "worktree", "lane": "build", "design_review": true, "blocked": "session wave 38", "operator_act": "", "notes": "Decision 0082 part 2. The version line belongs to RUN-BUILD-STAMP-UI.", "wave": 38, "owner": "session", "tier": "P2", "cluster": "UI"},
 {"id": "UI-CARD-COLLAPSE", "title": "Collapsible cards on Build and items and Run in the desktop client; state in the core", "goal": "A title button collapses a card to its title row inside the desktop client; open cards in the column share the height; the pager shows the rows that fit; the state lives in ops/runtime/ui_layout.json behind GET / PUT /api/ui/layout.", "units": ["OPREQ-1119-4"], "files": ["web/index.html", "web/app.css", "web/pager.js", "server/al/plug/stores.py"], "new_files": ["web/collapse.js", "server/al/uilayout.py", "server/al/plug/uilayout.py", "tests/test_card_collapse.py", "tests/test_ui_layout.py"], "integrator_edits": [{"file": "docs/design/reviews.log", "change": "Append the design-reviewer line this package returns."}], "tests": ["tests/test_card_collapse.py", "tests/test_ui_layout.py", "tests/test_a11y.py"], "accept": "python -m pytest -q tests/test_card_collapse.py tests/test_ui_layout.py tests/test_a11y.py passes and npm test --prefix app passes.", "zero_click": "Remembered by the app; nothing to set.", "size": "L", "est_min": 80, "deps": [], "serial_group": "web-shell", "agent": "general-purpose", "isolation": "worktree", "lane": "build", "design_review": true, "blocked": "session wave 38", "operator_act": "", "notes": "Decision 0082 part 3 and amendment 2026-11-19: buttons only when window.alClient is present; no localStorage; not exported, not cleared by Clear run history. Play regions and Settings never collapse; alerts expand their card. stores.py: one Checks row while unsaved.", "wave": 38, "owner": "session", "tier": "P2", "cluster": "UI"},
 {"id": "KINDLER-DATA", "title": "Kindler template schema and checked loader", "goal": "The schema of server/al/data/archetypes.json (templates of stages: trigger, skills with supports, gem timing, ordered passive prefix, ascendancy order, per-slot focus) and a loader that validates it against the cached tree export and gems snapshot, hot reloaded.", "units": ["OPREQ-1119-2"], "files": [], "new_files": ["server/al/theorycraft/archetypes.py", "tests/kindler_fixtures.py", "tests/test_kindler_data.py"], "integrator_edits": [], "tests": ["tests/test_kindler_data.py"], "accept": "python -m pytest -q tests/test_kindler_data.py passes.", "zero_click": "Reloads by itself on change.", "size": "M", "est_min": 60, "deps": [], "serial_group": "tc-data", "agent": "general-purpose", "isolation": "worktree", "lane": "data", "design_review": false, "blocked": "session wave 38", "operator_act": "", "notes": "Decision 0081 points 2, 6, 11 to 16. The breadth-first connectivity check lives in the validator only, never at run time. Gem names checked against the repoe-fork gems snapshot if cached, else checked=false. The data file itself is KINDLER-TEMPLATES.", "wave": 38, "owner": "session", "tier": "P2", "cluster": "TC"},
 {"id": "KINDLER-STORE", "title": "Kindler tabs store ops/runtime/gen_builds.json", "goal": "A bounded player-data file of up to 6 generator tabs (order, label, toggles, follow flag, result summary) with its token-gated tab route, durable like the other stores, cleared and exported per decision 0036.", "units": ["OPREQ-1119-2"], "files": ["server/al/settingsio.py", "server/al/runhistory.py", "server/al/plug/stores.py", "tests/test_settingsio.py"], "new_files": ["server/al/theorycraft/genstore.py", "server/al/plug/genbuilds.py", "tests/test_kindler_store.py"], "integrator_edits": [], "tests": ["tests/test_kindler_store.py", "tests/test_settingsio.py"], "accept": "python -m pytest -q tests/test_kindler_store.py tests/test_settingsio.py passes.", "zero_click": "Saved on every change.", "size": "M", "est_min": 55, "deps": [], "serial_group": "stores", "agent": "general-purpose", "isolation": "worktree", "lane": "build", "design_review": false, "blocked": "session wave 38", "operator_act": "", "notes": "Decision 0081 points 7, 11 and 17. Labels at most 32 characters, control characters stripped; follow flag on by default. runhistory.py: Clear run history also empties this file; stores.py: one Checks row while unsaved.", "wave": 38, "owner": "session", "tier": "P2", "cluster": "TC"},
 {"id": "ITEM-INFO-POB-TEXT", "title": "Text-parse PoB CurrencyNames, WorldAreas and Uniques Source lines under sha256 pins", "goal": "Where-found rows for the popover from pinned PoB text, never run as Lua, only with the calc component installed.", "units": ["OPREQ-1119-1"], "files": ["config/tc_pins.json", "server/al/iteminfo.py", "tests/test_tc_pob_drift_guard.py"], "new_files": ["server/al/theorycraft/pobtext.py", "tests/test_tc_pobtext.py"], "integrator_edits": [], "tests": ["tests/test_tc_pobtext.py", "tests/test_tc_pob_drift_guard.py"], "accept": "python -m pytest -q tests/test_tc_pobtext.py tests/test_tc_pob_drift_guard.py passes.", "zero_click": "Read once per pin; no setting.", "size": "M", "est_min": 60, "deps": ["ITEM-INFO-CORE"], "serial_group": "tc-pins", "agent": "general-purpose", "isolation": "worktree", "lane": "data", "design_review": false, "blocked": "session wave 39", "operator_act": "", "notes": "Decision 0083 point 3 (amends 0037). pob2_files gains one sha256 per parsed file; tc_drift moves them with the pin.", "wave": 39, "owner": "session", "tier": "P3", "cluster": "TC"},
 {"id": "ITEM-INFO-UI", "title": "Item names as link-like buttons with the shared item info popover", "goal": "web/iteminfo.js and one popover element serve Prices, movers and price watch; ItemInfo.attach is ready for the item card and Kindler.", "units": ["OPREQ-1119-1"], "files": ["web/index.html", "web/prices.js", "web/pricewatch.js", "web/app.js"], "new_files": ["web/iteminfo.js", "web/iteminfo.css", "tests/test_iteminfo_ui.py"], "integrator_edits": [{"file": "docs/design/reviews.log", "change": "Append the design-reviewer line this package returns."}], "tests": ["tests/test_iteminfo_ui.py", "tests/test_a11y.py", "tests/test_ux_review.py"], "accept": "python -m pytest -q tests/test_iteminfo_ui.py tests/test_a11y.py tests/test_ux_review.py passes.", "zero_click": "One click to look; it closes by itself on any other click.", "size": "M", "est_min": 60, "deps": ["ITEM-INFO-CORE"], "serial_group": "web-shell", "agent": "general-purpose", "isolation": "worktree", "lane": "build", "design_review": true, "blocked": "session wave 39", "operator_act": "", "notes": "Decision 0082 part 1 and 0083 points 1, 5, 6. The poe2db link goes through the client's link guard (decision 0041).", "wave": 39, "owner": "session", "tier": "P2", "cluster": "UI"},
 {"id": "KINDLER-TEMPLATES", "title": "First authored Kindler templates, act 1 to maps", "goal": "server/al/data/archetypes.json holds at least one template per archetype toggle (melee, spell, minion, bow), each a list of stages with skills, support links, gem timing, ordered passives, ascendancy order and per-slot focus, in AshLight's own words.", "units": ["OPREQ-1119-2"], "files": [], "new_files": ["server/al/data/archetypes.json", "tests/test_kindler_templates.py"], "integrator_edits": [], "tests": ["tests/test_kindler_templates.py"], "accept": "python -m pytest -q tests/test_kindler_templates.py passes.", "zero_click": "Reloads by itself on change.", "size": "L", "est_min": 90, "deps": ["KINDLER-DATA"], "serial_group": "tc-data", "agent": "general-purpose", "isolation": "worktree", "lane": "data", "design_review": false, "blocked": "session wave 39", "operator_act": "", "notes": "Decision 0081 points 2, 15, 16 and 18. Facts only from already permitted sources (cached tree export, gems snapshot, PoB's own data through the pinned checkout); unsure facts left out or checked=false; nothing copied from another tool; no drop, vendor, crafting or quest-gem facts.", "wave": 39, "owner": "session", "tier": "P2", "cluster": "TC"},
 {"id": "KINDLER-ENGINE", "title": "Kindler candidates, PoB scoring and deterministic ranking on the Generate route", "goal": "A bounded candidate set from the templates, composed as PoB XML, scored by the bridge one at a time inside the 0024 / 0028 budgets, ranked by the 0024 blend with a fixed tie order under one result key; calc off gives one unscored template.", "units": ["OPREQ-1119-2"], "files": ["server/al/theorycraft/bridge.py"], "new_files": ["server/al/theorycraft/kindler.py", "server/al/plug/kindler.py", "tests/test_kindler_engine.py", "tests/test_kindler_live.py"], "integrator_edits": [], "tests": ["tests/test_kindler_engine.py", "tests/test_kindler_live.py"], "accept": "python -m pytest -q tests/test_kindler_engine.py tests/test_kindler_live.py passes.", "zero_click": "One Generate click; results stay until the toggles change.", "size": "L", "est_min": 90, "deps": ["KINDLER-DATA", "KINDLER-TEMPLATES", "KINDLER-STORE"], "serial_group": "tc-calc", "agent": "general-purpose", "isolation": "worktree", "lane": "build", "design_review": false, "blocked": "session wave 40", "operator_act": "", "notes": "Decision 0081 points 2 to 5, 12, 13. Key = sha256(class, toggles, archetypes.json sha256, PoB pin, tree export version, level band); ties by template id then variant; a partial is never cached as final. Live reference-build check (0028) within 0.1 percent, skipped with the calc off. bridge.py only if a load_build reset is needed between candidates; no new bridge.lua command.", "wave": 40, "owner": "session", "tier": "P2", "cluster": "TC"},
 {"id": "KINDLER-UI-TABS", "title": "Build tab sub-tabs: Pasted build plus Kindler tabs with move, rename and close", "goal": "The Build tab holds the fixed Pasted build sub-tab and up to 6 Kindler sub-tabs with +, Move left / Move right, rename, close with an inline confirm, a class and league picker, tri-state toggles and Generate.", "units": ["OPREQ-1119-2"], "files": ["web/index.html", "web/tc.js", "web/app.css"], "new_files": ["web/kindler.js", "web/kindler.css", "tests/test_kindler_tabs_ui.py"], "integrator_edits": [{"file": "docs/design/reviews.log", "change": "Append the design-reviewer line this package returns."}], "tests": ["tests/test_kindler_tabs_ui.py", "tests/test_a11y.py", "tests/test_ux_review.py"], "accept": "python -m pytest -q tests/test_kindler_tabs_ui.py tests/test_a11y.py tests/test_ux_review.py and npm test --prefix app pass.", "zero_click": "The tabs come back by themselves; one Generate click per new idea.", "size": "M", "est_min": 60, "deps": ["KINDLER-STORE"], "serial_group": "web-shell", "agent": "general-purpose", "isolation": "worktree", "lane": "build", "design_review": true, "blocked": "session wave 40", "operator_act": "", "notes": "Decision 0081 points 7 to 11. Sub-tabs follow the tablist pattern of web/tabs.js; no drag; close never uses window.confirm.", "wave": 40, "owner": "session", "tier": "P2", "cluster": "TC"},
 {"id": "KINDLER-PLAN", "title": "Kindler result plan: stages, links, gem timing, passives, ascendancy, item focus", "goal": "From the top-ranked template, a plan of stages from levelling to maps (skills with support links, gem pick-up / swap timing, ordered passives, ascendancy, per-slot item focus) plus a resolver that picks the current stage from the published zone, act and level.", "units": ["OPREQ-1119-2"], "files": ["server/al/plug/kindler.py"], "new_files": ["server/al/theorycraft/kindlerplan.py", "tests/test_kindler_plan.py"], "integrator_edits": [], "tests": ["tests/test_kindler_plan.py"], "accept": "python -m pytest -q tests/test_kindler_plan.py passes.", "zero_click": "Follows the Play guidance by itself while the tab toggle is on.", "size": "L", "est_min": 80, "deps": ["KINDLER-ENGINE"], "serial_group": "tc-calc", "agent": "general-purpose", "isolation": "worktree", "lane": "build", "design_review": false, "blocked": "session wave 41", "operator_act": "", "notes": "Decision 0081 points 14 to 17. Item focus ranked by PoB per-mod weights (decision 0024) with the calc on, authored priority with it off; support applicability from PoB through the bridge; resolver reads only what the snapshot publishes (ZONE-GUIDE 0043, character 0038); never claims a step done.", "wave": 41, "owner": "session", "tier": "P2", "cluster": "TC"},
 {"id": "KINDLER-UI-RESULT", "title": "Kindler result card with stages and follow Play guidance", "goal": "The Kindler tab's result card shows the plan stages, skills with their links, gem timing, passive order, ascendancy and item focus, the per-tab follow toggle (on by default) and the current-stage highlight; items and mods open the shared popover.", "units": ["OPREQ-1119-2"], "files": ["web/index.html", "web/kindler.js", "web/kindler.css"], "new_files": ["tests/test_kindler_result_ui.py"], "integrator_edits": [{"file": "docs/design/reviews.log", "change": "Append the design-reviewer line this package returns."}], "tests": ["tests/test_kindler_result_ui.py", "tests/test_a11y.py", "tests/test_ux_review.py"], "accept": "python -m pytest -q tests/test_kindler_result_ui.py tests/test_a11y.py tests/test_ux_review.py and npm test --prefix app pass.", "zero_click": "The current step moves with the Play guidance by itself.", "size": "L", "est_min": 90, "deps": ["KINDLER-PLAN", "KINDLER-UI-TABS", "ITEM-INFO-UI"], "serial_group": "web-shell", "agent": "general-purpose", "isolation": "worktree", "lane": "build", "design_review": true, "blocked": "session wave 42", "operator_act": "", "notes": "Decision 0081 points 10, 15 to 18. Credits Path of Building; no number with the calc off; the .build stays a click download (0034); the card fits design A's 3 x 2 grid and pages.", "wave": 42, "owner": "session", "tier": "P2", "cluster": "TC"}
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
- Relicensing AshLight to fix the poe2db / wiki question: it would not
  help (decision 0083 amendment 2026-11-19). The missing piece is
  permission to fetch, not AshLight's licence.
- Kindler trims: own tree search or pathfinding at run time, drop
  locations, vendor shopping, crafting steps, uniques by where they
  drop, which quest gives which gem, DPS / EHP with the calc off,
  automatic regeneration, drag-and-drop tab reorder, waystone tier names
  without a sourced mapping; never any input to the game, and the .build
  stays a click download (decision 0081 point 18).
- Card collapse in a plain browser: the buttons appear only in the
  desktop client (decision 0082 amendment 2026-11-19).
