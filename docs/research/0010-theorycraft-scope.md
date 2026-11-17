# 0010 - Theorycraft and item-optimization scope

Research date: 2026-11-16 (operator order: AshLight also covers
theorycrafting builds and item optimization, beside the live companion).
Every claim cites a URL accessed 2026-11-16. Anything not confirmed by a
fetched page is marked UNVERIFIED. Earlier research this builds on: 0003
(clipboard), 0004 (trade API), 0005 (data sources), 0006 (existing tools).

## 1. Path of Building for PoE2 (PoB2)

Repo: https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2
(accessed 2026-11-16).

- What: "an offline build planner for Path of Exile 2"; offence and defence
  calcs, passive tree, skills, items; 1.9k stars, about 10.2k commits on
  `dev` (same URL) (accessed 2026-11-16).
- Latest release: v0.23.1, published 2026-07-28
  (https://api.github.com/repos/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases/latest)
  (accessed 2026-11-16).
- Feature lines relevant to us, quoted from
  https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/README.md
  (accessed 2026-11-16): "Add items from in game by copying and pasting them
  straight into the program!"; "Search the trade site for the most impactful
  items"; "see exactly how much of an upgrade a given item is!"; "You can
  import passive tree, items, and skills from existing characters"; "Share
  builds with other users by generating a share code".

### License check (recorded)

Source: https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/LICENSE.md
(accessed 2026-11-16).
- Main license: MIT, "Copyright (c) 2016 David Gowor".
- Third-party notices in the same file: LuaJIT (MIT, Mike Pall), PUC-Rio
  Lua (MIT), Lua-cURL and libcurl (MIT / curl), dkjson, sha1, sha2, xml.lua,
  lua-profiler, luasocket, lua-utf8 (MIT), SimpleGraphic (MIT), base64.lua
  (LGPL), fonts (Bitstream Vera license, SIL OFL 1.1), libsodium (ISC), re2,
  ANGLE, libjpeg-turbo (BSD-3), abseil (Apache-2.0), fmtlib, stb, GIFLIB.
- Verdict: no blocker for interoperation. Running an unmodified PoB checkout
  as a separate process and exchanging build XML with it copies no code. If
  any PoB file were ever redistributed, the MIT notice must ship with it and
  base64.lua is LGPL (keep it a separate, replaceable file; do not merge it
  into AshLight code). Game data inside PoB (`src/Data`) is GGG-owned content
  extracted from the client, not MIT-licensable by the PoB team (our
  inference; see section 3 for GGG's position). Plan: never vendor PoB into
  the tracked tree; fetch a pinned release at setup into the AL sidecar.

### Calc engine and headless use

- The repo ships `src/HeadlessWrapper.lua`: it loads `_SimpleGraphic.def.lua`
  whose functions "have dummy function bodies intended for headless use",
  runs `Launch.lua`, needs at least one `OnFrame`, and exposes
  `loadBuildFromXML(xmlText, name)` and `loadBuildFromJSON(characterJSON)`
  (the latter imports items, skills, passives and jewels from character JSON
  but "may lack a correct main skill or configuration options"); it "can be
  run using a standard lua interpreter, although LuaJIT is preferable"
  (https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/HeadlessWrapper.lua)
  (accessed 2026-11-16).
- Proven pattern: pob-mcp (MIT, Python + Lua) spawns a LuaJIT subprocess
  running a bridge "forked from PoB's own src/HeadlessWrapper.lua" and talks
  JSON-RPC over stdio; it "works the same way against a git checkout of
  PathOfBuilding-PoE2 and against an installed release build"; installed
  copies omit HeadlessWrapper.lua and PoB's runtime "doesn't ship a
  standalone interpreter", so LuaJIT must be supplied separately; methods
  cover loading codes / XML, `get_stats`, `equip_item_raw`, passive and gem
  edits, `export_build`
  (https://raw.githubusercontent.com/juddisjudd/pob-mcp/HEAD/README.md)
  (accessed 2026-11-16).
- pob2-mcp runs "an unmodified PathOfBuilding-PoE2 checkout" through a
  headless luajit `api-stdio` bridge and warns "a wildly newer/older PoB may
  drift"; it is GPL-3.0, so ideas only, no code
  (https://raw.githubusercontent.com/zgrummons/pob2-mcp/HEAD/README.md)
  (accessed 2026-11-16).
- LuaJIT on Windows: pob2-mcp tells users to "download from
  https://luajit.org/ and add to PATH" (same URL); luajit.org distributes
  source, so a Windows binary is built or obtained elsewhere (UNVERIFIED:
  no official Windows binary page fetched).
- poe.ninja itself states "DPS is calculated using Path of Building
  Community Fork" (https://poe.ninja/docs/dps-calculation) (accessed
  2026-11-16): PoB numbers are the community's common currency.
- Drift risk: PoB internals (`main.modes["BUILD"]`, calcs output keys) are
  not a public API; pin one PoB release and test the bridge against it.

### Build code format (interop without Lua)

- Export: `common.base64.encode(Deflate(self.build:SaveDB("code")))` then
  `+` -> `-` and `/` -> `_`. Import reverses it with `Inflate` of the base64
  decode; the payload is the build XML
  (https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Classes/ImportTab.lua)
  (accessed 2026-11-16).
- Consequence: Python stdlib `base64.urlsafe_b64decode` + `zlib.decompress`
  reads a PoB2 code into XML, and the reverse writes one. Build view
  (tree, gear, skills, PoB's saved stat summary in the XML) needs no Lua.
  Exact zlib header / raw-deflate framing: UNVERIFIED until tested on a
  real code (the `Deflate` helper lives outside ImportTab.lua).
- Code-sharing sites come from a `buildSites.websiteList` table (match URL,
  download); the default export target is "Pastebin" (same URL). AshLight
  should accept a pasted code and only fetch a share URL the user pasted.

## 2. Character and item import

### GGG official OAuth API

- Registration: "We are currently unable to process new applications."
  (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16).
  Applying when it reopens is an operator act.
- Standalone executables: "While not encouraged, these are permitted. They
  must use a public OAuth client if interacting with our APIs." Reverse
  engineering: "It is against our Terms of Use (section 7i) to
  reverse-engineer endpoints outside of this documentation." Commercial use:
  "we cannot allow our Intellectual Property to be used to generate
  commercial revenue." (same URL) (accessed 2026-11-16).
- Public clients: Authorization Code with PKCE, "must use a local redirect
  URI" (example http://127.0.0.1:8080/callback), access token 10 h, refresh
  7 days, rate limits shared with all public clients, users see a warning
  that the request's authenticity is unverifiable; public clients "Cannot
  use any service:* scopes"
  (https://www.pathofexile.com/developer/docs/authorization) (accessed
  2026-11-16).
- Account scopes: `account:profile`, `account:leagues`, `account:stashes`,
  `account:characters`, `account:league_accounts`, `account:item_filter`
  (same URL) (accessed 2026-11-16).
- PoE2 coverage (https://www.pathofexile.com/developer/docs/reference)
  (accessed 2026-11-16): `GET /character[/<realm>]` and
  `GET /character[/<realm>]/<name>` accept realm `poe2` (scope
  `account:characters`); Character has PoE2-only `skills`,
  `passives.specialisations` (set1..set3) and `passives.quest_stats`; Item
  has PoE2-only fields such as `runeMods`, `gemSockets`, `grantedSkills`,
  `desecrated`. Account Stashes and League Accounts are "PoE1 only". The
  page notes "There are currently limited APIs that return PoE2 game
  information."
- So the one sanctioned live import is: user signs in through a GGG public
  OAuth client registered to AshLight, scope `account:characters` (plus
  `account:profile`), loopback redirect on the AL port block. Blocked until
  GGG reopens registration. AshLight must never reuse another app's client
  id (that would misrepresent the app; our inference from the User-Agent
  rule `OAuth {clientId}/{version}` in research 0004).
- PoB2 already does this with its own client: ImportTab calls
  `main.api:DownloadCharacterList(realm.realmCode)` and
  `DownloadCharacter(...)` with realm code `poe2`, using OAuth tokens, no
  POESESSID
  (https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Classes/ImportTab.lua)
  (accessed 2026-11-16). Until AshLight has a client, the ToS-clean path is:
  user imports the character in PoB2, exports the share code, pastes it into
  AshLight.

### Public character / profile endpoints

- No documented public (unauthenticated) character endpoint for PoE2 in the
  reference (https://www.pathofexile.com/developer/docs/reference)
  (accessed 2026-11-16). The website's `character-window` endpoints are
  undocumented: using them is reverse engineering under ToU 7i
  (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16).
  They need a POESESSID for private profiles anyway. Ruled out.
- poe.ninja build / profile / PoB endpoints are "undocumented, unsupported,
  and not available for third-party use" (https://poe.ninja/docs/api)
  (accessed 2026-11-16; also research 0005). Ruled out; link out instead.
- Ladder: `GET /league/<league>/ladder` with realm poe2, top 1,000, scope
  `service:leagues:ladder`, which public clients cannot hold
  (https://www.pathofexile.com/developer/docs/reference and
  https://www.pathofexile.com/developer/docs/authorization) (accessed
  2026-11-16). Not reachable for a desktop app.

### Clipboard item read (existing per-press rule)

- GGG: reading screen or clipboard only "once per manual key press"
  (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16);
  AshLight decision 0003 already applies it (user presses Ctrl+C in game,
  then an AshLight hotkey reads the clipboard once; AshLight sends no input).
- The game's copied item text is what PoB itself accepts ("copying and
  pasting them straight into the program", README URL above) and what
  pob-mcp's `equip_item_raw` takes (pob-mcp README above). One clipboard read
  therefore feeds both the price check (PRICE-1) and an "evaluate against my
  build" action. Parser design: research 0003.

## 3. Game data sources (mods, bases, passives, skills)

All snapshots are taken at build time only, never fetched at runtime.

- GGG official exports: "We do not officially provide access to any in-game
  data outside of our supported APIs", with "The exception to this is the
  Passive trees"; PoE2 export: https://github.com/grindinggear/poe2-skilltree-export
  (https://www.pathofexile.com/developer/docs/data) (accessed 2026-11-16).
  The export repo holds `data.json` and `assets/`, no LICENSE file and no
  stated terms (https://github.com/grindinggear/poe2-skilltree-export)
  (accessed 2026-11-16). Status: GGG-published for third-party use; use it,
  credit GGG; terms beyond the developer docs UNVERIFIED.
- RePoE fork: repo code MIT ("Copyright (c) 2016 brather1ng"); separate
  notice that generated `data` files are owned by Grinding Gear Games "and
  shall not be used or published without being in" (compliance with GGG
  terms) (https://raw.githubusercontent.com/repoe-fork/repoe/master/LICENSE.md)
  (accessed 2026-11-16). Hosted exports: repoe-fork.github.io/poe2 and
  repoe-fork.github.io/pob-data/poe2 with mods.json, base_items.json,
  stats.json, stat_translations.json, gems.json; no version label or update
  date on the page (https://repoe-fork.github.io/) (accessed 2026-11-16).
  README: "the file formats are not final, they may change at any time"
  (https://github.com/repoe-fork/repoe) (accessed 2026-11-16). Status:
  usable as an attributed build-time snapshot; GGG owns the data and does
  not officially provide it (developer docs above), so ship it for a
  non-commercial app only, with credit, and keep the risk in decision 0004
  (DATA-LICENSE row).
- poe2db: "Wikis Content is available under CC BY-NC-SA 3.0 unless otherwise
  noted" (https://poe2db.tw/General_disclaimer) (accessed 2026-11-16); no API
  terms or scraping permission (https://poedb.tw/Developer_API) (accessed
  2026-11-16). Status: link out only; no scraping, no bundling.
- PoE2 wiki: CC BY-NC-SA 3.0 Unported
  (https://www.poe2wiki.net/wiki/Path_of_Exile_2_Wiki:General_disclaimer)
  (accessed 2026-11-16, via search summary in research 0005); automated
  access blocked by bot protection (research 0005). Status: link out only;
  any wiki text reused carries NC + ShareAlike.
- PoB's own `src/Data`: comes with the pinned PoB checkout at setup; used
  by PoB's engine in place; AshLight does not re-export it.
- Recommendation: AshLight's own mod/base tables (for the item evaluator
  without PoB) come from the RePoE fork PoE2 export plus GGG's skill tree
  export, snapshotted at build time into the sidecar Cache with a manifest
  (source URL, fetch date, sha256) and the attribution line from 0005.

## 4. Item optimization approaches

- DPS / EHP delta (the PoB model): PoB's TradeQueryGenerator writes each
  candidate mod (at a mid roll, `defaultItemAffixQuality` 0.5) onto a test
  item, recalculates, and keeps `weight = meanStatDiff / tradeModValue` for
  the user's chosen outputs (FullDPS with fallbacks TotalDPS, TotalDotDPS,
  CombinedDPS); it builds a trade2 query with one `"type": "weight"` stat
  group, under the trade site's "maximum complexity of 200" (4 per stat
  filter)
  (https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Classes/TradeQueryGenerator.lua)
  (accessed 2026-11-16). That file references no EHP; EHP weighting is a gap
  (same URL).
- PoB's trade requester parses rate limits through a limiter
  (`UpdateFromHeader`), honors `Retry-After` with capped exponential backoff,
  fetches in blocks of 10, sends `Authorization: Bearer` from its OAuth
  login, no POESESSID
  (https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Classes/TradeQueryRequests.lua)
  (accessed 2026-11-16).
- Stat-weight scoring (no calc engine): a user- or preset-defined weight per
  stat id, score = sum(weight x value) over parsed mods; cheap, instant,
  works on the clipboard item alone; inaccurate for conversions,
  breakpoints and multiplicative layers. Good as phase 1 and as a fallback.
- DPS / EHP delta via PoB headless: exact (as exact as PoB), needs the
  optional LuaJIT + PoB component; per-item cost is one PoB recalculation.
- Upgrade search: build the weighted trade2 query from the deltas, run it
  only on an explicit user action, through the single PRICE-1 rate-limited
  queue that rebuilds limits from `X-Rate-Limit-*` on every response
  (https://www.pathofexile.com/developer/docs/index) (accessed 2026-11-16;
  research 0004). trade2 is the website's own API, not in GGG's reference
  (research 0004), so it stays opt-in with the risk stated in the UI.
- poe.ninja: only the economy endpoints are supported for third parties
  (https://poe.ninja/docs/api) (accessed 2026-11-16); use them to price
  candidate upgrades (currency rates), hourly, ETag-cached (research 0005).
  Builds data is not available: link to poe.ninja builds pages
  (https://poe.ninja/poe2/builds) (accessed 2026-11-16; page states "poe.ninja
  is not affiliated with or endorsed by Grinding Gear Games").

## 5. Existing tools: gaps and ideas

- PoB2 (MIT): the reference calc engine and item-upgrade search; desktop
  GUI only, not glanceable, no live-session link (README above).
- poe.ninja builds: aggregate ladder builds, DPS via PoB
  (https://poe.ninja/docs/dps-calculation) (accessed 2026-11-16); closed data.
- Maxroll PoE2Planner: web planner; character import after logging into
  Maxroll ("you can only import your own characters"), imports tree, skills
  and equipment, can link a PoB; DPS not described
  (https://maxroll.gg/poe2/news/poe2planner-character-import-feature)
  (accessed 2026-11-16; article updated 2025-03-30). Closed, ideas only.
- Craft of Exile: closed crafting emulator website with a PoE2 mode
  (https://craftofexile.com/?game=poe2) (accessed 2026-11-16); link out.
- POE2_HTC: browser PoE2 crafting optimizer, cross-checked against Craft of
  Exile and a Monte-Carlo simulator (https://github.com/Dboire9/POE2_HTC/wiki)
  (accessed 2026-11-16, via search summary; license UNVERIFIED).
- pyoe2-craftpath (MIT per search summary): finds craft paths between a
  start and target PoE2 item (https://docs.rs/crate/pyoe2-craftpath/0.5.0/source/Cargo.toml)
  (accessed 2026-11-16, via search summary).
- autocraftofexile "automatically executes a Craft of Exile Simulator recipe
  in Path of Exile" (https://pypi.org/project/autocraftofexile/) (accessed
  2026-11-16, via search summary): input automation, breaches our floor;
  never emulate.
- pob-mcp (MIT) / pob2-mcp (GPL-3.0, ideas only): headless PoB bridges
  (URLs in section 1).
- Gaps AshLight can fill without a new calc engine: (1) the build you are
  playing, glanceable on the second screen next to the live session;
  (2) "is this item an upgrade for MY build" from one clipboard read, with
  a PoB delta when the optional component is installed and a stat-weight
  score when it is not; (3) EHP-aware upgrade weights (PoB's generator
  weighs only chosen offence outputs, section 4); (4) price the delta in
  currency via poe.ninja; (5) crafting: link out, do not build a simulator.

## 6. Does the name AshLight still fit?

- The name was chosen and re-reviewed for collisions and GGG vocabulary
  (decision 0001; research 0009 is under separate review and not edited
  here). Nothing in the wider scope changes a collision or trademark fact.
- Fit: "light on your build" reads as naturally as "light on your session";
  established tools in the space carry non-descriptive names (Path of
  Building, Sidekick, Exiled Exchange 2; research 0006). Verdict: keep
  AshLight; no flag for the name review needed. Reverses if: the product is
  split into two apps (then name the theorycraft one separately).

## Sources

- https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2 (accessed 2026-11-16)
- https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/README.md (accessed 2026-11-16)
- https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/LICENSE.md (accessed 2026-11-16)
- https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/HeadlessWrapper.lua (accessed 2026-11-16)
- https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Classes/ImportTab.lua (accessed 2026-11-16)
- https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Classes/TradeQueryGenerator.lua (accessed 2026-11-16)
- https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Classes/TradeQueryRequests.lua (accessed 2026-11-16)
- https://api.github.com/repos/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases/latest (accessed 2026-11-16)
- https://raw.githubusercontent.com/juddisjudd/pob-mcp/HEAD/README.md (accessed 2026-11-16)
- https://raw.githubusercontent.com/zgrummons/pob2-mcp/HEAD/README.md (accessed 2026-11-16)
- https://www.pathofexile.com/developer/docs (accessed 2026-11-16)
- https://www.pathofexile.com/developer/docs/index (accessed 2026-11-16)
- https://www.pathofexile.com/developer/docs/authorization (accessed 2026-11-16)
- https://www.pathofexile.com/developer/docs/reference (accessed 2026-11-16)
- https://www.pathofexile.com/developer/docs/data (accessed 2026-11-16)
- https://github.com/grindinggear/poe2-skilltree-export (accessed 2026-11-16)
- https://github.com/repoe-fork/repoe (accessed 2026-11-16)
- https://raw.githubusercontent.com/repoe-fork/repoe/master/LICENSE.md (accessed 2026-11-16)
- https://repoe-fork.github.io/ (accessed 2026-11-16)
- https://poe2db.tw/General_disclaimer (accessed 2026-11-16)
- https://poedb.tw/Developer_API (accessed 2026-11-16)
- https://www.poe2wiki.net/wiki/Path_of_Exile_2_Wiki:General_disclaimer (accessed 2026-11-16; via search summary)
- https://poe.ninja/docs/api (accessed 2026-11-16)
- https://poe.ninja/docs/dps-calculation (accessed 2026-11-16)
- https://poe.ninja/poe2/builds (accessed 2026-11-16)
- https://maxroll.gg/poe2/news/poe2planner-character-import-feature (accessed 2026-11-16)
- https://craftofexile.com/?game=poe2 (accessed 2026-11-16)
- https://github.com/Dboire9/POE2_HTC/wiki (accessed 2026-11-16; via search summary)
- https://docs.rs/crate/pyoe2-craftpath/0.5.0/source/Cargo.toml (accessed 2026-11-16; via search summary)
- https://pypi.org/project/autocraftofexile/ (accessed 2026-11-16; via search summary)
