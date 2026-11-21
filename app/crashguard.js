"use strict";
/* OVL-CLIENT-GUARD (finding F-105; decision 0041 point 2: the client, not
   the core, restarts the client): the client survives its own errors
   without a dialog and rebuilds a dead overlay or companion page.

   Pure: the clock, the log and every action are injected, so node --test
   covers the rules without Electron. app/parts/05-crashguard.js wires it.

   Caps (each "N events in a window"):
   - errors: 3 uncaught errors or unhandled rejections in 60 s relaunch
     the client once; a client that was relaunched less than 10 minutes
     ago never relaunches again (no relaunch loop across processes).
   - overlay: a dead, hung or failed overlay page is rebuilt at most 3
     times in 10 minutes; the next failure stops the rebuilds and the
     tray tooltip says so.
   - companion: the same cap for reloads of the companion page.

   The exit record <runtime>/client-exit.json is the one server/al/
   exitrecord.py reads (read_client): {at: epoch seconds, pid, reason:
   quit | relaunch | crash, detail: one ASCII line, no path, at most 160
   characters, or null}. Written atomically (unique temp file, rename),
   never appended to; a write never throws. No timer, window, process or
   dialog here. */

const path = require("path");

const ERROR_LIMIT = 3;
const ERROR_WINDOW_MS = 60 * 1000;
const REBUILD_LIMIT = 3;
const REBUILD_WINDOW_MS = 10 * 60 * 1000;
const RELAUNCH_QUIET_MS = 10 * 60 * 1000;

const FILE_NAME = "client-exit.json";
const REASONS = ["quit", "relaunch", "crash"];
const DETAIL_MAX = 160;
const MAX_BYTES = 4096;

// Windows keeps at most 127 characters of a tray tooltip.
const OVERLAY_STOPPED = "AshLight is running. The overlay stopped after 3 restarts " +
  "in 10 minutes. Right-click and pick Restart overlay.";
const COMPANION_STOPPED = "AshLight is running. Its window stopped reloading after 3 " +
  "tries in 10 minutes. Click to open it.";

/* Timestamps of events inside a sliding window. */
function windowCounter(limit, windowMs, now) {
  let times = [];
  function prune(t) { times = times.filter((x) => t - x < windowMs); }
  return {
    /* Record one event; the count inside the window, this one included. */
    hit() {
      const t = now();
      prune(t);
      times.push(t);
      return times.length;
    },
    /* Record one event only while fewer than limit sit in the window;
       true when it was taken. */
    take() {
      const t = now();
      prune(t);
      if (times.length >= limit) { return false; }
      times.push(t);
      return true;
    },
    count() { prune(now()); return times.length; }
  };
}

