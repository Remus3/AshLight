"use strict";
/* PLAY-TD-04A-DARK-CLIENT (TD-04): the desktop client opens dark before
   its first window. main.js, client/window.js and client/starting.css are
   read as text; nothing starts Electron. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const APP = path.join(__dirname, "..");
const MAIN_SRC = fs.readFileSync(path.join(APP, "main.js"), "utf8");
const WIN_SRC = fs.readFileSync(path.join(APP, "client", "window.js"), "utf8");
const CSS = fs.readFileSync(path.join(APP, "client", "starting.css"), "utf8");
const KIT_TOKENS = path.join(APP, "..", "ops", "fleet_kit", "tokens.css");

const SURFACE = "#0f1216";
const TEXT = "#e4e8ec";
const MUTED = "#99a1aa";

function luminance(hex) {
  const n = parseInt(hex.slice(1), 16);
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
}

function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

test("main.js sets the native theme to dark before any window is created", () => {
  assert.match(MAIN_SRC, /nativeTheme[^;]*\}\s*=\s*require\("electron"\)/);
  const set = MAIN_SRC.indexOf('nativeTheme.themeSource = "dark";');
  assert.ok(set > 0, "nativeTheme.themeSource = \"dark\" is missing");
  assert.equal(MAIN_SRC.indexOf("nativeTheme.themeSource", set + 1), -1,
    "the theme source is set once only");
  const firstWindow = MAIN_SRC.indexOf("new BrowserWindow(");
  assert.ok(firstWindow > set, "a BrowserWindow is created before the theme is set");
  const ready = MAIN_SRC.indexOf("app.whenReady().then(start)");
  assert.ok(ready > set, "the theme is set before app.whenReady().then(start)");
  const client = MAIN_SRC.indexOf('require("./client/window.js")');
  assert.ok(client > set, "the client window module is reached before the theme is set");
});

test("the client window paints the kit's dark surface before its page loads", () => {
  assert.match(WIN_SRC, /backgroundColor:\s*"#0f1216"/);
  assert.doesNotMatch(WIN_SRC, /#16181d/i);
});

test("the start page is dark by default with the kit's dark values", () => {
  assert.doesNotMatch(CSS, /prefers-color-scheme/);
  assert.doesNotMatch(CSS, /color-scheme:\s*light/);
  for (const v of [SURFACE, TEXT, MUTED]) {
    assert.ok(CSS.toLowerCase().includes(v), v + " is missing from starting.css");
  }
  assert.match(CSS, /font:[^;]*system-ui,\s*"Segoe UI",\s*sans-serif/);
  for (const old of ["#16181d", "#e8e8e6", "#a9adb5", "#f6f6f4", "#1d1f23", "#4f5560"]) {
    assert.ok(!CSS.toLowerCase().includes(old), old + " is a pre-TD-04 value");
  }
});

test("the start page values are the kit's dark tokens", () => {
  const kit = fs.readFileSync(KIT_TOKENS, "utf8").toLowerCase();
  assert.ok(kit.includes("--fk-surface: " + SURFACE));
  assert.ok(kit.includes("--fk-text: " + TEXT));
  assert.ok(kit.includes("--fk-text-muted: " + MUTED));
});

test("the start page text keeps its contrast on the dark surface", () => {
  assert.ok(contrast(TEXT, SURFACE) >= 7, "body text below 7:1");
  assert.ok(contrast(MUTED, SURFACE) >= 4.5, "muted text below 4.5:1");
});
