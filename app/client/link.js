"use strict";
/* DESKTOP-CLIENT (decision 0041): the pure rules of the companion window.
   No Electron here, so node --test covers every branch.

   - the dashboard URL carries the per-start token in the FRAGMENT: a
     fragment is never sent over the network, the window has no URL bar,
     and web/app.js moves it to sessionStorage and strips it at once;
   - the window may only show the local core (http://127.0.0.1:<port>);
     anything else is refused. A link leaves for the user's default
     browser only while the companion has focus, https only, to a host of
     config/link_hosts.json (or its subdomain), at most 1 a second and 5 a
     minute (OVL-LINKS-DOWNLOADS, decision 0041 amendment 2026-11-19);
   - a download is saved only from the core origin with a .build, .filter,
     .json or .txt name;
   - the saved size and position are used only when they still land on a
     connected display; with none, a display that is not the overlay's
     gets the window (OVL-SECOND-DISPLAY). */

const fs = require("fs");
const path = require("path");

const HEX_TOKEN = /^[0-9a-fA-F]{16,256}$/;
const DEFAULT_SIZE = { width: 1280, height: 860 };
const MIN_SIZE = { width: 560, height: 420 };
const CLIENT_FLAG = "--client";
const HOSTS_FILE = path.join(__dirname, "..", "..", "config", "link_hosts.json");
const RATE = { gapMs: 1000, windowMs: 60000, perWindow: 5 };
const DOWNLOAD_EXT = [".build", ".filter", ".json", ".txt"];

/* The host list from config/link_hosts.json ({"hosts": [...]}): lower-case
   names only. A missing or broken file gives [], so every link is refused
   (fail closed). */
function readHosts(file) {
  try {
    const doc = JSON.parse(fs.readFileSync(file || HOSTS_FILE, "utf8"));
    const list = doc && Array.isArray(doc.hosts) ? doc.hosts : [];
    return list.filter((h) => typeof h === "string" && /^[a-z0-9.-]+$/.test(h));
  } catch (e) {
    return [];
  }
}
const LINK_HOSTS = Object.freeze(readHosts());

function coreOrigin(port) {
  return "http://127.0.0.1:" + Number(port);
}

/* The dashboard address for the window, or "" without a usable token. */
function dashboardUrl(port, token) {
  if (!Number.isInteger(port) || port <= 0 || port > 65535) { return ""; }
  if (typeof token !== "string" || !HEX_TOKEN.test(token)) { return ""; }
  return coreOrigin(port) + "/#token=" + token;
}

function parse(url) {
  try { return new URL(String(url)); } catch (e) { return null; }
}

/* May the companion window itself show this URL? Only the local core. */
function isCoreUrl(url, port) {
  const u = parse(url);
  return !!u && u.protocol === "http:" && u.origin === coreOrigin(port) && !u.username &&
    !u.password;
}

function hostListed(host, hosts) {
  const h = String(host || "").toLowerCase();
  const list = Array.isArray(hosts) ? hosts : LINK_HOSTS;
  return !!h && list.some((l) => h === l || h.endsWith("." + l));
}

/* May this URL go to the user's default browser? https only, a listed host
   (or its subdomain), the default port, no user info: never a local file,
   script, custom scheme or plain http. */
function isExternalUrl(url, hosts) {
  const u = parse(url);
  return !!u && u.protocol === "https:" && !u.port && !u.username && !u.password &&
    hostListed(u.hostname, hosts);
}

/* The href handed to the browser: the parsed, normalised form ("" = none). */
function externalHref(url) {
  const u = parse(url);
  return u ? u.href : "";
}

/* The rate limiter, pure: may one more link open at `now`, given the times
   (ms) of the links opened before? At most 1 a second and 5 a minute. */
function rateAllows(history, now) {
  const t = Number(now);
  if (!Number.isFinite(t)) { return false; }
  const past = Array.isArray(history) ? history.filter((x) => Number.isFinite(x)) : [];
  if (past.some((x) => x > t - RATE.gapMs)) { return false; }
  return past.filter((x) => x > t - RATE.windowMs).length < RATE.perWindow;
}

/* The history after a link opened at `now`: the last minute only. */
function noteOpened(history, now) {
  const past = Array.isArray(history) ? history : [];
  return past.filter((x) => Number.isFinite(x) && x > now - RATE.windowMs).concat([now]);
}

/* What the window does with a navigation or popup request:
   "stay" (the core itself, navigations only), "external" (hand to the
   default browser) or "deny". A popup never opens a second window. A link
   leaves only when ctx ({focused, now, history}) says the companion has
   focus and the rate allows it; no ctx means no link (fail closed). */
function routeFor(url, port, isPopup, ctx) {
  if (isCoreUrl(url, port)) { return isPopup ? "deny" : "stay"; }
  const c = ctx && typeof ctx === "object" ? ctx : {};
  if (!isExternalUrl(url, c.hosts)) { return "deny"; }
  if (c.focused !== true) { return "deny"; }
  return rateAllows(c.history, c.now) ? "external" : "deny";
}

/* Is --client among these command-line args? */
function wantsClient(argv) {
  return Array.isArray(argv) && argv.some((a) => String(a).toLowerCase() === CLIENT_FLAG);
}

