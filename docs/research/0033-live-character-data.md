# 0033 - Live character data beyond Client.txt

Date 2026-11-17. Question: which PERMITTED sources can give AshLight the
player's own equipment, skills and passives live, so the player need not
paste a PoB code or press the item hotkey, plus what static data supports
campaign pathing. Floor: CLAUDE.md "Game ToS floor", decisions 0003, 0013,
0017; prior work 0010 section 2, 0022, 0024 (this note re-verifies and
extends them). All sources accessed 2026-11-17 unless stated.

## 1. GGG developer API (the one sanctioned live source)

- Registration is CLOSED: "We are currently unable to process new
  applications." No email or form channel is listed; existing apps are
  managed from "Manage applications" in the profile
  (https://www.pathofexile.com/developer/docs/index). Any channel not on
  that page is UNVERIFIED. Applying when it reopens is an operator act
  (ROADMAP TC-OAUTH-REG stays BLOCKED).
- Standalone executables "must use a public OAuth client if interacting
  with our APIs"; reverse engineering endpoints outside the docs is against
  ToU 7i; "Requests for access to any other internal website APIs or
  in-game resources will be denied"
  (https://www.pathofexile.com/developer/docs).
- Public client rules
  (https://www.pathofexile.com/developer/docs/authorization): "Must only
  use the Authorization Code (with PKCE) grant type" (verifier at least 32
  bytes of entropy); "must use a local redirect URI (ie.
  http://127.0.0.1:8080/callback)" - a loopback redirect IS allowed and no
  port rule is stated, so a port in the AL block (8960-8979) fits; access
  token 10 h, refresh token 7 days (confidential: 28 / 90 days); rate
  limits shared with all public clients; users see a warning that the
  request's authenticity "is unverifiable"; "Cannot use any service:*
  scopes".
- Account scopes (same page): `account:profile`, `account:leagues`,
  `account:stashes`, `account:characters` ("for viewing the account's
  characters and inventories"), `account:league_accounts`,
  `account:item_filter`.
- Endpoints and PoE2 support
  (https://www.pathofexile.com/developer/docs/reference; "There are
  currently limited APIs that return PoE2 game information"):
  - `GET /character[/<realm>]` (List Characters) and
    `GET /character[/<realm>]/<name>` (Get Character), scope
    `account:characters`; "`realm` can either be `xbox`, `sony`, or
    `poe2`". Base URL https://api.pathofexile.com.
  - Character fields for PoE2: `equipment` and `jewels` (both games),
    `skills` ("PoE2 only", array of Item), `passives` with
    `specialisations` set1..set3 and `quest_stats` (both "PoE2 only"),
    `metadata.version`. `inventory` and `rucksack` are "PoE1 only": the
    PoE2 backpack is NOT exposed. Account Stashes (`/stash`) and League
    Accounts are PoE1 only.
  - `GET /profile` (`account:profile`), `GET /account/leagues[/<realm>]`
    (`account:leagues`, `poe2` accepted), `/item-filter`
    (`account:item_filter`, realm `poe2` on create / update; AshLight
    writes no filter, decision 0033).
  - `/league` and `/league/<league>/ladder` need `service:*` scopes - not
    reachable from a public client. Currency Exchange
    (`https://web.poecdn.com/api/currency-exchange[/<realm>]`, realm
    `poe2`) is public, hourly history only (research 0004).
- Required headers (https://www.pathofexile.com/developer/docs/index):
  `User-Agent: OAuth {$clientId}/{$version} (contact: {$contact}) ...`;
  rate limits via `X-Rate-Limit-Policy`, `X-Rate-Limit-Rules`,
  `X-Rate-Limit-{rule}` (hits:period:restrict seconds),
  `X-Rate-Limit-{rule}-State` (hits:period:active restriction) and
  `Retry-After`; "These limits are dynamic and can change at any time";
  "Exceeding these limits frequently will result in your application
  access being revoked." Obey them dynamically.

## 2. How live is Get Character

- GGG only says API access "is almost always a read-only snapshot of data
  stored on the game servers" (https://www.pathofexile.com/developer/docs).
  No refresh rule, cache field or polling cadence is documented for
  characters (https://www.pathofexile.com/developer/docs/reference); two
  searches found no primary source on whether an equip change shows
  before a zone change or logout. Staleness: UNVERIFIED - measure once a
  client exists.
- Polling policy: none beyond the rate-limit headers and the revocation
  warning above. Design consequence (our inference): no free-running
  timer; fetch on a Client.txt trigger (area change, level-up) with a
  minimum interval, plus a dashboard Refresh button, and back off on
  `X-Rate-Limit-*-State`. Fits ZERO-CLICK and decision 0013 (web_data
  opt-in; the GGG sign-in is a second explicit opt-in).

## 3. PoB-PoE2 and poe.ninja

- PoB-PoE2 imports via the DOCUMENTED API, not character-window: base
  `https://api.pathofexile.com`, paths `/character/poe2` and
  `/character/poe2/<name>`, OAuth authorize / token at
  `https://www.pathofexile.com/oauth/authorize` and `/oauth/token`, PKCE
  S256, redirect `http://localhost:<port>`, its own `client_id=pob`, scopes
  `account:profile account:leagues account:characters account:trade`
  (`account:trade` is not in GGG's public scope list)
  (https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Classes/PoEAPI.lua).
  AshLight must not reuse the `pob` client id (the UA names the client;
  reuse would misrepresent the app - research 0010). Until AshLight has its
  own client the clean path stays: import in PoB2, export the code, paste.
- poe.ninja: "The builds / profiles API, and every other non-economy
  endpoint (character, Path of Building, authentication), are internal."
  "They are undocumented, unsupported, and not available for third-party
  use" (https://poe.ninja/docs/api). Ruled out; link out only.
- Website `character-window/*` endpoints: undocumented (ToU 7i) and need
  POESESSID (floor forbids). Ruled out (research 0010).

## 4. Game-side streams besides Client.txt

- GGG documents no overlay API, client API or other game data stream; it
  names only "information sourced from the screen, the clipboard, or the
  game's logs" (https://www.pathofexile.com/developer/docs).
- Screen / clipboard: once per manual key press only (floor; decision
  0003). Cannot be a live inventory feed.
- `.build` files in `Documents/My Games/Path of Exile 2/BuildPlanner`: a
  documented format the game READS (research 0018, 0027); they hold a
  planned build, not the live character. AshLight writes none (decision
  0034) and reading them gives nothing live. Not a source.
- Filter folder, game config ini, screenshots: game files outside the
  floor's Client.txt-only read rule, and none holds live character state.
  Not sources.
- Steam rich presence: set by the game through Steamworks and shown in the
  friends list
  (https://partner.steamgames.com/doc/features/enhancedrichpresence); that
  page documents no web read path, and whether PoE2 sets more than a status
  string is UNVERIFIED. Community Discord presence tools derive zone /
  level from the log instead (e.g. https://github.com/ezbooz/Path-Of-Exile-2-RPC,
  search result only, ideas only). Not a source.

## 5. Campaign pathing data (static, license-OK)

- The repoe-fork PoE2 export (https://repoe-fork.github.io/poe2/) has
  `world_areas.json` as its only area file; no quest, quest-state or
  waypoint file. The cached snapshot (decision 0020: build-time,
  attributed, never bundled) holds 448 areas with `act`, `area_level`,
  `connections` (the area graph), `has_waypoint`, `is_town`,
  `parent_town`, `bosses` (monster ids), `topologies` (the layout graph
  variants a zone picks from; G1_1 lists 5), `loading_screens`, `packs`,
  `tags` (read from the local cache 2026-11-17).
- Quest rewards / permanent bonuses: poe2wiki "List of quest rewards"
  (https://www.poe2wiki.net/wiki/List_of_quest_rewards, flagged as needing
  an update; search summary) and guides (Mobalytics 0.5 checklist,
  https://mobalytics.gg/poe-2/guides/0-5-campaign-checklist-stats-rewards-skillpoints-and-more,
  search summary) disagree on totals. Wiki / poe2db are CC BY-NC-SA: link
  out, facts in own words only (research 0005). GGG Data Exports cover
  only the passive tree (research 0018).
- Once OAuth exists, `passives.quest_stats` (PoE2 only) shows which quest
  passives the character already has: a verified missed-reward check.
- "Optimal pathing" without screen capture (each instance picks a random
  layout from a fixed variant set): realistically (a) zone order and the
  shortest route from the `connections` graph, (b) next waypoint and
  town, (c) which zones hold a boss or reward worth the detour (own
  authored notes plus `bosses`), (d) own-words per-zone layout tips
  ("exit usually opposite the entrance", "follow the road") labelled as
  tips, (e) level vs area level pace (HUD-ACT). No live minimap or
  per-instance route: that needs continuous screen reading, which the
  floor forbids.

## 6. Verdict

- Usable under the floor: GGG API public OAuth client (PKCE, loopback
  redirect, `account:profile` + `account:characters`, optional
  `account:leagues`) giving PoE2 equipment, jewels, skills, passives,
  weapon-set specialisations and quest passives; NOT the backpack.
  Blocked until GGG reopens registration (operator act). Static:
  repoe-fork world_areas (already cached).
- Not usable: poe.ninja builds / character, character-window, POESESSID,
  Steam rich presence, game folders other than Client.txt, continuous
  screen or clipboard reads.

## Sources

- https://www.pathofexile.com/developer/docs (accessed 2026-11-17)
- https://www.pathofexile.com/developer/docs/index (accessed 2026-11-17)
- https://www.pathofexile.com/developer/docs/authorization (accessed 2026-11-17)
- https://www.pathofexile.com/developer/docs/reference (accessed 2026-11-17)
- https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Classes/PoEAPI.lua (accessed 2026-11-17)
- https://poe.ninja/docs/api (accessed 2026-11-17)
- https://partner.steamgames.com/doc/features/enhancedrichpresence (accessed 2026-11-17)
- https://github.com/ezbooz/Path-Of-Exile-2-RPC (search result only, accessed 2026-11-17)
- https://repoe-fork.github.io/poe2/ (accessed 2026-11-17)
- https://www.poe2wiki.net/wiki/List_of_quest_rewards (search summary, accessed 2026-11-17)
- https://mobalytics.gg/poe-2/guides/0-5-campaign-checklist-stats-rewards-skillpoints-and-more (search summary, accessed 2026-11-17)
