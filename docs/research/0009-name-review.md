# Name review: AshLight (and a fallback shortlist)

Research date 2026-11-16. Extends `docs/decisions/name-check-2026-11-16.md`
and decision 0001; it does not re-argue the choice. Test applied (decision
0001 "Reverses if"): a verified PoE/PoE2 tool or an npm/PyPI package named
AshLight doing this job, or "Ashlight" confirmed as a GGG proper noun.
Anything not confirmed is marked UNVERIFIED. All lookups were anonymous public
reads (registry JSON, MediaWiki search API, GitHub search API, Steam store
search API, public DNS); no registrar or trademark-office account was used.

## 1. GGG proper nouns (closes the poe2wiki half of ROADMAP PUB-NAME)

- poe2wiki.net full-text search for `ashlight`: 0 hits; for `"ash light"`:
  0 hits
  (https://www.poe2wiki.net/api.php?action=query&list=search&srsearch=ashlight&format=json,
  same with `srsearch=%22ash%20light%22`) (accessed 2026-11-16).
- poewiki.net (PoE1) full-text search for `ashlight` and `"ash light"`: 0 hits
  each
  (https://www.poewiki.net/api.php?action=query&list=search&srsearch=ashlight&format=json)
  (accessed 2026-11-16).
- Near terms that DO exist in PoE2 (title search `intitle:ashen`): Ashen
  Forest, Ashen Staff, Varloch, the Ashen Lord, Ashen Arachnid
  (https://www.poe2wiki.net/api.php?action=query&list=search&srsearch=intitle:ashen&format=json)
  (accessed 2026-11-16). Herald of Ash is a PoE2 skill
  (https://poe2wiki.net/wiki/Herald_of_Ash/edit?redlink=1, seen in web search
  results) (accessed 2026-11-16). "Ash" is a generic English word used across
  the game; no compound "Ashlight" / "Ash Light" exists. Not a proper noun.
- Web search `"Ash Light" Path of Exile 2 unique OR skill OR item`: no item,
  skill or unique of that name; closest hits Herald of Ash and Ashen Staff
  (https://www.poe2wiki.net/wiki/Ashen_Staff) (accessed 2026-11-16).
- poe2db.tw search: UNVERIFIED. `https://poe2db.tw/us/search?q=Ashlight`
  redirects (302) to the site home page, so no search result could be read
  (accessed 2026-11-16).
- GGG registered marks seen: PATH OF EXILE, USPTO serial 77930807 (reg.
  4094194) and serial 87371356 (reg. 5358588), owner Grinding Gear Games Ltd
  (https://trademarks.justia.com/779/30/path-of-exile-77930807.html,
  https://trademarks.justia.com/873/71/path-of-87371356.html) (accessed
  2026-11-16). The full owner list page returned 403 to the fetcher; a
  "Wraeclast" registration is UNVERIFIED. AshLight contains neither word nor
  any Wraeclast-derived word. Verdict: no GGG trademark proximity.

## 2. Collisions for AshLight / Ashlight / Ash Light

- npm 404, PyPI 404, crates.io 404 for `ashlight` (re-checked:
  https://registry.npmjs.org/ashlight, https://pypi.org/pypi/ashlight/json,
  https://crates.io/api/v1/crates/ashlight) (accessed 2026-11-16).
- GitHub repos: 32 with "ashlight" in the name; top by stars
  ashlight-team/horror-photo (4, UE5 game), ashlightfiles/Ashlight (1,
  personal site), cruftbox/ashlight (1, ESPHome lamp)
  (https://api.github.com/search/repositories?q=ashlight+in:name) (accessed
  2026-11-16). `ashlight overlay` and `ashlight poe` repo searches: 0 results
  (https://api.github.com/search/repositories?q=ashlight+overlay,
  https://api.github.com/search/repositories?q=ashlight+poe) (accessed
  2026-11-16).
- GitHub accounts: 32 users / orgs match, including the exact login
  `AshLight` (user, 1 public repo, no bio) and orgs AshlightStudio,
  ashlight-team, ashlight-systems
  (https://api.github.com/search/users?q=ashlight) (accessed 2026-11-16).
  Consequence: a GitHub org named exactly `AshLight` is taken; the repo can
  still live under the operator's own account (decision 0001 assumes that).
- Steam: one app, "ASHLIGHT" (app 3160080), Hubrbr Studio, indie RPG /
  strategy, "Coming soon", Windows
  (https://store.steampowered.com/api/storesearch/?term=ashlight&cc=us&l=en,
  https://store.steampowered.com/api/appdetails?appids=3160080) (accessed
  2026-11-16). STRONGEST COLLISION FOUND: same spelling and also a PC-games
  product, but a game, not a PoE companion tool. Not same-job.
- itch.io: small hobby games "Ashlight Yard", "Ashlight Beta", "Ashlight
  Forms - Vol. 1", "ASH LIGHT" (jacketau)
  (https://itch.io/search?q=ashlight, https://jacketau.itch.io/z) (accessed
  2026-11-16). Unrelated.
- Web search `"Ashlight" Path of Exile`: nothing relevant. Web search
  `"Ashlight" app OR software OR game`: only the itch.io game above (accessed
  2026-11-16).
- Domains (public DNS NS lookup and the public home page only):
  - ashlight.app: registered, Cloudflare NS; serves "Ashlight - Tecnologia
    sob medida", a Brazilian custom-software company (https://ashlight.app)
    (accessed 2026-11-16). Different market (bespoke business software).
  - ashlight.io: registered; page reads "Squarespace - Website Expired"
    (https://ashlight.io) (accessed 2026-11-16).
  - ashlight.com: NS at afternic.com (domain marketplace, parked) (accessed
    2026-11-16).
  - ashlight.gg: NXDOMAIN, appears unregistered (accessed 2026-11-16).
  - ashlight.net: lookup returned SERVFAIL; UNVERIFIED.
- Trademarks: web search `"Ashlight" trademark USPTO OR EUIPO` found no
  ASHLIGHT mark; only distinct marks ASHIALIGHT (87294784, dead), ASHINELIGHT
  (87406023, dead), ASHIA LIGHT (86500128, dead), ASHLITE (77226982, dead),
  and LASHLIGHT / DASHLIGHT in unrelated classes
  (https://markinton.com/trademark/ashialight-87294784,
  https://markinton.com/trademark/ashlite-77226982,
  https://trademarks.justia.com/997/83/dashlight-99783361.html) (accessed
  2026-11-16). The official USPTO search (https://tmsearch.uspto.gov/) is a
  JavaScript app and EUIPO eSearch was not queried: a direct office search is
  UNVERIFIED. Re-check both before any commercial release.

## 3. Naming of existing PoE companion tools (confusability)

Pattern from 0006 and a 2026 roundup: names lean on "PoE" / "Exile" / "Path
of" (Path of Building, PoE Overlay II, PoE2K, PoE Lurker, Exilence CE, Exiled
Exchange 2, Exile-UI, ExileXP, Path of Levelling 2) or on generic trade words
(Awakened PoE Trade, Sidekick, SlimTrade, MercuryTrade, Chaos Recipe
Enhancer)
(https://boostmatch.gg/blog/poe-2/articles/poe2-third-party-tools-guide,
https://www.poeoverlay.com/download/poe-overlay-ii,
https://web.poecdn.com/forum/view-thread/3934202,
https://relatedrepos.com/gh/Kami-Guru/path-of-levelling-2; others cited in
0006) (accessed 2026-11-16). Most of those lean on GGG's mark; AshLight does
not, and it shares no stem or sound with any of them. Verdict: not
confusable.

## 4. Fallback shortlist (same quick checks, 2026-11-16)

Checks per name: npm, PyPI, crates.io registry 404 test; GitHub repo search
`<name> in:name`; poe2wiki and poewiki full-text search; Steam store search
(where noted); .app / .gg NS lookup. Endpoints as in section 2 with the name
substituted (accessed 2026-11-16).

| Name | npm/PyPI/crates | GitHub repos | PoE wikis | Steam | .app / .gg | Verdict |
|---|---|---|---|---|---|---|
| Kindlewatch | free/free/free | 0 | 0/0 | 0 | free/free | Cleanest; best fallback |
| Vigilmark | free/free/free | 3, all 0-star empty | 0/0 | 0 | taken/free | Good; root "Vigil" also in PoE2 area "Dusk Vigil" (generic word, low risk) |
| Emberglance | free/free/free | 0 | 0/0 | not checked | free/free | Clean; "glance" fits the glanceable UI |
| Sootglass | free/free/free | 0 | 0/0 | not checked | free/free | Clean; weaker meaning |
| Embersight | free/free/free | 3 (EmberSight org, a FIRE-finance app) | 0/0 | 0 | free/free | Usable; small same-name finance project |
| Lanternward | free/free/free | 2 (Lantern Warden privacy page, issues stub) | 0/0 | not checked | free/free | Weak; "Lantern Warden" is a live mobile app |

PoE2 title checks for candidate roots: `intitle:kindle`, `intitle:soot`,
`intitle:cinder`, `intitle:lantern` 0 hits; `intitle:vigil` 2 hits (Dusk
Vigil, Legacy of Dusk Vigil) (https://www.poe2wiki.net/api.php, accessed
2026-11-16). A combined web search for Vigilmark / Kindlewatch / Sootglass /
Emberglance found no product of those names (accessed 2026-11-16).
Cinderpane was dropped: aalpern/cinderpane is a 25-star UI library
(https://github.com/aalpern/cinderpane) (accessed 2026-11-16).

## 5. Candidate "Herald" (operator query, 2026-11-16)

Verdict: REJECT.
- GGG vocabulary in both games. poe2wiki title search `intitle:herald`: 9 hits
  incl. Herald (page), Herald of Ice / Thunder / Ash / Blood / Plague, Deadly
  Herald; poewiki (PoE1): 39 hits incl. Herald (ascendancy class), Herald of
  Thunder / Ash / Ice / Agony / Purity, Kitava's Herald, many "Herald Effect"
  cosmetics
  (https://www.poe2wiki.net/api.php?action=query&list=search&srsearch=intitle:herald&format=json,
  https://www.poewiki.net/api.php?action=query&list=search&srsearch=intitle:herald&format=json)
  (accessed 2026-11-16). PoE2 has a Herald gem tag
  (https://www.poe2wiki.net/wiki/Herald_(gem_tag), https://poe2db.tw/Herald_Skills)
  (accessed 2026-11-16). Same spirit as decision 0001's reversal condition (a
  GGG proper noun): a game-mechanic term reads as official vocabulary and
  would collide in every wiki / build search.
- Registries all taken: npm `herald`, PyPI `herald`, crates.io `herald` each
  return HTTP 200 (https://registry.npmjs.org/herald,
  https://pypi.org/pypi/herald/json, https://crates.io/api/v1/crates/herald)
  (accessed 2026-11-16).
- GitHub: 2820 repos with "herald" in the name; top: Herald-OS (656 stars),
  maily_herald (572), heralding (400), nagios-herald (319)
  (https://api.github.com/search/repositories?q=herald+in:name&sort=stars)
  (accessed 2026-11-16). A PoE-flavoured repo `cptleo92/poe-herald` already
  exists (0 stars) (https://api.github.com/search/repositories?q=herald+path+of+exile)
  (accessed 2026-11-16).
- Steam: 10 store hits for "herald" incl. "Herald of Havoc" and "Herald of
  Moira" (https://store.steampowered.com/api/storesearch/?term=herald&cc=us&l=en)
  (accessed 2026-11-16).
- Not checked: domains, trademarks (UNVERIFIED; moot given the rejection).
- Does not meet the AshLight reversal test and is worse on every axis checked;
  AshLight stays.

## Bottom line

KEEP AshLight. The reversal condition is NOT met:
- no PoE/PoE2 tool, overlay or companion named AshLight exists (GitHub, web,
  tool roundups);
- npm, PyPI and crates.io have no `ashlight` package;
- poe2wiki and poewiki have 0 hits for "Ashlight" / "Ash Light" (poe2db stays
  UNVERIFIED).

Residual risks (not reversal triggers): the coming-soon Steam game ASHLIGHT
(app 3160080) shares the spelling in the PC-games space; the GitHub login
`AshLight` and the .app / .io / .com domains are taken (ashlight.gg looks
free); direct USPTO / EUIPO searches are UNVERIFIED. If the Steam game ships
and files a mark covering software, re-run this review. Suggested fallback
order: Kindlewatch, then Vigilmark (decision 0001 names Vigilmark only; this
file does not change that decision).

## Sources

All accessed 2026-11-16; full URLs inline above.
- MediaWiki search API on www.poe2wiki.net and www.poewiki.net
- registry.npmjs.org, pypi.org JSON API, crates.io API
- api.github.com repository and user search
- store.steampowered.com storesearch and appdetails APIs
- itch.io search
- public DNS NS lookups; https://ashlight.app and https://ashlight.io home
  pages
- trademarks.justia.com, markinton.com, tmsearch.uspto.gov (reachability
  only)
- boostmatch.gg, poeoverlay.com, web.poecdn.com, relatedrepos.com tool pages
