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
  assert.equal(fmt.levelText(null), "Lv unknown");
  assert.equal(fmt.levelText(12), "Lv 12");
  assert.equal(fmt.deathsText(0), "0 deaths");
  assert.equal(fmt.deathsText(1), "1 death");
  // UX-REVIEW F1: the open trade count for the HUD status slot
  assert.equal(fmt.tradeCount(0), "");
  assert.equal(fmt.tradeCount(1), "1 trade");
  assert.equal(fmt.tradeCount(2), "2 trades");
  assert.equal(fmt.tradeCount(12), "12 trades");
  assert.equal(fmt.tradeCount(undefined), "");
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
                        deaths: "1 death", sep: "|", away: "", log: "", status: "live",
                        tradeFrom: "", tradeItem: "", tradeWhere: "", tradeMore: "",
                        anchor: "top", evalHead: "", evalItem: "", evalLine: "",
                        evalVerdict: "", trades: "" });
  const empty = gate.hudModel(null, 0);
  assert.equal(empty.status, "connecting");
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

test("DS-HUD-EMPTY: before the first snapshot there is no lone separator", () => {
  const m = gate.hudModel(null, 0);
  assert.equal(m.zone, "AshLight");
  assert.equal(m.timer, "");
  assert.equal(m.level, "");
  assert.equal(m.deaths, "");
  assert.equal(m.sep, "");
  assert.equal(m.away, "");
  assert.equal(m.status, "connecting");
  // The first snapshot fills the line and brings the separator back.
  const f = gate.hudModel(snap, 1000, "live");
  assert.deepEqual(gate.changedFields(m, f).sort(),
                   ["deaths", "level", "sep", "status", "timer", "zone"]);
  assert.equal(f.sep, "|");
});

test("DS-HUD-CLIP: the (HO) tag fits inside the 28-char zone limit", () => {
  const long = "The Grand Hideout of the Very Long Name";
  const z = fmt.zoneText(long, true);
  assert.equal(z.length, 28);
  assert.equal(z, "The Grand Hideout of... (HO)");
  assert.ok(z.endsWith("... (HO)"));
  assert.equal(fmt.zoneText(long, false).length, 28);
  // A short hideout name is not clipped.
  assert.equal(fmt.zoneText("Felled Hideout", true), "Felled Hideout (HO)");
  // Exactly at the limit with the tag: no clip.
  assert.equal(fmt.zoneText("A".repeat(23), true), "A".repeat(23) + " (HO)");
  assert.equal(fmt.zoneText("A".repeat(24), true), "A".repeat(20) + "... (HO)");
  const m = gate.hudModel({ ...snap, zone: long, in_hideout: true }, 1000, "live");
  assert.ok(m.zone.length <= 28);
});

test("DS-HUD-CLIP: stash position reads as tab name and (left,top)", () => {
  const c = fmt.tradeCard({ from: "Q", item: "Belt", price_amount: 5,
                            price_currency: "exalted", stash_tab: "Sale", left: 3, top: 7 });
  assert.equal(c.where, "5 exalted | tab Sale (3,7)");
  const noPos = fmt.tradeCard({ from: "Q", item: "Belt", price_amount: 5,
                                price_currency: "exalted", stash_tab: "Sale" });
  assert.equal(noPos.where, "5 exalted | tab Sale");
});

test("DS-HUD-AFK: AFK / DND show in the status slot while live", () => {
  const live = gate.hudModel(snap, 1000, "live");
  assert.equal(live.away, "");
  const afk = gate.hudModel({ ...snap, afk: true }, 1000, "live");
  assert.equal(afk.away, "AFK");
  assert.deepEqual(gate.changedFields(live, afk), ["away"]);
  const dnd = gate.hudModel({ ...snap, dnd: true }, 1000, "live");
  assert.equal(dnd.away, "DND");
  const both = gate.hudModel({ ...snap, afk: true, dnd: true }, 1000, "live");
  assert.equal(both.away, "AFK");
  // The away flag is in the render gate, so turning it off repaints once.
  assert.equal(gate.shouldRender(afk, live), true);
  assert.ok(gate.FIELDS.indexOf("away") >= 0);
  // A connection problem outranks AFK in the slot.
  assert.equal(gate.statusText(afk), "AFK");
  assert.equal(gate.statusText({ ...afk, status: "offline" }), "offline");
  assert.equal(gate.statusText(live), "");
});

