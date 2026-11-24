"use strict";
/* REL-AUTOSTART-SWITCH (decision 0011, ruling Q-08): "Start with Windows"
   in the tray menu. The checkbox shows the recorded choice
   (<runtime>/autostart.json, default off); a click runs the existing
   scripts\autostart.ps1 -Enable or -Disable hidden through the launcher
   (spawn injected here: the script never runs); the preload hands the
   dashboard exactly five fixed, argument-free actions (the fifth,
   setupCalc, is TC-CALC-OPTIN-BUTTON's, ruling W16-1); the IPC handlers
   answer only the companion window's main frame on the local core. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const vm = require("node:vm");
const Launcher = require("../client/launcher.js");
const TrayMenu = require("../client/tray_menu.js");
const Client = require("../client/window.js");
const Hello = require("../hello.js");
const crypto = require("node:crypto");

const APP = path.join(__dirname, "..");
const PORT = 8961;
const TOKEN = "ab".repeat(24);

function noop() {}

function acts(calls) {
  return { toggleCompanion: () => calls.push("c"), toggleOverlay: () => calls.push("o"),
           toggleWake: () => calls.push("w"), toggleAutostart: () => calls.push("a"),
           restart: () => calls.push("r"), quit: () => calls.push("q") };
}

test("tray template: the 'Start with Windows' checkbox carries the recorded state", () => {
  const calls = [];
  for (const on of [true, false]) {
    const items = TrayMenu.trayTemplate({ autostartOn: on }, acts(calls));
    const item = items.find((i) => i.id === "autostart");
    assert.ok(item, "the autostart item is in the menu");
    assert.equal(item.label, "Start with Windows");
    assert.equal(TrayMenu.AUTOSTART_LABEL, "Start with Windows");
    assert.equal(item.type, "checkbox");
    assert.equal(item.checked, on);
    item.click();
  }
  assert.deepEqual(calls, ["a", "a"]);
  // no state given: unchecked (autostart is off by default, decision 0011)
  const bare = TrayMenu.trayTemplate(undefined, acts([]));
  assert.equal(bare.find((i) => i.id === "autostart").checked, false);
  assert.equal(TrayMenu.trayTemplate({ autostartOn: "yes" }, acts([]))
    .find((i) => i.id === "autostart").checked, false);
});

function fakeSpawn(log, pid) {
  return (cmd, args, opts) => {
    const handlers = {};
    const child = {
      pid: pid,
      on(ev, fn) { handlers[ev] = fn; return child; },
      unref() { log.push("unref"); }
    };
    log.push({ cmd: cmd, args: args, opts: opts, emit: (ev, v) => handlers[ev](v) });
    return child;
  };
}

test("Launcher.setAutostart runs scripts\\autostart.ps1 -Enable / -Disable hidden, nothing else", () => {
  for (const [on, flag] of [[true, "-Enable"], [false, "-Disable"]]) {
    const log = [];
    const done = [];
    assert.equal(Launcher.setAutostart("R", on, fakeSpawn(log, 77), (c) => done.push(c)), 77);
    const run = log[0];
    assert.equal(run.cmd, Launcher.psExe());
    const script = path.join("R", "scripts", "autostart.ps1");
    assert.deepEqual(run.args, Launcher.psArgs(script, [flag]));
    // the script gets exactly one argument: the flag
    assert.deepEqual(run.args.slice(run.args.indexOf("-File") + 1), [script, flag]);
    assert.deepEqual(run.args.slice(0, run.args.indexOf("-File")),
      ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden"]);
    assert.equal(run.opts.windowsHide, true);
    assert.equal(run.opts.detached, false);
    assert.equal(run.opts.stdio, "ignore");
    assert.equal(run.opts.cwd, "R");
    assert.ok(log.includes("unref"));
    // done once, when the script exits
    assert.deepEqual(done, []);
    run.emit("exit", 0);
    run.emit("error", new Error("late"));
    assert.deepEqual(done, [0]);
  }
  // only a literal true enables
  const log = [];
  Launcher.setAutostart("R", "yes", fakeSpawn(log, 1));
  assert.equal(log[0].args[log[0].args.length - 1], "-Disable");
  // a spawn that throws: 0, and done(null)
  const done = [];
  assert.equal(Launcher.setAutostart("R", true, () => { throw new Error("no ps"); },
                                     (c) => done.push(c)), 0);
  assert.deepEqual(done, [null]);
  // the spawn failing later (error event): done(null) once
  const late = [];
  const done2 = [];
  Launcher.setAutostart("R", true, fakeSpawn(late, 5), (c) => done2.push(c));
  late[0].emit("error", new Error("ENOENT"));
  late[0].emit("exit", 1);
  assert.deepEqual(done2, [null]);
});

test("Launcher.readAutostart reads AshLight's own <runtime>/autostart.json, default off", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "al-autostart-"));
  try {
    const file = path.join(dir, Launcher.AUTOSTART_FILE);
    assert.equal(Launcher.AUTOSTART_FILE, "autostart.json");
    assert.equal(Launcher.readAutostart(dir), false); // no file: off
    fs.writeFileSync(file, '{"enabled":true,"task":"\\\\AshLight\\\\AshLight Autostart"}\n', "ascii");
    assert.equal(Launcher.readAutostart(dir), true);
    fs.writeFileSync(file, '{"enabled":false}\n', "ascii");
    assert.equal(Launcher.readAutostart(dir), false);
    fs.writeFileSync(file, '{"enabled":"true"}\n', "ascii");
    assert.equal(Launcher.readAutostart(dir), false); // only a JSON true
    fs.writeFileSync(file, "\uFEFF" + '{"enabled":true}', "utf8");
    assert.equal(Launcher.readAutostart(dir), true); // a BOM is tolerated
    fs.writeFileSync(file, "{broken", "ascii");
    assert.equal(Launcher.readAutostart(dir), false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
  // fs is injectable; the one path read is <home>/autostart.json
  const read = [];
  const fakeFs = { readFileSync: (p) => { read.push(p); return '{"enabled":true}'; } };
  assert.equal(Launcher.readAutostart("H", fakeFs), true);
  assert.deepEqual(read, [path.join("H", "autostart.json")]);
});

function code(js) {
  return js.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

test("preload: exactly restartOverlay, autostartOn, autostartOff, autostartState, setupCalc, no arguments", () => {
  const src = fs.readFileSync(path.join(APP, "client", "preload.js"), "utf8");
  const sent = [];
  let exposed = null;
  const electron = {
    contextBridge: { exposeInMainWorld: (name, api) => { exposed = { name: name, api: api }; } },
    ipcRenderer: {
      send: (...a) => { sent.push(["send"].concat(a)); },
      invoke: (...a) => { sent.push(["invoke"].concat(a)); return Promise.resolve(null); }
    }
  };
  vm.runInNewContext(src, { require: (m) => { assert.equal(m, "electron"); return electron; } });
  assert.equal(exposed.name, "alClient");
  assert.deepEqual(Object.keys(exposed.api).sort(),
    ["autostartOff", "autostartOn", "autostartState", "restartOverlay", "setupCalc"]);
  assert.ok(Object.isFrozen(exposed.api));
  for (const k of Object.keys(exposed.api)) {
    assert.equal(exposed.api[k].length, 0, k + " takes no argument");
  }
  // an argument the page passes is never forwarded: channel only
  exposed.api.restartOverlay("x");
  exposed.api.autostartOn({ evil: 1 });
  exposed.api.autostartOff(1);
  exposed.api.autostartState("y");
  exposed.api.setupCalc("powershell", ["-c"]);
  assert.deepEqual(sent, [["send", "al:restart-overlay"], ["send", "al:autostart-on"],
                          ["send", "al:autostart-off"], ["invoke", "al:autostart-state"],
                          ["invoke", "al:setup-calc"]]);
  // statically: every ipcRenderer call names one fixed channel and nothing else
  const calls = code(src).match(/ipcRenderer\.\w+\([^)]*\)/g);
  assert.equal(calls.length, 5);
  for (const c of calls) { assert.match(c, /^ipcRenderer\.(send|invoke)\("al:[a-z-]+"\)$/); }
  assert.ok(!/token|require\("fs"\)|sendSync|process\./.test(code(src)));
});

function emitter() {
  const handlers = {};
  return {
    on(ev, fn) { (handlers[ev] = handlers[ev] || []).push(fn); return this; },
    once(ev, fn) { return this.on(ev, fn); },
    emit(ev, ...args) { for (const fn of handlers[ev] || []) { fn(...args); } }
  };
}

/* SEC-HELLO-CLIENT (decision 0054): the fake core answers the hello
   handshake with a real proof (app/hello.js) for the nonce it got and the
   dialled port, so the client's health check sees a proven core. */
