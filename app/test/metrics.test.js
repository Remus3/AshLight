"use strict";
/* RUN-BUDGET-LOG-CLIENT (F-032): the client sums its own Electron process
   tree once a minute into ops/runtime/overlay-state.json. */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const M = require("../metrics.js");

const APP = path.resolve(__dirname, "..");

/* Rows shaped like Electron's ProcessMetric, with the identifying fields a
   row must never carry into the file. */
function rows() {
  return [
    { pid: 4242, type: "Browser", name: "secret-browser-name", creationTime: 1,
      cpu: { percentCPUUsage: 0.1, idleWakeupsPerSecond: 3 },
      memory: { workingSetSize: 60000, peakWorkingSetSize: 70000, privateBytes: 30000 },
      sandboxed: false, integrityLevel: "medium" },
    { pid: 4343, type: "Tab", name: "some\\dir\\renderer.exe", creationTime: 2,
      cpu: { percentCPUUsage: 0.05 }, memory: { workingSetSize: 50000, privateBytes: 25000 } },
    { pid: 4444, type: "Tab", serviceName: "renderer-svc",
      cpu: { percentCPUUsage: 0.0004 }, memory: { workingSetSize: 40000, privateBytes: 20000 } },
    { pid: 4545, type: "Utility", serviceName: "network.mojom.NetworkService", name: "Network Service",
      cpu: { percentCPUUsage: 0.01 }, memory: { workingSetSize: 15000, privateBytes: 8000 } },
    { pid: 4646, type: "Zygote", cpu: { percentCPUUsage: NaN }, memory: { workingSetSize: -5 } }
  ];
}

const made = [];
function tmpDir() {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), "al-metrics-"));
  made.push(d);
  return d;
}
test.after(() => { for (const d of made) { fs.rmSync(d, { recursive: true, force: true }); } });

test("rows are summed per own process type", () => {
  const doc = M.snapshot(rows(), { overlay_shown: true, companion_open: false },
    new Date("2026-11-20T10:00:00Z"));
  assert.strictEqual(doc.schema, 1);
  assert.strictEqual(doc.updated, "2026-11-20T10:00:00.000Z");
  assert.strictEqual(doc.period_s, 60);
  assert.strictEqual(doc.processes, 5);
  assert.strictEqual(doc.working_set_kb, 165000);
  assert.strictEqual(doc.private_kb, 83000);
  assert.strictEqual(doc.cpu_pct, 0.16);
  assert.deepStrictEqual(doc.by_type.tab, { count: 2, working_set_kb: 90000, private_kb: 45000, cpu_pct: 0.05 });
  assert.deepStrictEqual(doc.by_type.browser, { count: 1, working_set_kb: 60000, private_kb: 30000, cpu_pct: 0.1 });
  assert.deepStrictEqual(doc.by_type.utility, { count: 1, working_set_kb: 15000, private_kb: 8000, cpu_pct: 0.01 });
  // bad numbers count the process but add nothing
  assert.deepStrictEqual(doc.by_type.other, { count: 1, working_set_kb: 0, private_kb: 0, cpu_pct: 0 });
  assert.strictEqual(doc.overlay_shown, true);
  assert.strictEqual(doc.companion_open, false);
  assert.deepStrictEqual(Object.keys(doc.by_type).sort(), ["browser", "other", "tab", "utility"]);
});

