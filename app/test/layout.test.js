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
  assert.equal(n.opacity, 0.9);
  assert.equal(n.margin, 0);
  assert.equal(n.display, "primary");
});

test("DS-OPACITY / DS-SCALE: old layouts clamp to the floors", () => {
  assert.deepEqual(L.LAYOUT_LIMITS.opacity, [0.9, 1.0]);
  assert.deepEqual(L.LAYOUT_LIMITS.scale, [0.95, 2.0]);
  const n = L.normalizeLayout({ scale: 0.75, opacity: 0.3 });
  assert.equal(n.scale, 0.95);
  assert.equal(n.opacity, 0.9);
  assert.ok(13 * n.scale >= 12);
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
