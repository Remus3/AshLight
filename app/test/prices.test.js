"use strict";
/* DATA-NINJA-UI / PRICE-1-UI (decision 0016): the dashboard's pure view
   helpers in web/prices.js - the web-data opt-in words, the poe.ninja rates
   panel, "about N <primary>" conversions and the price check section.
   Fixture values are invented. */
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const p = web.load("prices.js");

const RATES = {
  web_data: true, source: "poe.ninja", credit: "Prices: poe.ninja",
  attribution: "Currency rates from poe.ninja (...)", league: "Dawn", primary: "divine",
  rates: {
    divine: { value: 1, name: "Divine Orb", volume: 900 },
    exalted: { value: 0.0025, name: "Exalted Orb", volume: 5000 },
    chaos: { value: 0.04, volume: 1200 },
    "mirror-shard": { value: 250.5, volume: 3 },
    annul: { value: 0.31234, name: "Orb of Annulment", volume: 400 }
  },
  age_s: 720, stale: false, refreshing: false, last_error: null, next_refresh_in_s: 2880
};

function with_(over) { return Object.assign({}, RATES, over); }

test("web-data words: off says nothing is asked; on says what is fetched", () => {
  assert.deepEqual(p.webDataView({ web_data: false }), {
    on: false,
    status: "Web data is off. AshLight asks nothing from the internet." });
  assert.deepEqual(p.webDataView({ web_data: true }), {
    on: true,
    status: "Web data is on. Prices come from poe.ninja about once an hour." });
  assert.equal(p.webDataView(null).on, false);
  assert.equal(p.savedText(true), "Saved. Web data is on. Currency values arrive within a minute.");
  assert.equal(p.savedText(false), "Saved. Web data is off. AshLight asks nothing from the internet now.");
});

test("numbers and ages read plainly", () => {
  assert.equal(p.num(1234.4), "1,234");
  assert.equal(p.num(250.5), "251");
  assert.equal(p.num(12.34), "12.3");
  assert.equal(p.num(1.5), "1.5");
  assert.equal(p.num(0.31234), "0.312");
  assert.equal(p.num(0.0025), "0.0025");
  assert.equal(p.num(0), "0");
  assert.equal(p.num("x"), "");
  assert.equal(p.ageText(20), "just now");
  assert.equal(p.ageText(60), "1 min ago");
  assert.equal(p.ageText(720), "12 min ago");
  assert.equal(p.ageText(3 * 3600 + 5), "3 h ago");
  assert.equal(p.ageText(86400), "1 day ago");
  assert.equal(p.ageText(3 * 86400), "3 days ago");
  assert.equal(p.ageText(null), "");
});

test("rates panel: top currencies in the primary unit, by volume", () => {
  const v = p.ratesView(RATES);
  assert.deepEqual(v.pill, { state: "done", glyph: "[+]", word: "updated 12 min ago" });
  assert.equal(v.primary, "Divine Orb");
  assert.equal(v.league, "Dawn");
  assert.equal(v.credit, "Prices: poe.ninja");
  assert.deepEqual(v.rows.map((r) => r.name),
    ["Exalted Orb", "Chaos", "Orb of Annulment", "Mirror shard"]);
  assert.deepEqual(v.rows[0], { name: "Exalted Orb", value: "0.0025 Divine Orb",
                                per: "400 per Divine Orb" });
  assert.deepEqual(v.rows[3], { name: "Mirror shard", value: "251 Divine Orb", per: "" });
});

test("rates panel: stale, off, fetching, failing, empty", () => {
  assert.deepEqual(p.ratesView(with_({ stale: true, age_s: 3 * 3600 })).pill,
    { state: "blocked", glyph: "[#]", word: "old values - from 3 h ago" });
  assert.deepEqual(p.ratesView(with_({ web_data: false, stale: true, age_s: 5 * 3600 })).pill,
    { state: "idle", glyph: "[-]", word: "not updating - web data is off (from 5 h ago)" });
  const off = p.ratesView(with_({ web_data: false, rates: {}, age_s: null }));
  assert.deepEqual(off.pill, { state: "idle", glyph: "[-]", word: "web data is off - no currency values" });
  assert.deepEqual(off.rows, []);
  assert.deepEqual(p.ratesView(with_({ rates: {}, refreshing: true })).pill,
    { state: "running", glyph: "[>]", word: "getting currency values from poe.ninja..." });
  assert.deepEqual(p.ratesView(with_({ rates: {}, last_error: "HTTP 503", next_refresh_in_s: 2700 })).pill,
    { state: "blocked", glyph: "[#]", word: "can't reach poe.ninja - trying again in 45 min" });
  assert.deepEqual(p.ratesView(with_({ rates: {}, age_s: null })).pill,
    { state: "pending", glyph: "[ ]", word: "currency values arrive within a minute" });
  assert.deepEqual(p.ratesView(null).pill,
    { state: "pending", glyph: "[ ]", word: "currency values not loaded yet" });
  for (const v of [p.ratesView(null), off]) {
    assert.ok(!/HTTP|token|core|undefined|null|!/.test(JSON.stringify(v.pill)));
  }
});

