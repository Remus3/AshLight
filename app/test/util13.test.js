/* NEWBIE-HINTS / UTIL-MAP-LADDER: exact output of the dashboard helpers
   (web/hints.js wire, web/runs.js ladderRows). The core sends the
   sentences and numbers; these only format, show and hide. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const hints = web.load("hints.js");
const runs = web.load("runs.js");
const status = web.load("status.js");

test("hints: only the Settings click is left; region N shows the tip", () => {
  // PLAY-LEGACY-OUT-2: the old tip card and its painter are gone
  assert.equal(hints.paint, undefined);
  assert.equal(hints.tipText, undefined);
  const said = { textContent: "x" };
  let click = null;
  const doc = { getElementById: (id) => (id === "hints-reset"
    ? { addEventListener: (k, f) => { click = f; } } : id === "hints-said" ? said : null) };
  const calls = [];
  let answer = Promise.resolve({ text: "Tips will show again." });
  hints.wire(doc, (m, path, body) => { calls.push([m, path, body]); return answer; });
  click();
  assert.equal(said.textContent, "");
  assert.deepEqual(calls, [["POST", "/api/hints", { reset: true }]]);
  return answer.then(() => {
    assert.equal(said.textContent, "Tips will show again.");
    answer = Promise.reject(new Error("HTTP 500"));
    click();
    return answer.catch(() => {});
  }).then(() => new Promise((r) => setImmediate(r))).then(() => {
    assert.equal(said.textContent, hints.FAILED);
    hints.wire({ getElementById: () => null }, () => answer); // no button: nothing wired
  });
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
