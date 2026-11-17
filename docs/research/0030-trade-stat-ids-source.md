# 0030 - Trade stat id source for upgrade-search mod filters (TC-UPGRADE-STATS)

Date: 2026-11-17. Trigger: ROADMAP row TC-UPGRADE-STATS (decision 0017
item 3). Question: is there a permitted source for the trade site's stat ids
(`explicit.stat_<number>` in a trade2 search `stats` group) so the offline
upgrade-search link can carry weighted mod filters? Ruling: decision 0037.

Builds on a stale lane draft (`refs/fleet-lanes/lane-0-1794928681`, commit
7aa228c, never merged, gates failed): that run had no web access and ended
"no permitted source, UNVERIFIED candidates". This note re-reads the
candidates at the source. Every URL below accessed 2026-11-17.

## 1. GGG API Reference and Data Exports (checked first)

- API Reference (https://www.pathofexile.com/developer/docs/reference):
  endpoint groups are Server, Account Profile, Account Item Filters,
  Leagues, PvP Matches, Account Leagues, Account Characters, Account
  Stashes, League Accounts, Guild Stashes, Public Stashes, Currency
  Exchange, Type and Extra Definitions. No trade endpoint and no trade stat
  or static-data endpoint; the only "trade" text is the Currency Exchange
  "trade history". Verdict: NOT A SOURCE.
- Data Exports (https://www.pathofexile.com/developer/docs/data): passive
  tree exports only (PoE2 tree, PoE1 tree, PoE1 atlas tree); "We do not
  officially provide access to any in-game data outside of our supported
  APIs." Verdict: NOT A SOURCE.
- The trade site's own stat list (`/api/trade2/data/stats`) is not in the
  docs; ToU 7i bars reverse-engineering endpoints outside them. Decision
  0017 and `webfetch.is_trade_url` keep the app off it at runtime and at
  build time. Verdict: RULED OUT.

## 2. repoe-fork PoE2 export (chosen)

- Index (https://repoe-fork.github.io/poe2/): no file named for trade
  data, but `stat_translations/stat_descriptions.json`, which AshLight
  ALREADY fetches into the sidecar cache under decision 0009
  (`snapshot.SOURCES["stat_translations"]`, cached as
  `stat_translations.json`), carries a `trade_stats` key on every entry:
  null or a list of `{id, text, type, option}` with ids such as
  `explicit.stat_3299347043` ("# to maximum Life") and types explicit,
  implicit, crafted, fractured, desecrated, enchant, augment, rune.
- Provenance: repoe-fork's generator
  (https://github.com/repoe-fork/repoe, `RePoE/parser/modules/stat_translations.py`,
  master, last commit caebf8f) requests
  `https://www.pathofexile.com/api/trade/data/stats` in its own build
  pipeline (User-Agent "OAuth RePoE/1.0.0 (contact: ...)") and joins the
  entries to game stat text by their formatted text. So the ids are GGG's
  trade site data relayed by repoe-fork; AshLight does not make that
  request.
- License: GitHub reports NOASSERTION for the repository; decision 0009 /
  research 0011 record the code as MIT and the data as GGG-owned, the same
  position as every other repoe-fork field AshLight already uses.
- Coverage (local check of the cached copy, 2026-11-17): 277 explicit
  trade ids; 11 of the 39 default weight keys match by text (life, %
  life, mana, the four "Adds # to #" damage lines, cast speed, movement
  speed, rarity, life on kill). Resistances, attributes, armour and others
  have no id in this copy (text join misses, likely markup in PoE2 text).
  A stat without an id gets no filter (decision 0037 condition 3).

## 3. Path of Building PoE2 (MIT code)

- `src/Data/TradeSiteStats.lua`
  (https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Data/TradeSiteStats.lua):
  header "This file contains the trade site data from
  https://www.pathofexile.com/api/trade2/data/stats", "Game data (c)
  Grinding Gear Games".
- `src/Data/QueryMods.lua` (same repo, dev): auto-generated, "mapped from
  trade hash to details relevant for generating search weights", entries
  with `tradeMod.id = "explicit.stat_<hash>"`.
- Verdict: same provenance as repoe-fork (a dump of the undocumented
  endpoint), but a second unvetted source and a Lua parse; not used.

## 4. poe2db and the PoE2 wiki

CC BY-NC-SA, link-only (decision 0009 item 4). NOT A SOURCE.

## 5. Result

Source: the `trade_stats` field of the repoe-fork `stat_translations`
snapshot already fetched under decisions 0009 / 0013. Used only to build
the offline `?q=` link (decision 0017); no new fetch host, no trade call,
no bundled table. Ruling, conditions and reversal: decision 0037.

## 6. Coverage of the cached copy (MATH-TRADESTAT-COVER)

Read 2026-11-17 from the sidecar cache copy of
stat_descriptions.json (Last-Modified 2026-11-14). Of 10759 entries,
292 carry `trade_stats` (277 explicit rows, 1 pseudo). Of entries with
markup ("[Tag|Text]") in the English string, 3 carry trade_stats and 5361
do not, so repoe-fork's trade-text matcher evidently skips marked-up
strings. All 28 default weight keys without an id (resistances,
attributes, armour / evasion / energy shield, spirit, increased physical /
spell / elemental damage, attack speed, crit, accuracy, skill levels,
recoup as life) have their template in the file with trade_stats null,
and no implicit, pseudo or local twin holds one. Coverage stays 11 of 39;
tradestats.norm strips markup so the keys map once upstream attaches the
rows. The trade number could be derived from the stat ids by hash, but
that is a guess outside the file and decision 0037 item 3 bars it.

## Sources

- https://www.pathofexile.com/developer/docs/reference (accessed 2026-11-17)
- https://www.pathofexile.com/developer/docs/data (accessed 2026-11-17)
- https://repoe-fork.github.io/poe2/ (accessed 2026-11-17)
- https://repoe-fork.github.io/poe2/stat_translations/stat_descriptions.json (accessed 2026-11-17)
- https://github.com/repoe-fork/repoe (RePoE/parser/modules/stat_translations.py, accessed 2026-11-17)
- https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Data/TradeSiteStats.lua (accessed 2026-11-17)
- https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Data/QueryMods.lua (accessed 2026-11-17)
