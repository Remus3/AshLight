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
                        deaths: "1 death", sep: "|", away: "", under: "", campaign: "", log: "",
                        status: "live",
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
  // TEST-LIVE-EXIT: a quiet log (game may be closed) freezes the timer.
  const idle = gate.hudModel({ ...snap, zone: "Crypt", zone_entered_at: 400,
    tailer: { consented: true, reading: true, path: "x", idle: true, last_line_at: 460 } },
                             1000, "live");
  assert.equal(idle.timer, "1m");
  assert.equal(idle.zone, "Crypt");
  assert.equal(gate.statusText(idle), gate.IDLE_WORD);
  // F-131: the overlay's short form of the dashboard's "log quiet" word
  assert.equal(gate.IDLE_WORD, "log quiet");
  const words = [quiet, wait, idle].map((m) => gate.statusText(m))
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

/* UTIL-MAPRUN-OVL (adjudicator 2026-11-17, option B): inside an open map
   the row-1 timer is the time in that map (it survives a hideout trip);
   elsewhere the zone-instance time. Still 2 lines, no new word. Values
   are invented. */
test("UTIL-MAPRUN-OVL: row-1 timer shows map time inside a map", () => {
  const cur = { name: "Crypt", area_level: 65, time_s: 750, deaths: 1, inside: true };
  // back in the map after a hideout trip: zone instance 1 min, map 12 min
  const snap = { now: 1000, zone: "Crypt", zone_entered_at: 940, level: 70, deaths: 3,
                 maps: { count: 1, current: cur }, tailer: { consented: true, reading: true } };
  const m = gate.hudModel(snap, 1000, "live");
  assert.equal(m.timer, "12m");
  assert.equal(m.zone, "Crypt");
  assert.equal(m.deaths, "3 deaths"); // row 2 keeps the session count
  assert.equal(gate.statusText(m), ""); // no map word in the status slot
  // moves on from the snapshot clock, minute resolution
  assert.equal(gate.hudModel(snap, 1030, "live").timer, "13m");
  assert.equal(gate.timerSeconds(snap, 1030), 780);
  // a clock skew never runs it backwards
  assert.equal(gate.timerSeconds(snap, 900), 750);
  // repaint gate: same minute, no repaint; next rollover from map time
  assert.equal(gate.shouldRender(m, gate.hudModel(snap, 1020, "live")), false);
  assert.equal(fmt.msUntilNextChange(gate.timerSeconds(snap, 1000)), 30000);
  // an idle log freezes it at the last line
  const idle = { ...snap, tailer: { consented: true, reading: true, idle: true, last_line_at: 1000 } };
  assert.equal(gate.hudModel(idle, 5000, "live").timer, "12m");
  // design review F1: the core pauses the map on an idle log (inside false);
  // the player still stands in it, so the frozen map time stays
  const paused = { ...idle, maps: { count: 1, current: { ...cur, inside: false } } };
  assert.equal(gate.hudModel(paused, 5000, "live").timer, "12m");
  // outside the map (hideout, map open): zone-instance time, unchanged
  const ho = { ...snap, zone: "Hideout", in_hideout: true, zone_entered_at: 970,
               maps: { count: 1, current: { ...cur, inside: false } } };
  assert.equal(gate.hudModel(ho, 1000, "live").timer, "<1m");
  // no map: zone-instance time; a bad time_s falls back too
  assert.equal(gate.hudModel({ ...snap, maps: { current: null } }, 1000, "live").timer, "1m");
  assert.equal(gate.hudModel({ ...snap, maps: null }, 1000, "live").timer, "1m");
  assert.equal(gate.hudModel({ ...snap, maps: { current: { ...cur, time_s: "x" } } }, 1000,
                             "live").timer, "1m");
  assert.equal(gate.timerSeconds(null, 1), null);
  // not opted in: no numbers at all
  assert.equal(gate.hudModel({ ...snap, tailer: { consented: false } }, 1000, "live").timer, "");
});

/* RUN-BUDGET-TESTS-DASH (B13, research 0048): a snapshot that changes no
   HUD string costs the overlay no paint. 1,000 snapshots differ from a busy
   base only in fields the HUD does not show (state version, counters, the
   dashboard's own views); the overlay's paint step (app/overlay/overlay.js
   paint: hudModel, then shouldRender) paints the first and none after.
   Seeded, so every run walks the same 1,000. Values are invented. */
