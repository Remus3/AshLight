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

test("FOLLOWUP11: Windows system combinations are refused and all in the table", () => {
  for (const input of ["Alt+Shift+Tab", "Shift+Alt+Tab", "Ctrl+Alt+Tab", "Alt+Shift+Escape",
    "Ctrl+Shift+Esc", "Ctrl+Alt+Delete", "Ctrl+Alt+End", "Win+Tab", "Win+D"]) {
    assert.strictEqual(Hotkey.safeAccelerator(input), null, input);
    assert.ok(CASES.bad.includes(input), input);
  }
  for (const k of Hotkey.GAME_KEYS) { assert.ok(CASES.bad.includes(k), k); }
});

test("HOTKEYS-LIVE: every fallback is safe, canonical and not a game key", () => {
  assert.deepStrictEqual(JSON.parse(JSON.stringify(Hotkey.FALLBACKS)), CASES.fallbacks);
  const seen = new Set();
  for (const name of ["eval", "toggle"]) {
    const list = Hotkey.FALLBACKS[name];
    assert.ok(list.length >= 1 && list.length <= 4, name);
    for (const k of list) {
      assert.strictEqual(Hotkey.safeAccelerator(k), k, k);
      assert.ok(!Hotkey.GAME_KEYS.has(k), k);
      assert.ok(!CASES.bad.includes(k), k);
      assert.ok(!/^Ctrl\+Alt\+[A-Z0-9]$/.test(k), "AltGr letter " + k);
      assert.ok(!seen.has(k), "shared " + k);
      seen.add(k);
    }
  }
  assert.strictEqual(Hotkey.FALLBACKS.eval[0], "Alt+Shift+E");
  assert.strictEqual(Hotkey.FALLBACKS.toggle[0], "Alt+Shift+A");
});

test("HOTKEYS-LIVE: alternates skip the wanted key and the other shortcut's key", () => {
  assert.deepStrictEqual(Hotkey.alternates("eval", "alt+shift+e"),
    ["Ctrl+Shift+F9", "Alt+Shift+F9", "Ctrl+Alt+F9"]);
  assert.deepStrictEqual(Hotkey.alternates("toggle", "Ctrl+Alt+K", ["Alt+Shift+A"]),
    ["Ctrl+Shift+F10", "Alt+Shift+F10", "Ctrl+Alt+F10"]);
  assert.deepStrictEqual(Hotkey.alternates("other", "Alt+Shift+E"), []);
  assert.deepStrictEqual(Hotkey.alternates("__proto__", "Alt+Shift+E"), []);
});
