# 0036 - poe.ninja as the PoE2 price source: contract, drift, watch design

Date: 2026-11-17. For the ultraplan (docs/plan/README.md), dimension B1
permitted data sources (poe.ninja). Scope: every poe.ninja request AshLight
makes, what poe.ninja asks of API consumers, what PoE2 1.0 (2026-12-11)
will change, alternatives, and the shape-watch input for note 0058.
Extends 0013 and 0019 (their live shape samples are not repeated here).
Status: draft

## Sources (all accessed 2026-11-17)

- ND: https://poe.ninja/docs/api - the API reference. The whole page text
  was read from the raw HTML (96,862 bytes, server rendered, no `<main>`
  element; `Cache-Control: public, max-age=600`, served through Cloudflare).
- WV: the responses research 0013 saved on 2026-11-17 under
  `<sidecar>\Scratch\wv` (league list, two Currency overviews, their
  headers, one 304, the docs page). Read locally; no new request.
- NF: https://poe.ninja/docs - Docs and FAQ index: 12 topics, the API
  reference is the only API page; "Data dumps" links to /poe1/data.
- NP: https://poe.ninja/posts/poe2-unique-items - poe.ninja's post on PoE2
  unique items in the economy section (dated Thu May 14, year not shown;
  2026 inferred: it speaks of the coming 0.5 launch, which research 0013
  dates 2026-05-29).
- NB: https://poe.ninja/poe2/builds - the PoE2 builds section (exists);
  NL: https://poe.ninja/docs/character-not-listed-poe2 - its data comes
  from GGG's ladder API.
- NE: https://poe.ninja/poe2/economy - its Economy link carries the league
  slug `forbiddenrites`. https://poe.ninja/poe2/data gave 404 (no PoE2
  data dumps) and https://poe.ninja/posts gave 502 (no posts index read).
- CN: a community poe.ninja API notes repository, README dated October 2025
  (its URL is entry 2 of the Sources list in
  docs/research/0005-data-sources.md; raw README read 2026-11-17; no
  license; third party, so every claim from it reads "reported").
- PS: https://poe2scout.com/ ; PSR: https://github.com/poe2scout/poe2scout
  (README, MIT); PSA: https://api.poe2scout.com/swagger and its OpenAPI
  document https://api.poe2scout.com/openapi/v1.json (62,797 bytes, title
  Poe2scout.Api, 20 GET paths).
- PW: https://poe.watch/ - navigation shows PoE1 sections only.
- GH1: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
- GH2: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- PV1: https://www.poe-vault.com/poe2/news/conquerors-of-wraeclast-explained-path-of-exile-2s-1-0-league-has-you-raise-an-army
- PV2: https://www.poe-vault.com/poe2/news/your-path-of-exile-early-access-characters-survive-1-0-but-they-will-never-reach-standard
- Repo: research 0013, 0018, 0019, 0021, 0033; decisions 0013, 0015, 0016,
  0017, 0026; server/al/ (ninja.py, pricebook.py, webfetch.py, price.py,
  core.py, http.py, state.py, diag.py, __main__.py), web/app.js,
  web/prices.js, app/client/window.js and the two price test files.
- No poe.ninja API endpoint was called for this note. Local facts (the
  key names of config/local.json, the sidecar Cache listing) were read
  2026-11-17.

## Summary

- Contract: 3 documented route families, 24 URL shapes (league list, 14
  exchange types, 9 unique types); at most 23 GETs an hour, 556 a day per
  install, behind the opt-in and a contact. Nothing formal backs it: one
  docs page, use tolerated, no SLA, no numeric limit, blocking for
  excess, and a request that desktop apps go through a backend (F1, F2).
- Worst findings: the price path has never run on the operator's machine
  (no contact, and the UI says values are coming; F3); prices refresh
  only while the dashboard is visible (F4); a field rename empties the
  cache silently (F5); the 1.0 league can take 6 h to be seen (F6).
- PoE2 builds API: closed, rejected (F10). Fallbacks checked: poe2scout,
  GGG Currency Exchange (blocked on OAuth), a project mirror (F11).
- 12 ranked recommendations; a three-layer shape watch for note 0058.

## Current state

### Contract (as lines)

- C1 leagues. `GET https://poe.ninja/poe2/api/economy/leagues`, no
  parameter, no If-None-Match (ninja.py:196). Read: the first entry's
  `id`, else `name`, cut to 80 characters (ninja.py:78-88). Cadence: every
  6 h (ninja.py:57), hourly after a 404 or an empty Currency overview
  (ninja.py:188, 250-257), never when "league" is configured
  (ninja.py:183-185), and only inside a refresh round. A failed read keeps
  the cached league (ninja.py:201-204).
