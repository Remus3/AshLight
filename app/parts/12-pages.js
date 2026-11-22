"use strict";
/* OVL-APP-SCHEME (decision 0061 amendment 2026-11-21, parts seam of
   decision 0053): the app scheme the overlay page and the starting page
   load from (app/pages.js holds the rules).

   - early: the one scheme is registered privileged (standard and secure,
     so a page on it has a real origin and is a secure context); Electron
     takes this only before app ready.
   - ready: the default session (the overlay's) and the companion's
     partition (PARTITION of app/client/window.js) serve the scheme.
   - overlayWindow / clientWindow: the window's own session serves it too,
     because the companion may start loading before ready runs; a session
     is served once.

   Each request reads one listed file under the app folder; no timer, no
   window, no network. Electron is required only inside the hooks
   (ctx.electron in tests). */

const fs = require("fs");
const path = require("path");
const Pages = require("../pages.js");

const APP_ROOT = path.resolve(__dirname, "..");

let served = new WeakSet();

function say(ctx) {
  return ctx && typeof ctx.log === "function" ? ctx.log : () => {};
}

function electronOf(ctx) {
  return (ctx && ctx.electron) || require("electron");
}

/* Read one listed file (Pages.resolve already matched it exactly). */
function reader(root) {
  return (file) => fs.readFileSync(path.join(root, ...file.split("/")));
}

/* The protocol.handle callback: a Request in, a Response out. A refused
   request is logged once per session (never its path). */
function handlerFor(ctx) {
  const read = reader(ctx.appRoot || APP_ROOT);
  const R = (ctx && ctx.Response) || Response;
  let logged = false;
  return (request) => {
    const r = Pages.respond(request && request.url, {
      port: ctx.port, method: request && request.method, read: read
    });
    if (r.status !== 200 && !logged) {
      logged = true;
      say(ctx)("pages: an app page request was refused (404)");
    }
    return new R(r.body, { status: r.status, headers: r.headers });
  };
}

/* Serve the scheme on ses once. */
function serve(ctx, ses) {
  if (!ses || typeof ses !== "object" || served.has(ses)) { return false; }
  const proto = ses.protocol;
  if (!proto || typeof proto.handle !== "function") { return false; }
  proto.handle(Pages.SCHEME, handlerFor(ctx));
  served.add(ses);
  return true;
}

function early(ctx) {
  const protocol = electronOf(ctx).protocol;
  if (protocol && typeof protocol.registerSchemesAsPrivileged === "function") {
    protocol.registerSchemesAsPrivileged([
      { scheme: Pages.SCHEME, privileges: { standard: true, secure: true } }
    ]);
  }
}

function ready(ctx) {
  const session = electronOf(ctx).session;
  const { PARTITION } = require("../client/window.js");
  serve(ctx, session.defaultSession);
  serve(ctx, session.fromPartition(PARTITION));
}

function overlayWindow(ctx, win) {
  if (win && win.webContents) { serve(ctx, win.webContents.session); }
}

function clientWindow(ctx, win, ses) {
  serve(ctx, ses || (win && win.webContents && win.webContents.session));
}

/* Tests only: forget which sessions are served. */
function reset() {
  served = new WeakSet();
}

module.exports = { early, ready, overlayWindow, clientWindow, serve, handlerFor, reset, APP_ROOT };
