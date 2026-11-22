"use strict";
/* OVL-POS layout math and HUD-WHISPER card model. */
const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../shared/layout.js");
const fmt = require("../shared/format.js");
const gate = require("../shared/render_gate.js");

function disp(id, x, y, w, h, sf, taskbar) {
  return { id: id, bounds: { x: x, y: y, width: w, height: h },
           workArea: { x: x, y: y, width: w, height: h - (taskbar || 0) },
           scaleFactor: sf || 1, label: "D" + id };
}

const PRIMARY = disp(10, 0, 0, 1920, 1080, 1, 40);
const LEFT = disp(20, -2560, -360, 2560, 1440, 1.5, 0);
const RIGHT = disp(30, 1920, 0, 1280, 1024, 1.25, 0);
const ALL = [PRIMARY, RIGHT, LEFT];

test("normalizeLayout fills defaults and clamps", () => {
  assert.deepEqual(L.normalizeLayout(null), L.LAYOUT_DEFAULT);
  const n = L.normalizeLayout({ corner: "nope", scale: 9, opacity: 0, margin: -5, display: "x" });
  assert.equal(n.corner, "top-right");
  assert.equal(n.scale, 2);
  assert.equal(n.opacity, 0.86); // schema 1 floor 0.9, migrated
  assert.equal(n.margin, 0);
  assert.equal(n.v, 2);
  assert.equal(n.display, "primary");
});

/* OVL-OVERLAY-KEYS: parts switches, quiet town, zone-guide choice. The
   rows between the SHARED-FIXTURE markers are plain JSON; the Python side
   (tests/test_overlay_layout.py) reads them and checks layout.normalize
   (strict=False) gives the same "out" for every "in". */
const ALL_ON = { zone: true, timer: true, level: true, deaths: true, status: true,
                 trade: true, item: true, moment: true, hint: true };