- C2 currency. `GET /poe2/api/economy/exchange/current/overview?league=
  <id>&type=Currency` (ninja.py:52-53, 261-262). Read: `lines[].id` (else
  `itemId`), `primaryValue`, `volumePrimaryValue` (ninja.py:109-122);
  names from top-level `items[].id` / `name`, then `core.items`
  (ninja.py:101-107); `core.primary` (ninja.py:123). Cadence: one attempt
  per 3,600 s, persisted before the request (ninja.py:56, 264-265);
  If-None-Match with the stored ETag on the same URL (ninja.py:266).
  Cache: `<sidecar>\Cache\ninja\rates.json`.
- C3 stackables. The same route with `type` = Fragments, Abyss, UncutGems,
  LineageSupportGems, Essences, SoulCores, Idols, Runes, Ritual,
  Expedition, Delirium, Breach, Verisium (pricebook.py:43-45). Read: as C2
  plus `sparkline.totalChange` (pricebook.py:61-68, 114-138). Cadence: per
  type hourly gate and ETag (pricebook.py:182-198). Cache: `book.json`,
  compact entries only.
- C4 uniques. `GET /poe2/api/economy/stash/current/item/overview?league=
  <id>&type=` UniqueWeapons, UniqueArmours, UniqueAccessories,
  UniqueFlasks, UniqueCharms, UniqueJewels, UniqueSanctumRelics,
  UniqueTablets, PrecursorTablets (pricebook.py:36-40). Read:
  `lines[].name`, `baseType`, `corrupted`, `primaryValue`, `listingCount`,
  `sparkLine.totalChange`; `core.primary` and its name in `core.items`
  (pricebook.py:71-79, 90-111). Cadence as C3.
- Documented but not read (ND): item lines `variant`, `itemId`,
  `detailsId`, `category`, `levelRequired`, the modifier lists; exchange
  lines `maxVolumeCurrency`, `maxVolumeRate`; `core.rates`, `core.secondary`.
- Volume: 1 + 13 + 9 = 23 overview GETs back to back, one at a time
  (ninja.py:212-220, 243-247; pricebook.py:182-219), at most hourly: 552 a
  day plus 4 league reads.

### Gates, identity and transport

- Opt-in: nothing is sent unless `web_data` is true (core.py:557-559;
  ninja.py:223-226) and a contact is set (ninja.py:227-229; decision 0015).
- User-Agent: `AshLight/0.1.0 (local Path of Exile 2 companion; currency
  rates from poe.ninja) (contact: <value>)` (webfetch.py:73-79;
  ninja.py:54, 230). The contact is printable ASCII, at most 120
  characters, no parenthesis or backslash (webfetch.py:54-65), read only
  from gitignored config/local.json (core.py:561-564), never echoed
  (http.py:568-580).
- Headers: User-Agent, `Accept: application/json` and, with a stored
  ETag, If-None-Match (ninja.py:175-180). No Accept-Encoding, never a
  cookie (webfetch.py:190-193).
- Transport: https, exact host `poe.ninja` (ninja.py:50;
  webfetch.py:99-127), at most 3 redirects each re-checked against the
  same host (webfetch.py:196-210), 10 s timeout (webfetch.py:30), 4 MiB
  cap (ninja.py:59).
- League: configured key, else the first list entry (C1). A league change
  drops the old league's book entries (pricebook.py:190-193). The same
  cached value feeds the trade-link league (core.py:575-587).

### Triggers and consumers

- A refresh starts in exactly two places: when the opt-in is switched on
  (core.py:589-596) and on `GET /api/rates` (http.py:287-293). The
  dashboard calls that route on connect (web/app.js:1120) and every 5
  minutes while the page is visible and its feed is live
  (web/app.js:800, 901-903, 1196). The core loop has no rates tick
  (server/al/__main__.py:215-265).
- Consumers, all cache-only: the price card `ninja` part on the
  item-check press (price.py:138-144; ninja.py:338-365), the rates panel
  and conversions (web/prices.js), movers (pricebook.py:270-288), price
  watch (pricewatch.py:133-151), loot filter value tiers
  (ninja.py:367-426), the note-price value math (theorycraft/value.py)
  and the trade-link league (core.py:575-587).

### Evidence base

- Parser tests use synthetic bodies shaped after 0013 / 0019
  (tests/test_price_book.py:5-7); the only real-shape sample in the tree is
  the trimmed Currency body (tests/test_data_ninja.py:25-42).
- Real exchange shape (WV, current league, Currency): top-level keys
  `core`, `lines`, `items`; 51 lines, each with `id`, `primaryValue`,
  `volumePrimaryValue`, `maxVolumeCurrency`, `maxVolumeRate`, `sparkline`
  (`totalChange`, `data`); 51 `items` (`id`, `name`, `image`, `category`,
  `detailsId`), one per line; `core.items` holds 3 reference currencies;
  `core.primary` is `divine` and its own line is worth 1. Every key the
  parser reads is on 51 of 51 lines. The league list has 6 entries and id
  equals name on all 6. No real item-overview body is saved anywhere, and
  the shipped client has never completed a request here (F3).

