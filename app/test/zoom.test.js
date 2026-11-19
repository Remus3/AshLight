"use strict";
/* OVL-CLIENT-ZOOM: page zoom keys in the desktop client window. */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const Zoom = require("../client/zoom.js");
const Part = require("../parts/30-zoom.js");

function key(k, mods, code) {
  return Object.assign({ type: "keyDown", key: k, code: code || "", control: true,
                         meta: false, alt: false, shift: false }, mods || {});
}

test("Ctrl plus / minus / 0 map to in / out / reset; other keys do nothing", () => {
  assert.equal(Zoom.actionFor(key("=")), "in");
  assert.equal(Zoom.actionFor(key("+", { shift: true })), "in");
  assert.equal(Zoom.actionFor(key("+", {}, "NumpadAdd")), "in");
  assert.equal(Zoom.actionFor(key("-")), "out");
  assert.equal(Zoom.actionFor(key("-", {}, "NumpadSubtract")), "out");
  assert.equal(Zoom.actionFor(key("0")), "reset");
  assert.equal(Zoom.actionFor(key("0", {}, "Numpad0")), "reset");
  assert.equal(Zoom.actionFor(key("=", { control: false })), null);
  assert.equal(Zoom.actionFor(key("=", { alt: true })), null);
  assert.equal(Zoom.actionFor(key("=", { type: "keyUp" })), null);
  assert.equal(Zoom.actionFor(key("a")), null);
  assert.equal(Zoom.actionFor(null), null);
});

test("one step in from 1.0 is 1.1, 2.0 is reachable and the cap", () => {
  assert.equal(Zoom.step(1, "in"), 1.1);
  assert.equal(Zoom.step(1, "out"), 0.9);
  assert.equal(Zoom.step(1.7, "reset"), 1);
  let f = 1;
  for (let i = 0; i < 20; i += 1) { f = Zoom.step(f, "in"); }
  assert.equal(f, 2);
  assert.equal(Zoom.MAX, 2);
  for (let i = 0; i < 30; i += 1) { f = Zoom.step(f, "out"); }
  assert.equal(f, Zoom.MIN);
  // an off-list factor moves to the next level in that direction
  assert.equal(Zoom.step(1.05, "in"), 1.1);
  assert.equal(Zoom.step(1.05, "out"), 1);
  assert.equal(Zoom.step(NaN, "in"), 1.1);
});

test("the factor is saved and read back; a bad file is 1.0", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "al-zoom-"));
  assert.equal(Zoom.load(dir), 1);
  Zoom.save(dir, 1.25);
  const raw = fs.readFileSync(path.join(dir, Zoom.FILE_NAME), "utf8");
  assert.equal(raw, '{"zoom":1.25}\n');
  assert.equal(Zoom.load(dir), 1.25);
  fs.writeFileSync(path.join(dir, Zoom.FILE_NAME), '{"zoom":9}');
  assert.equal(Zoom.load(dir), 1);
  fs.writeFileSync(path.join(dir, Zoom.FILE_NAME), "not json");
  assert.equal(Zoom.load(dir), 1);
  assert.equal(Zoom.load(null), 1);
  Zoom.save(null, 1.5); // no runtime dir: nothing written, no throw
});

function fakeWin() {
  const on = {};
  const wc = {
    factor: 1, sets: [],
    on: (ev, fn) => { (on[ev] = on[ev] || []).push(fn); return wc; },
    setZoomFactor: (f) => { wc.factor = f; wc.sets.push(f); },
    getZoomFactor: () => wc.factor,
    isDestroyed: () => false
  };
  return {
    webContents: wc,
    emit: (ev, ...args) => (on[ev] || []).forEach((fn) => fn(...args))
  };
}

function press(win, k, mods, code) {
  let prevented = false;
  win.emit("before-input-event", { preventDefault: () => { prevented = true; } }, key(k, mods, code));
  return prevented;
}

test("the part zooms the client window on its own keys and wheel, and persists", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "al-zoom-"));
  const ctx = { runtimeDir: dir, log: () => {} };
  const win = fakeWin();
  Part.clientWindow(ctx, win);
  assert.equal(win.webContents.factor, 1);
  assert.equal(press(win, "="), true);
  assert.equal(win.webContents.factor, 1.1);
  assert.equal(press(win, "a"), false); // other keys reach the page untouched
  assert.equal(win.webContents.factor, 1.1);
  win.emit("zoom-changed", {}, "in"); // Ctrl+wheel
  assert.equal(win.webContents.factor, 1.25);
  win.emit("zoom-changed", {}, "out");
  assert.equal(win.webContents.factor, 1.1);
  for (let i = 0; i < 12; i += 1) { press(win, "="); }
  assert.equal(win.webContents.factor, 2);
  // a navigation (starting page -> dashboard) keeps the player's factor
  win.webContents.factor = 1;
  win.emit("did-finish-load");
  assert.equal(win.webContents.factor, 2);
  // the factor survives a window restart
  const again = fakeWin();
  Part.clientWindow(ctx, again);
  assert.equal(again.webContents.factor, 2);
  press(again, "0");
  assert.equal(again.webContents.factor, 1);
  assert.equal(Zoom.load(dir), 1);
});

test("the part touches only the client window, never the overlay", () => {
  assert.equal(typeof Part.clientWindow, "function");
  assert.equal(Part.overlayWindow, undefined);
  const src = fs.readFileSync(path.join(__dirname, "..", "parts", "30-zoom.js"), "utf8");
  assert.ok(!/getOverlay|globalShortcut/.test(src));
});
