# 0065 - Augment data source (RES-AUGMENT-DATA)

Date: 2026-11-27. Question (research 0064 open question 1, row
RES-AUGMENT-DATA): which cached, permitted snapshot holds PoE2 augment
(rune, soul core, idol, talisman) effects with stat ids and socket or slot
rules, so TC-AUGMENT-WHATIF can rank them?

Verdict: NO permitted source among the cached repoe-fork snapshots. They
name every augment base and carry the trade filter ids of augment lines,
but no file maps an augment to the stat it grants, its value or the slot
it grants it in. "No permitted source" stands for the repoe-fork route,
and TC-AUGMENT-WHATIF stays BLOCKED.

Update 2026-11-27: decision 0091 admits PoB-PoE2 src/Data/ModRunes.lua as a
pinned text source (adjudicator ruling 2026-11-27; row DATA-AUGMENT-POB-TEXT).

One candidate outside that route was seen (section 4): the pinned,
MIT-licensed Path of Building PoE2 checkout holds `src/Data/ModRunes.lua`,
which has exactly the missing table. It is not an admitted source today.
Using it needs a decision amendment in the decision 0037 / 0083 pattern
(text parse under a pob2_files sha256 pin, calc component installed, never
run as Lua). That is a ruling, not something this note decides.

## 1. Sources (all read 2026-11-27, local cache only, no request made)