## Findings

- F1 No formal contract, only convention. ND is the whole agreement. In
  our words: the economy overviews are the one public surface; they exist
  to run the site, public use is tolerated, there is no versioning and no
  SLA, routes may change without notice (redirects are best effort), and
  clients that overuse the economy routes get blocked. There is no terms
  page, no numeric limit, no licence or attribution clause and no API
  changelog; contact is a Discord server (ND, NF). No public source
  repository or issue tracker for poe.ninja was found (UNVERIFIED
  negative). Why it matters: the price features are best effort by
  construction; the offline trade link (decision 0017) is the only part
  nobody can switch off.
- F2 poe.ninja asks desktop apps to proxy through their own backend, so
  per-user traffic does not hit it directly (ND). AshLight calls from the
  player's machine; decision 0013 recorded the mitigation (hourly gate,
  ETag, opt-in). At one user this is harmless. At go-public it is the
  first thing poe.ninja could object to: N installs mean up to 556 x N
  requests a day against a source that says badly behaved apps regularly
  cause it load problems and that requests to build on its API have risen
  sharply with AI-assisted development (ND). The edge does not absorb
  it: the league list and the current league's Currency overview came
  back `cache-control: no-cache`, revalidated against the origin; only
  the older league's overview was edge-cached, for 1,800 s (WV).
- F3 The feature is dark on the operator's machine and the UI hides why.
  config/local.json holds `web_data: true` and no `contact`; the folder
  `<sidecar>\Cache\ninja` does not exist, although the client writes its
  cache before its first request (ninja.py:193-194). So no real poe.ninja
  response has ever passed through the shipped parsers. In that state the
  dashboard says "Web data is on. Prices come from poe.ninja about once an
  hour" (web/prices.js:54-56), "currency values arrive within a minute"
  (web/prices.js:143) and "after the next hourly price update"
  (web/prices.js:192-194). `/api/rates` does carry `blocked: "contact not
  set"` (ninja.py:316) but web/ never reads `blocked` or `contact_set`
  (grep: 0 hits). Only the Checks card says it (diag.py:119-125). The fix
  is a hand edit of a JSON file (config/local.example.json `_doc_web`).
  Why it matters: every poe.ninja feature (price on the press, movers,
  price watch, filter tiers, conversions) is unproven in real use, and a
  new player meets the same wall.
- F4 Prices refresh only while the dashboard page is visible. The two
  refresh triggers are the opt-in switch and `GET /api/rates`
  (core.py:595; http.py:290); the only poller needs a visible page
  (web/app.js:901-903). Closing the companion window destroys the page
  (app/client/window.js:186-191), minimising hides it, and the overlay
  never calls the route. In overlay-only play the cache stops refreshing,
  yet the press still prices from it: `lookup` has no age check
  (ninja.py:338-365), the card drops `checked_at` (price.py:69) and its
  words carry no age (state.py:616-657). The 2 h stale flag
  (ninja.py:58, 323) reaches only the dashboard pill. Why it matters: a
  day-old price shown as current during a league start costs the player
  real currency, and "keep a window visible" breaks the zero-click rule.
- F5 A partial shape change empties the cache silently. On HTTP 200 the
  book replaces a type's entries with whatever the parser kept, even
  nothing, and clears the error (pricebook.py:200-211); the rates do the
  same and also flag a league rollover (ninja.py:274-282). A renamed
  `primaryValue`, `name` or `items` would therefore wipe good data and
  report success. Per-type errors exist (`PriceBook.summary`,
  pricebook.py:290-298) but nothing in server/ calls it; the Checks card
  reads only the Currency error (core.py:888; diag.py:128-139). Drift is
  not hypothetical: (a) ND places names under `core.items`, the live body
  had a top-level `items` (0013); (b) the PoE2 route was reported in
  October 2025 as `currencyexchange/overview?leagueName=&overviewName=`
  with `secondaryValue` fields, and the PoE1 routes as `/api/data/...`
  (CN), all different from ND today; (c) PoE2 unique overviews exist only
  since May 2026, announced with 8 categories including Maps (NP), while
  ND lists 9 types, no Maps, plus UniqueTablets and PrecursorTablets.