test("B13: 1,000 snapshots differing only outside the HUD fields give 0 paints", () => {
  const base = {
    now: 5000, zone: "Crypt", in_hideout: false, in_town: false, zone_entered_at: 4400,
    level: 71, deaths: 4, afk: false, dnd: false,
    tailer: { consented: true, reading: true, path: "x", idle: false, last_line_at: 4990 },
    maps: { count: 3, current: { name: "Crypt", area_level: 65, time_s: 600, deaths: 1, inside: true } },
    trade_requests: [tradeRow(1, "A"), tradeRow(2, "B")],
    card: { kind: "price", head: "Price: Doom Grip", line2: "12 exalted", line3: "",
            verdict: "note", expires_at: 5015 },
    overlay_layout: { corner: "top-right", quiet_town: true, zone_guide: "always",
                      parts: { zone: true, timer: true, level: true, deaths: true } },
    overlay: { guide_short: "Kill the boss", calm_at: 4000 },
    underlevel: { word: "" }, campaign: { word: "" }
  };
  const nowS = 5005;
  let seed = 20261121;
  const rnd = (n) => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed % n; };
  const NOISE = [
    (s, i) => { s.version = 100 + i; },
    (s, i) => { s.events_seen = 9000 + i * 3; },
    (s, i) => { s.run_history = { count: rnd(20), enabled: true }; },
    (s, i) => { s.diag = { rows: [{ id: "log", state: rnd(2) ? "ok" : "fix" }], failed: rnd(3) }; },
    (s, i) => { s.play = { notices: [{ id: "tip" + i, text: "Tip " + i }] }; },
    (s, i) => { s.maps = { ...s.maps, count: 3 + rnd(50), ladder_all: { rows: [{ level: rnd(80) }] } }; },
    (s, i) => { s.price = { book_at: 4000 + i, rows: rnd(500) }; },
    (s, i) => { s.build = { name: "Build " + rnd(9), stale: rnd(2) === 1 }; },
    (s, i) => { s.hotkeys = { eval: { key: "Ctrl+Alt+" + "DEF"[rnd(3)] } }; },
    (s, i) => { s.recent_events = [{ seq: i, type: "zone", at: 4000 + i }]; }
  ];
  let shown = null;
  let paints = 0;
  const paint = (s) => {
    const model = gate.hudModel(s, nowS, "live");
    if (gate.shouldRender(shown, model)) { paints++; shown = model; }
  };
  paint(base);
  assert.equal(paints, 1); // the first snapshot paints the HUD
  assert.ok(shown.zone && shown.timer && shown.evalHead, shown);
  paints = 0;
  for (let i = 0; i < 1000; i++) {
    const s = { ...base };
    const n = 1 + rnd(4);
    for (let k = 0; k < n; k++) { NOISE[rnd(NOISE.length)](s, i); }
    paint(s);
  }
  assert.equal(paints, 0);
  // the gate is not blind: one HUD string changed is one paint
  paint({ ...base, deaths: 5 });
  assert.equal(paints, 1);
});

/* OVL-OVERLAY-FEED (F-177): the core's /events?view=overlay frame holds
   only SNAP_FIELDS (server/al/overlayview.py OVERLAY_FIELDS; the Python
   test tests/test_overlay_feed.py compares the two lists too). Here: the
   lists are equal, a walk of every snapshot read render_gate.js makes on
   a set of full snapshots finds none outside the list and every entry read,
   and the HUD output for the small view equals the output for the full
   snapshot on every fixture (B13: the small feed changes no paint). */
const fs = require("node:fs");
const path = require("node:path");

const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

/* The JS twin of overlayview.small: only the listed fields; a dotted entry
   keeps one key of a top-level object; a non-object stays as it is. */
function smallView(snap, fields) {
  const out = {};
  for (const f of fields) {
    const i = f.indexOf(".");
    const top = i < 0 ? f : f.slice(0, i);
    const sub = i < 0 ? "" : f.slice(i + 1);
    if (!has(snap, top)) { continue; }
    const v = snap[top];
    if (!sub) {
      out[top] = v;
    } else if (!v || typeof v !== "object" || Array.isArray(v)) {
      if (!has(out, top)) { out[top] = v; }
    } else {
      if (!has(out, top)) { out[top] = {}; }
      if (has(v, sub)) { out[top][sub] = v[sub]; }
    }
  }
  out.version = snap.version;
  return out;
}

