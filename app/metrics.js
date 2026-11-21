"use strict";
/* RUN-BUDGET-LOG-CLIENT (F-032, OVL-BUDGET): the client's own footprint.

   Once a minute the Electron MAIN process sums app.getAppMetrics() per
   own process type and writes ops/runtime/overlay-state.json for the
   core's budget log (research 0048 budgets B10 to B12, B18). Floor:
   getAppMetrics() lists only Electron's own process tree (AshLight's
   browser, renderer, GPU and utility processes); the game process is
   never listed or opened (decisions 0029, 0006 method 3). Only numbers
   and two booleans leave a row: no pid, no path, no process or service
   name. The overlay page gets no timer (overlay FPS rule); the one timer
   lives here, in the main process.

   overlay-state.json is the one client -> core state file; a later
   package adds its field in snapshot() below (and to MAX_BYTES if it
   must). Shape (schema 1):
     { "schema": 1, "updated": "<UTC ISO>", "period_s": 60,
       "processes": n, "working_set_kb": n, "private_kb": n, "cpu_pct": n,
       "by_type": { "<browser|tab|gpu|utility|other>":
                    { "count", "working_set_kb", "private_kb", "cpu_pct" } },
       "overlay_shown": bool, "companion_open": bool,
       "overlay_state": "<shown|hidden_user|hidden_idle|starting>" }
   Memory is in KB as Electron reports it; cpu_pct is percent of one core
   since the previous sample (Electron's percentCPUUsage).
   RUN-EXPLAIN-OVERLAY-STATE (F-129): overlay_state is why the overlay is
   shown or hidden, read from AshLight's own overlay gate
   (app/overlay_gate.js state(); opts.overlayState), never from a screen
   read or a look at any other window. noteState() writes the file at once
   when that state changed since the last write (main.js calls it after a
   toggle, a gate report and the window's first show); otherwise the field
   rides the once-a-minute sample. */

const fs = require("fs");
const path = require("path");
const Gate = require("./overlay_gate.js");

const FILE_NAME = "overlay-state.json";
const PERIOD_MS = 60 * 1000;
const MAX_BYTES = 2048;
const SCHEMA = 1;
// Electron's process type names -> the few keys a row may carry; any other
// type (Zygote, Sandbox helper, Pepper Plugin, Unknown) is "other".
const TYPE_KEYS = { Browser: "browser", Tab: "tab", GPU: "gpu", Utility: "utility" };

function num(v) {
  return (typeof v === "number" && isFinite(v) && v > 0) ? v : 0;
}

function round(v, places) {
  const f = Math.pow(10, places);
  return Math.round(v * f) / f;
}

function typeKey(t) {
  return Object.prototype.hasOwnProperty.call(TYPE_KEYS, t) ? TYPE_KEYS[t] : "other";
}

/* Sum the metric rows per type key. Only the numbers named here are read;
   pid, name, serviceName and every other field of a row are never copied. */
function summarize(rows) {
  const byType = {};
  const total = { processes: 0, working_set_kb: 0, private_kb: 0, cpu_pct: 0 };
  for (const r of Array.isArray(rows) ? rows : []) {
    if (!r || typeof r !== "object") { continue; }
    const mem = r.memory || {};
    const cpu = r.cpu || {};
    const k = typeKey(r.type);
    const t = byType[k] || (byType[k] = { count: 0, working_set_kb: 0, private_kb: 0, cpu_pct: 0 });
    const ws = num(mem.workingSetSize);
    const pb = num(mem.privateBytes);
    const pc = num(cpu.percentCPUUsage);
    t.count += 1; t.working_set_kb += ws; t.private_kb += pb; t.cpu_pct += pc;
    total.processes += 1; total.working_set_kb += ws; total.private_kb += pb; total.cpu_pct += pc;
  }
  for (const k of Object.keys(byType)) {
    const t = byType[k];
    t.working_set_kb = Math.round(t.working_set_kb);
    t.private_kb = Math.round(t.private_kb);
    t.cpu_pct = round(t.cpu_pct, 3);
  }
  total.working_set_kb = Math.round(total.working_set_kb);
  total.private_kb = Math.round(total.private_kb);
  total.cpu_pct = round(total.cpu_pct, 3);
  return { total: total, byType: byType };
}

/* A window object is up (exists, not destroyed) / shown on screen. Read
   from AshLight's own window objects only, never from a screen read. */
function windowUp(w) {
  return !!(w && typeof w.isDestroyed === "function" && !w.isDestroyed());
}

function windowShown(w) {
  return windowUp(w) && typeof w.isVisible === "function" && w.isVisible() === true;
}

/* One of the gate's STATES; anything else reads "starting". */
function stateWord(s) {
  return Gate.STATES.indexOf(s) >= 0 ? s : "starting";
}