- F6 League handling has four gaps. (a) When the old league still answers
  200, the new league is seen only at the 6 h re-read (ninja.py:57,
  186-190); the runbook promises 1 h
  (docs/ops/1.0-launch-runbook.md:153-154); with F4 it can be never.
  (b) The league GET sends no If-None-Match (ninja.py:196) although the
  route returns an ETag (0013). (c) Only the `id` is kept (ninja.py:85)
  and reused as the trade-site league and the label (core.py:575-587):
  right only while id equals name. It does today (0013), but poe.ninja
  already uses a third form, a slug (NE), and had name aliases in 2025
  (CN). (d) "First entry" is the newest softcore challenge league. Today
  six coexist (Forbidden Rites, Runes of Aldur, their HC variants,
  Standard, Hardcore; WV), the player's own league is never asked, the
  dashboard has no league control (web/ only prints it), and the league
  the parser already reads from trade whispers (parser.py:103-116) is
  unused. A Hardcore or Standard player gets softcore challenge prices.
- F7 The client is polite on cadence but not on failure or bytes. No code
  handles 429, 403, 503 or Retry-After (grep of ninja.py, pricebook.py,
  webfetch.py: none): after a 429 the loop goes on through the remaining
  types (pricebook.py:182-219), and a type that keeps failing is retried
  hourly for ever. The 23 GETs run back to back. No Accept-Encoding is sent
  (ninja.py:176) although every saved response carries `Vary:
  accept-encoding` (WV), so bodies come uncompressed: UniqueArmours alone
  was 697,681 bytes (0019); the full round is unmeasured. ND publishes no
  limit; CN reports 12 requests per 5 minutes (UNVERIFIED), which the
  burst would break. The User-Agent purpose says "currency rates" on all
  23 requests, 22 of which fetch other prices (ninja.py:54, 246).
- F8 What the data is. Stackables come from the exchange overview and
  refresh about hourly for PoE2 (ND), so a price is at least an hour
  behind. Uniques come from the stash item overview; PoE2 has no public
  stash stream, so poe.ninja estimates unique prices from the official
  trade API (NP): `listingCount` is a sample, not the market. ND lists a
  `variant` field for uniques with several rolls (0019's live key list
  showed none, so it may be optional); AshLight ignores it
  (pricebook.py:90-111) and shows the most listed line as the price
  (pricebook.py:246-253).
- F9 Some requests may never produce a match. PrecursorTablets is fetched
  hourly, but only an item of rarity UNIQUE is looked up in the item types
  (pricebook.py:245-253) and precursor tablets are not unique items
  (UNVERIFIED: no real body seen). Whether uncut and lineage gem names
  equal the item text is unknown; both wait on F3. One thing is settled:
  the 11 poe.ninja ids that theorycraft/value.py:27-33 maps note prices
  to are all among the 51 real Currency ids (WV).
- F10 PoE2 character and build data. poe.ninja publishes PoE2 builds as
  pages (NB), fed by GGG's ladder API (NL). The API behind them is
  internal and closed to third parties, for load and because players hide
  characters (ND). Not permitted; and of little use here, since AshLight
  needs the player's own build (PoB today, GGG OAuth later; 0033), not the
  ladder's. A link the player opens is the only use.
- F11 Alternatives, each checked.
  - GGG Currency Exchange endpoint: official, in the API Reference, realm
    poe2, hourly history files (0018). Stackables only; ids are metadata
    paths that need base-item names. Ruled 2026-11-17: no call without an
    AshLight OAuth client (0018), so blocked on TC-OAUTH-REG.
  - poe2scout: site (PS), MIT repository with 557 commits and 66 stars
    (PSR), OpenAPI document with 20 GET paths: leagues, currencies and
    uniques by category, items, histories, exchange snapshot (PSA). Its
    README asks sustained users for a User-Agent with contact details and
    names GGG API client credentials for its workers. No terms page (a
    privacy policy only), no SLA, no limits published. A smaller volunteer
    service: the same class of risk as poe.ninja.
  - poe.watch: only PoE1 sections are visible (PW). Not an alternative
    (UNVERIFIED negative).
  - A project-run mirror: one scheduled job fetches the 23 overviews
    hourly and publishes one compact file that installs read; this is
    what F2's request describes. Feasible on GitHub: Pages allows a 1 GB
    site and 100 GB a month (soft) (GH1); scheduled workflows run at 5
    minute granularity, slip at the top of the hour and stop after 60
    days without repository activity (GH2). It republishes poe.ninja
    data to anyone, so it needs poe.ninja's yes first.
  - Floor state: the trade link alone (decision 0017), already the
    behaviour whenever the cache has no price.