const SHARED = /* SHARED-FIXTURE */ [
  {"in": {},
   "out": {"display": "primary", "corner": "top-right", "scale": 1.0, "opacity": 0.86,
           "margin": 16,
           "parts": {"zone": true, "timer": true, "level": true, "deaths": true,
                     "status": true, "trade": true, "item": true, "moment": true,
                     "hint": true},
           "quiet_town": false, "zone_guide": "entry", "v": 2}},
  {"in": {"corner": "bottom-left", "scale": 1.5, "display": 2, "opacity": 1.0,
          "margin": 30, "parts": {"zone": false, "trade": false},
          "quiet_town": true, "zone_guide": "never"},
   "out": {"display": 2, "corner": "bottom-left", "scale": 1.5, "opacity": 1.0,
           "margin": 30,
           "parts": {"zone": false, "timer": true, "level": true, "deaths": true,
                     "status": true, "trade": false, "item": true, "moment": true,
                     "hint": true},
           "quiet_town": true, "zone_guide": "never", "v": 2}},
  {"in": {"parts": {"offline": false, "hint": 0, "moment": false, "item": "no"},
          "quiet_town": "yes", "zone_guide": "sometimes"},
   "out": {"display": "primary", "corner": "top-right", "scale": 1.0, "opacity": 0.86,
           "margin": 16,
           "parts": {"zone": true, "timer": true, "level": true, "deaths": true,
                     "status": true, "trade": true, "item": true, "moment": false,
                     "hint": true},
           "quiet_town": false, "zone_guide": "entry", "v": 2}},
  {"in": {"parts": ["zone"], "quiet_town": 1, "zone_guide": "always",
          "scale": 0.5, "opacity": 3, "margin": 999, "display": 40},
   "out": {"display": "primary", "corner": "top-right", "scale": 0.95, "opacity": 1.0,
           "margin": 400,
           "parts": {"zone": true, "timer": true, "level": true, "deaths": true,
                     "status": true, "trade": true, "item": true, "moment": true,
                     "hint": true},
           "quiet_town": false, "zone_guide": "always", "v": 2}},
  {"in": {"parts": null, "zone_guide": null, "quiet_town": null},
   "out": {"display": "primary", "corner": "top-right", "scale": 1.0, "opacity": 0.86,
           "margin": 16,
           "parts": {"zone": true, "timer": true, "level": true, "deaths": true,
                     "status": true, "trade": true, "item": true, "moment": true,
                     "hint": true},
           "quiet_town": false, "zone_guide": "entry", "v": 2}},
  {"in": {"opacity": 0.95},
   "out": {"display": "primary", "corner": "top-right", "scale": 1.0, "opacity": 0.93,
           "margin": 16,
           "parts": {"zone": true, "timer": true, "level": true, "deaths": true,
                     "status": true, "trade": true, "item": true, "moment": true,
                     "hint": true},
           "quiet_town": false, "zone_guide": "entry", "v": 2}},
  {"in": {"opacity": 0.5, "v": 1},
   "out": {"display": "primary", "corner": "top-right", "scale": 1.0, "opacity": 0.86,
           "margin": 16,
           "parts": {"zone": true, "timer": true, "level": true, "deaths": true,
                     "status": true, "trade": true, "item": true, "moment": true,
                     "hint": true},
           "quiet_town": false, "zone_guide": "entry", "v": 2}},
  {"in": {"opacity": 0.85, "v": 2},
   "out": {"display": "primary", "corner": "top-right", "scale": 1.0, "opacity": 0.85,
           "margin": 16,
           "parts": {"zone": true, "timer": true, "level": true, "deaths": true,
                     "status": true, "trade": true, "item": true, "moment": true,
                     "hint": true},
           "quiet_town": false, "zone_guide": "entry", "v": 2}},
  {"in": {"opacity": 0.3, "v": 2},
   "out": {"display": "primary", "corner": "top-right", "scale": 1.0, "opacity": 0.8,
           "margin": 16,
           "parts": {"zone": true, "timer": true, "level": true, "deaths": true,
                     "status": true, "trade": true, "item": true, "moment": true,
                     "hint": true},
           "quiet_town": false, "zone_guide": "entry", "v": 2}}
] /* END-SHARED-FIXTURE */;

test("OVL-OVERLAY-KEYS: defaults keep today's overlay", () => {
  assert.deepEqual(L.LAYOUT_PARTS, ["zone", "timer", "level", "deaths", "status",
                                    "trade", "item", "moment", "hint"]);
  assert.deepEqual(L.ZONE_GUIDE, ["entry", "always", "never"]);
  const n = L.normalizeLayout(undefined);
  assert.deepEqual(n.parts, ALL_ON);
  assert.equal(n.quiet_town, false);
  assert.equal(n.zone_guide, "entry");
  // a failure word is not a part: it can never be switched off
  for (const word of ["offline", "no_client_txt", "not_reading", "failure"]) {
    assert.ok(L.LAYOUT_PARTS.indexOf(word) < 0, word);
  }
});

test("OVL-OVERLAY-KEYS: normalizeLayout fills the new keys and never shares DEFAULT", () => {
  const n = L.normalizeLayout({ parts: { level: false } });
  assert.deepEqual(n.parts, { ...ALL_ON, level: false });
  n.parts.zone = false;
  assert.equal(L.LAYOUT_DEFAULT.parts.zone, true);
  assert.equal(L.normalizeLayout({}).parts.zone, true);
  assert.notEqual(L.normalizeLayout({}).parts, L.LAYOUT_DEFAULT.parts);
  for (const junk of [null, 5, "all", ["zone"], {}]) {
    assert.deepEqual(L.normalizeLayout({ parts: junk }).parts, ALL_ON);
  }
});

