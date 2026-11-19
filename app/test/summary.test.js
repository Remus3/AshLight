"use strict";
/* UTIL-SESSION-SUMMARY: the last session card (web/summary.js). The core
   sends every sentence (server/al/summary.py); this only adds the end time.
   Fixture values are invented. */
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const s = web.load("summary.js");

const CARD = { id: 2, reason: "idle", reason_text: "after 20 minutes with no game activity",
  ended_at: 1700000000, lines: ["Played 1:00:00 and reached level 70.", "Maps: 2.",
  "Deaths: 1."] };

test("summary view: the core's lines and the end sentence", () => {
  const v = s.view(CARD, () => "14:05");
  assert.deepEqual(v.lines, CARD.lines);
  assert.equal(v.ended, "Session ended at 14:05 after 20 minutes with no game activity.");
  const closed = s.view(Object.assign({}, CARD, { reason_text: "when the game closed" }),
                        () => "9:30");
  assert.equal(closed.ended, "Session ended at 9:30 when the game closed.");
  assert.equal(s.view(Object.assign({}, CARD, { reason_text: "" }), () => "9:30").ended,
               "Session ended at 9:30.");
  assert.equal(s.view(Object.assign({}, CARD, { ended_at: "x" }), () => "9:30").ended, "");
});

test("summary clock: time today, date and time for an older card", () => {
  const ts = new Date(2026, 10, 16, 9, 5).getTime() / 1000;
  assert.equal(s.clock(ts, new Date(2026, 10, 16, 23, 0).getTime()), "09:05");
  assert.equal(s.clock(ts, new Date(2026, 10, 17, 8, 0).getTime()), "2026-11-16 09:05");
});

test("summary view: null for no card; junk lines dropped", () => {
  assert.equal(s.view(null), null);
  assert.equal(s.view({ lines: [] }), null);
  assert.equal(s.view({ lines: "x" }), null);
  const v = s.view({ lines: ["Maps: 1.", 5, null, ""], ended_at: 1 }, () => "0:00");
  assert.deepEqual(v.lines, ["Maps: 1."]);
});

test("summary paint: fills the card with textContent, hides it with no card", () => {
  const nodes = {};
  const mk = (id) => (nodes[id] = { id, hidden: false, textContent: "", kids: [],
    replaceChildren(...k) { this.kids = k; }, appendChild(k) { this.kids.push(k); } });
  ["summarybox", "summary-lines", "summary-ended"].forEach(mk);
  const doc = { getElementById: (id) => nodes[id],
    createElement: (tag) => ({ tag, textContent: "" }) };
  s.paint(doc, { session_summary: CARD }, () => "14:05");
  assert.equal(nodes.summarybox.hidden, false);
  assert.deepEqual(nodes["summary-lines"].kids.map((k) => k.textContent), CARD.lines);
  assert.equal(nodes["summary-ended"].textContent,
               "Session ended at 14:05 after 20 minutes with no game activity.");
  s.paint(doc, { session_summary: null }, () => "14:05");
  assert.equal(nodes.summarybox.hidden, true);
  assert.deepEqual(nodes["summary-lines"].kids, []);
});
