"use strict";
/* OVL-SHELL-GUARDS (decision 0061): the pure rules of the Electron shell
   guards. No Electron here, so node --test covers every branch;
   app/parts/10-guards.js wires them at the parts' early hook and
   app/main.js uses them in its IPC block.

   - isDebugStart(argv, env): an inspect switch, a remote-debugging port or
     pipe, or a NODE_OPTIONS value is a start the shell refuses (it quits),
     unless the developer said so with AL_DEV=1. Chromium on Windows also
     reads "-name" and "/name" as switches, so all three spellings count.
   - frameIsOverlayPage(frame, win, overlayUrl): the IPC sender is the
     overlay window's main frame showing exactly the overlay page on the
     app scheme (OVL-APP-SCHEME: origin al-app://app and path compared
     exactly, query and fragment ignored; app/pages.js pageKey). A file
     URL, another app scheme page or an http page is not it.
   - throttle(ms, now): a gate that lets one call through per ms.
   - createRegistry / attachDefaults: every webContents the app makes gets
     default-deny navigation, redirects, popups and webview attach; a
     webContents its creator registered gets that creator's policy,
     looked up at event time. */

const Pages = require("./pages.js");

const DEBUG_SWITCHES = ["remote-debugging-port", "remote-debugging-pipe"];

/* The environment names no child of the client gets (OVL-LAUNCH-ENV, F-110;
   REL-RUNTIME-SCRIPTS): either one turns electron.exe into a Node script
   host or a debug target before any app code runs. Kept here, the one place
   that names the debug variables; app/client/home.js childEnv() strips
   them (any case) and scripts/run.ps1 unsets the same two ($clientUnset). */
const STRIPPED_ENV = Object.freeze(["ELECTRON_RUN_AS_NODE", "NODE_OPTIONS"]);

/* The switch name of one command-line argument, or "" when it is none. */
function switchName(arg) {
  const s = String(arg == null ? "" : arg).trim();
  const m = /^(?:--|-|\/)([A-Za-z][A-Za-z0-9-]*)(?:=|$)/.exec(s);
  return m ? m[1].toLowerCase() : "";
}

function isDebugSwitch(name) {
  if (!name) { return false; }
  if (name === "inspect" || name.startsWith("inspect-")) { return true; }
  if (name === "debug" || name === "debug-brk") { return true; }
  return DEBUG_SWITCHES.includes(name);
}

/* True when this start must quit: a debug switch in argv or a NODE_OPTIONS
   value in env, and AL_DEV is not "1". */
function isDebugStart(argv, env) {
  const e = env && typeof env === "object" ? env : {};
  if (e.AL_DEV === "1") { return false; }
  const args = Array.isArray(argv) ? argv : [];
  if (args.some((a) => isDebugSwitch(switchName(a)))) { return true; }
  const opts = Object.keys(e).filter((k) => k.toUpperCase() === "NODE_OPTIONS");
  return opts.some((k) => typeof e[k] === "string" && e[k].trim() !== "");
}

/* Is frame the overlay window's main frame on exactly overlayUrl? */
function frameIsOverlayPage(frame, win, overlayUrl) {
  if (!frame || !win) { return false; }
  if (typeof win.isDestroyed === "function" && win.isDestroyed()) { return false; }
  const wc = win.webContents;
  if (!wc || frame !== wc.mainFrame) { return false; }
  const want = Pages.pageKey(overlayUrl);
  return want !== "" && Pages.pageKey(frame.url) === want;
}

/* A gate: the first call is let through (true), then every call within
   ms of the last one let through is refused (false). */
function throttle(ms, now) {
  const clock = typeof now === "function" ? now : Date.now;
  let last = null;
  return function gate() {
    const t = clock();
    if (last !== null && t - last < ms) { return false; }
    last = t;
    return true;
  };
}

/* The webContents its creator registered, each with a policy:
   policy(url, kind) -> true to allow; kind is "navigate", "redirect" or
   "popup". A webview attach is never allowed. */
function createRegistry() {
  const map = new WeakMap();
  return {
    register(wc, policy) {
      if (wc && typeof wc === "object") { map.set(wc, typeof policy === "function" ? policy : null); }
    },
    allows(wc, url, kind) {
      if (!wc || typeof wc !== "object" || !map.has(wc)) { return false; }
      const policy = map.get(wc);
      if (!policy) { return false; }
      try { return policy(String(url || ""), kind) === true; } catch (e) { return false; }
    },
    has(wc) { return !!wc && typeof wc === "object" && map.has(wc); }
  };
}

/* The policy that allows nothing (the overlay). */
function denyAll() { return false; }

function eventUrl(e, legacy) {
  return (e && typeof e.url === "string" && e.url) || (typeof legacy === "string" ? legacy : "");
}

/* Attach the default-deny handlers to one new webContents. say(msg) logs a
   refusal. The window's own handlers (app/main.js, app/client/window.js)
   may add more; a later setWindowOpenHandler of the creator replaces this
   one, and every creator's handler denies popups too. */
function attachDefaults(wc, registry, say) {
  const log = typeof say === "function" ? say : () => {};
  const refuse = (e, kind) => {
    if (e && typeof e.preventDefault === "function") { e.preventDefault(); }
    log("guards: " + kind + " refused");
  };
  wc.on("will-navigate", (e, legacy) => {
    if (!registry.allows(wc, eventUrl(e, legacy), "navigate")) { refuse(e, "navigation"); }
  });
  wc.on("will-redirect", (e, legacy) => {
    if (!registry.allows(wc, eventUrl(e, legacy), "redirect")) { refuse(e, "redirect"); }
  });
  wc.on("will-attach-webview", (e) => refuse(e, "webview"));
  wc.setWindowOpenHandler((details) => {
    const url = details && details.url;
    if (registry.allows(wc, url, "popup")) { return { action: "allow" }; }
    log("guards: popup refused");
    return { action: "deny" };
  });
}

module.exports = { isDebugStart, frameIsOverlayPage, throttle, createRegistry, attachDefaults,
                   denyAll, switchName, DEBUG_SWITCHES, STRIPPED_ENV };
