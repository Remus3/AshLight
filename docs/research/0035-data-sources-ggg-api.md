# 0035 - Data sources: GGG developer platform (OAuth, API Reference, Data Exports)

Date: 2026-11-17. For the ultraplan (docs/plan/README.md), dimension B1
permitted data sources (GGG platform). Scope: what GGG's developer platform
offers a local PoE2 desktop tool today, a claim-by-claim re-check of
research 0033, and what TC-OAUTH-REG, TC-IMPORT and TC-CURX can be. Only
documentation pages were read; no API endpoint was called.
Status: draft

## Sources (all accessed 2026-11-17)

Each D- page was read from the docs watch cache
(`<sidecar>\Cache\ggg_docs\pages\*.txt`, written 2026-11-18T02:06:44Z, which
is 20:06 local on 2026-11-17); D-IDX, D-AUTH and D-LOG were re-read live at
about 23:30 local and matched the cache.

- D-IDX: https://www.pathofexile.com/developer/docs (policy, errors, limits)
- D-AUTH: https://www.pathofexile.com/developer/docs/authorization
- D-REF: https://www.pathofexile.com/developer/docs/reference
- D-LOG: https://www.pathofexile.com/developer/docs/changelog
- D-DATA: https://www.pathofexile.com/developer/docs/data
- D-GAME: https://www.pathofexile.com/developer/docs/game
- TOU: https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy
- ROBOTS: https://www.pathofexile.com/robots.txt
- ARCH: 40 archived copies of D-IDX, 2024-01-16 to 2026-11-03, at
  https://web.archive.org/web/<stamp>/https://www.pathofexile.com/developer/docs
- TREE: https://github.com/grindinggear/poe2-skilltree-export and its public
  feeds `commits/main.atom`, `tags.atom`, `releases.atom`
- F-REG: https://www.pathofexile.com/forum/view-thread/3683605
- POB-API, POB-SRV, POB-IMP: `src/Classes/PoEAPI.lua`, `src/LaunchServer.lua`
  and `src/Classes/ImportTab.lua` under
  https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/
  (MIT project; read for behaviour only, nothing copied)
- NINJA: https://poe.ninja/docs/api
- REPOE: https://repoe-fork.github.io/poe2/
- STEAM: https://partner.steamgames.com/doc/features/enhancedrichpresence
- RFC8252: https://www.rfc-editor.org/rfc/rfc8252.txt
- EA-DATE (search summary only):
  https://gamesradar.com/games/action-rpg/path-of-exile-2-release-date-time-full-early-access
- Local, read 2026-11-17: the watch state `<sidecar>\Cache\ggg_docs\state.json`;
  the snapshot manifest `<sidecar>\Cache\gamedata\manifest.json`; a throwaway
  probe that fed `charjson` the item shape D-REF documents (sidecar Scratch
  folder, not committed); git history (commits 31e4ea4, 5f0e866).

## Summary

- Registration is closed, with no channel listed. It is the second
  closure since 2024; the first ended 4 to 6 weeks after a major launch,
  so a reopening some weeks after 1.0 is plausible (our inference).
- A desktop tool gets a public client only: PKCE, a registered loopback
  redirect, access 10 h, refresh 7 days with no extension. Best case: one
  browser approval per 7 days, not ROADMAP's "one sign-in ever".
- PoE2 data for a public client: own characters (gear, skills, passives;
  no backpack or stash), account leagues, item filters, public Currency
  Exchange history. The tree export is live, unlicensed, fetch-only.
- Research 0033 holds (23 claims: 17 true, 2 incomplete, 4 unverifiable,
  0 changed). Fixable now: `charjson` drops every implicit and explicit
  mod of an item in today's documented shape (R1); then R2, R3, R4.

## Current state

- Docs watch (decision 0044): `tools/ggg_docs_watch.py` reads six pages
  once per 24 h (:47-51), reads registration as closed while the index
  carries one fixed sentence (:58, :217-226), keeps the section text and
  any mail or form channel (:436-456) and tags diffs with eight topics
  (:68-78). The loop tick calls it before the HALT check
  (`tools/al_loop.py:1547`). State today: 6 of 6 pages read, registration
  closed, newest changelog entry 3.30.0, no diff written yet, no REG_OPEN
  flag. The flag would show as a developer note in the Checks view
  (`server/al/core.py:902-910`, `server/al/diag.py:214-223`).
