/* HUD-ACT: exact output of the dashboard act times and zone level helpers
   (web/acts.js). The core sends the sentences; these only format. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const a = require("../../web/acts.js");

const ACTS = {
  splits: [
    { key: "G1", label: "Act 1", started_at: 100, ended_at: 1300, current: false, partial: true },
    { key: "G2", label: "Act 2", started_at: 1300, ended_at: null, current: true, partial: false }
  ],
  zones: [
    { name: "Vastiri Outskirts", level: 16, town: false, here: true },
    { name: "Ardura Caravan", level: 16, town: true, here: false }
  ],
  zones_act: "Act 2",
  levels: true,
  source: "Zone levels: RePoE fork export, downloaded when AshLight was built. Game data (c) Grinding Gear Games.",
  empty_text: "No act times yet. They start by themselves when you enter a campaign zone.",
  no_levels_text: "Zone levels aren't downloaded yet. Run AshLight's build step (scripts/build.ps1) to get them.",
  no_zones_text: "Zone levels show here while you are in a campaign act.",
  partial_text: "partial: counted from when AshLight started"
};

test("duration matches the zone timer form", () => {
  assert.equal(a.duration(0), "0:00");
  assert.equal(a.duration(59.9), "0:59");
  assert.equal(a.duration(1200), "20:00");
  assert.equal(a.duration(3725), "1:02:05");
  assert.equal(a.duration(-5), "0:00");
  assert.equal(a.duration(null), "--:--");
  assert.equal(a.duration(NaN), "--:--");
});

test("splitRows: closed and open splits, exact", () => {
  assert.deepEqual(a.splitRows(ACTS, 4900), [
    { label: "Act 1", note: "partial: counted from when AshLight started", time: "20:00", total: "20:00", current: false },
    { label: "Act 2", note: "", time: "1:00:00", total: "1:20:00", current: true }
  ]);
  assert.deepEqual(a.splitRows(null, 1), []);
  assert.deepEqual(a.splitRows({ splits: [] }, 1), []);
});

test("zoneRows, zonesTitle and zonesEmpty, exact", () => {
  assert.deepEqual(a.zoneRows(ACTS), [
    { name: "Vastiri Outskirts", level: "16", note: "you are here", here: true },
    { name: "Ardura Caravan", level: "16", note: "town", here: false }
  ]);
  assert.equal(a.zonesTitle(ACTS), "Zone levels in Act 2");
  assert.equal(a.zonesTitle({}), "Zone levels");
  assert.equal(a.zonesEmpty(ACTS), "");
  assert.equal(a.zonesEmpty(Object.assign({}, ACTS, { levels: false, zones: [] })),
    "Zone levels aren't downloaded yet. Run AshLight's build step (scripts/build.ps1) to get them.");
  assert.equal(a.zonesEmpty(Object.assign({}, ACTS, { zones: [] })),
    "Zone levels show here while you are in a campaign act.");
  assert.equal(a.zonesEmpty(null), "");
});

/* A minimal DOM stand-in: enough for paint() (getElementById, createElement,
   textContent, children, querySelector on data-current, attributes). */
function fakeDoc(ids) {
  function node(tag) {
    const n = { tagName: tag, children: [], attrs: {}, hidden: false, className: "",
      _text: "",
      setAttribute(k, v) { this.attrs[k] = v; },
      appendChild(c) { this.children.push(c); return c; },
      querySelector(sel) {
        return this.children.find((c) => sel === "tr[data-current]" && "data-current" in c.attrs) || null;
      },
      get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); },
      set textContent(v) { this._text = v; this.children = []; }
    };
    return n;
  }
  const els = {};
  ids.forEach((id) => { els[id] = node("x"); });
  return { getElementById: (id) => els[id], createElement: node, els };
}

test("paint: one note per row, live tick, first-run heading hidden", () => {
  const doc = fakeDoc(["acts-rows", "acts-table", "acts-empty", "zones-title", "zones-rows",
    "zones-table", "zones-empty", "zones-source"]);
  const live = Object.assign({}, ACTS, { splits: [
    { key: "G3", label: "Act 3", started_at: 0, ended_at: null, current: true, partial: true }] });
  a.paint(doc, live, 65, true);
  const rows = doc.els["acts-rows"].children;
  assert.equal(rows.length, 1);
  assert.equal(rows[0].children[0].textContent,
    "Act 3 (now, partial: counted from when AshLight started)");
  assert.equal(rows[0].children[1].textContent, "1:05");
  a.paint(doc, live, 130, false);
  assert.equal(rows[0].children[1].textContent, "2:10");
  assert.equal(rows[0].children[2].textContent, "2:10");
  assert.equal(doc.els["zones-title"].textContent, "Zone levels in Act 2");
  assert.equal(doc.els["zones-title"].hidden, false);
  assert.equal(doc.els["zones-rows"].children[0].children[0].textContent,
    "Vastiri Outskirts (you are here)");
  assert.equal(doc.els["zones-source"].textContent, ACTS.source);
  // first run, no data: the act empty text and the download hint, no heading
  const none = Object.assign({}, ACTS, { splits: [], zones: [], levels: false, source: null,
    zones_act: null });
  a.paint(doc, none, 1, true);
  assert.equal(doc.els["acts-table"].hidden, true);
  assert.equal(doc.els["acts-empty"].textContent, ACTS.empty_text);
  assert.equal(doc.els["zones-title"].hidden, true);
  assert.equal(doc.els["zones-empty"].textContent, ACTS.no_levels_text);
  assert.equal(doc.els["zones-source"].hidden, true);
});
