"use strict";
/* OVL-PARTS-PAGE (F-118, plan 03 section 5.1): the overlay page honours
   the parts switches of snap.overlay_layout. A part that is off drops out,
   an empty HUD plate is absent, and a failure word always shows. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const gate = require("../shared/render_gate.js");
const L = require("../shared/layout.js");

const ALL_OFF = Object.fromEntries(L.LAYOUT_PARTS.map((p) => [p, false]));
/* Preset "Cards only": no HUD part, every card kind on. */
const CARDS_ONLY = Object.assign({}, ALL_OFF,
  { trade: true, item: true, moment: true, hint: true });

const TRADE = { id: 1, from: "Kalandra", item: "Rusted Sword", where: "Stash tab 1",
                at: 1000 };

function snap(parts, extra) {
  return Object.assign({
    zone: "Clearfell", in_hideout: false, in_town: false, zone_entered_at: 1000,
    level: 12, deaths: 2, version: 7, now: 1000, trade_requests: [],
    tailer: { consented: true, reading: true, path: "x" },
    overlay_layout: { corner: "top-right", parts: parts, quiet_town: false }
  }, extra || {});
}

function card(kind, extra) {
  return Object.assign({ kind: kind, head: "Upgrade: +12% DPS", line2: "Ring",
                         line3: "Life +40", verdict: "good", expires_at: 1020 }, extra || {});
}

const HUD_KEYS = ["zone", "timer", "level", "deaths", "sep", "away", "under",
                  "campaign", "log", "trades", "tradeFrom", "tradeItem", "tradeWhere",
                  "tradeMore", "evalHead", "evalItem", "evalLine", "evalVerdict"];

test("every part off: an empty model and the HUD plate is absent", () => {
  const m = gate.hudModel(snap(ALL_OFF, {
    afk: true, underlevel: { word: "4 lv under" }, campaign: { word: "Cold res 32%" },
    trade_requests: [TRADE], card: card("eval")
  }), 1005, "live");
  for (const k of HUD_KEYS) { assert.equal(m[k], "", k); }
  assert.equal(gate.statusText(m), "");
  assert.equal(m.hudShown, false);
  assert.ok(gate.FIELDS.includes("hudShown"));
});

test("missing parts or layout = all on (default Full)", () => {
  const m = gate.hudModel(snap(undefined), 1005, "live");
  assert.equal(m.zone, "Clearfell");
  assert.equal(m.level, "Lv 12");
  assert.equal(m.deaths, "2 deaths");
  assert.equal(m.sep, "|");
  assert.equal(m.hudShown, true);
  const bare = gate.hudModel(snap(undefined, { overlay_layout: null }), 1005, "live");
  assert.equal(bare.zone, "Clearfell");
  assert.equal(bare.hudShown, true);
  const one = gate.hudModel(snap({ level: false }), 1005, "live");
  assert.equal(one.level, "");
  assert.equal(one.deaths, "2 deaths");
  assert.equal(one.sep, "", "no lone separator");
});

test("preset Cards only shows nothing until a card or a failure word", () => {
  const quiet = gate.hudModel(snap(CARDS_ONLY, { afk: true }), 1005, "live");
  assert.equal(quiet.hudShown, false);
  assert.equal(quiet.evalHead, "");
  assert.equal(quiet.tradeItem, "");
  const press = gate.hudModel(snap(CARDS_ONLY, { card: card("eval") }), 1005, "live");
  assert.equal(press.hudShown, false, "the card shows, the HUD plate does not");
  assert.equal(press.evalHead, "Upgrade: +12% DPS");
  const trade = gate.hudModel(snap(CARDS_ONLY, { trade_requests: [TRADE] }), 1005, "live");
  assert.equal(trade.tradeItem, "Rusted Sword");
  assert.equal(trade.hudShown, false);
  const off = gate.hudModel(snap(CARDS_ONLY), 1005, "offline");
  assert.equal(gate.statusText(off), "offline");
  assert.equal(off.hudShown, true);
});

test("offline, not reading and no Client.txt always show", () => {
  const offline = gate.hudModel(snap(ALL_OFF), 1005, "offline");
  assert.equal(gate.statusText(offline), "offline");
  assert.equal(offline.hudShown, true);
  const notReading = gate.hudModel(snap(ALL_OFF, { tailer: { consented: false } }), 1005, "live");
  assert.equal(notReading.zone, "");
  assert.equal(gate.statusText(notReading), gate.STATUS_WORDS.states.off.overlay);
  assert.equal(notReading.hudShown, true);
  const missing = gate.hudModel(snap(ALL_OFF, { tailer: { consented: true, reading: false } }),
                                1005, "live");
  assert.equal(gate.statusText(missing), "no Client.txt");
  assert.equal(missing.hudShown, true);
  const waiting = gate.hudModel(snap(ALL_OFF, {
    tailer: { consented: true, reading: false, path: "x" } }), 1005, "live");
  assert.equal(gate.statusText(waiting), "waiting for log");
  const idle = gate.hudModel(snap(ALL_OFF, {
    tailer: { consented: true, reading: true, idle: true, last_line_at: 1000 } }), 1005, "live");
  assert.equal(gate.statusText(idle), gate.IDLE_WORD);
  assert.equal(idle.hudShown, true);
  /* before any snapshot: the HUD names AshLight and the link word */
  const none = gate.hudModel(null, 0);
  assert.equal(none.hudShown, true);
});