- Provider seam (decision 0045): `GggApiProvider` is a stub that reports
  "not set up" and raises NotConfigured
  (`server/al/theorycraft/providers.py:59-85`). `BuildStore.import_from`
  would load its answer like a paste (`server/al/theorycraft/store.py:315-323`)
  and the snapshot lists the providers (`store.py:349`), but no file under
  `web/` reads that list (grep 2026-11-17). A test pins `providers.py` to
  no network import and no URL text (`tests/test_build_live.py:291-302`).
- Mapping layer: `server/al/theorycraft/charjson.py` turns a pasted
  character object in GGG's Character / Item shape into PoB build XML
  (:189-239). Only a paste feeds it today (decision 0004 item 4).
- Outbound HTTP: `server/al/webfetch.py` is the one path: https only, host
  allowlist, cookie refused (:183-210), User-Agent
  `AshLight/<version> (...) (contact: ...)` (:73-79), 2 MiB default cap
  (:32). No rate-limit header parser is in the tree: the header-driven
  limiter of commit 31e4ea4 (`server/al/trade.py`, about 130 lines, with
  a 213-line test file) left in 5f0e866 with decision 0017.
- Ports: block 8960-8979, core 8960 (`server/al/ports.py:6-9`); see R2.
- Tree export: fetched at build time from the `main` branch of TREE
  (`server/al/theorycraft/snapshot.py:66-67`), only with web_data on and a
  contact set (`:43`, `:52-55`), at most once per 24 h (`:57`).
- Open rows: TC-OAUTH-REG (`ROADMAP.md:274-279`), TC-IMPORT
  (`ROADMAP.md:280-284`), TC-CURX (`ROADMAP.md:618-624`); hand-off
  `AL-NEXT-SESSION.txt:33-40`.

## Findings

### F1 - Registration is closed; it has closed and reopened before
D-IDX (cache and live): the registration section states that GGG is unable
to process new applications at present and that applications an account
already owns are managed from a profile link. No mail address, form or
other channel is on the page (watch state: 0 forms, 0 mail links).

ARCH, 40 archived copies of that page:
- open, by mail to an OAuth address: 5 copies, 2024-01-16 to 2024-09-09;
- closed: 10 copies, 2024-09-29 to 2025-01-03;
- open, by mail: 19 copies, 2025-01-20 to 2026-07-02;
- closed: 6 copies, 2026-07-31 to 2026-11-03, and today.

The first closure lasted 96 to 133 days and ended 28 to 45 days after the
PoE2 early access launch (2024-12-06, EA-DATE). The current one began
between 2026-07-02 and 2026-07-31 (docs entry 3.29.0 is dated 21/07/2026,
D-LOG) and is 109 to 138 days old. If GGG repeats the pattern around 1.0,
the page reopens between about 2027-01-08 and 2027-01-25: our inference,
not a GGG statement. Why it matters: the operator act is probably weeks
away, so R1 to R4 can be finished first. A staff reply to a registration
question in January 2025 gave only the general tool warning (F-REG): the
docs page is the one reliable signal, and the watch reads it.

### F2 - What an application contained when registration was open
ARCH (2024-01-16, 2025-01-24): GGG handled registration itself, at its
discretion, from a mail that had to state: the PoE account name, the
application name, the client type, the grant types, each scope wanted and
why, and a redirect URI (https on an owned domain for a confidential
client, a local one for a public client). The page called such requests
low priority and slow around league launches. In January 2025 it also said
requests for PoE2 game data would be rejected because no PoE2 API existed;
D-REF now says a limited set exists. Today's page lists nothing, so the
channel at reopening is unknown until the watch captures it.

### F3 - Public client rules (D-AUTH, D-IDX)
- A standalone executable is permitted, not encouraged, and must use a
  public OAuth client when it talks to the APIs (D-IDX).
- Grant: Authorization Code with PKCE only, `code_challenge_method` S256,
  a verifier with at least 32 bytes of entropy. No `service:*` scope.
- Redirect: a local URI (the page's example is a 127.0.0.1 address with a
  port and a path). The `redirect_uri` sent must match the client's
  registered URI. No port rule is stated, so a port in 8960-8979 is
  admissible, but it is fixed at registration.
- The authorization code lives 30 seconds. Tokens: access 10 hours,
  refresh 7 days (confidential clients: 28 and 90 days).
- Rate limits are shared between all public clients. The consent page
  warns the user that the request cannot be verified.
- The token answer carries `username` and `sub` next to the tokens.
- Users review and revoke tokens on their profile page; the revoke
  endpoint needs `oauth:revoke`, which is not a scope a client can ask for.
- Guidelines: no credentials in code or in a distributed binary; one
  product per registered application.