function helloReply(o, cb) {
  const res = emitter();
  res.statusCode = 200;
  res.resume = noop;
  const nonce = o.headers[Hello.NONCE_HEADER];
  const body = JSON.stringify({ port: o.port, proof: Hello.serverProof(crypto, TOKEN, nonce, o.port) });
  setImmediate(() => { cb(res); res.emit("data", Buffer.from(body)); res.emit("end"); });
}

function fakeWorld() {
  const windows = [];
  const menus = [];
  const ipc = { on: {}, handle: {} };
  class BrowserWindow {
    constructor() {
      Object.assign(this, emitter());
      this.url = "";
      this.webContents = Object.assign(emitter(), {
        setWindowOpenHandler() {},
        getURL: () => this.url,
        mainFrame: { url: "" }
      });
      windows.push(this);
    }
    setMenu() {}
    loadFile(f) { this.url = "file:///" + path.basename(f); this.webContents.mainFrame.url = this.url; }
    loadURL(u) { this.url = u; this.webContents.mainFrame.url = u; }
    isDestroyed() { return false; }
    isVisible() { return true; }
    isMinimized() { return false; }
    isMaximized() { return false; }
    isFocused() { return false; }
    show() {}
    showInactive() {}
    focus() {}
    restore() {}
    maximize() {}
    minimize() {}
    getBounds() { return { x: 0, y: 0, width: 1280, height: 860 }; }
    getNormalBounds() { return this.getBounds(); }
  }
  class Tray {
    constructor() { Object.assign(this, emitter()); }
    setToolTip() {}
    setContextMenu(m) { menus.push(m.template); }
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
    app: { getPath: () => os.tmpdir(), quit() {} },
    ipcMain: {
      on(ch, fn) { assert.ok(!ipc.on[ch], ch); ipc.on[ch] = fn; },
      handle(ch, fn) { assert.ok(!ipc.handle[ch], ch); ipc.handle[ch] = fn; }
    }
  };
  const http = {
    request(o, cb) {
      const req = emitter();
      req.destroy = noop;
      req.end = () => {
        if (o.path === Hello.PATH) { helloReply(o, cb); return; }
        setImmediate(() => cb({ statusCode: 200, resume() {} }));
      };
      return req;
    }
  };
  return { windows, menus, ipc, electron, http };
}

