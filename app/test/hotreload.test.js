"use strict";
/* HOT-RELOAD (decision 0041): the overlay page reloads when its own files
   change, in a source checkout only; the watch is a stat poll in the main
   process, debounced, and the page gets no timer of its own. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const HR = require("../hotreload.js");

test("devEnabled: env, then config, then the .git entry", () => {
  const yes = () => true;
  const no = () => false;
  assert.equal(HR.devEnabled("/r", {}, () => ({}), yes), true);
  assert.equal(HR.devEnabled("/r", {}, () => ({}), no), false);
  assert.equal(HR.devEnabled("/r", {}, () => ({ hot_reload: false }), yes), false);
  assert.equal(HR.devEnabled("/r", {}, () => ({ hot_reload: true }), no), true);
  assert.equal(HR.devEnabled("/r", { AL_HOT_RELOAD: "0" }, () => ({ hot_reload: true }), yes), false);
  assert.equal(HR.devEnabled("/r", { AL_HOT_RELOAD: "1" }, () => ({}), no), true);
  assert.equal(HR.devEnabled("/r", {}, () => { throw new Error("bad"); }, no), false);
});

test("pageFiles: html / js / css only, bounded", () => {
  const list = (d) => (d === "a" ? ["x.js", "y.css", "z.html", "n.md"] : ["s.js"]);
  assert.deepEqual(HR.pageFiles(["a", "b"], list),
    [path.join("a", "x.js"), path.join("a", "y.css"), path.join("a", "z.html"),
     path.join("b", "s.js")]);
  const many = () => Array.from({ length: 500 }, (_, i) => "f" + i + ".js");
  assert.equal(HR.pageFiles(["a"], many).length, HR.MAX_FILES);
  assert.deepEqual(HR.pageFiles(["gone"], () => { throw new Error("x"); }), []);
});

test("watch: a burst of saves reloads once; stop unwatches", () => {
  const listeners = new Map();
  const timers = [];
  const deps = {
    watchFile: (f, opts, fn) => {
      assert.equal(opts.persistent, false);
      assert.equal(opts.interval, HR.INTERVAL_MS);
      listeners.set(f, fn);
    },
    unwatchFile: (f) => listeners.delete(f),
    setTimeout: (fn, ms) => { const t = { fn, ms, live: true }; timers.push(t); return t; },
    clearTimeout: (t) => { t.live = false; }
  };
  let reloads = 0;
  const stop = HR.watch(["a.js", "b.css"], () => { reloads += 1; }, deps);
  assert.equal(listeners.size, 2);
  const same = { mtimeMs: 1, size: 1 };
  listeners.get("a.js")(same, same);          // no change: nothing scheduled
  assert.equal(timers.length, 0);
  listeners.get("a.js")({ mtimeMs: 2, size: 1 }, same);
  listeners.get("b.css")({ mtimeMs: 3, size: 1 }, same);
  const live = timers.filter((t) => t.live);
  assert.equal(live.length, 1);
  assert.equal(live[0].ms, HR.DEBOUNCE_MS);
  live[0].fn();
  assert.equal(reloads, 1);
  stop();
  assert.equal(listeners.size, 0);
});

test("main.js wires the watch to a page reload, and the page has no timer for it", () => {
  const main = fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf8");
  assert.match(main, /HotReload\.devEnabled\(/);
  assert.match(main, /win\.webContents\.reload\(\)/);
  assert.match(main, /stopHotReload\(\)/);
  const page = fs.readFileSync(path.join(__dirname, "..", "overlay", "overlay.js"), "utf8");
  assert.doesNotMatch(page, /setInterval|location\.reload|"reload"/);
});
