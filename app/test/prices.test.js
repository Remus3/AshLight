"use strict";
/* DATA-NINJA-UI / PRICE-1-UI (decision 0015): the dashboard's pure view
   helpers in web/prices.js - the web-data opt-in words, the poe.ninja rates
   panel, "about N <primary>" conversions and the price check section.
   Fixture values are invented. */
const test = require("node:test");
const assert = require("node:assert/strict");
const p = require("../../web/prices.js");

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
    status: "Web data is on. Currency values come from poe.ninja about once an hour. " +
            "The trade site is asked only when you check an item." });
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
  assert.equal(p.priceView(null, RATES, null), null);
  assert.equal(p.priceView({ id: 1 }, RATES, null), null); // no text from the core
});

test("price empty state says what will appear, and why not when off", () => {
  assert.equal(p.priceEmpty(false),
    "Prices need web data, which is off. Turn it on under Prices and web data.");
  assert.equal(p.priceEmpty(true),
    "Nothing priced yet. Check an item with Alt+Shift+E and its prices from the official " +
    "trade site show here.");
});