/* A deep read recorder: every property path read through it lands in seen. */
function recorder(obj, where, seen) {
  if (obj === null || typeof obj !== "object") { return obj; }
  const at = (k) => (where ? where + "." + String(k) : String(k));
  return new Proxy(obj, {
    get(t, k, r) {
      if (typeof k === "symbol") { return Reflect.get(t, k, r); }
      seen.add(at(k));
      return recorder(Reflect.get(t, k, r), at(k), seen);
    },
    has(t, k) {
      if (typeof k !== "symbol") { seen.add(at(k)); }
      return Reflect.has(t, k);
    },
    getOwnPropertyDescriptor(t, k) {
      if (typeof k !== "symbol") { seen.add(at(k)); }
      return Reflect.getOwnPropertyDescriptor(t, k);
    }
  });
}

/* Full snapshots as the core sends them, with dashboard-only state around
   the HUD fields. Values are invented. */
const NOISE_FIELDS = {
  version: 812, events_seen: 9001, recent_events: [{ seq: 1, type: "death", at: 4990 }],
  sources: { calc_on: true }, diag: { rows: [{ id: "log" }] }, run_history: { on: true },
  hotkeys: { eval: { key: "Alt+Shift+E" } }, build: { name: "B" }, price: { rows: 3 },
  zone_guide: { line: "long guide line" }, pace: { rate: 1 }, characters: [{ name: "Me" }]
};
const FEED_BASE = {
  ...NOISE_FIELDS,
  now: 5000, zone: "Crypt", in_hideout: false, in_town: false, zone_entered_at: 4400,
  level: 71, deaths: 4, afk: false, dnd: false, game_idle: false,
  tailer: { consented: true, reading: true, path: "x", idle: false, last_line_at: 4990 },
  maps: { count: 3, current: { name: "Crypt", area_level: 65, time_s: 600, deaths: 1, inside: true },
          recent: [{ name: "Old" }], ladder: { rows: [] } },
  trade_requests: [tradeRow(1, "A"), tradeRow(2, "B")],
  underlevel: { word: "", gap: 3 }, campaign: { word: "", rows: [] },
  card: { kind: "price", head: "Price: Doom Grip", line2: "12 exalted", line3: "",
          verdict: "note", expires_at: 5015 },
  eval: { text: { head: "Upgrade", item: "Doom Grip", line: "+4% DPS" }, expires_at: 5015,
          ok: true, verdict: "upgrade", mods: ["a", "b"], at: 4995 },
  overlay: { guide_short: "Kill the boss", calm_at: 4000 },
  overlay_layout: { corner: "top-right", quiet_town: true, zone_guide: "always",
                    parts: { zone: true, timer: true, level: true, deaths: true } }
};
const OLD_CORE = { ...FEED_BASE };  // a core without "card": the eval path
delete OLD_CORE.card;
const HINT = { kind: "hint", head: "Alt+Shift+E: check an item", line2: "", line3: "",
               verdict: "hint", expires_at: null };