test("conversion: about N primary, omitted when it can't be honest", () => {
  assert.equal(p.aboutText(RATES, 400, "exalted"), "about 1 Divine Orb");
  assert.equal(p.aboutText(RATES, 5, "Exalted Orb"), "about 0.0125 Divine Orb");
  assert.equal(p.aboutText(RATES, 2, "annulment"), "about 0.625 Divine Orb");
  assert.equal(p.aboutText(RATES, 3, "divine"), "");      // already the primary
  assert.equal(p.aboutText(RATES, 3, "unknown-orb"), ""); // no rate: no guess
  assert.equal(p.aboutText(RATES, null, "exalted"), "");
  assert.equal(p.aboutText(with_({ rates: {} }), 3, "exalted"), "");
  assert.equal(p.aboutText(null, 3, "exalted"), "");
  assert.equal(p.aboutText(with_({ primary: null }), 3, "exalted"), "");
});

test("trade row conversion uses the asked price; age goes in the tooltip", () => {
  assert.deepEqual(p.tradeAbout({ price_amount: 200, price_currency: "exalted" }, RATES),
    { text: "about 0.5 Divine Orb", title: "poe.ninja rate, updated 12 min ago" });
  assert.deepEqual(p.tradeAbout({ kind: "exchange", want_amount: 3, item: "Divine Orb",
                                  price_amount: 1200, price_currency: "exalted" }, RATES).text,
    "about 3 Divine Orb");
  assert.deepEqual(p.tradeAbout({ item: "Plain Belt" }, RATES), { text: "", title: "" });
});

const PRICE = {
  id: 4, at: 1000, expires_at: 1020, status: "done", league: "Dawn", count: 5,
  item: { name: "Doom Grip" },
  listings: [{ amount: 10, currency: "exalted" }, { amount: 1, currency: "divine" }],
  text: { head: "Price: Doom Grip", item: "Doom Grip", line: "5 listed, ~10 exalted",
          detail: "Lowest 10 exalted", sentence: "5 listed in Dawn. ...",
          rows: ["10 exalted", "1 divine"] }
};

test("price section: core words, conversions per listing, state word", () => {
  const v = p.priceView(PRICE, RATES, () => "14:05");
  assert.equal(v.item, "Doom Grip");
  assert.equal(v.sentence, "5 listed in Dawn. ...");
  assert.deepEqual(v.badge, { state: "done", glyph: "[+]", word: "priced" });
  assert.deepEqual(v.rows, [{ text: "10 exalted", about: "about 0.025 Divine Orb" },
                            { text: "1 divine", about: "" }]);
  assert.equal(v.when, "Checked at 14:05");
  assert.equal(v.key, "4");
  const states = { searching: ["running", "[>]", "searching"],
                   waiting: ["pending", "[ ]", "waiting"],
                   off: ["idle", "[-]", "web data off"],
                   error: ["failed", "[x]", "not priced"] };
  Object.keys(states).forEach((s) => {
    const b = p.priceView(Object.assign({}, PRICE, { status: s }), RATES, null).badge;
    assert.deepEqual([b.state, b.glyph, b.word], states[s]);
  });
  const retry = p.priceView(Object.assign({}, PRICE, { status: "error", error: "not an item" }), RATES, null);
  assert.deepEqual(retry.badge, { state: "blocked", glyph: "[#]", word: "can't price" });
  const noBase = p.priceView(Object.assign({}, PRICE, { status: "error", error: "no base type" }), RATES, null);
  assert.deepEqual(noBase.badge, { state: "blocked", glyph: "[#]", word: "can't price" });
  // PRICE-1-COPY F2: off for a missing contact never reads "web data off"
  const noContact = p.priceView(Object.assign({}, PRICE, { status: "off", error: "contact not set" }), RATES, null);
  assert.deepEqual(noContact.badge, { state: "idle", glyph: "[-]", word: "no contact" });
  assert.equal(p.priceView(null, RATES, null), null);
  assert.equal(p.priceView({ id: 1 }, RATES, null), null); // no text from the core
});