function settle() { return new Promise((r) => setTimeout(r, 30)); }

function lastAutostart(world) {
  return world.menus[world.menus.length - 1].find((i) => i.id === "autostart");
}

test("tray click and IPC: the script runs through the launcher; only the companion's main frame is answered", async (t) => {
  const world = fakeWorld();
  const runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "al-autostart-"));
  t.after(() => fs.rmSync(runtimeDir, { recursive: true, force: true }));
  const runs = [];
  const real = Launcher.setAutostart;
  Launcher.setAutostart = (repo, on, spawn, done) => { runs.push({ repo, on, spawn, done }); return 99; };
  t.after(() => { Launcher.setAutostart = real; });

  const client = Client.createClient({
    electron: world.electron, http: world.http, repo: "REPO", port: PORT,
    readToken: () => TOKEN, runtimeDir: runtimeDir, log: noop, argv: ["electron", "app", "--client"],
    toggleOverlay: noop, overlayVisible: () => true, restartOverlay: noop, overlayBounds: () => null
  });
  // the three handlers, registered once inside createClient
  assert.deepEqual(Object.keys(world.ipc.on).sort(), ["al:autostart-off", "al:autostart-on"]);
  assert.deepEqual(Object.keys(world.ipc.handle), ["al:autostart-state"]);
  const state = world.ipc.handle["al:autostart-state"];

  // before any window: nobody is the companion
  assert.equal(state({ sender: {}, senderFrame: {} }), null);
  world.ipc.on["al:autostart-on"]({ sender: {}, senderFrame: {} });
  assert.equal(runs.length, 0);

  client.open();
  await settle();
  const win = world.windows[0];
  assert.ok(win.url.startsWith("http://127.0.0.1:" + PORT), "the dashboard is shown");
  assert.equal(lastAutostart(world).checked, false, "no record: unchecked");

  const good = { sender: win.webContents, senderFrame: win.webContents.mainFrame };
  const strangers = [
    { sender: {}, senderFrame: win.webContents.mainFrame }, // another webContents
    { sender: win.webContents, senderFrame: { url: win.url } }, // a subframe
    { sender: win.webContents, senderFrame: null },
    undefined
  ];
  for (const e of strangers) {
    world.ipc.on["al:autostart-on"](e);
    world.ipc.on["al:autostart-off"](e);
    assert.equal(state(e), null);
  }
  assert.equal(runs.length, 0, "strangers start nothing");
  // the main frame off the core (the starting page) is refused too
  const saved = win.webContents.mainFrame.url;
  win.webContents.mainFrame.url = "file:///starting.html";
  world.ipc.on["al:autostart-on"](good);
  assert.equal(state(good), null);
  win.webContents.mainFrame.url = saved;
  assert.equal(runs.length, 0);

  assert.deepEqual(state(good), { enabled: false });
  world.ipc.on["al:autostart-on"](good, "-Status", { extra: 1 }); // data is ignored
  assert.equal(runs.length, 1);
  assert.equal(runs[0].repo, "REPO");
  assert.equal(runs[0].on, true);
  assert.equal(runs[0].spawn, undefined, "the real spawn, hidden, from the launcher");
  // one run at a time
  world.ipc.on["al:autostart-off"](good);
  assert.equal(runs.length, 1);
  // the script wrote its record and exited: the tray follows it
  fs.writeFileSync(path.join(runtimeDir, "autostart.json"), '{"enabled":true}\n', "ascii");
  const before = world.menus.length;
  runs[0].done(0);
  assert.ok(world.menus.length > before, "the menu is rebuilt on exit");
  assert.equal(lastAutostart(world).checked, true);
  assert.deepEqual(state(good), { enabled: true });

  world.ipc.on["al:autostart-off"](good);
  assert.equal(runs.length, 2);
  assert.equal(runs[1].on, false);
  fs.writeFileSync(path.join(runtimeDir, "autostart.json"), '{"enabled":false}\n', "ascii");
  runs[1].done(0);
  assert.equal(lastAutostart(world).checked, false);

  // the tray click flips the recorded choice
  lastAutostart(world).click();
  assert.equal(runs.length, 3);
  assert.equal(runs[2].on, true);
  runs[2].done(3); // -Enable refused (a task of another folder): the record stays off
  assert.equal(lastAutostart(world).checked, false);
  fs.writeFileSync(path.join(runtimeDir, "autostart.json"), '{"enabled":true}\n', "ascii");
  client.refresh();
  lastAutostart(world).click();
  assert.equal(runs[3].on, false);
});

test("a fake electron without ipcMain still builds the client (no handlers)", () => {
  const world = fakeWorld();
  delete world.electron.ipcMain;
  const client = Client.createClient({
    electron: world.electron, http: world.http, repo: "REPO", port: PORT,
    readToken: () => TOKEN, runtimeDir: os.tmpdir(), log: noop, argv: [],
    toggleOverlay: noop, overlayVisible: () => true, restartOverlay: noop, overlayBounds: () => null
  });
  assert.equal(typeof client.toggleAutostart, "function");
});
