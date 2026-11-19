"use strict";
/* OVL-SHELL-GUARDS (decision 0061): the Electron shell guards with fake
   webContents and a fake app; no Electron needed. */
const test = require("node:test");
const assert = require("node:assert/strict");
const Guards = require("../guards.js");
const Part = require("../parts/10-guards.js");

const PORT = 8960;
const CORE = "http://127.0.0.1:" + PORT;
// what url.pathToFileURL gives for an install path with a space in it (the
// one drive-rooted shape the leak sweep allows in a fixture)
const OVERLAY_URL = "file:///C:/ProgramData/Ash%20Light/app/overlay/index.html";

function fakeWc() {
  const handlers = {};
  return {
    handlers,
    openHandler: null,
    on(ev, fn) { (handlers[ev] = handlers[ev] || []).push(fn); return this; },
    setWindowOpenHandler(fn) { this.openHandler = fn; },
    emit(ev, url) {
      const e = { url, prevented: false, preventDefault() { this.prevented = true; } };
      for (const fn of handlers[ev] || []) { fn(e, url); }
      return e.prevented;
    }
  };
}

function fakeApp(switches) {
  const calls = [];
  const listeners = {};
  return {
    calls,
    listeners,
    on(ev, fn) { (listeners[ev] = listeners[ev] || []).push(fn); },
    enableSandbox() { calls.push("sandbox"); },
    exit(code) { calls.push("exit " + code); },
    quit() { calls.push("quit"); },
    commandLine: {
      appendSwitch(name) { calls.push("switch " + name); },
      hasSwitch(name) { return (switches || []).includes(name); }
    },
    create(wc) { for (const fn of listeners["web-contents-created"] || []) { fn({}, wc); } }
  };
}

function startPart(env, argv, switches) {
  const app = fakeApp(switches);
  const logged = [];
  const exits = [];
  const ctx = { app, env: env || {}, argv: argv || ["electron.exe", "app", "--client"],
                port: PORT, log: (m) => logged.push(m), exit: (c) => exits.push(c) };
  Part.early(ctx);
  return { app, ctx, logged, exits };
}

test("an unregistered webContents has navigation, redirects, popups and webview refused", () => {
  const { app } = startPart();
  assert.deepEqual(app.calls, ["sandbox", "switch disable-webgl"]);
  const wc = fakeWc();
  app.create(wc);
  assert.equal(wc.emit("will-navigate", CORE + "/"), true);
  assert.equal(wc.emit("will-navigate", "https://example.org/"), true);
  assert.equal(wc.emit("will-redirect", CORE + "/"), true);
  assert.equal(wc.emit("will-attach-webview", ""), true);
  assert.deepEqual(wc.openHandler({ url: CORE + "/" }), { action: "deny" });
  assert.deepEqual(wc.openHandler({ url: "https://example.org/" }), { action: "deny" });
});

test("the overlay registers deny-all; the companion keeps its same-origin loads", () => {
  const { app, ctx } = startPart();
  const overlay = fakeWc();
  const companion = fakeWc();
  app.create(overlay);
  app.create(companion);
  Part.overlayWindow(ctx, { webContents: overlay });
  Part.clientWindow(ctx, { webContents: companion }, {});
  assert.equal(overlay.emit("will-navigate", CORE + "/"), true);
  assert.equal(overlay.emit("will-navigate", "file:///C:/ProgramData/x.html"), true);
  // the companion: same-origin reload / dashboard stay; anything else refused
  assert.equal(companion.emit("will-navigate", CORE + "/#token=abc"), false);
  assert.equal(companion.emit("will-redirect", CORE + "/api/health"), false);
  assert.equal(companion.emit("will-navigate", "https://example.org/"), true);
  assert.equal(companion.emit("will-navigate", "http://127.0.0.1:9999/"), true);
  assert.equal(companion.emit("will-navigate", "file:///C:/ProgramData/x.html"), true);
  assert.equal(companion.emit("will-attach-webview", CORE + "/"), true);
  assert.deepEqual(companion.openHandler({ url: CORE + "/" }), { action: "deny" });
  // a webContents created before the guards existed is not in the registry
  assert.equal(Part.registry().has(fakeWc()), false);
});

test("a throwing policy refuses", () => {
  const reg = Guards.createRegistry();
  const wc = fakeWc();
  reg.register(wc, () => { throw new Error("boom"); });
  Guards.attachDefaults(wc, reg);
  assert.equal(wc.emit("will-navigate", CORE + "/"), true);
});

function fakeWin(frameUrl) {
  const mainFrame = { url: frameUrl };
  return { win: { webContents: { mainFrame }, isDestroyed: () => false }, mainFrame };
}

