# poe.ninja, poe2db, wiki and static data access

Research date: 2026-11-16. Items without a fetched source are marked UNVERIFIED.

## poe.ninja (PoE2)

Source for everything in this section: https://poe.ninja/docs/api (accessed 2026-11-16).
- Supported surface: only the economy overview endpoints. Builds/profiles, character, Path of Building and auth endpoints are internal, "undocumented, unsupported, and not available for third-party use". Do not use them.
- PoE2 endpoints:
  - GET /poe2/api/economy/leagues: array of {id, name}; first entry is the current temporary challenge league.
  - GET /poe2/api/economy/exchange/current/overview?league=<id>&type=<type>
  - GET /poe2/api/economy/stash/current/item/overview?league=<id>&type=<type>
  - No stash currency endpoint for PoE2; currency is served by the exchange overview.
- PoE2 exchange types: Currency, Fragments, Abyss, UncutGems, LineageSupportGems, Essences, SoulCores, Idols, Runes, Ritual, Expedition, Delirium, Breach, Verisium. PoE2 stash item types: UniqueWeapons, UniqueArmours, UniqueAccessories, UniqueFlasks, UniqueCharms, UniqueJewels, UniqueSanctumRelics, UniqueTablets, PrecursorTablets.
- Exchange response: lines[] (id, primaryValue, volumePrimaryValue, maxVolumeCurrency, maxVolumeRate, sparkline) and core (primary, secondary, rates, items). PoE2 item lines use primaryValue plus category, itemId and modifier groups.
- Etiquette: responses are HTTP-cached about 5 minutes with ETags; use conditional requests, do not bypass caching. PoE2 data refreshes about hourly, so polling faster gains nothing. Send a descriptive User-Agent with app name and contact. Keep volume and concurrency low. Do not use it to replicate the site.
- Desktop clients "should proxy through their own backend" rather than hit endpoints from end-user machines. This conflicts with a pure local-only app; mitigation is a long local cache and a single shared poll interval. Whether an app-owned backend is feasible: UNVERIFIED, a design decision for the team.
- Stability: no versioning, no SLA, breaking changes possible without notice. Excessive use of the economy endpoints gets blocked.
- Attribution: no license text found. Stated: poe.ninja is not affiliated with or endorsed by GGG. Practical: credit "Prices: poe.ninja" in the UI. Data license or terms beyond the docs page: UNVERIFIED.
- A community report of an alternate path /poe2/api/economy/currencyexchange/overview?leagueName=&overviewName= exists (https://github.com/Davenads/poeninjaAPI-2025, license UNVERIFIED, via search summary) (accessed 2026-11-16); it differs from the official doc, so prefer the documented path.
- Builds data is closed, so a "popular builds" feature cannot rely on poe.ninja.

## poe2db.tw

- Offers a database of PoE2 items, skills, mods, passives and more. Its Developer_API page lists only pointers: POESESSID-based website APIs (unofficial), official OAuth APIs, GGPK format notes, an atlas tree export; it mentions no rate limits and no separate API terms (https://poedb.tw/Developer_API) (accessed 2026-11-16).
- License: "Wikis Content is available under CC BY-NC-SA 3.0 unless otherwise noted"; poewiki-derived content is reused under CC BY-NC-SA 3.0; GGG holds copyright and trademarks for Path of Exile; "Copyright 2014-2026 PoE2DB" (https://poe2db.tw/General_disclaimer) (accessed 2026-11-16).
- Own public API or scraping permission: none found (a search found no terms page on scraping). Treat as no permission: do not scrape at runtime. Link out to poe2db pages instead (deep links are safe). The NonCommercial and ShareAlike terms apply if any content is copied; avoid copying.

## PoE2 Wiki (poe2wiki.net)

- Content license: CC BY-NC-SA 3.0 Unported for content the wiki may lawfully license (https://www.poe2wiki.net/wiki/Path_of_Exile_2_Wiki:Copyrights/history and https://www.poe2wiki.net/wiki/Path_of_Exile_2_Wiki:General_disclaimer, via search summary) (accessed 2026-11-16). A direct fetch of the Copyrights page was refused by bot protection.
- Data is mostly Cargo-based (https://www.poe2wiki.net/wiki/Help:Advice_for_experienced_editors, via search summary) (accessed 2026-11-16). The PoE1 wiki documents a Cargo/MediaWiki query API (https://www.poewiki.net/wiki/Path_of_Exile_Wiki:Data_query_API); fetching it returned an Anubis "Access Denied" page (accessed 2026-11-16), so automated access is actively blocked. Whether api.php on poe2wiki.net is open to apps, and its rate limits: UNVERIFIED. Do not depend on it at runtime; if used, build-time only, with a polite User-Agent and attribution.
- Derived data carries CC BY-NC-SA obligations. For an open-source non-commercial app this is workable but must be stated; if the app's own license is not share-alike compatible, avoid bundling wiki text.

## Game data exports (RePoE fork, PyPoE, GGPK)

- repoe-fork: GitHub repo forked from brather1ng/RePoE; parses via PyPoE; README warns "the file formats are not final, they may change at any time"; credits state GGG owns the contents of the data files; it links a LICENSE.md but the license was not shown, so repo license: UNVERIFIED (https://github.com/repoe-fork/repoe) (accessed 2026-11-16).
- Hosted exports: https://repoe-fork.github.io/poe2 (PoE2 game data JSON), https://repoe-fork.github.io/pob-data/poe2 (Path of Building export for PoE2), JSON schemas at https://repoe-fork.github.io/data-formats (https://repoe-fork.github.io/) (accessed 2026-11-16). The page states no license. Files include stats, mods, base_items, gems, stat_translations, item_classes.
- GGG policy: the developer docs say apps that interact with the game or its files result in account termination (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16). The Terms of Use forbid modifying or adapting the client or its data, including via third-party tools, without written approval (https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy, via search summary) (accessed 2026-11-16). Read-only extraction by an end-user app is not explicitly addressed.
- Assessment: the app itself must not open game files beyond Client.txt (the developer policy permits log reading when the user knows). Consuming prebuilt public exports downloaded from the internet is a separate act: the app never touches the user's game install. Risk is data ownership (GGG owns the data) rather than a ban risk; ship it as a build-time snapshot, credit GGG, and verify the repo licenses before bundling. Legal certainty: UNVERIFIED; ask GGG through the developer contact if the project grows.

## GGG official feeds

- Official API: leagues list and PoE2 ladder (top 1,000, OAuth scope service:leagues:ladder) per https://www.pathofexile.com/developer/docs/reference (accessed 2026-11-16). OAuth registration is closed (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16), so these may be unavailable to a new app; confirm. The poe.ninja leagues endpoint is a no-auth alternative for the league name.
- Patch notes RSS / forum feed URL: UNVERIFIED (not fetched). Check the PoE2 patch-notes forum section for an RSS link.

## Recommendation by feature

- Price check (single item): trade2 search + fetch on demand behind the rate limiter (see trade-api.md); fall back to the poe.ninja stash item overview for uniques (hourly, cached).
- Currency rates: poe.ninja exchange overview type=Currency, refresh no faster than hourly, honor ETag; optional cross-check with the official currency-exchange feed (hourly history).
- League name: poe.ninja /poe2/api/economy/leagues or trade2 data/leagues; cache per session.
- Zone/act info and boss info: no official or terms-clear API found. Use a project-authored static dataset (facts in own wording), with deep links to poe2db or the wiki for detail; do not scrape.
- Leveling guide data: project-authored static data; optional import of mod/gem metadata from repoe-fork snapshots at build time.
- Offline caching: keep the last good response per endpoint on disk with a timestamp; show staleness; refresh on launch if older than 1 h for prices, per patch for static data.
- Attribution text (suggested): "Not affiliated with or endorsed by Grinding Gear Games. Prices from poe.ninja. Game data (c) Grinding Gear Games; community exports via the RePoE fork. Wiki-derived text under CC BY-NC-SA 3.0 from the PoE2 Wiki / PoE2DB where used."

## Act / zone levels (HUD-ACT)

- The repoe-fork PoE2 directory listing (https://repoe-fork.github.io/poe2/,
  accessed 2026-11-17) holds `world_areas.json` and `world_areas.min.json`
  next to the files decision 0009 already uses; the page states no license
  (same as research 0011 line 3).
- `https://repoe-fork.github.io/poe2/world_areas.json` (accessed
  2026-11-17, about 1.9 MB): an object keyed by area id; each entry has
  `act`, `area_level`, `name`, `is_town`, `has_waypoint`, `connections`,
  `parent_town`, `tags` and more. The first key is a `NULL` placeholder
  with `area_level` 0.
- License position: unchanged from research 0011 (repoe-fork code MIT, data
  owned by GGG). poe2db / wiki act tables stay link-out only (CC BY-NC-SA).
- Live area ids seen: `G1_1`, `G1_town` (research 0002 section 7). Cruel
  `C_G<n>_` and interlude `P<n>_` prefixes are not yet seen live.
- Ruling: decision 0020 (build-time cache only, attributed, never bundled).

## Sources

- https://poe.ninja/docs/api (accessed 2026-11-16)
- https://github.com/Davenads/poeninjaAPI-2025 (accessed 2026-11-16; license UNVERIFIED; summary only)
- https://poedb.tw/Developer_API (accessed 2026-11-16)
- https://poe2db.tw/General_disclaimer (accessed 2026-11-16)
- https://www.poe2wiki.net/wiki/Path_of_Exile_2_Wiki:Copyrights/history (accessed 2026-11-16; summary only)
- https://www.poe2wiki.net/wiki/Path_of_Exile_2_Wiki:General_disclaimer (accessed 2026-11-16; summary only)
- https://www.poewiki.net/wiki/Path_of_Exile_Wiki:Data_query_API (accessed 2026-11-16; blocked)
- https://github.com/repoe-fork/repoe (accessed 2026-11-16; license UNVERIFIED)
- https://repoe-fork.github.io/ (accessed 2026-11-16)
- https://www.pathofexile.com/developer/docs (accessed 2026-11-16)
- https://www.pathofexile.com/developer/docs/reference (accessed 2026-11-16)
- https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy (accessed 2026-11-16; summary only)
- https://repoe-fork.github.io/poe2/world_areas.json (accessed 2026-11-17)
