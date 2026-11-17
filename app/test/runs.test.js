/* UTIL-MAPS / UTIL-DEATHS: exact output of the dashboard map run and death
   recap helpers (web/runs.js). The core sends the sentences; these only
   format. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const r = require("../../web/runs.js");

const MAPS = {
  count: 2, done: 1,
  current: { name: "Savannah", area_level: 66, time_s: 300, deaths: 0, inside: true },
  recent: [{ name: "Crypt", area_level: 65, time_s: 390, deaths: 1 }],
  avg_s: 390, avg_text: "Average map: 6:30 over 1 finished map.",
  deaths_text: "1 death in maps.",
  empty_text: "No maps yet. Map times start by themselves when you open a map."
};

test("duration matches the zone timer form", () => {
  assert.equal(r.duration(0), "0:00");
  assert.equal(r.duration(390), "6:30");
  assert.equal(r.duration(3725), "1:02:05");
  assert.equal(r.duration(null), "--:--");
});

test("liveTime counts up only while the player is in the map", () => {
  assert.equal(r.liveTime(MAPS.current, 1000, 1010), 310);
  assert.equal(r.liveTime(Object.assign({}, MAPS.current, { inside: false }), 1000, 1010), 300);
  assert.equal(r.liveTime(null, 1000, 1010), null);
});

test("mapRows: open map first, then finished maps", () => {
  assert.deepEqual(r.mapRows(MAPS, 1000, 1005), [
    { name: "Savannah", level: "66", time: "5:05", deaths: "0 deaths",
      note: "now", current: true },
    { name: "Crypt", level: "65", time: "6:30", deaths: "1 death",
      note: "", current: false }
  ]);
  const out = Object.assign({}, MAPS, {
    current: Object.assign({}, MAPS.current, { inside: false }) });
  assert.equal(r.mapRows(out, 1000, 1005)[0].note, "paused");
  const nolevel = { current: null, recent: [{ name: "Crypt", area_level: null, time_s: 60, deaths: 0 }] };
  assert.equal(r.mapRows(nolevel, 0, 0)[0].level, "unknown");
  assert.equal(r.levelText(undefined), "unknown");
  assert.equal(r.levelText(65), "65");
  assert.deepEqual(r.mapRows(null, 0, 0), []);
});

test("deathLines prints the core's sentences in order", () => {
  const recap = { recent: [
    { text: "Died in Crypt (area level 65), 0:05 into the zone." },
    { text: "Died in Savannah (area level 66) at level 72." }
  ], worst_text: "", empty_text: "No deaths this session." };
  assert.deepEqual(r.deathLines(recap), [
    "Died in Crypt (area level 65), 0:05 into the zone.",
    "Died in Savannah (area level 66) at level 72."
  ]);
  assert.deepEqual(r.deathLines(null), []);
});
