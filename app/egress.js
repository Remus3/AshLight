"use strict";
/* OVL-EGRESS-LOCK (decision 0061 amendment 2026-11-19): the egress lock of
   both Electron sessions (the overlay's default session and the
   companion's persist:client partition).

   allow(url, {port, dev, appRoot}) says whether a page may make a request:
   - file: pages and files under appRoot (the app folder) only;
   - the loopback core: http://127.0.0.1:<port>, that one port, no
     user name or password;
   - blob: and data: (in-page, no network);
   - devtools: only when dev (AL_DEV=1).
   Everything else is refused: https, ws, ftp, any other host or port,
   another file folder, chrome: and the like. So "the trade site is never
   called by the app" and "nothing hits the network while web data is off"
   hold for every page, not only by each page's own code.

   Links that leave go through shell.openExternal (app/client/window.js),
   which is not a session request, so this lock does not touch them. The
   main process's own Node http calls to the core are not session requests
   either.

   Pure: no Electron here; makeFilter builds the onBeforeRequest callback,
   one call per request, no timer. */

const path = require("path");
const url = require("url");

const LOOPBACK = "127.0.0.1";
const LOG_CAP = 64; // distinct refused origins logged per start

function parse(u) {
  try {
    return new URL(String(u));
  } catch (e) {
    return null;
  }
}

function norm(p, win) {
  const r = (win ? path.win32 : path).resolve(p);
  return win ? r.toLowerCase() : r;
}

/* Is the file: URL inside root (the folder itself or below it)? */
function underRoot(u, root, win) {
  if (!root || typeof root !== "string") { return false; }
  if (u.host) { return false; } // a UNC share or any host is not the app folder
  let p;
  try {
    p = url.fileURLToPath(u.href, { windows: win });
  } catch (e) {
    try { p = url.fileURLToPath(u.href); } catch (e2) { return false; }
  }
  const sep = win ? "\\" : "/";
  const r = norm(root, win);
  const f = norm(p, win);
  return f === r || f.startsWith(r.endsWith(sep) ? r : r + sep);
}

function allow(u, opts) {
  const o = opts && typeof opts === "object" ? opts : {};
  const p = parse(u);
  if (!p) { return false; }
  switch (p.protocol) {
    case "blob:":
    case "data:":
      return true;
    case "devtools:":
      return o.dev === true;
    case "file:": {
      const win = typeof o.windows === "boolean" ? o.windows : process.platform === "win32";
      return underRoot(p, o.appRoot, win);
    }
    case "http:":
      return p.hostname === LOOPBACK && Number.isInteger(o.port) && o.port > 0 &&
        p.port === String(o.port) && !p.username && !p.password;
    default:
      return false;
  }
}

/* The origin a refusal is logged under: scheme plus host, never a path or
   query (the token rides the core's query string; a path may name a
   folder). */
function originOf(u) {
  const p = parse(u);
  if (!p) { return "(bad url)"; }
  return p.host ? p.protocol + "//" + p.host : p.protocol;
}

/* The onBeforeRequest listener: cancel what allow() refuses, log each
   refused origin once (at most LOG_CAP of them). */
function makeFilter(opts) {
  const o = opts && typeof opts === "object" ? opts : {};
  const log = typeof o.log === "function" ? o.log : () => {};
  const seen = new Set();
  return (details, callback) => {
    const u = details && details.url;
    const ok = allow(u, o);
    if (!ok) {
      const origin = originOf(u);
      if (!seen.has(origin) && seen.size < LOG_CAP) {
        seen.add(origin);
        log("egress: request cancelled to " + origin);
      }
    }
    callback({ cancel: !ok });
  };
}

module.exports = { allow, makeFilter, originOf, LOG_CAP };
