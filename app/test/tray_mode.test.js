"use strict";
/* REL-AUTOSTART-TRAY (decision 0011 and 0041 amendments 2026-11-18): the
   opt-in logon task starts the client tray-only (--client --tray). The
   first open builds the tray and connects the core through the launcher
   (a fake here: nothing is started), with no companion window and no
   focus call; a later plain open (the Start Menu's --client start or a
   tray click) shows the window. Electron is replaced by in-memory fakes;
   no process, window or tray is ever made. */
const test = require("node:test");
const assert = require("node:assert/strict");
const os = require("node:os");
const fs = require("node:fs");
const path = require("node:path");
const Link = require("../client/link.js");
const Launcher = require("../client/launcher.js");
const Client = require("../client/window.js");

const TOKEN = "cd".repeat(24);
const PORT = 8962;

test("wantsTray needs --client and --tray together", () => {
  assert.equal(Link.wantsTray(["electron", "app", "--client", "--tray"]), true);
  assert.equal(Link.wantsTray(["electron", "app", "--TRAY", "--Client"]), true);
  assert.equal(Link.wantsTray(["electron", "app", "--client"]), false);
  assert.equal(Link.wantsTray(["electron", "app", "--tray"]), false); // not a client start
  assert.equal(Link.wantsTray(["--client", "--tray=1"]), false);
  assert.equal(Link.wantsTray([]), false);
  assert.equal(Link.wantsTray(null), false);
  assert.equal(Link.wantsTray("--client --tray"), false);
  assert.equal(Link.TRAY_FLAG, "--tray");
});

function fakeEmitter() {
  const handlers = {};
  return {
    handlers,
    on(ev, fn) { (handlers[ev] = handlers[ev] || []).push(fn); return this; },
    once(ev, fn) { return this.on(ev, fn); },
    emit(ev, ...args) { for (const fn of handlers[ev] || []) { fn(...args); } }
  };
}

function fakeWorld() {
  const calls = [];
  const windows = [];
  const trays = [];
  let coreUp = false;

  class BrowserWindow {
    constructor(o) {
      Object.assign(this, fakeEmitter());
      this.options = o;
      this.visible = false;
      this.destroyed = false;
      this.url = "";
      const wcEvents = fakeEmitter();
      this.webContents = Object.assign(wcEvents, {
        setWindowOpenHandler() {},
        getURL: () => this.url,
        mainFrame: {}
      });
      windows.push(this);
      calls.push("window");
    }
    setMenu() {}
    loadFile(f) { this.url = "file:///" + path.basename(f); }
    loadURL(u) { this.url = u; calls.push("loadURL"); }
    isDestroyed() { return this.destroyed; }
    isVisible() { return this.visible; }
    isMinimized() { return false; }
    isMaximized() { return false; }
    isFocused() { return false; }
    show() { this.visible = true; calls.push("show"); }
    showInactive() { this.visible = true; calls.push("showInactive"); }
    focus() { calls.push("focus"); }
    restore() { calls.push("restore"); }
    maximize() { calls.push("maximize"); }
    minimize() {}
    getBounds() { return { x: 0, y: 0, width: 1280, height: 860 }; }
    getNormalBounds() { return this.getBounds(); }
  }

  class Tray {
    constructor() { Object.assign(this, fakeEmitter()); trays.push(this); calls.push("tray"); }
    setToolTip() {}
    setContextMenu() {}
    displayBalloon() {}
    destroy() {}
  }

  const area = { x: 0, y: 0, width: 1920, height: 1040 };
  const display = { id: 1, workArea: area, bounds: area };
  const ses = { setPermissionRequestHandler() {}, setPermissionCheckHandler() {}, on() {} };
  const electron = {
    BrowserWindow, Tray,
    Menu: { buildFromTemplate: (t) => ({ template: t }) },
    nativeImage: { createEmpty: () => ({ addRepresentation() {} }) },
    session: { fromPartition: () => ses },
    shell: { openExternal: () => Promise.resolve() },
    screen: { getPrimaryDisplay: () => display, getAllDisplays: () => [display] },
    app: { getPath: () => os.tmpdir(), quit() { calls.push("quit"); } }
  };

  /* GET /api/health: refused until the (fake) launcher started the core. */
  const http = {
    request(o, cb) {
      const req = fakeEmitter();
      req.destroy = () => {};
      req.end = () => {
        calls.push("health");
        setImmediate(() => {
          if (coreUp) { cb({ statusCode: 200, resume() {} }); } else { req.emit("error", new Error("refused")); }
        });
      };
      return req;
    }
  };

  return {
    calls, windows, trays, electron, http,
    startCore() { coreUp = true; },
    coreUp: () => coreUp
  };
}

