/* NEWBIE-HINTS / UTIL-MAP-LADDER: exact output of the dashboard helpers
   (web/hints.js, web/runs.js ladderRows). The core sends the sentences and
   numbers; these only format, show and hide. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const hints = require("../../web/hints.js");
const runs = require("../../web/runs.js");
const status = require("../../web/status.js");

test("hints: tip shows until its end time, then hides", () => {
  const hint = { id: "start", text: "New character: hello.", at: 100, expires_at: 700 };
  assert.equal(hints.tipText(hint, 100), "New character: hello.");
  assert.equal(hints.tipText(hint, 699.9), "New character: hello.");
  assert.equal(hints.tipText(hint, 700), "");
  assert.equal(hints.tipText(null, 100), "");
  assert.equal(hints.tipText({ text: "" }, 100), "");
  assert.equal(hints.tipText({ text: "No end." }, 100), "No end.");
});

test("hints: the event list labels a tip", () => {
  assert.equal(status.kindOf({ type: "hint" }), "tip");
});

test("ladder: rows as the core counted them, highest first", () => {
  assert.deepEqual(runs.ladderRows({ levels: [
    { area_level: 67, maps: 2, deaths: 0, level_ups: 1, median_s: 400, median_text: "6:40" },
    { area_level: 65, maps: 1, deaths: 3, level_ups: 0, median_s: null, median_text: "--:--" }] }), [
    { level: "67", maps: "2", deaths: "0", median: "6:40", levelups: "1" },
    { level: "65", maps: "1", deaths: "3", median: "--:--", levelups: "0" }]);
  assert.deepEqual(runs.ladderRows(null), []);
  assert.deepEqual(runs.ladderRows({ levels: [{ area_level: null }] }), [
    { level: "unknown", maps: "0", deaths: "0", median: "--:--", levelups: "0" }]);
});
