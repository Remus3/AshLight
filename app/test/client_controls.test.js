"use strict";
/* DESKTOP-CLIENT (decision 0041), operator order 2026-11-17: the companion
   has the standard title bar and X closes it to the tray; the tray menu is
   Minimize / Restore, Show in-game overlay (reflects state), Restart
   overlay, Quit (everything); left-click restores; "Restart overlay" is
   one IPC action the dashboard reaches only inside the client
   (button id restart-overlay). OVL-WAKE-COMPANION: the tray checkbox
   "Open AshLight when the game wakes" switches the companion's return and
   is kept in client-prefs.json (default on). */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const os = require("node:os");
const Link = require("../client/link.js");
const TrayMenu = require("../client/tray_menu.js");
const web = require("./_web.js");

const APP = path.join(__dirname, "..");

function code(js) {
  return js.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

const WIN = code(fs.readFileSync(path.join(APP, "client", "window.js"), "utf8"));
const MAIN = code(fs.readFileSync(path.join(APP, "main.js"), "utf8"));

test("tray menu: the six actions, labels follow the state", () => {
  const calls = [];
  const acts = { toggleCompanion: () => calls.push("c"), toggleOverlay: () => calls.push("o"),
                 toggleWake: () => calls.push("w"), toggleAutostart: () => calls.push("a"),
                 restart: () => calls.push("r"), quit: () => calls.push("q") };
  const shown = TrayMenu.trayTemplate({ overlayOn: true, companionShown: true, wakeOn: true,
                                        autostartOn: true }, acts);
  const byId = Object.fromEntries(shown.filter((i) => i.id).map((i) => [i.id, i]));
  assert.deepEqual(Object.keys(byId), ["companion", "overlay", "wake", "autostart", "restart",
                                     "quit"]);
  assert.equal(byId.autostart.label, "Start with Windows");
  assert.equal(byId.autostart.type, "checkbox");
  assert.equal(byId.autostart.checked, true);
  assert.equal(byId.wake.label, "Open AshLight when the game wakes");
  assert.equal(byId.wake.type, "checkbox");
  assert.equal(byId.wake.checked, true);
  assert.equal(byId.companion.label, "Minimize AshLight");
  assert.equal(byId.overlay.type, "checkbox");
  assert.equal(byId.overlay.checked, true);
  assert.equal(byId.restart.label, "Restart overlay");
  assert.equal(byId.quit.label, "Quit AshLight");
  const hidden = TrayMenu.trayTemplate({ overlayOn: false, companionShown: false }, acts);
  assert.equal(hidden[0].label, "Restore AshLight");
  assert.equal(hidden[1].checked, false);
  assert.equal(hidden[2].checked, false);
  assert.equal(hidden[3].checked, false);
  for (const item of shown) { if (item.click) { item.click(); } }
  assert.deepEqual(calls, ["c", "o", "w", "a", "r", "q"]);
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
  // ruling Q-08: a small fixed set of argument-free actions (restart
  // overlay, autostart on / off / state, set up the calc (ruling W16-1);
  // app/test/autostart_switch.test.js)
  assert.equal((pre.match(/ipcRenderer\./g) || []).length, 5);
  assert.equal((pre.match(/ipcRenderer\.invoke\(/g) || []).length, 2);
  assert.match(pre, /autostartState: \(\) => ipcRenderer\.invoke\("al:autostart-state"\)/);
  assert.match(pre, /setupCalc: \(\) => ipcRenderer\.invoke\("al:setup-calc"\)/);
  // its one handler answers the companion's main frame only
  assert.match(MAIN, /ipcMain\.handle\("al:setup-calc", \(e\) => \{\s*if \(!client \|\| !client\.isCompanion\(e\)\) \{ return null; \}\s*return setupCalc\(\);/);
  assert.ok(!/token|require\("fs"\)|sendSync/.test(pre));
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
  const html = web.source("index.html");
  assert.match(html, /<p id="restart-overlay-row" class="tool-row" hidden><button id="restart-overlay" type="button" aria-describedby="restart-overlay-said">Restart overlay<\/button>\s*<span id="restart-overlay-said" class="muted"><\/span><\/p>/);
  const src = web.source("app.js");
  const start = src.indexOf("  function wireRestartOverlay()");
  const end = src.indexOf("\n  }\n", start) + 4;
  const fnSrc = src.slice(start, end);
  // MERGE-SEAMS F5: render() clears the note on the next state push,
  // before its same-version early return, so any push clears it
  const rStart = src.indexOf("  function render(s) {");
  const rBody = src.slice(rStart, src.indexOf("\n  }\n", rStart));
  const clear = rBody.match(/\n {4}(if \(restartSaid\) \{[^\n]*\})\n/);
  assert.ok(clear, "render() clears the restart note");
  assert.ok(rBody.indexOf(clear[1]) < rBody.indexOf("s.version === renderedVersion"));
  function run(alClient) {
    const els = fakeDoc(["restart-overlay-row", "restart-overlay", "restart-overlay-said"]);
    const ctx = { window: { alClient: alClient }, els: els, snap: null };
    vm.runInNewContext("function $(id) { return els[id]; }\n" +
      "function setText(n, t) { n.textContent = t; }\nvar restartSaid = false;\n" + fnSrc +
      "\nwireRestartOverlay();\nfunction push() { " + clear[1] + " }", ctx);
    els.push = ctx.push;
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
  inClient.push();
  assert.equal(inClient["restart-overlay-said"].textContent, "");
  // a later push without a new restart writes nothing
  inClient["restart-overlay-said"].textContent = "x";
  inClient.push();
  assert.equal(inClient["restart-overlay-said"].textContent, "x");
});

test("MERGE-SEAMS F7: no file under web/ or app/test/ names the old hints class (it is tool-row)", () => {
  for (const dir of [web.dir, path.join(APP, "test")]) {
    for (const name of fs.readdirSync(dir)) {
      const full = path.join(dir, name);
      if (!fs.statSync(full).isFile()) { continue; }
      assert.ok(!fs.readFileSync(full, "utf8").includes("hint" + "-reset"), name);
    }
  }
  const css = web.source("app.css");
  assert.match(css, /\.tool-row \{ margin: 8px 0 0; \}/);
});

test("the wake switch persists in client-prefs.json, default on", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "al-prefs-"));
  try {
    assert.deepEqual(Link.loadPrefs(dir), { wake: true }); // no file: on
    Link.savePrefs(dir, { wake: false });
    const file = path.join(dir, Link.PREFS_FILE);
    assert.equal(fs.readFileSync(file, "ascii"), '{"wake":false}\n');
    assert.deepEqual(Link.loadPrefs(dir), { wake: false });
    assert.ok(!fs.existsSync(file + ".tmp"));
    Link.savePrefs(dir, { wake: true });
    assert.deepEqual(Link.loadPrefs(dir), { wake: true });
    fs.writeFileSync(file, "{broken", "ascii");
    assert.deepEqual(Link.loadPrefs(dir), { wake: true }); // broken: the default
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
  // the window reads and writes it in the runtime dir, never config/local.json
  assert.equal(Link.PREFS_FILE, "client-prefs.json");
  assert.match(WIN, /Link\.loadPrefs\(opts\.runtimeDir\)/);
  assert.match(WIN, /Link\.savePrefs\(opts\.runtimeDir, prefs\)/);
  assert.match(WIN, /wakeOn: currentPrefs\(\)\.wake/);
  assert.match(WIN, /toggleWake: toggleWake/);
  assert.ok(!/local\.json/.test(WIN));
});