function makeClient(world, argv, runtimeDir) {
  return Client.createClient({
    electron: world.electron, http: world.http, repo: path.join(os.tmpdir(), "al-no-repo"),
    port: PORT, readToken: () => TOKEN, runtimeDir: runtimeDir, log: () => {},
    argv: argv, toggleOverlay() {}, overlayVisible: () => true, restartOverlay() {},
    overlayBounds: () => null
  });
}

function settle() { return new Promise((r) => setTimeout(r, 30)); }

test("a --client --tray first open: tray and core, no window, no focus", async (t) => {
  const world = fakeWorld();
  const runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "al-tray-"));
  t.after(() => fs.rmSync(runtimeDir, { recursive: true, force: true }));
  const started = [];
  const real = Launcher.startCore;
  Launcher.startCore = (repo, port) => { started.push(port); world.startCore(); return 4242; };
  t.after(() => { Launcher.startCore = real; });

  const client = makeClient(world, ["electron.exe", "app", "--client", "--tray"], runtimeDir);
  client.open();
  await settle();
  assert.equal(world.trays.length, 1, "the tray is built");
  assert.equal(client.hasTray(), true);
  assert.deepEqual(started, [PORT], "the core is started through the launcher, once");
  assert.equal(world.windows.length, 0, "no companion window");
  assert.equal(client.window(), null);
  assert.ok(!world.calls.includes("focus"), "no focus call");
  assert.ok(!world.calls.includes("show") && !world.calls.includes("showInactive"));

  // A later plain --client start (second instance -> open()) shows the
  // window; the core already answers, so it is not started again.
  client.open();
  assert.equal(world.windows.length, 1, "the window is created on the later open");
  world.windows[0].emit("ready-to-show");
  await settle();
  assert.ok(world.calls.includes("show"), "the window is shown");
  assert.ok(world.calls.includes("loadURL"), "the dashboard is loaded");
  assert.equal(world.trays.length, 1, "one tray only");
  assert.deepEqual(started, [PORT]);
});

test("a plain --client first open shows the window as before", async (t) => {
  const world = fakeWorld();
  const runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "al-tray-"));
  t.after(() => fs.rmSync(runtimeDir, { recursive: true, force: true }));
  const real = Launcher.startCore;
  Launcher.startCore = () => { world.startCore(); return 4243; };
  t.after(() => { Launcher.startCore = real; });

  const client = makeClient(world, ["electron.exe", "app", "--client"], runtimeDir);
  client.open();
  assert.equal(world.windows.length, 1);
  world.windows[0].emit("ready-to-show");
  await settle();
  assert.ok(world.calls.includes("show"));
});

test("a tray click after a tray-only start opens the window", async (t) => {
  const world = fakeWorld();
  const runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "al-tray-"));
  t.after(() => fs.rmSync(runtimeDir, { recursive: true, force: true }));
  const real = Launcher.startCore;
  Launcher.startCore = () => { world.startCore(); return 4244; };
  t.after(() => { Launcher.startCore = real; });

  const client = makeClient(world, ["electron.exe", "app", "--client", "--tray"], runtimeDir);
  client.open();
  await settle();
  assert.equal(world.windows.length, 0);
  world.trays[0].emit("click");
  assert.equal(world.windows.length, 1);
});
