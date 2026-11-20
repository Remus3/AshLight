"use strict";
/* OVL-EGRESS-LOCK (decision 0061 amendment 2026-11-19, parts seam of
   decision 0053): both Electron sessions cancel every request that is not
   an app page, the loopback core on the configured port or (AL_DEV=1)
   devtools (app/egress.js allow).

   - ready: the default session (the overlay's) and the companion's
     partition (PARTITION of app/client/window.js) get the filter.
   - overlayWindow / clientWindow: the window's own session gets it too,
     because those windows may start loading before ready runs; a session
     is locked once.

   One onBeforeRequest callback per request, no timer, no window. Electron
   is required only inside the hooks (ctx.electron in tests). */

const path = require("path");
const Egress = require("../egress.js");

const APP_ROOT = path.resolve(__dirname, "..");

let locked = new WeakSet();

function say(ctx) {
  return ctx && typeof ctx.log === "function" ? ctx.log : () => {};
}

function electronOf(ctx) {
  return (ctx && ctx.electron) || require("electron");
}

function filterFor(ctx) {
  return Egress.makeFilter({
    port: ctx.port,
    dev: ctx.devTools === true,
    appRoot: ctx.appRoot || APP_ROOT,
    log: say(ctx)
  });
}

/* Put the filter on ses once. */
function lock(ctx, ses) {
  if (!ses || typeof ses !== "object" || locked.has(ses)) { return false; }
  const wr = ses.webRequest;
  if (!wr || typeof wr.onBeforeRequest !== "function") { return false; }
  wr.onBeforeRequest(filterFor(ctx));
  locked.add(ses);
  return true;
}

function ready(ctx) {
  const session = electronOf(ctx).session;
  const { PARTITION } = require("../client/window.js");
  lock(ctx, session.defaultSession);
  lock(ctx, session.fromPartition(PARTITION));
}

function overlayWindow(ctx, win) {
  if (win && win.webContents) { lock(ctx, win.webContents.session); }
}

function clientWindow(ctx, win, ses) {
  lock(ctx, ses || (win && win.webContents && win.webContents.session));
}

/* Tests only: forget which sessions are locked. */
function reset() {
  locked = new WeakSet();
}

module.exports = { ready, overlayWindow, clientWindow, lock, reset, APP_ROOT };
