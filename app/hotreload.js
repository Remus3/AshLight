"use strict";
/* HOT-RELOAD (decision 0042): the overlay page reloads itself when one of
   its own files (app/overlay, app/shared) changes, in a source checkout
   only. The main process polls with fs.watchFile (stat only, once a
   second, not persistent); the page itself gets no timer, so the overlay
   FPS budget is untouched. main.js / preload.js changes still need an
   overlay restart (scripts/run.ps1). */

const fs = require("fs");
const path = require("path");

const INTERVAL_MS = 1000;
const DEBOUNCE_MS = 300;
const MAX_FILES = 200;
const EXTS = [".html", ".js", ".css"];
const TRUE = ["1", "true", "on", "yes"];
const FALSE = ["0", "false", "off", "no"];

/* env AL_HOT_RELOAD, then config "hot_reload" (a boolean), then "is this a
   source checkout" (a .git entry at the repo root); as server/al/hotreload.py. */
function devEnabled(repo, env, readConfig, exists) {
  const v = String((env || {}).AL_HOT_RELOAD || "").trim().toLowerCase();
  if (TRUE.includes(v)) { return true; }
  if (FALSE.includes(v)) { return false; }
  let cfg = null;
  try { cfg = readConfig(); } catch (e) { cfg = null; }
  if (cfg && typeof cfg.hot_reload === "boolean") { return cfg.hot_reload; }
  return Boolean(exists(path.join(repo, ".git")));
}

/* The overlay's own page files, at most MAX_FILES. */
function pageFiles(dirs, list) {
  const out = [];
  for (const dir of dirs) {
    let names = [];
    try { names = list(dir); } catch (e) { names = []; }
    for (const n of names.sort()) {
      if (EXTS.includes(path.extname(n).toLowerCase()) && out.length < MAX_FILES) {
        out.push(path.join(dir, n));
      }
    }
  }
  return out;
}

/* Watch `files`; call onChange once per burst of saves (debounced).
   Returns stop(). deps: {watchFile, unwatchFile, setTimeout, clearTimeout}. */
function watch(files, onChange, deps) {
  const d = deps || {};
  const watchFile = d.watchFile || fs.watchFile;
  const unwatchFile = d.unwatchFile || fs.unwatchFile;
  const setT = d.setTimeout || setTimeout;
  const clearT = d.clearTimeout || clearTimeout;
  let timer = null;
  const listener = (cur, prev) => {
    if (cur && prev && cur.mtimeMs === prev.mtimeMs && cur.size === prev.size) { return; }
    if (timer) { clearT(timer); }
    timer = setT(() => { timer = null; onChange(); }, DEBOUNCE_MS);
  };
  for (const f of files) {
    watchFile(f, { interval: INTERVAL_MS, persistent: false }, listener);
  }
  return function stop() {
    if (timer) { clearT(timer); timer = null; }
    for (const f of files) { unwatchFile(f, listener); }
  };
}

module.exports = { devEnabled, pageFiles, watch, INTERVAL_MS, DEBOUNCE_MS, MAX_FILES };