- F12 What 1.0 (2026-12-11) changes. A new league, Conquerors of
  Wraeclast, should lead the list; Forbidden Rites and Runes of Aldur end
  (0021). Per GGG's early-access FAQ as reported, early-access characters
  move to an "Early Access" league and never reach Standard (PV2; not
  reconfirmed for 1.0), so Standard and Hardcore would restart empty and
  continuing players sit in a league that is not first. The league adds
  crafting materials (PV1): expect new exchange lines or a new type.
  40 new and 70 revamped uniques (0021) grow the item overviews; the
  4 MiB cap is 6.0 times the largest body seen. First days: thin
  listings, hourly lag, possibly another primary currency (read
  dynamically; the filter tiers wait for a Divine Orb rate,
  ninja.py:380-386). Type renames cannot be predicted; F5 (c) has one.

### Drift risks (ranked, likelihood x impact)

1. League identity on 2026-12-11 (certain x high): new id, old leagues
   end, id may stop equalling name, list order may be transient. Guard
   today: 6 h re-read, 404 path. Gaps: F4, F6.
2. Silent partial shape change (medium x high): a read key renamed or
   moved. Guard today: none (F5).
3. Type list change (high at 1.0 x medium): a new league type is never
   priced; a renamed type fails hourly, unseen (F5, F7).
4. Block or policy tightening (low now, rising at go-public x high): the
   proxy request and the blocking sentence already exist (F1, F2).
5. Rate limiting at the edge (unknown x medium): no 429 handling and a
   23-request burst (F7).
6. Route move (low-medium x high, but loud): happened once since October
   2025 (F5 b); a host change fails closed with a visible Currency error.
7. Meaning and naming drift (medium x low-medium): primary currency
   switch, variant lines, sampled counts, names unproven per type (F8, F9).
8. Size growth (low x low): 6.0 times headroom (F12).

## Recommendations

- R1 PRICE-CONTACT-UX. Action: add a write-only contact field to Settings
  (stored as "contact" in config/local.json, read back only as
  `contact_set`) and make the rates card, the web-data status and the
  movers text show "contact not set" from `blocked`. Impact: H - turns on
  every poe.ninja feature on the operator's machine, where none has ever
  run. Effort: S. Risk: the value leaking into a log, the settings export
  or the diagnostics report; keep decision 0015's rules (never echoed,
  NEVER list in settingsio.py:108, masked in diag). ToS check:
  truthful-User-Agent rule and poe.ninja's contact ask (ND); the value
  stays in a gitignored file, still its only source, so decision 0015
  stands. Depends on: nothing; the operator types the value once. Files:
  server/al/http.py, core.py, web/index.html, web/app.js, web/prices.js,
  tests/test_data_ninja.py, app/test/prices.test.js. Acceptance: with
  web_data on and no contact the card names the missing contact; after a
  POST, `contact_set` is true, the value appears in no GET, export or
  report, and the first round creates `<sidecar>\Cache\ninja\rates.json`.
  ZERO-CLICK: one typed value, once (an identity cannot be guessed and
  the hygiene rule bars a tracked default); nothing after.
- R2 PRICE-LEAGUE-1.0 (before 2026-12-11). Action: re-read the league
  list on every hourly round with If-None-Match; cache the whole list as
  id + name; use the id for poe.ninja and the name for trade links and
  labels; show the league on the overlay price line for 24 h after a
  change; correct runbook step 8. Impact: H - on launch day every price
  and trade link hangs on it. Effort: S. Risk: 20 more league reads a day
  (24, was 4), bodiless when unchanged. ToS check: public-web-data rule
  (documented poe.ninja route, conditional as ND asks); the trade link is
  still only built, never called (decision 0017). Depends on: R3 for
  overlay-only play. Files: server/al/ninja.py, core.py, state.py,
  docs/ops/1.0-launch-runbook.md, tests/test_price_book.py,
  tests/test_util_10_ready.py; an amendment line in decision 0026 item 4.
  Acceptance: a list whose id differs from its name puts the id in the
  poe.ninja URL and the name in the trade URL; a list change while the old
  league still answers 200 is followed within 2 rounds; the league GET
  carries If-None-Match. ZERO-CLICK: automatic.
- R3 PRICE-REFRESH-CORE. Action: start a due refresh from the core loop
  when web data is on and either the log is not idle (decision 0029) or
  `/api/rates` was read in the last 10 minutes; pass the cache age to the
  card: older than 2 h reads "price from N h ago", older than 24 h shows
  the link only. Impact: H - right prices in overlay-only play, no
  requests while nobody plays. Effort: S. Risk: the card's `ninja` keys
  are listed in decisions 0016 / 0026, so this needs an amendment line.
  ToS check: Client.txt rule (staleness of the permitted log read,
  decision 0029; no process check) and public-web-data rule (opt-in and
  truthful User-Agent kept); no input. Depends on: R1 to matter. Files:
  server/al/__main__.py, core.py, ninja.py, price.py, state.py,
  tests/test_price_book.py, tests/test_price_text.py. Acceptance: with no
  HTTP client and an active log a fake transport sees one round an hour;
  with the log idle for 20 minutes, none; exact card text for a 3 h and a
  30 h old cache. ZERO-CLICK: automatic.