test("no pid, path or name ever reaches the file", () => {
  const dir = tmpDir();
  const doc = M.snapshot(rows(), {}, new Date());
  const file = M.writeState(dir, doc);
  const text = fs.readFileSync(file, "ascii");
  for (const bad of ["pid", "4242", "4343", "name", "secret", "path", "renderer-svc",
                     "network", "Network", "mojom", "sandbox", "integrity", "creation", "renderer.exe", "dir", "\\\\"]) {
    assert.ok(!text.includes(bad), bad);
  }
  const keys = [];
  (function walk(o) {
    for (const k of Object.keys(o)) { keys.push(k); if (o[k] && typeof o[k] === "object") { walk(o[k]); } }
  })(JSON.parse(text));
  const allowed = new Set(["schema", "updated", "period_s", "processes", "working_set_kb", "private_kb",
    "cpu_pct", "by_type", "overlay_shown", "companion_open", "overlay_state", "count",
    ...Object.values(M.TYPE_KEYS), "other"]);
  for (const k of keys) { assert.ok(allowed.has(k), k); }
  // empty or broken input gives an all-zero document
  const empty = M.snapshot(null, null, new Date());
  assert.strictEqual(empty.processes, 0);
  assert.deepStrictEqual(empty.by_type, {});
  assert.strictEqual(empty.overlay_shown, false);
  assert.strictEqual(empty.overlay_state, "starting");
});

test("the write is atomic (tmp then rename), ASCII + LF, bounded", () => {
  const calls = [];
  const fake = {
    mkdirSync: (d) => calls.push(["mkdir", d]),
    writeFileSync: (f, t, o) => calls.push(["write", f, t, o.encoding]),
    renameSync: (a, b) => calls.push(["rename", a, b])
  };
  const doc = M.snapshot(rows(), { overlay_shown: false, companion_open: true }, new Date());
  const file = M.writeState("rt", doc, fake);
  assert.strictEqual(file, path.join("rt", "overlay-state.json"));
  assert.deepStrictEqual(calls.map((c) => c[0]), ["mkdir", "write", "rename"]);
  assert.strictEqual(calls[1][1], file + ".tmp");
  assert.strictEqual(calls[1][3], "ascii");
  assert.deepStrictEqual(calls[2].slice(1), [file + ".tmp", file]);
  const text = calls[1][2];
  assert.ok(/^[\x00-\x7f]*$/.test(text) && text.endsWith("}\n") && !text.includes("\r"));
  assert.ok(text.length <= M.MAX_BYTES, text.length);
  // the worst case: every type key present stays well inside the bound
  const every = Object.keys(M.TYPE_KEYS).concat(["Zygote"]).map((t) =>
    ({ type: t, cpu: { percentCPUUsage: 123456.789 }, memory: { workingSetSize: 9e12, privateBytes: 9e12 } }));
  const big = JSON.stringify(M.snapshot(every.concat(every), {}, new Date()), null, 1);
  assert.ok(big.length < M.MAX_BYTES / 2, big.length);
  // over the bound nothing is written
  const none = [];
  assert.throws(() => M.writeState("rt", { pad: "x".repeat(M.MAX_BYTES) },
    { mkdirSync: () => none.push(1), writeFileSync: () => none.push(1), renameSync: () => none.push(1) }));
  assert.strictEqual(none.length, 0);
  // a real write leaves no tmp file behind
  const dir = tmpDir();
  M.writeState(dir, doc);
  assert.deepStrictEqual(fs.readdirSync(dir), ["overlay-state.json"]);
});

function fakeTimers() {
  const t = { set: [], cleared: [] };
  t.setInterval = (fn, ms) => { const h = { fn: fn, ms: ms, unrefd: false, unref() { this.unrefd = true; } };
    t.set.push(h); return h; };
  t.clearInterval = (h) => t.cleared.push(h);
  return t;
}

