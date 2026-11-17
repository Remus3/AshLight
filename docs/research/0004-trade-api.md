# PoE2 trade API and rate limits

Research date: 2026-11-16. Items without a fetched source are marked UNVERIFIED.

## Endpoints used by tools for PoE2 (unofficial trade site API)

Status: these are the website's own endpoints, not part of the official documented API. The official docs say only documented resources may be accessed and reverse-engineering undocumented endpoints is prohibited (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16). poedb itself calls the website API (POESESSID based) "not officially supported" (https://poedb.tw/Developer_API) (accessed 2026-11-16).

Shape, as implemented by the third-party crate poe2-agent (license UNVERIFIED, not shown on the page; no code copied) (https://docs.rs/crate/poe2-agent/0.5.0/source/src/trade.rs) (accessed 2026-11-16):
- POST https://www.pathofexile.com/api/trade2/search/poe2/<league>: body has a top-level "query" object (status, optional name, type, filters, stats groups) and a "sort" object. Response: id, total, result (array of hashes), optional error {code, message}.
- GET /api/trade2/fetch/<hashes>?query=<search id>: up to 10 hashes per call. Response: result array; each has listing (optional price amount + currency) and item (name, typeLine, baseType, ilvl, frameType, implicit/explicit mods).
- POST /api/trade2/exchange/poe2/<league>: body "query" with status online, "have" and "want" arrays, plus sort and engine "new". Response: result map; each entry has listing.offers with exchange and item sides (currency, amount) and item stock; plus total and optional error.
- GET /api/trade2/data/leagues: result array of {id, realm, text}.
- GET /api/trade2/data/stats: result array of groups, each with label and entries {id, text, type}. Fetch once and cache.
- /api/trade2/data/items, /data/static, /data/filters: UNVERIFIED in this research (no source fetched). Treat as static metadata endpoints to be cached; confirm by observing the trade site's own network traffic.
- A 2018 staff post says searches and exchange queries share one rate-limit policy (https://pathofexile.com/forum/view-thread/2079853/filter-account-type/staff) (accessed 2026-11-16). That post predates PoE2; whether it still holds is UNVERIFIED.

## Rate limit headers

Official definition (https://www.pathofexile.com/developer/docs/index) (accessed 2026-11-16):
- X-Rate-Limit-Policy: the policy applying to the request; endpoints may share a policy.
- X-Rate-Limit-Rules: comma-separated rule names (for example ip, account, client); names the per-rule headers to read.
- X-Rate-Limit-<rule>: "max hits:period seconds:restriction seconds".
- X-Rate-Limit-<rule>-State: "current hits:period seconds:active restriction seconds" (0 when not limited).
- Retry-After: seconds until the limit expires, on 429 responses.
- Exceeding a limit returns HTTP 429; frequent violation can get an application's access revoked (same source). Too many invalid 4xx responses can also restrict access (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16). Limits "can change at any time" (same).

Observed values (all dated or secondhand; treat as examples only):
- A forum post quotes x-rate-limit-ip "20:5:60" with state "2:5:0" (format hits:period:restriction); old PoE1 era (https://pathofexile.com/forum/view-thread/2079853/filter-account-type/staff) (accessed 2026-11-16).
- A forum thread about trade websocket live search shows X-Rate-Limit-Ip 15:60:60,30:60:300,45:120:3600 under policy trade-websocket-request-limit (via search summary of https://de.pathofexile.com/forum/view-thread/3848810/page/3) (accessed 2026-11-16). Page itself not read: UNVERIFIED.
- A roughly 2019 forum thread listed trade-search-request-limit as 5 per 12 s, 15 per 62 s, 30 per 302 s and trade-fetch-request-limit as 12 per 6 s, 16 per 14 s (via search summary of https://www.pathofexile.com/forum/view-thread/3056323) (accessed 2026-11-16). Probably stale; no current PoE2 search/fetch numbers were found. Current typical values: UNVERIFIED. Measure with a live request.
- Several rules in one header are normal (multiple windows with escalating restriction times, e.g. 60 s, 300 s, 3600 s in the websocket example above).

Violation behavior: a 2018 staff post says exceeding 20 requests in 5 seconds gave a 60-second restriction (https://pathofexile.com/forum/view-thread/2079853/filter-account-type/staff) (accessed 2026-11-16). Escalating restriction times across windows are visible in the websocket example above. Whether repeated violations lengthen restrictions beyond the configured tiers: UNVERIFIED.

429 handling by a reference client: read retry-after in seconds, default 60 if missing (poe2-agent, license UNVERIFIED) (https://docs.rs/crate/poe2-agent/0.5.0/source/src/trade.rs) (accessed 2026-11-16).

## Official developer docs (OAuth, User-Agent, policy)

Source: https://www.pathofexile.com/developer/docs (accessed 2026-11-16).
- OAuth 2.1. New application registration is currently closed.
- User-Agent is mandatory: "OAuth {$clientId}/{$version} (contact: {$contact}) ..." with optional text after. Example in https://www.pathofexile.com/developer/docs/index (accessed 2026-11-16).
- Policy: websites and web apps are the safest; standalone executables are permitted but discouraged and must use a public OAuth client.
- Reading screen, clipboard or log data is allowed only if the user knows what is being done and only once per manual key press. This is the clause most relevant to a Client.txt reader.
- Apps that interact with the game or its files result in account termination (same page).
- Required visible notice: "This product isn't affiliated with or endorsed by Grinding Gear Games in any way."
- Apps must not use GGG IP to generate commercial revenue.
- No uptime guarantee; details may change without notice.

Official PoE2-capable endpoints (https://www.pathofexile.com/developer/docs/reference) (accessed 2026-11-16):
- GET /league, /league/<league>: realms pc (default), xbox, sony, poe2; scope service:leagues; limit max 50.
- GET /league/<league>/ladder: realm poe2 allowed; scope service:leagues:ladder; PoE2 ladder holds top 1,000 entries; limit max 500.
- Currency Exchange: GET https://web.poecdn.com/api/currency-exchange[/<realm>][/<id>]; realm xbox, sony or poe2; no scope listed (public); id is a unix timestamp; response has next_change_id and markets (league, market_id, market_pair, volume_traded, lowest/highest stock and ratio). Hourly, historical only (no current-hour data).
- Several sections (stashes, public stashes, account leagues) are PoE1 only (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16).
- Whether the public currency-exchange feed needs an OAuth token in practice: UNVERIFIED (reference lists no scope); still send the required User-Agent.

## POESESSID

- The trade site switches tracking from IP to account when a session id is sent; same limits, but the per-IP allowance is double (2018 staff post) (https://pathofexile.com/forum/view-thread/2079853/filter-account-type/staff) (accessed 2026-11-16). The cookie is a rate-limit tool but also an account credential.
- poedb marks POESESSID-based APIs "not officially supported" (https://poedb.tw/Developer_API) (accessed 2026-11-16).
- A forum thread title states "Do not share POESESSID values with other people" (https://webcdn.pathofexile.com/forum/view-thread/3328601) (accessed 2026-11-16); content not read.
- Recommendation: the app must work with no cookie. poe2-agent sends only a User-Agent per the source above; whether anonymous trade2 requests are currently throttled harder: UNVERIFIED. Never store or log a cookie.

## Best practice (design guidance)

- Parse X-Rate-Limit-* on every response and rebuild the token bucket per policy; never hard-code numbers (official docs: limits change at any time).
- One global request queue per policy; serialize search then fetch; batch fetch at 10 ids.
- On 429: stop all requests for that policy, wait Retry-After (fallback 60 s), then resume slowly.
- Keep headroom (stay one hit under the max of the tightest window) because state headers lag concurrent requests.
- Cache static data (stats, leagues) for the session or the patch; cache search results briefly.
- Avoid 4xx: validate queries locally against cached stat ids.

## Design consequences

- Treat the trade2 API as an unofficial, best-effort dependency behind an adapter; the official developer policy forbids undocumented endpoints, so ship price check as opt-in and document the risk. Official supported price signals are limited to the currency-exchange feed (hourly, historical).
- Prefer poe.ninja exchange data for bulk prices (see data-sources.md); use trade2 only for on-demand single-item checks.
- Send a descriptive User-Agent in the official format even for unofficial calls.
- Show the non-affiliation notice in the About dialog.
- Do not require POESESSID; if an optional power-user setting is ever added, keep it in the OS credential store.
- The rate limiter must be data-driven and surface "waiting N s" in the UI.
- Measure real search/fetch limits at development time by logging headers; record them in docs as observed, dated values.

## Sources

- https://www.pathofexile.com/developer/docs (accessed 2026-11-16)
- https://www.pathofexile.com/developer/docs/index (accessed 2026-11-16)
- https://www.pathofexile.com/developer/docs/reference (accessed 2026-11-16)
- https://pathofexile.com/forum/view-thread/2079853/filter-account-type/staff (accessed 2026-11-16)
- https://docs.rs/crate/poe2-agent/0.5.0/source/src/trade.rs (accessed 2026-11-16; license UNVERIFIED)
- https://de.pathofexile.com/forum/view-thread/3848810/page/3 (accessed 2026-11-16; via search summary)
- https://www.pathofexile.com/forum/view-thread/3056323 (accessed 2026-11-16; via search summary)
- https://webcdn.pathofexile.com/forum/view-thread/3328601 (accessed 2026-11-16; title only)
- https://poedb.tw/Developer_API (accessed 2026-11-16)