- R4 PRICE-SHAPE-GUARD. Action: treat "HTTP 200, lines present, no usable
  entry" and "fewer than half the lines kept, 5 lines or more" as a shape
  error: keep the last good entries, set `last_error` to "shape: ...",
  publish per-type state in `/api/rates` and feed the Checks card with
  the worst type. Impact: H - the difference between "prices quietly
  gone" and a clear line saying why. Effort: S. Risk: an empty type at a
  league start must stay quiet, so zero lines is never an error.
  ToS check: public-web-data rule; no request is added, the checks are
  local. Depends on: nothing. Files: server/al/pricebook.py, ninja.py,
  core.py, diag.py, tests/test_price_book.py, tests/test_diag_self.py.
  Acceptance: a body with a renamed value key keeps yesterday's entries,
  sets a "shape" error and a failing Checks line naming poe.ninja; an
  empty-lines body raises nothing. ZERO-CLICK: automatic.
- R5 PRICE-POLITE. Action: (a) on 429, 403 or 503 stop the round, honour
  Retry-After bounded to 1 h - 24 h and persist the back-off; (b) after 3
  failures in a row retry that type daily; (c) send Accept-Encoding: gzip
  and inflate through a bounded stream (the 4 MiB cap applies after
  inflation); (d) wait 2 s between the 23 GETs; (e) make the User-Agent
  purpose say "prices". Impact: M - lowers the chance of a block and the
  bytes pulled while the game runs. Effort: M. Risk: an unbounded inflate
  would be a memory bomb; the round lasts about 44 s longer (the press
  never waits on it). ToS check: truthful-User-Agent rule; follows the
  source's own requests (ND: caching, low concurrency); no cookie.
  Depends on: nothing. Files: server/al/webfetch.py, ninja.py,
  pricebook.py, tests/test_data_ninja.py, tests/test_price_book.py,
  tests/test_fuzz.py. Acceptance: a 429 with Retry-After 7200 means no
  request for 2 h across a restart; a gzip body decodes and a body
  inflating past the cap is refused; a type failing 3 times waits 24 h;
  22 gaps of 2 s with a fake sleep. ZERO-CLICK: automatic.
- R6 PRICE-SHAPE-WATCH. Action: build the watch described below (the
  input for 0058). Impact: M-H for the operator - upstream changes turn
  into a filed row without a reminder. Effort: M. Risk: cosmetic edits of
  the docs page make noise; tag changed lines by topic as the GGG docs
  watch does. ToS check: public-web-data rule; the docs page is public
  documentation, 1 GET a day with the truthful User-Agent; the in-core
  part adds no request. Depends on: R4 (shared signature code). Files:
  tools/ggg_docs_watch.py (generalised) or a sibling, tools/al_loop.py,
  server/al/pricebook.py, server/al/data/ (baseline, new), diag.py, tests.
  Acceptance: a fixture docs page gaining a PoE2 type writes a dated note
  naming it and raises a flag; a body with an extra unknown key raises
  nothing; a body missing a read key raises the flag. ZERO-CLICK:
  automatic, in the loop tick and in the core.