test("UI-REVIEW-2: the HUD says when Client.txt is not being read", () => {
  // Not opted in: no made-up numbers, one status word.
  const off = gate.hudModel({ ...snap, zone: null, zone_entered_at: null, level: null, deaths: 0,
                              tailer: { consented: false, reading: false, path: null } }, 1000, "live");
  assert.equal(off.zone, "AshLight");
  assert.equal(off.timer, "");
  assert.equal(off.level, "");
  assert.equal(off.deaths, "");
  assert.equal(off.sep, "");
  // UX-FIRSTRUN: the word says where the one opt-in click is.
  assert.equal(off.log, "not reading - see dashboard");
  assert.equal(gate.statusText(off), "not reading - see dashboard");
  // Opted in but the file is missing or quiet: keep what is known, say so.
  const wait = gate.hudModel({ ...snap, tailer: { consented: true, reading: false, path: null } },
                             1000, "live");
  assert.equal(wait.level, "Lv 3");
  assert.equal(wait.log, "no Client.txt");
  assert.equal(gate.statusText(wait), "no Client.txt");
  // UX-COPY: the file is known but quiet - waiting, not missing.
  const quiet = gate.hudModel({ ...snap, tailer: { consented: true, reading: false, path: "logs/Client.txt" } },
                              1000, "live");
  assert.equal(gate.statusText(quiet), "waiting for log");
  // Design review F2: a status word shown next to the numbers stays within
  // the 15 characters that fit after "Lv 100 | 99 deaths" at 13 px.
  const words = [quiet, wait].map((m) => gate.statusText(m))
    .concat(["offline", "connecting", "9 trades", "AFK", "DND"]);
  words.forEach((w) => assert.ok(w.length <= 15, w));
  // Reading, or an older core without the tailer field: nothing extra.
  const ok = gate.hudModel({ ...snap, tailer: { consented: true, reading: true, path: "x" } }, 1000, "live");
  assert.equal(ok.log, "");
  assert.equal(gate.hudModel(snap, 1000, "live").log, "");
  assert.ok(gate.FIELDS.indexOf("log") >= 0);
  // Order in the slot: connection, then log, then AFK.
  const both = gate.hudModel({ ...snap, afk: true, tailer: { consented: true, reading: false } }, 1000, "live");
  assert.equal(gate.statusText(both), "no Client.txt");
  assert.equal(gate.statusText({ ...both, status: "offline" }), "offline");
});

test("UI-REVIEW-2: no zone yet means no timer dashes", () => {
  const m = gate.hudModel({ ...snap, zone: null, zone_entered_at: null }, 1000, "live");
  assert.equal(m.zone, "No zone yet");
  assert.equal(m.timer, "");
});

/* UX-REVIEW F1 (2026-11-17): while a card holds the one slot, open trade
   requests still show as a count in the HUD status slot. */
const tradeRow = (id, from) => ({ id: id, from: from, kind: "item", item: "Ring",
                                  text: from + " wants Ring - 1 exalted", where: "" });
const slotCard = { kind: "price", head: "Price: Doom Grip", line2: "Prices in 8 s",
                   line3: "", verdict: "note", expires_at: 1020 };

test("F1: trade count shows in the status slot while a card holds the slot", () => {
  const one = gate.hudModel({ ...snap, card: slotCard, trade_requests: [tradeRow(1, "A")] },
                            1000, "live");
  assert.equal(one.tradeItem, "");
  assert.equal(one.trades, "1 trade");
  assert.equal(gate.statusText(one), "1 trade");
  const three = gate.hudModel({ ...snap, card: slotCard,
                                trade_requests: [tradeRow(1, "A"), tradeRow(2, "B"), tradeRow(3, "C")] },
                              1000, "live");
  assert.equal(three.trades, "3 trades");
  assert.equal(gate.statusText(three), "3 trades");
  assert.ok(gate.FIELDS.indexOf("trades") >= 0);
});

test("F1: no count when the trade card itself shows or nothing is open", () => {
  const own = gate.hudModel({ ...snap, trade_requests: [tradeRow(1, "A")] }, 1000, "live");
  assert.equal(own.trades, "");
  assert.equal(gate.statusText(own), "");
  const none = gate.hudModel({ ...snap, card: slotCard, trade_requests: [] }, 1000, "live");
  assert.equal(none.trades, "");
  // The card has left: the trade card is back and the count goes.
  const after = gate.hudModel({ ...snap, card: slotCard, trade_requests: [tradeRow(1, "A")] },
                              1020, "live");
  assert.equal(after.trades, "");
  assert.equal(after.tradeItem, "Ring");
});

test("F1: slot order is connection, log, trades, then AFK", () => {
  const base = { ...snap, card: slotCard, trade_requests: [tradeRow(1, "A")] };
  const afk = gate.hudModel({ ...base, afk: true }, 1000, "live");
  assert.equal(gate.statusText(afk), "1 trade");
  const log = gate.hudModel({ ...base, tailer: { consented: true, reading: false } }, 1000, "live");
  assert.equal(gate.statusText(log), "no Client.txt");
  assert.equal(gate.statusText({ ...afk, status: "offline" }), "offline");
});