test("al:config answers only the overlay main frame on the exact page", () => {
  const spellings = [
    OVERLAY_URL,
    "file:///C:/ProgramData/Ash Light/app/overlay/index.html",
    "file:///c:/ProgramData/Ash%20Light/app/overlay/index.html",
    "file://C:\\ProgramData\\Ash Light\\app\\overlay\\index.html"
  ];
  for (const s of spellings) {
    const { win, mainFrame } = fakeWin(s);
    assert.equal(Guards.frameIsOverlayPage(mainFrame, win, OVERLAY_URL), true, s);
  }
  // a foreign file URL that also ends in /overlay/index.html
  const foreign = fakeWin("file:///C:/ProgramData/Downloads/evil/overlay/index.html");
  assert.equal(Guards.frameIsOverlayPage(foreign.mainFrame, foreign.win, OVERLAY_URL), false);
  // the right URL, but a subframe (not the main frame)
  const { win } = fakeWin(OVERLAY_URL);
  assert.equal(Guards.frameIsOverlayPage({ url: OVERLAY_URL }, win, OVERLAY_URL), false);
  // no window, a destroyed window, no frame, an http page
  assert.equal(Guards.frameIsOverlayPage({ url: OVERLAY_URL }, null, OVERLAY_URL), false);
  const gone = fakeWin(OVERLAY_URL);
  gone.win.isDestroyed = () => true;
  assert.equal(Guards.frameIsOverlayPage(gone.mainFrame, gone.win, OVERLAY_URL), false);
  assert.equal(Guards.frameIsOverlayPage(null, win, OVERLAY_URL), false);
  const web = fakeWin(CORE + "/overlay/index.html");
  assert.equal(Guards.frameIsOverlayPage(web.mainFrame, web.win, OVERLAY_URL), false);
  // a bad percent escape is not the page
  const bad = fakeWin("file:///C:/ProgramData/Ash%ZZLight/app/overlay/index.html");
  assert.equal(Guards.frameIsOverlayPage(bad.mainFrame, bad.win, OVERLAY_URL), false);
});

test("al:restart-overlay: at most once per 2 s", () => {
  let now = 1000;
  const gate = Guards.throttle(2000, () => now);
  assert.equal(gate(), true);
  now = 1500;
  assert.equal(gate(), false);
  now = 2999;
  assert.equal(gate(), false);
  now = 3000;
  assert.equal(gate(), true);
  now = 3001;
  assert.equal(gate(), false);
});

test("a debugging start quits unless AL_DEV=1", () => {
  const plain = ["electron.exe", "app", "--client"];
  assert.equal(Guards.isDebugStart(plain, {}), false);
  for (const arg of ["--inspect", "--inspect=9229", "--inspect-brk", "--inspect-brk-node=1",
                     "--remote-debugging-port=9222", "-remote-debugging-port=9222",
                     "/remote-debugging-port=9222", "--remote-debugging-pipe",
                     "--REMOTE-DEBUGGING-PORT=1", "--debug"]) {
    assert.equal(Guards.isDebugStart(plain.concat([arg]), {}), true, arg);
    assert.equal(Guards.isDebugStart(plain.concat([arg]), { AL_DEV: "1" }), false, arg);
  }
  assert.equal(Guards.isDebugStart(plain, { NODE_OPTIONS: "--require x.js" }), true);
  assert.equal(Guards.isDebugStart(plain, { node_options: "--inspect" }), true);
  assert.equal(Guards.isDebugStart(plain, { NODE_OPTIONS: "  " }), false);
  assert.equal(Guards.isDebugStart(plain, { NODE_OPTIONS: "x", AL_DEV: "1" }), false);
  assert.equal(Guards.isDebugStart(plain, { AL_DEV: "0", NODE_OPTIONS: "x" }), true);
  // words that only look alike
  assert.equal(Guards.isDebugStart(plain.concat(["--inspector-off", "--debugger"]), {}), false);

  const quit = startPart({}, plain.concat(["--inspect"]));
  assert.deepEqual(quit.app.calls, ["exit 1"]);
  assert.deepEqual(quit.exits, [1]);
  assert.match(quit.logged[0], /quits/);
  assert.equal((quit.app.listeners["web-contents-created"] || []).length, 0);
  const envQuit = startPart({ NODE_OPTIONS: "--require x.js" });
  assert.deepEqual(envQuit.exits, [1]);
  // a switch Chromium parsed in another spelling
  const chromium = startPart({}, plain, ["remote-debugging-port"]);
  assert.deepEqual(chromium.exits, [1]);
  const dev = startPart({ AL_DEV: "1", NODE_OPTIONS: "x" }, plain.concat(["--inspect"]),
                        ["remote-debugging-port"]);
  assert.deepEqual(dev.exits, []);
  assert.deepEqual(dev.app.calls, ["sandbox", "switch disable-webgl"]);
});
