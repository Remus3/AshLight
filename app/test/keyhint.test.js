"use strict";
/* OVL-KEY-HINT (F-166, TD-17): the empty card slot teaches the item-check
   key. The core sends a card of kind "hint" (server/al/overlayview.py
   CARD_HOLDERS "hint", expires_at null while due); the overlay page
   renders it as one muted line, never over a trade card, and only while
   parts.hint is on. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const gate = require("../shared/render_gate.js");

const HEAD = "Alt+Shift+E: check an item";
const TRADE = { id: 1, from: "Kalandra", item: "Rusted Sword", where: "Stash tab 1",
                at: 1000 };

function hint(extra) {
  return Object.assign({ kind: "hint", head: HEAD, line2: "", line3: "",
                         verdict: "hint", expires_at: null }, extra || {});
}

function snap(extra, parts) {
  return Object.assign({
    zone: "Clearfell", in_hideout: false, in_town: false, zone_entered_at: 1000,
    level: 12, deaths: 2, version: 7, now: 1000, trade_requests: [],
    tailer: { consented: true, reading: true, path: "x" },
    overlay_layout: { corner: "top-right", parts: parts || {}, quiet_town: false },
    card: hint()
  }, extra || {});
}

test("the hint renders as line 1 only, marked muted", () => {
  const m = gate.hudModel(snap(), 1005, "live");
  assert.equal(m.evalHead, HEAD);
  assert.equal(m.evalItem, "");
  assert.equal(m.evalLine, "");
  assert.equal(m.evalVerdict, "hint");
  assert.equal(m.trades, "");
  /* stray lines from a core are never drawn under the hint */
  const extra = gate.hudModel(snap({ card: hint({ line2: "x", line3: "y" }) }), 1005, "live");
  assert.equal(extra.evalItem, "");
  assert.equal(extra.evalLine, "");
  /* the HUD lines stay as they were */
  assert.equal(m.zone, "Clearfell");
  assert.equal(m.level, "Lv 12");
});

test("the hint has no expiry while the core sends it", () => {
  const s = snap();
  assert.equal(gate.msUntilEvalExpires(s, 1005), null, "no timer for the hint");
  assert.equal(gate.hudModel(s, 1005 + 86400, "live").evalHead, HEAD);
  /* the core drops it on the next push: the slot is then empty */
  const gone = gate.hudModel(snap({ card: null }), 1006, "live");
  assert.equal(gone.evalHead, "");
  assert.equal(gate.shouldRender(gate.hudModel(s, 1005, "live"), gone), true);
});

test("never over a trade card: an open trade outranks the hint", () => {
  const m = gate.hudModel(snap({ trade_requests: [TRADE] }), 1005, "live");
  assert.equal(m.evalHead, "");
  assert.equal(m.evalVerdict, "");
  assert.equal(m.tradeItem, "Rusted Sword");
  assert.equal(m.tradeFrom, "Trade: Kalandra");
  assert.equal(m.trades, "");
  /* trade part off: no trade card, so the hint takes the free slot */
  const off = gate.hudModel(snap({ trade_requests: [TRADE] }, { trade: false }), 1005, "live");
  assert.equal(off.tradeItem, "");
  assert.equal(off.evalHead, HEAD);
  /* a press card still covers the trade card as before */
  const press = { kind: "eval", head: "Upgrade: +12% DPS", line2: "Ring", line3: "",
                  verdict: "upgrade", expires_at: 1020 };
  const p = gate.hudModel(snap({ trade_requests: [TRADE], card: press }), 1005, "live");
  assert.equal(p.evalHead, "Upgrade: +12% DPS");
  assert.equal(p.tradeItem, "");
});

test("parts.hint off hides it; parts.item does not", () => {
  assert.equal(gate.hudModel(snap({}, { hint: false }), 1005, "live").evalHead, "");
  assert.equal(gate.hudModel(snap({}, { item: false, moment: false }), 1005, "live").evalHead,
               HEAD);
});

test("the hint line fits the 34-character card clip", () => {
  const key19 = gate.hudModel(snap({ card: hint({ head: "Ctrl+Shift+PageDown: check an item" }) }),
                              1005, "live");
  assert.equal(key19.evalHead.length, 34);
  assert.equal(key19.evalHead, "Ctrl+Shift+PageDown: check an item");
  const long = gate.hudModel(snap({ card: hint({ head: "Ctrl+Alt+Shift+Backspace: check an item" }) }),
                             1005, "live");
  assert.equal(long.evalHead.length, 34);
  assert.ok(long.evalHead.endsWith("..."));
});

test("the page draws the hint as one muted line", () => {
  const root = path.join(__dirname, "..", "overlay");
  const js = fs.readFileSync(path.join(root, "overlay.js"), "utf8");
  assert.match(js, /setAttribute\("data-verdict", model\.evalVerdict\)/);
  const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
  assert.match(html, /id="evalHead" class="row head"/);
  const css = fs.readFileSync(path.join(root, "overlay.css"), "utf8");
  const rule = /\.evalcard\[data-verdict="hint"\] \.head \{([^}]*)\}/.exec(css);
  assert.ok(rule, "a muted rule for the hint line");
  assert.match(rule[1], /color:\s*var\(--al-ovl-text-2\)/);
  assert.match(rule[1], /font-weight:\s*400/);
  assert.doesNotMatch(rule[1], /font(-size)?\s*:/, "the card size stays");
  /* the edge stays the neutral card edge (--al-edge): no own colour */
  assert.doesNotMatch(css, /\.evalcard\[data-verdict="hint"\] \{/);
});
