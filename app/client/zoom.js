"use strict";
/* OVL-CLIENT-ZOOM: page zoom in the desktop client window.

   Root cause: the client window has no menu (win.setMenu(null), decision
   0041), so Electron's default View menu, whose zoomIn / zoomOut /
   resetZoom roles carry the Ctrl plus / minus / 0 accelerators, is gone and
   the keys did nothing. app/parts/30-zoom.js restores them with a
   before-input-event handler on the client window's own webContents (only
   keys the player presses in AshLight's own focused window; nothing is sent
   anywhere) and Ctrl+wheel through its zoom-changed event, and keeps the
   factor in ops/runtime/client_zoom.json so it survives a window restart.
   The overlay keeps its fixed layout zoom (app/shared/layout.js).

   Pure: no Electron; fs is passed in or Node's own. */

const fs = require("fs");
const path = require("path");

const FILE_NAME = "client_zoom.json";
// Chromium's own zoom steps, capped at 200 percent (WCAG 1.4.4).
const LEVELS = [0.5, 0.67, 0.75, 0.8, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2];
const MIN = LEVELS[0];
const MAX = LEVELS[LEVELS.length - 1];

/* "in", "out", "reset" or null for one before-input-event input. */
function actionFor(input) {
  if (!input || input.type !== "keyDown") { return null; }
  if (!(input.control || input.meta) || input.alt) { return null; }
  const k = input.key;
  const c = input.code;
  if (k === "=" || k === "+" || c === "NumpadAdd") { return "in"; }
  if (k === "-" || k === "_" || c === "NumpadSubtract") { return "out"; }
  if (k === "0" || c === "Numpad0") { return "reset"; }
  return null;
}

function valid(f) {
  return typeof f === "number" && isFinite(f) && f >= MIN && f <= MAX;
}

/* The next level from factor f for action a (in / out / reset). */
function step(f, a) {
  if (a === "reset") { return 1; }
  const cur = valid(f) ? f : 1;
  const eps = 1e-6;
  if (a === "in") {
    for (const l of LEVELS) { if (l > cur + eps) { return l; } }
    return MAX;
  }
  if (a === "out") {
    for (let i = LEVELS.length - 1; i >= 0; i -= 1) {
      if (LEVELS[i] < cur - eps) { return LEVELS[i]; }
    }
    return MIN;
  }
  return cur;
}

/* The saved factor in dir, else 1. */
function load(dir, fsi) {
  if (!dir) { return 1; }
  try {
    const doc = JSON.parse((fsi || fs).readFileSync(path.join(dir, FILE_NAME), "utf8"));
    return valid(doc && doc.zoom) ? doc.zoom : 1;
  } catch (e) {
    return 1;
  }
}

/* Write factor f to dir: tmp then rename, ASCII and LF. */
function save(dir, f, fsi) {
  if (!dir || !valid(f)) { return; }
  const x = fsi || fs;
  const file = path.join(dir, FILE_NAME);
  const tmp = file + ".tmp";
  x.writeFileSync(tmp, JSON.stringify({ zoom: f }) + "\n", { encoding: "ascii" });
  x.renameSync(tmp, file);
}

module.exports = { FILE_NAME, LEVELS, MIN, MAX, actionFor, step, load, save };
