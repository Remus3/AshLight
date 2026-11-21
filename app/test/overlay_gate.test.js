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
  assert.match(Gate.HINTS.starting, /once the game log is active/);
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