Practice (POB-API, POB-SRV): PoB-PoE2 uses its own client id, S256, a
`localhost` redirect on three fixed ports (49082 to 49084, tried in
order) and a 60 s wait. That suggests GGG matches the port and accepts
several registered URIs (inference). RFC8252 section 8.3 prefers the IP
literal over `localhost`; section 8.12 forbids an embedded web view.

### F4 - "One sign-in ever" is impossible: the 7-day ceiling
D-AUTH, Refresh Token Grant: each refresh returns a new refresh token, the
used one expires at once, and the new one inherits the old expiry; the
lifetime cannot be extended. For a public client that is 7 days, so the
player must approve again in the browser every 7 days at the latest.
`ROADMAP.md:284` promises one sign-in ever and silent refresh after that.

D-AUTH, Managing Tokens, adds that refresh tokens must be stored securely
on a server and can be switched off for an application whose flow cannot
do that. A desktop tool has no server. Read literally, GGG may grant no
refresh token; then a session lasts 10 hours and every play day starts
with an approval. PoB-PoE2 keeps a refresh token in its local settings
(POB-API), so the practice exists. R2 asks GGG. Why it matters: a lapsed
grant is the normal case, not an error; the last import must stay usable
(it is saved as the character's build file, decision 0045) and the
reconnect prompt must never interrupt play.

### F5 - Scopes: one needed, one optional, `account:profile` not needed
D-AUTH lists `account:profile`, `account:leagues`, `account:stashes`,
`account:characters`, `account:league_accounts`, `account:item_filter`.
- `account:characters` covers both character endpoints: all of TC-IMPORT.
- `account:profile` (uuid, name, locale, twitch link, D-REF) adds nothing:
  the token answer already names the account. ROADMAP and decision 0004
  item 4 ask for it; dropping it means less data and a shorter consent.
- `account:item_filter` creates and updates an account filter for realm
  `poe2`, with optional validation against the current game version
  (D-REF). Research 0022 section 3 and decision 0031 already say this
  upload is added once a client exists. Scopes are fixed at registration,
  so it belongs in the first request.
- `account:leagues` is not needed: each character carries its `league`.
- Scopes are named per authorisation request, so the import sign-in can
  ask for `account:characters` alone.

### F6 - Which endpoints serve PoE2 today (D-REF, D-AUTH, D-LOG)
Base https://api.pathofexile.com. D-REF opens with a note that only a
limited set of APIs returns PoE2 data. Reachable by a public client:
- `GET /character/poe2` and `GET /character/poe2/<name>`
  (`account:characters`): the account's own characters only.
- `GET /account/leagues/poe2` (`account:leagues`): documented as enabled
  for PoE2 in entry 3.30.0 (12/11/2026).
- `GET /profile` (`account:profile`): not game specific.
- `GET` and `POST /item-filter[/<id>]` (`account:item_filter`).
- `GET https://web.poecdn.com/api/currency-exchange/poe2[/<id>]`: marked
  Public API, hourly history (F11).

PoE2 capable but out of reach (service scopes need a confidential client
and the client-credentials grant): `GET /league`, `GET /league/<league>`
(`service:leagues`) and `GET /league/<league>/ladder`
(`service:leagues:ladder`; top 1000 for PoE2, at most 500 per call,
enabled in entry 0.5.0 of 26/05/2026). PoE1 only: event ladders, PvP,
Account Stashes, League Accounts (atlas trees), Guild Stashes and Public
Stashes.

### F7 - Fields returned for a PoE2 character (D-REF)
Character: `id`, `name`, `realm`, `class`, `league`, `level`, `experience`,
flags `expired` / `deleted` / `current`, `equipment`, `jewels`, `skills`
(PoE2 only), `passives`, `metadata.version` (the realm's game version).
`inventory` and `rucksack` are PoE1 only; entry 3.27.0 (28/10/2025) says
the PoE2 endpoint stopped returning unequipped items. No backpack.

`passives`: `hashes`; `specialisations` with keys `set1`, `set2`, `set3`
(PoE2 only); `skill_overrides` (keyed by the node replaced); `jewel_data`
(keyed by the jewel's `x`); `quest_stats` (PoE2 only, strings, passives
granted by quests; added in entry 0.4.0 of 10/12/2025).

Item fields a build import needs: `inventoryId`, `x`, `rarity`, `name`,
`typeLine`, `baseType`, `ilvl`, `corrupted`, `sanctified`, `properties`,
`sockets`, `socketedItems`, `enchantMods`, `runeMods`, `bondedMods`,
`implicitMods`, `explicitMods`, `grantedSkills`, `support`, `gemSkill`.

Shape changes that matter:
- Entry 3.29.0 (21/07/2026): `implicitMods` and `explicitMods` became
  arrays of ItemMod objects (`description` plus `flags` such as fractured,
  crafted, desecrated); `craftedMods`, `fracturedMods`, `mutatedMods` and
  `desecratedMods` were removed.
- Entry 0.5.0: `frameType` is deprecated for `frameTypeId`, a string whose
  values D-REF does not list.

Extra value: `current` may name the character being played at start
(decision 0045 lists the official API as a possible better key);
`league` can pin the price league; `metadata.version` is a no-click
patch detector; `quest_stats` could confirm campaign rewards the zone
guide only assumes (decision 0043). The meaning of `current` and the
text of `quest_stats` are UNVERIFIED until a real answer is seen.

### F8 - Rate limits, invalid requests and the User-Agent (D-IDX)
- Limits are dynamic; an application must parse and follow
  `X-Rate-Limit-Policy`, `X-Rate-Limit-Rules` (rule names such as ip,
  account, client), `X-Rate-Limit-<rule>` (max hits, period, restriction,
  in seconds; several windows), `X-Rate-Limit-<rule>-State` and
  `Retry-After` on a 429. Frequent breaches cost the application access.
- Too many 4xx answers in a short time (401, 403 and 429 count) restrict
  the application or user. A client must refresh before the access token
  expires, take character names from the list call and never retry inside
  a restriction.
- Errors: `{"error": {"code", "message"}}` with codes 0 to 10; act on the
  code. OAuth endpoints answer in the RFC form.
- User-Agent: every application that uses the API sends a header starting
  `OAuth <clientId>/<version> (contact: <contact>)`; free text may follow.
  `webfetch.user_agent` cannot produce that prefix
  (`server/al/webfetch.py:73-79`), and its contact is the install's own
  (decision 0015) while GGG's is meant to reach the application's owner.
- No numbers are documented. POB-API expects two PoE2 policies,
  `character-list-request-limit-poe2` and `character-request-limit-poe2`;
  we have seen neither (no call made).
- `webfetch.request` hands every header to each redirect hop
  (`server/al/webfetch.py:198`). A bearer token must never travel that
  way: the API call needs a one-host allowlist and no redirect.

### F9 - The character reader is behind the documented shape (defect)
Probe, 2026-11-17: an item in today's documented shape (ItemMod objects in
`implicitMods` / `explicitMods`, plus `bondedMods` and `runeMods`) left
`charjson.item_text` with the rune mod only. Cause:
`server/al/theorycraft/charjson.py:134-137` keeps a mod only when it is a
string, and `MOD_FIELDS` (:63-64) lists four fields GGG removed and omits
`bondedMods`. The fixture uses the old string form
(`tests/tc_fixtures.py:123-124`), so the tests pass.

Lesser gaps from the same probe:
- `set1` / `set2` nodes are merged into one node list (:153-164), so PoB
  counts both weapon sets as always active.
- `skill_overrides`, `jewel_data` and `quest_stats` are ignored.
- `class`: a display name maps to its base class (:39-50), an internal id
  such as `Monk2` passes through as the class name. POB-IMP maps internal
  ascendancy ids to names first, so the API may send either form.
- `Flask` items map to `Flask <x+1>` (:167-174); POB-IMP treats Flask
  positions above 1 as charms. Jewels are not placed (:21).
- Rarity falls back to the deprecated `frameType` (:110-115).

D-REF gives types, not values, for `inventoryId`, `frameTypeId`, `class`
and the `quest_stats` strings; POB-IMP is the only public evidence
(inventory ids Weapon, Offhand, Weapon2, Offhand2, Helm, BodyArmour,
Gloves, Boots, Amulet, Ring, Ring2, Ring3, Belt, Flask, PassiveJewels):
PoB's observations, not GGG documentation. A real sample is within reach
with no call by AshLight: POB-API writes each successful API answer to a
local file in PoB's folder (dev branch; the pinned release is
UNVERIFIED), and the existing JSON paste accepts that text.

