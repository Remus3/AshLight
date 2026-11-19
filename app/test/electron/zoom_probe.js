"use strict";
/* OVL-CLIENT-ZOOM probe (run by tests/test_client_zoom.py, opt-in):
   electron app/test/electron/zoom_probe.js <runtime dir>

   Opens one HIDDEN window of its own (a local data: page), attaches the
   real zoom part (app/parts/30-zoom.js) exactly as main.js does for the
   client window, sends Ctrl+= / Ctrl+wheel / Ctrl+0 to that window's own
   webContents and prints one line "ZOOMPROBE <json>" with the factors read
   back, then a second window to show the factor survives a restart.
   ToS floor: synthetic events go only to this probe's own hidden window
   through its own webContents, never the OS input queue and never the
   game (F-145). */

const path = require("path");
const { app, BrowserWindow } = require("electron");
const Part = require("../../parts/30-zoom.js");

const dir = process.argv[process.argv.length - 1];
app.setPath("userData", path.join(dir, "probe-profile"));
app.disableHardwareAcceleration();

const PAGE = "data:text/html,<p>zoom probe</p>";
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function makeWin() {
  const win = new BrowserWindow({ show: false, width: 400, height: 300,
    webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false } });
  Part.clientWindow({ runtimeDir: dir, log: () => {} }, win);
  return win;
}

/* The one place this probe sends a synthetic event: to its own hidden
   window's webContents only (never the OS input queue, never the game). */
function toOwnHiddenWindow(win, ev) {
  win.webContents.sendInputEvent(ev);
}

function ctrlKey(win, keyCode) {
  toOwnHiddenWindow(win, { type: "keyDown", keyCode: keyCode, modifiers: ["control"] });
  toOwnHiddenWindow(win, { type: "keyUp", keyCode: keyCode, modifiers: ["control"] });
}

async function main() {
  const out = {};
  const win = makeWin();
  await win.loadURL(PAGE);
  out.start = win.webContents.getZoomFactor();
  ctrlKey(win, "=");
  await wait(150);
  out.afterOneIn = win.webContents.getZoomFactor();
  for (let i = 0; i < 12; i += 1) { ctrlKey(win, "="); }
  await wait(300);
  out.afterManyIn = win.webContents.getZoomFactor();
  ctrlKey(win, "0");
  await wait(150);
  out.afterReset = win.webContents.getZoomFactor();
  toOwnHiddenWindow(win, { type: "mouseWheel", x: 50, y: 50, deltaX: 0, deltaY: 120,
                           wheelTicksY: 1, canScroll: true, modifiers: ["control"] });
  await wait(300);
  out.afterWheel = win.webContents.getZoomFactor();
  ctrlKey(win, "=");
  await wait(150);
  out.beforeRestart = win.webContents.getZoomFactor();
  win.destroy();
  const again = makeWin();
  await again.loadURL(PAGE);
  out.afterRestart = again.webContents.getZoomFactor();
  again.destroy();
  process.stdout.write("ZOOMPROBE " + JSON.stringify(out) + "\n");
}

app.whenReady().then(main).catch((e) => {
  process.stdout.write("ZOOMPROBE " + JSON.stringify({ error: String(e && e.message) }) + "\n");
}).then(() => app.exit(0));