const DRIVE_PATH = /[A-Za-z]:[\\/][^\s"']*/g;
const UNC_PATH = /\\\\[^\s"']+/g;
const POSIX_PATH = /(^|[^\w.])\/(?:[^\s/"']+\/)+[^\s"']*/g;

/* text as one short ASCII line with no path, or null when empty (the
   same rule as exitrecord.clean_detail). */
function cleanDetail(text) {
  if (text === null || text === undefined) { return null; }
  let s = String(text);
  s = s.replace(DRIVE_PATH, "<path>").replace(UNC_PATH, "<path>")
    .replace(POSIX_PATH, (m, pre) => pre + "<path>");
  s = s.split(/\s+/).filter(Boolean).join(" ");
  s = s.replace(/[^\x20-\x7e]/g, "?");
  if (s.length > DETAIL_MAX) { s = s.slice(0, DETAIL_MAX - 3).trimEnd() + "..."; }
  return s || null;
}

/* The detail line of a thrown value: its name and first message line. */
function errorDetail(kind, err) {
  let text;
  if (err instanceof Error) {
    const msg = String(err.message || "").split("\n")[0];
    text = (err.name || "Error") + (msg ? ": " + msg : "");
  } else {
    text = String(err);
  }
  return cleanDetail(kind + ": " + text);
}

/* The full text logged for a thrown value (stack when there is one). */
function errorText(err) {
  if (err instanceof Error && err.stack) { return String(err.stack); }
  return String(err);
}

function record(reason, detail, nowMs, pid) {
  if (REASONS.indexOf(reason) < 0) { throw new Error("unknown client exit reason " + reason); }
  return { at: nowMs / 1000, pid: pid, reason: reason, detail: cleanDetail(detail) };
}

/* Write dir/client-exit.json atomically; true when written, never throws. */
function writeRecord(fsi, dir, doc) {
  const file = path.join(dir, FILE_NAME);
  const tmp = file + "." + doc.pid + "." + Math.random().toString(36).slice(2, 10) + ".tmp";
  try {
    const text = JSON.stringify(doc) + "\n";
    if (!/^[\x00-\x7f]*$/.test(text) || text.length > MAX_BYTES) { return false; }
    fsi.mkdirSync(dir, { recursive: true });
    fsi.writeFileSync(tmp, text, { encoding: "ascii" });
    fsi.renameSync(tmp, file);
    return true;
  } catch (e) {
    try { fsi.unlinkSync(tmp); } catch (e2) { /* never made */ }
    return false;
  }
}

/* The last record of dir, or null (missing, too big, malformed). */
function readRecord(fsi, dir) {
  try {
    const file = path.join(dir, FILE_NAME);
    if (fsi.statSync(file).size > MAX_BYTES) { return null; }
    const doc = JSON.parse(fsi.readFileSync(file, "utf8"));
    if (!doc || typeof doc !== "object" || REASONS.indexOf(doc.reason) < 0) { return null; }
    if (typeof doc.at !== "number" || !isFinite(doc.at)) { return null; }
    return doc;
  } catch (e) {
    return null;
  }
}

/* True unless the previous run ended in a relaunch less than
   RELAUNCH_QUIET_MS ago (or the record lies in the future). */
function mayRelaunch(prev, nowMs) {
  if (!prev || prev.reason !== "relaunch") { return true; }
  return nowMs - prev.at * 1000 >= RELAUNCH_QUIET_MS;
}

/* The one detail line of a page failure event, or null when the event is
   not a failure worth a rebuild (a clean exit, an aborted or sub-frame
   load). kind: render-process-gone | unresponsive | did-fail-load. */
function pageFailure(kind, info) {
  const i = info || {};
  if (kind === "render-process-gone") {
    if (i.reason === "clean-exit") { return null; }
    return cleanDetail("renderer gone (" + (i.reason || "unknown") + ")");
  }
  if (kind === "unresponsive") { return "page not responding"; }
  if (kind === "did-fail-load") {
    if (i.isMainFrame === false || i.errorCode === -3) { return null; }
    return cleanDetail("page did not load (" + i.errorCode + ")");
  }
  return null;
}

/* The guard. deps: now (ms), pid, log, prevExit (the record found at
   start), writeExit(reason, detail), relaunch(), restartOverlay(),
   reloadCompanion(), setTooltip(text). Every dep is optional. */
function createGuard(deps) {
  const d = deps || {};
  const now = typeof d.now === "function" ? d.now : () => Date.now();
  const call = (fn, ...a) => { if (typeof fn === "function") { return fn(...a); } return undefined; };
  const say = (m) => { try { call(d.log, m); } catch (e) { /* log gone */ } };
  const errors = windowCounter(ERROR_LIMIT, ERROR_WINDOW_MS, now);
  const overlay = windowCounter(REBUILD_LIMIT, REBUILD_WINDOW_MS, now);
  const companion = windowCounter(REBUILD_LIMIT, REBUILD_WINDOW_MS, now);
  const state = { relaunched: false, relaunchRefused: false, overlayStopped: false,
                  companionStopped: false, quitting: false };

  /* An uncaught error or unhandled rejection: log, record, carry on; the
     third in 60 s relaunches once. Returns "logged" or "relaunch". */
  function onError(kind, err) {
    const detail = errorDetail(kind, err);
    say("client error (" + kind + "): " + errorText(err));
    // once a relaunch is under way its record stays the last word
    if (state.relaunched) { return "logged"; }
    call(d.writeExit, "crash", detail);
    const n = errors.hit();
    if (n < ERROR_LIMIT || state.relaunched || state.quitting) { return "logged"; }
    if (!mayRelaunch(d.prevExit, now())) {
      if (!state.relaunchRefused) {
        state.relaunchRefused = true;
        say("client: " + n + " errors in 60 s; no relaunch, the last one was under 10 minutes ago");
      }
      return "logged";
    }
    state.relaunched = true;
    say("client: " + n + " errors in 60 s; relaunching once");
    call(d.writeExit, "relaunch", detail);
    call(d.relaunch);
    return "relaunch";
  }

  function onPage(which, kind, info) {
    if (state.quitting) { return "ignored"; }
    const detail = pageFailure(kind, info);
    if (!detail) { return "ignored"; }
    const isOverlay = which === "overlay";
    const counter = isOverlay ? overlay : companion;
    const stoppedKey = isOverlay ? "overlayStopped" : "companionStopped";
    const name = isOverlay ? "overlay" : "companion";
    if (state[stoppedKey]) { return "stopped"; }
    if (counter.take()) {
      say(name + " page failed: " + detail + "; " + (isOverlay ? "rebuilding" : "reloading"));
      call(isOverlay ? d.restartOverlay : d.reloadCompanion);
      return isOverlay ? "rebuilt" : "reloaded";
    }
    state[stoppedKey] = true;
    say(name + " page failed: " + detail + "; " + REBUILD_LIMIT +
        " tries in 10 minutes already, stopped");
    call(d.setTooltip, isOverlay ? OVERLAY_STOPPED : COMPANION_STOPPED);
    return "stopped";
  }

  function onQuit() {
    state.quitting = true;
    if (state.relaunched) { return; }
    call(d.writeExit, "quit", null);
  }

  return {
    onError: onError,
    onOverlayFailure: (kind, info) => onPage("overlay", kind, info),
    onCompanionFailure: (kind, info) => onPage("companion", kind, info),
    onQuitting: () => { state.quitting = true; },
    onQuit: onQuit,
    state: () => Object.assign({}, state)
  };
}

module.exports = {
  ERROR_LIMIT, ERROR_WINDOW_MS, REBUILD_LIMIT, REBUILD_WINDOW_MS, RELAUNCH_QUIET_MS,
  FILE_NAME, REASONS, DETAIL_MAX, MAX_BYTES, OVERLAY_STOPPED, COMPANION_STOPPED,
  windowCounter, cleanDetail, errorDetail, errorText, record, writeRecord, readRecord,
  mayRelaunch, pageFailure, createGuard
};
