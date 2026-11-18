"use strict";
/* DESKTOP-CLIENT (decision 0041), operator order 2026-11-17: the companion
   has the standard title bar and X closes it to the tray; the tray menu is
   Minimize / Restore, Show in-game overlay (reflects state), Restart
   overlay, Quit (everything); left-click restores; "Restart overlay" is
   one IPC action the dashboard reaches only inside the client
   (button id restart-overlay). */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const TrayMenu = require("../client/tray_menu.js");

const APP = path.join(__dirname, "..");
const WEB = path.join(APP, "..", "web");

function code(js) {
  return js.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

const WIN = code(fs.readFileSync(path.join(APP, "client", "window.js"), "utf8"));
const MAIN = code(fs.readFileSync(path.join(APP, "main.js"), "utf8"));

test("tray menu: the four actions, labels follow the state", () => {
  const calls = [];
  const acts = { toggleCompanion: () => calls.push("c"), toggleOverlay: () => calls.push("o"),
                 restart: () => calls.push("r"), quit: () => calls.push("q") };
  const shown = TrayMenu.trayTemplate({ overlayOn: true, companionShown: true }, acts);
  const byId = Object.fromEntries(shown.filter((i) => i.id).map((i) => [i.id, i]));
  assert.deepEqual(Object.keys(byId), ["companion", "overlay", "restart", "quit"]);
  assert.equal(byId.companion.label, "Minimize AshLight");
  assert.equal(byId.overlay.type, "checkbox");
  assert.equal(byId.overlay.checked, true);
  assert.equal(byId.restart.label, "Restart overlay");
  assert.equal(byId.quit.label, "Quit AshLight");
  const hidden = TrayMenu.trayTemplate({ overlayOn: false, companionShown: false }, acts);
  assert.equal(hidden[0].label, "Restore AshLight");
  assert.equal(hidden[1].checked, false);
  for (const item of shown) { if (item.click) { item.click(); } }
  assert.deepEqual(calls, ["c", "o", "r", "q"]);
  assert.match(TrayMenu.TOOLTIP, /Right-click for the menu/);
  assert.match(TrayMenu.CLOSED_NOTE, /keeps running/);
});

test("companion: standard title bar, X closes to the tray, left-click restores", () => {
  assert.match(WIN, /frame: true,/);
  assert.ok(!/maximizable: false|minimizable: false|closable: false|titleBarStyle/.test(WIN));
  // X: the window closes (renderer freed) and the tray note says AshLight runs on
  assert.match(WIN, /win\.on\("closed", \(\) => \{[\s\S]*?noteClosedToTray\(\);/);
  assert.match(WIN, /tray\.on\("click", open\);/);
  assert.match(WIN, /tray\.setToolTip\(TrayMenu\.TOOLTIP\);/);
  // Quit closes everything: stop.ps1 (core, supervisor, client + overlay)
  assert.match(WIN, /function quit\(\) \{\s*Launcher\.stopAll\(opts\.repo\);\s*app\.quit\(\);/);
  // the tray checkbox follows the window state on every change
  assert.match(WIN, /for \(const ev of \["minimize", "restore", "show", "hide"\]\) \{ win\.on\(ev, refresh\); \}/);
});

test("restart overlay: one IPC action, honoured from the companion's core page only", () => {
  const pre = code(fs.readFileSync(path.join(APP, "client", "preload.js"), "utf8"));
  assert.match(pre, /restartOverlay: \(\) => ipcRenderer\.send\("al:restart-overlay"\)/);
  assert.equal((pre.match(/ipcRenderer\./g) || []).length, 1);
  assert.ok(!/token|require\("fs"\)|invoke|sendSync/.test(pre));
  assert.match(MAIN, /ipcMain\.on\("al:restart-overlay", \(e\) => \{\s*if \(client && client\.isCompanion\(e\)\) \{ restartOverlay\(\); \}/);
  assert.match(WIN, /e\.senderFrame === win\.webContents\.mainFrame/);
  assert.match(WIN, /Link\.isCoreUrl\(e\.senderFrame\.url, port\)/);
  // a clean close and rebuild of the one overlay window
  const fn = MAIN.slice(MAIN.indexOf("function restartOverlay()"));
  const body = fn.slice(0, fn.indexOf("\n}\n"));
  assert.match(body, /old\.destroy\(\);/);
  assert.match(body, /createWindow\(\);/);
  assert.match(body, /if \(!wantsIt\) \{ gate\.toggleUser\(\); \}/);
});

function fakeDoc(ids) {
  const els = {};
  for (const id of ids) {
    els[id] = { id: id, hidden: true, textContent: "", listeners: {},
                addEventListener(t, f) { this.listeners[t] = f; } };
  }
  return els;
}

test("dashboard: the restart-overlay button shows only inside the client", () => {
  const html = fs.readFileSync(path.join(WEB, "index.html"), "utf8");
  assert.match(html, /<p id="restart-overlay-row" class="hint-reset" hidden><button id="restart-overlay" type="button" aria-describedby="restart-overlay-said">Restart overlay<\/button>\s*<span id="restart-overlay-said" class="muted"><\/span><\/p>/);
  const src = fs.readFileSync(path.join(WEB, "app.js"), "utf8");
  const start = src.indexOf("  function wireRestartOverlay()");
  const end = src.indexOf("\n  }\n", start) + 4;
  const fnSrc = src.slice(start, end);
  function run(alClient) {
    const els = fakeDoc(["restart-overlay-row", "restart-overlay", "restart-overlay-said"]);
    const ctx = { window: { alClient: alClient }, els: els, snap: null };
    vm.runInNewContext("function $(id) { return els[id]; }\n" +
      "function setText(n, t) { n.textContent = t; }\n" + fnSrc + "\nwireRestartOverlay();", ctx);
    return els;
  }
  const browser = run(undefined);
  assert.equal(browser["restart-overlay-row"].hidden, true);
  assert.equal(browser["restart-overlay"].listeners.click, undefined);
  let restarted = 0;
  const inClient = run({ restartOverlay: () => { restarted += 1; } });
  assert.equal(inClient["restart-overlay-row"].hidden, false);
  inClient["restart-overlay"].listeners.click();
  assert.equal(restarted, 1);
  assert.equal(inClient["restart-overlay-said"].textContent, "Restarting the overlay.");
});
