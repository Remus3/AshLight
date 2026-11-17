/* UTIL-MULTICHAR: exact output of the per-character selector helpers
   (web/chars.js, decision 0037). Synthetic names only. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const ch = require("../../web/chars.js");

const SNAP = {
  character: "Sable", "class": "Witch", level: 4, deaths: 2, level_ups: 3,
  pace: { text: "Pace: now." }, underlevel: { text: "3 levels under this zone." },
  acts: { splits: [{ key: "G1" }], zones: [{ name: "Clearfell" }], current: "G1",
    empty_text: "No act times yet." },
  characters: [
    { name: "Sable", current: true, "class": "Witch", level: 4, deaths: 2, level_ups: 3,
      pace: { text: "Pace: now." }, acts: { splits: [{ key: "G1" }] } },
    { name: "Quill", current: false, "class": "Monk", level: 20, deaths: 5, level_ups: 2,
      pace: { text: "" }, acts: { splits: [{ key: "G1" }, { key: "G2" }] } }],
  run_history: { on: true, best: [{ key: "G1" }], by_character: {
    Quill: { on: true, best: [{ key: "G2" }] }, Old: { on: true, best: [] } } },
};

test("chars: names list the current one first, then live, then saved only", () => {
  assert.deepEqual(ch.names(SNAP), [{ name: "Sable", current: true },
    { name: "Quill", current: false }, { name: "Old", current: false }]);
  assert.deepEqual(ch.names(null), []);
});

test("chars: names are capped at 12", () => {
  const by = {};
  for (let i = 0; i < 20; i++) { by["C" + i] = { best: [] }; }
  assert.equal(ch.names({ characters: [], run_history: { by_character: by } }).length, ch.MAX);
  assert.equal(ch.MAX, 12);
});

test("chars: view keeps the snapshot for the current character", () => {
  assert.equal(ch.view(SNAP, ""), SNAP);
  assert.equal(ch.view(SNAP, "Sable"), SNAP);
  assert.equal(ch.view(SNAP, "Nobody"), SNAP);
});

test("chars: view swaps in a live character's numbers", () => {
  const v = ch.view(SNAP, "Quill");
  assert.equal(v.character, "Quill");
  assert.equal(v["class"], "Monk");
  assert.equal(v.level, 20);
  assert.equal(v.deaths, 5);
  assert.equal(v.acts.splits.length, 2);
  assert.deepEqual(v.run_history.best, [{ key: "G2" }]);
  assert.equal(v.underlevel, null);
  assert.equal(v.who_note, " (not playing)");
  assert.equal(SNAP.character, "Sable"); // the snapshot is not changed
});

test("chars: a saved-only character shows its run history, no live numbers", () => {
  const v = ch.view(SNAP, "Old");
  assert.equal(v.level, null);
  assert.equal(v.deaths, 0);
  assert.deepEqual(v.acts.splits, []);
  assert.deepEqual(v.acts.zones, []);
  assert.equal(v.acts.empty_text, "No act times yet.");
  assert.deepEqual(v.run_history.best, []);
  assert.equal(v.who_note, " (history only)");
  assert.equal(SNAP.acts.splits.length, 1);
});

test("chars: a name past the 12-name cap is not picked", () => {
  const by = {};
  for (let i = 0; i < 20; i++) { by["C" + i] = { best: [] }; }
  const snap = { character: "Sable", characters: [], run_history: { by_character: by } };
  assert.equal(ch.view(snap, "C19"), snap);
  assert.notEqual(ch.view(snap, "C0"), snap);
});