test("OVL-OVERLAY-KEYS: Python and JS agree on the shared fixture", () => {
  assert.ok(SHARED.length >= 4);
  for (const row of SHARED) {
    assert.deepEqual(L.normalizeLayout(row.in), row.out, JSON.stringify(row.in));
  }
  assert.deepEqual(SHARED[0].out, L.LAYOUT_DEFAULT);
});

test("DS-OPACITY / DS-SCALE: old layouts clamp to the floors", () => {
  assert.deepEqual(L.LAYOUT_LIMITS.opacity, [0.8, 1.0]);
  assert.deepEqual(L.LAYOUT_LIMITS.scale, [0.95, 2.0]);
  assert.equal(L.LAYOUT_DEFAULT.opacity, 0.86);
  assert.equal(L.LAYOUT_DEFAULT.v, 2);
  const n = L.normalizeLayout({ scale: 0.75, opacity: 0.3 });
  assert.equal(n.scale, 0.95);
  assert.equal(n.opacity, 0.86); // schema 1: clamped to 0.9, then migrated
  assert.ok(13 * n.scale >= 12);
  assert.equal(L.normalizeLayout({ opacity: 0.3, v: 2 }).opacity, 0.8);
  assert.equal(L.normalizeLayout({ opacity: 7, v: 2 }).opacity, 1);
});

/* OVL-TD05-PLATE: a layout saved without "v": 2 held a page opacity in
   0.9 to 1.0; it maps linearly onto the plate alpha 0.86 to 1.0, once. */
test("OVL-TD05-PLATE: saved 0.9 to 1.0 maps linearly onto 0.86 to 1.0 once", () => {
  assert.equal(L.normalizeLayout({ opacity: 0.9 }).opacity, 0.86);
  assert.equal(L.normalizeLayout({ opacity: 0.95 }).opacity, 0.93);
  assert.equal(L.normalizeLayout({ opacity: 1.0 }).opacity, 1);
  assert.equal(L.normalizeLayout({}).opacity, 0.86); // the old default 0.9
  for (let i = 0; i <= 100; i++) {
    const old = 0.9 + i / 1000;
    const got = L.normalizeLayout({ opacity: old }).opacity;
    assert.ok(Math.abs(got - (0.86 + (old - 0.9) * 1.4)) <= 0.005 + 1e-9, old + " -> " + got);
    assert.equal(got, Math.round(got * 100) / 100, "whole hundredths");
  }
  // once: a migrated layout carries v 2 and reads back unchanged
  for (const old of [0.9, 0.91, 0.95, 0.99, 1.0]) {
    const first = L.normalizeLayout({ opacity: old, corner: "top-left" });
    assert.equal(first.v, 2);
    assert.deepEqual(L.normalizeLayout(first), first);
  }
  // a non-number keeps the default, never NaN
  assert.equal(L.normalizeLayout({ opacity: "x" }).opacity, 0.86);
  assert.equal(L.normalizeLayout({ opacity: NaN, v: 2 }).opacity, 0.86);
});

test("displays are indexed left to right", () => {
  const order = L.orderDisplays(ALL).map((d) => d.id);
  assert.deepEqual(order, [20, 10, 30]);
  const desc = L.describeDisplays(ALL, 10);
  assert.deepEqual(desc.map((d) => d.index), [0, 1, 2]);
  assert.equal(desc[1].primary, true);
  assert.equal(desc[0].scale_factor, 1.5);
});

test("default: top-right of the primary work area", () => {
  const b = L.computeBounds({}, ALL, 10);
  assert.deepEqual([b.x, b.y, b.width, b.height],
                   [1920 - L.BASE.width - 16, 16, L.BASE.width, L.BASE.height]);
  assert.equal(b.displayId, 10);
});

