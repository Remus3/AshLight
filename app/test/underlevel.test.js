/* UTIL-UNDERLEVEL: the under-level word in the overlay HUD status slot
   (app/shared/render_gate.js). The core sends the word; this only places it. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const gate = require("../shared/render_gate.js");

const snap = {
  zone: "Clearfell", in_hideout: false, zone_entered_at: 1000,
  level: 3, deaths: 1, version: 7
};

test("the under-level word fills the status slot", () => {
  const live = gate.hudModel(snap, 1000, "live");
  const under = gate.hudModel({ ...snap, underlevel: { gap: 4, word: "4 lv under" } }, 1000, "live");
  assert.equal(live.under, "");
  assert.equal(under.under, "4 lv under");
  assert.deepEqual(gate.changedFields(live, under), ["under"]);
  assert.equal(gate.shouldRender(live, under), true);
  assert.equal(gate.statusText(under), "4 lv under");
});

test("slot order: connection, log state, trade count, under-level, AFK", () => {
  const both = gate.hudModel({ ...snap, afk: true, underlevel: { word: "4 lv under" } }, 1000, "live");
  assert.equal(gate.statusText(both), "4 lv under");
  assert.equal(gate.statusText({ ...both, trades: "2 trades" }), "2 trades");
  assert.equal(gate.statusText({ ...both, log: "waiting for log" }), "waiting for log");
  assert.equal(gate.statusText({ ...both, status: "offline" }), "offline");
});

test("no word, a bad word or one over 15 characters shows nothing", () => {
  assert.equal(gate.hudModel({ ...snap, underlevel: null }, 1000, "live").under, "");
  assert.equal(gate.hudModel({ ...snap, underlevel: { word: 5 } }, 1000, "live").under, "");
  assert.equal(gate.hudModel({ ...snap, underlevel: { word: "1234567890123456" } }, 1000,
    "live").under, "");
  assert.equal(gate.hudModel(null, 0).under, "");
});
