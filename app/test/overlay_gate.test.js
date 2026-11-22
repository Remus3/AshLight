"use strict";
/* Decision 0029 amendment 2026-11-17 (DESKTOP-CLIENT, decision 0041): the
   overlay hides while the game may be closed (snapshot game_idle, Client.txt
   staleness only) and comes back on the next fresh line; app/overlay_gate.js
   is the one place that decides, setOverlayGate in main.js its one hook. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Gate = require("../overlay_gate.js");
const S = require("../shared/render_gate.js");

function code(js) {
  return js.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

function fakeView() {
  const v = { visible: false, calls: [] };
  v.isVisible = () => v.visible;
  v.showInactive = () => { v.visible = true; v.calls.push("show"); };
  v.hide = () => { v.visible = false; v.calls.push("hide"); };
  return v;
}

test("idle hides, a fresh line shows again (showInactive only)", () => {
  const v = fakeView();
  const g = Gate.createOverlayGate(v);
  g.ready();
  assert.equal(v.visible, false); // not before the first report
  g.setGate(true);
  assert.deepEqual(v.calls, ["show"]);
  g.setGate(false); // idle: game may be closed
  assert.equal(v.visible, false);
  g.setGate(false);
  g.setGate(true); // fresh log line
  assert.deepEqual(v.calls, ["show", "hide", "show"]);
});

test("stale at start stays hidden, no flash", () => {
  const v = fakeView();
  const g = Gate.createOverlayGate(v);
  g.ready();
  g.setGate(false);
  g.graceOver();
  assert.deepEqual(v.calls, []);
  g.setGate(true);
  assert.deepEqual(v.calls, ["show"]);
});

test("no report in time shows the HUD (offline word); the player's off wins", () => {
  const v = fakeView();
  const g = Gate.createOverlayGate(v);
  g.setGate(true); // a report before ready: nothing yet
  assert.deepEqual(v.calls, []);
  g.ready();
  assert.deepEqual(v.calls, ["show"]);
  g.toggleUser();
  assert.equal(v.visible, false);
  assert.equal(g.userWants(), false);
  g.setGate(false);
  g.setGate(true); // the gate never overrides the player's off
  assert.equal(v.visible, false);
  g.toggleUser();
  assert.equal(v.visible, true);
  const w = fakeView();
  const h = Gate.createOverlayGate(w);
  h.ready();
  h.graceOver();
  assert.deepEqual(w.calls, ["show"]);
  assert.ok(Gate.GRACE_MS > 0 && Gate.GRACE_MS <= 5000);
});

test("overlayWanted reads game_idle from a live snapshot only", () => {
  assert.equal(S.overlayWanted({ game_idle: true }, "live"), false);
  assert.equal(S.overlayWanted({ game_idle: false }, "live"), true);
  assert.equal(S.overlayWanted({ game_idle: true }, "offline"), true);
  assert.equal(S.overlayWanted(null, "live"), true);
  // an older core without game_idle: the 0029 tailer fields
  assert.equal(S.overlayWanted({ tailer: { consented: true, idle: true } }, "live"), false);
  assert.equal(S.overlayWanted({ tailer: { consented: false, idle: true } }, "live"), true);
});

test("the overlay page reports the gate on change only, via the preload", () => {
  const ovl = code(fs.readFileSync(path.join(__dirname, "..", "overlay", "overlay.js"), "utf8"));
  assert.match(ovl, /var want = S\.overlayWanted\(snap, status\);/);
  assert.match(ovl, /if \(want !== reported && typeof cfg\.reportGate === "function"\)/);
  const pre = code(fs.readFileSync(path.join(__dirname, "..", "preload.js"), "utf8"));
  assert.match(pre, /reportGate: \(visible\) => ipcRenderer\.send\("al:gate", visible === true\)/);
  assert.equal((pre.match(/ipcRenderer\.send\(/g) || []).length, 1);
  const main = code(fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf8"));
  assert.equal((main.match(/gate\.setGate\(/g) || []).length, 1); // one hook
});

/* RUN-EXPLAIN-OVERLAY-STATE (F-129): the gate names why the overlay is
   shown or hidden, from its own flags only. */