test("every corner stays inside the work area (taskbar excluded)", () => {
  for (const corner of L.CORNERS) {
    const b = L.computeBounds({ corner: corner, margin: 24 }, ALL, 10);
    assert.ok(b.x >= 0 && b.y >= 0, corner);
    assert.ok(b.x + b.width <= 1920, corner);
    assert.ok(b.y + b.height <= 1040, corner);
  }
  const bl = L.computeBounds({ corner: "bottom-left", margin: 24 }, ALL, 10);
  assert.equal(bl.x, 24);
  assert.equal(bl.y, 1040 - L.BASE.height - 24);
  const tc = L.computeBounds({ corner: "top-center", margin: 0 }, ALL, 10);
  assert.equal(tc.x, Math.floor((1920 - L.BASE.width) / 2));
});

test("multi-monitor: index picks the monitor, negative origins work", () => {
  const b = L.computeBounds({ display: 0, corner: "top-left", margin: 10 }, ALL, 10);
  assert.equal(b.displayId, 20);
  assert.deepEqual([b.x, b.y], [-2560 + 10, -360 + 10]);
  assert.equal(b.scaleFactor, 1.5);
  const r = L.computeBounds({ display: 2, corner: "bottom-right", margin: 0 }, ALL, 10);
  assert.equal(r.displayId, 30);
  assert.equal(r.x + r.width, 1920 + 1280);
  assert.equal(r.y + r.height, 1024);
});

test("a stored monitor that is gone falls back to the primary", () => {
  const b = L.computeBounds({ display: 5 }, ALL, 10);
  assert.equal(b.displayId, 10);
  const none = L.computeBounds({ display: 1 }, [PRIMARY], 10);
  assert.equal(none.displayId, 10);
});

test("scale multiplies the window in DIPs and never exceeds the work area", () => {
  const b = L.computeBounds({ scale: 1.5 }, ALL, 10);
  assert.equal(b.width, Math.round(L.BASE.width * 1.5));
  assert.equal(b.height, Math.round(L.BASE.height * 1.5));
  assert.ok(Number.isInteger(b.x) && Number.isInteger(b.y));
  const tiny = disp(1, 0, 0, 300, 200, 2, 0);
  const t = L.computeBounds({ scale: 2, margin: 100 }, [tiny], 1);
  assert.ok(t.width <= 300 && t.height <= 200);
  assert.ok(t.x >= 0 && t.y >= 0 && t.x + t.width <= 300 && t.y + t.height <= 200);
});

test("UX-DPI: the HUD grows by itself only on tall low-scale monitors", () => {
  // DIP height = physical height / Windows scale factor.
  assert.equal(L.autoScale(disp(1, 0, 0, 1920, 1080, 1)), 1);    // 1080p 100%
  assert.equal(L.autoScale(disp(1, 0, 0, 2560, 1440, 1)), 1.2);  // 1440p 100%
  assert.equal(L.autoScale(disp(1, 0, 0, 2560, 1440, 1.5)), 1.2);  // 4K 150% (1440 DIP)
  assert.equal(L.autoScale(disp(1, 0, 0, 3072, 1728, 1.25)), 1.45); // 4K 125%
  assert.equal(L.autoScale(disp(1, 0, 0, 3840, 2160, 1)), 1.8);  // 4K 100%
  assert.equal(L.autoScale(disp(1, 0, 0, 7680, 4320, 1)), 2);    // 8K 100%: capped
  assert.equal(L.autoScale(null), 1);
  const big = disp(1, 0, 0, 3840, 2160, 1, 40);
  const b = L.computeBounds({ scale: 1.2 }, [big], 1);
  assert.equal(b.zoom, 2.16);
  assert.equal(b.width, Math.round(L.BASE.width * 2.16));
  assert.equal(L.computeBounds({}, [big], 1).zoom, 1.8);
  // 13 px secondary text: physical px never under the 1200 DIP size.
  assert.ok(13 * L.computeBounds({}, [big], 1).zoom >= 13 * 2160 / 1200);
  assert.equal(L.computeBounds({ scale: 1.5 }, ALL, 10).zoom, 1.5);
  assert.equal(L.computeBounds({ scale: 2 }, [disp(1, 0, 0, 7680, 4320, 1)], 1).zoom, 2.5);
});

