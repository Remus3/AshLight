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
   Showing is always showInactive (never takes focus from the game). */

const GRACE_MS = 3000;

function createOverlayGate(view, log) {
  const say = log || (() => {});
  let ready = false;
  let known = false;
  let gate = true;
  let user = true;

  function wanted() { return ready && known && user && gate; }

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
    /* the player's toggle */
    toggleUser() { user = !user; return apply(); },
    userWants() { return user; },
    /* a new window (page reload keeps the state; a new window re-seeds) */
    reset() { ready = false; known = false; gate = true; },
    wanted: wanted
  };
}

module.exports = { createOverlayGate, GRACE_MS };
