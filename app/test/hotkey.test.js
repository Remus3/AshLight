"use strict";
/* AREA-AUDIT P5-3: an AshLight hotkey always needs a modifier and never
   takes a key the game uses, before globalShortcut.register sees it. */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const Hotkey = require("../hotkey.js");

const CASES = JSON.parse(fs.readFileSync(path.join(__dirname, "hotkey_cases.json"), "utf8"));
const MAIN = fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf8");

test("safe hotkeys come back canonical", () => {
  for (const [input, want] of Object.entries(CASES.ok)) {
    assert.strictEqual(Hotkey.safeAccelerator(input), want, input);
  }
});

test("bare keys, Shift+typing keys and game keys are refused", () => {
  for (const input of CASES.bad) {
    assert.strictEqual(Hotkey.safeAccelerator(input), null, JSON.stringify(input));
  }
  for (const input of [null, undefined, 5, {}, ["Alt", "K"]]) {
    assert.strictEqual(Hotkey.safeAccelerator(input), null);
  }
});

test("pick takes the first safe candidate, else the default", () => {
  const logged = [];
  const log = (m) => logged.push(m);
  assert.strictEqual(Hotkey.pick(["C", "ctrl+alt+k"], "Alt+Shift+A", log), "Ctrl+Alt+K");
  assert.strictEqual(logged.length, 1);
  assert.match(logged[0], /hotkey "C" refused/);
  assert.strictEqual(Hotkey.pick([undefined, "", "Space"], "Alt+Shift+A", log), "Alt+Shift+A");
});

test("main.js validates both hotkeys before globalShortcut.register", () => {
  assert.match(MAIN, /require\("\.\/hotkey\.js"\)/);
  assert.match(MAIN, /const toggleKey = Hotkey\.pick\(/);
  assert.match(MAIN, /const evalKey = Hotkey\.pick\(/);
  assert.ok(!/config\.overlay_toggle \|\|/.test(MAIN), "raw config hotkey still used");
  assert.ok(!/config\.eval_hotkey \|\|/.test(MAIN), "raw config hotkey still used");
  for (const m of MAIN.matchAll(/globalShortcut\.register\(([^,]+),/g)) {
    assert.ok(["toggleKey", "evalKey"].includes(m[1].trim()), m[1]);
  }
});