- R7 GO-PUBLIC-NINJA. Action: before the repository goes public (1) the
  operator asks poe.ninja on its Discord whether per-install polling at
  the R3 / R5 cadence is acceptable or a project mirror is wanted;
  (2) without an answer ship direct calls with a tiered cadence (Currency
  hourly, the other 22 types every 3 h unless pressed in the last 24 h:
  the all-day ceiling falls from 552 to 200 overview GETs); (3) keep the
  mirror design (F11) ready. Impact: H for go-public risk. Effort: S for
  (1) and (2), L for a mirror. Risk: a mirror republishes poe.ninja data;
  scheduled jobs slip and stop after 60 idle days (GH2). ToS check:
  public-web-data rule (poe.ninja is a named source; a mirror is
  AshLight's own file, no GGG endpoint, no trade site); no-revenue rule
  (free, attributed). Depends on: notes 0052, 0053, 0057; an operator
  act. Files: a new decision; server/al/ninja.py; a workflow file only
  for a mirror. Acceptance: a decision records the answer or the default,
  and a test proves the daily request ceiling. ZERO-CLICK: nothing for
  players; one operator message.
- R8 PRICE-LEAGUE-FOLLOW. Action: when 2 trade whispers in a session name
  a league that is in the cached list (R2) and is not the current auto
  league, switch to it and say so once; add a league dropdown fed by the
  same list that writes the existing "league" key. Impact: M - Hardcore,
  Standard and, after 1.0, early-access players get their own league's
  prices. Effort: M. Risk: a whisper about another character's sale
  flips the league; the 2-whisper rule and the R2 league label bound it.
  ToS check: Client.txt rule (lines already parsed after consent) and the
  already cached list; no request added, nothing sent to the game.
  Depends on: R2. Files: server/al/core.py, state.py, ninja.py,
  web/index.html, web/app.js, tests. Acceptance: a replay with two
  whispers naming the HC league moves `/api/rates` to it on the next
  round and shows the notice; the dropdown lists the cached leagues and
  survives a restart. ZERO-CLICK: automatic from the log; the dropdown is
  an override.
- R9 PRICE-TYPE-PROOF. Action: move the two type lists into a hot-reloaded
  data file (decision 0042); after the first real round report per type
  the entry count and whether any press can match it; drop or fix what
  cannot (first candidate PrecursorTablets); put value.py's 11 currency
  ids under the R6 watch. Impact: M - fewer dead requests, and a new type
  becomes a data edit. Effort: S. Risk: a fixture with real names would
  bundle third-party data (decision 0009's spirit); keep fixtures
  synthetic, record counts and key names only. ToS check: public-web-data
  rule; same documented routes, fewer requests. Depends on: R1. Files:
  server/al/pricebook.py, server/al/data/ (new), theorycraft/value.py,
  tools/ (report), tests. Acceptance: every requested type has entries
  and a matching path or is removed; every alias id exists in rates.json
  or is removed. ZERO-CLICK: automatic; the report runs in the loop tick.
- R10 PRICE-VARIANT. Action: keep `variant` in the compact entry; when
  several variants match, show the low-high range and that it depends on
  the roll. Impact: M-L - no false precision on multi-roll uniques.
  Effort: S. Risk: card density; it stays one line. ToS check: one read
  per press rule; the same press, a cache lookup only. Depends on: R1
  (confirm on a real body that lines carry `variant`, F8). Files:
  server/al/pricebook.py, state.py, tests. Acceptance: 3 variant lines
  give the range text; one variant is unchanged. ZERO-CLICK: same press.
- R11 PRICE-FALLBACK-RUNBOOK. Action: write the fallback order (poe.ninja,
  a project mirror, poe2scout, GGG Currency Exchange for stackables once
  an OAuth client exists, link only) with, per source, the docs URL, the
  date its terms were read and the field map to the compact entry; add
  no code and call no second source until decision 0026's "Reverses if"
  fires and a new decision is filed. Impact: M - days, not weeks, to
  recover. Effort: S. Risk: none now. ToS check: public-web-data rule;
  nothing is called, and each future source needs its own check
  (documented API, truthful User-Agent, no cookie). Depends on: nothing.
  Files: docs/decisions (a contingency note). Acceptance: the note names
  the 4 fallbacks with their terms dates. ZERO-CLICK: not applicable
  (session work).
- R12 PRICE-NINJA-LINK. Action: next to the trade link offer a link the
  player opens in their own browser to the poe.ninja category page of the
  checked item. Impact: L - price history for the player, traffic back to
  the source. Effort: S. Risk: the page URL form is undocumented and uses
  a slug (NE); link only to forms read from the public site. ToS check:
  public-web-data rule; the app requests nothing, the player's browser
  does (as decision 0017 does for trade). Depends on: R2. Files:
  server/al/price.py, state.py, web/prices.js, tests. Acceptance: the
  card carries an https poe.ninja URL for a unique and none for an
  unknown category. ZERO-CLICK: an optional click; nothing is needed.

### Shape-watch design (input for 0058)

- Layer 1, in the core, no extra request. On every HTTP 200 body the
  parser records per route family and type: status, content type, ETag
  present, the Cache-Control class; the key sets at top level, in `core`
  and across lines; for each key the parser READS, the share of lines
  carrying it; counts of lines, kept entries and named entries; and these
  invariants: the league list is a non-empty list of unique string ids;
  `core.primary` is a string and, on exchange bodies, its own line is
  worth 1; values are finite and positive; `listingCount` is an integer.
- Baseline: one tracked file of read-key names per family (key names
  only, no prices, no item names). The exchange and league baselines can
  be cut from WV today; the item baseline needs the first real round
  (R1). Leagues: id, name. Exchange: lines.id, lines.primaryValue,
  lines.volumePrimaryValue, lines.sparkline.totalChange, items.id,
  items.name, core.primary, core.items.id, core.items.name. Item:
  lines.name, lines.baseType, lines.corrupted, lines.primaryValue,
  lines.listingCount, lines.sparkLine.totalChange, lines.variant (after
  R10), core.primary, core.items.
- Verdicts. BREAK: a read key on under half the lines, under half the
  lines kept (5 lines or more), a list that is not a list, 3 failing
  rounds for one type, or a redirect off the host. CHANGE: new unknown
  keys, another Cache-Control class, a vanished ETag (information only).
  LEAGUE: the first league id changed (expected; a notice, not an alarm).
- Layer 2, on the operator's machine: one GET a day of the docs page ND
  from the loop tick, like the GGG docs watch (decision 0044): hash the
  normalised page text, never the raw HTML or the Last-Modified header
  (two reads 17 h apart differed as HTML, 96,712 and 96,862 bytes, and
  were identical as text, 13,196 characters; Last-Modified is the render
  time). The page has no `<main>`, so take the text from the "API
  Reference" heading to the footer line. Keep the baseline in the sidecar
  Cache, write a diff to the sidecar Logs, tag changed lines as types
  (the two PoE2 type tables), routes (lines starting GET /poe2) or policy
  (proxy, blocked, User-Agent, contact, cache, hourly, replicate,
  versioning). Runs while HALTed (read-only, no agent spawn), 3 h retry
  after a network error, stops at a 429 or 503.
- Layer 3, the league: R2's hourly re-read; a Checks line "league changed
  to X" stays for 7 days. How often: layer 1 every round (hourly while
  playing), layer 2 every 24 h, layer 3 hourly.
- On BREAK: keep the last good cache, age the card text (R3), show a
  failing Checks line, write `ops/runtime/ninja/SHAPE_DRIFT` (family,
  type, missing keys, first seen), probe a broken type daily, and let the
  loop tick file one ROADMAP row per signature. On a types or routes
  change: a flag file and one row carrying the diff path; a session
  applies it (unattended commits stay off, as in decision 0025). On a
  policy change: the row goes to an adjudicator with decisions 0013 /
  0026 "Reverses if" as the question. On a block lasting 24 h: cards read
  "source unavailable", the trade link stays, R11's runbook is filed as a
  row. No toast and no chat line, as in decision 0044.

## Cut or merge

- Merge Currency into the price book: ninja.parse_overview and
  pricebook.parse_exchange_overview repeat the same name resolution
  (ninja.py:101-107; pricebook.py:120-126) and the same gate; one parser
  and one cache would halve the code R4 and R5 must touch.
- Cut PrecursorTablets unless R9 finds a matching path (F9).
- Cut the hourly cadence for the 22 non-currency types to every 3 h when
  the repository goes public (R7): saves 352 of 552 daily requests.
- Cut the dead price-card states (for the features review, 0038):
  `searching`, `waiting`, `done`, `off` and the "contact not set" words
  are not produced since decision 0017 (web/prices.js:199-213;
  state.py:559-561).
- Keep movers: no request of its own. Its 20-listing floor rests on a
  sampled count (F8), so word it as a trend, not a fact.

## Rejected

- poe.ninja's builds, profiles, character or Path of Building endpoints:
  closed to third parties by the source itself (ND), and they would carry
  other players' data.
- Reading poe.ninja's HTML pages for data, or its undocumented routes
  seen in a browser (history, details, the 2025
  `currencyexchange/overview`): outside ND, so not permitted here.
- Polling faster than hourly, cache-busting parameters, or a request on
  every item-check press: against ND and decision 0026 item 2.
- The trade site as a price fallback: floor rule (the trade site is never
  called by the app) and decision 0017.
- GGG's Currency Exchange endpoint today: the 0018 ruling stands until an
  AshLight OAuth client exists; its "Reverses if" is not met.
- Paid third-party price APIs that wrap the trade site: trade data by
  proxy, and money changing hands over GGG-derived data.
- Another tool's User-Agent, or a nameless one, to get past a block:
  breaks the truthful-User-Agent rule.
- A shared default contact in a tracked file while the repository is
  private: public-repo hygiene rule (see open question 2).

## Open questions

1. Does poe.ninja accept per-install polling from a public desktop app
   at the R7 cadence, or does it want a mirror, and would a mirror file
   count as replicating the site? Operator act (a Discord message), then
   a decision.
2. Once the repository is public, may its URL be the User-Agent contact
   for every install? ND asks for the app's contact, not each player's;
   that would remove R1's one typed value. It amends decision 0015 item
   1, whose "Reverses if" is not met, so it needs an operator decision.
3. Unobserved until R1 lands: per-type body sizes, the compressed sizes,
   whether a 429 exists and its Retry-After, the item-overview keys on
   real lines (`variant` above all), the names on uncut and lineage gem
   lines, and the PrecursorTablets line shape.
4. Observable on 2026-12-11 only: what poe.ninja returns for an ended
   league (404, empty or a frozen 200), how soon the 1.0 league leads the
   list, whether its id equals its name, and whether GGG keeps
   early-access characters in a separate league (PV2 reports an older
   FAQ; GGG has not restated it).
5. poe2scout's data source, limits and stance on desktop clients: ask
   only if R11 is triggered.