test("price empty state says what will appear, web data on or off", () => {
  // PRICE-TRADE-LINK: the trade link is built offline, so web data does not gate it
  // OVL-KEYS-WEB: the bound item key comes in as an argument
  const want = "Nothing checked yet. After you check an item with Ctrl+Alt+K, a link to " +
    "search for it on the official trade site shows here.";
  assert.equal(p.priceEmpty(false, "Ctrl+Alt+K"), want);
  assert.equal(p.priceEmpty(true, "Ctrl+Alt+K"), want);
});

test("price empty state names no key while none is bound", () => {
  const want = "Nothing checked yet. After you check an item with the item check key, a " +
    "link to search for it on the official trade site shows here.";
  assert.equal(p.priceEmpty(false), want);
  assert.equal(p.priceEmpty(true, ""), want);
  assert.equal(p.priceEmpty(true, null), want);
});

const LINK = "https://www.pathofexile.com/trade2/search/poe2/Dawn?q=%7B%22query%22%3A%7B%7D%7D";

test("trade link: shown only for a trade2 search URL, opens in the browser", () => {
  const card = { id: 7, status: "link", url: LINK, at: 1, listings: [],
    text: { item: "Doom Grip", sentence: "A trade site search for this item in Dawn is ready.",
            rows: [] } };
  const v = p.priceView(card, RATES, null);
  assert.deepEqual(v.badge, { state: "done", glyph: "[+]", word: "link ready" });
  assert.deepEqual(v.link, { href: LINK, text: "Search the official trade site for Doom Grip",
    label: "Search the official trade site for Doom Grip (opens in a new tab)" });
  assert.deepEqual(v.rows, []);
  for (const bad of [undefined, null, "", "http://www.pathofexile.com/trade2/search/poe2/D?q=1",
    "https://evil.example/trade2/search/poe2/D?q=1", "javascript:alert(1)",
    // split so the no-trade-endpoint scan (tests/test_trade_link.py) stays strict
    "https://www.pathofexile.com/api" + "/trade2/search/poe2/D", "https://www.pathofexile.com.evil/trade2/search/poe2/D?q=1",
    "https://www.pathofexile.com/trade2/search/poe2/D?q=1 x"]) {
    const w = p.priceView(Object.assign({}, card, { url: bad }), RATES, null);
    assert.equal(w.link, null, String(bad));
  }
  const plain = p.priceView(Object.assign({}, card, { status: "error", error: "x" }), RATES, null);
  assert.equal(plain.link, null);
  assert.equal(p.tradeLink("x"), "");
  assert.equal(p.tradeLink(LINK), LINK);
});

/* TC-UPGRADE (decision 0017 item 3): the item check's upgrade-search link. */
const UP_URL = "https://www.pathofexile.com/trade2/search/poe2/Standard?q=%7B%22query%22%3A%7B%7D%7D";

test("upgrade view: the worn base, link text and label", () => {
  const v = p.upgradeView({ slot: "Gloves", base: "Example Gloves", source: "equipped",
                            rarity: "rare", league: "Standard", url: UP_URL });
  assert.deepEqual(v, {
    href: UP_URL,
    sentence: "Your build wears Example Gloves in Gloves, so this finds rare items of " +
              "that base. It matches base type and rarity only, not stats.",
    text: "Search the official trade site for rare Example Gloves (Gloves)",
    label: "Search the official trade site for rare Example Gloves (Gloves) (opens in a new tab)"
  });
});

test("upgrade view: an empty slot uses the checked item's base", () => {
  const v = p.upgradeView({ slot: "Ring 1", base: "Example Ring", source: "item", url: UP_URL });
  assert.equal(v.sentence, "Your build has nothing in Ring 1, so this uses the checked " +
    "item's base, Example Ring. It matches base type and rarity only, not stats.");
  assert.equal(v.text, "Search the official trade site for rare Example Ring (Ring 1)");
  assert.ok(v.label.startsWith(v.text)); // visible text inside the label (SC 2.5.3)
});

test("upgrade view: no view without a valid trade2 search URL, base or slot", () => {
  const ok = { slot: "Gloves", base: "Example Gloves", source: "equipped", url: UP_URL };
  assert.equal(p.upgradeView(null), null);
  assert.equal(p.upgradeView("x"), null);
  for (const bad of ["https://example.org/?q=1", "javascript:alert(1)", UP_URL + "&x=1", 5]) {
    assert.equal(p.upgradeView(Object.assign({}, ok, { url: bad })), null, String(bad));
  }
  assert.equal(p.upgradeView(Object.assign({}, ok, { base: " " })), null);
  assert.equal(p.upgradeView(Object.assign({}, ok, { slot: null })), null);
});