test("anchor follows the corner", () => {
  assert.equal(L.anchor({ corner: "bottom-center" }), "bottom");
  assert.equal(L.anchor({ corner: "top-left" }), "top");
  assert.equal(L.anchor(null), "top");
});

const ITEM = { id: 1, from: "Tradewind", kind: "item", item: "Grim Bane Ruby Ring",
               price_amount: 5, price_currency: "exalted", league: "Standard",
               stash_tab: "Sale", left: 3, top: 7 };

test("tradeCard: item, unpriced and exchange", () => {
  assert.deepEqual(fmt.tradeCard(ITEM), {
    from: "Trade: Tradewind", item: "Grim Bane Ruby Ring",
    where: "5 exalted | tab Sale (3,7)" });
  const unpriced = fmt.tradeCard({ ...ITEM, price_amount: null, price_currency: null });
  assert.equal(unpriced.where, "no price set | tab Sale (3,7)");
  const ex = fmt.tradeCard({ id: 2, from: "Coin", kind: "exchange", item: "Chaos Orb",
                             want_amount: 10, price_amount: 1, price_currency: "Divine Orb" });
  assert.equal(ex.item, "10 Chaos Orb");
  assert.equal(ex.where, "for 1 Divine Orb");
  const long = fmt.tradeCard({ ...ITEM, item: "X".repeat(80) });
  assert.ok(long.item.length <= 34 && long.item.endsWith("..."));
  assert.deepEqual(fmt.tradeCard(null), { from: "", item: "", where: "" });
});

test("hudModel shows the newest open trade and repaints only on change", () => {
  const snap = { zone: "Clearfell", zone_entered_at: 0, level: 2, deaths: 0,
                 trade_requests: [], overlay_layout: { corner: "top-right" } };
  const a = gate.hudModel(snap, 10, "live");
  assert.equal(a.tradeItem, "");
  assert.equal(a.anchor, "top");
  const b = gate.hudModel({ ...snap, trade_requests: [ITEM, { ...ITEM, id: 2, from: "Q" }] },
                          10, "live");
  assert.equal(b.tradeFrom, "Trade: Q");
  assert.equal(b.tradeMore, "+1 more");
  assert.deepEqual(gate.changedFields(a, b), ["tradeFrom", "tradeItem", "tradeWhere", "tradeMore"]);
  const c = gate.hudModel({ ...snap, overlay_layout: { corner: "bottom-left" } }, 10, "live");
  assert.deepEqual(gate.changedFields(a, c), ["anchor"]);
});

/* OVL-LINE2-RULE: the hudModel line 2 fields (level, deaths, sep and the
   status word) follow the one order and the 26-character rule. */
