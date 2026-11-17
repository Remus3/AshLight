# 0025 - PoE2 search box and item filter syntax (AREA-UTIL batch 6)

Date: 2026-11-17. Lane AREA-UTIL batch 6. Purpose: verify the assumptions
of batch 5 (decisions 0030, 0031; ROADMAP UTIL-WAYSTONE, UTIL-SEARCHSTR,
UX-ZONE-NOTES, UTIL-FILTER) without the game. All sources accessed
2026-11-17. Nothing from these pages is copied into the repo; the game-data
checks read the build-time snapshot in the AL sidecar cache only (decision
0009), fetched with the documented developer opt-in (`snapshot --opt-in`,
the path build.ps1 -Snapshot runs).

## 1. Stash / vendor search box

Findings:
- Character limit: 250 since PoE2 0.5.0. GGG's 0.5.0 patch notes:
  "Increased the maximum character limit of search textboxes to 250
  characters." and "Searching by an item's text will now match the
  advanced description format." Source: Early Access Patch Notes - Content
  Update 0.5.0, https://www.pathofexile.com/forum/view-thread/3932540
  (accessed 2026-11-17). Before 0.5.0 players reported about 48-50
  characters (https://www.pathofexile.com/forum/view-thread/3855389, post
  of 2025-09-16, "The regex length limit of 48 characters is too short";
  https://boostmatch.gg/blog/poe-2/articles/poe2-regex-search-bar-guide,
  "Currently 50 characters. Expected to increase to 250 in a future
  patch."). Community guides written before the patch still say 50.
- Syntax (community-documented, no official reference page found): the
  box takes a regular expression; `|` is OR, a leading `!` negates;
  double quotes wrap a string so spaces stay inside one term; several
  quoted blocks must all match. Sources: forum guide "Some useful regular
  expressions for Waystone modifiers", 2025-09-22,
  https://ru.pathofexile.com/forum/view-thread/3858429 ("| is an OR
  operator ...", "! is used for negation so "!m.+e:" will display
  waystones without Monster Pack Size modifier"); boostmatch guide above
  (operator table: quote "Wraps your full search string", `|` "OR:
  matches either term", `!` "Exclude: hide matching items", space
  "Separate independent search blocks"). Case: matching is
  case-insensitive in every example (lower-case patterns match
  capitalised mod text); not stated explicitly by a source.

Effect on AshLight: searchstr.MAX_LEN 250 is now the documented limit
(test `test_worst_case_waystone_string_keeps_every_term_within_the_limit`);
the generator's form `"term|term"` and `"!term|term"` with plain lower-case
terms (regex characters removed) matches the syntax. In-game check of the
`!` scope over a whole OR group stays a LIVE- note (UTIL-SEARCHSTR).

## 2. Item filter

- GGG reference: https://www.pathofexile.com/item-filter/about (accessed
  2026-11-17): blocks Show / Hide / Minimal / Continue / Import; Rarity
  Normal / Magic / Rare / Unique; BaseType with `==` exact match;
  SetFontSize 1-45; Set*Color red / green / blue 0-255 with optional alpha
  0-255; PlayEffect colours Red, Green, Blue, Brown, White, Yellow, Cyan,
  Grey, Orange, Pink, Purple; MinimapIcon size 0-2, the same colours,
  shapes Circle, Diamond, Hexagon, Square, Star, Triangle, Cross, Moon,
  Raindrop, Kite, Pentagon, UpsideDownHouse; "Use Optional after the
  filename to skip the file if it does not exist."; matching stops at a
  matched block unless it has `Continue`.
- PoE2 uses the same grammar (no separate PoE2 page renders without
  JavaScript; pathofexile2.com/item-filter/about returned only its title):
  poe2wiki revision history, https://www.poe2wiki.net/wiki/Item_filter/history
  ("Item filters seem to work the same way they did in Path of Exile 1";
  quoted from the search-result excerpt, the page itself is behind a bot
  check).
- The filter AshLight writes (one Show block: Rarity Rare, BaseType ==,
  SetFontSize 40, SetBorderColor 255 190 60, PlayEffect Yellow,
  MinimapIcon 1 Yellow Diamond) uses only these words and ranges
  (tests/test_lootfilter.py grammar check).
- Fix: a BaseType value that names no item is a filter error; when the
  snapshot base list is cached, generate() now keeps only base names it
  knows, in the game's spelling. The filter uses no Class condition, so
  no class name needs checking. Whether the game rejects an unknown
  BaseType or only ignores it stays a LIVE- note (UTIL-FILTER).

## 3. Game-data snapshot checks (repoe-fork, fetched 2026-11-17)

- world_areas: every campaign area id of Acts 1-4 and Interludes 1-3
  resolves to a zone note or its act default
  (`test_snapshot_ids_all_resolve` now runs). No Cruel (C_) ids are in
  the snapshot. Three Act 2 note names matched no area name and would
  never show: "Ardura Caravan" (real: "The Ardura Caravan"), "The
  Dreadnought" and "Dreadnought Vanguard" (real: "The Dreadnought's Wake",
  "Dreadnought"); fixed, and `test_every_zone_note_names_a_snapshot_zone_of_its_act`
  guards it. Interlude zones use the act default (no zone notes yet).
- mods: the waystone pool (area-domain prefixes / suffixes with map_key
  spawn weights, 116 mods, 135 text lines). Of the 12 batch-5 rules, 5
  matched no waystone mod (no regeneration, energy shield recharge,
  curses, reflect, extra projectiles; their wordings exist only on
  zero-weight or unique-area mods); `monster_crit` also caught the
  player-side "Monsters take ...% reduced Extra Damage from Critical
  Hits"; `ground` listed burning / shocking words no mod uses. The table
  now has 11 rules, each matching real mods, each search term unique to
  its own rule's lines in the pool.