function intersects(a, b) {
  return a.x < b.x + b.width && b.x < a.x + a.width &&
    a.y < b.y + b.height && b.y < a.y + a.height;
}

function sameRect(a, b) {
  return !!a && !!b && a.x === b.x && a.y === b.y && a.width === b.width && a.height === b.height;
}

/* Window bounds from the saved state and the displays' work areas
   ([{x,y,width,height}], primary first). A saved rect that no display shows
   at least 80x80 of falls back to the default size, centred on the primary;
   with two or more areas and `avoid` (the work area of the overlay's
   display), centred on the largest area that is not `avoid`
   (OVL-SECOND-DISPLAY). */
function windowBounds(saved, workAreas, avoid) {
  const areas = [];
  for (const a of Array.isArray(workAreas) ? workAreas : []) {
    if (a && a.width > 0 && a.height > 0 && !areas.some((b) => sameRect(a, b))) { areas.push(a); }
  }
  let primary = areas[0] || { x: 0, y: 0, width: 1920, height: 1080 };
  const s = saved && typeof saved === "object" ? saved : {};
  const w = Math.round(Number(s.width));
  const h = Math.round(Number(s.height));
  const x = Math.round(Number(s.x));
  const y = Math.round(Number(s.y));
  if ([w, h, x, y].every(Number.isFinite) && w >= MIN_SIZE.width && h >= MIN_SIZE.height &&
      w <= 16384 && h <= 16384) {
    const rect = { x: x, y: y, width: w, height: h };
    const seen = areas.some((a) => {
      const core = { x: rect.x + 40, y: rect.y, width: Math.max(1, rect.width - 80), height: 80 };
      return intersects(core, a);
    });
    if (seen) { return { bounds: rect, maximized: s.maximized === true }; }
  }
  if (areas.length > 1 && areas.some((a) => sameRect(a, avoid))) {
    primary = areas.filter((a) => !sameRect(a, avoid)).reduce((best, a) =>
      (a.width * a.height > best.width * best.height ? a : best));
  }
  const width = Math.min(DEFAULT_SIZE.width, primary.width);
  const height = Math.min(DEFAULT_SIZE.height, primary.height);
  return {
    bounds: { x: primary.x + Math.round((primary.width - width) / 2),
              y: primary.y + Math.round((primary.height - height) / 2),
              width: width, height: height },
    maximized: false
  };
}

/* The state document saved on move / resize / close. */
function stateDoc(bounds, maximized) {
  return { x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height,
           maximized: maximized === true };
}

/* A download's file name, reduced to a safe base name ("" = refuse). */
function safeFileName(name) {
  const base = String(name || "").split(/[\\/]/).pop().replace(/[\x00-\x1f<>:"|?*]/g, "_")
    .replace(/^[.\s]+/, "").trim();
  return base.slice(0, 120);
}

/* May this download be saved? Only from the core origin (its own page or
   a blob: URL the page made) and only with a .build, .filter, .json or
   .txt name. */
function downloadAllowed(url, filename, port) {
  const u = parse(url);
  if (!u) { return false; }
  const from = u.protocol === "blob:" ? u.pathname : u.href;
  if (!isCoreUrl(from, port)) { return false; }
  const name = safeFileName(filename).toLowerCase();
  return DOWNLOAD_EXT.some((ext) => name.length > ext.length && name.endsWith(ext));
}

/* Poll check() (resolves true when the core answers) every stepMs until
   it is true or timeoutMs passed. Resolves true / false. */
function waitFor(check, timeoutMs, stepMs, sleep, now) {
  const clock = now || Date.now;
  const pause = sleep || ((ms) => new Promise((r) => setTimeout(r, ms)));
  const end = clock() + timeoutMs;
  function round() {
    return Promise.resolve().then(check).then((ok) => ok === true, () => false).then((ok) => {
      if (ok) { return true; }
      if (clock() >= end) { return false; }
      return pause(stepMs).then(round);
    });
  }
  return round();
}

/* GET /api/health with the token; resolves true on 200, false otherwise. */
function makeHealthCheck(http, port, getToken) {
  return function healthy() {
    return new Promise((resolve) => {
      const token = getToken();
      if (!token || !port) { resolve(false); return; }
      const req = http.request({
        host: "127.0.0.1", port: port, path: "/api/health", method: "GET", timeout: 2000,
        headers: { "X-AL-Token": token }
      }, (res) => {
        res.resume();
        resolve(res.statusCode === 200);
      });
      req.on("timeout", () => req.destroy(new Error("timeout")));
      req.on("error", () => resolve(false));
      req.end();
    });
  };
}

module.exports = { dashboardUrl, isCoreUrl, isExternalUrl, externalHref, routeFor,
                   rateAllows, noteOpened, readHosts, downloadAllowed, wantsClient,
                   windowBounds, stateDoc, safeFileName, waitFor, makeHealthCheck,
                   coreOrigin, CLIENT_FLAG, DEFAULT_SIZE, MIN_SIZE, LINK_HOSTS, HOSTS_FILE,
                   RATE, DOWNLOAD_EXT };
