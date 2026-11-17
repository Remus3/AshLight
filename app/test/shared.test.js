"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fmt = require("../shared/format.js");
const gate = require("../shared/render_gate.js");

test("minutes: coarse zone timer", () => {
  assert.equal(fmt.minutes(null), "--");
  assert.equal(fmt.minutes(-1), "--");
  assert.equal(fmt.minutes(0), "<1m");
  assert.equal(fmt.minutes(59.9), "<1m");
  assert.equal(fmt.minutes(60), "1m");
  assert.equal(fmt.minutes(3599), "59m");
  assert.equal(fmt.minutes(3600 + 5 * 60), "1h05m");
});

test("msUntilNextChange lands on the next minute boundary", () => {
  assert.equal(fmt.msUntilNextChange(null), null);
  assert.equal(fmt.msUntilNextChange(0), 60000);
  assert.equal(fmt.msUntilNextChange(59.5), 500);
  assert.equal(fmt.msUntilNextChange(119.99), 250); // floor at 250 ms
});

test("level, deaths and zone text", () => {
  assert.equal(fmt.levelText(null), "Lv -");
  assert.equal(fmt.levelText(12), "Lv 12");
  assert.equal(fmt.deathsText(0), "0 deaths");
  assert.equal(fmt.deathsText(1), "1 death");
  assert.equal(fmt.zoneText(null, false), "No zone yet");
  assert.equal(fmt.zoneText("Felled Hideout", true), "Felled Hideout (HO)");
  const long = fmt.zoneText("A".repeat(40), false, 10);
  assert.equal(long.length, 10);
  assert.ok(long.endsWith("..."));
});

const snap = {
  zone: "Clearfell", in_hideout: false, zone_entered_at: 1000,
  level: 3, deaths: 1, version: 7
};

test("hudModel builds the visible strings", () => {
  const m = gate.hudModel(snap, 1000 + 125, "live");
  assert.deepEqual(m, { zone: "Clearfell", timer: "2m", level: "Lv 3",
                        deaths: "1 death", status: "live", tradeFrom: "",
                        tradeItem: "", tradeWhere: "", tradeMore: "", anchor: "top" });
  const empty = gate.hudModel(null, 0);
  assert.equal(empty.status, "waiting");
});

test("shouldRender: only when a visible string changes", () => {
  const a = gate.hudModel(snap, 1010, "live");
  assert.equal(gate.shouldRender(null, a), true);
  // Same minute, other fields changed (version) -> no frame.
  const b = gate.hudModel({ ...snap, version: 8, events_seen: 99 }, 1050, "live");
  assert.equal(gate.shouldRender(a, b), false);
  assert.deepEqual(gate.changedFields(a, b), []);
  // Minute ticks -> one frame.
  const c = gate.hudModel(snap, 1061, "live");
  assert.equal(gate.shouldRender(b, c), true);
  assert.deepEqual(gate.changedFields(b, c), ["timer"]);
  // Death -> one frame, one field.
  const d = gate.hudModel({ ...snap, deaths: 2 }, 1061, "live");
  assert.deepEqual(gate.changedFields(c, d), ["deaths"]);
  // Connection status is visible too.
  const e = gate.hudModel({ ...snap, deaths: 2 }, 1061, "offline");
  assert.deepEqual(gate.changedFields(d, e), ["status"]);
});