/* UTIL-MOVERS: the week's biggest price changes from the cached overviews. */
test("price movers: words not colour, hidden while web data is off", () => {
  const doc = {
    web_data: true,
    movers: {
      up: [{ name: "Greater Essence of Ruin", type: "Essences", value: 0.35,
             unit: "Divine Orb", change: 61 }],
      down: [{ name: "Hollow Crown", type: "UniqueArmours", value: 1234.5,
               unit: "Divine Orb", change: -25.5 }]
    }
  };
  const v = p.moversView(doc);
  assert.equal(v.show, true);
  assert.equal(v.empty, "");
  assert.deepEqual(v.up, [{ name: "Greater Essence of Ruin", change: "up 61%",
                            value: "0.35 Divine Orb" }]);
  assert.deepEqual(v.down, [{ name: "Hollow Crown", change: "down 25.5%",
                              value: "1,235 Divine Orb" }]);
  assert.equal(p.moversView({ web_data: false, movers: doc.movers }).show, false);
  assert.equal(p.moversView(null).show, false);
  const none = p.moversView({ web_data: true, movers: { up: [], down: [] } });
  assert.equal(none.empty,
    "No price changes to show yet. They appear after the next hourly price update.");
  const odd = p.moversView({ web_data: true, movers: { up: [{ change: 5 }], down: "x" } });
  assert.deepEqual(odd.up, [{ name: "Unnamed item", change: "up 5%", value: "" }]);
  assert.deepEqual(odd.down, []);
  const flat = p.moversView({ web_data: true, movers: { up: [{ name: "A", change: 0.2 }],
                                                        down: [{ name: "B", change: "x" }] } });
  assert.equal(flat.up[0].change, "no change");
  assert.equal(flat.down[0].change, "no change");
});

/* MATH-VALUE-UI: the item check's value doc (MATH-VALUE) -> card words */
const VALUE = {
  price: { kind: "price", amount: 4, currency: "exalted", name: "Exalted Orb" },
  primary: "divine", primary_name: "Divine Orb", price_primary: 0.01,
  score_per_primary: 2500, stale: false, credit: "Prices: poe.ninja"
};

test("value view: listed price, its primary value and points per unit", () => {
  assert.deepEqual(p.valueView(VALUE), {
    sentence: "Asking price: 4 Exalted Orb, about 0.01 Divine Orb.",
    per: "2,500 points per Divine Orb.",
    stale: "",
    credit: "Prices: poe.ninja"
  });
  const bo = p.valueView(Object.assign({}, VALUE, {
    price: { kind: "b/o", amount: 0.5, currency: "divine", name: "Divine Orb" },
    price_primary: 0.5, score_per_primary: 1, stale: true }));
  assert.equal(bo.sentence, "Buyout price: 0.5 Divine Orb.");
  assert.equal(bo.per, "1 point per Divine Orb.");
  assert.equal(bo.stale, "These currency values may be out of date.");
});

test("value view: no rates or no rate for the currency say so honestly", () => {
  const none = p.valueView({ price: { kind: "price", amount: 4, currency: "exalted",
    name: "exalted" }, primary: null, primary_name: null, price_primary: null,
    score_per_primary: null, stale: true, credit: null });
  assert.equal(none.sentence, "Asking price: 4 Exalted. No currency values are saved yet, " +
    "so AshLight can't compare the item's price with its points.");
  assert.equal(none.per, "");
  assert.equal(none.stale, "");
  assert.equal(none.credit, "");
  const miss = p.valueView(Object.assign({}, VALUE, { price: { kind: "price", amount: 3,
    currency: "regal", name: "regal" }, price_primary: null, score_per_primary: null }));
  assert.equal(miss.sentence, "Asking price: 3 Regal. There is no saved value for Regal yet, " +
    "so AshLight can't compare the item's price with its points.");
  assert.equal(miss.credit, "");
  const neg = p.valueView(Object.assign({}, VALUE, { score_per_primary: -120.5 }));
  assert.equal(neg.per, "-121 points per Divine Orb.");
});

test("value view: null for no doc or a malformed price", () => {
  assert.equal(p.valueView(null), null);
  assert.equal(p.valueView("x"), null);
  assert.equal(p.valueView({}), null);
  for (const bad of [0, -1, NaN, Infinity, "4"]) {
    assert.equal(p.valueView(Object.assign({}, VALUE, {
      price: Object.assign({}, VALUE.price, { amount: bad }) })), null, String(bad));
  }
  assert.equal(p.valueView(Object.assign({}, VALUE, {
    price: Object.assign({}, VALUE.price, { currency: "" }) })), null);
});
