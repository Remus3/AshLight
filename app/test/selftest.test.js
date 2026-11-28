"use strict";
/* REL-SELFTEST-CLIENT: the client half of the update self-test
   (app/selftest.js, the --selftest branch of app/main.js). */

const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");

const Parts = require("../parts.js");
const Selftest = require("../selftest.js");
const Egress = require("../parts/15-egress.js");

const APP = path.resolve(__dirname, "..");
const PARTS_DIR = path.join(APP, "parts");

function fakeElectron(opts) {
  const o = opts || {};
  const def = { name: "default", webRequest: { onBeforeRequest: () => {} } };
  const part = { name: "partition", webRequest: { onBeforeRequest: () => {} } };
  const exits = [];
  return {
    exits: exits,
    app: { whenReady: () => Promise.resolve(), exit: (code) => exits.push(code) },
    session: { defaultSession: def, fromPartition: () => part },
    BrowserWindow: { getAllWindows: () => new Array(o.windows || 0) },
    sessions: [def, part]
  };
}

function partsOf(table) {
  const failed = [];
  const parts = Parts.load("dir", () => Object.keys(table),
    (p) => { const f = table[path.basename(p)]; return typeof f === "function" ? f() : f; },
    () => {}, failed);
  return { parts: parts, failed: failed };
}

function egressPart(lockIt) {
  return {
    ready: (ctx) => {
      if (lockIt) {
        const s = ctx.electron.session;
        Egress.lock(ctx, s.defaultSession);
        Egress.lock(ctx, s.fromPartition("x"));
      }
    },
    isLocked: Egress.isLocked
  };
}

async function runWith(table, opts) {
  Egress.reset();
  const el = fakeElectron(opts);
  const loaded = partsOf(table);
  const ctx = { electron: el, port: 8961, log: () => {} };
  const early = Parts.run(loaded.parts, "early", ctx);
  const out = [];
  const v = await Selftest.start({
    app: el.app, session: el.session, BrowserWindow: el.BrowserWindow, Parts: Parts,
    parts: loaded.parts, ctx: ctx, partition: "persist:client",
    failures: loaded.failed.concat(early), out: { write: (s) => out.push(s) },
    setTimer: () => null
  });
  return { v: v, exits: el.exits, out: out };
}

test("wanted reads the --selftest switch only", () => {
  assert.strictEqual(Selftest.wanted(["electron.exe", ".", "--selftest"]), true);
  assert.strictEqual(Selftest.wanted(["electron.exe", ".", "--client"]), false);
  assert.strictEqual(Selftest.wanted(null), false);
});

test("load and run report every failing part", () => {
  const failed = [];
  const parts = Parts.load("dir", () => ["a.js", "b.js"], (p) => {
    if (p.endsWith("b.js")) { throw new Error("boom"); }
    return { early: () => { throw new Error("bad early"); } };
  }, () => {}, failed);
  assert.deepStrictEqual(failed, [{ name: "b.js", hook: "load", message: "boom" }]);
  const ran = Parts.run(parts, "early", { log: () => {} });
  assert.deepStrictEqual(ran, [{ name: "a.js", hook: "early", message: "bad early" }]);
  assert.deepStrictEqual(Parts.run(parts, "ready", {}), []);
});

test("every part loads, the egress lock is on, no window: exit 0", async () => {
  const r = await runWith({ "15-egress.js": egressPart(true), "20-x.js": { early: () => {} } });
  assert.deepStrictEqual(r.exits, [Selftest.EXIT.ok]);
  assert.deepStrictEqual(r.out, ["selftest: ok\n"]);
});

test("a part that throws while loading fails the stage", async () => {
  const r = await runWith({ "15-egress.js": egressPart(true),
                            "50-bad.js": () => { throw new Error("syntax"); } });
  assert.deepStrictEqual(r.exits, [Selftest.EXIT.part]);
  assert.match(r.out[0], /^selftest: part 50-bad\.js failed in load\n$/);
});

test("a part that throws in early or a safe ready hook fails the stage", async () => {
  const early = await runWith({ "15-egress.js": egressPart(true),
                                "50-bad.js": { early: () => { throw new Error("x"); } } });
  assert.deepStrictEqual(early.exits, [Selftest.EXIT.part]);
  const ready = await runWith({ "12-pages.js": { ready: () => { throw new Error("x"); } },
                                "15-egress.js": egressPart(true) });
  assert.deepStrictEqual(ready.exits, [Selftest.EXIT.part]);
});

test("ready runs only for the safe parts (no hotkey registration)", async () => {
  let hot = 0;
  const r = await runWith({ "15-egress.js": egressPart(true),
                            "20-hotkeys.js": { ready: () => { hot += 1; } } });
  assert.strictEqual(hot, 0);
  assert.deepStrictEqual(r.exits, [Selftest.EXIT.ok]);
});

test("egress lock off or missing fails, a window fails", async () => {
  const off = await runWith({ "15-egress.js": egressPart(false) });
  assert.deepStrictEqual(off.exits, [Selftest.EXIT.egress]);
  const none = await runWith({ "20-x.js": {} });
  assert.deepStrictEqual(none.exits, [Selftest.EXIT.egress]);
  const win = await runWith({ "15-egress.js": egressPart(true) }, { windows: 1 });
  assert.deepStrictEqual(win.exits, [Selftest.EXIT.window]);
});

test("the timer ends a run that never gets ready", async () => {
  const exits = [];
  let fire = null;
  const p = Selftest.start({
    app: { whenReady: () => new Promise(() => {}), exit: (c) => exits.push(c) },
    session: {}, BrowserWindow: {}, Parts: Parts, parts: [], ctx: {},
    setTimer: (fn) => { fire = fn; return null; }
  });
  fire();
  assert.deepStrictEqual(exits, [Selftest.EXIT.timeout]);
  assert.ok(p instanceof Promise);
});

test("the real parts all load and the egress part exposes isLocked", () => {
  const failed = [];
  const parts = Parts.load(PARTS_DIR, fs.readdirSync, require, () => {}, failed);
  assert.deepStrictEqual(failed, []);
  const names = fs.readdirSync(PARTS_DIR).filter((n) => n.endsWith(".js")).sort();
  assert.deepStrictEqual(parts.map((p) => p.name), names);
  assert.ok(names.includes(Selftest.EGRESS_PART));
  for (const n of Selftest.SAFE_READY) { assert.ok(names.includes(n), n); }
  assert.strictEqual(typeof Egress.isLocked, "function");
  assert.ok(Selftest.TIMEOUT_MS < 30000);
});

test("main.js runs the self-test before the single-instance lock and windows", () => {
  const src = fs.readFileSync(path.join(APP, "main.js"), "utf8");
  const at = src.indexOf("if (SELFTEST) {");
  assert.ok(at > 0);
  assert.ok(at < src.indexOf("requestSingleInstanceLock()"));
  assert.ok(at < src.indexOf("app.whenReady().then(start)"));
  assert.match(src, /Parts\.load\([^;]*partFailures\)/);
  assert.match(src, /SELFTEST && process\.env\.AL_SELFTEST_PROFILE/);
});