test("one timer, 60 s, in the main process only", () => {
  const t = fakeTimers();
  let reads = 0;
  const written = [];
  const fsi = { mkdirSync() {}, writeFileSync: (f, txt) => written.push(JSON.parse(txt)), renameSync() {} };
  let overlay = { isDestroyed: () => false, isVisible: () => true };
  let companion = null;
  const s = M.createSampler({ getMetrics: () => { reads += 1; return rows(); }, dir: "rt", fs: fsi,
    overlay: () => overlay, companion: () => companion, log: () => {},
    setInterval: t.setInterval, clearInterval: t.clearInterval, processType: "browser" });
  assert.strictEqual(s.start(), true);
  assert.strictEqual(s.start(), false); // a second start keeps the one timer
  assert.strictEqual(t.set.length, 1);
  assert.strictEqual(t.set[0].ms, 60000);
  assert.strictEqual(M.PERIOD_MS, 60000);
  assert.ok(t.set[0].unrefd, "the timer never keeps the app alive");
  assert.strictEqual(reads, 1, "start only primes the CPU counters");
  assert.strictEqual(written.length, 0, "no file before the first full period");
  t.set[0].fn();
  assert.strictEqual(written.length, 1);
  assert.strictEqual(written[0].overlay_shown, true);
  assert.strictEqual(written[0].companion_open, false);
  // a hidden overlay and a minimised (still alive) companion
  overlay = { isDestroyed: () => false, isVisible: () => false };
  companion = { isDestroyed: () => false, isVisible: () => false };
  t.set[0].fn();
  assert.strictEqual(written[1].overlay_shown, false);
  assert.strictEqual(written[1].companion_open, true);
  s.stop();
  assert.deepStrictEqual(t.cleared, [t.set[0]]);
  assert.strictEqual(s.running(), false);
  s.stop();
  assert.strictEqual(t.cleared.length, 1);

  // a renderer (or plain node) never starts a sampler
  for (const ptype of ["renderer", "worker", undefined]) {
    const t2 = fakeTimers();
    const r = M.createSampler({ getMetrics: () => [], dir: "rt", fs: fsi, processType: ptype,
      setInterval: t2.setInterval, clearInterval: t2.clearInterval });
    assert.strictEqual(r.start(), false, String(ptype));
    assert.strictEqual(t2.set.length, 0);
  }
});

test("a failing sample is logged once and never throws into the timer", () => {
  const logged = [];
  let fail = true;
  const fsi = { mkdirSync() {}, writeFileSync() { if (fail) { throw new Error("disk full"); } }, renameSync() {} };
  const s = M.createSampler({ getMetrics: () => rows(), dir: "rt", fs: fsi, log: (m) => logged.push(m),
    processType: "browser", setInterval: () => null, clearInterval: () => {} });
  assert.strictEqual(s.sample(), null);
  assert.strictEqual(s.sample(), null);
  assert.strictEqual(logged.length, 1);
  assert.ok(logged[0].includes("disk full"));
  fail = false;
  assert.ok(s.sample());
  assert.strictEqual(logged.length, 2);
  const thrower = M.createSampler({ getMetrics: () => { throw new Error("no metrics"); }, dir: "rt",
    fs: fsi, log: () => {}, processType: "browser", setInterval: () => null, clearInterval: () => {} });
  assert.strictEqual(thrower.sample(), null);
});

