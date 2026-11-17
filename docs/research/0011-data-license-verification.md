# 0011 - Data license verification (DATA-LICENSE-VERIFY)

Evidence for decision 0009. All pages accessed 2026-11-17 unless noted.
Quotes are as returned by the fetch tool (a summarizer), so exact wording
should be re-read at the source before any legal reliance.

## Findings

- repoe-fork LICENSE: MIT, (c) 2016 brather1ng; generated `data` files are
  owned by Grinding Gear Games and "shall not be used or published without
  being in accordance with their terms of use".
  https://raw.githubusercontent.com/repoe-fork/repoe/master/LICENSE.md
- repoe-fork README credits: "The contents of all `data` files obviously
  belong to them" (GGG). No PoE2 mention in the README.
  https://github.com/repoe-fork/repoe
- Hosted PoE2 index (no license text; links to the GitHub project):
  https://repoe-fork.github.io/poe2/ and /index.json. HTTP checks: mods.json,
  base_items.json, stats_by_file.json, stat_translations/stat_descriptions.json
  return 200; stats.json and stat_translations.json return 404.
- GGG PoE2 tree export exists, no LICENSE file seen (404 on raw LICENSE):
  https://github.com/grindinggear/poe2-skilltree-export (data.json, assets/,
  README). PoE1: https://github.com/grindinggear/skilltree-export (no license
  file visible).
- Path of Building PoE2: MIT (c) David Gowor plus bundled third-party
  licenses.
  https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/LICENSE.md
  and https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2
- GGG developer docs: https://www.pathofexile.com/developer/docs (User-Agent
  format `OAuth {clientId}/{version} (contact: {contact})`, dynamic
  `X-Rate-Limit-*` and `Retry-After`, repeated overage revokes access, only
  API Reference and Data Exports supported, no commercial use of GGG IP,
  affiliation line). Terms of Use 7b / 7c / 7i cited but not shown.
- poe2db: https://poe2db.tw/General_disclaimer (CC BY-NC-SA 3.0, no scraping
  or API terms).
- PoE2 wiki: Copyrights page CC BY-NC-SA 3.0 Unported (search summary of
  https://www.poe2wiki.net/wiki/Path_of_Exile_2_Wiki:Copyrights); direct
  fetches of the page, /General_disclaimer and /COPYING hit an Anubis bot wall.
- poe.ninja: https://poe.ninja/docs/api (User-Agent with contact, ETag, no
  replicating the site, proxy desktop-app requests via own backend, economy
  endpoints only, no SLA). Footer disclaimer at https://poe.ninja/.

## Still UNVERIFIED

- Wiki license text read first-hand; GGG Terms of Use 7b/7c/7i text;
  PoB2 `src/Data` terms; trade2 endpoint docs; repoe-fork format-change
  warning; GGG staff forum quotes on User-Agent (search summary only).
