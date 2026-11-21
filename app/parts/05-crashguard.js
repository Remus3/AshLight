"use strict";
/* OVL-CLIENT-GUARD (finding F-105; decision 0053 parts seam; decision 0041
   point 2: the client, not the core, restarts the client). The rules and
   caps live in app/crashguard.js; this part wires them to the client.

   - early: handlers for uncaught errors and unhandled rejections in the
     main process. A registered handler is what keeps Electron's error
     dialog away, so no box can take focus from the game: the stack goes
     to the log, a crash record is written and the client carries on. The
     third error in 60 s writes a relaunch record, then app.relaunch() and
     app.exit(0), once (never again within 10 minutes of the last one).
   - overlayWindow: render-process-gone, unresponsive and did-fail-load on
     the overlay page rebuild it through ctx.actions.restartOverlay(), at
     most 3 times in 10 minutes; then the tray tooltip says it stopped.
   - clientWindow: the same three events reload the companion page, with
     the same cap.
   - quit: a quit record (client-exit.json in the runtime dir) for the
     Checks row of OBS-CRASH.

   Handlers run only on failure events; no timer, window, process or
   dialog. ctx.app is Electron's app (or a test fake); ctx.process and
   ctx.fs and ctx.now are test seams. */

const fs = require("fs");
const Guard = require("../crashguard.js");

let guard = null;
let companion = null; // the companion window last registered

function proc(ctx) { return (ctx && ctx.process) || process; }
function fsi(ctx) { return (ctx && ctx.fs) || fs; }
function clock(ctx) { return ctx && typeof ctx.now === "function" ? ctx.now : () => Date.now(); }

function makeGuard(ctx) {
  const now = clock(ctx);
  const pid = proc(ctx).pid || 0;
  const dir = ctx.runtimeDir;
  const writeExit = (reason, detail) => {
    if (!dir) { return false; }
    return Guard.writeRecord(fsi(ctx), dir, Guard.record(reason, detail, now(), pid));
  };
  return Guard.createGuard({
    now: now,
    log: ctx.log,
    prevExit: dir ? Guard.readRecord(fsi(ctx), dir) : null,
    writeExit: writeExit,
    relaunch: () => {
      const app = ctx.app;
      if (app && typeof app.relaunch === "function") { app.relaunch(); }
      if (app && typeof app.exit === "function") { app.exit(0); }
    },
    restartOverlay: () => {
      const a = ctx.actions;
      if (a && typeof a.restartOverlay === "function") { a.restartOverlay(); }
    },
    reloadCompanion: () => {
      const w = companion;
      if (w && !(typeof w.isDestroyed === "function" && w.isDestroyed()) && w.webContents) {
        w.webContents.reload();
      }
    },
    setTooltip: (text) => {
      const client = typeof ctx.getClient === "function" ? ctx.getClient() : null;
      const tray = client && typeof client.tray === "function" ? client.tray() : null;
      if (tray && typeof tray.setToolTip === "function") { tray.setToolTip(text); }
    }
  });
}

function ensure(ctx) {
  if (!guard) { guard = makeGuard(ctx); }
  return guard;
}

/* Never let the handler itself throw: that would be an error in the
   error path. */
function safely(fn) {
  return (...args) => {
    try { fn(...args); } catch (e) { /* the log is gone too; carry on */ }
  };
}

function early(ctx) {
  guard = makeGuard(ctx);
  const g = guard;
  const p = proc(ctx);
  p.on("uncaughtException", safely((err) => g.onError("uncaught exception", err)));
  p.on("unhandledRejection", safely((reason) => g.onError("unhandled rejection", reason)));
  const app = ctx.app;
  if (app && typeof app.on === "function") {
    app.on("before-quit", safely(() => g.onQuitting()));
  }
}

/* The three failure events of one page, each handed to onFail(kind,
   info) while live() still holds. */
function watchPage(wc, live, onFail) {
  if (!wc || typeof wc.on !== "function") { return; }
  wc.on("render-process-gone", safely((e, details) => {
    if (live()) { onFail("render-process-gone", details || {}); }
  }));
  wc.on("unresponsive", safely(() => {
    if (live()) { onFail("unresponsive", {}); }
  }));
  wc.on("did-fail-load", safely((e, errorCode, errorDescription, validatedURL, isMainFrame) => {
    if (live()) { onFail("did-fail-load", { errorCode: errorCode, isMainFrame: isMainFrame }); }
  }));
}

function overlayWindow(ctx, win) {
  const g = ensure(ctx);
  // only the current overlay counts: a window restartOverlay() already
  // replaced (and destroyed) is not rebuilt a second time
  const live = () => typeof ctx.getOverlay !== "function" || ctx.getOverlay() === win;
  watchPage(win && win.webContents, live, (kind, info) => g.onOverlayFailure(kind, info));
}

function clientWindow(ctx, win) {
  const g = ensure(ctx);
  companion = win;
  const live = () => companion === win &&
    !(win && typeof win.isDestroyed === "function" && win.isDestroyed());
  watchPage(win && win.webContents, live, (kind, info) => g.onCompanionFailure(kind, info));
}

function quit(ctx) {
  ensure(ctx).onQuit();
}

module.exports = { early, overlayWindow, clientWindow, quit, guard: () => guard };