test("the sampler is wired in the main process only, never in a page", () => {
  const main = fs.readFileSync(path.join(APP, "main.js"), "utf8");
  assert.strictEqual((main.match(/require\("\.\/metrics\.js"\)/g) || []).length, 1);
  assert.strictEqual((main.match(/Metrics\.startSampler\(/g) || []).length, 1);
  const startFn = main.slice(main.indexOf("function start()"), main.indexOf('app.on("will-quit"'));
  assert.ok(startFn.includes("Metrics.startSampler("), "the one call sits in start()");
  assert.ok(startFn.includes("app.getAppMetrics()"));
  const quit = main.slice(main.indexOf('app.on("will-quit"'));
  assert.ok(/metrics\.stop\(\)/.test(quit.slice(0, quit.indexOf("});"))), "stopped on will-quit");
  // no page script (overlay, shared, preloads, client pages, web) knows the sampler
  const pageDirs = [path.join(APP, "overlay"), path.join(APP, "shared"), path.join(APP, "..", "web")];
  const pageFiles = [path.join(APP, "preload.js"), path.join(APP, "client", "preload.js"),
                     path.join(APP, "client", "starting.js")];
  for (const d of pageDirs) {
    if (!fs.existsSync(d)) { continue; }
    for (const n of fs.readdirSync(d)) { if (/\.(js|html)$/.test(n)) { pageFiles.push(path.join(d, n)); } }
  }
  for (const f of pageFiles) {
    if (!fs.existsSync(f)) { continue; }
    const text = fs.readFileSync(f, "utf8");
    for (const word of ["metrics.js", "getAppMetrics", "overlay-state"]) {
      assert.ok(!text.includes(word), path.relative(APP, f) + ": " + word);
    }
  }
  // the module itself reads Electron's own tree only: no process listing, no spawn
  const mod = fs.readFileSync(path.join(APP, "metrics.js"), "utf8");
  for (const word of ["child_process", "tasklist", "Get-Process", "wmic", "process.kill",
                      "OpenProcess", "require(\"electron\")"]) {
    assert.ok(!mod.includes(word), word);
  }
});

/* RUN-EXPLAIN-OVERLAY-STATE (F-129): overlay_state from the gate. */
test("state field written on change, no screen or window query", () => {
  assert.strictEqual(M.snapshot([], { overlay_state: "hidden_idle" }, new Date()).overlay_state, "hidden_idle");
  assert.strictEqual(M.snapshot([], { overlay_state: "maximised" }, new Date()).overlay_state, "starting");
  assert.strictEqual(M.stateWord(undefined), "starting");
  const t = fakeTimers();
  const written = [];
  const logged = [];
  const fsi = { mkdirSync() {}, writeFileSync: (f, txt) => written.push(JSON.parse(txt)), renameSync() {} };
  let state = "starting";
  let stateReads = 0;
  let windowReads = 0;
  const overlay = { isDestroyed: () => { windowReads += 1; return false; }, isVisible: () => true };
  const s = M.createSampler({ getMetrics: () => rows(), dir: "rt", fs: fsi, log: (m) => logged.push(m),
    overlay: () => overlay, companion: () => null,
    overlayState: () => { stateReads += 1; return state; },
    setInterval: t.setInterval, clearInterval: t.clearInterval, processType: "browser" });
  // before start nothing is written (a renderer, or the sampler not yet up)
  assert.strictEqual(s.noteState(), false);
  assert.strictEqual(written.length, 0);
  s.start();
  // the first note writes the state at once
  assert.strictEqual(s.noteState(), true);
  assert.strictEqual(written.length, 1);
  assert.strictEqual(written[0].overlay_state, "starting");
  // unchanged: no write, the gate is the only thing read
  windowReads = 0;
  const before = stateReads;
  assert.strictEqual(s.noteState(), false);
  assert.strictEqual(written.length, 1);
  assert.strictEqual(windowReads, 0);
  assert.strictEqual(stateReads, before + 1);
  // a change writes once, with the hint in the log
  state = "hidden_idle";
  assert.strictEqual(s.noteState(), true);
  assert.strictEqual(s.noteState(), false);
  assert.strictEqual(written.length, 2);
  assert.strictEqual(written[1].overlay_state, "hidden_idle");
  assert.ok(logged.some((m) => m.startsWith("overlay state hidden_idle: ") && m.includes("game looks closed")));
  // the minute sample carries the field too
  state = "shown";
  t.set[0].fn();
  assert.strictEqual(written[2].overlay_state, "shown");
  assert.strictEqual(s.noteState(), false, "already written by the sample");
  // a throwing gate reads starting, never throws
  state = null;
  const bad = M.createSampler({ getMetrics: () => [], dir: "rt", fs: fsi, processType: "browser",
    overlayState: () => { throw new Error("gone"); }, setInterval: t.setInterval, clearInterval: t.clearInterval });
  bad.start();
  assert.doesNotThrow(() => bad.noteState());
  assert.strictEqual(written[written.length - 1].overlay_state, "starting");
  s.stop();
  assert.strictEqual(s.noteState(), false);
  // the module never looks at the screen or at any other window (code only)
  const mod = fs.readFileSync(path.join(APP, "metrics.js"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
  for (const word of ["screen.", "getAllDisplays", "getAllWindows", "getFocusedWindow", "FindWindow",
                      "EnumWindows", "GetForegroundWindow", "require(\"electron\")"]) {
    assert.ok(!mod.includes(word), word);
  }
  assert.match(mod, /require\("\.\/overlay_gate\.js"\)/);
});