Why it matters: a player who pastes a current-shape character today gets
a build whose items have no mods, so every delta, weight and upgrade
notice for it is silently wrong. It is also the layer TC-IMPORT stands on.

### F10 - Data Exports: the PoE2 passive tree (D-DATA, TREE, D-REF)
- Status: D-DATA says GGG gives no official access to game data outside
  its APIs, with the passive trees as the exception; for PoE2 that is TREE
  (`data.json`, `assets/`, a short README pointing at the developer docs).
- Licence: none. No LICENSE file, no licence shown by the host. Decision
  0009 (fetch only, never bundle, credit GGG) stays right.
- Cadence: 7 commits, each named for a game version: 0.4.0 and "0.5.0
  Preview" (2026-05-26), "0.5.0 Preview 2" (05-28), 0.5.1 (06-04), 0.5.2
  (06-15), 0.5.4 and 0.5.5 (both 2026-09-04). Nothing since; the live
  patch is 0.5.5f (research 0018). Tags exist for 0.4.0, 0.5.0, 0.5.1 and
  0.5.2 only, so following `main` (`snapshot.py:66-67`) is correct and a
  tag pin would be two versions behind. The preview commits suggest a 1.0
  preview may land before 2026-12-11 (inference).
- On the operator's machine the export is absent: the manifest lists five
  repoe-fork files and no tree, because web_data is on but no contact is
  set (decision 0015 item 2). Tree names, the `.build` passive ids
  (decision 0034) and R7 depend on it.
