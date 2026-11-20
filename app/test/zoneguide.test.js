/* ZONE-GUIDE (decision 0043): exact rows of the dashboard zone guide
   (web/zoneguide.js). The core sends the sentences; this only lays them
   out, short part first, the rest folded. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const zg = web.load("zoneguide.js");

const GUIDE = {
  kind: "campaign", zone: "Clearfell", act: "Act 1",
  objective: "Find the way on.",
  optional: [{ kind: "resist", text: "Rare boss: resist." }, { kind: "odd", text: "X." }],
  layout: "Cave by the waypoint.", next: "The Grelwood", waypoint: "Waypoint in this zone.",
  advice: { mode: "clear", text: "You are 3 levels under this zone." },
  quest: { act: "Act 1", steps: [{}, {}], steps_done: 1,
           bonus_text: "Act 1 bonus zones entered: 0 of 2.",
           missed: [{ text: "Act 0: not entered yet: Nowhere." }] },
  source: "Own notes."
};

test("zone guide: short rows first, the rest folded, empty fields left out", () => {
  const rows = zg.rows(GUIDE);
  assert.deepEqual(rows.map((r) => (r.more ? "+ " : "") + r.label + r.text), [
    "Act 1: Clearfell",
    "Goal: Find the way on.",
    "Bonus: Rare boss: resist.",
    "You are 3 levels under this zone.",
    "Next zone: The Grelwood",
    "+ Waypoint in this zone.",
    "+ Bonus: X.",
    "+ Layout: Cave by the waypoint.",
    "+ Act 1 main path: 1 of 2 zones passed.",
    "+ Act 1 bonus zones entered: 0 of 2.",
    "+ Act 0: not entered yet: Nowhere.",
    "+ Own notes."]);
  assert.equal(rows[3].cls, "zg-advice zg-clear");
  assert.equal(rows[6].cls, "zg-bonus zg-other");
});

test("zone guide: nothing for no guide", () => {
  assert.deepEqual(zg.rows(null), []);
  assert.deepEqual(zg.rows({ zone: "" }), []);
  assert.deepEqual(zg.rows({ zone: "Alpine Ridge", act: "Endgame map", quest: null })
    .map((r) => r.text), ["Endgame map: Alpine Ridge"]);
});

function fakeDoc() {
  function el(tag) {
    return {
      tag, children: [], className: "", textContent: "", open: false, hidden: true,
      appendChild(c) { this.children.push(c); return c; },
      removeChild(c) { this.children.splice(this.children.indexOf(c), 1); },
      get firstChild() { return this.children[0] || null; },
      addEventListener() {}
    };
  }
  const slot = el("div");
  return { slot, createElement: el, createTextNode: (t) => ({ text: t }),
           getElementById: (id) => (id === "zone-guide" ? slot : null) };
}

test("zone guide: paints the #zone-guide slot, folding the extra rows", () => {
  const doc = fakeDoc();
  zg.paint(doc, { zone_guide: GUIDE });
  const body = doc.slot.children[0];
  assert.equal(doc.slot.hidden, false);
  assert.equal(body.children.filter((c) => c.tag === "p").length, 5);
  const fold = body.children.find((c) => c.tag === "details");
  assert.equal(fold.children[0].textContent, zg.MORE);
  assert.equal(fold.children.length, 8);
  zg.paint(doc, { zone_guide: null });
  assert.equal(doc.slot.hidden, true);
});

test("zone guide: uses ALTabs.fill when the page provides it (the Run tab slot)", () => {
  const doc = fakeDoc();
  const calls = [];
  global.self = { ALTabs: { fill: (d, id, node) => calls.push([id, node.className]) } };
  try {
    zg.paint(doc, { zone_guide: Object.assign({}, GUIDE, { zone: "Mud Burrow" }) });
  } finally {
    delete global.self;
  }
  assert.deepEqual(calls, [["zone-guide", "zone-guide-body"]]);
  assert.equal(doc.slot.children.length, 0);
});
