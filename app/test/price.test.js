"use strict";
/* PRICE-1-UI (decision 0016): the overlay card slot follows the core's
   chosen card (server/al/text/overlaycard.py overlay_card), clipped by
   format.js cardText; an older core without "card" keeps the item check
   path. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fmt = require("../shared/format.js");
const gate = require("../shared/render_gate.js");

const base = {
  zone: "Clearfell", in_hideout: false, zone_entered_at: 1000, level: 3, deaths: 1,
  version: 9,
  trade_requests: [{ id: 1, from: "Quietfox", item: "Plain Belt", price_amount: 5,
                     price_currency: "exalted" }],
  eval: null,
  price: null
};

const merged = Object.assign({}, base, {
  card: { kind: "merged", head: "Upgrade +12 vs Gloves", line2: "5 listed, ~12 exalted",
          line3: "+35 to maximum Life", verdict: "upgrade", expires_at: 1020 }
});

test("cardText clips each line to 26 and keeps the verdict", () => {
  const long = { kind: "price", head: "Price: " + "x".repeat(60), line2: "a", line3: "b",
                 verdict: "price", expires_at: 5 };
  const c = fmt.cardText(long);
  assert.equal(c.head.length, 26);
  assert.ok(c.head.endsWith("..."));
  assert.deepEqual([c.line2, c.line3, c.verdict], ["a", "b", "price"]);
  assert.deepEqual(fmt.cardText(null), { head: "", line2: "", line3: "", verdict: "" });
  assert.deepEqual(fmt.cardText({ head: "" }), { head: "", line2: "", line3: "", verdict: "" });
});

test("merged card takes the slot while fresh; trade card waits", () => {
  const m = gate.hudModel(merged, 1005, "live");
  assert.equal(m.evalHead, "Upgrade +12 vs Gloves");
  assert.equal(m.evalItem, "5 listed, ~12 exalted");
  assert.equal(m.evalLine, "+35 to maximum Life");
  assert.equal(m.evalVerdict, "upgrade");
  assert.equal(m.tradeFrom, "");
  assert.equal(m.tradeItem, "");
  const later = gate.hudModel(merged, 1020, "live");
  assert.equal(later.evalHead, "");
  assert.equal(later.tradeFrom, "Trade: Quietfox");
});

test("price-only card shows its three lines", () => {
  const s = Object.assign({}, base, {
    card: { kind: "price", head: "Price: Doom Grip", line2: "Prices in 8 s",
            line3: "Waiting for the trade site", verdict: "price", expires_at: 1020 } });
  const m = gate.hudModel(s, 1001, "live");
  assert.deepEqual([m.evalHead, m.evalItem, m.evalLine, m.evalVerdict],
    ["Price: Doom Grip", "Prices in 8 s", "Waiting for the trade site", "price"]);
});

test("expiry timer follows the card, and a null card shows nothing", () => {
  assert.equal(gate.msUntilEvalExpires(merged, 1019.5), 500);
  assert.equal(gate.msUntilEvalExpires(merged, 1020), null);
  const none = Object.assign({}, base, { card: null,
    eval: { ok: true, verdict: "upgrade", at: 1000, expires_at: 1020,
            text: { head: "Upgrade +1 vs Belt", item: "a", line: "b" } } });
  // the core said "no card": a stale eval field is not shown on its own
  assert.equal(gate.hudModel(none, 1005, "live").evalHead, "");
  assert.equal(gate.msUntilEvalExpires(none, 1005), null);
});

test("an older core without card keeps the item check path", () => {
  const old = Object.assign({}, base, {
    eval: { ok: true, verdict: "upgrade", at: 1000, expires_at: 1020,
            text: { head: "Upgrade +1 vs Belt", item: "Plain Belt", line: "+1 to Life" } } });
  delete old.card;
  const m = gate.hudModel(old, 1005, "live");
  assert.deepEqual([m.evalHead, m.evalItem, m.evalLine], ["Upgrade +1 vs Belt", "Plain Belt", "+1 to Life"]);
});

test("a repaint happens only when a card line changes", () => {
  const a = gate.hudModel(merged, 1005, "live");
  const b = gate.hudModel(Object.assign({}, merged, { version: 10 }), 1006, "live");
  assert.equal(gate.shouldRender(a, b), false);
  const c = gate.hudModel(Object.assign({}, merged, {
    card: Object.assign({}, merged.card, { line2: "5 listed, ~13 exalted" }) }), 1006, "live");
  assert.deepEqual(gate.changedFields(a, c), ["evalItem"]);
});