const FEED_FIXTURES = [
  FEED_BASE,
  OLD_CORE,
  { ...OLD_CORE, eval: { ...FEED_BASE.eval, ok: false } },
  { ...FEED_BASE, card: null, trade_requests: [] },
  { ...FEED_BASE, tailer: { consented: false } },
  { ...FEED_BASE, game_idle: true, card: null,
    tailer: { consented: true, reading: true, path: "x", idle: true, last_line_at: 4800 },
    maps: { ...FEED_BASE.maps, current: { ...FEED_BASE.maps.current, inside: false } } },
  { ...FEED_BASE, tailer: { consented: true, reading: false, unreadable: true, path: "x" } },
  { ...FEED_BASE, tailer: { consented: true, reading: false, path: null }, maps: null },
  { ...FEED_BASE, in_town: true, card: null, trade_requests: [] },
  { ...FEED_BASE, in_hideout: true, zone: "Felled Hideout", card: null },
  { ...FEED_BASE, card: { kind: "zone", head: "Kill the boss", line2: "Next: Grelwood",
                          line3: "", verdict: "", expires_at: 5010 } },
  { ...FEED_BASE, card: HINT },
  { ...FEED_BASE, card: HINT, trade_requests: [] },
  { ...FEED_BASE, card: null, trade_requests: [],
    overlay: { guide_short: "Kill the boss", calm_at: 5010 } },
  { ...FEED_BASE, card: null, trade_requests: [], afk: true },
  { ...FEED_BASE, card: null, trade_requests: [], dnd: true,
    underlevel: { word: "4 lv under", gap: 3 }, campaign: { word: "Cold res 32%" } },
  { ...FEED_BASE, card: null, trade_requests: [], underlevel: null, campaign: null,
    overlay_layout: { corner: "bottom-left", quiet_town: false, zone_guide: "never",
                      parts: { trade: false, status: false, hint: false } } },
  { ...FEED_BASE, overlay_layout: null, overlay: { guide_short: "", calm_at: null } }
];
const FEED_TIMES = [4990, 5000, 5005, 5012, 5020, 5100];

/* Everything the overlay page asks render_gate.js about one snapshot. */
function hudOutputs(s, nowS) {
  const m = gate.hudModel(s, nowS, "live");
  return { model: m, guide: m.guide, hudShown: m.hudShown, status: gate.statusText(m),
           evalMs: gate.msUntilEvalExpires(s, nowS), guideMs: gate.msUntilGuideDue(s, nowS),
           timer: gate.timerSeconds(s, nowS), wanted: gate.overlayWanted(s, "live") };
}

test("OVERLAY-FEED: SNAP_FIELDS equals the core's OVERLAY_FIELDS", () => {
  const py = fs.readFileSync(path.join(__dirname, "..", "..", "server", "al", "overlayview.py"),
                             "utf8");
  const m = /^OVERLAY_FIELDS = \(([\s\S]*?)\)$/m.exec(py);
  assert.ok(m, "overlayview.py lost OVERLAY_FIELDS");
  const list = m[1].match(/"[^"]+"/g).map((q) => q.slice(1, -1));
  assert.deepEqual(gate.SNAP_FIELDS, list);
  assert.equal(new Set(list).size, list.length);
});

test("OVERLAY-FEED: every snapshot read of render_gate.js is in SNAP_FIELDS, every entry read", () => {
  const seen = new Set();
  for (const s of FEED_FIXTURES) {
    for (const t of FEED_TIMES) { hudOutputs(recorder(s, "", seen), t); }
  }
  const fields = gate.SNAP_FIELDS;
  const covered = (r) => fields.some((f) => r === f || r.startsWith(f + ".") ||
                                            f.startsWith(r + "."));
  const outside = [...seen].filter((r) => !covered(r)).sort();
  assert.deepEqual(outside, [], "reads outside SNAP_FIELDS");
  const unread = fields.filter((f) => ![...seen].some((r) => r === f || r.startsWith(f + ".")));
  assert.deepEqual(unread, [], "SNAP_FIELDS entries no fixture read");
  /* a source walk too: a top-level read on a branch no fixture takes */
  const tops = new Set(fields.map((f) => f.split(".")[0]));
  for (const file of ["../shared/render_gate.js", "../overlay/overlay.js"]) {
    const src = fs.readFileSync(path.join(__dirname, file), "utf8");
    for (const hit of src.matchAll(/\bsnap\.(\w+)/g)) {
      assert.ok(tops.has(hit[1]), file + " reads snap." + hit[1]);
    }
  }
});

test("OVERLAY-FEED B13: the small view paints exactly what the full snapshot paints", () => {
  for (const s of FEED_FIXTURES) {
    const small = smallView(s, gate.SNAP_FIELDS);
    for (const k of Object.keys(NOISE_FIELDS)) {
      if (k !== "version") { assert.ok(!has(small, k), k); }
    }
    for (const t of FEED_TIMES) {
      const full = hudOutputs(s, t);
      const view = hudOutputs(small, t);
      assert.deepEqual(view, full, JSON.stringify({ t: t, zone: s.zone }));
      assert.equal(gate.shouldRender(full.model, view.model), false);
    }
  }
});