test("parts.status off drops the lower status words, never rank 1", () => {
  const s = snap({ status: false }, { afk: true, underlevel: { word: "4 lv under" },
                                       campaign: { word: "Cold res 32%" },
                                       trade_requests: [TRADE], card: card("eval") });
  const m = gate.hudModel(s, 1005, "live");
  assert.equal(m.away, "");
  assert.equal(m.under, "");
  assert.equal(m.campaign, "");
  assert.equal(m.trades, "");
  assert.equal(gate.statusText(m), "");
  assert.equal(m.level, "Lv 12");
  assert.equal(gate.statusText(gate.hudModel(s, 1005, "offline")), "offline");
});

test("quiet_town hides the zone line in town and hideout", () => {
  const lay = (extra) => snap(undefined, Object.assign({
    overlay_layout: { corner: "top-right", quiet_town: true } }, extra));
  const town = gate.hudModel(lay({ zone: "Clearfell Encampment", in_town: true }), 1100, "live");
  assert.equal(town.zone, "");
  assert.equal(town.timer, "");
  assert.equal(town.level, "Lv 12");
  assert.equal(town.hudShown, true);
  const ho = gate.hudModel(lay({ zone: "Felled Hideout", in_hideout: true }), 1100, "live");
  assert.equal(ho.zone, "");
  assert.equal(ho.timer, "");
  const field = gate.hudModel(lay({}), 1100, "live");
  assert.equal(field.zone, "Clearfell");
  assert.equal(field.timer, "1m");
  /* quiet_town off: town still shows */
  const loud = gate.hudModel(snap(undefined, { zone: "Clearfell Encampment", in_town: true }),
                             1100, "live");
  assert.equal(loud.zone, "Clearfell Encampment");
});

test("parts.trade and parts.item hide their card kinds", () => {
  const both = { trade_requests: [TRADE], card: card("eval") };
  const noItem = gate.hudModel(snap({ item: false }, both), 1005, "live");
  assert.equal(noItem.evalHead, "");
  assert.equal(noItem.tradeItem, "Rusted Sword", "the trade card takes the free slot");
  assert.equal(noItem.trades, "");
  assert.equal(gate.msUntilEvalExpires(snap({ item: false }, both), 1005), null);
  for (const kind of ["price", "merged"]) {
    const m = gate.hudModel(snap({ item: false }, { card: card(kind) }), 1005, "live");
    assert.equal(m.evalHead, "", kind);
  }
  const noTrade = gate.hudModel(snap({ trade: false }, both), 1005, "live");
  assert.equal(noTrade.tradeItem, "");
  assert.equal(noTrade.tradeFrom, "");
  assert.equal(noTrade.evalHead, "Upgrade: +12% DPS");
  assert.equal(noTrade.trades, "1 trade", "the count rule stays");
  const alone = gate.hudModel(snap({ trade: false }, { trade_requests: [TRADE, TRADE] }),
                              1005, "live");
  assert.equal(alone.tradeItem, "");
  assert.equal(alone.tradeMore, "");
  const notConsented = gate.hudModel(snap({ trade: false }, {
    trade_requests: [TRADE], tailer: { consented: false } }), 1005, "live");
  assert.equal(notConsented.tradeItem, "");
  /* an older core without "card": the eval card follows parts.item */
  const old = { eval: { text: { head: "Keep" }, expires_at: 1020 } };
  const oldOff = gate.hudModel(snap({ item: false }, old), 1005, "live");
  assert.equal(oldOff.evalHead, "");
  /* parts.moment / parts.hint do not touch today's press cards */
  assert.equal(gate.hudModel(snap({ moment: false, hint: false }, { card: card("eval") }),
                             1005, "live").evalHead, "Upgrade: +12% DPS");
});

test("TC-GEM-UNLOCK: the gem card follows parts.moment, not parts.item", () => {
  const gem = { card: card("gem", { head: "Gem usable at level 14", line2: "Frost Bomb",
                                    line3: "", verdict: "" }) };
  assert.equal(gate.hudModel(snap({ item: false }, gem), 1005, "live").evalHead,
               "Gem usable at level 14");
  assert.equal(gate.hudModel(snap({ moment: false }, gem), 1005, "live").evalHead, "");
});

test("no repaint when a hidden part changes", () => {
  const a = gate.hudModel(snap({ deaths: false, status: false }), 1005, "live");
  const b = gate.hudModel(snap({ deaths: false, status: false }, {
    deaths: 9, afk: true, campaign: { word: "Cold res 32%" } }), 1005, "live");
  assert.equal(gate.shouldRender(a, b), false);
  assert.deepEqual(gate.changedFields(a, b), []);
  const c = gate.hudModel(snap(CARDS_ONLY, { level: 13 }), 1005, "live");
  const d = gate.hudModel(snap(CARDS_ONLY, { level: 14, zone: "The Grelwood" }), 1300, "live");
  assert.equal(gate.shouldRender(c, d), false);
  /* the plate coming back is one change: hudShown */
  const e = gate.hudModel(snap(CARDS_ONLY), 1005, "offline");
  assert.ok(gate.changedFields(c, e).includes("hudShown"));
});

function code(js) {
  return js.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

test("the page hides the plate from hudShown and adds no timer", () => {
  const js = code(fs.readFileSync(path.join(__dirname, "..", "overlay", "overlay.js"), "utf8"));
  assert.match(js, /nodes\.hud\.hidden\s*=\s*!model\.hudShown/);
  assert.ok((js.match(/setTimeout\(/g) || []).length <= 1);
  assert.ok(!/setInterval|requestAnimationFrame/.test(js));
});