- Tree URL: D-REF documents the format; version 7 (PoE2 site since 0.5.0)
  is a 4-byte version, class byte, ascendancy byte, 2-byte count, then per
  node a 2-byte hash, 2-byte flags, an optional weapon-set byte (flag bit
  0) and an optional 2-byte override hash (flag bit 1). The page's own
  PoE2 example decodes cleanly: big-endian, version 7, class 10, 5 nodes,
  34 of 34 bytes. The class and ascendancy byte values are not listed.
- Shape and id space: research 0014, 0015, 0027; note 0037 has the rest.

### F11 - Currency Exchange history: public, still blocked for us
D-REF marks the endpoint Public API, D-AUTH's `service:cxapi` line adds
that it can also be reached publicly, and D-LOG entry 3.29.0 says to use
the CDN copy. Fields: `next_change_id` (unix hour) and per market
`league`, `market_id`, `market_pair` (base item ids), `volume_traded`,
`lowest_stock`, `highest_stock`, `lowest_ratio`, `highest_ratio`. History
only: no current hour, and old hours may be removed.

The adjudicator ruling of 2026-11-17 (research 0018 section 3) stands: no
call without an AshLight client. Its reverse condition, a written
exemption, is not met: the two "public" notes say no token is needed, but
they neither lift D-IDX's public-client rule for executables nor say what
User-Agent to send without a client id. One hour file was 1,589,380 bytes
with 1,927 markets (research 0018), 76 percent of the 2 MiB default cap
(`server/al/webfetch.py:32`). Value is low while poe.ninja's hourly
exchange overview is in use (decision 0026).

### F12 - The policy texts that bound a tool
- TOU section 7 (items numbered on the page, cited by letter in the
  docs): 7b no modifying the client or its data, also through third-party
  tools; 7c no automated software or bots against the website or
  services; 7i no reverse engineering; also no other client software and
  no data extraction tools against the website.
- TOU clause 22: GGG may change or remove website APIs at any time; users
  must follow the API Policies (the developer docs) and the call limits
  and must not get around them.
- D-IDX: executables that run apart from the game are allowed under the
  macro rules, the overlay rules (the user knows what is read; screen and
  clipboard once per manual key press), a public OAuth client for API
  use, no commercial revenue from GGG IP, the non-affiliation statement
  and respect for the privacy of players who grant access. GGG may remove
  access without notice. Only the API Reference and the Data Exports are
  supported; tools that touch the game or its files are banned.
- ROBOTS disallows `/api/`, `/search/` and account pages for every agent,
  not `/developer/`: the docs watch stays inside it, so decision 0044's
  reverse condition is not met.
- Research 0001 keeps the verified quotes. Nothing here changes the floor.

### F13 - Research 0033, claim by claim
Still true (17):
1. Registration closed, no channel listed (D-IDX); since July 2026 (F1).
2. Executables need a public client; ToU 7i bars other endpoints (D-IDX).
3. The six account scopes (D-AUTH).
4. The PoE2 note, character endpoints with realm `poe2`, base URL (D-REF).
5. Character fields; no `inventory` / `rucksack`; stashes PoE1 only (D-REF).
6. `/profile`, `/account/leagues`, `/item-filter` accept PoE2 (D-REF).
7. Leagues and ladders need service scopes; the Currency Exchange is
   public, hourly, history only (D-REF, D-AUTH).