test("gate exposes one of four states", () => {
  assert.deepEqual(Gate.STATES, ["shown", "hidden_user", "hidden_idle", "starting"]);
  const v = fakeView();
  const g = Gate.createOverlayGate(v);
  const seen = [];
  const note = () => { const s = g.state(); assert.ok(Gate.STATES.includes(s), s); seen.push(s); };
  note(); // a new window: starting
  g.ready(); note(); // ready, no report yet: still starting
  g.setGate(true); note(); // shown
  g.setGate(false); note(); // the game looks closed
  g.toggleUser(); note(); // the player's off wins over the idle gate
  g.setGate(true); note();
  g.toggleUser(); note(); // back on, gate open: shown
  g.reset(); note(); // a new window re-seeds: starting
  assert.deepEqual(seen, ["starting", "starting", "shown", "hidden_idle", "hidden_user",
                          "hidden_user", "shown", "starting"]);
  // the state always agrees with what the gate did to the window
  const w = fakeView();
  const h = Gate.createOverlayGate(w);
  h.ready();
  h.graceOver();
  assert.equal(h.state(), "shown");
  assert.equal(w.visible, true);
  h.toggleUser();
  assert.equal(h.state(), "hidden_user");
  assert.equal(w.visible, false);
  // the player's off before the page is ready already reads hidden_user
  const x = Gate.createOverlayGate(fakeView());
  x.toggleUser();
  assert.equal(x.state(), "hidden_user");
  // one fixed hint per state; exclusive fullscreen is only named, never detected
  for (const s of Gate.STATES) {
    assert.equal(typeof Gate.HINTS[s], "string");
    assert.ok(/^[\x20-\x7e]+$/.test(Gate.HINTS[s]) && Gate.HINTS[s].length < 200, s);
  }
  assert.match(Gate.HINTS.shown, /exclusive fullscreen/);
  assert.match(Gate.HINTS.shown, /Windowed Fullscreen/);
  for (const sentence of Gate.HINTS.shown.split(/(?<=\.) /)) {
    assert.ok(sentence.split(" ").length <= 20, sentence);
  }
  assert.match(Gate.HINTS.starting, /a few seconds/);
  const mod = code(fs.readFileSync(path.join(__dirname, "..", "overlay_gate.js"), "utf8"));
  for (const word of ["require(", "getAllDisplays", "getAllWindows", "getFocusedWindow", "FindWindow",
                      "process", "child_process"]) {
    assert.ok(!mod.includes(word), word);
  }
  assert.ok(!/(^|[^A-Za-z])screen\./.test(mod), "screen.");
  // main.js asks for a state write after a toggle and after a gate report
  const main = code(fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf8"));
  const toggleFn = main.slice(main.indexOf("function toggle()"), main.indexOf("function restartOverlay()"));
  assert.match(toggleFn, /gate\.toggleUser\(\);\s*noteOverlayState\(\);/);
  const gateFn = main.slice(main.indexOf("function setOverlayGate(visible)"));
  assert.match(gateFn.slice(0, gateFn.indexOf("\n}\n")), /gate\.setGate\(visible === true\); \}\s*noteOverlayState\(\);/);
  assert.match(main, /function overlayState\(\) \{\s*return gate \? gate\.state\(\) : "starting";\s*\}/);
  assert.match(main, /overlayState: overlayState, log: log \}\);/);
});

/* OVL-LINE2-GUIDE (plan 03 section 5.3): the card's near edge is anchored
   62 px from the window's anchored edge (the 2-line HUD, 55.6 px, + 6),
   whatever line 2 shows. The HUD plate is out of the flow at that edge
   and the cards start after the body padding, so no HUD state (two lines,
   the guide line, one line, no plate) can move a card. */
