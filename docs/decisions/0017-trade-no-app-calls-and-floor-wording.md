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
