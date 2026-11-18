"use strict";
/* DESKTOP-CLIENT (decision 0041): the pure rules of the companion window.
   No Electron here, so node --test covers every branch.

   - the dashboard URL carries the per-start token in the FRAGMENT: a
     fragment is never sent over the network, the window has no URL bar,
     and web/app.js moves it to sessionStorage and strips it at once;
   - the window may only show the local core (http://127.0.0.1:<port>);
     anything else is refused, and only http(s) links leave, to the user's
     default browser;
   - the saved size and position are used only when they still land on a
     connected display. */

const HEX_TOKEN = /^[0-9a-fA-F]{16,256}$/;
const DEFAULT_SIZE = { width: 1280, height: 860 };
const MIN_SIZE = { width: 560, height: 420 };
const CLIENT_FLAG = "--client";

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

/* May this URL go to the user's default browser? http(s) only, with a host,
   never a local file, script or custom scheme. */
function isExternalUrl(url) {
  const u = parse(url);
  return !!u && (u.protocol === "https:" || u.protocol === "http:") && !!u.hostname &&
    !u.username && !u.password;
}

/* What the window does with a navigation or popup request:
   "stay" (the core itself, navigations only), "external" (hand to the
   default browser) or "deny". A popup never opens a second window. */
function routeFor(url, port, isPopup) {
  if (isCoreUrl(url, port)) { return isPopup ? "deny" : "stay"; }
  if (isExternalUrl(url)) { return "external"; }
  return "deny";
}

/* Is --client among these command-line args? */
function wantsClient(argv) {
  return Array.isArray(argv) && argv.some((a) => String(a).toLowerCase() === CLIENT_FLAG);
}

function intersects(a, b) {
  return a.x < b.x + b.width && b.x < a.x + a.width &&
    a.y < b.y + b.height && b.y < a.y + a.height;
}

/* Window bounds from the saved state and the displays' work areas
   ([{x,y,width,height}], primary first). A saved rect that no display shows
   at least 80x80 of falls back to the default size, centred on the primary. */
function windowBounds(saved, workAreas) {
  const areas = Array.isArray(workAreas) ? workAreas.filter((a) => a && a.width > 0) : [];
  const primary = areas[0] || { x: 0, y: 0, width: 1920, height: 1080 };
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

module.exports = { dashboardUrl, isCoreUrl, isExternalUrl, routeFor, wantsClient,
                   windowBounds, stateDoc, safeFileName, waitFor, makeHealthCheck,
                   coreOrigin, CLIENT_FLAG, DEFAULT_SIZE, MIN_SIZE };
