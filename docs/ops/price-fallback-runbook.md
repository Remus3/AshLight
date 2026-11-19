# Price source fallback runbook

Status: filed 2026-11-18 (package DATA-PRICE-FALLBACK-RUNBOOK). A contingency
note, not a decision: it takes no decision number. Written from research
0036 (F11, R11) with that note's access dates (2026-11-17, re-read
2026-11-18). No web read was made for this file and nothing here is called by
the app.

## When this applies

Today prices come from poe.ninja only (decisions 0016, 0026). Do nothing
from this file until decision 0026's "Reverses if" fires: poe.ninja asks
clients to poll less or blocks the pattern, the overview shapes break the
parsers every release, or GGG documents a trade price source. Then file a new
decision first (decision, alternatives, why, reverses if) and only then add
code for the source it picks.

Each future source needs its own check before any call: a documented API,
a truthful User-Agent naming AshLight and its version, no cookie, nothing
read from the trade site (Game ToS floor in CLAUDE.md; decisions 0013,
0017). The "terms read" dates below are the dates research 0036 read each
source; a source's terms are re-read on the day it is picked, never assumed.

## Fallback order

Floor state at every step: with no price in the cache the card shows the
trade-search link alone (decision 0017). That is the behaviour already in
force when a source is down, so a fallback only adds numbers, never removes
the link.

### 1. poe.ninja (in use)

- Docs: https://poe.ninja/docs/api
- Terms read: 2026-11-17, re-read 2026-11-18 (research 0036, ND). It asks for
  contact in the User-Agent, HTTP-caches overview responses for about 5
  minutes with ETags, has no PoE2 stash currency route, and does not allow
  using the API to replicate the site directly.
- Field map to the compact entry (research 0036 C1 to C4): leagues
  `id` else `name`; exchange overview `lines[].id` (else `itemId`),
  `primaryValue`, `volumePrimaryValue`, names from `items[].id` / `name`,
  `core.primary`; stackables add the change from the first sparkline that
  has `totalChange`; uniques read `lines[].name`, `baseType`, `corrupted`,
  `primaryValue`, `listingCount`, `sparkLine.totalChange`.
- Cadence kept by any switch back: one attempt per type per hour, ETag
  re-use, no cache-busting parameter.

### 2. A project-run mirror

- Docs: none yet; it would be AshLight's own published file. Hosting limits
  (research 0036 GH1, GH2): GitHub Pages allows a 1 GB site and a soft 100 GB
  a month; scheduled workflows run at 5 minute granularity, slip at the top
  of the hour and stop after 60 days without repository activity in a public
  repository.
- Terms read: poe.ninja's API terms 2026-11-18 (ND). A mirror republishes
  poe.ninja data to anyone, and ND forbids using the API to replicate the
  site directly, so it needs poe.ninja's yes first (research 0036 open
  question 1, an operator act). Without that yes this step does not start.
- Field map: one compact file of the 23 overviews (1 currency, 13
  stackable types, 9 unique types) in the same compact entries as
  poe.ninja's map above; installs read the one file at most hourly.

### 3. poe2scout (second community source)

- Docs: https://api.poe2scout.com/swagger ; OpenAPI document
  https://api.poe2scout.com/openapi/v1.json ; repository
  https://github.com/poe2scout/poe2scout
- Terms read: 2026-11-17 (site), re-read 2026-11-18 (repository and
  OpenAPI): MIT licence, 20 GET paths. Its README asks sustained users for a
  User-Agent with contact details, and names no upstream source, no terms, no
  SLA and no limits; the site showed a privacy policy only. Same risk class
  as poe.ninja (a smaller volunteer service). Open question 5 of research
  0036 (its data source, limits and stance on desktop clients) is asked
  only now.
- Field map: the API lists leagues, currencies and uniques by category,
  items, histories and an exchange snapshot. Map each response's item name
  and price fields to the compact entry (name, price in the primary
  currency, listing count, change) from a real body fetched on the day the
  decision is filed; research 0036 holds no real body, so this map is open.

### 4. GGG Currency Exchange (stackables only, link only otherwise)

- Docs: https://www.pathofexile.com/developer/docs/reference (the API
  Reference); changelog https://www.pathofexile.com/developer/docs/changelog
- Terms read: 2026-11-17 (research 0018, 0036 F11). Realm poe2, hourly
  history digests, stackables only; ids are base-item metadata paths that
  need base-item names. Ruled 2026-11-17: no call without an AshLight OAuth
  client (research 0018), so it waits on TC-OAUTH-REG.
- Condition: this step starts only with a separate written GGG grant of the
  Currency Exchange scope. The ask is question 3 of the OAuth application
  (docs/ops/ggg-oauth-application.md, package DATA-GGG-APPLICATION). No scope
  name is written here from memory: quote the wording of the written grant
  when it exists. AshLight's own client asks for account:characters only.
- Field map (research 0018, reference read 2026-11-17): `markets` with
  `league`, `market_id`, `market_pair`, `volume_traded`, `lowest_stock`,
  `highest_stock`, `lowest_ratio`, `highest_ratio`; `next_change_id` is a
  unix hour. Digests are purely historical (no current hour), so a price is
  a ratio from the latest closed hour.
- Never for uniques; those stay on steps 1 to 3 or the link.

## Last resort

The trade-search link the player opens in their own browser (decision 0017).
Not a source: the app never calls the trade site, and no step above may
replace this link with a request to it.

## Re-check

Every step needs a fresh read of its terms on the day it is picked. This file
is corrected by editing it, with the new access date beside the old one.
