"use strict";
/* AUDIT-ELECTRON (audit findings S6-S7, docs/audit/2026-11-17-audit.md):
   the overlay is never packaged, so devTools must not follow
   !app.isPackaged (always on); they follow an explicit AL_DEV=1 env. And a
   permission CHECK handler denies every check next to the request handler. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const SRC = fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf8");

test("devTools are gated on AL_DEV, not on isPackaged", () => {
  assert.doesNotMatch(SRC, /devTools:\s*!app\.isPackaged/);
  assert.match(SRC, /devTools:\s*DEV_TOOLS\b/);
  assert.match(SRC, /const DEV_TOOLS = process\.env\.AL_DEV === "1";/);
});

test("permission checks and requests are both denied", () => {
  assert.match(SRC, /setPermissionRequestHandler\(\(wc, perm, cb\) => cb\(false\)\)/);
  assert.match(SRC, /setPermissionCheckHandler\(\(\) => false\)/);
});

/* OVL-SHELL-GUARDS (decision 0061): the shell guards live in one part the
   next window inherits, and the IPC block answers only exact senders. */
function code(js) {
  return js.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}
const MAIN = code(SRC);
const PART = code(fs.readFileSync(path.join(__dirname, "..", "parts", "10-guards.js"), "utf8"));

test("the guards part: sandbox, WebGL off, defaults on every new webContents", () => {
  assert.match(PART, /app\.enableSandbox\(\)/);
  assert.match(PART, /appendSwitch\("disable-webgl"\)/);
  assert.match(PART, /app\.on\("web-contents-created"/);
  assert.match(PART, /Guards\.attachDefaults\(wc, reg/);
  assert.match(PART, /Guards\.isDebugStart\(argv, env\)/);
  // 10-guards runs first, or second after 05-crashguard (which creates no window or webContents)
  const parts = fs.readdirSync(path.join(__dirname, "..", "parts")).filter((n) => n.endsWith(".js")).sort();
  const guardAt = parts.indexOf("10-guards.js");
  assert.ok(guardAt === 0 || (guardAt === 1 && parts[0] === "05-crashguard.js"), parts.join());
  const CG = fs.readFileSync(path.join(__dirname, "..", "parts", "05-crashguard.js"), "utf8");
  assert.doesNotMatch(CG, /new\s+(BrowserWindow|BrowserView|WebContentsView)/);
});

test("main.js: exact-sender IPC, throttled restart, popups still denied", () => {
  assert.match(MAIN, /Guards\.frameIsOverlayPage\(e\.senderFrame, win, OVERLAY_URL\)/);
  // OVL-APP-SCHEME (decision 0061 amendment 2026-11-21): the app scheme
  // URL, loaded with loadURL; no file page is loaded any more
  assert.match(MAIN, /const OVERLAY_URL = Pages\.urlFor\("overlay\/index\.html"\);/);
  assert.match(MAIN, /win\.loadURL\(OVERLAY_URL\);/);
  assert.doesNotMatch(MAIN, /loadFile\(|pathToFileURL/);
  assert.doesNotMatch(MAIN, /endsWith\("\/overlay\/index\.html"\)/);
  assert.match(MAIN, /const restartGate = Guards\.throttle\(RESTART_MIN_MS\);/);
  assert.match(MAIN, /const RESTART_MIN_MS = 2000;/);
  const fn = MAIN.slice(MAIN.indexOf("function restartOverlay()"));
  assert.match(fn.slice(0, fn.indexOf("\n}\n")), /^function restartOverlay\(\) \{\s*if \(!restartGate\(\)\)/);
  assert.match(MAIN, /setWindowOpenHandler\(\(\) => \(\{ action: "deny" \}\)\)/);
  assert.match(MAIN, /e\.sender !== win\.webContents/);
});
