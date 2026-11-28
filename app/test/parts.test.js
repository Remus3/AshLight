"use strict";
/* OVL-MAIN-PARTS (decision 0053): the main-process parts seam. */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const Parts = require("../parts.js");
const Hotkeys = require("../parts/20-hotkeys.js");

const APP = path.join(__dirname, "..");
const PARTS_DIR = path.join(APP, "parts");

function code(js) {
  return js.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

const MAIN = code(fs.readFileSync(path.join(APP, "main.js"), "utf8"));

function fakeDir(files) {
  const seen = [];
  return {
    readdirSync: () => Object.keys(files),
    req: (p) => { seen.push(path.basename(p)); return files[path.basename(p)]; },
    seen: seen
  };
}

test("parts load in file-name order, .js files only", () => {
  const d = fakeDir({ "30-zoom.js": { id: 30 }, "05-guard.js": { id: 5 },
                      "20-hotkeys.js": { id: 20 }, "notes.txt": {}, "10-x.json": {} });
  const parts = Parts.load("dir", d.readdirSync, d.req);
  assert.deepEqual(parts.map((p) => p.name), ["05-guard.js", "20-hotkeys.js", "30-zoom.js"]);
  assert.deepEqual(d.seen, ["05-guard.js", "20-hotkeys.js", "30-zoom.js"]);
  const calls = [];
  const mk = (n) => ({ ready: (ctx, a, b) => calls.push([n, ctx.tag, a, b]) });
  const ordered = Parts.load("dir", () => ["b.js", "a.js", "c.js"],
    (p) => mk(path.basename(p)));
  Parts.run(ordered, "ready", { tag: "ctx" }, 1, 2);
  assert.deepEqual(calls, [["a.js", "ctx", 1, 2], ["b.js", "ctx", 1, 2], ["c.js", "ctx", 1, 2]]);
});

test("a throwing part is logged and skipped; the others still run", () => {
  const logged = [];
  const ran = [];
  const parts = [
    { name: "10-bad.js", mod: { gate: () => { throw new Error("boom"); } } },
    { name: "20-good.js", mod: { gate: (ctx, v) => ran.push(v) } },
    { name: "30-none.js", mod: {} }
  ];
  Parts.run(parts, "gate", { log: (m) => logged.push(m) }, true);
  assert.deepEqual(ran, [true]);
  assert.deepEqual(logged, ["part 10-bad.js failed in gate: boom"]);
  // a part that fails to load is logged and left out
  const loadLog = [];
  const loaded = Parts.load("dir", () => ["a.js", "b.js"], (p) => {
    if (p.endsWith("a.js")) { throw new Error("syntax"); }
    return { ready: () => {} };
  }, (m) => loadLog.push(m));
  assert.deepEqual(loaded.map((p) => p.name), ["b.js"]);
  assert.deepEqual(loadLog, ["part a.js not loaded: syntax"]);
});

test("a missing parts dir is no parts", () => {
  const none = Parts.load(path.join(APP, "no-such-parts-dir"), fs.readdirSync, require);
  assert.deepEqual(none, []);
  Parts.run(none, "ready", { log: () => assert.fail("nothing to log") });
});

test("main.js runs every hook name, once each, from the places the seam names", () => {
  assert.deepEqual(Parts.HOOKS, ["early", "ready", "overlayWindow", "clientWindow",
    "configChanged", "gate", "toggled", "quit"]);
  for (const hook of Parts.HOOKS) {
    const n = (MAIN.match(new RegExp('runParts\\("' + hook + '"', "g")) || []).length;
    assert.equal(n, 1, hook);
  }
  assert.match(MAIN, /Parts\.load\(path\.join\(__dirname, "parts"\), fs\.readdirSync, require, log,\s+partFailures\)/);
  // early runs before the mode branch that ends in app.whenReady()
  assert.ok(MAIN.indexOf('runParts("early")') < MAIN.indexOf("if (!CLIENT_MODE && !OVERLAY_ALONE_TEST)"));
  // ready: after onEval is built, before the start line diag reads
  const ready = MAIN.indexOf('runParts("ready")');
  assert.ok(MAIN.indexOf("ctx.actions.onEval = onEval;") < ready);
  assert.ok(ready < MAIN.indexOf('log("overlay started;'));
  // the shortcuts are registered by the part, not by main.js
  assert.ok(!/globalShortcut\.register\(/.test(MAIN));
  assert.match(MAIN, /onWindow: \(w, s\) => runParts\("clientWindow", w, s\)/);
});

test("the hotkeys part registers the two keys with the same log sentences", () => {
  const reg = [];
  const logged = [];
  const toggle = () => {};
  const onEval = () => {};
  const ctx = { keys: { toggle: "Alt+Shift+A", eval: "Alt+Shift+E" },
                actions: { toggle: toggle, onEval: onEval }, log: (m) => logged.push(m) };
  Hotkeys.registerKeys({ register: (k, fn) => { reg.push([k, fn]); return true; } }, ctx);
  assert.deepEqual(reg, [["Alt+Shift+A", toggle], ["Alt+Shift+E", onEval]]);
  assert.deepEqual(logged, []);
  Hotkeys.registerKeys({ register: () => false }, ctx);
  assert.deepEqual(logged, ["toggle shortcut not available: Alt+Shift+A",
                            "item check shortcut not available: Alt+Shift+E"]);
});

test("every part is a plain module: no window, no clipboard, no timer, no process", () => {
  const names = fs.readdirSync(PARTS_DIR).filter((n) => n.endsWith(".js")).sort();
  assert.ok(names.includes("20-hotkeys.js"));
  for (const n of names) {
    assert.match(n, /^\d\d-[a-z0-9-]+\.js$/, n);
    const c = code(fs.readFileSync(path.join(PARTS_DIR, n), "utf8"));
    for (const banned of [/new\s+BrowserWindow\s*\(/, /clipboard/, /setInterval\(/,
                          /child_process/]) {
      assert.ok(!banned.test(c), n + " " + banned);
    }
    const mod = require(path.join(PARTS_DIR, n));
    assert.ok(Parts.HOOKS.some((h) => typeof mod[h] === "function"), n + " has no hook");
  }
  const real = Parts.load(PARTS_DIR, fs.readdirSync, require);
  assert.deepEqual(real.map((p) => p.name), names);
});
