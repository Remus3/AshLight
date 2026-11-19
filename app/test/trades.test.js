"use strict";
/* UX-REVIEW F6 (2026-11-17): the dashboard's polite live-region sentence
   for new trade requests (web/trades.js). Said only when the set of open
   trade ids grows; never on first paint, a dismiss or an expiry. */
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const t = web.load("trades.js");

const row = (id, from) => ({ id: id, from: from });

test("ids: the open trade ids in order", () => {
  assert.deepEqual(t.tradeIds([row(3, "A"), row(5, "B")]), [3, 5]);
  assert.deepEqual(t.tradeIds([]), []);
  assert.deepEqual(t.tradeIds(null), []);
});

test("one new request names the player", () => {
  assert.equal(t.newTradeSentence([1], [row(1, "A"), row(2, "Quietfox")]),
    "New trade request from Quietfox.");
  assert.equal(t.newTradeSentence([], [row(4, "Quietfox")]),
    "New trade request from Quietfox.");
});

test("one new request without a name still says so", () => {
  assert.equal(t.newTradeSentence([], [row(4, "")]), "New trade request.");
  assert.equal(t.newTradeSentence([], [{ id: 4 }]), "New trade request.");
});

test("several new requests are counted", () => {
  assert.equal(t.newTradeSentence([1], [row(1, "A"), row(2, "B"), row(3, "C")]),
    "2 new trade requests.");
});

test("no sentence on first paint, shrink or no change", () => {
  assert.equal(t.newTradeSentence(null, [row(1, "A")]), "");
  assert.equal(t.newTradeSentence([1, 2], [row(2, "B")]), "");
  assert.equal(t.newTradeSentence([1, 2], [row(1, "A"), row(2, "B")]), "");
  assert.equal(t.newTradeSentence([1], []), "");
});

test("a new id replacing an expired one still counts as new", () => {
  assert.equal(t.newTradeSentence([1], [row(2, "B")]), "New trade request from B.");
});

/* Design review 2026-11-17 F2: a repeated sentence is cleared first so it
   is said again; a shrinking set clears the stale sentence. */
function fakeRegion(text) {
  const writes = [];
  let value = text;
  return {
    writes: writes,
    get textContent() { return value; },
    set textContent(v) { value = v; writes.push(v); }
  };
}

test("showStatus: a new request writes its sentence once", () => {
  const el = fakeRegion("");
  t.showStatus(el, [1], [row(1, "A"), row(2, "B")]);
  assert.deepEqual(el.writes, ["New trade request from B."]);
});

test("showStatus: the same sentence again is cleared, then written", () => {
  const el = fakeRegion("New trade request.");
  t.showStatus(el, [1], [row(1, ""), row(2, "")]);
  assert.deepEqual(el.writes, ["", "New trade request."]);
});

test("showStatus: a shrinking set clears the old sentence", () => {
  const el = fakeRegion("New trade request from B.");
  t.showStatus(el, [1, 2], [row(1, "A")]);
  assert.deepEqual(el.writes, [""]);
});

test("showStatus: first paint and no change write nothing", () => {
  const el = fakeRegion("Not dismissed. Try again.");
  t.showStatus(el, null, [row(1, "A")]);
  t.showStatus(el, [1], [row(1, "A")]);
  assert.deepEqual(el.writes, []);
  const empty = fakeRegion("");
  t.showStatus(empty, [1], []);
  assert.deepEqual(empty.writes, []);
});