8. User-Agent form and rate-limit headers (D-IDX); F8 adds the 4xx rule.
9. No polling rule beyond the headers (D-IDX, D-REF).
10. PoB-PoE2: documented API, own client id, S256, localhost redirect, a
    scope `account:trade` that D-AUTH does not list (POB-API); F3 adds its
    three fixed ports (POB-SRV).
11. poe.ninja's builds, profile and character endpoints: internal (NINJA).
12. GGG names only screen, clipboard and logs as tool inputs (D-IDX).
13. `.build` files are a documented format the game reads (D-GAME).
14. Steam rich presence has no documented read path (STEAM).
15. repoe-fork's only area file is world_areas (REPOE).
16. The cached snapshot holds 448 areas with the listed fields (local).
17. `quest_stats` is documented for PoE2 (D-REF, D-LOG).

True but missing a binding detail (2):
18. Loopback redirect with "no port rule": the URI must equal the
    registered one, so the port is fixed at registration (F3).
19. Token lifetimes: the refresh token cannot be extended (F4), and the
    server-side storage sentence was not recorded.

Unverifiable (4):
20. How stale a character answer is: no documented rule; one search found
    nothing. Measure after registration.
21. The `character-window` endpoints: never called, by design; the policy
    basis for ruling them out stands (D-IDX, TOU).
22. The community presence tool: a search result in 0033, not re-read.
23. Quest reward totals from the wiki and a guide: search summaries in
    0033, outside this dimension (research 0034).

Changed: none. The 0033 verdict stands with F4's correction.

### F14 - What stays impossible even with a client
- The PoE2 backpack, stash, atlas tree and public stash data: no PoE2
  endpoint (F6, F7). The item check keeps its manual press.
- League lists, ladders and other players' characters: service scopes, or
  not offered to an account scope at all.
- A permanent sign-in: 7 days at most per approval (F4).
- Live events or push: the API is a read-only snapshot with no stream and
  no documented freshness (D-IDX).
- Trade data: no documented endpoint; decision 0017 stands.

## Recommendations

No registration needed: R1, R2, R3, R4, R7. Waiting for GGG: R5, R6.

### R1 - Bring `charjson` to the shapes GGG documents today
- Action: accept ItemMod objects as well as strings in `implicitMods` /
  `explicitMods`, read `bondedMods`, keep the removed fields for old
  pastes, map internal class ids through the cached tree export when it is
  there, treat Flask positions above 1 as charms, keep weapon-set
  membership, and add fixtures in both shapes.
- Impact: H. Today a current-shape paste loses every implicit and
  explicit mod (F9); TC-IMPORT stands on this layer.
- Effort: S for the mod fields; M with sets, overrides and class ids.
- Risk: low; parser only, old shape still accepted.
- ToS check: no floor rule touched. No network, no new read; the input is
  text the player pastes (decision 0004 item 4).
- Depends on: nothing. Optional operator act afterwards: paste one real
  answer captured by PoB (F9) so a session can record the real
  `inventoryId` and `class` values; the sample is never committed
  (decision 0038) and the fixture stays synthetic.
- Files likely touched: `server/al/theorycraft/charjson.py`,
  `tests/tc_fixtures.py`, `tests/test_tc_json.py`.
- Acceptance test: a fixture item with ItemMod objects yields its mod
  lines in the item text; the old fixture still passes; internal and
  display class names give the same build.
- ZERO-CLICK: same paste path, no new press.

### R2 - Prepare the application and one decision now
- Action: write the application note (answers to F2's six asks: public
  client; authorization code with PKCE plus refresh; `account:characters`
  and `account:item_filter` with a one-line reason each; redirect URIs
  `http://127.0.0.1:8979/oauth/callback` and the same on 8978; two
  questions for GGG: refresh tokens for a desktop client, and the public
  Currency Exchange endpoint) and a decision record for scopes, ports,
  token store, the User-Agent contact and the 7-day behaviour. Restate
  `ROADMAP.md:284` as "one browser approval per 7 days at most".
- Impact: H. Unblocks three rows; GGG's queue was described as slow, so a
  same-day send matters.
- Effort: S. Risk: GGG may decline or stay closed; preparation is cheap.
- ToS check: documentation only. The application is the path D-IDX
  requires of an executable. No floor rule bent.
- Depends on: the go-public plan (a public repository and a public
  contact make the request credible). The operator's account name is
  never written to a tracked file.
- Files likely touched: `docs/ops/` (new note), `docs/decisions/` (new
  record), `ROADMAP.md`, `AL-NEXT-SESSION.txt`, `server/al/ports.py`
  (two constants).
