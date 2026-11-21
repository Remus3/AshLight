"use strict";
/* OVL-CLIENT-GUARD (F-105): the client survives its own errors without a
   dialog and rebuilds a dead overlay or companion page, within caps. */
const test = require("node:test");
const assert = require("node:assert");
const EventEmitter = require("events");
const fs = require("fs");
const os = require("os");
const path = require("path");
const Guard = require("../crashguard.js");
const Part = require("../parts/05-crashguard.js");

const APP = path.join(__dirname, "..");

function code(js) {
  return js.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

// a drive letter built at run time: no machine path in a tracked file
const DRIVE = String.fromCharCode(68) + ":";

function tmpDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "al-crashguard-"));
}

function readExit(dir) {
  return JSON.parse(fs.readFileSync(path.join(dir, Guard.FILE_NAME), "utf8"));
}

function fakeWin() {
  const wc = new EventEmitter();
  wc.reloads = 0;
  wc.reload = () => { wc.reloads += 1; };
  const w = { webContents: wc, destroyed: false };
  w.isDestroyed = () => w.destroyed;
  return w;
}

/* A client ctx with a fake app, process, clock and tray. */
function harness(opts) {
  const o = opts || {};
  const t = { ms: o.start || 1800000000000 };
  const logs = [];
  const calls = { relaunch: 0, exit: [], restart: 0, tooltip: [] };
  const app = new EventEmitter();
  app.relaunch = () => { calls.relaunch += 1; };
  app.exit = (c) => { calls.exit.push(c); };
  const proc = new EventEmitter();
  proc.pid = 4242;
  const dir = o.dir || tmpDir();
  let overlay = null;
  const tray = { setToolTip: (s) => calls.tooltip.push(s) };
  const ctx = {
    app: app, process: proc, runtimeDir: dir, log: (m) => logs.push(m),
    now: () => t.ms,
    getOverlay: () => overlay,
    getClient: () => ({ tray: () => tray }),
    actions: { restartOverlay: () => { calls.restart += 1; } }
  };
  Part.early(ctx);
  return {
    ctx: ctx, t: t, logs: logs, calls: calls, app: app, proc: proc, dir: dir,
    setOverlay: (w) => { overlay = w; }
  };
}