Cached repoe-fork / GGG snapshots in the AL sidecar `Cache\gamedata\`
(resolved with `server/al/paths.py sidecar_dir("Cache")`), attributed per
decision 0009 (repoe-fork code MIT; the data files belong to Grinding Gear
Games; credit sentence in `server/al/theorycraft/datacredit.py`). Upstream
URL and fetch date from the cache's manifest.json:

- base_items.json: https://repoe-fork.github.io/poe2/base_items.json,
  fetched 2026-11-17, sha256 da8c1136...0d83a8.
- mods.json: https://repoe-fork.github.io/poe2/mods.json, fetched
  2026-11-17, sha256 10c208cc...7922.
- stats.json: https://repoe-fork.github.io/poe2/stats_by_file.json,
  fetched 2026-11-17.
- stat_translations.json:
  https://repoe-fork.github.io/poe2/stat_translations/stat_descriptions.json,
  fetched 2026-11-22, sha256 af043ebb...500e.
- uniques.json: https://repoe-fork.github.io/poe2/uniques.json, fetched
  2026-11-24.
- world_areas.json: repoe-fork world_areas, fetched 2026-11-17.
- skilltree.json: GGG's public tree export
  (grindinggear/poe2-skilltree-export data.json), fetched 2026-11-22.
- gems.json is not cached on this host (DATA-GEMS-SNAP source, web data
  gated); it is a gem list and would not hold augment effects.

Method: a stdlib scan of every key and string value of each file for
rune, soul core, talisman, idol, augment, socketable and socket, then a
read of the matching fields. Nothing was copied into a tracked file except
counts, field names and two short sample strings.

## 2. What each file holds

- base_items.json: 313 bases of item_class `SoulCore` (tags: rune 226,
  soul_core 52, idol 31, plus tier tags such as rune_lesser / rune_greater
  / rune_perfect and soul_core_tier2 / soul_core_tier3), all
  release_state released. Fields: name, tags, drop_level, stack_size and
  `properties.description`. On all 313, `implicits` is empty and
  `grants_buff`, `skills_granted` and `requirements` are null. 198 of them
  carry a slot rule only as free text in the description ("Place into an
  empty [Augment] Socket in a Helmet to apply its effect ...": 45 distinct
  slot phrasings, from "any Equipment" to "One Hand Mace or Quarterstaff");
  115 have an empty description. The effect itself (stat, value) is not
  there. Also 31 `Talisman` bases (a two-hand weapon class, 16 with
  implicits: weapon bases, not augments), 16 PoE1-era Delve socketable
  currencies and 8 `TowerAugmentation` items (atlas, not gear).
- mods.json: no domain or generation_type for augments (the domains are
  item, monster, area, misc, desecrated and others; none is a socketable
  domain). The 61 mod ids naming SoulCore / Socketable are unique-item mods
  ("... per Socketable", UniqueLocalSoulCoreEffect1). Nine
  `LocalItemBenefitSocketableAsIf<Slot>` mods (helmet, gloves, boots, body
  armour, shield) say an item takes socketed bonuses as another slot: a
  slot-rule modifier, but with no effect table to apply it to. The 22
  `talisman` generation_type mods are monster mods.
- stat_translations.json: 402 entries carry a `trade_stats` row of type
  `augment` (409 rows, ids `rune.stat_<n>`, 423 stat ids). These are the
  trade filter ids and display text of augment lines; they say nothing of
  which augment grants them or in which slot.
- stats.json: stat definitions only (implied stats such as
  local_can_socket_x_*_jewels for jewels, map_*talisman* map stats).
- uniques.json: names only (6 entries of item_class Talisman).
- world_areas.json: one Incursion soul core boss pack id, nothing else.
- skilltree.json: jewel sockets (`isJewelSocket`, 19 nodes) and one
  ascendancy text about Bonded modifiers on Runes and Idols.

So: stat ids exist (trade ids, stat_translations), slot rules exist as
free text (base_items descriptions), but the join between an augment, its
stat and its slot does not exist in any cached repoe-fork file. A rule
table built from the description text plus guessed stats would be a guess
(decision 0037: a missing id means no filter, never guessed).

## 3. Licence and attribution

Any later use of the repoe-fork files above stays under decision 0009: a
sidecar snapshot behind the one web_data opt-in, never bundled, with the
repoe-fork credit sentence. No new credit line is needed for what this
note reads.

## 4. Candidate outside the repoe-fork route (not admitted)

The pinned Path of Building PoE2 checkout in the sidecar
(`Cache\pob2\PathOfBuilding-PoE2-<commit>`, commit 7d6f530c of
config/tc_pins.json, licence MIT, (c) 2016 David Gowor; header line
"Item data (c) Grinding Gear Games") holds `src/Data/ModRunes.lua`
(5684 lines, 188915 bytes, sha256 85d5f1d2...a6fb387, read 2026-11-27).
It is generated data: 287 augment names, each with one table per slot key
("helmet", "gloves", "boots", "body armour", "armour", "caster", "wand",
"staff", "sceptre", "bow", "one hand mace" and others, 20 slot keys seen),
and per slot: `type` (Rune 411, Idol 77, SoulCore 69, AbyssalEye 12,
CongealedMist 1), the stat line text, `statOrder`, `tradeHashes` (the same
numbers as the `rune.stat_<n>` trade ids above), `isSocketBound` (true on
20) and `rank`. That is the stat and slot join section 2 lacks.

It is not in config/tc_pins.json `pob2_files` today (TradeSiteStats.lua,
WorldAreas.lua, Gems.lua and the Uniques files are). Admitting it would
follow decision 0037's amendment and ITEM-INFO-POB-TEXT: read as text,
never run as Lua, only while the optional calc component is installed,
under its own pob2_files sha256 and the checkout marker; repoe-fork wins
any conflict. TC-AUGMENT-WHATIF is a PoB calc stage, so it runs only when
the calc component is installed anyway. Proposed follow-up (for the
integrator): an adjudicator ruling or decision amendment on admitting
ModRunes.lua, then a data row that pins it and builds the table; once that
lands TC-AUGMENT-WHATIF can drop its BLOCKED tag.

## 5. Reverses if

- repoe-fork publishes an augment / soul core effect file (then a
  snapshot.SOURCES entry under decision 0009 settles the route), or a
  cached base_items refresh fills augment implicits or buffs.
- A ruling admits PoB-PoE2 `src/Data/ModRunes.lua` as a pinned text
  source (section 4).
