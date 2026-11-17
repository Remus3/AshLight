# 0026 - Price book: unique and stackable poe.ninja prices, movers, league rollover

Date: 2026-11-17. Trigger: ROADMAP rows PRICE-UNIQUE, PRICE-STACKABLES,
UTIL-MOVERS, UTIL-1.0-READY (lane area-util batch 2). Inputs: decisions
0013 (one web_data opt-in, default off), 0015 / 0016 (price on the
item-check hotkey, contact from config/local.json, card contract), 0017
(prices from poe.ninja only, trade only as a link), research 0019 (poe.ninja
PoE2 contract) and 0018 (PoE2 1.0 on 2026-12-11). Number check: main and
every local branch held 0001-0022 (two 0022 files, a renumber in flight)
and 0023 was reported taken; 0024 (tc-delta) and 0025 (tc-drift) went to renumbers, so this is 0026.

## Decision

1. `server/al/pricebook.py` PriceBook caches the 9 Unique* stash item
   overviews and 13 more exchange overview types (research 0019 list;
   Currency stays in rates.json). It owns no transport: RatesClient's own
   refresh drives it after the opt-in and contact checks, with the same
   GET (truthful User-Agent, poe.ninja allowlist, no cookie), the same
   league and one request at a time. Each type has its own hourly gate
   (a failed attempt counts, persisted, so a restart never refetches
   early) and its own ETag (If-None-Match). One failing type never stops
   the rest. The cache keeps compact entries (name, base, corrupted, value,
   listings, 7-day change), never raw bodies.
2. The item-check press reads the cache only (`RatesClient.lookup`): no
   request on a press, no own endpoint. Uniques match name + base type
   (+ corrupted), then name + base type; stackables match the base name
   (Currency from rates.json by name). The decision 0016 card gains one
   key, `ninja` (kind, name, value, unit, listings, few, change, league) or
   None; the card's words come from `state.ninja_text`. Off (web data
   off) or another league's cache -> None, and the link card is unchanged.
3. UTIL-MOVERS: `/api/rates` gains `movers` (5 risers, 5 fallers by
   7-day change from the same cache, thin markets out: uniques under 20
   listings, stackables under 1.0 volume). Empty while web data is off.
   No extra request.
4. League rollover: the auto league is re-read every 6 h (was 24 h), and
   after a 404 or an empty currency overview for the auto league within
   the hour. A configured league never rolls over. A league change drops
   the old league's book entries (new URL, no ETag reuse).
5. The offline trade links (price card and upgrade link) use the
   configured league, else the cached poe.ninja league while web data is
   on, else Standard (`Core.trade_league`). Still built offline, never
   opened by the core (decision 0017).

## Alternatives

- Fetch a type only on the first press of an item of that kind: fewer
  requests, but the first press would show no price and movers would have
  no data. Rejected; the hourly gate already meets poe.ninja's guidance.
- Store raw overview bodies: up to ~700 KB per unique type. Rejected for
  compact entries.
- Own `/api/price` endpoint: rejected by decision 0015 (price shares the
  hotkey and the snapshot).
- Keep 24 h league re-reads: a 1.0 launch day would price the old league
  for up to a day. Rejected.

## Why

About 23 conditional GETs per hour while the opt-in is on, one user,
ETag-respecting, is within research 0019's guidance ("roughly hourly",
"use conditional requests"), and every value shown still comes from
poe.ninja only.

## Reverses if

poe.ninja asks clients to poll less or blocks the pattern; decision 0013
changes to per-feature opt-in; the overview shapes break the parsers every
release (then fall back to Currency only); or GGG documents a trade price
API that decision 0017 would allow.
