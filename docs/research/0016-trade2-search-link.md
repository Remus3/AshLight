# 0016 - trade2 search link form (?q=) for PRICE-TRADE-LINK

Date: 2026-11-17. Trigger: decision 0017 (no app calls to the trade site;
the app builds a search URL the user opens in their own browser). Question:
does `https://www.pathofexile.com/trade2/search/poe2/<league>?q=<url-encoded
JSON>` open a pre-filled search, and what JSON shape does it take?

Method: third-party sources only. No request was sent to pathofexile.com.

## Findings

1. The PoE2 link form is built by a widely used open-source price checker
   from the same object it would POST as a search body.
   Exiled-Exchange-2, `TradeListing.vue` `makeTradeLink`:
   `https://${getTradeEndpoint()}/trade2/search/poe2/${league}?q=${JSON.stringify(createTradeRequest(...))}`.
   Source: https://raw.githubusercontent.com/Kvan7/Exiled-Exchange-2/master/renderer/src/web/price-check/trade/TradeListing.vue
   (accessed 2026-11-17).
2. The PoE1 equivalent `trade/search/<league>?q=<JSON>` has been built the
   same way for a long time by Awakened PoE Trade.
   Source: https://raw.githubusercontent.com/SnosMe/awakened-poe-trade/master/renderer/src/web/price-check/trade/TradeListing.vue
   (accessed 2026-11-17).
3. poedb's API:Trade page says the search page accepts "POST JSON to or GET
   ?q=JSON", with an example holding `"rarity": {"option": "rare"}`.
   Source: https://poedb.tw/API%3ATrade (accessed 2026-11-17).
4. Rarity filter path: `query.filters.type_filters.filters.rarity.option`.
   Exiled-Exchange-2 sets it via
   `propSet(query.filters, "type_filters.filters.rarity.option", ...)` and
   assigns only `normal`, `magic` and `nonunique` (its type also allows
   `uniquefoil`); `rare` is confirmed by poedb. Status options include
   `online`.
   Sources: https://raw.githubusercontent.com/Kvan7/Exiled-Exchange-2/master/renderer/src/web/price-check/trade/pathofexile-trade.ts
   and https://raw.githubusercontent.com/Kvan7/Exiled-Exchange-2/master/renderer/src/web/price-check/filters/create-item-filters.ts
   (both accessed 2026-11-17).

## UNVERIFIED

- GGG documents neither the page nor the `?q=` parameter (it is not in the
  API Reference). It is ordinary trade-site use by the user's own browser,
  which is what decision 0017 allows; its stability is not promised.
- `"unique"` as a rarity option: no source above confirms it. AshLight
  therefore sends no rarity filter for uniques and selects them by `name`
  plus `type`, as both tools do.
- Whether the site applies `sort` when it arrives through `?q=` (the tools
  pass the whole request object, `sort` included; harmless if ignored).

## Consequence for AshLight

`server/al/trade.py search_link` builds the link offline: `status` online,
`name` (uniques) and `type` (base), and the rarity filter for normal /
magic / rare items; no stat filters (TC-UPGRADE-STATS). League from
config/local.json, else Standard. If the form proves unstable, decision
0017's reversal applies: drop the link and show poe.ninja only.