test("hudModel: line 2 fields follow the order", () => {
  const snap = { zone: "Clearfell", zone_entered_at: 0, level: 74, deaths: 3,
                 trade_requests: [ITEM], overlay_layout: { corner: "top-right" } };
  const card = { head: "Upgrade: +12% DPS", line2: "Ring", line3: "", verdict: "upgrade",
                 expires_at: 100 };
  const line2 = (m) => [m.level, m.sep, m.deaths, gate.statusText(m)];
  // rank 7: level and deaths alone
  assert.deepEqual(line2(gate.hudModel(snap, 10, "live")), ["Lv 74", "|", "3 deaths", ""]);
  // rank 6: a campaign word that fits beside "Lv 74  3 deaths" (15 + 10 = 25)
  assert.deepEqual(line2(gate.hudModel({ ...snap, campaign: { word: "Boss: cold" } }, 10, "live")),
                   ["Lv 74", "|", "3 deaths", "Boss: cold"]);
  // rank 6 over 26 characters: the deaths text drops, the separator with it
  assert.deepEqual(line2(gate.hudModel({ ...snap, campaign: { word: "Boots: no speed" } }, 10,
                                       "live")), ["Lv 74", "", "", "Boots: no speed"]);
  // rank 4 beats rank 6
  assert.equal(gate.statusText(gate.hudModel({ ...snap, afk: true,
    campaign: { word: "Boss: cold" } }, 10, "live")), "AFK");
  // rank 3 beats rank 4
  assert.equal(gate.statusText(gate.hudModel({ ...snap, afk: true,
    underlevel: { word: "3 lv under" } }, 10, "live")), "3 lv under");
  // rank 2: a card covers the open trade, so the count beats rank 3
  const covered = gate.hudModel({ ...snap, card, underlevel: { word: "3 lv under" } }, 10, "live");
  assert.deepEqual(line2(covered), ["Lv 74", "|", "3 deaths", "1 trade"]);
  // rank 1: the Client.txt word beats the trade count
  const quiet = gate.hudModel({ ...snap, card,
    tailer: { consented: true, reading: false, path: "x" } }, 10, "live");
  assert.deepEqual(line2(quiet), ["Lv 74", "", "", "waiting for log"]);
  // rank 1 before any data: the word alone
  assert.deepEqual(line2(gate.hudModel(null, 10, "connecting")), ["", "", "", "connecting"]);
  const off = gate.hudModel({ ...snap, tailer: { consented: false } }, 10, "live");
  assert.deepEqual(line2(off), ["", "", "", "not reading - see dashboard"]);
  // a dropped deaths text is one repaint of the deaths and sep nodes
  const before = gate.hudModel(snap, 10, "live");
  const after = gate.hudModel({ ...snap, campaign: { word: "Boots: no speed" } }, 10, "live");
  assert.deepEqual(gate.changedFields(before, after), ["deaths", "sep", "campaign"]);
});

/* UX-REAL-OVERLAY: on the real desktop a transparent, software-composited
   window with BrowserWindow.setOpacity drew nothing at all. The value is
   page CSS instead; OVL-TD05-PLATE: only the plate alpha knob, never a
   page opacity, so text stays opaque. */
test("opacityCss sets the plate alpha only, clamped to the layout limits", () => {
  assert.equal(L.opacityCss(0.86), ":root { --al-plate-a: 0.86; }");
  assert.equal(L.opacityCss(1), ":root { --al-plate-a: 1; }");
  assert.equal(L.opacityCss(0.8), ":root { --al-plate-a: 0.8; }");
  assert.equal(L.opacityCss(0.2), ":root { --al-plate-a: 0.8; }");
  assert.equal(L.opacityCss("x"), ":root { --al-plate-a: 0.86; }");
  for (const v of [0.8, 0.86, 0.93, 1, 0.2, "x"]) {
    assert.ok(!/(?<![-\w])opacity\s*:/.test(L.opacityCss(v)), "no page opacity");
    assert.ok(!/html/.test(L.opacityCss(v)));
  }
});

test("OVL-TD05-PLATE: high-contrast modes replace the plate the knob feeds", () => {
  const css = require("fs").readFileSync(
    require("path").join(__dirname, "..", "overlay", "overlay.css"), "utf8");
  for (const q of ["prefers-contrast: more", "forced-colors: active"]) {
    const at = css.indexOf("@media (" + q + ")");
    assert.ok(at > 0, q);
    const end = css.indexOf(";", css.indexOf("--al-plate:", at));
    assert.ok(/--al-plate:\s*(#[0-9a-fA-F]{6}|Canvas)\s*;$/.test(css.slice(at, end + 1)), q);
  }
});

test("main.js never uses the window-level opacity", () => {
  const src = require("fs").readFileSync(require("path").join(__dirname, "..", "main.js"), "utf8");
  assert.ok(!/\.setOpacity\s*\(/.test(src), "BrowserWindow.setOpacity hides the overlay");
  assert.ok(/insertCSS\(/.test(src) && /opacityCss\(/.test(src));
});
