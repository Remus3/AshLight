# 0019 - poe.ninja PoE2 endpoint contract, rate guidance, new data

All sources accessed 2026-11-17. Extends 0013 (first live check). Scope:
what poe.ninja data can power new features within decisions 0013 (one
opt-in web_data setting, default off), 0015 / 0016 (price on the
item-check hotkey, contact from config/local.json) and 0017 (prices from
poe.ninja only; trade only as a link).

## Contract (docs, 2026-11-17)

Source: https://poe.ninja/docs/api (accessed 2026-11-17).

- Documented, permitted surface: ECONOMY ONLY, GET, `{game}` = poe1 / poe2:
  - `/{game}/api/economy/leagues` - `[{id, name}]`, first = current
    temporary challenge league.
  - `/{game}/api/economy/exchange/current/overview?league=&type=` - PoE2
    types: Currency, Fragments, Abyss, UncutGems, LineageSupportGems,
    Essences, SoulCores, Idols, Runes, Ritual (Omens), Expedition,
    Delirium (Liquid Emotions), Breach (Catalysts), Verisium.
  - `/{game}/api/economy/stash/current/item/overview?league=&type=` - PoE2
    types: UniqueWeapons, UniqueArmours, UniqueAccessories, UniqueFlasks,
    UniqueCharms, UniqueJewels, UniqueSanctumRelics, UniqueTablets,
    PrecursorTablets.
  - PoE2 currency goes through the exchange overview, not the PoE1-only
    stash currency overview.
- EXCLUDED: builds, profiles, character, Path of Building and auth
  endpoints are internal, "undocumented, unsupported, and not available
  for third-party use" (load and player privacy). AshLight must not call
  them; a "meta builds" feature from poe.ninja is NOT feasible.
- Caching / rate: HTTP cache "roughly 5 minutes", ETag based, "Use
  conditional requests and respect the cache headers; do not bypass
  caching"; PoE2 data refreshes "roughly hourly"; polling more often than
  every few minutes "wastes bandwidth"; misbehaving or excessive clients
  "will be blocked".
- Identity: "Send a descriptive User-Agent that identifies your app and a
  contact" (AshLight: contact from config/local.json, decision 0015).
- Stability: "There is no versioning and no SLA, and breaking changes can
  happen to the economy endpoints without notice"; redirects on moves are
  "best effort rather than a promise".
- Desktop guidance: desktop apps "should proxy these requests through
  their own backend" (decision 0013 records the mitigation: hourly gate,
  ETag, opt-in, one user).
- Use: "Don't use the API to directly replicate the site."; no license or
  attribution clause; "poe.ninja is not affiliated with or endorsed by
  Grinding Gear Games."

## Live checks (2026-11-17, truthful AshLight research UA, no cookie)

- `stash/current/item/overview?league=Forbidden Rites&type=UniqueArmours`
  -> 200 application/json, 697,681 bytes, 438 lines, `cache-control:
  no-cache` with a weak ETag (the exchange overview had max-age 1800 in
  0013; cache headers differ per route, so always send If-None-Match).
- Top-level keys `core` (same reference currencies as the exchange
  overview: divine, exalted, ...) and `lines`. Line keys: `id`, `itemId`,
  `detailsId`, `name`, `baseType`, `category` (Body Armour 141, Helmet
  100, Gloves 71, Boots 47, ...), `levelRequired`, `primaryValue`,
  `listingCount`, `corrupted`, `sparkLine` (`totalChange`, 7 points, nulls
  allowed), `explicitModifiers`, `propertyModifiers`,
  `requirementModifiers`, `flavourText`, `icon`.
- Variant names appear in `baseType`, e.g. a "Runemastered" base for 0.5.5
  runemastered uniques (cf. 0017), so a unique match must key on
  name + baseType, not name alone.
- Unique lines carry no line-level `items` array; names are on the line
  itself (unlike the exchange overview, 0013 DATA-NINJA-NAMES).

## Stability assessment

- The PoE2 route family `/poe2/api/economy/...` is unchanged since 0013
  (one day earlier) and matches the docs. Risk: no SLA; the exchange
  overview's real shape already differs from the docs table (0013). Keep
  parsers defensive, fixture-tested on real trimmed bodies, failing to a
  visible "price unavailable" state.
- League rollover at PoE2 1.0 (2026-12-11, 0018): "first = current" will
  switch to the 1.0 league; ninja.py should re-read leagues on its hourly
  gate (already its behaviour per 0013) and the price card should show the
  league name.

## New data -> features (within 0013 / 0015-0017)

1. Unique prices on the item-check press: the same hotkey press that
   checks a unique looks it up in the cached Unique* overview (name +
   baseType, corrupted flag) -> price card value, listing count (low count
   = thin market, show "few listings"), 7-day trend from `sparkLine`.
   Fits 0015 (shares the hotkey) and 0017 (poe.ninja only). Row
   PRICE-UNIQUE.
2. More exchange categories for stackables: Essences, Omens (Ritual,
   the Forbidden Rites mechanic), Runes, SoulCores, Catalysts, Liquid
   Emotions, Fragments, UncutGems, LineageSupportGems priced on the hotkey
   when the clipboard item is a stackable of that kind. One request per
   type per hour, ETag. Row PRICE-STACKABLES.
3. Session value (no drop data exists, 0018): a "price sheet" panel on the
   dashboard with the top movers (`sparkline.totalChange`) of the current
   league; zero clicks, refreshed with the hourly gate. Row UTIL-MOVERS.
- NOT feasible: builds / meta / character data (excluded endpoints);
  replicating poe.ninja pages wholesale ("don't replicate the site").

## Sources

- https://poe.ninja/docs/api (accessed 2026-11-17)
- https://poe.ninja/poe2/api/economy/stash/current/item/overview?league=Forbidden%20Rites&type=UniqueArmours (live GET, accessed 2026-11-17)
- docs/research/0013-web-endpoint-verify.md (prior live checks, 2026-11-17)