function cssRules(css) {
  const out = {};
  const flat = css.replace(/\/\*[\s\S]*?\*\//g, "").replace(/@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g, "");
  for (const m of flat.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const decl = {};
    for (const d of m[2].split(";")) {
      const i = d.indexOf(":");
      if (i > 0) { decl[d.slice(0, i).trim()] = d.slice(i + 1).trim(); }
    }
    out[m[1].trim()] = Object.assign(out[m[1].trim()] || {}, decl);
  }
  return out;
}

function px(v) {
  const m = /^(-?[\d.]+)px$/.exec(String(v || "").trim());
  return m ? Number(m[1]) : (String(v || "").trim() === "0" ? 0 : NaN);
}

test("the card's near edge is 62 px from the anchored edge in every state", () => {
  const css = fs.readFileSync(path.join(__dirname, "..", "overlay", "overlay.css"), "utf8");
  const r = cssRules(css);
  const ANCHOR = 62;
  // the 2-line HUD height from the CSS itself: border + padding + 2 lines
  const hud = r[".hud"];
  const fs16 = px(/--al-ovl-fs-hud:\s*([^;]+);/.exec(css)[1]);
  const lh = Number(/\/([\d.]+)\s/.exec(hud.font)[1]);
  const pad = hud.padding.split(/\s+/).map(px);
  const border = px(hud.border.split(/\s+/)[0]);
  const hudH = 2 * border + 2 * pad[0] + 2 * fs16 * lh;
  assert.ok(Math.abs(hudH - 55.6) < 0.01, String(hudH));
  assert.equal(Math.ceil(hudH) + 6, ANCHOR);
  // the HUD sits out of the flow, at the anchored edge, for both anchors
  assert.equal(hud.position, "absolute");
  assert.equal(px(hud.top), 0);
  assert.equal(px(hud.left), 0);
  assert.equal(px(hud.right), 0);
  assert.equal(px(hud.margin), 0);
  assert.ok(!("min-height" in hud) && !("height" in hud));
  const hudBottom = r['body[data-anchor="bottom"] .hud'];
  assert.equal(hudBottom.top, "auto");
  assert.equal(px(hudBottom.bottom), 0);
  // the cards start ANCHOR px from the anchored edge: top, then bottom
  const body = r.body;
  assert.equal(body.position, "relative");
  assert.equal(body["box-sizing"], "border-box");
  assert.equal(body["flex-direction"], "column");
  assert.equal(px(body["padding-top"]), ANCHOR);
  assert.equal(px(r["html, body"].margin), 0);
  const bottom = r['body[data-anchor="bottom"]'];
  assert.equal(bottom["flex-direction"], "column-reverse");
  assert.equal(px(bottom["padding-top"]), 0);
  assert.equal(px(bottom["padding-bottom"]), ANCHOR);
  // the cards are plain flow items with no margin of their own, so the
  // near edge of the first card is exactly the body padding
  for (const sel of [".trade", ".evalcard"]) {
    assert.equal(px(r[sel].margin), 0, sel);
    assert.ok(!("position" in r[sel]), sel);
  }
  // no other rule positions or sizes the HUD, the body or a card by state
  for (const sel of Object.keys(r)) {
    if (/(^|[\s,])\.(trade|evalcard)\b/.test(sel) && sel !== ".trade" && sel !== ".evalcard") {
      for (const k of ["margin", "margin-top", "margin-bottom", "position", "top", "bottom"]) {
        assert.ok(!(k in r[sel]), sel + " " + k);
      }
    }
  }
  // the card fits under the anchor inside the window (layout.js BASE)
  const L = require("../shared/layout.js");
  const card = 2 * 1 + 2 * 5 + 3 * 14 * 1.3;
  assert.ok(ANCHOR + card <= L.BASE.height, String(ANCHOR + card));
  // the HUD and the cards are siblings in the body, the HUD first
  const html = fs.readFileSync(path.join(__dirname, "..", "overlay", "index.html"), "utf8");
  const order = ["id=\"hud\"", "id=\"trade\"", "id=\"evalCard\""].map((s) => html.indexOf(s));
  assert.ok(order.every((i) => i > 0) && order[0] < order[1] && order[1] < order[2], order.join());
});

/* ZONE-CARD-ITEM-GATE (OVL-ZONE-CARD review D-1): the zone moment card
   follows parts.moment, never parts.item. */
test("a kind zone card renders with parts.item off and an item card does not", () => {
  const base = {
    zone: "The Grelwood", in_hideout: false, in_town: false, zone_entered_at: 1000,
    level: 12, deaths: 0, now: 1000, trade_requests: [],
    tailer: { consented: true, reading: true, path: "x" }
  };
  const zone = { kind: "zone", head: "Find the Sacred Grove", line2: "Next: The Red Vale",
                 line3: "Fits Lv 12", verdict: "", expires_at: 1012 };
  const item = { kind: "eval", head: "Upgrade: +12% DPS", line2: "Ring", line3: "Life +40",
                 verdict: "upgrade", expires_at: 1020 };
  const snapOf = (parts, card) => Object.assign({}, base,
    { overlay_layout: { corner: "top-right", parts: parts }, card: card });
  const zoneNoItem = S.hudModel(snapOf({ item: false }, zone), 1005, "live");
  assert.equal(zoneNoItem.evalHead, "Find the Sacred Grove");
  assert.equal(zoneNoItem.evalItem, "Next: The Red Vale");
  assert.ok(S.msUntilEvalExpires(snapOf({ item: false }, zone), 1005) > 0);
  const itemNoItem = S.hudModel(snapOf({ item: false }, item), 1005, "live");
  assert.equal(itemNoItem.evalHead, "");
  assert.equal(S.msUntilEvalExpires(snapOf({ item: false }, item), 1005), null);
  // the zone card's own part is parts.moment; it does not touch item cards
  assert.equal(S.hudModel(snapOf({ moment: false }, zone), 1005, "live").evalHead, "");
  assert.equal(S.hudModel(snapOf({ moment: false }, item), 1005, "live").evalHead,
               "Upgrade: +12% DPS");
  assert.equal(S.hudModel(snapOf({}, zone), 1005, "live").evalHead, "Find the Sacred Grove");
});
