# Copy sheet: price

Templates for the price family: `server/al/text/price.py`
(`price_card_text`) and the price, points and upgrade search lines of
web/prices.js. The rules that bind every template (one event, one
sentence; player text quoted; missing fields read honestly; overlay
register; line limits; plurals; time words; passive notifications; an
exact-output test per template) stay in design 0001 section 9
([0001-design-system.md](../0001-design-system.md)). This sheet holds the
templates only, moved word for word out of design 0001 (TEST-COPY-SHEETS);
a new or changed price template is edited here, not in design 0001.

## Templates

- price and points (MATH-VALUE-UI, web/prices.js `valueView`): `Asking
  price: <n> <currency>, about <n> <primary>.` (`Buyout price: ...` for
  a b/o note; no "about" when already the primary), `<n> points per
  <primary>.`, `These currency values may be out of date.`, the
  poe.ninja credit; without rates `No currency values are saved yet, so
  AshLight can't compare the item's price with its points.`, without a
  rate for that currency `There is no saved value for <currency> yet,
  so AshLight can't compare the item's price with its points.`; hidden
  when the item has no note price.
- price check (PRICE-1-UI, `price_card_text`): overlay `Price: <item>`,
  `<n> listed, ~<middle>` / `Lowest <amount> <currency>`, `Searching
  prices...`, `Prices in about <n> s`, `Web data is off`, `No listings found`,
  `Price check failed`; dashboard `<n> listed in <league>. The cheapest
  is <a>; the middle of the <k> cheapest is <b>.`; the one card is
  chosen by `overlay_card` (decision 0016)
- upgrade search (TC-UPGRADE, `web/prices.js upgradeView`): dashboard
  only, `Your build wears <base> in <slot>, so this finds rare items of
  that base.` (empty slot: `Your build has nothing in <slot>, so this
  uses the checked item's base, <base>.`) then `It matches base type and
  rarity only, not stats.`; link `Search the official trade site for
  rare <base> (<slot>)`