- Acceptance test: every one of the six asks is answered with no private
  value (leak sweep clean); the decision has a "Reverses if"; the ROADMAP
  line is corrected.
- ZERO-CLICK: the watch raises REG_OPEN by itself; sending is one
  operator act because a registration belongs to the operator's account.

Why ports 8979 and 8978: the core port is movable (`ports.py:28-47`) and
every core call needs the per-start token (`server/al/http.py:189-201`),
which a browser redirect cannot carry, so the redirect needs its own
one-shot listener; test cores fill the block from 8961 upward
(`tests/tc_live_util.py:39-51`) and the runbook uses 8977
(`docs/ops/1.0-launch-runbook.md:91`).

### R3 - Give the docs watch a "shape" topic
- Action: add a topic keyed on the field names the reader uses, so a
  reference or changelog diff that touches them is tagged and the note
  line names the fields.
- Impact: M. The 3.29.0 change matches none of today's eight topics
  (`tools/ggg_docs_watch.py:68-78`); the reader was written against a
  shape already 4 months old and nothing flagged it.
- Effort: S. Risk: none; dev tool, read only. Depends on: nothing.
- ToS check: floor rule "public web data": the same six documentation
  pages at the same cadence (decision 0044), allowed by ROBOTS; they are
  not API endpoints and no API call is made.
- Files likely touched: `tools/ggg_docs_watch.py`,
  `tests/test_ggg_docs_watch.py`.
- Acceptance test: a synthetic reference diff that retypes `explicitMods`
  gets the topic "shape" and a note naming the field.
- ZERO-CLICK: runs on the loop tick, also while HALTed.

### R4 - Build the offline core of a GGG client
- Action: in a module outside `providers.py`, with an injected transport:
  the `OAuth <clientId>/<version>` User-Agent, PKCE and state, the
  authorize URL, token exchange and refresh with the 7-day ceiling kept
  across rotations, the header-driven limiter restored from commit
  31e4ea4, a one-shot 127.0.0.1 listener (state and path checked, closes
  after one hit or 120 s), and a token store in Windows Credential
  Manager through ctypes (already used at `server/al/exepin.py:30`).
  With no client id every call raises NotConfigured.
- Impact: M now, H at approval (only the client id and one live smoke
  test remain). Effort: M.
- Risk: rests on details only GGG's reply settles (port matching, refresh
  on or off); a declined application wastes the day. Depends on: R2.
- ToS check: no request is possible without a client id. Later requests
  go only to hosts in the API Reference, with GGG's User-Agent form and
  headers obeyed dynamically (floor: documented GGG endpoints only,
  truthful User-Agent, no POESESSID). The listener binds 127.0.0.1 on a
  port in the block.
- Files likely touched: new `server/al/gggapi.py`, `server/al/ratelimit.py`,
  `server/al/ports.py`, `server/al/settingsio.py` (NEVER list, :108),
  tests.
- Acceptance test: the verifier and challenge pair in D-AUTH's example
  round-trips (checked here: it does); a refresh never moves the stored
  ceiling; the limiter honours a synthetic header set and Retry-After;
  the listener refuses a wrong state, path or Host; no token shows in the
  state snapshot, a log, the diag report or the settings export.
- ZERO-CLICK: not applicable until wired (R5).

### R5 - TC-IMPORT once a client exists
- Action: a Connect action (web_data on, decision 0013) opens GGG's
  consent page in the system browser (`app/client/window.js:106-115`);
  then fetch on events only: core start, character switch, level-up, a
  town or hideout entry when the last fetch is over 5 minutes old, and a
  Refresh click. One list call per game start. Measure staleness once and
  record it here.
- Impact: H. Ends the export-and-paste loop for the build view, item
  deltas and upgrade notices. Effort: M after R4.
- Risk: limits shared with every public client; staleness unknown; the
  weekly approval. Depends on: TC-OAUTH-REG, R1, R4.
- ToS check: documented endpoints, the player's own account by their
  consent on GGG's page, no POESESSID, no undocumented endpoint, nothing
  sent to the game, headers obeyed.
- Files likely touched: `server/al/theorycraft/providers.py`,
  `server/al/core.py`, the Build tab under `web/`.
- Acceptance test: the mocked-flow tests ROADMAP asks for, one live smoke
  by the operator, and a lapsed grant leaves the last import loaded.
- ZERO-CLICK: no click between approvals; one browser approval per 7 days
  is GGG's limit (F4). A lapse shows the last import with its age and a
  quiet reconnect note on the dashboard, never on the overlay.

