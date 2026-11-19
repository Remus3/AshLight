"use strict";
/* OVL-CLIENT-ZOOM (decision 0053 parts seam): Ctrl plus / minus / 0 and
   Ctrl+wheel zoom the desktop client window again, and the factor survives
   a window restart (app/client/zoom.js says why the keys were dead).

   clientWindow only: the overlay keeps its fixed layout zoom. The handler
   listens to keys the player presses in AshLight's own window; it sends
   nothing anywhere and registers no global key. */

const Zoom = require("../client/zoom.js");

function clientWindow(ctx, win) {
  if (!win || !win.webContents) { return; }
  const wc = win.webContents;
  const dir = ctx && ctx.runtimeDir;
  const say = ctx && typeof ctx.log === "function" ? ctx.log : () => {};
  let factor = Zoom.load(dir);

  function apply() {
    if (wc.isDestroyed && wc.isDestroyed()) { return; }
    wc.setZoomFactor(factor);
  }

  function set(next) {
    if (next === factor) { apply(); return; }
    factor = next;
    apply();
    try {
      Zoom.save(dir, factor);
    } catch (e) {
      say("client zoom not saved: " + (e && e.message));
    }
  }

  wc.on("before-input-event", (e, input) => {
    const a = Zoom.actionFor(input);
    if (!a) { return; }
    if (e && typeof e.preventDefault === "function") { e.preventDefault(); }
    set(Zoom.step(factor, a));
  });
  // Ctrl+wheel: Electron reports the direction and leaves the zoom to us.
  wc.on("zoom-changed", (e, direction) => {
    set(Zoom.step(factor, direction === "in" ? "in" : "out"));
  });
  // Chromium keys zoom by origin: re-apply after every load (starting page,
  // then the dashboard on 127.0.0.1).
  wc.on("did-finish-load", apply);
  apply();
}

module.exports = { clientWindow };
