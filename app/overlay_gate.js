"use strict";
/* Overlay visibility (decision 0041; decision 0029 amendment 2026-11-17).

   The overlay window shows only when ALL of these hold:
   - the page is ready (ready-to-show);
   - the player wants it (the toggle hotkey / tray "Show overlay");
   - the gate is open: setGate(false) while the core reports the 0029 idle
     "game may be closed" state (Client.txt staleness only; no window,
     process or memory check), setGate(true) on the next fresh log line;
   - the gate is known: the first report from the page seeds it (stale at
     start = hidden, no flash), or GRACE_MS passes without one (no core yet:
     the HUD shows its offline word).
   Showing is always showInactive (never takes focus from the game).

   RUN-EXPLAIN-OVERLAY-STATE (F-129): state() names why the overlay is
   shown or hidden, from this gate's own flags only (no screen read, no
   look at any other window): one of STATES, the player's off first (the
   gate never overrides it), then "starting" (page not ready or no first
   report yet), then "hidden_idle" (game may be closed), else "shown".
   HINTS holds one fixed sentence per state; exclusive fullscreen is never
   detected, it is only named in the fixed "shown" hint.

   RUN-OVERLAY-REMEMBER (F-188): the player's show / hide choice outlives a
   client restart. main.js reads CHOICE_FILE (ops/runtime, beside
   displays.json) once at start (readChoice) and hands the value to
   createOverlayGate as opts.userOn; toggleUser reports each change through
   opts.onUserChange, and main.js writes it with writeChoice (tmp file then
   rename, ASCII and LF). Only an explicit {"user_on": false} starts hidden;
   a missing, oversized or unreadable file means shown (the default). The
   caller passes the fs functions in; this module requires nothing. */

const GRACE_MS = 3000;
const CHOICE_FILE = "overlay-choice.json";
const CHOICE_MAX_BYTES = 4096;
const STATES = ["shown", "hidden_user", "hidden_idle", "starting"];
const HINTS = {
  shown: "The overlay is shown. If you can't see it over the game, set the game to " +
    "Windowed Fullscreen. An exclusive fullscreen game covers every other window.",
  hidden_user: "The overlay is hidden because you turned it off. The show / hide key " +
    "or the tray brings it back.",
  hidden_idle: "The overlay is hidden because the game looks closed (no new game log " +
    "line for a while). It comes back on the next one.",
  starting: "The overlay is starting. This takes a few seconds."
};

/* The remembered choice: false only for an explicit {"user_on": false}. */
function readChoice(file, fsi) {
  try {
    const text = fsi.readFileSync(file, "utf8");
    if (typeof text !== "string" || text.length > CHOICE_MAX_BYTES) { return true; }
    const doc = JSON.parse(text);
    return !(doc && typeof doc === "object" && doc.user_on === false);
  } catch (e) {
    return true;
  }
}

/* Write the choice: tmp file then rename, so a reader never sees half a file. */
function writeChoice(file, userOn, fsi, now) {
  const doc = { updated: (now || new Date()).toISOString(), user_on: userOn === true };
  const tmp = file + ".tmp";
  fsi.writeFileSync(tmp, JSON.stringify(doc, null, 1) + "\n", { encoding: "ascii" });
  fsi.renameSync(tmp, file);
  return doc;
}

function createOverlayGate(view, log, opts) {
  const say = log || (() => {});
  const o = opts || {};
  const onUserChange = typeof o.onUserChange === "function" ? o.onUserChange : null;
  let ready = false;
  let known = false;
  let gate = true;
  let user = o.userOn !== false;

  function wanted() { return ready && known && user && gate; }

  function state() {
    if (!user) { return "hidden_user"; }
    if (!ready || !known) { return "starting"; }
    if (!gate) { return "hidden_idle"; }
    return "shown";
  }

  function apply() {
    const want = wanted();
    if (want && !view.isVisible()) { view.showInactive(); }
    if (!want && view.isVisible()) { view.hide(); }
    return want;
  }

  return {
    /* the window is ready to show */
    ready() { ready = true; return apply(); },
    /* the gate hook: false hides (game may be closed), true shows again */
    setGate(visible) {
      const v = visible === true;
      if (known && v === gate) { return wanted(); }
      if (v !== gate) { say("overlay gate " + (v ? "open" : "closed (game may be closed)")); }
      gate = v;
      known = true;
      return apply();
    },
    /* no report from the page in time: show as before (offline HUD) */
    graceOver() { if (!known) { known = true; } return apply(); },
    /* the player's toggle; the change is reported once (RUN-OVERLAY-REMEMBER) */
    toggleUser() {
      user = !user;
      const want = apply();
      if (onUserChange) {
        try { onUserChange(user); } catch (e) { say("overlay choice not kept: " + e.message); }
      }
      return want;
    },
    userWants() { return user; },
    /* a new window (page reload keeps the state; a new window re-seeds) */
    reset() { ready = false; known = false; gate = true; },
    wanted: wanted,
    /* why the overlay is shown or hidden: one of STATES */
    state: state
  };
}

module.exports = { createOverlayGate, readChoice, writeChoice, GRACE_MS, STATES, HINTS,
                   CHOICE_FILE };