/* The overlay-state.json document. */
function snapshot(rows, view, now) {
  const s = summarize(rows);
  const v = view || {};
  return {
    schema: SCHEMA,
    updated: (now || new Date()).toISOString(),
    period_s: PERIOD_MS / 1000,
    processes: s.total.processes,
    working_set_kb: s.total.working_set_kb,
    private_kb: s.total.private_kb,
    cpu_pct: s.total.cpu_pct,
    by_type: s.byType,
    overlay_shown: v.overlay_shown === true,
    companion_open: v.companion_open === true,
    overlay_state: stateWord(v.overlay_state)
  };
}

/* Write doc to dir/overlay-state.json: tmp then rename (a reader never sees
   half a file), ASCII and LF only, at most MAX_BYTES or nothing is written. */
function writeState(dir, doc, fsi) {
  const f = fsi || fs;
  const text = JSON.stringify(doc, null, 1)
    .replace(/[^\x00-\x7f]/g, (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0")) + "\n";
  if (text.length > MAX_BYTES) {
    throw new Error("overlay state over " + MAX_BYTES + " bytes (" + text.length + ")");
  }
  const file = path.join(dir, FILE_NAME);
  const tmp = file + ".tmp";
  f.mkdirSync(dir, { recursive: true });
  f.writeFileSync(tmp, text, { encoding: "ascii" });
  f.renameSync(tmp, file);
  return file;
}

/* The sampler. opts: getMetrics (app.getAppMetrics), overlay / companion
   (getters of AshLight's own two windows), overlayState (the gate's
   state(), a getter), dir (the runtime dir), log;
   injectable for tests: fs, setInterval, clearInterval, now, processType
   (default process.type: "browser" in Electron's main process). */
function createSampler(opts) {
  const o = opts || {};
  const say = typeof o.log === "function" ? o.log : () => {};
  const setI = o.setInterval || setInterval;
  const clearI = o.clearInterval || clearInterval;
  const now = o.now || (() => new Date());
  const getWin = (g) => (typeof g === "function" ? g() : null);
  let timer = null;
  let failing = false;
  let lastState = null; // the overlay_state of the last file written

  function currentState() {
    try {
      return stateWord(typeof o.overlayState === "function" ? o.overlayState() : null);
    } catch (e) {
      return "starting";
    }
  }

  function view() {
    return { overlay_shown: windowShown(getWin(o.overlay)),
             companion_open: windowUp(getWin(o.companion)),
             overlay_state: currentState() };
  }

  /* One sample: read, sum, write. A failure is logged once until a write
     succeeds again; it never throws into the timer. */
  function sample() {
    try {
      const doc = snapshot(o.getMetrics(), view(), now());
      writeState(o.dir, doc, o.fs);
      if (failing) { say("metrics: overlay state written again"); }
      failing = false;
      lastState = doc.overlay_state;
      return doc;
    } catch (e) {
      if (!failing) { say("metrics: overlay state not written: " + e.message); }
      failing = true;
      return null;
    }
  }

  /* Start the one timer (main process only). A second start is a no-op.
     The first getAppMetrics() call only primes Electron's CPU counters
     (it reports 0), so the first file is written one period later. */
  function start() {
    const ptype = Object.prototype.hasOwnProperty.call(o, "processType") ? o.processType : process.type;
    if (ptype !== "browser") { say("metrics: not the main process; no sampler"); return false; }
    if (timer !== null || !o.dir || typeof o.getMetrics !== "function") { return false; }
    try { o.getMetrics(); } catch (e) { /* the first real sample logs it */ }
    timer = setI(sample, PERIOD_MS);
    if (timer && typeof timer.unref === "function") { timer.unref(); }
    return true;
  }

  function stop() {
    if (timer !== null) { clearI(timer); timer = null; }
  }

  /* The overlay's state may have changed: write the file now when it did
     (a running sampler only); true when a write was asked. The gate's
     state is read first; nothing else is looked at when it is unchanged. */
  function noteState() {
    if (timer === null) { return false; }
    const s = currentState();
    if (s === lastState) { return false; }
    say("overlay state " + s + ": " + Gate.HINTS[s]);
    sample();
    return true;
  }

  return { start: start, stop: stop, sample: sample, noteState: noteState,
           running: () => timer !== null };
}

/* main.js's one call: build the sampler and start it. */
function startSampler(opts) {
  const s = createSampler(opts);
  s.start();
  return s;
}

module.exports = { FILE_NAME, PERIOD_MS, MAX_BYTES, SCHEMA, TYPE_KEYS, summarize, snapshot,
                   stateWord, writeState, windowUp, windowShown, createSampler, startSampler };