test("an error thrown in the main process logs its stack and opens no dialog", () => {
  const h = harness();
  assert.equal(h.proc.listenerCount("uncaughtException"), 1);
  assert.equal(h.proc.listenerCount("unhandledRejection"), 1);
  const err = new Error("boom in " + DRIVE + "\\work\\x.js");
  h.proc.emit("uncaughtException", err);
  assert.ok(h.logs.some((l) => l.includes("client error (uncaught exception)") &&
                               l.includes(err.stack)), h.logs.join("\n"));
  assert.equal(h.calls.relaunch, 0);
  assert.deepEqual(h.calls.exit, []);
  const rec = readExit(h.dir);
  assert.equal(rec.reason, "crash");
  assert.equal(rec.pid, 4242);
  assert.equal(rec.at, h.t.ms / 1000);
  assert.equal(rec.detail, "uncaught exception: Error: boom in <path>");
  h.proc.emit("unhandledRejection", "plain reason");
  assert.ok(h.logs.some((l) => l.includes("client error (unhandled rejection): plain reason")));
  // no dialog anywhere in the guard: the registered handlers are what keep
  // Electron's own error box away
  for (const f of ["crashguard.js", "parts/05-crashguard.js"]) {
    const c = code(fs.readFileSync(path.join(APP, f), "utf8"));
    assert.ok(!/dialog|showMessageBox|showErrorBox/.test(c), f);
    for (const banned of [/setInterval\(/, /setTimeout\(/, /new\s+BrowserWindow/,
                          /child_process/, /clipboard/]) {
      assert.ok(!banned.test(c), f + " " + banned);
    }
  }
});

test("a handler that meets a broken log still carries on", () => {
  const h = harness();
  h.ctx.log = () => { throw new Error("log gone"); };
  Part.early(h.ctx);
  assert.doesNotThrow(() => h.proc.emit("uncaughtException", new Error("x")));
});

test("three errors in 60 s relaunch once", () => {
  const h = harness();
  h.proc.emit("uncaughtException", new Error("one"));
  h.t.ms += 20000;
  h.proc.emit("uncaughtException", new Error("two"));
  assert.equal(h.calls.relaunch, 0);
  h.t.ms += 20000;
  h.proc.emit("unhandledRejection", new Error("three"));
  assert.equal(h.calls.relaunch, 1);
  assert.deepEqual(h.calls.exit, [0]);
  const rec = readExit(h.dir);
  assert.equal(rec.reason, "relaunch");
  assert.equal(rec.detail, "unhandled rejection: Error: three");
  // once: more errors do not relaunch again, and a quit keeps the record
  for (let i = 0; i < 5; i += 1) { h.proc.emit("uncaughtException", new Error("more")); }
  assert.equal(h.calls.relaunch, 1);
  Part.quit(h.ctx);
  assert.equal(readExit(h.dir).reason, "relaunch");
});

test("errors spread over more than 60 s never relaunch", () => {
  const h = harness();
  for (let i = 0; i < 6; i += 1) {
    h.proc.emit("uncaughtException", new Error("slow " + i));
    h.t.ms += 31000;
  }
  assert.equal(h.calls.relaunch, 0);
});

test("a client relaunched under 10 minutes ago does not relaunch again", () => {
  const dir = tmpDir();
  const start = 1800000000000;
  Guard.writeRecord(fs, dir, Guard.record("relaunch", "x", start - 5 * 60 * 1000, 1));
  const h = harness({ dir: dir, start: start });
  for (let i = 0; i < 3; i += 1) { h.proc.emit("uncaughtException", new Error("e" + i)); }
  assert.equal(h.calls.relaunch, 0);
  assert.ok(h.logs.some((l) => l.includes("no relaunch")));
  // an older relaunch record does not block it
  Guard.writeRecord(fs, dir, Guard.record("relaunch", "x", start - 11 * 60 * 1000, 1));
  const h2 = harness({ dir: dir, start: start });
  for (let i = 0; i < 3; i += 1) { h2.proc.emit("uncaughtException", new Error("e" + i)); }
  assert.equal(h2.calls.relaunch, 1);
  assert.equal(Guard.mayRelaunch(null, start), true);
  assert.equal(Guard.mayRelaunch({ reason: "crash", at: start / 1000 }, start), true);
  assert.equal(Guard.mayRelaunch({ reason: "relaunch", at: start / 1000 + 60 }, start), false);
});

test("a killed overlay renderer is rebuilt at most 3 times in 10 minutes, then the tray tooltip says so", () => {
  const h = harness();
  const win = fakeWin();
  h.setOverlay(win);
  Part.overlayWindow(h.ctx, win);
  for (let i = 0; i < 3; i += 1) {
    win.webContents.emit("render-process-gone", {}, { reason: "killed" });
    h.t.ms += 60000;
  }
  assert.equal(h.calls.restart, 3);
  assert.deepEqual(h.calls.tooltip, []);
  win.webContents.emit("unresponsive");
  assert.equal(h.calls.restart, 3);
  assert.deepEqual(h.calls.tooltip, [Guard.OVERLAY_STOPPED]);
  assert.ok(h.logs.some((l) => l.includes("overlay page failed") && l.includes("stopped")));
  // stopped stays stopped (no loop), and the tooltip is set once
  h.t.ms += 20 * 60000;
  win.webContents.emit("did-fail-load", {}, -105, "x", "file:///x", true);
  assert.equal(h.calls.restart, 3);
  assert.equal(h.calls.tooltip.length, 1);
  assert.ok(Guard.OVERLAY_STOPPED.length <= 127 && Guard.COMPANION_STOPPED.length <= 127);
});

test("the overlay rebuild cap is a sliding 10-minute window", () => {
  const h = harness();
  const win = fakeWin();
  h.setOverlay(win);
  Part.overlayWindow(h.ctx, win);
  for (let i = 0; i < 6; i += 1) {
    win.webContents.emit("render-process-gone", {}, { reason: "crashed" });
    h.t.ms += 4 * 60000;
  }
  assert.equal(h.calls.restart, 6);
  assert.deepEqual(h.calls.tooltip, []);
});

test("a replaced overlay window, a clean exit and an aborted load rebuild nothing", () => {
  const h = harness();
  const old = fakeWin();
  const cur = fakeWin();
  h.setOverlay(cur);
  Part.overlayWindow(h.ctx, old);
  old.webContents.emit("render-process-gone", {}, { reason: "killed" });
  assert.equal(h.calls.restart, 0);
  Part.overlayWindow(h.ctx, cur);
  cur.webContents.emit("render-process-gone", {}, { reason: "clean-exit" });
  cur.webContents.emit("did-fail-load", {}, -3, "aborted", "file:///x", true);
  cur.webContents.emit("did-fail-load", {}, -105, "x", "http://x", false);
  assert.equal(h.calls.restart, 0);
  // during a quit nothing is rebuilt
  h.app.emit("before-quit");
  cur.webContents.emit("render-process-gone", {}, { reason: "killed" });
  assert.equal(h.calls.restart, 0);
});

test("the companion reloads on render-process-gone, unresponsive and did-fail-load", () => {
  const h = harness();
  const win = fakeWin();
  Part.clientWindow(h.ctx, win);
  win.webContents.emit("render-process-gone", {}, { reason: "oom" });
  assert.equal(win.webContents.reloads, 1);
  win.webContents.emit("unresponsive");
  assert.equal(win.webContents.reloads, 2);
  win.webContents.emit("did-fail-load", {}, -3, "aborted", "http://127.0.0.1/", true);
  assert.equal(win.webContents.reloads, 2);
  win.webContents.emit("did-fail-load", {}, -102, "refused", "http://127.0.0.1/", true);
  assert.equal(win.webContents.reloads, 3);
  // the same cap: the fourth in 10 minutes stops and says so
  win.webContents.emit("unresponsive");
  assert.equal(win.webContents.reloads, 3);
  assert.deepEqual(h.calls.tooltip, [Guard.COMPANION_STOPPED]);
  // a destroyed companion is never reloaded
  const h2 = harness();
  const gone = fakeWin();
  Part.clientWindow(h2.ctx, gone);
  gone.destroyed = true;
  gone.webContents.emit("render-process-gone", {}, { reason: "killed" });
  assert.equal(gone.webContents.reloads, 0);
});

test("client-exit.json is written on quit, relaunch and crash", () => {
  const h = harness();
  h.proc.emit("uncaughtException", new Error("first"));
  assert.equal(readExit(h.dir).reason, "crash");
  Part.quit(h.ctx);
  const q = readExit(h.dir);
  assert.deepEqual(Object.keys(q).sort(), ["at", "detail", "pid", "reason"]);
  assert.equal(q.reason, "quit");
  assert.equal(q.detail, null);
  const h2 = harness();
  for (let i = 0; i < 3; i += 1) { h2.proc.emit("uncaughtException", new Error("e")); }
  assert.equal(readExit(h2.dir).reason, "relaunch");
  // atomic: no temp file is left; ASCII and LF only
  for (const d of [h.dir, h2.dir]) {
    assert.deepEqual(fs.readdirSync(d), [Guard.FILE_NAME]);
    const raw = fs.readFileSync(path.join(d, Guard.FILE_NAME), "latin1");
    assert.match(raw, /^[\x20-\x7e]*\n$/);
  }
  // no runtime dir: nothing written, nothing thrown
  assert.equal(Guard.writeRecord(fs, path.join(h.dir, Guard.FILE_NAME, "x"),
    Guard.record("quit", null, 0, 1)), false);
  assert.throws(() => Guard.record("stop", null, 0, 1));
});

test("details are one short ASCII line with no path", () => {
  assert.equal(Guard.cleanDetail(null), null);
  assert.equal(Guard.cleanDetail("   "), null);
  assert.equal(Guard.cleanDetail("at " + DRIVE + "\\a\\b.js and \\\\host\\share\\x and /home/u/x.js"),
    "at <path> and <path> and <path>");
  assert.equal(Guard.cleanDetail("two\nlines\u00e9"), "two lines?");
  const long = Guard.cleanDetail("x".repeat(400));
  assert.equal(long.length, Guard.DETAIL_MAX);
  assert.ok(long.endsWith("..."));
  assert.equal(Guard.readRecord(fs, path.join(tmpDir(), "none")), null);
});

test("the window counter counts inside its window only", () => {
  let t = 0;
  const c = Guard.windowCounter(2, 1000, () => t);
  assert.equal(c.take(), true);
  assert.equal(c.take(), true);
  assert.equal(c.take(), false);
  t = 1000;
  assert.equal(c.count(), 0);
  assert.equal(c.hit(), 1);
});