### R6 - TC-CURX stays blocked; ask, then build small
- Action: put the question in R2's application. After a yes or a client:
  one request per completed hour while the app runs, immutable-hour
  cache, an 8 MiB cap, names from the cached base_items snapshot.
- Impact: L (F11). Effort: S to M. Risk: large hour files; history may
  be trimmed.
- ToS check: documented in the API Reference; no call until a registered
  client or a written exemption exists (ruling in research 0018).
- Depends on: TC-OAUTH-REG or GGG's written answer; R4.
- Files likely touched: new `server/al/curx.py`, tests.
- Acceptance test: parser tests on a synthetic digest; an hour is never
  requested twice; no request at all while unregistered.
- ZERO-CLICK: background fetch on the hour boundary under web_data.

### R7 - Official tree viewer link (version 7 URL)
- Action: encode the loaded build as a version 7 tree URL and show it as
  a link the player opens in their own browser.
- Impact: L to M (a visual tree with no bundled art). Effort: S.
- Risk: the class and ascendancy byte values are undocumented; check them
  against the tree export before shipping.
- ToS check: a documented format; the app only builds a URL and the
  player opens it (the pattern of decision 0017). No request by the app.
- Depends on: the cached tree export (F10).
- Files likely touched: new `server/al/theorycraft/treeurl.py`, the build
  view, tests.
- Acceptance test: decoding D-REF's PoE2 example gives version 7, class
  10, 5 nodes and no bytes left; encode(decode(x)) equals x.
- ZERO-CLICK: the link is always ready; one click opens the browser.

## Cut or merge

- Cut `account:profile` from the scope request (F5).
- Merge TC-OAUTH-REG and R2 into one row with one operator act.
- Merge TC-CURX into the GGG client work (R4) as a late, low-value
  follow-on; cut it if poe.ninja's exchange data stays sufficient.
- Keep the BUILD-LIVE stale-build alert for paste users; mute it while a
  grant is live.
- Decision 0044 lets the watch shrink to the changelog once registration
  is done. Keep all six pages: shape and lifetime changes matter more
  once a client is live.

## Rejected

- Another application's client id (PoB's): an untruthful User-Agent,
  barred by decision 0004 item 4.
- `character-window`, profile page scraping, a POESESSID cookie, or any
  other route to the PoE2 backpack or stash (trade site, memory,
  packets): the floor and ToU 7i.
- Calling the Currency Exchange endpoint now, with a plain or an invented
  `OAuth` User-Agent: against the ruling in research 0018.
- A confidential client behind a hosted backend, for service scopes and
  longer tokens: D-IDX wants a public client for an executable, there is
  no backend, and LAN access stays off.
- An embedded web view for the sign-in (RFC8252 section 8.12; the
  password would pass through the app) or an automated consent click
  (ToU 7c; the approval must be the player's own act).
- A timer that polls the character every few seconds: shared limits and
  the invalid-request rule; events are enough.
- Tokens in `config/local.json`, a log or the settings export.
- Applying through the old mail channel or support while D-IDX says
  closed and names no channel.
- Bundling the tree export: no licence, decision 0009.

## Open questions

1. For GGG's reply (R2): does it match the loopback port exactly and
   accept two registered URIs; does a desktop public client get refresh
   tokens (F4); may an unregistered tool call the public Currency Exchange
   endpoint with a plain truthful User-Agent?
2. To measure after registration: how stale a character answer is, the
   real limits, and whether the consent page is skipped for a returning
   user (it decides how heavy the weekly approval is). All UNVERIFIED.
3. Which contact goes into the `OAuth` User-Agent of a public release: a
   project mailbox or the repository address? Decisions 0015 / 0016 keep
   personal contacts out of tracked files. OPERATOR decision.
4. Decision 0015 item 2 gates the tree export on a contact, but that file
   is served by a code host, not by GGG's API, and D-IDX's User-Agent rule
   speaks of applications that use the API. The decision's reverse
   condition (GGG drops the contact ask) is not met, so no reversal is
   recommended here; an ADJUDICATOR or the operator may rule on the gate's
   scope, or operator act (g) in the hand-off (set the contact) ends it.
5. May AshLight read PoB's local API answer file by itself (a new read
   source)? Needs an ADJUDICATOR; note 0037 owns PoB interop.
6. The form of `class`, the `inventoryId` values and the `quest_stats`
   strings on a live answer (F9): R1's optional paste or the first call.

No adjudicator was needed for this note.
