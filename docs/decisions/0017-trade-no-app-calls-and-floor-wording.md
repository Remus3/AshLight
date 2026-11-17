# 0017 - No app calls to trade2; trade-search link only; floor wording (PRICE-1, TC-UPGRADE, RES-POLICY)

Date: 2026-11-17. Trigger: the 2026-11-17 policy re-read (research 0001)
found three floor gaps. Ruled by an adjudicator agent; the operator is away.

## Decision

1. Floor wording (CLAUDE.md, Game ToS floor):
   a. Add: no commercial revenue from GGG intellectual property.
   b. Branding: never present AshLight as developed, authorised or
      endorsed by GGG.
   c. Trade: the app calls no trade-site endpoint. GGG endpoints only if
      in the API Reference or Data Exports. The app may build a
      trade-search URL that the user opens in their own browser.
2. PRICE-1 / decisions 0013 item 5, 0015 item 3: the app's own HTTP to
   trade2 (/data/stats, /data/leagues, /search, /fetch) is removed from
   every reachable path. build_query stays and produces a search URL
   offline. The price card (0016 Fork 1) gains status "link" with a
   `url`; the dashboard shows a click-through link, the overlay a short
   notice; the core never opens it. The league for the URL comes from
   config, else Standard; nothing is fetched.
3. TC-UPGRADE: becomes a link builder. Mod filters need trade stat ids,
   which have no permitted source yet; filed TC-UPGRADE-STATS (source and
   license check, decision 0009). Until then the link carries name, base
   and rarity only.
4. Pricing shown by the app comes from poe.ninja only (decision 0013 item
   3). A test asserts no trade host is in the webfetch allowlist.

## Alternatives not taken

- Keep trade2 calls as opt-in best-effort (research proposal): rejected,
  the endpoints are undocumented and ToU 7i bars reverse-engineered ones;
  honest doubt tightens.
- Stop only TC-UPGRADE: rejected, same risk in the shipped path.
- Drop all trade features: rejected, the user opening a link is ordinary
  site use and costs the app nothing.

## Why

Account termination is the cost of a wrong call; a link the user opens
puts the request in the user's browser, not the app. One read per press,
no input to the game and the clipboard rules are unchanged.

## Reverses if

GGG documents trade endpoints or permits third-party use in writing, the
operator rules otherwise, or the ?q= URL form proves unstable (then show
poe.ninja only). Amends 0013 item 5, 0015 item 3 and Settled entries
"Price check shares the item-check hotkey ..." (the trade2 queue part).

## Status

Item 2 built 2026-11-17 (PRICE-TRADE-LINK). `trade.TradeClient`, `Job`,
`RateLimiter`, `search_url` / `fetch_url` and price.py's stat-table,
league-list, search and fetch path are deleted, not just unwired: the
limiter parsed trade2 headers only and has no other caller (poe.ninja has
its own pacing), so keeping it would be dead code. `trade.build_query` /
`search_link` build the URL offline (research 0016: name, base type,
rarity; no rarity filter for uniques). `webfetch.check_url` refuses every
pathofexile.com `/trade...` or `/api/trade...` URL and redirect whatever a
caller's allowlist says (`is_trade_url`); no allowlist holds a
pathofexile.com host. Tests: tests/test_trade_link.py,
tests/test_price_check.py. Card contract: decision 0016 amendment
PRICE-TRADE-LINK.

Item 3 built 2026-11-17 (TC-UPGRADE, link builder). `server/al/upgrade.py
link(result, league)` takes the item check's best slot (the hotkey press,
decision 0014) and builds `trade.upgrade_link`: rare items of the base the
build wears in that slot, else the checked item's base when the slot is
empty; status online, base type and rarity only, no name, no stat filters.
Both links go through one URL builder, `trade.link_for` (no duplicate);
`trade.complexity` counts 4 per stat filter against the site's cap of 200
(research 0010 section 4), so a later TC-UPGRADE-STATS stat group cannot
exceed it. No build loaded, not an item or no gear slot: no link. The eval
card carries `upgrade` {slot, base, source, rarity, league, url} or null,
so a build or weights change rebuilds it with no click; the dashboard Item
check card shows it as a click-through link (web/prices.js upgradeView, the
same trade2 URL check as the price link); the overlay is unchanged. Tests:
tests/test_tc_upgrade.py (exact query and URL, round trip, no network call
on a press), app/test/prices.test.js.
