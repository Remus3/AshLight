"use strict";
/* OVL-SHELL-GUARDS (decision 0061, parts seam of decision 0053): the shell
   hardening every window and page inherits, so a new window never has to
   repeat it.

   - early: the debug-start quit (an inspect switch, a remote-debugging
     port or pipe, or NODE_OPTIONS; AL_DEV=1 allows them), the sandbox for
     every renderer (app.enableSandbox), WebGL off for every page, and the
     web-contents-created defaults: navigation, redirects, popups and
     webview attach are refused on any webContents its creator did not
     register, the registry being read at event time.
   - overlayWindow: the overlay registers with the deny-all policy.
   - clientWindow: the companion registers with its own route rule
     (app/client/link.js routeFor): it may stay on the local core, so its
     same-origin reload and dashboard loads keep working; links that leave
     are still handed to the default browser by app/client/window.js.

   No window, timer, process or clipboard here; ctx.app is Electron's app
   (or a test fake). */

const Guards = require("../guards.js");
const Link = require("../client/link.js");

let registry = Guards.createRegistry();

function say(ctx) {
  return ctx && typeof ctx.log === "function" ? ctx.log : () => {};
}

/* Quit before any window or listener exists: app.exit, then the process
   exit (ctx.exit in tests), so the rest of app/main.js never runs on. */
function quitNow(ctx) {
  const app = ctx.app;
  if (typeof app.exit === "function") { app.exit(1); } else { app.quit(); }
  const exit = typeof ctx.exit === "function" ? ctx.exit : (code) => process.exit(code);
  exit(1);
}

/* A debug switch Chromium itself already parsed (any spelling). */
function chromiumDebugSwitch(app) {
  const cl = app && app.commandLine;
  if (!cl || typeof cl.hasSwitch !== "function") { return false; }
  return Guards.DEBUG_SWITCHES.some((n) => cl.hasSwitch(n));
}

function early(ctx) {
  const app = ctx.app;
  const env = ctx.env || {};
  const argv = Array.isArray(ctx.argv) ? ctx.argv : process.argv;
  if (Guards.isDebugStart(argv, env) || (env.AL_DEV !== "1" && chromiumDebugSwitch(app))) {
    say(ctx)("guards: a debugging switch or Node options are set; AshLight quits (AL_DEV=1 allows it)");
    quitNow(ctx);
    return;
  }
  if (typeof app.enableSandbox === "function") { app.enableSandbox(); }
  if (app.commandLine && typeof app.commandLine.appendSwitch === "function") {
    app.commandLine.appendSwitch("disable-webgl");
  }
  registry = Guards.createRegistry();
  const reg = registry;
  app.on("web-contents-created", (e, wc) => {
    if (wc && typeof wc.on === "function") { Guards.attachDefaults(wc, reg, say(ctx)); }
  });
}

function overlayWindow(ctx, win) {
  if (win && win.webContents) { registry.register(win.webContents, Guards.denyAll); }
}

/* The companion may navigate (or be redirected) only onto the local core;
   it never opens a popup. */
function companionPolicy(port) {
  return (url, kind) => kind !== "popup" && Link.routeFor(url, port, false) === "stay";
}

function clientWindow(ctx, win) {
  if (win && win.webContents) { registry.register(win.webContents, companionPolicy(ctx.port)); }
}

module.exports = { early, overlayWindow, clientWindow, companionPolicy,
                   registry: () => registry };
