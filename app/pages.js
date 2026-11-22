"use strict";
/* OVL-APP-SCHEME (decision 0061 amendment 2026-11-21, plan unit F-174): the
   app's two local pages, the overlay and the companion's starting page,
   come from one privileged app scheme instead of file://, so each has a
   real origin (al-app://app) and a header CSP that names the exact core
   port.

   - FILES: the fixed list of files the scheme serves (the two pages and
     the scripts and styles they load); nothing else under the app folder
     is reachable.
   - resolve(url): the listed file a request names, or null. The path is
     looked up exactly (no decoding, no file system call sees request
     text), so "..", an encoded slash or a backslash never reaches a file
     outside the list.
   - cspFor(port, file): the page CSP. The overlay's connect-src is
     http://127.0.0.1:<port> exactly (its one request is the core's SSE
     feed); the starting page connects nowhere.
   - respond(url, opts): {status, headers, body} for one request; a file
     not in the list, another host, a port or a user name is 404.
   - urlFor(file, {query, hash}): the scheme URL of a listed file.

   Pure: no Electron here; app/parts/12-pages.js registers the scheme and
   serves it through protocol.handle on both sessions. */

const SCHEME = "al-app";
const HOST = "app";
const ORIGIN = SCHEME + "://" + HOST;
const LOOPBACK = "127.0.0.1";

const FILES = Object.freeze([
  "overlay/index.html",
  "overlay/overlay.css",
  "overlay/overlay.js",
  "shared/format.js",
  "shared/render_gate.js",
  "client/starting.html",
  "client/starting.css",
  "client/starting.js"
]);

const TYPES = Object.freeze({
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8"
});

const OVERLAY_PAGE = "overlay/index.html";
const STARTING_PAGE = "client/starting.html";

function parse(u) {
  try {
    return new URL(String(u));
  } catch (e) {
    return null;
  }
}

/* The listed file the URL names, or null. Query and fragment are ignored
   (the starting page reads its own). */
function resolve(u) {
  const p = parse(u);
  if (!p || p.protocol !== SCHEME + ":" || p.hostname !== HOST) { return null; }
  if (p.port || p.username || p.password) { return null; }
  const rel = p.pathname.startsWith("/") ? p.pathname.slice(1) : "";
  return FILES.includes(rel) ? rel : null;
}

function validPort(port) {
  return Number.isInteger(port) && port > 0 && port < 65536;
}

/* The CSP of a served file: the overlay may connect to the core on its
   one port, the starting page to nothing. No port, no connection. */
function cspFor(port, file) {
  const core = !String(file || "").startsWith("client/") && validPort(port);
  const connect = core ? "http://" + LOOPBACK + ":" + port : "'none'";
  return "default-src 'none'; script-src 'self'; style-src 'self'; connect-src " + connect +
    "; img-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'";
}

function typeOf(file) {
  const dot = file.lastIndexOf(".");
  return (dot >= 0 && TYPES[file.slice(dot)]) || "application/octet-stream";
}

const NOT_FOUND = Object.freeze({ status: 404, headers: { "Content-Type": "text/plain; charset=utf-8",
  "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store" }, body: "not found\n" });

/* One request: opts {port, method, read(file) -> bytes}. A listed file is
   read fresh on every request (no cache), so a hot reload of the page
   shows the edit. A read failure is 404 too. */
function respond(u, opts) {
  const o = opts && typeof opts === "object" ? opts : {};
  const method = String(o.method || "GET").toUpperCase();
  const file = resolve(u);
  if (!file || (method !== "GET" && method !== "HEAD") || typeof o.read !== "function") {
    return { status: NOT_FOUND.status, headers: Object.assign({}, NOT_FOUND.headers), body: NOT_FOUND.body };
  }
  let body;
  try {
    body = o.read(file);
  } catch (e) {
    return { status: NOT_FOUND.status, headers: Object.assign({}, NOT_FOUND.headers), body: NOT_FOUND.body };
  }
  return {
    status: 200,
    headers: {
      "Content-Type": typeOf(file),
      "Content-Security-Policy": cspFor(o.port, file),
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
      "Cache-Control": "no-store"
    },
    body: method === "HEAD" ? "" : body
  };
}

/* The scheme URL of a listed file, with an optional query object and
   fragment (as loadFile's options were). Throws for a file not listed. */
function urlFor(file, opts) {
  if (!FILES.includes(file)) { throw new Error("not an app page file: " + file); }
  const o = opts && typeof opts === "object" ? opts : {};
  let out = ORIGIN + "/" + file;
  if (o.query && typeof o.query === "object") {
    const q = new URLSearchParams();
    for (const k of Object.keys(o.query)) { q.append(k, String(o.query[k])); }
    const s = q.toString();
    if (s) { out += "?" + s; }
  }
  if (typeof o.hash === "string" && o.hash) { out += "#" + o.hash.replace(/^#/, ""); }
  return out;
}

/* One spelling of an app scheme URL for comparison: origin and path, no
   query or fragment; "" for anything else (another scheme or host, a
   port, a user name). */
function pageKey(u) {
  const p = parse(u);
  if (!p || p.protocol !== SCHEME + ":" || p.hostname !== HOST) { return ""; }
  if (p.port || p.username || p.password) { return ""; }
  return ORIGIN + p.pathname;
}

module.exports = { SCHEME, HOST, ORIGIN, FILES, OVERLAY_PAGE, STARTING_PAGE, resolve, cspFor,
                   respond, urlFor, pageKey };
