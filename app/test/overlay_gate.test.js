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
